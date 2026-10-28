"""Integración en una base separada: requiere TEST_DATABASE_URL, nunca usa datos del usuario."""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from app.database.connection import Database
from app.models.schemas import Analysis, Change, ProjectCreate, Review
from app.services.events import Events
from app.services.project_service import ProjectService

pytestmark = pytest.mark.integration


def run(coro):
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
    with asyncio.Runner(loop_factory=factory) as runner:
        return runner.run(coro)


@asynccontextmanager
async def environment(mode="supervisado"):
    url = os.getenv("TEST_DATABASE_URL")
    if not url or "fabrica_test" not in url:
        pytest.skip("Configure TEST_DATABASE_URL con una base fabrica_test separada")
    db = Database(url)
    await db.open()
    events = Events(db)
    service = ProjectService(db, events)
    project = await service.create(ProjectCreate(nombre="Proyecto de prueba", modo=mode))
    pid = str(project["id_proyecto"])
    cid, mid = str(uuid4()), str(uuid4())
    await db.execute(
        "INSERT INTO conversations(id,project_id,title) VALUES(%s,%s,'Prueba')", (cid, pid)
    )
    rid = await events.create_run(pid, "chat", conversation_id=cid)
    await db.execute(
        "INSERT INTO messages(id,conversation_id,execution_id,role,content) "
        "VALUES(%s,%s,%s,'user','Requisito de prueba')",
        (mid, cid, rid),
    )
    try:
        yield db, service, events, pid, rid, mid
    finally:
        await db.close()


def new_requirement(text="Registrar solicitudes de soporte"):
    return Change(operacion="crear", tipo="requisito_funcional", descripcion=text)


def test_supervised_version_history_and_immutable_baselines():
    async def scenario():
        async with environment() as (db, service, _, pid, rid, mid):
            proposed = await service.propose(pid, rid, mid, Analysis(cambios=[new_requirement()]))
            state = await service.state(pid)
            assert not state["elementos"]
            assert proposed[0]["estado"] == "propuesto"
            approved = await service.review(pid, proposed[0]["id"], Review(accion="aprobar"))
            assert approved["id_elemento"] == "RF-001"
            first = await service.publish(pid, True)
            change = Change(
                operacion="modificar",
                tipo="requisito_funcional",
                descripcion="Registrar y priorizar solicitudes de soporte",
                id_elemento="RF-001",
                version_esperada=1,
            )
            later_run = await Events(db).create_run(pid, "chat")
            later = await service.propose(pid, later_run, mid, Analysis(cambios=[change]))
            await service.review(pid, later[0]["id"], Review(accion="aprobar"))
            second = await service.publish(pid, True)
            assert second["requisitos"][0]["id"] == "RF-001"
            assert second["requisitos"][0]["version"] == 2
            stored = await db.one(
                "SELECT payload FROM baselines WHERE project_id=%s AND version=1", (pid,)
            )
            assert stored["payload"] == first
            assert first["requisitos"][0]["version"] == 1
            from psycopg import Error

            with pytest.raises(Error, match="inmutables"):
                await db.execute(
                    "UPDATE baselines SET payload=%s WHERE project_id=%s AND version=1",
                    (Jsonb({}), pid),
                )
            history = await db.fetch(
                "SELECT version FROM functional_items WHERE project_id=%s ORDER BY version", (pid,)
            )
            assert [v["version"] for v in history] == [1, 2]
            # Las versiones sobreviven al cierre y reapertura de conexiones.
            reopened = Database(db.url)
            await reopened.open()
            try:
                assert (
                    await reopened.one(
                        "SELECT count(*) AS n FROM baselines WHERE project_id=%s", (pid,)
                    )
                )["n"] == 2
            finally:
                await reopened.close()

    run(scenario())


