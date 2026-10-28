import json
from uuid import uuid4

from psycopg.types.json import Jsonb

SENSITIVE = {"password", "token", "api_key", "authorization", "secret", "thinking", "reasoning"}


def clean(value):
    if isinstance(value, dict):
        return {
            k: clean(v)
            for k, v in value.items()
            if not any(word in k.casefold() for word in SENSITIVE)
        }
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


class Events:
    def __init__(self, db):
        self.db = db

    async def create_run(self, project_id, kind, data=None, conversation_id=None, request_id=None):
        run_id = str(uuid4())
        await self.db.execute(
            "INSERT INTO executions(id,project_id,kind,input,conversation_id,request_id) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (run_id, project_id, kind, Jsonb(data or {}), conversation_id, request_id),
        )
        return run_id

    async def emit(
        self, run_id, component, operation, status, description, data=None, duration=None
    ):
        await self.db.execute(
            "INSERT INTO events(execution_id,component,operation,status,description,data,duration_ms) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (run_id, component, operation, status, description, Jsonb(clean(data or {})), duration),
        )

    async def status(self, run_id, status, output=None):
        await self.db.execute(
            "UPDATE executions SET status=%s,output=%s,finished_at=CASE "
            "WHEN %s IN ('completado','error','interrumpido') THEN now() ELSE NULL END WHERE id=%s",
            (status, Jsonb(output) if output is not None else None, status, run_id),
        )

    async def list(self, run_id, after=0):
        return await self.db.fetch(
            "SELECT id AS id_evento,execution_id AS id_ejecucion,created_at AS fecha,"
            "component AS componente,operation AS operacion,status AS estado,"
            "description AS descripcion,data AS datos,duration_ms AS duracion_ms "
            "FROM events WHERE execution_id=%s AND id>%s ORDER BY id LIMIT 250",
            (run_id, after),
        )


def sse(event: str, data, event_id=None):
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return (
        prefix
        + f"event: {event}\ndata: "
        + json.dumps(data, default=str, ensure_ascii=False)
        + "\n\n"
    )
