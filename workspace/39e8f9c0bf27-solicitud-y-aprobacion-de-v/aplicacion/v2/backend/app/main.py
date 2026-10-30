import hmac
import json
import os
from typing import Any, Optional

import psycopg
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

app = FastAPI()

api_router = APIRouter(prefix="/api")
admin_router = APIRouter(prefix="/api/admin")


def get_conn():
    url = os.environ["DATABASE_URL"]
    conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def require_admin(authorization: Optional[str] = Header(default=None)):
    token = os.environ.get("ADMIN_API_TOKEN", "")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    provided = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="No autorizado")
    return True


def audit_access(conn, actor_id: Optional[int], recurso: str, operacion: str, detalle: Any = None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vacaciones.auditoria_acceso (actor_id, recurso, operacion, detalle)
            VALUES (%s, %s, %s, %s)
            """,
            (actor_id, recurso, operacion, json.dumps(detalle) if detalle is not None else None),
        )


class HealthResponse(BaseModel):
    estado: str


class TipoAusenciaPublico(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    permite_horas: bool


class TipoAusenciaAdmin(BaseModel):
    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    requiere_motivo: bool
    requiere_observacion: bool
    permite_horas: bool
    requiere_validacion_th: bool
    activo: bool
    visible_portal: bool
    visible_publico: bool
    version: int


class TipoAusenciaUpsert(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: Optional[str] = None
    requiere_motivo: bool = False
    requiere_observacion: bool = False
    permite_horas: bool = False
    requiere_validacion_th: bool = False
    activo: bool = True
    visible_portal: bool = True
    visible_publico: bool = False


class TipoAusenciaFlujo(BaseModel):
    rol_aprobador_codigo: str = Field(min_length=1, max_length=30)
    es_obligatorio: bool = True
    activo: bool = True


@app.get("/api/health", response_model=HealthResponse)
def health():
    return {"estado": "ok"}


@api_router.get("/tipos-ausencia", response_model=list[TipoAusenciaPublico])
def listar_tipos_ausencia_publico(conn=Depends(get_conn), request: Request = None):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, nombre, descripcion, permite_horas
            FROM vacaciones.v_tipo_ausencia_publico
            ORDER BY nombre
            """
        )
        rows = cur.fetchall()
    return rows


@admin_router.get("/tipos-ausencia", response_model=list[TipoAusenciaAdmin], dependencies=[Depends(require_admin)])
def listar_tipos_ausencia_admin(conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, codigo, nombre, descripcion, requiere_motivo, requiere_observacion,
                   permite_horas, requiere_validacion_th, activo, visible_portal,
                   visible_publico, version
            FROM vacaciones.tipo_ausencia
            ORDER BY nombre
            """
        )
        return cur.fetchall()


@admin_router.post("/tipos-ausencia", response_model=TipoAusenciaAdmin, status_code=201, dependencies=[Depends(require_admin)])
def crear_tipo_ausencia(payload: TipoAusenciaUpsert, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vacaciones.tipo_ausencia
            (codigo, nombre, descripcion, requiere_motivo, requiere_observacion, permite_horas,
             requiere_validacion_th, activo, visible_portal, visible_publico)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id, codigo, nombre, descripcion, requiere_motivo, requiere_observacion,
                      permite_horas, requiere_validacion_th, activo, visible_portal,
                      visible_publico, version
            """,
            (
                payload.codigo,
                payload.nombre,
                payload.descripcion,
                payload.requiere_motivo,
                payload.requiere_observacion,
                payload.permite_horas,
                payload.requiere_validacion_th,
                payload.activo,
                payload.visible_portal,
                payload.visible_publico,
            ),
        )
        return cur.fetchone()


@admin_router.put("/tipos-ausencia/{tipo_id}", response_model=TipoAusenciaAdmin, dependencies=[Depends(require_admin)])
def actualizar_tipo_ausencia(tipo_id: int, payload: TipoAusenciaUpsert, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE vacaciones.tipo_ausencia
               SET codigo=%s, nombre=%s, descripcion=%s, requiere_motivo=%s,
                   requiere_observacion=%s, permite_horas=%s, requiere_validacion_th=%s,
                   activo=%s, visible_portal=%s, visible_publico=%s, version=version+1,
                   actualizado_en=now()
             WHERE id=%s
             RETURNING id, codigo, nombre, descripcion, requiere_motivo, requiere_observacion,
                       permite_horas, requiere_validacion_th, activo, visible_portal,
                       visible_publico, version
            """,
            (
                payload.codigo,
                payload.nombre,
                payload.descripcion,
                payload.requiere_motivo,
                payload.requiere_observacion,
                payload.permite_horas,
                payload.requiere_validacion_th,
                payload.activo,
                payload.visible_portal,
                payload.visible_publico,
                tipo_id,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Tipo de ausencia no encontrado")
        return row


@admin_router.put("/tipos-ausencia/{tipo_id}/flujo", dependencies=[Depends(require_admin)])
def asignar_flujo(tipo_id: int, pasos: list[TipoAusenciaFlujo], conn=Depends(get_conn)):
    if not pasos:
        raise HTTPException(422, "Debe enviar al menos un paso")
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM vacaciones.tipo_ausencia WHERE id=%s", (tipo_id,))
            if not cur.fetchone():
                raise HTTPException(404, "Tipo de ausencia no encontrado")
            cur.execute(
                "INSERT INTO vacaciones.flujo_aprobacion (tipo_ausencia_id, version, activo) VALUES (%s, 1, TRUE) RETURNING id",
                (tipo_id,),
            )
            flujo_id = cur.fetchone()["id"]
            for idx, paso in enumerate(pasos, start=1):
                cur.execute(
                    "SELECT id FROM vacaciones.rol_aprobador WHERE codigo=%s AND activo=TRUE",
                    (paso.rol_aprobador_codigo,),
                )
                rol = cur.fetchone()
                if not rol:
                    raise HTTPException(422, "Rol aprobador inválido")
                cur.execute(
                    """
                    INSERT INTO vacaciones.flujo_aprobacion_paso
                    (flujo_aprobacion_id, secuencia, rol_aprobador_id, es_obligatorio, activo)
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (flujo_id, idx, rol["id"], paso.es_obligatorio, paso.activo),
                )
    return {"flujo_aprobacion_id": flujo_id}


app.include_router(api_router)
app.include_router(admin_router)