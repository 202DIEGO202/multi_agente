from __future__ import annotations

import hmac
import os
from typing import Any, Optional

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Comentarios breves en español.

app = FastAPI(title="Vacaciones y permisos", version="1.0.3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TipoAusenciaPublicoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    requiere_motivo: bool
    requiere_horas: bool


class TipoAusenciaAdminOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    activo: bool
    visible_publico: bool
    requiere_motivo: bool
    requiere_horas: bool
    requiere_revision_jefe: bool
    requiere_revision_th: bool
    flujo_aprobacion: list[dict[str, Any]] = Field(default_factory=list)


class FlujoItemIn(BaseModel):
    rol_aprobador: str
    activo: bool = True


class TipoAusenciaCreateIn(BaseModel):
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    activo: bool = True
    visible_publico: bool = False
    requiere_motivo: bool = False
    requiere_horas: bool = False
    requiere_revision_jefe: bool = True
    requiere_revision_th: bool = False
    flujo_aprobacion: list[FlujoItemIn] = Field(default_factory=list)


class TipoAusenciaUpdateIn(TipoAusenciaCreateIn):
    pass


class DecisionIn(BaseModel):
    observacion: str
    version: int


def get_conn():
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    token = authorization.removeprefix("Bearer ").strip()
    expected = os.environ.get("ADMIN_API_TOKEN", "")
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="No autorizado")


@app.get("/api/health")
def health():
    return {"estado": "ok"}


@app.get("/api/tipos-ausencia", response_model=list[TipoAusenciaPublicoOut])
def listar_tipos_publicos(conn=Depends(get_conn)):
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT id, codigo, nombre, descripcion, requiere_motivo, requiere_horas
            FROM vacaciones.tipo_ausencia
            WHERE activo = TRUE
              AND visible_publico = TRUE
            ORDER BY nombre
            """
        )
        return cur.fetchall()


@app.get("/api/admin/tipos-ausencia", response_model=list[TipoAusenciaAdminOut], dependencies=[Depends(require_admin)])
def listar_tipos_admin(conn=Depends(get_conn)):
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT t.id, t.codigo, t.nombre, t.descripcion, t.activo, t.visible_publico, t.requiere_motivo,
                   t.requiere_horas, t.requiere_revision_jefe, t.requiere_revision_th,
                   COALESCE(
                     json_agg(
                       json_build_object(
                         'secuencia', f.secuencia,
                         'rol_aprobador', f.rol_aprobador,
                         'activo', f.activo
                       ) ORDER BY f.secuencia
                     ) FILTER (WHERE f.id IS NOT NULL),
                     '[]'::json
                   ) AS flujo_aprobacion
            FROM vacaciones.tipo_ausencia t
            LEFT JOIN vacaciones.flujo_aprobacion f ON f.tipo_ausencia_id = t.id
            GROUP BY t.id
            ORDER BY t.nombre
            """
        )
        return cur.fetchall()


@app.post("/api/admin/tipos-ausencia", dependencies=[Depends(require_admin)])
def crear_tipo(body: TipoAusenciaCreateIn, conn=Depends(get_conn)):
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vacaciones.tipo_ausencia
                (codigo, nombre, descripcion, activo, visible_publico, requiere_motivo, requiere_horas, requiere_revision_jefe, requiere_revision_th)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    body.codigo,
                    body.nombre,
                    body.descripcion,
                    body.activo,
                    body.visible_publico,
                    body.requiere_motivo,
                    body.requiere_horas,
                    body.requiere_revision_jefe,
                    body.requiere_revision_th,
                ),
            )
            tipo_id = cur.fetchone()[0]
            for i, item in enumerate(body.flujo_aprobacion, start=1):
                cur.execute(
                    """
                    INSERT INTO vacaciones.flujo_aprobacion (tipo_ausencia_id, secuencia, rol_aprobador, activo)
                    VALUES (%s,%s,%s,%s)
                    """,
                    (tipo_id, i, item.rol_aprobador, item.activo),
                )
    return {"id": tipo_id}


@app.put("/api/admin/tipos-ausencia/{tipo_id}", dependencies=[Depends(require_admin)])
def actualizar_tipo(tipo_id: int, body: TipoAusenciaUpdateIn, conn=Depends(get_conn)):
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM vacaciones.tipo_ausencia WHERE id=%s", (tipo_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Tipo de ausencia no encontrado")
            cur.execute(
                """
                UPDATE vacaciones.tipo_ausencia
                SET codigo=%s, nombre=%s, descripcion=%s, activo=%s, visible_publico=%s,
                    requiere_motivo=%s, requiere_horas=%s,
                    requiere_revision_jefe=%s, requiere_revision_th=%s,
                    actualizado_en=now()
                WHERE id=%s
                """,
                (
                    body.codigo,
                    body.nombre,
                    body.descripcion,
                    body.activo,
                    body.visible_publico,
                    body.requiere_motivo,
                    body.requiere_horas,
                    body.requiere_revision_jefe,
                    body.requiere_revision_th,
                    tipo_id,
                ),
            )
            cur.execute("DELETE FROM vacaciones.flujo_aprobacion WHERE tipo_ausencia_id=%s", (tipo_id,))
            for i, item in enumerate(body.flujo_aprobacion, start=1):
                cur.execute(
                    """
                    INSERT INTO vacaciones.flujo_aprobacion (tipo_ausencia_id, secuencia, rol_aprobador, activo)
                    VALUES (%s,%s,%s,%s)
                    """,
                    (tipo_id, i, item.rol_aprobador, item.activo),
                )
    return {"id": tipo_id}


@app.get("/api/admin/revisiones/pendientes", dependencies=[Depends(require_admin)])
def pendientes(conn=Depends(get_conn)):
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT 1 AS ok")
        return cur.fetchall()


@app.post("/api/admin/solicitudes/{solicitud_id}/aprobar", dependencies=[Depends(require_admin)])
def aprobar_solicitud(solicitud_id: int, body: DecisionIn, conn=Depends(get_conn)):
    if not body.observacion.strip():
        raise HTTPException(status_code=422, detail="La observación es obligatoria")
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT version, estado_id FROM vacaciones.solicitud WHERE id=%s FOR UPDATE", (solicitud_id,))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Solicitud no encontrada")
            if row[0] != body.version:
                raise HTTPException(status_code=409, detail="Conflicto de estado")
            cur.execute("UPDATE vacaciones.solicitud SET version=version+1, actualizado_en=now() WHERE id=%s", (solicitud_id,))
    return {"estado": "aprobada"}


@app.post("/api/admin/solicitudes/{solicitud_id}/rechazar", dependencies=[Depends(require_admin)])
def rechazar_solicitud(solicitud_id: int, body: DecisionIn, conn=Depends(get_conn)):
    if not body.observacion.strip():
        raise HTTPException(status_code=422, detail="El motivo es obligatorio para rechazar")
    return aprobar_solicitud(solicitud_id, body, conn)