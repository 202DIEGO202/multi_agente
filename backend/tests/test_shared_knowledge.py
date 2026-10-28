import hashlib
import os
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import numpy as np
import pytest
from test_persistence import environment, run

from app.config import Settings
from app.models.schemas import ProjectCreate
from app.rag.document_ingestion import DocumentIngestion
from app.rag.rag_service import RAGService
from app.services.knowledge_service import KnowledgeService


async def seed(db, projects, settings, path):
    source = await projects.create(ProjectCreate(nombre="Fuente indexada compartida"))
    sid = str(source["id_proyecto"])
    did, cid = str(uuid4()), str(uuid4())
    content = b"VPN corporativa y acceso seguro"
    path.write_bytes(content)
    await db.execute(
        "INSERT INTO documents(id,project_id,name,media_type,category,content_hash,status,embedding_signature,storage_path) VALUES(%s,%s,'vpn.txt','text/plain','IT',%s,'indexado',%s,%s)",
        (did, sid, hashlib.sha256(content).hexdigest(), settings.embedding_signature, str(path)),
    )
    await db.execute(
        "INSERT INTO chunks(id,document_id,page,position,content,embedding) VALUES(%s,%s,1,0,'VPN corporativa y acceso seguro',%s)",
        (cid, did, np.array([1.0, 0.0], dtype=np.float32)),
    )
    return sid, did, cid, content


def test_link_uses_original_vectors_avoids_duplicate_import_and_unlinks_safely(tmp_path):
    async def scenario():
        async with environment() as (db, projects, events, pid, rid, mid):
            settings = Settings(
                embedding_model="modelo-compartido-prueba",
                embedding_dimensions=2,
                storage_dir=tmp_path,
            )
            sid, did, cid, content = await seed(db, projects, settings, tmp_path / "vpn.txt")
            service = KnowledgeService(db, settings)
            before = await db.one("SELECT count(*) AS n FROM chunks")
            assert sid in {str(s["id_proyecto"]) for s in await service.sources(pid)}
            linked = await service.link(pid, sid)
            assert linked["documentos_vinculados"] == 1 and linked["sin_inferencia"]
            assert (await service.link(pid, sid))["documentos_vinculados"] == 0
            assert (await db.one("SELECT count(*) AS n FROM chunks")) == before
            state = await projects.state(pid)
            assert state["conocimiento"]["documentos_indexados"] == 1
            assert state["elementos"] == []
            # Importar de nuevo el mismo archivo reutiliza el vínculo antes de extraer/indexar.
            models = AsyncMock()
            ingestion = DocumentIngestion(db, models, settings, events)
            assert await ingestion.ingest(pid, "vpn.txt", content, rid) == did
            models.embed.assert_not_awaited()
            models.json.assert_not_awaited()
            assert not await db.one("SELECT id FROM documents WHERE project_id=%s", (pid,))
            with pytest.raises(ValueError, match="otros proyectos"):
                await ingestion.delete(sid, did)
            assert await ingestion.delete(pid, did)
            assert await db.one("SELECT id FROM chunks WHERE id=%s", (cid,))
            assert (await projects.state(pid))["conocimiento"]["documentos_indexados"] == 0
            assert await db.one(
                "SELECT id FROM events WHERE operation='desvincular_documento' AND data->>'id_documento'=%s",
                (did,),
            )

    run(scenario())


