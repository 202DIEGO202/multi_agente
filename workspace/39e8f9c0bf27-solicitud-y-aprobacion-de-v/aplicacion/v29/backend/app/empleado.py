from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import PositiveInt

from .models import SolicitudCreate
from .routers import crear_solicitud
from .security import audit_access, get_db, get_employee_actor

empleado = APIRouter(prefix='/api/empleado', tags=['Empleado'], dependencies=[Depends(get_employee_actor)])


@empleado.get('/identidad')
def identidad(actor=Depends(get_employee_actor)):
    return {'id': actor['id'], 'nombre': actor['nombre']}


@empleado.get('/tipos-ausencia')
def catalogo(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_employee_actor), db=Depends(get_db)):
    audit_access(db, actor, request, 'CONSULTA_CATALOGO', True)
    return db.execute("SELECT t.id, t.nombre, t.requiere_motivo, t.modalidad_horas FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id = t.flujo_id WHERE t.estado = 'ACTIVO' AND f.activo ORDER BY lower(t.nombre), t.id LIMIT %s OFFSET %s", (limit, offset)).fetchall()


@empleado.post('/solicitudes', status_code=201)
def registrar(body: SolicitudCreate, request: Request, background_tasks: BackgroundTasks, actor=Depends(get_employee_actor), db=Depends(get_db)):
    # Reutiliza las validaciones y la transacción existentes con el actor de esta sesión.
    return crear_solicitud(body=body, request=request, background_tasks=background_tasks, actor=actor, db=db)


@empleado.get('/solicitudes')
def solicitudes(request: Request, estado: Literal['ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA'] | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_employee_actor), db=Depends(get_db)):
    audit_access(db, actor, request, 'CONSULTA_ESTADO', True)
    return db.execute('SELECT s.*, t.nombre AS tipo_ausencia FROM solicitudes s JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id WHERE s.solicitante_id = %s AND s.eliminado_en IS NULL AND (%s::text IS NULL OR s.estado_codigo = %s) ORDER BY s.creado_en DESC, s.id DESC LIMIT %s OFFSET %s', (actor['id'], estado, estado, limit, offset)).fetchall()


def solicitud_propia(db, actor, request, solicitud_id, operation):
    row = db.execute('SELECT s.*, t.nombre AS tipo_ausencia FROM solicitudes s JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id WHERE s.id = %s AND s.solicitante_id = %s AND s.eliminado_en IS NULL', (solicitud_id, actor['id'])).fetchone()
    audit_access(db, actor, request, operation, row is not None, solicitud_id if row else None)
    if not row:
        raise HTTPException(404, 'Solicitud no disponible')
    return row


@empleado.get('/solicitudes/{solicitud_id}')
def detalle(solicitud_id: PositiveInt, request: Request, actor=Depends(get_employee_actor), db=Depends(get_db)):
    return solicitud_propia(db, actor, request, solicitud_id, 'CONSULTA_DETALLE')


@empleado.get('/solicitudes/{solicitud_id}/historial')
def historial(solicitud_id: PositiveInt, request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_employee_actor), db=Depends(get_db)):
    solicitud_propia(db, actor, request, solicitud_id, 'CONSULTA_HISTORIAL')
    return db.execute('SELECT h.id, h.operacion, h.estado_anterior, h.estado_nuevo, h.version, h.creado_en FROM historial_solicitud h JOIN solicitudes s ON s.id = h.solicitud_id WHERE h.solicitud_id = %s AND s.solicitante_id = %s AND s.eliminado_en IS NULL ORDER BY h.version LIMIT %s OFFSET %s', (solicitud_id, actor['id'], limit, offset)).fetchall()


@empleado.get('/notificaciones')
def notificaciones(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_employee_actor), db=Depends(get_db)):
    audit_access(db, actor, request, 'CONSULTA_ESTADO', True)
    return db.execute("SELECT n.id, n.solicitud_id, n.tipo, n.prioridad, n.estado_envio, n.creado_en, n.enviada_en, n.leida_en, h.estado_nuevo AS estado_notificado FROM notificaciones n JOIN solicitudes s ON s.id = n.solicitud_id LEFT JOIN historial_solicitud h ON h.id = n.historial_id WHERE n.destinatario_id = %s AND s.solicitante_id = %s AND s.eliminado_en IS NULL AND n.tipo = 'CAMBIO_ESTADO' ORDER BY n.creado_en DESC, n.id DESC LIMIT %s OFFSET %s", (actor['id'], actor['id'], limit, offset)).fetchall()