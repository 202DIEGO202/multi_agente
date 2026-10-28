from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import Error
from test_backlog_persistence import seed
from test_persistence import environment, run

from app.agents.mockup_team import MockupTeam
from app.models.backlog import ReviewBacklog
from app.models.mockups import Design, DesignReview, GenerateMockups, ReviewMockups
from app.services.mockup_service import MockupService, assess_design, merge_design


def design_fixture(second=False):
    screens = [
        {
            "id": "PA-001",
            "titulo": "Solicitud de soporte",
            "descripcion": "Registrar una solicitud con descripción",
            "ids_historias": ["HU-001"],
            "controles": [
                {
                    "clave": "descripcion",
                    "tipo": "entrada",
                    "etiqueta": "Descripción de la solicitud",
                    "obligatorio": True,
                    "ids_criterios": ["HU-001-CA-01"],
                },
                {"clave": "enviar", "tipo": "boton", "etiqueta": "Registrar solicitud"},
            ],
        }
    ]
    if second:
        screens.append(
            {
                "id": "PA-002",
                "titulo": "Ayuda de soporte",
                "descripcion": "Consulta de ayuda",
                "ids_historias": ["HU-001"],
                "controles": [
                    {"clave": "ayuda", "tipo": "texto", "etiqueta": "Describe tu necesidad"}
                ],
            }
        )
    return Design.model_validate({"pantallas": screens}).model_dump(mode="json")


class FakeModels:
    settings = SimpleNamespace(
        llm_model="modelo-controlado", llm_provider="prueba-sin-red", mockup_max_tokens=6144
    )

    def __init__(self, always_fail=False):
        self.calls = []
        self.always_fail = always_fail
        self.target = False

    async def json(self, messages, schema, max_tokens=None, max_attempts=2):
        self.calls.append(schema.__name__)
        if schema is Design:
            result = design_fixture(second=not self.target)
            if self.target:
                result["pantallas"][0]["titulo"] = "Solicitud simplificada"
            return Design.model_validate(result)
        if schema is DesignReview:
            if self.always_fail:
                return DesignReview.model_validate(
                    {
                        "observaciones": [
                            {
                                "severidad": "error",
                                "descripcion": "Falta aclarar un mensaje",
                                "ids_elementos": ["PA-001"],
                            }
                        ]
                    }
                )
            return DesignReview()
        raise AssertionError("No debe llamarse a otro modelo")


async def setup(db, projects, events, pid, rid, mid):
    backlog, _ = await seed(db, projects, events, pid, rid, mid)
    await backlog.review(pid, 1, ReviewBacklog(accion="aprobar", nota="Origen aprobado de prueba"))
    service = MockupService(db, events, backlog)
    saver = AsyncPostgresSaver(db.pool)
    await saver.setup()
    return service, saver


async def execute(service, team, events, pid, request):
    rid, created = await service.start(pid, request)
    assert created
    row = await service.db.one("SELECT input FROM executions WHERE id=%s", (rid,))
    await events.status(rid, "ejecutando")
    result = await team.graph.ainvoke(
        {**row["input"], "execution_id": rid}, {"configurable": {"thread_id": rid}}
    )
    await events.status(rid, "completado", result["content"])
    return rid, result["content"]


def request(**kwargs):
    return GenerateMockups(version_backlog=1, id_solicitud=uuid4(), **kwargs).model_dump(
        mode="json"
    )


def test_design_coverage_navigation_palette_and_scope():
    backlog = {
        "historias": [
            {
                "id": "HU-001",
                "criterios_aceptacion": [{"id": "HU-001-CA-01"}],
                "requisitos_origen": [],
            }
        ]
    }
    design = design_fixture(second=True)
    assert assess_design(design, backlog, {})["puede_publicar"]
    broken = deepcopy(design)
    broken["pantallas"][0]["controles"][0]["ids_criterios"] = []
    broken["pantallas"][0]["controles"][1]["destino"] = "PA-999"
    broken["paleta"]["texto"] = "#FFFFFF"
    report = assess_design(broken, backlog, {})
    assert not report["puede_publicar"]
    assert report["criterios_sin_representacion"] == ["HU-001-CA-01"]
    targeted = deepcopy(design)
    targeted["pantallas"] = targeted["pantallas"][:1]
    targeted["pantallas"][0]["titulo"] = "Solicitud simplificada"
    targeted["paleta"]["acento"] = "#000000"
    merged = merge_design(targeted, design, "PA-001")
    assert merged["pantallas"][1] == design["pantallas"][1]
    assert merged["paleta"] == design["paleta"]
    with pytest.raises(ValueError):
        merge_design(design, design, "PA-001")
    with pytest.raises(ValueError):
        assess_design(
            design,
            backlog,
            {
                "observaciones": [
                    {
                        "severidad": "error",
                        "descripcion": "Una observación",
                        "ids_elementos": ["RF-999"],
                    }
                ]
            },
        )


