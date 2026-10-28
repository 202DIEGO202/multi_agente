import asyncio
import os
from uuid import uuid4

import httpx
import pytest
from backlog_fixtures import organization_fixture, stories_fixture
from test_persistence import run

from app.models.backlog import Organization, SemanticReview, Stories
from app.models.schemas import Analysis, Change

pytestmark = pytest.mark.integration


def test_backlog_api_agents_sse_review_edit_and_scope(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url or "fabrica_test" not in url:
        pytest.skip("Requiere TEST_DATABASE_URL aislada")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("API_TOKEN", "acceso-fase-2-de-prueba")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app, lifespan
    from app.providers import Models

    calls = []

    async def controlled_json(
        self, messages, schema, rewrite=False, max_tokens=None, max_attempts=2
    ):
        calls.append(schema.__name__)
        if schema is Organization:
            return organization_fixture()
        if schema is Stories:
            assert '"organizacion"' in messages[-1]["content"]
            return stories_fixture()
        if schema is SemanticReview:
            assert '"FE-001"' in messages[-1]["content"]
            return SemanticReview()
        raise AssertionError("Modelo inesperado en esta prueba controlada")

    monkeypatch.setattr(Models, "json", controlled_json)

    async def scenario():
        async with (
            lifespan(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://prueba.local",
                headers={"Authorization": "Bearer acceso-fase-2-de-prueba"},
            ) as api,
        ):
            project = (
                await api.post("/api/projects", json={"nombre": "API fase 2", "modo": "automatico"})
            ).json()
            pid = project["id_proyecto"]
            base = f"/api/projects/{pid}"
            no_source = await api.post(
                base + "/backlog/generate",
                json={"version_linea_base": 1, "id_solicitud": str(uuid4())},
            )
            assert no_source.status_code == 409
            cid = (await api.post(base + "/conversations")).json()["id"]
            rid = await app.state.events.create_run(pid, "chat", conversation_id=cid)
            mid = str(uuid4())
            await app.state.db.execute(
                "INSERT INTO messages(id,conversation_id,execution_id,role,content) VALUES(%s,%s,%s,'user','Datos de prueba')",
                (mid, cid, rid),
            )
            await app.state.projects.propose(
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
            await app.state.projects.publish(pid, False)
            await app.state.db.execute("UPDATE projects SET mode='supervisado' WHERE id=%s", (pid,))
            body = {"version_linea_base": 1, "id_solicitud": str(uuid4()), "instrucciones": ""}
            response = await api.post(base + "/backlog/generate", json=body)
            assert response.status_code == 202
            run_id = response.json()["id_ejecucion"]
            await asyncio.gather(*list(app.state.tasks))
            result = (await api.get(base + "/backlog/1")).json()
            assert result["estado"] == "propuesto" and result["contrato"]["historias"]
            assert calls == ["Organization", "Stories", "SemanticReview"]
            replay = await api.post(base + "/backlog/generate", json=body)
            assert replay.json()["id_ejecucion"] == run_id and len(calls) == 3
            stream = await api.get(base + f"/executions/{run_id}/events")
            for component in ("organizador_funcional", "historias_usuario", "validador_funcional"):
                assert component in stream.text
            assert "event: fin" in stream.text
            approved = await api.post(
                base + "/backlog/1/review",
                json={"accion": "aprobar", "nota": "Revisión completa de prueba"},
            )
            assert approved.status_code == 200 and approved.json()["publicado"]
            publication = (await api.get(base + "/backlog/1/publication")).json()
            assert publication["estado"] == "aprobado_por_humano"
            edited = await api.post(
                base + "/backlog/1/edit",
                json={
                    "id_solicitud": str(uuid4()),
                    "id_elemento": "FE-001",
                    "titulo": "Recepción de solicitudes",
                    "descripcion": "Registrar solicitudes con descripción",
                    "ids_requisitos": ["RF-001"],
                    "id_padre": "EP-001",
                    "nota": "Ajustar el título de la feature",
                },
            )
            assert edited.status_code == 202
            await asyncio.gather(*list(app.state.tasks))
            revised = (await api.get(base + "/backlog/2")).json()
            assert revised["contrato"]["features"][0]["version"] == 2
            assert revised["estado"] == "propuesto"
            assert (await api.get(base + "/backlog/1/publication")).json() == publication
            history = (await api.get(base + "/backlog/items/FE-001/history")).json()
            assert len(history) == 2
            other = (await api.post("/api/projects", json={"nombre": "Otro ámbito fase 2"})).json()[
                "id_proyecto"
            ]
            assert (await api.get(f"/api/projects/{other}/backlog/1")).status_code == 404
            assert (
                await api.get(f"/api/projects/{other}/backlog/items/FE-001/history")
            ).status_code == 404
            assert (
                await api.get(f"/api/projects/{other}/backlog/1/publication")
            ).status_code == 404

    try:
        run(scenario())
    finally:
        get_settings.cache_clear()
