import os
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import PositiveInt

from .models import Decision, FlujoUpdate, Health, ObservacionCreate, SolicitudCreate, Tipo, TipoUpdate
from .notificaciones import process_notifications
from .security import audit_access, authorized_request, get_actor, get_db, require_admin, require_role, set_actor

publico = APIRouter(prefix='/api')
administrador = APIRouter(prefix='/api/admin', dependencies=[Depends(require_admin)])


@publico.get('/health', response_model=Health)
def health():
    return {'estado': 'ok'}


@administrador.get('/identidad', dependencies=[Depends(require_admin)])
def identidad(actor=Depends(get_actor)):
    return actor


def find_flow(db, code):
    row = db.execute('SELECT id, codigo, nombre FROM flujo_aprobacion WHERE codigo = %s AND activo', (code,)).fetchone()
    if not row:
        raise HTTPException(422, 'Flujo inexistente o inactivo')
    return row


def lock_type(db, tipo_id):
    row = db.execute('SELECT * FROM tipos_ausencia WHERE id = %s FOR UPDATE', (tipo_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Tipo de ausencia inexistente')
    return row


@administrador.get('/flujos', dependencies=[Depends(require_admin)])
def flujos(request: Request, actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'TALENTO_HUMANO', 'CONSULTA_CATALOGO')
    return db.execute('SELECT f.id, f.codigo, f.nombre, f.activo, p.orden, p.rol_codigo, p.requiere_validacion FROM flujo_aprobacion f JOIN pasos_flujo p ON p.flujo_id = f.id ORDER BY f.id, p.orden').fetchall()


@administrador.get('/tipos-ausencia', dependencies=[Depends(require_admin)])
def tipos(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_actor), db=Depends(get_db)):
    allowed = bool(set(actor['roles']) & {'EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO'})
    audit_access(db, actor, request, 'CONSULTA_CATALOGO', allowed)
    if not allowed:
        raise HTTPException(403, 'Rol no autorizado')
    all_types = 'TALENTO_HUMANO' in actor['roles']
    return db.execute("SELECT t.*, f.codigo AS flujo FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id = t.flujo_id WHERE (%s OR (t.estado = 'ACTIVO' AND f.activo)) ORDER BY lower(t.nombre), t.id LIMIT %s OFFSET %s", (all_types, limit, offset)).fetchall()


@administrador.get('/tipos-ausencia/{tipo_id}', dependencies=[Depends(require_admin)])
def tipo_detail(tipo_id: PositiveInt, request: Request, actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'TALENTO_HUMANO', 'CONSULTA_CATALOGO')
    row = db.execute('SELECT t.*, f.codigo AS flujo FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id = t.flujo_id WHERE t.id = %s', (tipo_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Tipo de ausencia inexistente')
    return row


@administrador.post('/tipos-ausencia', status_code=201, dependencies=[Depends(require_admin)])
def crear_tipo(body: Tipo, request: Request, actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'TALENTO_HUMANO')
    with db.transaction():
        set_actor(db, actor)
        flow = find_flow(db, body.flujo)
        return db.execute('INSERT INTO tipos_ausencia(nombre, estado, flujo_id, requiere_motivo, modalidad_horas) VALUES (%s, %s, %s, %s, %s) RETURNING *', (body.nombre, body.estado, flow['id'], body.requiere_motivo, body.modalidad_horas)).fetchone()


@administrador.put('/tipos-ausencia/{tipo_id}', dependencies=[Depends(require_admin)])
def actualizar_tipo(tipo_id: PositiveInt, body: TipoUpdate, request: Request, actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'TALENTO_HUMANO')
    with db.transaction():
        set_actor(db, actor)
        old = lock_type(db, tipo_id)
        if old['version'] != body.version:
            raise HTTPException(409, 'El catálogo cambió; vuelva a consultarlo')
        flow = find_flow(db, body.flujo)
        row = db.execute('UPDATE tipos_ausencia SET nombre = %s, estado = %s, flujo_id = %s, requiere_motivo = %s, modalidad_horas = %s, version = version + 1, actualizado_en = clock_timestamp() WHERE id = %s AND version = %s RETURNING *', (body.nombre, body.estado, flow['id'], body.requiere_motivo, body.modalidad_horas, tipo_id, body.version)).fetchone()
        if not row:
            raise HTTPException(409, 'Conflicto de versión')
        return row


@administrador.put('/tipos-ausencia/{tipo_id}/flujo', dependencies=[Depends(require_admin)])
def actualizar_flujo(tipo_id: PositiveInt, body: FlujoUpdate, request: Request, actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'TALENTO_HUMANO')
    with db.transaction():
        set_actor(db, actor)
        old = lock_type(db, tipo_id)
        if old['version'] != body.version:
            raise HTTPException(409, 'Conflicto de versión')
        flow = find_flow(db, body.flujo)
        return db.execute('UPDATE tipos_ausencia SET flujo_id = %s, version = version + 1, actualizado_en = clock_timestamp() WHERE id = %s AND version = %s RETURNING *', (flow['id'], tipo_id, body.version)).fetchone()


@administrador.delete('/tipos-ausencia/{tipo_id}', dependencies=[Depends(require_admin)])
def eliminar_tipo(tipo_id: PositiveInt, request: Request, version: Annotated[int, Query(gt=0)], actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'TALENTO_HUMANO')
    with db.transaction():
        set_actor(db, actor)
        old = lock_type(db, tipo_id)
        if old['version'] != version:
            raise HTTPException(409, 'Conflicto de versión')
        if db.execute('SELECT 1 FROM solicitudes WHERE tipo_ausencia_id = %s LIMIT 1', (tipo_id,)).fetchone():
            raise HTTPException(409, 'El tipo está utilizado; desactívelo en lugar de eliminarlo')
        db.execute('DELETE FROM tipos_ausencia WHERE id = %s AND version = %s', (tipo_id, version))
        return {'eliminado': True, 'id': tipo_id}


def assigned_approvers(db, actor, flow_id):
    steps = db.execute('SELECT orden, rol_codigo, requiere_validacion FROM pasos_flujo WHERE flujo_id = %s ORDER BY orden', (flow_id,)).fetchall()
    if not steps or [s['orden'] for s in steps] != list(range(1, len(steps) + 1)):
        raise HTTPException(422, 'El flujo no tiene pasos consecutivos válidos')
    result = []
    for step in steps:
        if step['rol_codigo'] == 'JEFE_INMEDIATO':
            approver = db.execute('SELECT j.id FROM usuarios e JOIN usuarios j ON j.id = e.jefe_inmediato_id JOIN usuarios_roles r ON r.usuario_id = j.id AND r.rol_codigo = %s WHERE e.id = %s AND j.activo FOR SHARE OF j, r', (step['rol_codigo'], actor['id'])).fetchone()
        else:
            external_id = os.environ.get('TH_APPROVER_EXTERNAL_ID')
            if not external_id:
                raise HTTPException(503, 'El aprobador de Talento Humano no está configurado')
            approver = db.execute('SELECT u.id FROM usuarios u JOIN usuarios_roles r ON r.usuario_id = u.id AND r.rol_codigo = %s WHERE u.identidad_externa = %s AND u.activo FOR SHARE OF u, r', (step['rol_codigo'], external_id)).fetchone()
        if not approver or approver['id'] == actor['id']:
            raise HTTPException(422, 'El flujo requiere un aprobador activo distinto del solicitante')
        result.append({**step, 'aprobador_id': approver['id']})
    return result


@administrador.post('/mis-solicitudes', status_code=201, dependencies=[Depends(require_admin)])
def crear_solicitud(body: SolicitudCreate, request: Request, background_tasks: BackgroundTasks, actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'EMPLEADO')
    with db.transaction():
        set_actor(db, actor)
        db.execute('SELECT id FROM usuarios WHERE id = %s AND activo FOR SHARE', (actor['id'],)).fetchone()
        tipo = db.execute('SELECT t.*, f.activo AS flujo_activo FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id = t.flujo_id WHERE t.id = %s FOR SHARE OF t, f', (body.tipo_ausencia_id,)).fetchone()
        if not tipo or tipo['estado'] != 'ACTIVO' or not tipo['flujo_activo']:
            raise HTTPException(422, 'Tipo de ausencia inexistente o inactivo')
        if tipo['requiere_motivo'] and not body.motivo:
            raise HTTPException(422, 'Este tipo de ausencia requiere motivo u observación')
        if tipo['modalidad_horas'] == 'NO_APLICA' and body.hora_inicio is not None:
            raise HTTPException(422, 'Este tipo de ausencia no admite horas')
        if tipo['modalidad_horas'] == 'OBLIGATORIA' and body.hora_inicio is None:
            raise HTTPException(422, 'Este tipo de ausencia requiere horas')
        approvers = assigned_approvers(db, actor, tipo['flujo_id'])
        row = db.execute('INSERT INTO solicitudes(solicitante_id, tipo_ausencia_id, flujo_id, origen, referencia_formato, fecha_inicio, fecha_fin, hora_inicio, hora_fin, motivo, requiere_motivo, modalidad_horas) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *', (actor['id'], tipo['id'], tipo['flujo_id'], body.origen, body.referencia_formato, body.fecha_inicio, body.fecha_fin, body.hora_inicio, body.hora_fin, body.motivo, tipo['requiere_motivo'], tipo['modalidad_horas'])).fetchone()
        for step in approvers:
            db.execute('INSERT INTO aprobaciones(solicitud_id, orden, rol_codigo, aprobador_id, requiere_validacion) VALUES (%s, %s, %s, %s, %s)', (row['id'], step['orden'], step['rol_codigo'], step['aprobador_id'], step['requiere_validacion']))
        row = db.execute("UPDATE solicitudes SET estado_codigo = 'EN_REVISION', version = version + 1 WHERE id = %s AND version = %s RETURNING *", (row['id'], row['version'])).fetchone()
        db.execute("UPDATE aprobaciones SET estado = 'PENDIENTE', version = version + 1 WHERE solicitud_id = %s AND orden = 1 AND estado = 'BLOQUEADA'", (row['id'],))
    background_tasks.add_task(process_notifications, 20)
    return row


@administrador.get('/mis-solicitudes', dependencies=[Depends(require_admin)])
def mis_solicitudes(request: Request, estado: Literal['ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA'] | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'EMPLEADO', 'CONSULTA_ESTADO')
    return db.execute('SELECT * FROM solicitudes WHERE solicitante_id = %s AND eliminado_en IS NULL AND (%s::text IS NULL OR estado_codigo = %s) ORDER BY creado_en DESC, id DESC LIMIT %s OFFSET %s', (actor['id'], estado, estado, limit, offset)).fetchall()


@administrador.get('/revisiones/pendientes', dependencies=[Depends(require_admin)])
def pendientes(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_actor), db=Depends(get_db)):
    allowed = bool(set(actor['roles']) & {'JEFE_INMEDIATO', 'TALENTO_HUMANO'})
    audit_access(db, actor, request, 'CONSULTA_BANDEJA', allowed)
    if not allowed:
        raise HTTPException(403, 'Se requiere rol de aprobador')
    return db.execute("SELECT s.id AS solicitud_id, s.version AS version_solicitud, s.estado_codigo, s.fecha_inicio, s.fecha_fin, s.hora_inicio, s.hora_fin, s.motivo, t.nombre AS tipo_ausencia, u.nombre AS solicitante, u.area, a.id AS aprobacion_id, a.version AS version_revision, a.rol_codigo, a.requiere_validacion, a.validada_en FROM aprobaciones a JOIN solicitudes s ON s.id = a.solicitud_id JOIN usuarios u ON u.id = s.solicitante_id JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id JOIN usuarios_roles r ON r.usuario_id = a.aprobador_id AND r.rol_codigo = a.rol_codigo WHERE a.aprobador_id = %s AND a.estado = 'PENDIENTE' AND s.estado_codigo = 'EN_REVISION' AND s.eliminado_en IS NULL ORDER BY a.creado_en, a.id LIMIT %s OFFSET %s", (actor['id'], limit, offset)).fetchall()


@administrador.get('/solicitudes/{solicitud_id}', dependencies=[Depends(require_admin)])
def solicitud_detail(solicitud_id: PositiveInt, request: Request, actor=Depends(get_actor), db=Depends(get_db)):
    row = authorized_request(db, actor, request, solicitud_id, 'CONSULTA_DETALLE')
    row['aprobaciones'] = db.execute('SELECT id, orden, rol_codigo, aprobador_id, requiere_validacion, estado, validada_por, validada_en, decision_por, decidida_en, version FROM aprobaciones WHERE solicitud_id = %s ORDER BY orden', (solicitud_id,)).fetchall()
    row['observaciones'] = db.execute('SELECT id, aprobacion_id, autor_id, accion, contenido, creado_en FROM observaciones WHERE solicitud_id = %s ORDER BY creado_en, id', (solicitud_id,)).fetchall()
    return row


@administrador.get('/solicitudes/{solicitud_id}/historial', dependencies=[Depends(require_admin)])
def historial(solicitud_id: PositiveInt, request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_actor), db=Depends(get_db)):
    authorized_request(db, actor, request, solicitud_id, 'CONSULTA_HISTORIAL')
    return db.execute('SELECT id, actor_id, operacion, estado_anterior, estado_nuevo, version, creado_en FROM historial_solicitud WHERE solicitud_id = %s ORDER BY version LIMIT %s OFFSET %s', (solicitud_id, limit, offset)).fetchall()


def check_revision(db, actor, request, revision_id):
    row = db.execute('SELECT * FROM aprobaciones WHERE id = %s', (revision_id,)).fetchone()
    allowed = bool(row and row['aprobador_id'] == actor['id'] and row['rol_codigo'] in actor['roles'])
    audit_access(db, actor, request, 'ACCION_SENSIBLE', allowed, row['solicitud_id'] if row else None)
    if not allowed:
        raise HTTPException(404, 'Revisión no disponible')
    return row


@administrador.post('/revisiones/{revision_id}/decision', dependencies=[Depends(require_admin)])
def decidir(revision_id: PositiveInt, body: Decision, request: Request, background_tasks: BackgroundTasks, actor=Depends(get_actor), db=Depends(get_db)):
    revision = check_revision(db, actor, request, revision_id)
    with db.transaction():
        set_actor(db, actor)
        solicitud = db.execute('SELECT * FROM solicitudes WHERE id = %s FOR UPDATE', (revision['solicitud_id'],)).fetchone()
        revision = db.execute('SELECT * FROM aprobaciones WHERE id = %s FOR UPDATE', (revision_id,)).fetchone()
        if solicitud['version'] != body.version_solicitud or revision['version'] != body.version_revision:
            raise HTTPException(409, 'Conflicto de versión; vuelva a consultar la solicitud')
        if solicitud['estado_codigo'] != 'EN_REVISION' or solicitud['eliminado_en'] is not None or revision['estado'] != 'PENDIENTE':
            raise HTTPException(409, 'La revisión ya no está pendiente')
        if body.accion in ('VALIDAR', 'VALIDAR_APROBAR') and revision['rol_codigo'] != 'TALENTO_HUMANO':
            raise HTTPException(422, 'La validación corresponde a Talento Humano')
        if body.accion == 'APROBAR' and revision['requiere_validacion'] and revision['validada_en'] is None:
            raise HTTPException(422, 'Primero debe validar o utilizar VALIDAR_APROBAR')
        if body.accion == 'VALIDAR' and revision['validada_en'] is not None:
            raise HTTPException(409, 'La revisión ya está validada')
        if body.accion == 'VALIDAR_APROBAR' and revision['validada_por'] is not None and revision['validada_por'] != actor['id']:
            raise HTTPException(409, 'La validación pertenece a otro actor')
        db.execute('SELECT registrar_decision(%s, %s, %s, %s, %s)', (revision_id, body.version_solicitud, body.version_revision, body.accion, body.observacion)).fetchone()
        result = db.execute('SELECT id, estado_codigo, version, actualizado_en FROM solicitudes WHERE id = %s', (solicitud['id'],)).fetchone()
        result['revision'] = db.execute('SELECT id, estado, version, validada_por, validada_en, decision_por, decidida_en FROM aprobaciones WHERE id = %s', (revision_id,)).fetchone()
    background_tasks.add_task(process_notifications, 20)
    return result


@administrador.post('/revisiones/{revision_id}/observaciones', status_code=201, dependencies=[Depends(require_admin)])
def observar(revision_id: PositiveInt, body: ObservacionCreate, request: Request, actor=Depends(get_actor), db=Depends(get_db)):
    revision = check_revision(db, actor, request, revision_id)
    with db.transaction():
        set_actor(db, actor)
        solicitud = db.execute('SELECT * FROM solicitudes WHERE id = %s FOR UPDATE', (revision['solicitud_id'],)).fetchone()
        revision = db.execute('SELECT * FROM aprobaciones WHERE id = %s FOR UPDATE', (revision_id,)).fetchone()
        if solicitud['version'] != body.version_solicitud or revision['version'] != body.version_revision:
            raise HTTPException(409, 'Conflicto de versión')
        if solicitud['estado_codigo'] != 'EN_REVISION' or solicitud['eliminado_en'] is not None or revision['estado'] != 'PENDIENTE':
            raise HTTPException(409, 'La revisión no admite observaciones')
        observation = db.execute("INSERT INTO observaciones(solicitud_id, aprobacion_id, autor_id, accion, contenido) VALUES (%s, %s, %s, 'REVISION', %s) RETURNING *", (solicitud['id'], revision_id, actor['id'], body.contenido)).fetchone()
        db.execute('UPDATE aprobaciones SET version = version + 1 WHERE id = %s AND version = %s', (revision_id, body.version_revision))
        updated = db.execute('UPDATE solicitudes SET version = version + 1 WHERE id = %s AND version = %s RETURNING version', (solicitud['id'], body.version_solicitud)).fetchone()
        return {'observacion': observation, 'version_solicitud': updated['version'], 'version_revision': body.version_revision + 1}


@administrador.get('/mis-notificaciones', dependencies=[Depends(require_admin)])
def notificaciones(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0, actor=Depends(get_actor), db=Depends(get_db)):
    audit_access(db, actor, request, 'CONSULTA_ESTADO', True)
    return db.execute('SELECT n.id, n.solicitud_id, n.tipo, n.prioridad, n.estado_envio, n.creado_en, n.enviada_en, n.leida_en, h.estado_nuevo AS estado_notificado FROM notificaciones n LEFT JOIN historial_solicitud h ON h.id = n.historial_id WHERE n.destinatario_id = %s ORDER BY n.creado_en DESC, n.id DESC LIMIT %s OFFSET %s', (actor['id'], limit, offset)).fetchall()


@administrador.post('/notificaciones/procesar', dependencies=[Depends(require_admin)])
def procesar_notificaciones(request: Request, background_tasks: BackgroundTasks, actor=Depends(get_actor), db=Depends(get_db)):
    require_role(db, actor, request, 'TALENTO_HUMANO')
    background_tasks.add_task(process_notifications, 100)
    return {'estado': 'programado'}