def test_mockup_graph_targeted_revision_approval_and_immutable_history():
    async def scenario():
        async with environment("supervisado") as (db, projects, events, pid, rid, mid):
            service, saver = await setup(db, projects, events, pid, rid, mid)
            models = FakeModels()
            team = MockupTeam(service, models, events, saver)
            body = request()
            run_id, content = await execute(service, team, events, pid, body)
            assert models.calls == ["Design", "DesignReview"]
            assert content["validacion"]["puede_publicar"]
            assert content["historias_origen"] == [{"id": "HU-001", "version": 1}]
            assert await service.start(pid, body) == (run_id, False)
            with pytest.raises(ValueError, match="otros datos"):
                await service.start(pid, {**body, "instrucciones": "Diferente"})
            await service.review(pid, 1, ReviewMockups(accion="aprobar", nota="Diseño revisado"))
            models.target = True
            _, second = await execute(
                service,
                team,
                events,
                pid,
                request(pantalla_id="PA-001", version_base=1, instrucciones="Simplificar"),
            )
            assert second["diseno"]["pantallas"][0]["version"] == 2
            assert second["diseno"]["pantallas"][1] == content["diseno"]["pantallas"][1]
            assert (await service.get(pid, 1))["payload"] == content
            assert (await service.get(pid, 1))["decision"] == "aprobado_por_humano"
            await service.view(pid, 2, "PA-001")
            logs = await db.fetch(
                "SELECT operation,data FROM events WHERE execution_id=%s", (second["id_ejecucion"],)
            )
            assert {r["operation"] for r in logs} >= {
                "disenar",
                "validar_diseno",
                "resultado_validacion",
                "guardar_revision",
                "pantalla_visualizada",
            }
            assert models.calls == ["Design", "DesignReview", "Design", "DesignReview"]
            with pytest.raises(Error, match="inmutables"):
                await db.execute(
                    "UPDATE mockup_revisions SET payload='{}' WHERE project_id=%s", (pid,)
                )
            with pytest.raises(LookupError):
                await service.get(str(uuid4()), 1)
            with pytest.raises(ValueError, match="última revisión"):
                await service.start(pid, request(pantalla_id="PA-001", version_base=1))

    run(scenario())


def test_valid_design_is_approved_automatically_only_in_automatic_mode():
    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            service, saver = await setup(db, projects, events, pid, rid, mid)
            await db.execute("UPDATE projects SET mode='automatico' WHERE id=%s", (pid,))
            team = MockupTeam(service, FakeModels(), events, saver)
            _, content = await execute(service, team, events, pid, request())
            result = await service.get(pid, content["version_mockup"])
            assert result["decision"] == "validado_automaticamente"
            assert "sin bloqueos ni preguntas" in result["nota"]
            with pytest.raises(ValueError, match="decisión registrada"):
                await service.review(
                    pid,
                    content["version_mockup"],
                    ReviewMockups(accion="aprobar", nota="Aprobación duplicada"),
                )

    run(scenario())


def test_one_automatic_correction_then_human_block():
    async def scenario():
        async with environment("supervisado") as (db, projects, events, pid, rid, mid):
            service, saver = await setup(db, projects, events, pid, rid, mid)
            models = FakeModels(always_fail=True)
            team = MockupTeam(service, models, events, saver)
            run_id, content = await execute(service, team, events, pid, request())
            assert models.calls == ["Design", "DesignReview", "Design", "DesignReview"]
            assert content["correcciones_automaticas"] == 1
            assert not content["validacion"]["puede_publicar"]
            assert await db.one(
                "SELECT id FROM events WHERE execution_id=%s AND operation='limite_correcciones'",
                (run_id,),
            )
            with pytest.raises(ValueError, match="errores"):
                await service.review(pid, 1, ReviewMockups(accion="aprobar", nota="No debe pasar"))
            await service.review(
                pid, 1, ReviewMockups(accion="rechazar", nota="Necesita correcciones")
            )
            assert (await service.get(pid, 1))["decision"] == "descartado"

    run(scenario())


