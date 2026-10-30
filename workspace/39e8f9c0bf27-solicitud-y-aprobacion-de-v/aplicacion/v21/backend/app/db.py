import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row


def get_db() -> Iterator[psycopg.Connection]:
    try:
        with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as connection:
            yield connection
    except psycopg.Error as exc:
        if exc.sqlstate in {'40001', '40P01', '23505', '23503'}:
            raise HTTPException(409, 'Conflicto de versión, concurrencia o referencias existentes') from exc
        if exc.sqlstate in {'23514', '23502', '22001', '22003', '22007', '22P02'}:
            raise HTTPException(422, 'Los datos incumplen las restricciones del dominio') from exc
        if exc.sqlstate == '42501':
            raise HTTPException(403, 'Operación no autorizada') from exc
        raise HTTPException(503, 'Servicio de persistencia no disponible') from exc
    except KeyError as exc:
        raise HTTPException(503, 'Configuración de persistencia incompleta') from exc


@contextmanager
def actor_transaction(db: psycopg.Connection, actor_id: int):
    # Los disparadores usan esta identidad únicamente dentro de la transacción.
    with db.transaction():
        db.execute("SELECT set_config('app.usuario_id', %s, true)", (str(actor_id),))
        yield


def audit_access(db, actor_id, operation, solicitud_id=None, result='PERMITIDO'):
    db.execute(
        'INSERT INTO auditoria_acceso (actor_id, solicitud_id, operacion, resultado) VALUES (%s, %s, %s, %s)',
        (actor_id, solicitud_id, operation, result),
    )