import asyncio
import os
from uuid import uuid4

import httpx
import pytest
from test_backlog_persistence import seed
from test_mockups import FakeModels
from test_persistence import run

from app.models.backlog import ReviewBacklog


def test_mockups_api_authorization_events_view_and_review(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url or "fabrica_test" not in url:
        pytest.skip("Requiere base de pruebas separada")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("API_TOKEN", "clave-de-prueba-mockups")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app, lifespan
    from app.providers import Models

    models = FakeModels()

    async def fake_json(self, messages, schema, rewrite=False, max_tokens=None, max_attempts=2):
        return await models.json(messages, schema, max_tokens)

    monkeypatch.setattr(Models, "json", fake_json)

    async def scenario():
        async with (
            lifespan(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://prueba.local",
                headers={"Authorization": "Bearer clave-de-prueba-mockups"},
            ) as api,
        ):
            pid = (
                await api.post(
                    "/api/projects", json={"nombre": "Mockups API prueba", "modo": "supervisado"}
                )
            ).json()["id_proyecto"]
            base = f"/api/projects/{pid}"
            body = {"version_backlog": 1, "id_solicitud": str(uuid4())}
            missing = await api.post(base + "/mockups/generate", json=body)
            assert missing.status_code == 409
            cid = (await api.post(base + "/conversations")).json()["id"]
            rid = await app.state.events.create_run(pid, "chat", conversation_id=cid)
            mid = str(uuid4())
            await app.state.db.execute(
                "INSERT INTO messages(id,conversation_id,execution_id,role,content) VALUES(%s,%s,%s,'user','Prueba de interfaces')",
                (mid, cid, rid),
            )
            backlog, _ = await seed(
                app.state.db, app.state.projects, app.state.events, pid, rid, mid
            )
            await backlog.review(
                pid, 1, ReviewBacklog(accion="aprobar", nota="Publicado para pruebas")
            )
            started = await api.post(base + "/mockups/generate", json=body)
            assert started.status_code == 202
            run_id = started.json()["id_ejecucion"]
            await asyncio.gather(*list(app.state.tasks))
            result = (await api.get(base + "/mockups/1")).json()
            assert result["payload"]["validacion"]["puede_publicar"]
            assert result["decision"] is None
            replay = await api.post(base + "/mockups/generate", json=body)
            assert replay.json()["id_ejecucion"] == run_id
            assert models.calls == ["Design", "DesignReview"]
            view = await api.post(base + "/mockups/1/view", json={"pantalla_id": "PA-001"})
            assert view.status_code == 200
            stream = await api.get(base + f"/executions/{run_id}/events")
            for step in (
                "disenador_interfaces",
                "validador_diseno",
                "guardar_revision",
                "pantalla_visualizada",
            ):
                assert step in stream.text
            assert "event: fin" in stream.text
            reviewed = await api.post(
                base + "/mockups/1/review",
                json={"accion": "aprobar", "nota": "Revisado visualmente por prueba"},
            )
            assert reviewed.json()["decision"] == "aprobado_por_humano"
            assert len(models.calls) == 2
            other = (
                await api.post("/api/projects", json={"nombre": "Otro proyecto mockups"})
            ).json()["id_proyecto"]
            assert (await api.get(f"/api/projects/{other}/mockups/1")).status_code == 404
            assert (
                await api.get(base + "/mockups", headers={"Authorization": "Bearer incorrecto"})
            ).status_code == 401

    try:
        run(scenario())
    finally:
        get_settings.cache_clear()
