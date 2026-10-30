import asyncio
import hashlib
import secrets
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.config import ROOT
from app.models.schemas import (
    ConflictResolution,
    KnowledgeLink,
    MessageCreate,
    ProjectCreate,
    PublishBaseline,
    QuestionAnswer,
    Review,
)
from app.services.events import sse
from app.services.failures import failure_detail


async def authorize(request: Request, authorization: str = Header(default="")):
    expected = request.app.state.settings.api_token.get_secret_value()
    if expected and not secrets.compare_digest(authorization, f"Bearer {expected}"):
        raise HTTPException(401, "Se requiere la clave de acceso del servidor")
    project_id = request.path_params.get("project_id")
    if project_id and request.scope.get("route").name != "restore_project":
        try:
            parsed_id = UUID(str(project_id))
        except ValueError:
            return  # FastAPI devuelve el error de parámetro UUID.
        await request.app.state.projects.get(parsed_id)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and "/workflow" not in request.url.path:
            active = await request.app.state.db.one(
                "SELECT id FROM executions WHERE project_id=%s AND kind='flujo_completo' "
                "AND status IN ('pendiente','ejecutando') LIMIT 1", (parsed_id,))
            if active:
                raise HTTPException(409, "Hay un flujo integral activo. Páuselo antes de modificar sus fuentes o iniciar otra ejecución.")


router = APIRouter(prefix="/api", dependencies=[Depends(authorize)])


def spawn(request: Request, coroutine):
    task = asyncio.create_task(coroutine)
    tasks = request.app.state.tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)


@router.get("/health")
async def health(request: Request):
    await request.app.state.db.one("SELECT 1")
    s = request.app.state.settings
    return {
        "estado": "disponible",
        "base_datos": "conectada",
        "version_esquema": "1.0",
        "contratos": {
            "funcional": "1.0",
            "recuperacion": "1.1",
            "backlog": "2.0",
            "mockups": "3.0",
            "arquitectura": "4.0",
            "construccion": "5.0",
        },
        "ia_configurada": bool(s.llm_base_url and s.llm_model),
    }


@router.get("/configuration")
async def configuration(request: Request):
    s = request.app.state.settings
    return {
        "analista": {"proveedor": s.llm_provider, "modelo": s.llm_model},
        "reformulacion": {"proveedor": s.rewrite_provider, "modelo": s.rewrite_model},
        "embeddings": {
            "proveedor": s.embedding_provider,
            "modelo": s.embedding_model,
            "dimensiones": s.embedding_dimensions,
        },
        "version_esquema": "1.0",
    }


@router.get("/projects")
async def list_projects(request: Request):
    return await request.app.state.projects.list()


@router.post("/projects", status_code=201)
async def create_project(data: ProjectCreate, request: Request):
    return await request.app.state.projects.create(data)


@router.get("/projects/trash")
async def project_trash(request: Request):
    return await request.app.state.projects.trash()


@router.delete("/projects/{project_id}")
async def delete_project(project_id: UUID, request: Request):
    return await request.app.state.projects.set_deleted(project_id, True)


@router.post("/projects/{project_id}/restore")
async def restore_project(project_id: UUID, request: Request):
    return await request.app.state.projects.set_deleted(project_id, False)


@router.get("/projects/{project_id}/state")
async def project_state(project_id: UUID, request: Request):
    return await request.app.state.projects.state(project_id)


@router.get("/projects/{project_id}/items/{item_id}/history")
async def item_history(project_id: UUID, item_id: str, request: Request):
    await request.app.state.projects.get(project_id)
    return [
        r["payload"]
        for r in await request.app.state.db.fetch(
            "SELECT payload FROM functional_items WHERE project_id=%s AND id=%s ORDER BY version",
            (project_id, item_id),
        )
    ]