def test_stale_sources_active_job_and_partial_persistence():
    async def scenario():
        async with environment("supervisado") as (db, projects, events, pid, rid, mid):
            service, saver = await setup(db, projects, events, pid, rid, mid)
            run_id, _ = await service.start(pid, request())
            with pytest.raises(ValueError, match="en curso"):
                await service.start(pid, request())
            await events.status(run_id, "error")
            models = FakeModels()
            team = MockupTeam(service, models, events, saver)
            _, content = await execute(service, team, events, pid, request())
            await db.execute(
                "UPDATE projects SET state_revision=state_revision+1 WHERE id=%s", (pid,)
            )
            assert (await service.get(pid, 1))["desactualizado"]
            with pytest.raises(ValueError, match="desactualizado"):
                await service.review(
                    pid, 1, ReviewMockups(accion="aprobar", nota="No debe aprobar")
                )
            with pytest.raises(ValueError, match="desactualizado"):
                await service.start(pid, request())
            assert len(await service.list(pid)) == 1

    run(scenario())


def test_checkpoint_resume_does_not_repeat_completed_designer():
    class InterruptedModels(FakeModels):
        def __init__(self):
            super().__init__()
            self.failed = False

        async def json(self, messages, schema, max_tokens=None, max_attempts=2):
            if schema is DesignReview and not self.failed:
                self.failed = True
                raise RuntimeError("Fallo controlado sin red")
            return await super().json(messages, schema, max_tokens)

    async def scenario():
        async with environment("supervisado") as (db, projects, events, pid, rid, mid):
            service, saver = await setup(db, projects, events, pid, rid, mid)
            models = InterruptedModels()
            team = MockupTeam(service, models, events, saver)
            run_id, _ = await service.start(pid, request())
            row = await db.one("SELECT input FROM executions WHERE id=%s", (run_id,))
            config = {"configurable": {"thread_id": run_id}}
            with pytest.raises(RuntimeError, match="Fallo controlado"):
                await team.graph.ainvoke({**row["input"], "execution_id": run_id}, config)
            assert await service.list(pid) == []
            result = await team.graph.ainvoke(None, config)
            assert result["content"]["validacion"]["puede_publicar"]
            assert models.calls == ["Design", "DesignReview"]
            assert len(await service.list(pid)) == 1

    run(scenario())


def test_requirement_ids_are_separated_without_ignoring_unknown_criteria():
    from app.services.mockup_service import normalize_design_references

    backlog = {
        "historias": [
            {
                "id": "HU-001",
                "requisitos_origen": [{"id": "RNF-001"}],
                "criterios_aceptacion": [{"id": "HU-001-CA-01"}],
            }
        ]
    }
    design = design_fixture()
    control = design["pantallas"][0]["controles"][0]
    control["ids_criterios"].append("RNF-001")
    fixed = normalize_design_references(design, backlog)
    assert fixed["pantallas"][0]["controles"][0]["ids_requisitos"] == ["RNF-001"]
    assert assess_design(fixed, backlog, {})["puede_publicar"]
    fixed["pantallas"][0]["controles"][0]["ids_criterios"].append("HU-999-CA-01")
    assert not assess_design(normalize_design_references(fixed, backlog), backlog, {})[
        "puede_publicar"
    ]


def test_visual_criterion_belongs_to_screen_style_without_a_fake_notice():
    backlog = {
        "historias": [
            {
                "id": "HU-001",
                "requisitos_origen": [],
                "criterios_aceptacion": [{"id": "HU-001-CA-01"}],
            }
        ]
    }
    design = design_fixture()
    design["pantallas"][0]["controles"][0]["ids_criterios"] = []
    assert not assess_design(design, backlog, {})["puede_publicar"]
    design["pantallas"][0]["ids_criterios_visuales"] = ["HU-001-CA-01"]
    assert assess_design(design, backlog, {})["puede_publicar"]
    design["pantallas"][0]["ids_criterios_visuales"] = ["HU-002-CA-01"]
    assert not assess_design(design, backlog, {})["puede_publicar"]
