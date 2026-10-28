import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.routes import authorize, spawn
from app.models.backlog import EditBacklog, GenerateBacklog, ReviewBacklog, ValidateBacklog
from app.services.failures import failure_detail

router = APIRouter(prefix="/api/projects/{project_id}/backlog", dependencies=[Depends(authorize)])


async def run_backlog(app, run_id, initial=None):
    try:
        await app.state.events.status(run_id, "ejecutando")
        result = await app.state.backlog_team.graph.ainvoke(
            initial, {"configurable": {"thread_id": str(run_id)}}
        )
        content = result["content"]
        await app.state.events.emit(
            run_id,
            "langgraph",
            "backlog",
            "completado",
            "Flujo de fase 2 finalizado",
            {
                "version_backlog": content["version_backlog"],
                "puede_publicar": content["validacion"]["puede_publicar"],
            },
        )
        await app.state.events.status(
            run_id,
            "completado",
            {
                "version_backlog": content["version_backlog"],
                "contrato": content,
                "publicable": content["validacion"]["puede_publicar"],
            },
        )
    except asyncio.CancelledError:
        await app.state.events.status(run_id, "interrumpido")
        raise
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, (ValueError, LookupError))
            else "La API de IA o la persistencia no pudo completar la fase 2"
        )
        await app.state.events.emit(
            run_id,
            "fase_2",
            "backlog",
            "error",
            message,
            {
                **failure_detail(exc, run_id, "fase_2"),
                "validacion": getattr(exc, "validation_errors", []),
            },
        )
        await app.state.events.status(run_id, "error", {"error": message})


async def dispatch(request, project_id, operation, data, version=None):
    await request.app.state.projects.get(project_id)
    run_id, created = await request.app.state.backlog.start(project_id, operation, data, version)
    if created:
        row = await request.app.state.db.one("SELECT input FROM executions WHERE id=%s", (run_id,))
        spawn(request, run_backlog(request.app, run_id, {**row["input"], "execution_id": run_id}))
    return {"id_ejecucion": run_id}


@router.get("")
async def list_versions(project_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.backlog.list(project_id)


@router.post("/generate", status_code=202)
async def generate(project_id: UUID, data: GenerateBacklog, request: Request):
    return await dispatch(request, project_id, "generar", data.model_dump(mode="json"))


@router.get("/items/{item_id}/history")
async def history(project_id: UUID, item_id: str, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.backlog.history(project_id, item_id)


@router.get("/{version}/publication")
async def publication(project_id: UUID, version: int, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.backlog.publication(project_id, version)


@router.get("/{version}")
async def get_version(project_id: UUID, version: int, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.backlog.get(project_id, version)


@router.post("/{version}/edit", status_code=202)
async def edit(project_id: UUID, version: int, data: EditBacklog, request: Request):
    return await dispatch(request, project_id, "editar", data.model_dump(mode="json"), version)


@router.post("/{version}/validate", status_code=202)
async def validate(project_id: UUID, version: int, data: ValidateBacklog, request: Request):
    return await dispatch(request, project_id, "validar", data.model_dump(mode="json"), version)


@router.post("/{version}/review")
async def review(project_id: UUID, version: int, data: ReviewBacklog, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.backlog.review(project_id, version, data)
