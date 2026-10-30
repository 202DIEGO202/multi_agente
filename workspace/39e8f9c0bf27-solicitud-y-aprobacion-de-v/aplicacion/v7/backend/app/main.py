import hmac
import os
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Path, Query

from .db import actor_transaction, audit_access, get_db
from .models import DecisionInput, FlujoUpdate, TipoCreate, TipoUpdate

app = FastAPI()
public_router = APIRouter(prefix='/api', tags=['Salud'])
admin_router = APIRouter(prefix='/api/admin', tags=['Administración'])
Db = Annotated[object, Depends(get_db)]
PositiveId = Annotated[int, Path(ge=1)]


def require_admin(authorization: Annotated[str | None, Header()] = None):
    expected = os.environ.get('ADMIN_API_TOKEN', '')
    if not expected or not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Autenticación administrativa requerida', headers={'WWW-Authenticate': 'Bearer'})
    token = authorization[7:]
    if not token or not hmac.compare_digest(token.encode('utf-8'), expected.encode('utf-8')):
        raise HTTPException(401, 'Credenciales administrativas inválidas', headers={'WWW-Authenticate': 'Bearer'})


def get_actor(db: Db, authenticated=Depends(require_admin)):
    # El actor está vinculado al token en configuración, nunca en datos del cliente.
    try:
        actor_id = int(os.environ['ADMIN_USER_ID'])
        if actor_id <= 0:
            raise ValueError
    except (KeyError, ValueError) as exc:
        raise HTTPException(503, 'Identidad administrativa no configurada') from exc
    actor = db.execute('SELECT id, nombre FROM usuarios WHERE id = %s AND activo', (actor_id,)).fetchone()
    if not actor:
        audit_access(db, None, 'AUTENTICACION', result='DENEGADO')
        raise HTTPException(403, 'Identidad administrativa inactiva o inexistente')
    roles = {row['rol_codigo'] for row in db.execute('SELECT rol_codigo FROM usuario_roles WHERE usuario_id = %s', (actor_id,)).fetchall()}
    if not roles.intersection({'administrador', 'jefe_inmediato', 'talento_humano'}):
        audit_access(db, actor_id, 'AUTENTICACION', result='DENEGADO')
        raise HTTPException(403, 'La identidad no tiene funciones administrativas')
    actor['roles'] = roles
    audit_access(db, actor_id, 'AUTENTICACION')
    return actor


Actor = Annotated[dict, Depends(get_actor)]


def require_catalog_permission(db, actor):
    if not actor['roles'].intersection({'administrador', 'talento_humano'}):
        audit_access(db, actor['id'], 'ACCION_SENSIBLE', result='DENEGADO')
        raise HTTPException(403, 'El catálogo requiere Talento Humano o administración')


def visible_solicitud(db, actor, solicitud_id):
    row = db.execute(
        '''SELECT s.*, u.nombre AS solicitante, u.area, u.cargo,
                  t.nombre AS tipo_ausencia, e.nombre AS estado
           FROM solicitudes s JOIN usuarios u ON u.id = s.solicitante_id
           JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id
           JOIN estados e ON e.codigo = s.estado_codigo
           WHERE s.id = %s AND s.eliminado_en IS NULL
             AND (%s OR EXISTS (SELECT 1 FROM revisiones r
                  WHERE r.solicitud_id = s.id AND r.aprobador_id = %s))''',
        (solicitud_id, 'administrador' in actor['roles'], actor['id']),
    ).fetchone()
    if not row:
        audit_access(db, actor['id'], 'CONSULTA_SOLICITUD', result='DENEGADO')
        raise HTTPException(404, 'Solicitud no disponible para esta identidad')
    return row


def find_flow(db, codigo):
    flow = db.execute('SELECT id FROM flujo_aprobacion WHERE codigo = %s AND activo FOR SHARE', (codigo,)).fetchone()
    if not flow:
        raise HTTPException(422, 'El flujo seleccionado no está activo')
    return flow['id']


