from uuid import uuid4

import pytest
from backlog_fixtures import content_fixture
from psycopg import Error
from psycopg.types.json import Jsonb
from test_persistence import environment, run

from app.models.backlog import ReviewBacklog, SemanticReview
from app.models.schemas import Analysis, Change, Review
from app.services.backlog_logic import prepare_existing, validate_backlog
from app.services.backlog_service import BacklogService

pytestmark = pytest.mark.integration


async def seed(db, projects, events, pid, rid, mid, mode="supervisado"):
    await projects.propose(
        pid,
        rid,
        mid,
        Analysis(
            cambios=[
                Change(
                    operacion="crear",
                    tipo="requisito_funcional",
                    descripcion="Registrar solicitudes de soporte con descripción",
                ),
                Change(operacion="crear", tipo="actor", descripcion="Empleado"),
            ]
        ),
    )
    project = await projects.get(pid)
    if project["modo"] == "supervisado":
        for proposal in (await projects.state(pid))["propuestas"]:
            if proposal["estado"] == "propuesto":
                await projects.review(pid, proposal["id"], Review(accion="aprobar"))
    await projects.publish(pid, project["modo"] == "supervisado")
    await db.execute("UPDATE projects SET mode=%s WHERE id=%s", (mode, pid))
    service = BacklogService(db, events)
    context = await service.context(pid, "generar", 1)
    run_id = await events.create_run(pid, "backlog")
    content, counters = content_fixture(context, run_id)
    await service.persist(context, content, counters)
    await events.status(run_id, "completado")
    return service, content


def test_review_publication_edit_history_and_immutable_contracts():
    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            service, content = await seed(db, projects, events, pid, rid, mid)
            assert (await service.get(pid, 1))["estado"] == "propuesto"
            await service.review(
                pid, 1, ReviewBacklog(accion="aprobar", nota="Revisado por el usuario de prueba")
            )
            published = await service.publication(pid, 1)
            assert published["estado"] == "aprobado_por_humano"
            context = await service.context(pid, "editar", version=1)
            run_id = await events.create_run(pid, "backlog")
            candidate, counters = prepare_existing(
                context,
                run_id,
                {
                    "id_elemento": "FE-001",
                    "titulo": "Recepción de solicitudes",
                    "descripcion": "Registrar solicitudes con descripción",
                    "ids_requisitos": ["RF-001"],
                    "id_padre": "EP-001",
                    "nota": "Ajuste humano del nombre",
                },
            )
            revised = validate_backlog(candidate, context["baseline"], SemanticReview()).model_dump(
                mode="json"
            )
            await service.persist(context, revised, counters)
            await events.status(run_id, "completado")
            assert (await service.get(pid, 2))["estado"] == "propuesto"
            history = await service.history(pid, "FE-001")
            assert [h["elemento"]["version"] for h in history] == [1, 2]
            assert await service.publication(pid, 1) == published
            assert content["features"][0]["version"] == 1
            with pytest.raises(Error, match="inmutables"):
                await db.execute(
                    "UPDATE backlog_revisions SET payload=%s WHERE project_id=%s AND version=1",
                    (Jsonb({}), pid),
                )
            with pytest.raises(LookupError):
                await service.get(str(uuid4()), 1)
            assert (await service.get(pid, 2))["cambios"]["modificados"] == ["FE-001"]

    run(scenario())


def test_automatic_publication_is_explicitly_not_human():
    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            service, _ = await seed(db, projects, events, pid, rid, mid, mode="automatico")
            assert (await service.publication(pid, 1))["estado"] == "validado_automaticamente"
            assert (await service.get(pid, 1))["decision"]["estado"] == "validado_automaticamente"
            with pytest.raises(ValueError, match="decisión"):
                await service.review(
                    pid, 1, ReviewBacklog(accion="aprobar", nota="Intento de repetir decisión")
                )

    run(scenario())


def test_source_changes_mark_impacts_and_block_stale_approval_and_generation():
    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            service, original = await seed(db, projects, events, pid, rid, mid)
            await db.execute("UPDATE projects SET mode='automatico' WHERE id=%s", (pid,))
            changed_run = await events.create_run(pid, "chat")
            await projects.propose(
                pid,
                changed_run,
                mid,
                Analysis(
                    cambios=[
                        Change(
                            operacion="modificar",
                            tipo="requisito_funcional",
                            id_elemento="RF-001",
                            version_esperada=1,
                            descripcion="Registrar solicitudes con descripción y prioridad",
                        )
                    ]
                ),
            )
            state = await service.get(pid, 1)
            assert state["desactualizado"]
            assert state["origenes_modificados"] == ["RF-001"]
            assert set(state["elementos_afectados"]) == {"EP-001", "FE-001", "HU-001"}
            with pytest.raises(ValueError, match="desactualizada"):
                await service.review(
                    pid, 1, ReviewBacklog(accion="aprobar", nota="Aprobación obsoleta")
                )
            with pytest.raises(ValueError, match="desactualizada"):
                await service.context(pid, "generar", 1)
            assert (await service.get(pid, 1))["contrato"] == original

    run(scenario())


def test_no_partial_persistence_when_source_changes_during_generation():
    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            service, _ = await seed(db, projects, events, pid, rid, mid)
            context = await service.context(pid, "generar", 1)
            generation_run = await events.create_run(pid, "backlog")
            content, counters = content_fixture(context, generation_run)
            await db.execute(
                "UPDATE projects SET state_revision=state_revision+1 WHERE id=%s", (pid,)
            )
            with pytest.raises(ValueError, match="cambió"):
                await service.persist(context, content, counters)
            assert len(await service.list(pid)) == 1
            stored = await db.one("SELECT counters FROM projects WHERE id=%s", (pid,))
            assert stored["counters"]["EP"] == 1

    run(scenario())


def test_request_replay_and_active_execution_are_controlled():
    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            service, _ = await seed(db, projects, events, pid, rid, mid)
            request = {"version_linea_base": 1, "id_solicitud": str(uuid4()), "instrucciones": ""}
            run_id, created = await service.start(pid, "generar", request)
            same, created_again = await service.start(pid, "generar", request)
            assert created and not created_again and same == run_id
            with pytest.raises(ValueError, match="otro contenido"):
                await service.start(pid, "generar", {**request, "instrucciones": "Otra propuesta"})
            with pytest.raises(ValueError, match="activa"):
                await service.start(pid, "generar", {**request, "id_solicitud": str(uuid4())})

    run(scenario())
