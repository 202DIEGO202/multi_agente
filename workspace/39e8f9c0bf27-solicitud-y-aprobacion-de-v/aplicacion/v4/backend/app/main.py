from __future__ import annotations

import hmac
import os
from contextlib import contextmanager
from datetime import date, time
from typing import Any, Optional

import psycopg
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

app = FastAPI(title="Vacaciones y permisos")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

portal_router = APIRouter(prefix="/api")
admin_router = APIRouter(prefix="/api/admin")


@contextmanager
def get_conn():
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def require_admin(authorization: Optional[str] = Header(default=None)):
    token = os.environ.get("ADMIN_API_TOKEN", "")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    bearer = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(bearer, token):
        raise HTTPException(status_code=401, detail="No autorizado")
    return True


class TipoAusenciaPublicoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    requiere_motivo: bool
    permite_horas: bool


class TipoAusenciaAdminOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    requiere_motivo: bool
    permite_horas: bool
    estado: str
    activo: bool
    flujo_aprobacion: list[dict[str, Any]] = Field(default_factory=list)


class SolicitudCreate(BaseModel):
    solicitante_id: int
    solicitante_nombre: str
    solicitante_documento: str
    solicitante_area: str
    solicitante_cargo: str
    tipo_ausencia_id: int
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    motivo_observacion: Optional[str] = None


class DecisionIn(BaseModel):
    observacion: str = Field(min_length=1)


class SolicitudOut(BaseModel):
    id: int
    codigo: str
    estado: str
    version: int


@app.get("/api/health")
def health():
    return {"estado": "ok"}


@portal_router.get("/tipos-ausencia", response_model=list[TipoAusenciaPublicoOut])
def tipos_ausencia_publicos():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, codigo, nombre, descripcion, requiere_motivo, permite_horas
            FROM vacaciones.tipo_ausencia
            WHERE estado = 'activo'
            ORDER BY nombre
            """
        )
        return cur.fetchall()


@admin_router.get("/tipos-ausencia", dependencies=[Depends(require_admin)], response_model=list[TipoAusenciaAdminOut])
def tipos_ausencia_admin():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ta.id, ta.codigo, ta.nombre, ta.descripcion, ta.requiere_motivo,
                   ta.permite_horas, ta.estado, ta.activo,
                   COALESCE(
                     jsonb_agg(
                       jsonb_build_object(
                         'orden', fap.orden,
                         'rol_aprobador', ra.codigo,
                         'obligatorio', fap.obligatorio
                       ) ORDER BY fap.orden
                     ) FILTER (WHERE fap.id IS NOT NULL),
                     '[]'::jsonb
                   ) AS flujo_aprobacion
            FROM vacaciones.tipo_ausencia ta
            LEFT JOIN vacaciones.flujo_aprobacion fa ON fa.tipo_ausencia_id = ta.id
            LEFT JOIN vacaciones.flujo_aprobacion_paso fap ON fap.flujo_aprobacion_id = fa.id
            LEFT JOIN vacaciones.rol_aprobador ra ON ra.id = fap.rol_aprobador_id
            GROUP BY ta.id
            ORDER BY ta.nombre
            """
        )
        return cur.fetchall()


@portal_router.post("/solicitudes", status_code=201, response_model=SolicitudOut)
def crear_solicitud(payload: SolicitudCreate):
    if payload.fecha_fin < payload.fecha_inicio:
        raise HTTPException(status_code=422, detail="Rango de fechas inválido")
    if (payload.hora_inicio is None) ^ (payload.hora_fin is None):
        raise HTTPException(status_code=422, detail="Las horas deben venir completas o no enviarse")
    if payload.hora_inicio and payload.hora_fin and payload.hora_fin <= payload.hora_inicio:
        raise HTTPException(status_code=422, detail="Rango de horas inválido")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, requiere_motivo, permite_horas FROM vacaciones.tipo_ausencia WHERE id=%s AND estado='activo'",
            (payload.tipo_ausencia_id,),
        )
        tipo = cur.fetchone()
        if not tipo:
            raise HTTPException(status_code=422, detail="Tipo de ausencia inválido")
        if tipo["requiere_motivo"] and not (payload.motivo_observacion and payload.motivo_observacion.strip()):
            raise HTTPException(status_code=422, detail="El motivo es obligatorio para este tipo de ausencia")
        if payload.hora_inicio and not tipo["permite_horas"]:
            raise HTTPException(status_code=422, detail="Este tipo de ausencia no permite horas")

        cur.execute("SELECT id FROM vacaciones.solicitud_estado WHERE codigo='enviada'")
        estado = cur.fetchone()
        cur.execute(
            """
            INSERT INTO vacaciones.solicitud
            (codigo, solicitante_id, solicitante_nombre, solicitante_documento, solicitante_area, solicitante_cargo,
             tipo_ausencia_id, fecha_inicio, fecha_fin, hora_inicio, hora_fin, motivo_observacion, estado_id, enviada_en)
            VALUES ('SOL-' || to_char(NOW(),'YYYYMMDDHH24MISSMS'), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, codigo, version
            """,
            (
                payload.solicitante_id,
                payload.solicitante_nombre,
                payload.solicitante_documento,
                payload.solicitante_area,
                payload.solicitante_cargo,
                payload.tipo_ausencia_id,
                payload.fecha_inicio,
                payload.fecha_fin,
                payload.hora_inicio,
                payload.hora_fin,
                payload.motivo_observacion,
                estado["id"],
            ),
        )
        s = cur.fetchone()
        return {"id": s["id"], "codigo": s["codigo"], "estado": "enviada", "version": s["version"]}


