from __future__ import annotations

import hmac
import json
import os
from datetime import date, datetime, time
from typing import Any, Optional
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")

app = FastAPI()


class TiposAusenciaPublicoOut(BaseModel):
    id: UUID
    nombre: str


class TipoAusenciaAdminOut(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str]
    requiere_motivo: bool
    requiere_observacion: bool
    permite_horas: bool
    activo: bool
    version: int
    creado_en: datetime
    actualizado_en: datetime


class SolicitudDecisionBody(BaseModel):
    observacion: Optional[str] = None

    @field_validator("observacion")
    @classmethod
    def validar_observacion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("La observación no puede estar vacía")
        return v


class DecisionRespuesta(BaseModel):
    id: UUID
    solicitud_id: UUID
    estado_resultante: str
    version_solicitud: int
    observacion: Optional[str]
    decidida_en: datetime
    decidida_por: Optional[UUID]


class SolicitudAdminDetalle(BaseModel):
    id: UUID
    solicitante_id: UUID
    tipo_ausencia_id: UUID
    estado_id: int
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: Optional[time]
    hora_fin: Optional[time]
    motivo: Optional[str]
    observacion: Optional[str]
    version: int
    creado_en: datetime
    actualizado_en: datetime
    historial: list[dict[str, Any]] = Field(default_factory=list)


def get_conn():
    conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autorizado")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, ADMIN_API_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autorizado")


def registrar_auditoria_acceso(conn, usuario_id: UUID | None, accion: str, recurso: str, referencia_id: UUID | None, request: Request):
    conn.execute(
        """
        INSERT INTO auditoria_acceso (usuario_id, accion, recurso, referencia_id, ip, usuario_agente)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            usuario_id,
            accion,
            recurso,
            referencia_id,
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
        ),
    )


def obtener_estado_id(conn, codigo: str) -> int:
    row = conn.execute("SELECT id FROM estado_solicitud WHERE codigo = %s AND activo = TRUE", (codigo,)).fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Estado no configurado")
    return int(row["id"])


@app.get("/api/health")
def health():
    return {"estado": "ok"}


@app.get("/api/tipos-ausencia", response_model=list[TiposAusenciaPublicoOut])
def listar_tipos_ausencia_publicos(request: Request, conn=Depends(get_conn)):
    rows = conn.execute("SELECT id, nombre FROM tipo_ausencia WHERE activo = TRUE ORDER BY nombre").fetchall()
    registrar_auditoria_acceso(conn, None, "CONSULTAR", "TIPOS_AUSENCIA_PUBLICOS", None, request)
    return rows


@app.get("/api/admin/tipos-ausencia", response_model=list[TipoAusenciaAdminOut], dependencies=[Depends(require_admin)])
def listar_tipos_ausencia_admin(request: Request, conn=Depends(get_conn)):
    rows = conn.execute(
        """
        SELECT id, nombre, descripcion, requiere_motivo, requiere_observacion, permite_horas,
               activo, version, creado_en, actualizado_en
        FROM tipo_ausencia
        ORDER BY nombre
        """
    ).fetchall()
    registrar_auditoria_acceso(conn, None, "CONSULTAR", "TIPOS_AUSENCIA_ADMIN", None, request)
    return rows


@app.get("/api/admin/solicitudes/{id}", response_model=SolicitudAdminDetalle, dependencies=[Depends(require_admin)])
def detalle_solicitud_admin(id: UUID, request: Request, conn=Depends(get_conn)):
    solicitud = conn.execute(
        """
        SELECT id, solicitante_id, tipo_ausencia_id, estado_id, fecha_inicio, fecha_fin,
               hora_inicio, hora_fin, motivo, observacion, version, creado_en, actualizado_en
        FROM solicitud_ausencia
        WHERE id = %s
        """,
        (id,),
    ).fetchone()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    historial = conn.execute(
        """
        SELECT id, estado_id, actor_id, operacion, observacion, detalle, creado_en
        FROM historial_solicitud
        WHERE solicitud_id = %s
        ORDER BY creado_en ASC
        """,
        (id,),
    ).fetchall()
    registrar_auditoria_acceso(conn, None, "CONSULTAR", "SOLICITUD_ADMIN", id, request)
    data = dict(solicitud)
    data["historial"] = historial
    return data


@app.post("/api/admin/solicitudes/{id}/aprobar", response_model=DecisionRespuesta, dependencies=[Depends(require_admin)])
def aprobar_solicitud(id: UUID, body: SolicitudDecisionBody, request: Request, conn=Depends(get_conn)):
    return _decidir_solicitud(id, body, "APROBADA", "APROBAR", request, conn)


@app.post("/api/admin/solicitudes/{id}/rechazar", response_model=DecisionRespuesta, dependencies=[Depends(require_admin)])
def rechazar_solicitud(id: UUID, body: SolicitudDecisionBody, request: Request, conn=Depends(get_conn)):
    if body.observacion is None:
        raise HTTPException(status_code=422, detail="La observación es obligatoria para rechazar")
    return _decidir_solicitud(id, body, "RECHAZADA", "RECHAZAR", request, conn)


def _decidir_solicitud(id: UUID, body: SolicitudDecisionBody, codigo_estado: str, operacion: str, request: Request, conn):
    estado_id = obtener_estado_id(conn, codigo_estado)
    if codigo_estado == "RECHAZADA" and not body.observacion:
        raise HTTPException(status_code=422, detail="La observación es obligatoria para rechazar")
    with conn.transaction():
        solicitud = conn.execute(
            "SELECT id, estado_id, version, solicitante_id FROM solicitud_ausencia WHERE id = %s FOR UPDATE",
            (id,),
        ).fetchone()
        if not solicitud:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada")
        estado_actual = int(solicitud["estado_id"])
        if estado_actual in (obtener_estado_id(conn, "APROBADA"), obtener_estado_id(conn, "RECHAZADA"), obtener_estado_id(conn, "CANCELADA")):
            raise HTTPException(status_code=409, detail="La solicitud ya tiene una decisión final")
        version_actual = int(solicitud["version"])
        nueva_version = version_actual + 1
        updated = conn.execute(
            """
            UPDATE solicitud_ausencia
            SET estado_id = %s, version = %s, actualizado_en = now()
            WHERE id = %s AND version = %s
            RETURNING id
            """,
            (estado_id, nueva_version, id, version_actual),
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=409, detail="Conflicto de versión")
        actor_id = None
        conn.execute(
            """
            INSERT INTO revision_solicitud (solicitud_id, revisor_id, estado_resultante_id, observacion, version_solicitud)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (id, actor_id, estado_id, body.observacion, version_actual),
        )
        conn.execute(
            """
            INSERT INTO historial_solicitud (solicitud_id, estado_id, actor_id, operacion, observacion, detalle)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (id, estado_id, actor_id, operacion, body.observacion, json.dumps({"estado": codigo_estado})),
        )
        registrar_auditoria_acceso(conn, None, operacion, "SOLICITUD_ADMIN", id, request)
    return {
        "id": id,
        "solicitud_id": id,
        "estado_resultante": codigo_estado,
        "version_solicitud": nueva_version,
        "observacion": body.observacion,
        "decidida_en": datetime.utcnow(),
        "decidida_por": None,
    }