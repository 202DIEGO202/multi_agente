import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.agents.construction_team import TechnicalConstructionError
from app.api.routes import authorize, spawn
from app.models.construction import DeployRequest, GenerateConstruction, ReviewConstruction
from app.services.failures import failure_detail

router = APIRouter(
    prefix="/api/projects/{project_id}/construction", dependencies=[Depends(authorize)]
)
notifications = APIRouter(prefix="/api/notifications", dependencies=[Depends(authorize)])


async def run_construction(app, run_id, initial=None):
    try:
        await app.state.events.status(run_id, "ejecutando")
        result = await app.state.construction_team.graph.ainvoke(
            initial, {"configurable": {"thread_id": str(run_id)}}
        )
        content = result["content"]
        await app.state.events.emit(
            run_id,
            "langgraph",
            "construccion",
            "completado",
            "Red de agentes de construcción finalizada",
            {
                "version_construccion": content["version_construccion"],
                "consumo": content["consumo"],
            },
        )
        await app.state.events.status(
            run_id, "completado", {"version_construccion": content["version_construccion"]}
        )
    except asyncio.CancelledError:
        await app.state.events.status(run_id, "interrumpido")
        raise
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, (ValueError, LookupError))
            else "No se pudo completar la construcción"
        )
        await app.state.events.emit(
            run_id,
            "fase_5",
            "construccion",
            "error",
            message,
            failure_detail(exc, run_id, "fase_5"),
        )
        await app.state.events.status(
            run_id,
            "error",
            {
                "error": message,
                "tipo_error": "contrato_construccion"
                if isinstance(exc, TechnicalConstructionError)
                else "ejecucion",
            },
        )
        row = await app.state.db.one("SELECT project_id FROM executions WHERE id=%s", (run_id,))
        if row:
            await app.state.construction.notify(
                row["project_id"],
                "construccion",
                "La construcción no terminó",
                message,
                "/construction",
                run_id,
            )


@router.get("")
async def list_versions(project_id: UUID, request: Request):
    return await request.app.state.construction.list(project_id)


@router.post("/generate", status_code=202)
async def generate(project_id: UUID, data: GenerateConstruction, request: Request):
    run_id, created = await request.app.state.construction.start(
        project_id, data.model_dump(mode="json")
    )
    if created:
        row = await request.app.state.db.one("SELECT input FROM executions WHERE id=%s", (run_id,))
        spawn(
            request, run_construction(request.app, run_id, {**row["input"], "execution_id": run_id})
        )
    return {"id_ejecucion": run_id}


@router.get("/{version}")
async def get_version(project_id: UUID, version: int, request: Request):
    return await request.app.state.construction.get(project_id, version)


@router.get("/{version}/file")
async def get_file(project_id: UUID, version: int, path: str, request: Request):
    return await request.app.state.construction.file(project_id, version, path)


@router.post("/{version}/review")
async def review(project_id: UUID, version: int, data: ReviewConstruction, request: Request):
    service = request.app.state.construction
    result = await service.review(project_id, version, data)
    remote_run_id = result.pop("despliegue_remoto_id_ejecucion", None)
    if remote_run_id:
        spawn(request, service.deploy_remote(project_id, version, remote_run_id))
    return result


@router.post("/{version}/deploy", status_code=202)
async def deploy(project_id: UUID, version: int, data: DeployRequest, request: Request):
    service = request.app.state.construction
    run_id, created = await service.start_deploy(project_id, version, data.id_solicitud)
    if created:
        spawn(request, service.deploy(project_id, version, run_id))
    return {"id_ejecucion": run_id}


@router.post("/{version}/stop")
async def stop(project_id: UUID, version: int, request: Request):
    return await request.app.state.construction.stop(project_id, version)


@notifications.get("")
async def list_notifications(request: Request, unread: bool = False):
    return await request.app.state.db.fetch(
        "SELECT n.id,n.project_id AS id_proyecto,p.name AS proyecto,n.kind AS tipo,n.title AS titulo,n.message AS mensaje,"
        "n.link AS enlace,n.execution_id AS id_ejecucion,n.read_at AS leida,n.created_at AS fecha FROM notifications n "
        "JOIN projects p ON p.id=n.project_id WHERE p.deleted_at IS NULL AND (NOT %s OR n.read_at IS NULL) "
        "ORDER BY n.created_at DESC LIMIT 30",
        (unread,),
    )


@notifications.post("/{notification_id}/read")
async def read_notification(notification_id: int, request: Request):
    await request.app.state.db.execute(
        "UPDATE notifications SET read_at=now() WHERE id=%s AND read_at IS NULL", (notification_id,)
    )
    return {"estado": "leida"}


@notifications.post("/read-all")
async def read_all(request: Request):
    await request.app.state.db.execute(
        "UPDATE notifications SET read_at=now() WHERE read_at IS NULL"
    )
    return {"estado": "leidas"}
