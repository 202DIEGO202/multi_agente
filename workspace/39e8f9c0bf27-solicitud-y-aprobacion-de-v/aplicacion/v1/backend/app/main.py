import hmac
import json
import os
from datetime import date, time
from typing import Optional

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AdminUser(BaseModel):
    usuario: str = "admin"
    rol: str = "ADMINISTRADOR"


class SolicitudCreate(BaseModel):
    solicitante_nombre: str = Field(min_length=1, max_length=200)
    solicitante_documento: str = Field(min_length=1, max_length=30)
    area: str = Field(min_length=1, max_length=120)
    cargo: str = Field(min_length=1, max_length=120)
    tipo_ausencia_id: int = Field(gt=0)
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    motivo_observacion: Optional[str] = None
    creado_por: str = Field(min_length=1, max_length=120)
    creador_rol: str = Field(default="EMPLEADO")


class DecisionCreate(BaseModel):
    observacion: str = Field(min_length=1, max_length=1000)
    usuario: str = Field(min_length=1, max_length=120)
    rol: str = Field(min_length=1, max_length=60)
    version_esperada: Optional[int] = Field(default=None, ge=1)


class TipoAusenciaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: Optional[str] = None
    requiere_motivo: bool = False
    requiere_horas: bool = False
    requiere_aprobacion_th: bool = False
    requiere_aprobacion_jefe: bool = True
    activo: bool = True
    flujo_aprobacion_id: Optional[int] = None


class TipoAusenciaUpdate(TipoAusenciaCreate):
    pass


class FlujoAsignar(BaseModel):
    flujo_aprobacion_id: int = Field(gt=0)


def get_conn():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


def require_admin(authorization: Optional[str] = Header(default=None)) -> AdminUser:
    token = os.environ.get("ADMIN_API_TOKEN", "")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    provided = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="No autorizado")
    return AdminUser()


def audit_access(usuario: str, rol: str, accion: str, entidad: str, entidad_id: Optional[str], detalle: dict, ip: Optional[str]):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO auditoria_acceso (usuario, rol, accion, entidad, entidad_id, detalle, ip)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (usuario, rol, accion, entidad, entidad_id, json.dumps(detalle), ip),
        )


def row_to_dict(cur, row):
    return dict(zip([c.name for c in cur.description], row))


@app.get("/api/health")
def health():
    return {"estado": "ok"}


@app.get("/api/tipos-ausencia")
def listar_tipos_ausencia():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, codigo, nombre FROM tipo_ausencia WHERE activo = TRUE ORDER BY nombre")
        return [row_to_dict(cur, row) for row in cur.fetchall()]


