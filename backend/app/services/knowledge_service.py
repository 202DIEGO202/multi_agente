from uuid import uuid4

from psycopg.types.json import Jsonb


class KnowledgeService:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    async def sources(self, pid):
        return await self.db.fetch(
            "SELECT p.id AS id_proyecto,p.name AS nombre,count(d.id) AS documentos,"
            "(SELECT count(*) FROM chunks c JOIN documents x ON x.id=c.document_id WHERE x.project_id=p.id AND x.status='indexado' AND x.embedding_signature=%s) AS fragmentos "
            "FROM projects p JOIN documents d ON d.project_id=p.id WHERE p.deleted_at IS NULL AND p.id<>%s "
            "AND d.status='indexado' AND d.embedding_signature=%s GROUP BY p.id ORDER BY p.name",
            (self.settings.embedding_signature, pid, self.settings.embedding_signature),
        )

    async def link(self, pid, source):
        if str(pid) == str(source):
            raise ValueError("La base ya pertenece a este proyecto")
        async with self.db.pool.connection() as conn, conn.transaction():
            target = await (
                await conn.execute(
                    "SELECT id FROM projects WHERE id=%s AND deleted_at IS NULL FOR UPDATE", (pid,)
                )
            ).fetchone()
            origin = await (
                await conn.execute(
                    "SELECT id FROM projects WHERE id=%s AND deleted_at IS NULL", (source,)
                )
            ).fetchone()
            if not target or not origin:
                raise LookupError("Proyecto no encontrado")
            docs = await (
                await conn.execute(
                    "SELECT d.id,d.name,d.content_hash,d.embedding_signature FROM documents d WHERE d.project_id=%s "
                    "AND d.status='indexado' AND d.embedding_signature=%s ORDER BY d.id",
                    (source, self.settings.embedding_signature),
                )
            ).fetchall()
            if not docs:
                raise ValueError(
                    "El proyecto de origen no tiene documentos indexados compatibles con el modelo actual"
                )
            linked = []
            for doc in docs:
                found = await (
                    await conn.execute(
                        "SELECT id FROM project_knowledge_documents WHERE consumer_project_id=%s AND status='indexado' "
                        "AND lower(name)=lower(%s) AND content_hash=%s AND embedding_signature=%s LIMIT 1",
                        (pid, doc["name"], doc["content_hash"], doc["embedding_signature"]),
                    )
                ).fetchone()
                if found:
                    continue
                result = await conn.execute(
                    "INSERT INTO project_document_links(project_id,document_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                    (pid, doc["id"]),
                )
                if result.rowcount:
                    linked.append(str(doc["id"]))
            run_id = str(uuid4())
            output = {
                "documentos_vinculados": len(linked),
                "ya_disponibles": len(docs) - len(linked),
                "id_proyecto_origen": str(source),
                "ids_documentos": linked,
                "sin_inferencia": True,
            }
            await conn.execute(
                "INSERT INTO executions(id,project_id,kind,status,input,output,finished_at) VALUES(%s,%s,'conocimiento','completado',%s,%s,now())",
                (run_id, pid, Jsonb({"id_proyecto_origen": str(source)}), Jsonb(output)),
            )
            await conn.execute(
                "INSERT INTO events(execution_id,component,operation,status,description,data) VALUES(%s,'conocimiento','vincular_base','completado','Base indexada reutilizada sin generar embeddings',%s)",
                (run_id, Jsonb(output)),
            )
        return {**output, "id_ejecucion": run_id}
