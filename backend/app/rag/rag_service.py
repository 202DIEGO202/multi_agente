import asyncio
import time

from app.models.schemas import RetrievalResult
from app.rag.bm25_search import BM25Search
from app.rag.query_rewriting import rewrite_query
from app.rag.rank_fusion import reciprocal_rank_fusion
from app.rag.vector_search import vector_search


class RAGService:
    def __init__(self, db, models, settings, events):
        self.db, self.models, self.settings, self.events = db, models, settings, events
        self.bm25 = BM25Search()

    async def search_knowledge(self, project_id, original, context, run_id):
        corpus = await self.db.one(
            "SELECT p.knowledge_revision,(SELECT count(c.id) FROM chunks c "
            "JOIN project_knowledge_documents d ON d.id=c.document_id WHERE d.consumer_project_id=p.id "
            "AND d.status='indexado') AS fragmentos FROM projects p WHERE p.id=%s",
            (project_id,),
        )
        if not corpus:
            raise LookupError("Proyecto no encontrado")
        if not corpus["fragmentos"]:
            result = RetrievalResult(
                consulta_original=original,
                consulta_reformulada=original,
                vectoriales=[],
                bm25=[],
                rrf=[],
                seleccionados=[],
                degradaciones=[],
                duracion_ms=0,
                revision_conocimiento=corpus["knowledge_revision"],
                motivo_sin_evidencia="proyecto_sin_documentos_indexados",
            ).model_dump(mode="json", exclude_none=True)
            await self.events.emit(
                run_id,
                "rag",
                "resultado",
                "completado",
                "El proyecto activo no tiene documentos indexados",
                result,
            )
            return result
        if not self.settings.embedding_model:
            raise ValueError("La API de embeddings del RAG todavía no está configurada.")
        mismatch = await self.db.one(
            "SELECT id FROM project_knowledge_documents WHERE consumer_project_id=%s AND status='indexado' "
            "AND embedding_signature<>%s LIMIT 1",
            (project_id, self.settings.embedding_signature),
        )
        if mismatch:
            raise ValueError(
                "Reindexe los documentos con el modelo de embeddings por API configurado."
            )
        start = time.perf_counter()
        degraded = []
        await self.events.emit(
            run_id,
            "rag",
            "reformular",
            "ejecutando",
            "Reformulando consulta",
            {"consulta_original": original},
        )
        rewrite_start = time.perf_counter()
        try:
            query = await rewrite_query(self.models, original, context)
        except Exception:
            query = original
            degraded.append("Reformulación no disponible: se utilizó la consulta original")
        await self.events.emit(
            run_id,
            "rag",
            "reformular",
            "completado",
            "Consulta preparada",
            {"consulta_original": original, "consulta_reformulada": query},
            (time.perf_counter() - rewrite_start) * 1000,
        )
        vector = (await self.models.embed([query]))[0]
        search_start = time.perf_counter()
        await self.events.emit(
            run_id, "rag", "recuperar", "ejecutando", "Búsqueda vectorial y BM25 en paralelo"
        )
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            project = await (
                await conn.execute(
                    "SELECT knowledge_revision FROM projects WHERE id=%s", (project_id,)
                )
            ).fetchone()
            if not project:
                raise ValueError("Proyecto inexistente")
            mismatch = await (
                await conn.execute(
                    "SELECT id FROM project_knowledge_documents WHERE consumer_project_id=%s AND status='indexado' "
                    "AND embedding_signature<>%s LIMIT 1",
                    (project_id, self.settings.embedding_signature),
                )
            ).fetchone()
            if mismatch:
                raise ValueError(
                    "Cambió el modelo de embeddings. Reindexe los documentos del proyecto."
                )
            rows = await (
                await conn.execute(
                    "SELECT c.id AS id_fragmento,c.document_id AS id_documento,c.content AS contenido,"
                    "c.page AS pagina,c.position AS posicion,d.name AS documento,"
                    "d.version AS version_documento,d.category AS categoria "
                    "FROM chunks c JOIN project_knowledge_documents d ON d.id=c.document_id "
                    "WHERE d.consumer_project_id=%s AND d.status='indexado' ORDER BY c.id",
                    (project_id,),
                )
            ).fetchall()
            for row in rows:
                row["id_fragmento"], row["id_documento"] = (
                    str(row["id_fragmento"]),
                    str(row["id_documento"]),
                )
            vector_results, lexical_results = await asyncio.gather(
                vector_search(conn, project_id, vector, self.settings.retrieval_k),
                asyncio.to_thread(
                    self.bm25.search,
                    project_id,
                    project["knowledge_revision"],
                    rows,
                    query,
                    self.settings.retrieval_k,
                ),
            )
        await self.events.emit(
            run_id,
            "rag",
            "recuperar",
            "completado",
            "Recuperación completada",
            {"vectoriales": vector_results, "bm25": lexical_results},
            (time.perf_counter() - search_start) * 1000,
        )
        fused = reciprocal_rank_fusion(vector_results, lexical_results)
        await self.events.emit(
            run_id, "rag", "rrf", "completado", "Rankings fusionados", {"resultados": fused}
        )
        selected = fused[: self.settings.final_k]
        result = {
            "version_esquema": "1.1",
            "consulta_original": original,
            "consulta_reformulada": query,
            "vectoriales": vector_results,
            "bm25": lexical_results,
            "rrf": fused,
            "seleccionados": selected,
            "degradaciones": degraded,
            "duracion_ms": (time.perf_counter() - start) * 1000,
            "revision_conocimiento": project["knowledge_revision"],
        }
        result = RetrievalResult.model_validate(result).model_dump(mode="json", exclude_none=True)
        await self.events.emit(
            run_id,
            "rag",
            "seleccionar",
            "degradado" if degraded else "completado",
            "Evidencia documental disponible",
            {"seleccionados": selected, "degradaciones": degraded},
        )
        await self.events.emit(run_id, "rag", "resultado", "completado", "Trazabilidad RAG", result)
        return result
