import os
from uuid import uuid4

import httpx
import pytest
from psycopg.errors import CheckViolation
from test_persistence import environment, run

from app.models.schemas import Analysis, Change


def test_soft_delete_restore_preserves_state_and_audit():
    async def scenario():
        async with environment("automatico") as (db, service, events, pid, rid, mid):
            await service.propose(
                pid,
                rid,
                mid,
                Analysis(
                    cambios=[
                        Change(
                            operacion="crear",
                            tipo="requisito_funcional",
                            descripcion="Conservar solicitudes de soporte",
                        )
                    ]
                ),
            )
            baseline = await service.publish(pid, False)
            await events.status(rid, "completado")
            before = await service.state(pid)
            await service.set_deleted(pid, True)
            assert pid not in {str(p["id_proyecto"]) for p in await service.list()}
            assert pid in {str(p["id_proyecto"]) for p in await service.trash()}
            with pytest.raises(LookupError):
                await service.get(pid)
            assert (await db.one("SELECT payload FROM baselines WHERE project_id=%s", (pid,)))[
                "payload"
            ] == baseline
            await service.set_deleted(pid, True)
            with pytest.raises(CheckViolation):
                await events.create_run(pid, "chat")
            await service.set_deleted(pid, False)
            await service.set_deleted(pid, False)
            restored = await service.state(pid)
            assert restored["elementos"] == before["elementos"]
            assert restored["propuestas"] == before["propuestas"]
            assert restored["lineas_base"] == before["lineas_base"]
            logs = await db.fetch(
                "SELECT operation FROM project_lifecycle_events WHERE project_id=%s ORDER BY id",
                (pid,),
            )
            assert [r["operation"] for r in logs] == ["eliminar", "restaurar"]

    run(scenario())


def test_active_execution_prevents_project_deletion():
    async def scenario():
        async with environment() as (db, service, events, pid, rid, mid):
            with pytest.raises(ValueError, match="tarea en curso"):
                await service.set_deleted(pid, True)
            assert await service.get(pid)
            assert not await db.one(
                "SELECT id FROM project_lifecycle_events WHERE project_id=%s", (pid,)
            )
            await events.status(rid, "error")
            await service.set_deleted(pid, True)
            # Un checkpoint detenido tampoco se puede reactivar dentro de la papelera.
            with pytest.raises(CheckViolation):
                await events.status(rid, "pendiente")

    run(scenario())


def test_project_trash_api_authentication_and_resource_guard(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url or "fabrica_test" not in url:
        pytest.skip("Requiere base separada fabrica_test")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("API_TOKEN", "acceso-pruebas-papelera")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app, lifespan

    async def scenario():
        async with (
            lifespan(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://prueba.local",
                headers={"Authorization": "Bearer acceso-pruebas-papelera"},
            ) as api,
        ):
            pid = (await api.post("/api/projects", json={"nombre": "Eliminar y restaurar"})).json()[
                "id_proyecto"
            ]
            base = f"/api/projects/{pid}"
            cid = (await api.post(base + "/conversations")).json()["id"]
            assert (
                await api.delete(base, headers={"Authorization": "Bearer incorrecto"})
            ).status_code == 401
            assert (await api.delete(base)).status_code == 200
            assert pid not in {p["id_proyecto"] for p in (await api.get("/api/projects")).json()}
            assert pid in {p["id_proyecto"] for p in (await api.get("/api/projects/trash")).json()}
            for path in (
                "/state",
                "/documents",
                "/backlog",
                "/mockups",
                "/conversations",
                f"/conversations/{cid}/messages",
                "/executions",
            ):
                assert (await api.get(base + path)).status_code == 404, path
            resume = await api.post(base + f"/executions/{uuid4()}/resume")
            assert resume.status_code == 404
            assert (
                await api.post(base + "/restore", headers={"Authorization": "Bearer incorrecto"})
            ).status_code == 401
            assert (await api.post(base + "/restore")).status_code == 200
            assert (await api.get(base + "/conversations")).json()[0]["id"] == cid
            assert (await api.get(base + "/state")).status_code == 200
            assert (await api.post(f"/api/projects/{uuid4()}/restore")).status_code == 404

    try:
        run(scenario())
    finally:
        get_settings.cache_clear()
