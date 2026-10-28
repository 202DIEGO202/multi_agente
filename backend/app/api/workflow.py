import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.routes import authorize
from app.models.workflow import StartWorkflow

router = APIRouter(prefix="/api/projects/{project_id}/workflow", dependencies=[Depends(authorize)])


def dispatch(request, pid, rid):
    task = asyncio.create_task(request.app.state.workflow.run(pid, rid))
    request.app.state.tasks.add(task)
    request.app.state.workflow_tasks[rid] = task
    task.add_done_callback(request.app.state.tasks.discard)
    task.add_done_callback(lambda _: request.app.state.workflow_tasks.pop(rid, None))


@router.get("")
async def list_workflows(project_id: UUID, request: Request):
    return await request.app.state.db.fetch(
        "SELECT w.id,w.mode AS modo,e.status AS estado,e.created_at AS fecha FROM development_workflows w "
        "JOIN executions e ON e.id=w.id WHERE w.project_id=%s ORDER BY e.created_at DESC LIMIT 30", (project_id,))


@router.post("", status_code=202)
async def start_workflow(project_id: UUID, data: StartWorkflow, request: Request):
    rid, created = await request.app.state.workflow.start(project_id, data.model_dump(mode="json"))
    if created:
        dispatch(request, project_id, rid)
    return {"id_ejecucion": rid}


@router.get("/{run_id}")
async def get_workflow(project_id: UUID, run_id: UUID, request: Request):
    return await request.app.state.workflow.get(project_id, run_id)


@router.post("/{run_id}/resume", status_code=202)
async def resume_workflow(project_id: UUID, run_id: UUID, request: Request):
    await request.app.state.workflow.resume(project_id, run_id)
    dispatch(request, project_id, str(run_id))
    return {"id_ejecucion": str(run_id)}


@router.post("/{run_id}/pause")
async def pause_workflow(project_id: UUID, run_id: UUID, request: Request):
    await request.app.state.workflow.get(project_id, run_id)
    task = request.app.state.workflow_tasks.get(str(run_id))
    if task and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await request.app.state.db.execute("UPDATE executions SET status='interrumpido' WHERE id=%s AND status='pendiente'", (run_id,))
    return await request.app.state.workflow.get(project_id, run_id)


@router.post("/{run_id}/retry", status_code=202)
async def retry_workflow(project_id: UUID, run_id: UUID, request: Request):
    await request.app.state.workflow.resume(project_id, run_id, retry=True)
    dispatch(request, project_id, str(run_id))
    return {"id_ejecucion": str(run_id)}