def lock_tipo(db, tipo_id, version):
    row = db.execute('SELECT * FROM tipos_ausencia WHERE id = %s FOR UPDATE', (tipo_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Tipo de ausencia inexistente')
    if row['version'] != version:
        raise HTTPException(409, 'El tipo de ausencia fue modificado; recargue el catálogo')
    return row


def enqueue_state_notification(db, solicitud_id):
    db.execute(
        '''INSERT INTO notificaciones
           (solicitud_id, destinatario_id, historial_id, tipo, asunto, mensaje)
           SELECT s.id, s.solicitante_id, h.id, 'CAMBIO_ESTADO',
                  'Cambio de estado de solicitud', 'Nuevo estado: ' || e.nombre
           FROM solicitudes s JOIN historial_solicitud h
             ON h.solicitud_id = s.id AND h.version = s.version
           JOIN estados e ON e.codigo = s.estado_codigo
           WHERE s.id = %s AND h.evento = 'CAMBIO_ESTADO'
           ON CONFLICT DO NOTHING''',
        (solicitud_id,),
    )


def enqueue_pending_notification(db, revision):
    db.execute(
        '''INSERT INTO notificaciones
           (solicitud_id, destinatario_id, revision_id, tipo, asunto, mensaje)
           VALUES (%s, %s, %s, 'PENDIENTE_REVISION',
                   'Solicitud pendiente de revisión', 'Tiene una solicitud asignada para revisión')
           ON CONFLICT DO NOTHING''',
        (revision['solicitud_id'], revision['aprobador_id'], revision['id']),
    )


@public_router.get('/health')
def health():
    return {'estado': 'ok'}


# El catálogo es interno: no existe una copia anónima en /api/tipos-ausencia.
@admin_router.get('/tipos-ausencia', dependencies=[Depends(require_admin)])
def list_tipos(db: Db, actor: Actor, limite: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0):
    require_catalog_permission(db, actor)
    with actor_transaction(db, actor['id']):
        audit_access(db, actor['id'], 'CONSULTA_CATALOGO')
        return db.execute(
            '''SELECT t.*, f.codigo AS flujo_codigo, f.nombre AS flujo
               FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id = t.flujo_id
               ORDER BY lower(t.nombre), t.id LIMIT %s OFFSET %s''',
            (limite, offset),
        ).fetchall()


@admin_router.get('/tipos-ausencia/{tipo_id}', dependencies=[Depends(require_admin)])
def detail_tipo(tipo_id: PositiveId, db: Db, actor: Actor):
    require_catalog_permission(db, actor)
    with actor_transaction(db, actor['id']):
        row = db.execute(
            '''SELECT t.*, f.codigo AS flujo_codigo, f.nombre AS flujo
               FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id = t.flujo_id
               WHERE t.id = %s''', (tipo_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, 'Tipo de ausencia inexistente')
        audit_access(db, actor['id'], 'CONSULTA_CATALOGO')
        return row


@admin_router.post('/tipos-ausencia', status_code=201, dependencies=[Depends(require_admin)])
def create_tipo(body: TipoCreate, db: Db, actor: Actor):
    require_catalog_permission(db, actor)
    with actor_transaction(db, actor['id']):
        flow_id = find_flow(db, body.flujo_codigo)
        row = db.execute(
            '''INSERT INTO tipos_ausencia (nombre, estado, requiere_motivo, permite_horas, flujo_id)
               VALUES (%s, %s, %s, %s, %s) RETURNING *''',
            (body.nombre, body.estado, body.requiere_motivo, body.permite_horas, flow_id),
        ).fetchone()
        audit_access(db, actor['id'], 'ACCION_SENSIBLE')
        return row


@admin_router.put('/tipos-ausencia/{tipo_id}', dependencies=[Depends(require_admin)])
def update_tipo(tipo_id: PositiveId, body: TipoUpdate, db: Db, actor: Actor):
    require_catalog_permission(db, actor)
    with actor_transaction(db, actor['id']):
        lock_tipo(db, tipo_id, body.version_esperada)
        flow_id = find_flow(db, body.flujo_codigo)
        row = db.execute(
            '''UPDATE tipos_ausencia SET nombre = %s, estado = %s, requiere_motivo = %s,
               permite_horas = %s, flujo_id = %s, version = version + 1
               WHERE id = %s AND version = %s RETURNING *''',
            (body.nombre, body.estado, body.requiere_motivo, body.permite_horas, flow_id, tipo_id, body.version_esperada),
        ).fetchone()
        if not row:
            raise HTTPException(409, 'Conflicto de versión')
        audit_access(db, actor['id'], 'ACCION_SENSIBLE')
        return row


@admin_router.put('/tipos-ausencia/{tipo_id}/flujo', dependencies=[Depends(require_admin)])
def update_flujo(tipo_id: PositiveId, body: FlujoUpdate, db: Db, actor: Actor):
    require_catalog_permission(db, actor)
    with actor_transaction(db, actor['id']):
        lock_tipo(db, tipo_id, body.version_esperada)
        flow_id = find_flow(db, body.flujo_codigo)
        row = db.execute(
            '''UPDATE tipos_ausencia SET flujo_id = %s, version = version + 1
               WHERE id = %s AND version = %s RETURNING *''',
            (flow_id, tipo_id, body.version_esperada),
        ).fetchone()
        if not row:
            raise HTTPException(409, 'Conflicto de versión')
        audit_access(db, actor['id'], 'ACCION_SENSIBLE')
        return row


@admin_router.delete('/tipos-ausencia/{tipo_id}', dependencies=[Depends(require_admin)])
def delete_tipo(tipo_id: PositiveId, db: Db, actor: Actor, version_esperada: Annotated[int, Query(ge=1)]):
    require_catalog_permission(db, actor)
    with actor_transaction(db, actor['id']):
        lock_tipo(db, tipo_id, version_esperada)
        if db.execute('SELECT 1 FROM solicitudes WHERE tipo_ausencia_id = %s LIMIT 1', (tipo_id,)).fetchone():
            raise HTTPException(409, 'El tipo tiene solicitudes asociadas; puede desactivarlo')
        db.execute('DELETE FROM tipos_ausencia WHERE id = %s AND version = %s', (tipo_id, version_esperada))
        audit_access(db, actor['id'], 'ACCION_SENSIBLE')
        return {'estado': 'eliminado', 'id': tipo_id}


@admin_router.get('/flujos-aprobacion', dependencies=[Depends(require_admin)])
def list_flows(db: Db, actor: Actor):
    require_catalog_permission(db, actor)
    with actor_transaction(db, actor['id']):
        audit_access(db, actor['id'], 'CONSULTA_CATALOGO')
        return db.execute(
            '''SELECT f.id, f.codigo, f.nombre, f.activo,
                      jsonb_agg(jsonb_build_object('id', e.id, 'orden', e.orden,
                      'rol_codigo', e.rol_codigo, 'requiere_validacion', e.requiere_validacion)
                      ORDER BY e.orden) AS etapas
               FROM flujo_aprobacion f JOIN etapas_flujo e ON e.flujo_id = f.id
               GROUP BY f.id ORDER BY f.codigo'''
        ).fetchall()


@admin_router.get('/revisiones/pendientes', dependencies=[Depends(require_admin)])
def pending_reviews(db: Db, actor: Actor, limite: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0):
    with actor_transaction(db, actor['id']):
        audit_access(db, actor['id'], 'CONSULTA_BANDEJA')
        return db.execute(
            '''SELECT r.id AS revision_id, r.version AS version_revision,
                      r.aprobador_id, r.rol_codigo, r.estado AS estado_revision,
                      e.requiere_validacion, s.id AS solicitud_id,
                      s.version AS version_solicitud, s.estado_codigo,
                      s.fecha_inicio, s.fecha_fin, s.hora_inicio, s.hora_fin,
                      s.motivo AS observacion_empleado, s.requiere_revision_adicional,
                      u.nombre AS solicitante, u.area, t.nombre AS tipo_ausencia
               FROM revisiones r JOIN solicitudes s ON s.id = r.solicitud_id
               JOIN etapas_flujo e ON e.id = r.etapa_id
               JOIN usuarios u ON u.id = s.solicitante_id
               JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id
               WHERE r.estado IN ('PENDIENTE', 'EN_REVISION')
                 AND s.estado_codigo = 'EN_REVISION' AND s.eliminado_en IS NULL
                 AND (%s OR r.aprobador_id = %s)
                 AND NOT EXISTS (
                     SELECT 1 FROM etapas_flujo previa
                     WHERE previa.flujo_id = s.flujo_id AND previa.orden < e.orden
                       AND NOT EXISTS (
                           SELECT 1 FROM revisiones rp JOIN aprobaciones ap ON ap.revision_id = rp.id
                           WHERE rp.solicitud_id = s.id AND rp.etapa_id = previa.id
                             AND ap.decision IN ('APROBAR', 'VALIDAR_Y_APROBAR')))
               ORDER BY r.asignada_en, r.id LIMIT %s OFFSET %s''',
            ('administrador' in actor['roles'], actor['id'], limite, offset),
        ).fetchall()


@admin_router.get('/solicitudes/{solicitud_id}', dependencies=[Depends(require_admin)])
def detail_solicitud(solicitud_id: PositiveId, db: Db, actor: Actor):
    visible_solicitud(db, actor, solicitud_id)
    with actor_transaction(db, actor['id']):
        row = visible_solicitud(db, actor, solicitud_id)
        audit_access(db, actor['id'], 'CONSULTA_SOLICITUD', solicitud_id)
        row['revisiones'] = db.execute(
            '''SELECT r.*, u.nombre AS aprobador, e.orden, e.requiere_validacion
               FROM revisiones r JOIN usuarios u ON u.id = r.aprobador_id
               JOIN etapas_flujo e ON e.id = r.etapa_id
               WHERE r.solicitud_id = %s ORDER BY e.orden''', (solicitud_id,),
        ).fetchall()
        row['observaciones'] = db.execute(
            '''SELECT o.id, o.actor_id, u.nombre AS actor, o.clase, o.contenido, o.creada_en
               FROM observaciones o JOIN usuarios u ON u.id = o.actor_id
               WHERE o.solicitud_id = %s ORDER BY o.creada_en, o.id''', (solicitud_id,),
        ).fetchall()
        return row


@admin_router.get('/solicitudes/{solicitud_id}/historial', dependencies=[Depends(require_admin)])
def history_solicitud(solicitud_id: PositiveId, db: Db, actor: Actor):
    visible_solicitud(db, actor, solicitud_id)
    with actor_transaction(db, actor['id']):
        audit_access(db, actor['id'], 'CONSULTA_HISTORIAL', solicitud_id)
        return db.execute(
            '''SELECT h.*, u.nombre AS actor FROM historial_solicitud h
               JOIN usuarios u ON u.id = h.actor_id
               WHERE h.solicitud_id = %s ORDER BY h.version''', (solicitud_id,),
        ).fetchall()


@admin_router.post('/revisiones/{revision_id}/decision', dependencies=[Depends(require_admin)])
def decide_revision(revision_id: PositiveId, body: DecisionInput, db: Db, actor: Actor):
    reference = db.execute('SELECT solicitud_id, aprobador_id FROM revisiones WHERE id = %s', (revision_id,)).fetchone()
    if not reference or reference['aprobador_id'] != actor['id']:
        audit_access(db, actor['id'], 'ACCION_SENSIBLE', result='DENEGADO')
        raise HTTPException(404, 'Revisión no asignada a esta identidad')
    with actor_transaction(db, actor['id']):
        solicitud = db.execute('SELECT * FROM solicitudes WHERE id = %s FOR UPDATE', (reference['solicitud_id'],)).fetchone()
        revision = db.execute('SELECT * FROM revisiones WHERE id = %s FOR UPDATE', (revision_id,)).fetchone()
        if revision['aprobador_id'] != actor['id']:
            raise HTTPException(403, 'La revisión no está asignada a esta identidad')
        if solicitud['eliminado_en'] is not None or solicitud['estado_codigo'] != 'EN_REVISION' or revision['estado'] not in {'PENDIENTE', 'EN_REVISION'}:
            raise HTTPException(409, 'La revisión ya no admite decisiones')
        if solicitud['version'] != body.version_solicitud_esperada or revision['version'] != body.version_revision_esperada:
            raise HTTPException(409, 'Las versiones cambiaron; recargue la solicitud')
        etapa = db.execute('SELECT * FROM etapas_flujo WHERE id = %s FOR SHARE', (revision['etapa_id'],)).fetchone()
        if etapa['rol_codigo'] not in actor['roles']:
            raise HTTPException(403, 'La identidad no conserva el rol de la etapa')
        previous_incomplete = db.execute(
            '''SELECT 1 FROM etapas_flujo e WHERE e.flujo_id = %s AND e.orden < %s
               AND NOT EXISTS (SELECT 1 FROM revisiones r JOIN aprobaciones a ON a.revision_id = r.id
                 WHERE r.solicitud_id = %s AND r.etapa_id = e.id
                   AND a.decision IN ('APROBAR', 'VALIDAR_Y_APROBAR')) LIMIT 1''',
            (solicitud['flujo_id'], etapa['orden'], solicitud['id']),
        ).fetchone()
        if previous_incomplete:
            raise HTTPException(409, 'Una etapa anterior sigue pendiente')
        if body.decision == 'VALIDAR_Y_APROBAR' and etapa['rol_codigo'] != 'talento_humano':
            raise HTTPException(422, 'Solo Talento Humano puede validar y aprobar')
        if body.decision == 'APROBAR' and etapa['requiere_validacion']:
            raise HTTPException(422, 'Esta etapa requiere VALIDAR_Y_APROBAR')
        next_stage = None
        next_revision = None
        next_actor_id = None
        if body.decision != 'RECHAZAR':
            next_stage = db.execute(
                'SELECT * FROM etapas_flujo WHERE flujo_id = %s AND orden > %s ORDER BY orden LIMIT 1 FOR SHARE',
                (solicitud['flujo_id'], etapa['orden']),
            ).fetchone()
        if next_stage:
            next_revision = db.execute(
                'SELECT * FROM revisiones WHERE solicitud_id = %s AND etapa_id = %s FOR UPDATE',
                (solicitud['id'], next_stage['id']),
            ).fetchone()
            if next_revision:
                if next_revision['estado'] not in {'PENDIENTE', 'EN_REVISION'}:
                    raise HTTPException(409, 'La siguiente etapa tiene un estado incompatible')
                next_actor_id = next_revision['aprobador_id']
                if body.siguiente_aprobador_id is not None and body.siguiente_aprobador_id != next_actor_id:
                    raise HTTPException(409, 'La siguiente etapa ya tiene otro aprobador asignado')
            else:
                next_actor_id = body.siguiente_aprobador_id
                if next_actor_id is None:
                    raise HTTPException(422, 'Debe indicar siguiente_aprobador_id para la siguiente etapa')
            eligible = db.execute(
                '''SELECT u.id FROM usuarios u JOIN usuario_roles ur ON ur.usuario_id = u.id
                   WHERE u.id = %s AND u.activo AND ur.rol_codigo = %s FOR SHARE OF u, ur''',
                (next_actor_id, next_stage['rol_codigo']),
            ).fetchone()
            if not eligible:
                raise HTTPException(422, 'El siguiente aprobador debe estar activo y tener el rol requerido')
            if next_stage['rol_codigo'] == 'jefe_inmediato':
                owner = db.execute('SELECT jefe_inmediato_id FROM usuarios WHERE id = %s FOR SHARE', (solicitud['solicitante_id'],)).fetchone()
                if owner['jefe_inmediato_id'] != next_actor_id:
                    raise HTTPException(422, 'El aprobador debe ser el jefe inmediato del solicitante')
        elif body.siguiente_aprobador_id is not None:
            raise HTTPException(422, 'No existe una siguiente etapa para asignar')
        approval = db.execute(
            '''INSERT INTO aprobaciones
               (revision_id, solicitud_id, actor_id, decision, version_solicitud_esperada, version_revision_esperada)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING *''',
            (revision_id, solicitud['id'], actor['id'], body.decision,
             body.version_solicitud_esperada, body.version_revision_esperada),
        ).fetchone()
        if body.observacion:
            clase = {'APROBAR': 'APROBACION', 'RECHAZAR': 'RECHAZO', 'VALIDAR_Y_APROBAR': 'VALIDACION'}[body.decision]
            db.execute(
                '''INSERT INTO observaciones (solicitud_id, actor_id, aprobacion_id, clase, contenido)
                   VALUES (%s, %s, %s, %s, %s)''',
                (solicitud['id'], actor['id'], approval['id'], clase, body.observacion),
            )
        if next_stage:
            if not next_revision:
                next_revision = db.execute(
                    '''INSERT INTO revisiones (solicitud_id, flujo_id, etapa_id, rol_codigo, aprobador_id)
                       VALUES (%s, %s, %s, %s, %s) RETURNING *''',
                    (solicitud['id'], solicitud['flujo_id'], next_stage['id'], next_stage['rol_codigo'], next_actor_id),
                ).fetchone()
            enqueue_pending_notification(db, next_revision)
        enqueue_state_notification(db, solicitud['id'])
        audit_access(db, actor['id'], 'ACCION_SENSIBLE', solicitud['id'])
        current = db.execute('SELECT id, estado_codigo, version FROM solicitudes WHERE id = %s', (solicitud['id'],)).fetchone()
        current_revision = db.execute('SELECT id, estado, version FROM revisiones WHERE id = %s', (revision_id,)).fetchone()
        return {'decision': approval, 'solicitud': current, 'revision': current_revision, 'siguiente_revision': next_revision}


@admin_router.get('/notificaciones', dependencies=[Depends(require_admin)])
def list_notifications(db: Db, actor: Actor, limite: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0):
    with actor_transaction(db, actor['id']):
        audit_access(db, actor['id'], 'CONSULTA_BANDEJA')
        return db.execute(
            '''SELECT id, solicitud_id, revision_id, tipo, canal, prioridad, asunto,
                      mensaje, estado_envio, creada_en, enviada_en, leida_en
               FROM notificaciones WHERE destinatario_id = %s
               ORDER BY creada_en DESC, id DESC LIMIT %s OFFSET %s''',
            (actor['id'], limite, offset),
        ).fetchall()


app.include_router(public_router)
app.include_router(admin_router)