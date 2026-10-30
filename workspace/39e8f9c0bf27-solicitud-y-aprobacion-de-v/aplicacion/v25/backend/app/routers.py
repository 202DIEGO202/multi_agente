import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from .db import audit, get_db, transaction
from .models import AbsenceType, Application, Flow, Page, ReadResult, Record, ReviewAction
from .security import require_admin, require_employee, require_hr

portal = APIRouter(prefix='/api', tags=['Portal'])
admin = APIRouter(prefix='/api/admin', tags=['Administración'])


def page(rows, limit, offset):
    return {'items': rows, 'limite': limit, 'desplazamiento': offset}


def get_application(connection, actor, request, application_id, administrative=False, operation='CONSULTAR_DETALLE', lock=False):
    if lock:
        row = connection.execute('SELECT * FROM solicitudes WHERE id=%s FOR UPDATE', (application_id,)).fetchone()
    else:
        row = connection.execute('SELECT * FROM solicitudes WHERE id=%s', (application_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Solicitud no encontrada')
    if administrative:
        authorized = connection.execute('SELECT 1 FROM revisiones WHERE solicitud_id=%s AND aprobador_id=%s', (application_id, actor['id'])).fetchone() is not None
    else:
        authorized = row['solicitante_id'] == actor['id']
    if not authorized:
        audit(connection, actor, request, operation, application_id, False)
        raise HTTPException(403, 'No tiene autorización sobre esta solicitud')
    return row


def type_record(connection, type_id):
    row = connection.execute('SELECT t.*, f.codigo AS flujo_codigo FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id=t.flujo_id WHERE t.id=%s', (type_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Tipo de ausencia no encontrado')
    return row


def flow_id(connection, code):
    row = connection.execute('SELECT id FROM flujo_aprobacion WHERE codigo=%s', (code,)).fetchone()
    if not row:
        raise HTTPException(422, 'Flujo no configurado')
    return row['id']


# Catálogo interno del empleado; no existe un listado público.
@portal.get('/empleado/tipos-ausencia', response_model=Page)
def employee_catalog(request: Request, limite: int = Query(50, ge=1, le=100), desplazamiento: int = Query(0, ge=0), actor=Depends(require_employee), connection=Depends(get_db)):
    with transaction(connection, actor):
        rows = connection.execute('SELECT id,nombre,requiere_motivo,modalidad_horas FROM tipos_ausencia WHERE estado=%s ORDER BY nombre,id LIMIT %s OFFSET %s', ('ACTIVO', limite, desplazamiento)).fetchall()
        audit(connection, actor, request, 'CONSULTAR_CATALOGO')
    return page(rows, limite, desplazamiento)


@portal.post('/solicitudes', status_code=201, response_model=Record)
def create_application(body: Application, request: Request, actor=Depends(require_employee), connection=Depends(get_db)):
    with transaction(connection, actor):
        employee = connection.execute('SELECT id,jefe_inmediato_id FROM usuarios WHERE id=%s AND activo FOR UPDATE', (actor['id'],)).fetchone()
        if not employee:
            raise HTTPException(403, 'Empleado inactivo')
        absence_type = connection.execute('SELECT * FROM tipos_ausencia WHERE id=%s FOR SHARE', (body.tipo_ausencia_id,)).fetchone()
        if not absence_type or absence_type['estado'] != 'ACTIVO':
            raise HTTPException(422, 'Seleccione un tipo de ausencia activo')
        if absence_type['requiere_motivo'] and not body.motivo:
            raise HTTPException(422, 'El tipo de ausencia requiere motivo')
        if absence_type['modalidad_horas'] == 'NO_APLICA' and body.hora_inicio is not None:
            raise HTTPException(422, 'Este tipo no permite horas')
        if absence_type['modalidad_horas'] == 'OBLIGATORIA' and body.hora_inicio is None:
            raise HTTPException(422, 'Este tipo requiere horas')
        duplicate = connection.execute('SELECT id FROM solicitudes WHERE solicitante_id=%s AND tipo_ausencia_id=%s AND fecha_inicio=%s AND fecha_fin=%s AND hora_inicio IS NOT DISTINCT FROM %s::time AND hora_fin IS NOT DISTINCT FROM %s::time AND estado_codigo<>%s', (actor['id'], body.tipo_ausencia_id, body.fecha_inicio, body.fecha_fin, body.hora_inicio, body.hora_fin, 'RECHAZADA')).fetchone()
        if duplicate:
            raise HTTPException(409, 'Ya existe una solicitud para el mismo tipo e intervalo')
        stages = connection.execute('SELECT * FROM etapas_flujo WHERE flujo_id=%s ORDER BY orden', (absence_type['flujo_id'],)).fetchall()
        if not stages or [s['orden'] for s in stages] != list(range(1, len(stages) + 1)):
            raise HTTPException(422, 'El flujo está incompleto')
        assignments = []
        for stage in stages:
            if stage['rol_codigo'] == 'JEFE_INMEDIATO':
                approver_id = employee['jefe_inmediato_id']
            else:
                try:
                    approver_id = int(os.environ['TALENTO_HUMANO_ID'])
                except (KeyError, ValueError) as exc:
                    raise HTTPException(503, 'Aprobador de Talento Humano no configurado') from exc
            approver = connection.execute('SELECT u.id FROM usuarios u JOIN usuario_roles r ON r.usuario_id=u.id WHERE u.id=%s AND u.activo AND r.rol_codigo=%s FOR SHARE OF u', (approver_id, stage['rol_codigo'])).fetchone()
            if not approver or approver_id == actor['id']:
                raise HTTPException(422, 'El flujo requiere un aprobador activo distinto del solicitante')
            assignments.append((stage, approver_id))
        row = connection.execute('INSERT INTO solicitudes (solicitante_id,tipo_ausencia_id,flujo_id,origen,referencia_formato,fecha_inicio,fecha_fin,hora_inicio,hora_fin,motivo,requiere_motivo,modalidad_horas) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *', (actor['id'], body.tipo_ausencia_id, absence_type['flujo_id'], body.origen, body.referencia_formato, body.fecha_inicio, body.fecha_fin, body.hora_inicio, body.hora_fin, body.motivo, absence_type['requiere_motivo'], absence_type['modalidad_horas'])).fetchone()
        for stage, approver_id in assignments:
            connection.execute('INSERT INTO revisiones (solicitud_id,flujo_id,orden,rol_codigo,aprobador_id) VALUES (%s,%s,%s,%s,%s)', (row['id'], row['flujo_id'], stage['orden'], stage['rol_codigo'], approver_id))
        connection.execute('SELECT iniciar_revision(%s,%s)', (row['id'], row['version']))
        result = connection.execute('SELECT * FROM solicitudes WHERE id=%s', (row['id'],)).fetchone()
    return result


@portal.get('/empleado/solicitudes', response_model=Page)
def employee_applications(request: Request, estado: Literal['ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA'] | None = None, limite: int = Query(50, ge=1, le=100), desplazamiento: int = Query(0, ge=0), actor=Depends(require_employee), connection=Depends(get_db)):
    with transaction(connection, actor):
        rows = connection.execute('SELECT id,tipo_ausencia_id,estado_codigo,fecha_inicio,fecha_fin,hora_inicio,hora_fin,motivo,version,creado_en,actualizado_en FROM solicitudes WHERE solicitante_id=%s AND (%s::text IS NULL OR estado_codigo=%s) ORDER BY creado_en DESC,id DESC LIMIT %s OFFSET %s', (actor['id'], estado, estado, limite, desplazamiento)).fetchall()
        audit(connection, actor, request, 'ACCESO', detail={'operacion': 'LISTAR_SOLICITUDES', 'estado': estado})
    return page(rows, limite, desplazamiento)


@portal.get('/empleado/solicitudes/{solicitud_id}', response_model=Record)
def employee_detail(request: Request, solicitud_id: int = Path(gt=0), actor=Depends(require_employee), connection=Depends(get_db)):
    row = get_application(connection, actor, request, solicitud_id)
    with transaction(connection, actor):
        audit(connection, actor, request, 'CONSULTAR_DETALLE', solicitud_id)
    fields = ('id', 'tipo_ausencia_id', 'estado_codigo', 'origen', 'referencia_formato', 'fecha_inicio', 'fecha_fin', 'hora_inicio', 'hora_fin', 'motivo', 'version', 'creado_en', 'actualizado_en')
    return {field: row[field] for field in fields}


@portal.get('/empleado/solicitudes/{solicitud_id}/historial', response_model=Page)
def employee_history(request: Request, solicitud_id: int = Path(gt=0), limite: int = Query(50, ge=1, le=100), desplazamiento: int = Query(0, ge=0), actor=Depends(require_employee), connection=Depends(get_db)):
    get_application(connection, actor, request, solicitud_id, operation='CONSULTAR_HISTORIAL')
    with transaction(connection, actor):
        rows = connection.execute('SELECT id,operacion,estado_anterior,estado_nuevo,version,ocurrido_en FROM historial_solicitud WHERE solicitud_id=%s ORDER BY ocurrido_en,id LIMIT %s OFFSET %s', (solicitud_id, limite, desplazamiento)).fetchall()
        audit(connection, actor, request, 'CONSULTAR_HISTORIAL', solicitud_id)
    return page(rows, limite, desplazamiento)


@portal.get('/notificaciones', response_model=Page)
def employee_notifications(request: Request, limite: int = Query(50, ge=1, le=100), desplazamiento: int = Query(0, ge=0), actor=Depends(require_employee), connection=Depends(get_db)):
    with transaction(connection, actor):
        rows = connection.execute('SELECT id,solicitud_id,tipo,asunto,contenido,creado_en,leida_en FROM notificaciones WHERE destinatario_id=%s ORDER BY creado_en DESC,id DESC LIMIT %s OFFSET %s', (actor['id'], limite, desplazamiento)).fetchall()
        audit(connection, actor, request, 'ACCESO', detail={'operacion': 'CONSULTAR_NOTIFICACIONES'})
    return page(rows, limite, desplazamiento)


@portal.patch('/notificaciones/{notificacion_id}/leida', response_model=ReadResult)
def read_notification(request: Request, notificacion_id: int = Path(gt=0), actor=Depends(require_employee), connection=Depends(get_db)):
    with transaction(connection, actor):
        row = connection.execute('UPDATE notificaciones SET leida_en=coalesce(leida_en,now()) WHERE id=%s AND destinatario_id=%s RETURNING id,leida_en', (notificacion_id, actor['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Notificación no encontrada')
        audit(connection, actor, request, 'ACCESO', detail={'operacion': 'MARCAR_NOTIFICACION_LEIDA', 'notificacion_id': notificacion_id})
    return row


@admin.get('/', response_model=Page)
@admin.get('/solicitudes', response_model=Page)
def admin_applications(request: Request, pendientes: bool = True, estado: Literal['ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA'] | None = None, limite: int = Query(50, ge=1, le=100), desplazamiento: int = Query(0, ge=0), actor=Depends(require_admin), connection=Depends(get_db)):
    with transaction(connection, actor):
        rows = connection.execute('SELECT s.* FROM solicitudes s WHERE EXISTS (SELECT 1 FROM revisiones r WHERE r.solicitud_id=s.id AND r.aprobador_id=%s AND (NOT %s OR r.estado=%s)) AND (%s::text IS NULL OR s.estado_codigo=%s) ORDER BY s.creado_en,s.id LIMIT %s OFFSET %s', (actor['id'], pendientes, 'PENDIENTE', estado, estado, limite, desplazamiento)).fetchall()
        audit(connection, actor, request, 'CONSULTAR_BANDEJA', detail={'pendientes': pendientes, 'estado': estado})
    return page(rows, limite, desplazamiento)


@admin.get('/solicitudes/{solicitud_id}', response_model=Record)
def admin_detail(request: Request, solicitud_id: int = Path(gt=0), actor=Depends(require_admin), connection=Depends(get_db)):
    get_application(connection, actor, request, solicitud_id, True)
    with transaction(connection, actor):
        row = connection.execute('SELECT * FROM solicitudes WHERE id=%s', (solicitud_id,)).fetchone()
        row['revisiones'] = connection.execute('SELECT * FROM revisiones WHERE solicitud_id=%s ORDER BY orden', (solicitud_id,)).fetchall()
        row['observaciones'] = connection.execute('SELECT * FROM observaciones WHERE solicitud_id=%s ORDER BY creado_en,id', (solicitud_id,)).fetchall()
        row['aprobaciones'] = connection.execute('SELECT a.* FROM aprobaciones a JOIN revisiones r ON r.id=a.revision_id WHERE r.solicitud_id=%s ORDER BY a.decidido_en,a.id', (solicitud_id,)).fetchall()
        row['solicitante'] = connection.execute('SELECT id,nombre,area,cargo FROM usuarios WHERE id=%s', (row['solicitante_id'],)).fetchone()
        audit(connection, actor, request, 'CONSULTAR_DETALLE', solicitud_id)
    return row


@admin.get('/solicitudes/{solicitud_id}/historial', response_model=Page)
def admin_history(request: Request, solicitud_id: int = Path(gt=0), limite: int = Query(50, ge=1, le=100), desplazamiento: int = Query(0, ge=0), actor=Depends(require_admin), connection=Depends(get_db)):
    get_application(connection, actor, request, solicitud_id, True, 'CONSULTAR_HISTORIAL')
    with transaction(connection, actor):
        rows = connection.execute('SELECT * FROM historial_solicitud WHERE solicitud_id=%s ORDER BY ocurrido_en,id LIMIT %s OFFSET %s', (solicitud_id, limite, desplazamiento)).fetchall()
        audit(connection, actor, request, 'CONSULTAR_HISTORIAL', solicitud_id)
    return page(rows, limite, desplazamiento)


@admin.post('/solicitudes/{solicitud_id}/decisiones', response_model=Record)
def decide(body: ReviewAction, request: Request, solicitud_id: int = Path(gt=0), actor=Depends(require_admin), connection=Depends(get_db)):
    get_application(connection, actor, request, solicitud_id, True)
    revision_access = connection.execute('SELECT aprobador_id FROM revisiones WHERE id=%s AND solicitud_id=%s', (body.revision_id, solicitud_id)).fetchone()
    if not revision_access:
        raise HTTPException(404, 'Revisión no encontrada')
    if revision_access['aprobador_id'] != actor['id']:
        audit(connection, actor, request, 'ACCESO', solicitud_id, False, {'operacion': 'DECIDIR', 'revision_id': body.revision_id})
        raise HTTPException(403, 'La revisión está asignada a otro aprobador')
    with transaction(connection, actor):
        row = get_application(connection, actor, request, solicitud_id, True, lock=True)
        revision = connection.execute('SELECT * FROM revisiones WHERE id=%s AND solicitud_id=%s FOR UPDATE', (body.revision_id, solicitud_id)).fetchone()
        if row['version'] != body.version_esperada:
            raise HTTPException(409, 'La versión cambió; vuelva a consultar la solicitud')
        if row['estado_codigo'] != 'EN_REVISION' or revision['estado'] != 'PENDIENTE':
            raise HTTPException(409, 'La revisión no admite esta acción')
        if revision['rol_codigo'] not in actor['roles']:
            raise HTTPException(403, 'El actor ya no posee el rol de la revisión')
        if row['solicitante_id'] == actor['id']:
            raise HTTPException(403, 'No puede decidir sobre su propia solicitud')
        if body.accion in {'VALIDAR', 'VALIDAR_APROBAR'} and revision['rol_codigo'] != 'TALENTO_HUMANO':
            raise HTTPException(422, 'La validación corresponde a Talento Humano')
        if body.accion == 'VALIDAR' and revision['validada_en'] is not None:
            raise HTTPException(409, 'La revisión ya fue validada')
        if body.accion == 'APROBAR' and revision['requiere_validacion'] and revision['validada_en'] is None:
            raise HTTPException(422, 'Debe validar previamente o usar VALIDAR_APROBAR')
        approval_id = None
        if body.accion == 'VALIDAR':
            connection.execute('SELECT validar_revision(%s,%s)', (body.revision_id, body.version_esperada))
        else:
            approval_id = connection.execute('INSERT INTO aprobaciones (revision_id,actor_id,decision,version_esperada) VALUES (%s,%s,%s,%s) RETURNING id', (body.revision_id, actor['id'], body.accion, body.version_esperada)).fetchone()['id']
        if body.observacion:
            connection.execute('INSERT INTO observaciones (solicitud_id,revision_id,aprobacion_id,autor_id,texto) VALUES (%s,%s,%s,%s,%s)', (solicitud_id, body.revision_id, approval_id, actor['id'], body.observacion))
        audit(connection, actor, request, 'ACCESO', solicitud_id, detail={'operacion': body.accion, 'revision_id': body.revision_id, 'version_esperada': body.version_esperada})
        result = connection.execute('SELECT * FROM solicitudes WHERE id=%s', (solicitud_id,)).fetchone()
        result['revision'] = connection.execute('SELECT * FROM revisiones WHERE id=%s', (body.revision_id,)).fetchone()
        result['aprobacion_id'] = approval_id
    return result


@admin.get('/tipos-ausencia', response_model=Page)
def admin_catalog(request: Request, limite: int = Query(50, ge=1, le=100), desplazamiento: int = Query(0, ge=0), actor=Depends(require_admin), connection=Depends(get_db)):
    require_hr(actor, connection, request)
    with transaction(connection, actor):
        rows = connection.execute('SELECT t.*,f.codigo AS flujo_codigo FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id=t.flujo_id ORDER BY t.nombre,t.id LIMIT %s OFFSET %s', (limite, desplazamiento)).fetchall()
        audit(connection, actor, request, 'CONSULTAR_CATALOGO')
    return page(rows, limite, desplazamiento)


@admin.get('/tipos-ausencia/{tipo_id}', response_model=Record)
def admin_type_detail(request: Request, tipo_id: int = Path(gt=0), actor=Depends(require_admin), connection=Depends(get_db)):
    require_hr(actor, connection, request)
    with transaction(connection, actor):
        row = type_record(connection, tipo_id)
        audit(connection, actor, request, 'CONSULTAR_CATALOGO', detail={'tipo_id': tipo_id})
    return row


@admin.post('/tipos-ausencia', status_code=201, response_model=Record)
def create_type(body: AbsenceType, request: Request, actor=Depends(require_admin), connection=Depends(get_db)):
    require_hr(actor, connection, request)
    with transaction(connection, actor):
        identifier = connection.execute('INSERT INTO tipos_ausencia (nombre,estado,flujo_id,requiere_motivo,modalidad_horas) VALUES (%s,%s,%s,%s,%s) RETURNING id', (body.nombre, body.estado, flow_id(connection, body.flujo_codigo), body.requiere_motivo, body.modalidad_horas)).fetchone()['id']
        result = type_record(connection, identifier)
    return result


@admin.put('/tipos-ausencia/{tipo_id}', response_model=Record)
def update_type(body: AbsenceType, request: Request, tipo_id: int = Path(gt=0), actor=Depends(require_admin), connection=Depends(get_db)):
    require_hr(actor, connection, request)
    with transaction(connection, actor):
        row = connection.execute('UPDATE tipos_ausencia SET nombre=%s,estado=%s,flujo_id=%s,requiere_motivo=%s,modalidad_horas=%s,actualizado_en=now() WHERE id=%s RETURNING id', (body.nombre, body.estado, flow_id(connection, body.flujo_codigo), body.requiere_motivo, body.modalidad_horas, tipo_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Tipo de ausencia no encontrado')
        result = type_record(connection, tipo_id)
    return result


@admin.put('/tipos-ausencia/{tipo_id}/flujo', response_model=Record)
def update_flow(body: Flow, request: Request, tipo_id: int = Path(gt=0), actor=Depends(require_admin), connection=Depends(get_db)):
    require_hr(actor, connection, request)
    with transaction(connection, actor):
        row = connection.execute('UPDATE tipos_ausencia SET flujo_id=%s,actualizado_en=now() WHERE id=%s RETURNING id', (flow_id(connection, body.flujo_codigo), tipo_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Tipo de ausencia no encontrado')
        result = type_record(connection, tipo_id)
    return result


@admin.delete('/tipos-ausencia/{tipo_id}', response_model=Record)
def delete_type(request: Request, tipo_id: int = Path(gt=0), actor=Depends(require_admin), connection=Depends(get_db)):
    require_hr(actor, connection, request)
    with transaction(connection, actor):
        row = connection.execute('SELECT id FROM tipos_ausencia WHERE id=%s FOR UPDATE', (tipo_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Tipo de ausencia no encontrado')
        if connection.execute('SELECT 1 FROM solicitudes WHERE tipo_ausencia_id=%s LIMIT 1', (tipo_id,)).fetchone():
            raise HTTPException(409, 'El tipo tiene solicitudes asociadas; puede desactivarlo')
        connection.execute('DELETE FROM tipos_ausencia WHERE id=%s', (tipo_id,))
    return {'id': tipo_id, 'eliminado': True}