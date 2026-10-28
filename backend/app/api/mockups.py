import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.agents.mockup_team import TechnicalDesignError
from app.api.routes import authorize, spawn
from app.models.mockups import GenerateMockups, ReviewMockups, ViewScreen
from app.services.failures import failure_detail

router = APIRouter(prefix="/api/projects/{project_id}/mockups", dependencies=[Depends(authorize)])


async def run_mockups(app, run_id, initial=None):
    try:
        await app.state.events.status(run_id, "ejecutando")
        result = await app.state.mockup_team.graph.ainvoke(
            initial, {"configurable": {"thread_id": str(run_id)}}
        )
        await app.state.events.emit(
            run_id,
            "langgraph",
            "mockups",
            "completado",
            "Flujo de mockups finalizado",
            {"version_mockup": result["content"]["version_mockup"]},
        )
        await app.state.events.status(run_id, "completado", result["content"])
    except asyncio.CancelledError:
        await app.state.events.status(run_id, "interrumpido")
        raise
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, (ValueError, LookupError))
            else "No se pudo completar el diseño o su persistencia"
        )
        await app.state.events.emit(
            run_id, "fase_3", "mockups", "error", message, failure_detail(exc, run_id, "fase_3")
        )
        await app.state.events.status(
            run_id,
            "error",
            {
                "error": message,
                "tipo_error": "contrato_diseno"
                if isinstance(exc, TechnicalDesignError)
                else "ejecucion",
            },
        )


@router.get("")
async def list_versions(project_id: UUID, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.mockups.list(project_id)


@router.post("/generate", status_code=202)
async def generate(project_id: UUID, data: GenerateMockups, request: Request):
    await request.app.state.projects.get(project_id)
    run_id, created = await request.app.state.mockups.start(
        project_id, data.model_dump(mode="json")
    )
    if created:
        row = await request.app.state.db.one("SELECT input FROM executions WHERE id=%s", (run_id,))
        spawn(request, run_mockups(request.app, run_id, {**row["input"], "execution_id": run_id}))
    return {"id_ejecucion": run_id}


@router.get("/{version}")
async def get_version(project_id: UUID, version: int, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.mockups.get(project_id, version)


@router.post("/{version}/review")
async def review(project_id: UUID, version: int, data: ReviewMockups, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.mockups.review(project_id, version, data)


@router.post("/{version}/view")
async def view(project_id: UUID, version: int, data: ViewScreen, request: Request):
    await request.app.state.projects.get(project_id)
    return await request.app.state.mockups.view(project_id, version, data.pantalla_id)