@admin_router.get("/solicitudes", dependencies=[Depends(require_admin)])
def listar_solicitudes():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.codigo, se.codigo AS estado, s.version
            FROM vacaciones.solicitud s
            JOIN vacaciones.solicitud_estado se ON se.id = s.estado_id
            ORDER BY s.creada_en DESC
            LIMIT 100
            """
        )
        return cur.fetchall()


@admin_router.post("/solicitudes/{solicitud_id}/aprobar", dependencies=[Depends(require_admin)])
def aprobar_solicitud(solicitud_id: int, payload: DecisionIn):
    if not payload.observacion.strip():
        raise HTTPException(status_code=422, detail="La observación es obligatoria")
    with get_conn() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.id, s.version, se.codigo AS estado
                    FROM vacaciones.solicitud s
                    JOIN vacaciones.solicitud_estado se ON se.id = s.estado_id
                    WHERE s.id=%s
                    FOR UPDATE
                    """,
                    (solicitud_id,),
                )
                s = cur.fetchone()
                if not s:
                    raise HTTPException(status_code=404, detail="Solicitud no encontrada")
                if s["estado"] not in {"enviada", "en_revision"}:
                    raise HTTPException(status_code=409, detail="Conflicto de estado")
                cur.execute("SELECT id FROM vacaciones.solicitud_estado WHERE codigo='aprobada_jefe'")
                nuevo = cur.fetchone()["id"]
                cur.execute(
                    "UPDATE vacaciones.solicitud SET estado_id=%s, version=version+1, actualizada_en=NOW() WHERE id=%s",
                    (nuevo, solicitud_id),
                )
                cur.execute(
                    """
                    INSERT INTO vacaciones.solicitud_historico
                    (solicitud_id, estado_id, actor_id, actor_nombre, accion, observacion, version_anterior, version_nueva)
                    VALUES (%s,%s,NULL,'administrador','aprobacion',%s,%s,%s)
                    """,
                    (solicitud_id, nuevo, payload.observacion, s["version"], s["version"] + 1),
                )
    return {"estado": "aprobada"}


@admin_router.post("/solicitudes/{solicitud_id}/rechazar", dependencies=[Depends(require_admin)])
def rechazar_solicitud(solicitud_id: int, payload: DecisionIn):
    if not payload.observacion.strip():
        raise HTTPException(status_code=422, detail="El motivo es obligatorio al rechazar")
    with get_conn() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.id, s.version, se.codigo AS estado
                    FROM vacaciones.solicitud s
                    JOIN vacaciones.solicitud_estado se ON se.id = s.estado_id
                    WHERE s.id=%s
                    FOR UPDATE
                    """,
                    (solicitud_id,),
                )
                s = cur.fetchone()
                if not s:
                    raise HTTPException(status_code=404, detail="Solicitud no encontrada")
                if s["estado"] not in {"enviada", "en_revision", "aprobada_jefe"}:
                    raise HTTPException(status_code=409, detail="Conflicto de estado")
                cur.execute("SELECT id FROM vacaciones.solicitud_estado WHERE codigo='rechazada_jefe'")
                nuevo = cur.fetchone()["id"]
                cur.execute(
                    "UPDATE vacaciones.solicitud SET estado_id=%s, version=version+1, actualizada_en=NOW() WHERE id=%s",
                    (nuevo, solicitud_id),
                )
                cur.execute(
                    """
                    INSERT INTO vacaciones.solicitud_historico
                    (solicitud_id, estado_id, actor_id, actor_nombre, accion, observacion, version_anterior, version_nueva)
                    VALUES (%s,%s,NULL,'administrador','rechazo',%s,%s,%s)
                    """,
                    (solicitud_id, nuevo, payload.observacion, s["version"], s["version"] + 1),
                )
    return {"estado": "rechazada"}


app.include_router(portal_router)
app.include_router(admin_router)