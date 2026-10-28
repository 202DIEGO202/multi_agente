import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.agents.architecture_team import TechnicalArchitectureError
from app.api.routes import authorize, spawn
from app.models.architecture import GenerateArchitecture, ReviewArchitecture
from app.services.failures import failure_detail

router = APIRouter(
    prefix="/api/projects/{project_id}/architecture", dependencies=[Depends(authorize)]
)


async def run_architecture(app, run_id, initial=None):
    try:
        await app.state.events.status(run_id, "ejecutando")
        result = await app.state.architecture_team.graph.ainvoke(
            initial, {"configurable": {"thread_id": str(run_id)}}
        )
        content = result["content"]
        await app.state.events.emit(
            run_id,
            "langgraph",
            "arquitectura",
            "completado",
            "Flujo de arquitectura finalizado",
            {
                "version_arquitectura": content["version_arquitectura"],
                "consumo": content["consumo"],
            },
        )
        await app.state.events.status(
            run_id, "completado", {"version_arquitectura": content["version_arquitectura"]}
        )
    except asyncio.CancelledError:
        await app.state.events.status(run_id, "interrumpido")
        raise
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, (ValueError, LookupError))
            else "No se pudo completar la arquitectura o su persistencia"
        )
        await app.state.events.emit(
            run_id,
            "fase_4",
            "arquitectura",
            "error",
            message,
            failure_detail(exc, run_id, "fase_4"),
        )
        await app.state.events.status(
            run_id,
            "error",
            {
                "error": message,
                "tipo_error": "contrato_arquitectura"
                if isinstance(exc, TechnicalArchitectureError)
                else "ejecucion",
            },
        )


@router.get("")
async def list_versions(project_id: UUID, request: Request):
    return await request.app.state.architecture.list(project_id)


@router.get("/technologies")
async def technologies(project_id: UUID, request: Request):
    return request.app.state.settings.architecture_technologies


@router.post("/generate", status_code=202)
async def generate(project_id: UUID, data: GenerateArchitecture, request: Request):
    run_id, created = await request.app.state.architecture.start(
        project_id, data.model_dump(mode="json")
    )
    if created:
        row = await request.app.state.db.one("SELECT input FROM executions WHERE id=%s", (run_id,))
        spawn(
            request,
            run_architecture(request.app, run_id, {**row["input"], "execution_id": run_id}),
        )
    return {"id_ejecucion": run_id}


@router.get("/{version}")
async def get_version(project_id: UUID, version: int, request: Request):
    return await request.app.state.architecture.get(project_id, version)


@router.get("/{version}/files/{name}")
async def get_file(project_id: UUID, version: int, name: str, request: Request):
    return await request.app.state.architecture.file(project_id, version, name)


@router.post("/{version}/review")
async def review(project_id: UUID, version: int, data: ReviewArchitecture, request: Request):
    return await request.app.state.architecture.review(project_id, version, data)
