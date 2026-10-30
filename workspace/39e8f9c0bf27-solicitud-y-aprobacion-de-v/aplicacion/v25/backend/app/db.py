import os
from contextlib import contextmanager
from typing import Any

import psycopg
from fastapi import HTTPException, Request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def get_db():
    try:
        with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row, connect_timeout=10) as connection:
            yield connection
    except psycopg.Error as exc:
        if exc.sqlstate in {'40001', '40P01', '23505', '55000'}:
            raise HTTPException(409, 'Conflicto de estado, versión o registro duplicado') from exc
        if exc.sqlstate == '42501':
            raise HTTPException(403, 'Operación no autorizada') from exc
        if exc.sqlstate in {'23514', '23503', '23502', '22001', '22007', 'P0002'}:
            raise HTTPException(422, 'Los datos incumplen las reglas o referencias del sistema') from exc
        raise HTTPException(503, 'Servicio de persistencia no disponible') from exc


@contextmanager
def transaction(connection, actor):
    with connection.transaction():
        connection.execute("SELECT set_config('app.usuario_id', %s, true)", (str(actor['id']),))
        yield


def audit(connection, actor, request: Request, operation: str, solicitud_id=None, authorized=True, detail: dict[str, Any] | None = None):
    connection.execute(
        'INSERT INTO auditoria_acceso (actor_id, solicitud_id, operacion, autorizado, identificador_peticion, detalle) VALUES (%s,%s,%s,%s,%s,%s)',
        (actor['id'], solicitud_id, operation, authorized, request.state.request_id, Jsonb(detail or {})),
    )