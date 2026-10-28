"""Verificación opcional de los tres agentes con Azure, exclusivamente en datos de prueba."""

import os

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from test_persistence import environment, run

from app.agents.backlog_team import BacklogTeam
from app.config import Settings
from app.models.schemas import Analysis, Change
from app.providers import Models
from app.services.backlog_service import BacklogService

pytestmark = pytest.mark.live


def test_real_azure_backlog_team_and_checkpoints():
    if not os.getenv("RUN_LIVE_BACKLOG"):
        pytest.skip("Active RUN_LIVE_BACKLOG=1; consume tokens de Azure")

    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            await projects.propose(
                pid,
                rid,
                mid,
                Analysis(
                    cambios=[
                        Change(
                            operacion="crear",
                            tipo="requisito_funcional",
                            descripcion="El empleado debe registrar una solicitud de soporte con una descripción para comunicar su necesidad de asistencia.",
                        ),
                        Change(
                            operacion="crear",
                            tipo="actor",
                            descripcion="Empleado que solicita soporte",
                        ),
                    ]
                ),
            )
            await projects.publish(pid, False)
            await db.execute("UPDATE projects SET mode='supervisado' WHERE id=%s", (pid,))
            service = BacklogService(db, events)
            models = Models(Settings())
            try:
                saver = AsyncPostgresSaver(db.pool)
                await saver.setup()
                team = BacklogTeam(service, models, events, saver)
                run_id = await events.create_run(pid, "backlog")
                initial = {
                    "project_id": pid,
                    "operation": "generar",
                    "version": None,
                    "execution_id": run_id,
                    "request": {
                        "version_linea_base": 1,
                        "instrucciones": "Organiza únicamente la capacidad de registro indicada, con una épica, una feature y una historia. No añadas autenticación ni seguimiento.",
                    },
                }
                result = await team.graph.ainvoke(initial, {"configurable": {"thread_id": run_id}})
                content = result["content"]
                assert content["version_esquema"] == "2.0"
                assert content["epicas"] and content["features"] and content["historias"]
                assert content["historias"][0]["actor"]["id"] == "ACT-001"
                assert content["historias"][0]["requisitos_origen"] == [
                    {"id": "RF-001", "version": 1}
                ]
                assert not (await service.get(pid, 1))["publicado"]
                snapshot = await team.graph.aget_state({"configurable": {"thread_id": run_id}})
                assert snapshot.values["content"] == content
                activity = await events.list(run_id)
                assert {"organizador_funcional", "historias_usuario", "validador_funcional"} <= {
                    e["componente"] for e in activity
                }
                await events.status(run_id, "completado", {"version_backlog": 1})
            finally:
                await models.close()

    run(scenario())