def test_automatic_validation_is_not_human_approval_and_conflicts_block():
    async def scenario():
        async with environment("automatico") as (db, service, _, pid, rid, mid):
            proposal = await service.propose(pid, rid, mid, Analysis(cambios=[new_requirement()]))
            assert proposal[0]["estado"] == "validado_automaticamente"
            baseline = await service.publish(pid, False)
            assert baseline["estado"] == "validado_automaticamente"
            assert baseline["requisitos"][0]["estado"] == "validado_automaticamente"
            next_run = await Events(db).create_run(pid, "chat")
            result = await service.propose(
                pid,
                next_run,
                mid,
                Analysis(
                    cambios=[new_requirement("Cerrar solicitudes automáticamente")],
                    contradicciones_criticas=[
                        "Los plazos de cierre difieren de la decisión vigente"
                    ],
                ),
            )
            assert result[0]["estado"] == "pendiente_aclaracion"
            with pytest.raises(ValueError, match="contradicciones"):
                await service.publish(pid, False)
            with pytest.raises(ValueError, match="contradicciones"):
                await service.review(pid, result[0]["id"], Review(accion="aprobar"))
            assert len((await service.state(pid))["elementos"]) == 1

    run(scenario())


def test_proposals_are_idempotent_and_stale_approval_is_rejected():
    async def scenario():
        async with environment("automatico") as (db, service, _, pid, rid, mid):
            analysis = Analysis(cambios=[new_requirement()])
            await service.propose(pid, rid, mid, analysis)
            await service.propose(pid, rid, mid, analysis)
            assert len((await service.state(pid))["elementos"]) == 1
            await db.execute("UPDATE projects SET mode='supervisado' WHERE id=%s", (pid,))
            change = Change(
                operacion="modificar",
                tipo="requisito_funcional",
                descripcion="Nuevo alcance A",
                id_elemento="RF-001",
                version_esperada=1,
            )
            run_a, run_b = (
                await Events(db).create_run(pid, "chat"),
                await Events(db).create_run(pid, "chat"),
            )
            a = await service.propose(pid, run_a, mid, Analysis(cambios=[change]))
            b = await service.propose(
                pid,
                run_b,
                mid,
                Analysis(cambios=[change.model_copy(update={"descripcion": "Nuevo alcance B"})]),
            )
            await service.review(pid, a[0]["id"], Review(accion="aprobar"))
            with pytest.raises(ValueError, match="versión"):
                await service.review(pid, b[0]["id"], Review(accion="aprobar"))
            state = await service.state(pid)
            assert state["elementos"][0]["version"] == 2
            assert state["elementos"][0]["descripcion"] == "Nuevo alcance A"

    run(scenario())


def test_pgvector_and_bm25_update_delete_and_project_isolation():
    async def scenario():
        import numpy as np

        from app.rag.bm25_search import BM25Search
        from app.rag.vector_search import vector_search

        async with environment() as (db, service, _, pid, _, __):
            other = str((await service.create(ProjectCreate(nombre="Otro ámbito")))["id_proyecto"])
            doc, chunk = str(uuid4()), str(uuid4())
            await db.execute(
                "INSERT INTO documents(id,project_id,name,media_type,category,content_hash,"
                "status,embedding_signature,storage_path) VALUES(%s,%s,'guia.txt','text/plain','IT',"
                "'hash','indexado','test:2','test')",
                (doc, pid),
            )
            await db.execute(
                "INSERT INTO chunks(id,document_id,page,position,content,embedding) "
                "VALUES(%s,%s,1,0,'VPN corporativa',%s)",
                (chunk, doc, np.array([1.0, 0.0], dtype=np.float32)),
            )
            async with db.pool.connection() as conn:
                results = await vector_search(conn, pid, [1.0, 0.0], 5)
                assert results[0]["puntuacion_vectorial"] == pytest.approx(1)
                assert await vector_search(conn, other, [1.0, 0.0], 5) == []
            bm25 = BM25Search()
            assert bm25.search(pid, 1, results, "VPN", 5)[0]["id_fragmento"] == chunk
            from app.rag.document_ingestion import DocumentIngestion

            assert await DocumentIngestion(db, None, None, None).delete(pid, doc)
            async with db.pool.connection() as conn:
                assert await vector_search(conn, pid, [1.0, 0.0], 5) == []
            assert bm25.search(pid, 2, [], "VPN", 5) == []

    run(scenario())
