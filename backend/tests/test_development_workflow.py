from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_persistence import environment, run

from app.models.schemas import Analysis, Change, Review
from app.services.development_workflow import DevelopmentWorkflow, WorkflowPause


def coordinator(db, projects, events):
    return DevelopmentWorkflow(SimpleNamespace(state=SimpleNamespace(db=db, projects=projects, events=events)))


def test_workflow_requests_isolation_and_explicit_retry_preserve_previous_steps():
    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, old, _):
            await events.status(old, "completado")
            service = coordinator(db, projects, events)
            request = {"id_solicitud": str(uuid4()), "objetivo": "Construir un catálogo público de productos", "desplegar_local": False}
            rid, created = await service.start(pid, request)
            assert created
            assert await service.start(pid, request) == (rid, False)
            with pytest.raises(ValueError, match="otro objetivo"):
                await service.start(pid, {**request, "objetivo": "Otro objetivo incompatible"})
            with pytest.raises(LookupError):
                await service.get(str(uuid4()), rid)
            with pytest.raises(ValueError, match="activa"):
                await service.start(pid, {**request, "id_solicitud": str(uuid4())})
            child = await events.create_run(pid, "mockups")
            await events.status(child, "error")
            await service.save(rid, {"analisis": {"completado": True}, "mockups": {"ejecucion": child, "fuentes": {"origen": 1}}})
            await events.status(rid, "error")
            await service.resume(pid, rid, retry=True)
            stored = await service.get(pid, rid)
            assert stored["estado"] == "pendiente"
            assert stored["pasos"]["analisis"]["completado"]
            assert stored["pasos"]["mockups"]["intentos_anteriores"] == [child]
            assert stored["pasos"]["mockups"]["reintentar"]
            assert (await db.one("SELECT status FROM executions WHERE id=%s", (child,)))["status"] == "error"
    run(scenario())


@pytest.mark.parametrize("mode", ["supervisado", "automatico"])
def test_business_questions_pause_both_modes_and_manual_requires_publication(mode):
    async def scenario():
        async with environment(mode) as (db, projects, events, pid, old, mid):
            service = coordinator(db, projects, events)
            changes = Analysis(cambios=[
                Change(operacion="crear", tipo="requisito_funcional", descripcion="Consultar productos disponibles del catálogo"),
                Change(operacion="crear", tipo="actor", descripcion="Cliente que consulta el catálogo"),
            ])
            proposed = await projects.propose(pid, old, mid, changes)
            if mode == "supervisado":
                with pytest.raises(WorkflowPause):
                    await service.baseline(pid, {"modo": mode})
                for item in proposed:
                    await projects.review(pid, item["id"], Review(accion="aprobar"))
                with pytest.raises(WorkflowPause, match="Publique"):
                    await service.baseline(pid, {"modo": mode})
                await projects.publish(pid, True)
            assert await service.baseline(pid, {"modo": mode}) == 1
            assert await service.baseline(pid, {"modo": mode}) == 1
            question = Analysis(cambios=[Change(operacion="crear", tipo="pregunta_pendiente", descripcion="¿Qué roles pueden modificar los precios del catálogo?")])
            await projects.propose(pid, old, mid, question)
            with pytest.raises(WorkflowPause):
                await service.baseline(pid, {"modo": mode})
    run(scenario())


def test_workflow_stops_before_any_generation_when_business_decision_missing():
    async def scenario():
        async with environment() as (db, projects, events, pid, old, _):
            await events.status(old, "completado")
            service = coordinator(db, projects, events)
            rid, _ = await service.start(pid, {"id_solicitud": str(uuid4()), "objetivo": "Sistema de reservas con reglas por definir", "desplegar_local": False})
            service.analyze = AsyncMock()
            service.phase = AsyncMock()
            await service.run(pid, rid)
            stored = await service.get(pid, rid)
            assert stored["estado"] == "esperando_revision"
            service.phase.assert_not_called()
    run(scenario())
