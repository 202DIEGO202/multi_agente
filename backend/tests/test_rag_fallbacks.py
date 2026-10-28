from unittest.mock import AsyncMock
from uuid import uuid4

import numpy as np
import pytest
from test_persistence import environment, run

from app.config import Settings
from app.rag.rag_service import RAGService

pytestmark = pytest.mark.integration


def test_empty_project_explains_missing_corpus_without_ai_requests():
    async def scenario():
        async with environment() as (db, _, events, pid, rid, __):
            models = AsyncMock()
            result = await RAGService(db, models, Settings(), events).search_knowledge(
                pid, "¿Cómo restablecer mi contraseña?", "", rid
            )
            assert result["motivo_sin_evidencia"] == "proyecto_sin_documentos_indexados"
            assert result["seleccionados"] == []
            models.json.assert_not_awaited()
            models.embed.assert_not_awaited()
            activity = await events.list(rid)
            assert activity[-1]["datos"]["motivo_sin_evidencia"] == result["motivo_sin_evidencia"]

    run(scenario())


def test_rewrite_failure_preserves_rrf_order_and_reports_degradation():
    async def scenario():
        async with environment() as (db, _, events, pid, rid, __):
            settings = Settings(embedding_model="modelo-de-prueba", embedding_dimensions=2)
            doc, chunk = str(uuid4()), str(uuid4())
            await db.execute(
                "INSERT INTO documents(id,project_id,name,media_type,category,content_hash,"
                "status,embedding_signature,storage_path) VALUES(%s,%s,'vpn.txt','text/plain','IT',"
                "'hash','indexado',%s,'test')",
                (doc, pid, settings.embedding_signature),
            )
            await db.execute(
                "INSERT INTO chunks(id,document_id,page,position,content,embedding) "
                "VALUES(%s,%s,1,0,'VPN corporativa y conexión segura',%s)",
                (chunk, doc, np.array([1.0, 0.0], dtype=np.float32)),
            )
            # Dobles de prueba: provocan fallos controlados, nunca se usan en la aplicación.
            models = AsyncMock()
            models.json.side_effect = RuntimeError("Reformulador no disponible")
            models.embed.return_value = [[1.0, 0.0]]
            rag = RAGService(db, models, settings, events)
            result = await rag.search_knowledge(pid, "VPN", "", rid)
            assert result["consulta_original"] == result["consulta_reformulada"] == "VPN"
            assert len(result["degradaciones"]) == 1
            assert result["seleccionados"][0]["id_fragmento"] == chunk
            assert result["seleccionados"][0]["posicion_rrf"] == 1
            assert result["seleccionados"] == result["rrf"][: settings.final_k]
            assert result["version_esquema"] == "1.1"
            settings.embedding_model = "otro-modelo"
            with pytest.raises(ValueError, match="Reindexe"):
                await rag.search_knowledge(pid, "VPN", "", rid)

    run(scenario())
