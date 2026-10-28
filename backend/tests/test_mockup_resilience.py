import httpx
import pytest
from test_mockups import FakeModels, design_fixture, request, setup
from test_persistence import environment, run

from app.agents.mockup_team import MockupTeam
from app.config import Settings
from app.models.mockups import Design, DesignReview
from app.providers import Models, ProviderError


class FaultyModels(FakeModels):
    def __init__(self, fault):
        super().__init__()
        self.fault = fault

    async def json(self, messages, schema, max_tokens=None, max_attempts=2):
        assert max_attempts == 1, "El grafo controla todos los reintentos"
        self.calls.append(schema.__name__)
        attempt = self.calls.count(schema.__name__)
        if schema is Design:
            if self.fault == "invalid_contract" and attempt == 1:
                raise ProviderError(
                    "Contrato inválido", [{"loc": ["pantallas"], "type": "missing"}]
                )
            value = design_fixture()
            if self.fault == "normalize":
                value["pantallas"][0]["ids_historias"] = [" hu-001 ", "HU-001"]
                value["pantallas"][0]["controles"][0]["ids_criterios"] = [
                    "hu-001-ca-01",
                    "rf-001",
                    "rf-001",
                ]
            if self.fault == "structure" and attempt == 1 or self.fault == "always_structure":
                value["pantallas"][0]["controles"][0]["ids_criterios"] = ["HU-999-CA-01"]
            if self.fault == "question":
                value["preguntas"] = ["¿Qué nombre debe mostrar el portal?"]
            return Design.model_validate(value)
        if self.fault == "validator" and attempt == 1:
            return DesignReview.model_validate(
                {
                    "observaciones": [
                        {
                            "severidad": "error",
                            "descripcion": "Observación con ID incorrecto",
                            "ids_elementos": ["HU-999"],
                        }
                    ]
                }
            )
        if self.fault == "always_validator":
            raise ProviderError(
                "Contrato de revisión inválido", [{"loc": ["observaciones"], "type": "invalid"}]
            )
        return DesignReview()


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("normalize", ["Design", "DesignReview"]),
        ("invalid_contract", ["Design", "Design", "DesignReview"]),
        ("structure", ["Design", "Design", "DesignReview"]),
        ("validator", ["Design", "DesignReview", "DesignReview"]),
    ],
)
def test_predictable_errors_are_corrected_before_presenting_proposal(fault, expected):
    async def scenario():
        async with environment("supervisado") as (db, projects, events, pid, rid, mid):
            service, saver = await setup(db, projects, events, pid, rid, mid)
            models = FaultyModels(fault)
            team = MockupTeam(service, models, events, saver)
            run_id, _ = await service.start(pid, request())
            row = await db.one("SELECT input FROM executions WHERE id=%s", (run_id,))
            result = await team.graph.ainvoke(
                {**row["input"], "execution_id": run_id}, {"configurable": {"thread_id": run_id}}
            )
            assert result["content"]["validacion"]["puede_publicar"]
            assert models.calls == expected
            assert len(await service.list(pid)) == 1
            logs = await db.fetch("SELECT operation FROM events WHERE execution_id=%s", (run_id,))
            assert "prevalidar" in {r["operation"] for r in logs}
            if fault == "normalize":
                assert "normalizar_referencias" in {r["operation"] for r in logs}
                control = result["content"]["diseno"]["pantallas"][0]["controles"][0]
                assert control["ids_requisitos"] == ["RF-001"]
            assert (await service.get(pid, 1))["decision"] is None

    run(scenario())


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("always_structure", ["Design", "Design"]),
        ("always_validator", ["Design", "DesignReview", "DesignReview"]),
    ],
)
def test_invalid_technical_output_is_not_saved_as_user_proposal(fault, expected):
    async def scenario():
        async with environment("supervisado") as (db, projects, events, pid, rid, mid):
            service, saver = await setup(db, projects, events, pid, rid, mid)
            models = FaultyModels(fault)
            team = MockupTeam(service, models, events, saver)
            run_id, _ = await service.start(pid, request())
            row = await db.one("SELECT input FROM executions WHERE id=%s", (run_id,))
            with pytest.raises(ValueError, match="No tienes que corregir identificadores"):
                await team.graph.ainvoke(
                    {**row["input"], "execution_id": run_id},
                    {"configurable": {"thread_id": run_id}},
                )
            assert models.calls == expected
            assert await service.list(pid) == []
            assert await db.one(
                "SELECT id FROM events WHERE execution_id=%s AND operation='propuesta_no_admitida'",
                (run_id,),
            )

    run(scenario())


def test_real_user_question_does_not_trigger_pointless_generation():
    async def scenario():
        async with environment("supervisado") as (db, projects, events, pid, rid, mid):
            service, saver = await setup(db, projects, events, pid, rid, mid)
            models = FaultyModels("question")
            team = MockupTeam(service, models, events, saver)
            run_id, _ = await service.start(pid, request())
            row = await db.one("SELECT input FROM executions WHERE id=%s", (run_id,))
            result = await team.graph.ainvoke(
                {**row["input"], "execution_id": run_id}, {"configurable": {"thread_id": run_id}}
            )
            assert models.calls == ["Design", "DesignReview"]
            assert not result["content"]["validacion"]["puede_publicar"]
            assert result["content"]["diseno"]["preguntas"]

    run(scenario())


def test_provider_can_disable_hidden_retries_without_network():
    async def scenario():
        calls = []

        def transport(req):
            calls.append(req)
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [{"content": [{"type": "output_text", "text": "{}"}]}],
                },
            )

        models = Models(Settings(llm_base_url="https://example.invalid", llm_model="prueba"))
        await models.client.aclose()
        models.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(ProviderError):
                await models.json([], Design, max_attempts=1)
            assert len(calls) == 1
        finally:
            await models.close()

    run(scenario())