def test_shared_rag_sees_source_changes_and_survives_owner_trash(tmp_path):
    async def scenario():
        async with environment() as (db, projects, events, pid, rid, mid):
            settings = Settings(embedding_model="modelo-compartido-prueba", embedding_dimensions=2)
            sid, did, cid, _ = await seed(db, projects, settings, tmp_path / "vpn.txt")
            await KnowledgeService(db, settings).link(pid, sid)
            models = AsyncMock()
            models.json.side_effect = RuntimeError("Sin reformulación de prueba")
            models.embed.return_value = [[1.0, 0.0]]
            rag = RAGService(db, models, settings, events)
            first = await rag.search_knowledge(pid, "VPN", "", rid)
            assert first["seleccionados"][0]["id_fragmento"] == cid
            assert first["seleccionados"][0]["id_documento"] == did
            async with db.pool.connection() as conn, conn.transaction():
                await conn.execute("UPDATE documents SET version=version+1 WHERE id=%s", (did,))
                await conn.execute(
                    "UPDATE chunks SET content='VPN actualizada acceso remoto' WHERE id=%s", (cid,)
                )
            second = await rag.search_knowledge(pid, "VPN", "", rid)
            assert second["revision_conocimiento"] > first["revision_conocimiento"]
            assert "actualizada" in second["bm25"][0]["contenido"]
            assert second["seleccionados"][0]["version_documento"] == 2
            await projects.set_deleted(sid, True)
            assert (await rag.search_knowledge(pid, "VPN", "", rid))["seleccionados"]
            assert sid not in {
                str(s["id_proyecto"]) for s in await KnowledgeService(db, settings).sources(pid)
            }
            isolated = await projects.create(ProjectCreate(nombre="Sin vínculo"))
            empty = await rag.search_knowledge(str(isolated["id_proyecto"]), "VPN", "", rid)
            assert empty["seleccionados"] == []
            assert (
                models.embed.await_count == 3
            )  # Solo embeddings de las tres preguntas, nunca documentos.

    run(scenario())


def test_shared_documents_api_file_scope_and_no_model_calls(monkeypatch, tmp_path):
    url = os.getenv("TEST_DATABASE_URL")
    if not url or "fabrica_test" not in url:
        pytest.skip("Requiere fabrica_test")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("API_TOKEN", "prueba-base-compartida")
    monkeypatch.setenv("EMBEDDING_MODEL", "modelo-api-compartido")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "2")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app, lifespan
    from app.providers import Models

    embed = AsyncMock(side_effect=AssertionError("No debe indexar"))
    generation = AsyncMock(side_effect=AssertionError("No debe invocar LLM"))
    monkeypatch.setattr(Models, "embed", embed)
    monkeypatch.setattr(Models, "json", generation)

    async def scenario():
        async with (
            lifespan(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://prueba.local",
                headers={"Authorization": "Bearer prueba-base-compartida"},
            ) as api,
        ):
            sid, did, cid, _ = await seed(
                app.state.db, app.state.projects, app.state.settings, tmp_path / "api-vpn.txt"
            )
            pid = (
                await api.post("/api/projects", json={"nombre": "Consumidor compartido"})
            ).json()["id_proyecto"]
            base = f"/api/projects/{pid}"
            assert sid in {
                r["id_proyecto"] for r in (await api.get(base + "/knowledge/sources")).json()
            }
            result = await api.post(base + "/knowledge/link", json={"id_proyecto_origen": sid})
            assert result.status_code == 200 and result.json()["documentos_vinculados"] == 1
            docs = (await api.get(base + "/documents")).json()
            assert len(docs) == 1 and docs[0]["compartido"] and docs[0]["id"] == did
            assert (await api.get(base + f"/documents/{did}/file")).status_code == 200
            other = (
                await api.post("/api/projects", json={"nombre": "Otro ámbito sin compartir"})
            ).json()["id_proyecto"]
            assert (await api.get(f"/api/projects/{other}/documents/{did}/file")).status_code == 404
            assert (await api.post(base + "/knowledge/reindex")).status_code == 409
            assert (await api.delete(base + f"/documents/{did}")).status_code == 204
            assert (await api.get(base + "/documents")).json() == []
            assert (await api.get(f"/api/projects/{sid}/documents")).json()[0]["id"] == did
            embed.assert_not_awaited()
            generation.assert_not_awaited()

    try:
        run(scenario())
    finally:
        get_settings.cache_clear()
