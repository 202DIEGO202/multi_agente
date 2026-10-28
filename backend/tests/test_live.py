"""Verifica la API configurada sobre una base de pruebas separada; consume tokens."""

import os
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from test_persistence import environment, run

from app.agents.functional_analyst import FunctionalAnalyst
from app.config import Settings
from app.providers import Models
from app.rag.rag_service import RAGService

pytestmark = pytest.mark.live


def test_real_langgraph_conversation_and_requirement_modification():
    if not os.getenv("RUN_LIVE_TESTS"):
        pytest.skip("Active RUN_LIVE_TESTS=1 para ejecutar modelos locales reales")

    async def scenario():
        async with environment("automatico") as (db, projects, events, pid, rid, mid):
            models = Models(Settings())
            try:
                saver = AsyncPostgresSaver(db.pool)
                await saver.setup()
                rag = RAGService(db, models, models.settings, events)
                rag.search_knowledge = AsyncMock(wraps=rag.search_knowledge)
                analyst = FunctionalAnalyst(db, models, rag, projects, events, saver)
                conversation = await db.one(
                    "SELECT conversation_id FROM executions WHERE id=%s", (rid,)
                )
                initial = {
                    "project_id": pid,
                    "conversation_id": str(conversation["conversation_id"]),
                    "execution_id": rid,
                    "message_id": mid,
                    "message": "Requisito funcional explícito: el sistema debe registrar solicitudes de soporte con su descripción y prioridad.",
                }
                await db.execute(
                    "UPDATE messages SET content=%s WHERE id=%s", (initial["message"], mid)
                )
                first = await analyst.graph.ainvoke(initial, {"configurable": {"thread_id": rid}})
                assert first["response"].strip()
                assert not first["interpretation"]["consultar_conocimiento"]
                assert rag.search_knowledge.await_count == 0
                state = await projects.state(pid)
                assert any(i["tipo"] == "requisito_funcional" for i in state["elementos"])
                item = next(i for i in state["elementos"] if i["tipo"] == "requisito_funcional")
                await events.status(rid, "completado")
                next_run = await events.create_run(
                    pid, "chat", conversation_id=conversation["conversation_id"]
                )
                next_message = str(uuid4())
                text = (
                    f"Modifica el requisito {item['id']} versión {item['version']}: "
                    "el sistema debe registrar solicitudes de soporte con descripción, prioridad y correo del solicitante. "
                    "Es una corrección del mismo requisito, no uno nuevo."
                )
                await db.execute(
                    "INSERT INTO messages(id,conversation_id,execution_id,role,content) "
                    "VALUES(%s,%s,%s,'user',%s)",
                    (next_message, conversation["conversation_id"], next_run, text),
                )
                second = await analyst.graph.ainvoke(
                    {
                        **initial,
                        "execution_id": next_run,
                        "message_id": next_message,
                        "message": text,
                    },
                    {"configurable": {"thread_id": next_run}},
                )
                assert second["response"].strip()
                final = await projects.state(pid)
                updated = next(i for i in final["elementos"] if i["id"] == item["id"])
                assert updated["version"] == item["version"] + 1
                assert "correo" in updated["descripcion"].casefold()
                checkpoint = await analyst.graph.aget_state(
                    {"configurable": {"thread_id": next_run}}
                )
                assert checkpoint.values["response"] == second["response"]
                messages = await db.fetch(
                    "SELECT * FROM messages WHERE conversation_id=%s",
                    (conversation["conversation_id"],),
                )
                assert len(messages) == 4
            finally:
                await models.close()

    run(scenario())