@app.post("/api/solicitudes", status_code=201)
def crear_solicitud(payload: SolicitudCreate, request: Request):
    if payload.fecha_fin < payload.fecha_inicio:
        raise HTTPException(status_code=422, detail="Fechas inválidas")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT requiere_motivo, requiere_horas, activo FROM tipo_ausencia WHERE id=%s", (payload.tipo_ausencia_id,))
        tipo = cur.fetchone()
        if not tipo or not tipo[2]:
            raise HTTPException(status_code=422, detail="Tipo de ausencia inválido")
        if tipo[0] and not payload.motivo_observacion:
            raise HTTPException(status_code=422, detail="El motivo/observación es obligatorio")
        if tipo[1] and (payload.hora_inicio is None or payload.hora_fin is None):
            raise HTTPException(status_code=422, detail="Las horas son obligatorias")
        if payload.hora_inicio is not None and payload.hora_fin is not None and payload.hora_fin <= payload.hora_inicio:
            raise HTTPException(status_code=422, detail="Horas inválidas")
        cur.execute(
            """INSERT INTO solicitud_ausencia
               (solicitante_nombre, solicitante_documento, area, cargo, tipo_ausencia_id, fecha_inicio, fecha_fin, hora_inicio, hora_fin, motivo_observacion, estado_codigo, creado_por)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ENVIADA',%s)
               RETURNING id""",
            (
                payload.solicitante_nombre,
                payload.solicitante_documento,
                payload.area,
                payload.cargo,
                payload.tipo_ausencia_id,
                payload.fecha_inicio,
                payload.fecha_fin,
                payload.hora_inicio,
                payload.hora_fin,
                payload.motivo_observacion,
                payload.creado_por,
            ),
        )
        solicitud_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO historial_solicitud
               (solicitud_id, estado_codigo, accion, observacion, actor_usuario, actor_rol, version_resultante)
               VALUES (%s,'ENVIADA','CREADA',%s,%s,%s,1)""",
            (solicitud_id, payload.motivo_observacion, payload.creado_por, payload.creador_rol),
        )
    audit_access(payload.creado_por, payload.creador_rol, "CREAR_SOLICITUD", "solicitud_ausencia", str(solicitud_id), {"accion": "crear"}, request.headers.get("x-forwarded-for"))
    return {"id": solicitud_id}


@app.get("/api/admin/solicitudes")
def admin_listar_solicitudes(admin: AdminUser = Depends(require_admin)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, solicitante_nombre, solicitante_documento, area, cargo, tipo_ausencia_id, fecha_inicio, fecha_fin, estado_codigo, version, creado_en FROM solicitud_ausencia WHERE eliminado_en IS NULL ORDER BY creado_en DESC")
        return [row_to_dict(cur, row) for row in cur.fetchall()]


@app.get("/api/admin/solicitudes/{solicitud_id}")
def admin_detalle_solicitud(solicitud_id: int, admin: AdminUser = Depends(require_admin)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM solicitud_ausencia WHERE id=%s", (solicitud_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No encontrado")
        return row_to_dict(cur, row)


@app.get("/api/admin/solicitudes/{solicitud_id}/historial")
def admin_historial_solicitud(solicitud_id: int, admin: AdminUser = Depends(require_admin)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, solicitud_id, estado_codigo, accion, observacion, actor_usuario, actor_rol, version_resultante, creado_en FROM historial_solicitud WHERE solicitud_id=%s ORDER BY creado_en ASC", (solicitud_id,))
        return [row_to_dict(cur, row) for row in cur.fetchall()]


def _decidir_solicitud(solicitud_id: int, payload: DecisionCreate, estado: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT estado_codigo, version FROM solicitud_ausencia WHERE id=%s FOR UPDATE", (solicitud_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No encontrado")
        if row[0] in ("APROBADA", "RECHAZADA", "CANCELADA"):
            raise HTTPException(status_code=409, detail="Conflicto de estado")
        if payload.version_esperada is not None and payload.version_esperada != row[1]:
            raise HTTPException(status_code=409, detail="Conflicto de estado")
        nueva_version = row[1] + 1
        cur.execute("UPDATE solicitud_ausencia SET estado_codigo=%s, version=%s, actualizado_en=now() WHERE id=%s AND version=%s", (estado, nueva_version, solicitud_id, row[1]))
        if cur.rowcount != 1:
            raise HTTPException(status_code=409, detail="Conflicto de estado")
        cur.execute(
            """INSERT INTO revision_solicitud
               (solicitud_id, secuencia, rol_revisor, revisor_usuario, decision, observacion, version_esperada, version_real, decidido_en)
               VALUES (%s, COALESCE((SELECT MAX(secuencia) + 1 FROM revision_solicitud WHERE solicitud_id=%s), 1), %s, %s, %s, %s, %s, %s, now())""",
            (solicitud_id, solicitud_id, payload.rol, payload.usuario, estado, payload.observacion, payload.version_esperada or row[1], nueva_version),
        )
        cur.execute("""INSERT INTO historial_solicitud
               (solicitud_id, estado_codigo, accion, observacion, actor_usuario, actor_rol, version_resultante)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""", (solicitud_id, estado, estado, payload.observacion, payload.usuario, payload.rol, nueva_version))
    return {"estado": estado}


@app.post("/api/admin/solicitudes/{solicitud_id}/aprobar")
def aprobar_solicitud(solicitud_id: int, payload: DecisionCreate, admin: AdminUser = Depends(require_admin)):
    return _decidir_solicitud(solicitud_id, payload, "APROBADA")


@app.post("/api/admin/solicitudes/{solicitud_id}/rechazar")
def rechazar_solicitud(solicitud_id: int, payload: DecisionCreate, admin: AdminUser = Depends(require_admin)):
    return _decidir_solicitud(solicitud_id, payload, "RECHAZADA")


@app.post("/api/admin/solicitudes/{solicitud_id}/validar")
def validar_solicitud(solicitud_id: int, payload: DecisionCreate, admin: AdminUser = Depends(require_admin)):
    return _decidir_solicitud(solicitud_id, payload, "VALIDADA")


@app.post("/api/admin/solicitudes/{solicitud_id}/{accion}")
def decidir_solicitud_generica(solicitud_id: int, accion: str, payload: DecisionCreate, admin: AdminUser = Depends(require_admin)):
    accion = accion.lower()
    if accion == "aprobar":
        return _decidir_solicitud(solicitud_id, payload, "APROBADA")
    if accion == "rechazar":
        return _decidir_solicitud(solicitud_id, payload, "RECHAZADA")
    if accion == "validar":
        return _decidir_solicitud(solicitud_id, payload, "VALIDADA")
    raise HTTPException(status_code=422, detail="Acción inválida")


@app.get("/api/admin/tipos-ausencia")
def admin_listar_tipos(admin: AdminUser = Depends(require_admin)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM tipo_ausencia ORDER BY nombre")
        return [row_to_dict(cur, row) for row in cur.fetchall()]


@app.post("/api/admin/tipos-ausencia")
def admin_crear_tipo(payload: TipoAusenciaCreate, admin: AdminUser = Depends(require_admin)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO tipo_ausencia
               (codigo, nombre, descripcion, requiere_motivo, requiere_horas, requiere_aprobacion_th, requiere_aprobacion_jefe, activo, flujo_aprobacion_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",
            (payload.codigo, payload.nombre, payload.descripcion, payload.requiere_motivo, payload.requiere_horas, payload.requiere_aprobacion_th, payload.requiere_aprobacion_jefe, payload.activo, payload.flujo_aprobacion_id),
        )
        return {"id": cur.fetchone()[0]}