@router.post("/projects/{project_id}/proposals/{proposal_id}/review")
async def review(project_id: UUID, proposal_id: UUID, data: Review, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.projects.review(project_id, proposal_id, data)


@router.post("/projects/{project_id}/conflicts/{conflict_id}/resolve")
async def resolve(project_id: UUID, conflict_id: UUID, data: ConflictResolution, request: Request):
    await request.app.state.projects.get(project_id)
    result = await request.app.state.projects.resolve_conflict(
        project_id, conflict_id, data.resolucion
    )
    reanalysis = result.pop("reanalisis")
    result["id_ejecucion_reanalisis"] = None
    if reanalysis:
        try:
            result["id_ejecucion_reanalisis"] = await start_chat(
                request, project_id, UUID(reanalysis["id_conversacion"]), reanalysis["mensaje"]
            )
        except UniqueViolation:
            pass  # Hay un análisis en curso en esa conversación; el usuario puede pedirlo después.
    return result


@router.post("/projects/{project_id}/items/{item_id}/answer", status_code=202)
async def answer_question(project_id: UUID, item_id: str, data: QuestionAnswer, request: Request):
    await request.app.state.projects.get(project_id)
    result = await request.app.state.projects.answer_question(project_id, item_id, data.respuesta)
    try:
        run_id = await start_chat(request, project_id, UUID(result["id_conversacion"]), result["mensaje"])
    except UniqueViolation:
        raise HTTPException(409, "Hay un análisis en curso en esa conversación; inténtelo de nuevo en unos segundos.")
    return {"id_ejecucion_reanalisis": run_id, "id_conversacion": result["id_conversacion"]}


@router.post("/projects/{project_id}/baselines", status_code=201)
async def publish_baseline(project_id: UUID, data: PublishBaseline, request: Request):
    return await request.app.state.projects.publish(project_id, data.aprobacion_humana)


@router.get("/projects/{project_id}/baselines/{version}")
async def get_baseline(project_id: UUID, version: int, request: Request):
    row = await request.app.state.db.one(
        "SELECT payload FROM baselines WHERE project_id=%s AND version=%s", (project_id, version)
    )
    if not row:
        raise LookupError("Línea base no encontrada")
    return row["payload"]


@router.get("/projects/{project_id}/conversations")
async def conversations(project_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.db.fetch(
        "SELECT id,title AS titulo,created_at AS fecha FROM conversations WHERE project_id=%s ORDER BY created_at DESC",
        (project_id,),
    )


@router.post("/projects/{project_id}/conversations", status_code=201)
async def create_conversation(project_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    conversation_id = str(uuid4())
    await request.app.state.db.execute(
        "INSERT INTO conversations(id,project_id,title) VALUES(%s,%s,%s)",
        (conversation_id, project_id, "Nuevo análisis"),
    )
    return {"id": conversation_id, "titulo": "Nuevo análisis"}


async def require_conversation(request, project_id, conversation_id):
    row = await request.app.state.db.one(
        "SELECT id FROM conversations WHERE id=%s AND project_id=%s", (conversation_id, project_id)
    )
    if not row:
        raise LookupError("Conversación no encontrada en este proyecto")


@router.get("/projects/{project_id}/conversations/{conversation_id}/messages")
async def messages(project_id: UUID, conversation_id: UUID, request: Request):
    await require_conversation(request, project_id, conversation_id)
    return await request.app.state.db.fetch(
        "SELECT id,role AS rol,content AS contenido,sources AS fuentes,execution_id AS id_ejecucion,"
        "created_at AS fecha FROM messages WHERE conversation_id=%s ORDER BY created_at,id",
        (conversation_id,),
    )


async def run_chat(app, run_id, initial=None):
    events = app.state.events
    try:
        await events.status(run_id, "ejecutando")
        result = await app.state.analyst.graph.ainvoke(
            initial, {"configurable": {"thread_id": str(run_id)}}
        )
        output = {
            "respuesta": result.get("response", ""),
            "propuestas": result.get("changes", []),
            "rag": result.get("evidence", {}),
        }
        await events.emit(run_id, "langgraph", "ejecucion", "completado", "Análisis finalizado")
        await events.status(run_id, "completado", output)
    except asyncio.CancelledError:
        await events.status(run_id, "interrumpido")
        raise
    except Exception as exc:
        await events.emit(
            run_id,
            "langgraph",
            "ejecucion",
            "error",
            "La ejecución se detuvo. Puede reanudarla después de corregir la configuración.",
            {
                **failure_detail(exc, run_id, "analista"),
                "validacion": getattr(exc, "validation_errors", []),
                "valido": False,
            },
        )
        await events.status(run_id, "error", {"error": "No se pudo completar el análisis"})


async def start_chat(request, project_id, conversation_id, content):
    run_id, message_id = str(uuid4()), str(uuid4())
    initial = {
        "project_id": str(project_id),
        "conversation_id": str(conversation_id),
        "execution_id": run_id,
        "message_id": message_id,
        "message": content,
    }
    async with request.app.state.db.pool.connection() as conn, conn.transaction():
        await conn.execute(
            "INSERT INTO executions(id,project_id,conversation_id,kind,input) VALUES(%s,%s,%s,'chat',%s)",
            (run_id, project_id, conversation_id, Jsonb(initial)),
        )
        await conn.execute(
            "INSERT INTO messages(id,conversation_id,execution_id,role,content) VALUES(%s,%s,%s,'user',%s)",
            (message_id, conversation_id, run_id, content),
        )
    spawn(request, run_chat(request.app, run_id, initial))
    return run_id


@router.post("/projects/{project_id}/conversations/{conversation_id}/messages", status_code=202)
async def send_message(
    project_id: UUID, conversation_id: UUID, data: MessageCreate, request: Request
):
    await require_conversation(request, project_id, conversation_id)
    run_id, message_id = str(uuid4()), str(uuid4())
    initial = {
        "project_id": str(project_id),
        "conversation_id": str(conversation_id),
        "execution_id": run_id,
        "message_id": message_id,
        "message": data.contenido,
    }
    try:
        async with request.app.state.db.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "SELECT id FROM conversations WHERE id=%s FOR UPDATE", (conversation_id,)
            )
            existing = await (
                await conn.execute(
                    "SELECT id FROM executions WHERE conversation_id=%s AND request_id=%s",
                    (conversation_id, data.id_solicitud),
                )
            ).fetchone()
            if existing:
                return {
                    "id_ejecucion": str(existing["id"]),
                    "id_conversacion": str(conversation_id),
                }
            await conn.execute(
                "INSERT INTO executions(id,project_id,conversation_id,request_id,kind,input) "
                "VALUES(%s,%s,%s,%s,'chat',%s)",
                (run_id, project_id, conversation_id, data.id_solicitud, Jsonb(initial)),
            )
            await conn.execute(
                "INSERT INTO messages(id,conversation_id,execution_id,role,content) VALUES(%s,%s,%s,'user',%s)",
                (message_id, conversation_id, run_id, data.contenido),
            )
            await conn.execute(
                "UPDATE conversations SET title=%s WHERE id=%s AND title='Nuevo análisis'",
                (data.contenido[:65], conversation_id),
            )
    except UniqueViolation as exc:
        raise HTTPException(409, "Ya hay un análisis en curso en esta conversación") from exc
    spawn(request, run_chat(request.app, run_id, initial))
    return {"id_ejecucion": run_id, "id_conversacion": str(conversation_id)}


@router.get("/projects/{project_id}/executions")
async def executions(project_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.db.fetch(
        "SELECT id AS id_ejecucion,kind AS tipo,status AS estado,conversation_id AS id_conversacion,"
        "created_at AS fecha,finished_at AS fecha_fin FROM executions WHERE project_id=%s "
        "ORDER BY created_at DESC LIMIT 100",
        (project_id,),
    )


async def require_run(request, project_id, run_id):
    row = await request.app.state.db.one(
        "SELECT * FROM executions WHERE id=%s AND project_id=%s", (run_id, project_id)
    )
    if not row:
        raise LookupError("Ejecución no encontrada")
    return row


@router.get("/projects/{project_id}/executions/{run_id}")
async def execution(project_id: UUID, run_id: UUID, request: Request):
    row = await require_run(request, project_id, run_id)
    return {
        "id_ejecucion": row["id"],
        "tipo": row["kind"],
        "estado": row["status"],
        "resultado": row["output"],
        "eventos": await request.app.state.events.list(run_id),
    }


@router.post("/projects/{project_id}/executions/{run_id}/resume", status_code=202)
async def resume(project_id: UUID, run_id: UUID, request: Request):
    row = await require_run(request, project_id, run_id)
    if row["kind"] not in {"chat", "backlog", "mockups", "arquitectura", "construccion"} or row[
        "status"
    ] not in {
        "error",
        "interrumpido",
    }:
        raise ValueError("Solo puede reanudar un análisis, backlog, diseño o arquitectura detenido")
    graph = (
        request.app.state.construction_team.graph
        if row["kind"] == "construccion"
        else request.app.state.architecture_team.graph
        if row["kind"] == "arquitectura"
        else request.app.state.mockup_team.graph
        if row["kind"] == "mockups"
        else request.app.state.backlog_team.graph
        if row["kind"] == "backlog"
        else request.app.state.analyst.graph
    )
    snapshot = await graph.aget_state({"configurable": {"thread_id": str(run_id)}})
    try:
        async with request.app.state.db.pool.connection() as conn, conn.transaction():
            result = await conn.execute(
                "UPDATE executions SET status='pendiente' WHERE id=%s "
                "AND status IN ('error','interrumpido')",
                (run_id,),
            )
            if not result.rowcount:
                raise ValueError("La ejecución ya fue reanudada")
    except UniqueViolation as exc:
        raise HTTPException(409, "Hay otro análisis activo en esta conversación") from exc
    if row["kind"] == "construccion":
        from app.api.construction import run_construction

        initial = None if snapshot.values else {**row["input"], "execution_id": str(run_id)}
        spawn(request, run_construction(request.app, str(run_id), initial))
    elif row["kind"] == "arquitectura":
        from app.api.architecture import run_architecture

        initial = None if snapshot.values else {**row["input"], "execution_id": str(run_id)}
        spawn(request, run_architecture(request.app, str(run_id), initial))
    elif row["kind"] == "mockups":
        from app.api.mockups import run_mockups

        initial = None if snapshot.values else {**row["input"], "execution_id": str(run_id)}
        spawn(request, run_mockups(request.app, str(run_id), initial))
    elif row["kind"] == "backlog":
        from app.api.backlog import run_backlog

        initial = None if snapshot.values else {**row["input"], "execution_id": str(run_id)}
        spawn(request, run_backlog(request.app, str(run_id), initial))
    else:
        spawn(
            request, run_chat(request.app, str(run_id), None if snapshot.values else row["input"])
        )
    return {"id_ejecucion": str(run_id)}


@router.get("/projects/{project_id}/executions/{run_id}/events")
async def stream_events(
    project_id: UUID,
    run_id: UUID,
    request: Request,
    after: int = 0,
    last_event_id: str = Header(default=""),
):
    await require_run(request, project_id, run_id)
    cursor = max(after, int(last_event_id)) if last_event_id.isdigit() else max(0, after)

    async def generate():
        position, idle = cursor, 0
        while not await request.is_disconnected():
            rows = await request.app.state.events.list(run_id, position)
            for row in rows:
                position = row["id_evento"]
                yield sse("actividad", row, position)
            row = await request.app.state.db.one(
                "SELECT status FROM executions WHERE id=%s", (run_id,)
            )
            if row["status"] in {"completado", "error", "interrumpido", "esperando_revision", "pausado"} and len(rows) < 250:
                # Evita perder eventos insertados entre el último SELECT y el cambio de estado.
                final_rows = await request.app.state.events.list(run_id, position)
                if final_rows:
                    for event in final_rows:
                        position = event["id_evento"]
                        yield sse("actividad", event, position)
                    continue
                yield sse("fin", {"estado": row["status"], "id_ejecucion": str(run_id)})
                break
            idle += 1
            if idle % 20 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/projects/{project_id}/documents")
async def documents(project_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.db.fetch(
        "SELECT d.id,d.name AS nombre,d.media_type AS tipo,d.category AS categoria,d.version,"
        "d.status AS estado,d.created_at AS fecha_incorporacion,d.updated_at AS fecha_actualizacion,"
        "d.last_error AS ultimo_error,d.compartido,p.name AS proyecto_origen,"
        "(SELECT count(*) FROM chunks c WHERE c.document_id=d.id) AS fragmentos "
        "FROM project_knowledge_documents d JOIN projects p ON p.id=d.project_id "
        "WHERE d.consumer_project_id=%s ORDER BY d.name",
        (project_id,),
    )


@router.get("/projects/{project_id}/documents/{document_id}/file")
async def document_file(
    project_id: UUID, document_id: UUID, request: Request, version: int | None = None
):
    row = await request.app.state.db.one(
        "SELECT * FROM project_knowledge_documents WHERE consumer_project_id=%s AND id=%s",
        (project_id, document_id),
    )
    if row and version is not None:
        row = await request.app.state.db.one(
            "SELECT v.* FROM document_versions v JOIN project_knowledge_documents d ON d.id=v.document_id "
            "WHERE d.consumer_project_id=%s AND d.id=%s AND v.version=%s",
            (project_id, document_id, version),
        )
    if not row or not Path(row["storage_path"]).is_file():
        raise LookupError("Archivo no disponible")
    return FileResponse(
        row["storage_path"],
        media_type=row["media_type"],
        filename=row["name"],
        content_disposition_type="inline",
    )


async def ingest_files(app, project_id, run_id, files, force=False):
    succeeded, failed = 0, 0
    await app.state.events.status(run_id, "ejecutando")
    try:
        for path, name, category in files:
            content = None
            try:
                content = await asyncio.to_thread(Path(path).read_bytes)
                await app.state.ingestion.ingest(
                    str(project_id), name, content, run_id, category, force
                )
                succeeded += 1
            except Exception as exc:
                failed += 1
                message = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else "No se pudo indexar el documento; revise modelos y conectividad"
                )
                await app.state.events.emit(
                    run_id,
                    "ingesta",
                    "indexar",
                    "error",
                    message,
                    {"documento": name, **failure_detail(exc, run_id, "ingesta")},
                )
                if content is not None:
                    await app.state.ingestion.record_failure(
                        str(project_id), name, content, category, message
                    )
        await app.state.events.status(
            run_id,
            "error" if failed else "completado",
            {"procesados": succeeded, "fallidos": failed},
        )
    except asyncio.CancelledError:
        await app.state.events.status(run_id, "interrumpido")
        raise
    except Exception as exc:
        await app.state.events.emit(
            run_id,
            "ingesta",
            "ejecucion",
            "error",
            "Ingesta interrumpida",
            failure_detail(exc, run_id, "ingesta"),
        )
        await app.state.events.status(run_id, "error")


@router.post("/projects/{project_id}/documents", status_code=202)
async def upload(project_id: UUID, file: UploadFile, request: Request):
    await request.app.state.projects.get(project_id)
    name = Path((file.filename or "").replace("\\", "/")).name
    if Path(name).suffix.lower() not in {".pdf", ".txt", ".md"}:
        raise HTTPException(415, "Tipos admitidos: PDF, TXT y Markdown")
    content = await file.read(request.app.state.settings.max_upload_mb * 1024**2 + 1)
    if len(content) > request.app.state.settings.max_upload_mb * 1024**2:
        raise HTTPException(413, "Archivo demasiado grande")
    stage = request.app.state.settings.storage_dir / "staging"
    stage.mkdir(parents=True, exist_ok=True)
    path = stage / (hashlib.sha256(content).hexdigest() + Path(name).suffix.lower())
    await asyncio.to_thread(path.write_bytes, content)
    run_id = await request.app.state.events.create_run(project_id, "ingesta", {"documento": name})
    spawn(request, ingest_files(request.app, project_id, run_id, [(path, name, "carga_manual")]))
    return {"id_ejecucion": run_id}


@router.get("/projects/{project_id}/knowledge/sources")
async def knowledge_sources(project_id: UUID, request: Request):
    return await request.app.state.knowledge.sources(project_id)


@router.post("/projects/{project_id}/knowledge/link")
async def link_knowledge(project_id: UUID, data: KnowledgeLink, request: Request):
    return await request.app.state.knowledge.link(project_id, data.id_proyecto_origen)


@router.post("/projects/{project_id}/knowledge/import", status_code=202)
async def import_corpus(project_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    # Solo el corpus entregado, nunca una ruta arbitraria enviada por el navegador.
    files = [
        (path, path.name, path.parent.name)
        for category in ("FAQS-*", "Manuales-*", "Politicas-*")
        for folder in ROOT.glob(category)
        if folder.is_dir()
        for path in folder.rglob("*.pdf")
    ]
    if not files:
        raise ValueError("No se encontró el corpus inicial en la carpeta del proyecto")
    run_id = await request.app.state.events.create_run(
        project_id, "ingesta", {"documentos": len(files)}
    )
    spawn(request, ingest_files(request.app, project_id, run_id, files))
    return {"id_ejecucion": run_id, "documentos": len(files)}


@router.post("/projects/{project_id}/knowledge/reindex", status_code=202)
async def reindex(project_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    rows = await request.app.state.db.fetch(
        "SELECT storage_path,name,category FROM documents WHERE project_id=%s", (project_id,)
    )
    files = [(r["storage_path"], r["name"], r["category"]) for r in rows]
    if not files:
        raise ValueError(
            "No hay documentos propios para reindexar. Los vinculados se administran desde el proyecto de origen."
        )
    run_id = await request.app.state.events.create_run(
        project_id, "ingesta", {"reindexacion": True}
    )
    spawn(request, ingest_files(request.app, project_id, run_id, files, True))
    return {"id_ejecucion": run_id}


@router.delete("/projects/{project_id}/documents/{document_id}", status_code=204)
async def delete_document(project_id: UUID, document_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    if not await request.app.state.ingestion.delete(project_id, document_id):
        raise LookupError("Documento no encontrado")


@router.post("/projects/{project_id}/knowledge/search", status_code=202)
async def search(project_id: UUID, data: MessageCreate, request: Request):
    await request.app.state.projects.get(project_id)
    run_id = await request.app.state.events.create_run(
        project_id, "rag", {"consulta": data.contenido}
    )

    async def perform():
        try:
            await request.app.state.events.status(run_id, "ejecutando")
            result = await request.app.state.rag.search_knowledge(
                str(project_id), data.contenido, "", run_id
            )
            await request.app.state.events.status(run_id, "completado", result)
        except Exception as exc:
            message = (
                str(exc)
                if isinstance(exc, ValueError)
                else "No se pudo completar la recuperación documental"
            )
            await request.app.state.events.emit(
                run_id, "rag", "ejecucion", "error", message, failure_detail(exc, run_id, "rag")
            )
            await request.app.state.events.status(run_id, "error", {"error": message})

    spawn(request, perform())
    return {"id_ejecucion": run_id}
