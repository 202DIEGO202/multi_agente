from types import SimpleNamespace

import pytest
from backlog_fixtures import content_fixture
from test_backlog_persistence import seed
from test_persistence import environment, run

from app.agents.backlog_team import BacklogTeam
from app.models.backlog import ReviewBacklog, SemanticReview
from app.services.backlog_logic import UnknownReviewReference, validate_backlog


def test_retired_ids_can_be_reviewed_without_becoming_valid_current_sources():
    from backlog_fixtures import context_fixture

    context = context_fixture()
    candidate, _ = content_fixture(context)
    review = SemanticReview.model_validate(
        {
            "observaciones": [
                {
                    "severidad": "advertencia",
                    "codigo": "HISTORIA",
                    "descripcion": "El requisito anterior fue descartado",
                    "ids_elementos": [" rf-002 ", "hu-001-ca-1"],
                }
            ]
        }
    )
    result = validate_backlog(candidate, context["baseline"], review, {"RF-002"})
    assert result.validacion.observaciones[-1].ids_elementos == ["RF-002", "HU-001-CA-01"]
    with pytest.raises(UnknownReviewReference):
        validate_backlog(candidate, context["baseline"], review)
    candidate["historias"][0]["requisitos_origen"].append({"id": "RF-002", "version": 1})
    result = validate_backlog(candidate, context["baseline"], SemanticReview(), {"RF-002"})
    assert any(f.codigo == "ORIGEN_INVALIDO" for f in result.validacion.observaciones)


@pytest.mark.parametrize("always_invalid", [False, True])
def test_validator_repairs_its_contract_or_saves_explicitly_unvalidated_draft(always_invalid):
    class Models:
        settings = SimpleNamespace(
            llm_model="sin-red", llm_provider="simulado", backlog_max_tokens=4096
        )
        calls = 0

        async def json(self, messages, schema, max_tokens=None, max_attempts=2):
            assert schema is SemanticReview
            assert max_attempts == 1
            self.calls += 1
            if always_invalid or self.calls == 1:
                return SemanticReview.model_validate(
                    {
                        "observaciones": [
                            {
                                "severidad": "error",
                                "codigo": "ERROR_ID",
                                "descripcion": "Observación con referencia inexistente",
                                "ids_elementos": ["RF-999"],
                            }
                        ]
                    }
                )
            return SemanticReview()

    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            service, _ = await seed(db, projects, events, pid, rid, mid)
            context = await service.context(pid, "generar", 1)
            run_id = await events.create_run(pid, "backlog")
            candidate, counters = content_fixture(context, run_id)
            models = Models()
            team = BacklogTeam(service, models, events, None)
            result = await team.validate(
                {
                    "project_id": pid,
                    "execution_id": run_id,
                    "context": context,
                    "candidate": candidate,
                }
            )
            assert models.calls == 2
            saved = await service.persist(context, result["content"], counters)
            assert saved["version_backlog"] == 2
            if always_invalid:
                assert saved["validacion"]["semantica"] == "pendiente"
                assert not saved["validacion"]["puede_publicar"]
                with pytest.raises(ValueError):
                    await service.review(
                        pid, 2, ReviewBacklog(accion="aprobar", nota="No debe aprobarse")
                    )
            else:
                assert saved["validacion"]["puede_publicar"]
            logs = await db.fetch("SELECT operation FROM events WHERE execution_id=%s", (run_id,))
            assert sum(r["operation"] == "contrato_revision" for r in logs) == 2

    run(scenario())
