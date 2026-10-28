import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.errors import CheckViolation

from app.agents.architecture_team import ArchitectureTeam
from app.agents.backlog_team import BacklogTeam
from app.agents.construction_team import ConstructionTeam
from app.agents.functional_analyst import FunctionalAnalyst
from app.agents.mockup_team import MockupTeam
from app.api.architecture import router as architecture_router
from app.api.backlog import router as backlog_router
from app.api.construction import notifications as notifications_router
from app.api.construction import router as construction_router
from app.api.mockups import router as mockup_router
from app.api.routes import router
from app.api.workflow import router as workflow_router
from app.config import get_settings
from app.database.connection import Database
from app.providers import Models
from app.rag.document_ingestion import DocumentIngestion
from app.rag.rag_service import RAGService
from app.services.architecture_service import ArchitectureService
from app.services.backlog_service import BacklogService
from app.services.construction_service import ConstructionService
from app.services.development_workflow import DevelopmentWorkflow
from app.services.events import Events
from app.services.knowledge_service import KnowledgeService
from app.services.mockup_service import MockupService
from app.services.project_service import ProjectService

# Trazas de la plataforma (logger "trama") en la salida del servidor; uvicorn conserva los suyos.
_trama_logger = logging.getLogger("trama")
if not _trama_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    _trama_logger.addHandler(_handler)
    _trama_logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app):
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    settings = get_settings()
    if not settings.api_token.get_secret_value():
        _trama_logger.warning(
            "API_TOKEN vacío: la API no exige autenticación. Úselo solo en este equipo (127.0.0.1)."
        )
    db = Database(settings.database_url.get_secret_value())
    await db.open()
    models = Models(settings)
    try:
        checkpointer = AsyncPostgresSaver(db.pool)
        await checkpointer.setup()
        events = Events(db)
        projects = ProjectService(db, events)
        rag = RAGService(db, models, settings, events)
        app.state.settings, app.state.db, app.state.models = settings, db, models
        app.state.events, app.state.projects, app.state.rag = events, projects, rag
        app.state.knowledge = KnowledgeService(db, settings)
        app.state.ingestion = DocumentIngestion(db, models, settings, events)
        app.state.analyst = FunctionalAnalyst(db, models, rag, projects, events, checkpointer)
        app.state.backlog = BacklogService(db, events)
        app.state.backlog_team = BacklogTeam(app.state.backlog, models, events, checkpointer)
        app.state.mockups = MockupService(db, events, app.state.backlog)
        app.state.mockup_team = MockupTeam(app.state.mockups, models, events, checkpointer)
        app.state.architecture = ArchitectureService(db, events, app.state.mockups, settings)
        app.state.architecture_team = ArchitectureTeam(
            app.state.architecture, models, events, checkpointer
        )
        app.state.construction = ConstructionService(db, events, settings, app.state.mockups)
        app.state.construction_team = ConstructionTeam(
            app.state.construction, models, events, checkpointer
        )
        app.state.tasks = set()
        app.state.workflow_tasks = {}
        app.state.workflow = DevelopmentWorkflow(app)
        await db.execute(
            "UPDATE executions SET status='interrumpido',finished_at=now() "
            "WHERE status IN ('ejecutando','pendiente')"
        )
        await db.execute(
            "UPDATE deployments SET status='interrumpido',updated_at=now() WHERE status='ejecutando'"
        )
        yield
    finally:
        tasks = getattr(app.state, "tasks", set())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await models.close()
        await db.close()


app = FastAPI(title="Fábrica de Software · Análisis y backlog", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Last-Event-ID"],
)
app.include_router(router)
app.include_router(backlog_router)
app.include_router(mockup_router)
app.include_router(architecture_router)
app.include_router(construction_router)
app.include_router(notifications_router)
app.include_router(workflow_router)


@app.exception_handler(LookupError)
async def not_found(request: Request, exc: LookupError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(CheckViolation)
async def project_constraint(request: Request, exc: CheckViolation):
    if exc.diag.constraint_name == "project_in_trash":
        return JSONResponse(
            status_code=409,
            content={"detail": "El proyecto está en la papelera. Restáuralo antes de continuar."},
        )
    return JSONResponse(
        status_code=409, content={"detail": "La operación no cumple las reglas del proyecto."}
    )


@app.exception_handler(ValueError)
async def invalid_operation(request: Request, exc: ValueError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    route = request.scope.get("route")
    route_path = getattr(route, "path", "<ruta-no-resuelta>")
    _trama_logger.error(
        "Error HTTP no controlado en %s %s (%s)",
        request.method,
        route_path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Ocurrió un error interno. El detalle no se expone en la respuesta."
        },
    )
