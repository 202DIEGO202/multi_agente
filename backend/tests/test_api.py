import asyncio
import os

import httpx
import pytest
from test_persistence import run

pytestmark = pytest.mark.integration


def test_auth_project_scope_and_sse_replay(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url or "fabrica_test" not in url:
        pytest.skip("Requiere una base de pruebas separada")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("API_TOKEN", "acceso-exclusivo-de-prueba")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app, lifespan

    async def scenario():
        async with (
            lifespan(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://prueba.local"
            ) as api,
        ):
            assert (await api.get("/api/projects")).status_code == 401
            api.headers["Authorization"] = "Bearer acceso-exclusivo-de-prueba"
            project = (await api.post("/api/projects", json={"nombre": "Prueba de API"})).json()
            other = (await api.post("/api/projects", json={"nombre": "Ámbito diferente"})).json()
            base = f"/api/projects/{project['id_proyecto']}"
            conv = (await api.post(base + "/conversations")).json()
            cross = await api.get(
                f"/api/projects/{other['id_proyecto']}/conversations/{conv['id']}/messages"
            )
            assert cross.status_code == 404
            rid = await app.state.events.create_run(project["id_proyecto"], "rag")
            await app.state.events.emit(
                rid, "prueba", "inicio", "ejecutando", "Operación de prueba real"
            )
            await app.state.events.emit(
                rid, "prueba", "validar", "completado", "Validación completada", {"valido": True}
            )
            await app.state.events.status(rid, "completado")
            rows = await app.state.events.list(rid)
            stream = await api.get(base + f"/executions/{rid}/events")
            assert stream.headers["content-type"].startswith("text/event-stream")
            assert stream.text.count("event: actividad") == 2
            assert "event: fin" in stream.text
            replay = await api.get(
                base + f"/executions/{rid}/events",
                headers={"Last-Event-ID": str(rows[0]["id_evento"])},
            )
            assert replay.text.count("event: actividad") == 1
            assert "Validación completada" in replay.text
            config = (await api.get("/api/configuration")).text
            assert "acceso-exclusivo-de-prueba" not in config
            assert "api_key" not in config
            assert (
                await api.get(f"/api/projects/{other['id_proyecto']}/executions/{rid}")
            ).status_code == 404
            invalid = await api.post(
                base + "/conversations/" + conv["id"] + "/messages", json={"contenido": ""}
            )
            assert invalid.status_code == 422
            upload = await api.post(
                base + "/documents",
                files={"file": ("invalido.pdf", b"No es PDF", "application/pdf")},
            )
            assert upload.status_code == 202
            await asyncio.gather(*app.state.tasks)
            docs = (await api.get(base + "/documents")).json()
            assert docs[0]["estado"] == "error"
            assert docs[0]["fragmentos"] == 0

    try:
        run(scenario())
    finally:
        get_settings.cache_clear()
