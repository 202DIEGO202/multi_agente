import hmac
import os
from datetime import date, datetime, time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from pydantic import Field, model_validator

from .db import actor_transaction, audit_access, get_db
from .models import InputModel

router = APIRouter(prefix='/api', tags=['Portal del empleado'])
Db = Annotated[object, Depends(get_db)]
PositiveId = Annotated[int, Path(ge=1)]


class SolicitudCreate(InputModel):
    tipo_ausencia_id: int = Field(ge=1, strict=True)
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: time | None = None
    hora_fin: time | None = None
    motivo: str | None = Field(default=None, min_length=1, max_length=5000)
    origen: Literal['PORTAL', 'FORMATO_OFICIAL'] = 'PORTAL'

    @model_validator(mode='after')
    def validar_periodo(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError('La fecha de fin no puede preceder a la fecha de inicio')
        if (self.hora_inicio is None) != (self.hora_fin is None):
            raise ValueError('Debe proporcionar ambas horas o ninguna')
        if self.hora_inicio is not None:
            if self.hora_inicio.tzinfo is not None or self.hora_fin.tzinfo is not None:
                raise ValueError('Las horas deben ser locales, sin zona horaria')
            inicio = datetime.combine(self.fecha_inicio, self.hora_inicio)
            fin = datetime.combine(self.fecha_fin, self.hora_fin)
            if fin <= inicio:
                raise ValueError('La fecha y hora final deben ser posteriores al inicio')
        return self


def require_employee(authorization: Annotated[str | None, Header()] = None):
    expected = os.environ.get('EMPLOYEE_API_TOKEN', '')
    if not expected or not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Autenticación del empleado requerida', headers={'WWW-Authenticate': 'Bearer'})
    token = authorization[7:]
    if not token or not hmac.compare_digest(token.encode('utf-8'), expected.encode('utf-8')):
        raise HTTPException(401, 'Credenciales del empleado inválidas', headers={'WWW-Authenticate': 'Bearer'})


def get_employee(db: Db, authenticated=Depends(require_employee)):
    # La identidad se vincula a la credencial en el servidor.
    try:
        employee_id = int(os.environ['EMPLOYEE_USER_ID'])
        if employee_id <= 0:
            raise ValueError
    except (KeyError, ValueError) as exc:
        raise HTTPException(503, 'Identidad del empleado no configurada') from exc
    employee = db.execute(
        '''SELECT u.id FROM usuarios u
           WHERE u.id = %s AND u.activo
             AND EXISTS (SELECT 1 FROM usuario_roles ur
                         WHERE ur.usuario_id = u.id AND ur.rol_codigo = 'empleado')''',
        (employee_id,),
    ).fetchone()
    if not employee:
        audit_access(db, None, 'AUTENTICACION', result='DENEGADO')
        raise HTTPException(403, 'Identidad del empleado inactiva o sin permiso')
    audit_access(db, employee_id, 'AUTENTICACION')
    return employee


Employee = Annotated[dict, Depends(get_employee)]


def own_solicitud(db, employee, solicitud_id):
    # Solo datos de seguimiento propios, sin la proyección administrativa.
    row = db.execute(
        '''SELECT s.id, t.nombre AS tipo_ausencia, e.nombre AS estado,
                  s.estado_codigo, s.fecha_inicio, s.fecha_fin,
                  s.hora_inicio, s.hora_fin, s.motivo, s.version,
                  s.creado_en, s.actualizado_en
           FROM solicitudes s JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id
           JOIN estados e ON e.codigo = s.estado_codigo
           WHERE s.id = %s AND s.solicitante_id = %s AND s.eliminado_en IS NULL''',
        (solicitud_id, employee['id']),
    ).fetchone()
    if not row:
        audit_access(db, employee['id'], 'CONSULTA_SOLICITUD', result='DENEGADO')
        raise HTTPException(404, 'Solicitud no disponible para esta identidad')
    return row


def first_approver(db, employee_id, etapa):
    if etapa['rol_codigo'] == 'jefe_inmediato':
        row = db.execute(
            '''SELECT jefe.id FROM usuarios empleado
               JOIN usuarios jefe ON jefe.id = empleado.jefe_inmediato_id
               JOIN usuario_roles ur ON ur.usuario_id = jefe.id
               WHERE empleado.id = %s AND jefe.activo
                 AND ur.rol_codigo = 'jefe_inmediato'
               FOR SHARE OF empleado, jefe, ur''',
            (employee_id,),
        ).fetchone()
        if not row:
            raise HTTPException(409, 'El empleado no tiene un jefe inmediato activo con el rol requerido')
        return row['id']
    configured = os.environ.get('TALENTO_HUMANO_USER_ID')
    if configured is not None:
        try:
            actor_id = int(configured)
            if actor_id <= 0:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(503, 'Asignación de Talento Humano mal configurada') from exc
        rows = db.execute(
            '''SELECT u.id FROM usuarios u JOIN usuario_roles ur ON ur.usuario_id = u.id
               WHERE u.id = %s AND u.activo AND ur.rol_codigo = 'talento_humano'
               FOR SHARE OF u, ur''', (actor_id,),
        ).fetchall()
    else:
        rows = db.execute(
            '''SELECT u.id FROM usuarios u JOIN usuario_roles ur ON ur.usuario_id = u.id
               WHERE u.activo AND ur.rol_codigo = 'talento_humano'
               ORDER BY u.id LIMIT 2 FOR SHARE OF u, ur'''
        ).fetchall()
    if len(rows) != 1:
        raise HTTPException(409, 'Debe configurarse un aprobador activo de Talento Humano inequívoco')
    return rows[0]['id']


@router.post('/solicitudes', status_code=201, dependencies=[Depends(require_employee)])
def create_solicitud(body: SolicitudCreate, db: Db, employee: Employee):
    with actor_transaction(db, employee['id']):
        active = db.execute('SELECT id FROM usuarios WHERE id = %s AND activo FOR SHARE', (employee['id'],)).fetchone()
        if not active:
            raise HTTPException(403, 'El empleado ya no está activo')
        tipo = db.execute(
            '''SELECT t.* FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id = t.flujo_id
               WHERE t.id = %s AND t.estado = 'Activo' AND f.activo FOR SHARE OF t, f''',
            (body.tipo_ausencia_id,),
        ).fetchone()
        if not tipo:
            raise HTTPException(422, 'Debe seleccionar un tipo de ausencia activo con flujo activo')
        if tipo['requiere_motivo'] and not body.motivo:
            raise HTTPException(422, 'El motivo es obligatorio para este tipo de ausencia')
        if body.hora_inicio is not None and not tipo['permite_horas']:
            raise HTTPException(422, 'El tipo de ausencia no permite registrar horas')
        etapa = db.execute(
            'SELECT * FROM etapas_flujo WHERE flujo_id = %s ORDER BY orden LIMIT 1 FOR SHARE',
            (tipo['flujo_id'],),
        ).fetchone()
        if not etapa:
            raise HTTPException(409, 'El flujo no tiene una etapa inicial configurada')
        aprobador_id = first_approver(db, employee['id'], etapa)
        solicitud = db.execute(
            '''INSERT INTO solicitudes
               (solicitante_id, tipo_ausencia_id, flujo_id, origen, fecha_inicio, fecha_fin,
                hora_inicio, hora_fin, motivo, requiere_motivo, permite_horas)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *''',
            (employee['id'], tipo['id'], tipo['flujo_id'], body.origen,
             body.fecha_inicio, body.fecha_fin, body.hora_inicio, body.hora_fin,
             body.motivo, tipo['requiere_motivo'], tipo['permite_horas']),
        ).fetchone()
        revision = db.execute(
            '''INSERT INTO revisiones (solicitud_id, flujo_id, etapa_id, rol_codigo, aprobador_id)
               VALUES (%s, %s, %s, %s, %s) RETURNING *''',
            (solicitud['id'], solicitud['flujo_id'], etapa['id'], etapa['rol_codigo'], aprobador_id),
        ).fetchone()
        solicitud = db.execute(
            '''UPDATE solicitudes SET estado_codigo = 'EN_REVISION', version = version + 1
               WHERE id = %s AND version = %s RETURNING *''',
            (solicitud['id'], solicitud['version']),
        ).fetchone()
        db.execute(
            '''INSERT INTO notificaciones
               (solicitud_id, destinatario_id, revision_id, tipo, asunto, mensaje)
               VALUES (%s, %s, %s, 'PENDIENTE_REVISION',
                       'Solicitud pendiente de revisión', 'Tiene una solicitud asignada para revisión')''',
            (solicitud['id'], aprobador_id, revision['id']),
        )
        db.execute(
            '''INSERT INTO notificaciones
               (solicitud_id, destinatario_id, historial_id, tipo, asunto, mensaje)
               SELECT s.id, s.solicitante_id, h.id, 'CAMBIO_ESTADO',
                      'Cambio de estado de solicitud', 'Nuevo estado: En revisión'
               FROM solicitudes s JOIN historial_solicitud h
                 ON h.solicitud_id = s.id AND h.version = s.version
               WHERE s.id = %s AND h.evento = 'CAMBIO_ESTADO' ''',
            (solicitud['id'],),
        )
        audit_access(db, employee['id'], 'ACCION_SENSIBLE', solicitud['id'])
        return solicitud


@router.get('/portal/solicitudes/{solicitud_id}', dependencies=[Depends(require_employee)])
def detail_solicitud(solicitud_id: PositiveId, db: Db, employee: Employee):
    # Se audita también el intento denegado, sin revelar la existencia del recurso.
    own_solicitud(db, employee, solicitud_id)
    with actor_transaction(db, employee['id']):
        row = own_solicitud(db, employee, solicitud_id)
        audit_access(db, employee['id'], 'CONSULTA_SOLICITUD', solicitud_id)
        return row


@router.get('/portal/solicitudes/{solicitud_id}/historial', dependencies=[Depends(require_employee)])
def history_solicitud(solicitud_id: PositiveId, db: Db, employee: Employee):
    own_solicitud(db, employee, solicitud_id)
    with actor_transaction(db, employee['id']):
        own_solicitud(db, employee, solicitud_id)
        audit_access(db, employee['id'], 'CONSULTA_HISTORIAL', solicitud_id)
        # La identidad de los revisores permanece en el historial administrativo.
        return db.execute(
            '''SELECT h.version, h.estado_anterior, h.estado_nuevo,
                      h.evento, h.ocurrido_en
               FROM historial_solicitud h
               JOIN solicitudes s ON s.id = h.solicitud_id
               WHERE h.solicitud_id = %s AND s.solicitante_id = %s
                 AND s.eliminado_en IS NULL
               ORDER BY h.version''',
            (solicitud_id, employee['id']),
        ).fetchall()


@router.get('/portal/tipos-ausencia', dependencies=[Depends(require_employee)])
def employee_tipos(
    db: Db,
    employee: Employee,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    # Catálogo interno mínimo para resolver identificadores y guiar el formulario.
    with actor_transaction(db, employee['id']):
        audit_access(db, employee['id'], 'CONSULTA_CATALOGO')
        return db.execute(
            '''SELECT t.id, t.nombre, t.requiere_motivo, t.permite_horas
               FROM tipos_ausencia t
               JOIN flujo_aprobacion f ON f.id = t.flujo_id
               WHERE t.estado = 'Activo' AND f.activo
               ORDER BY lower(t.nombre), t.id LIMIT %s OFFSET %s''',
            (limite, offset),
        ).fetchall()


@router.get('/portal/solicitudes', dependencies=[Depends(require_employee)])
def employee_solicitudes(
    db: Db,
    employee: Employee,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    # No se admite seleccionar otra identidad mediante parámetros del cliente.
    with actor_transaction(db, employee['id']):
        audit_access(db, employee['id'], 'CONSULTA_BANDEJA')
        return db.execute(
            '''SELECT s.id, t.nombre AS tipo_ausencia,
                      s.fecha_inicio, s.fecha_fin, s.hora_inicio, s.hora_fin,
                      s.estado_codigo, e.nombre AS estado, s.version,
                      s.creado_en, s.actualizado_en,
                      h.evento AS ultimo_cambio,
                      h.ocurrido_en AS fecha_ultimo_cambio
               FROM solicitudes s
               JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id
               JOIN estados e ON e.codigo = s.estado_codigo
               LEFT JOIN historial_solicitud h
                 ON h.solicitud_id = s.id AND h.version = s.version
               WHERE s.solicitante_id = %s AND s.eliminado_en IS NULL
               ORDER BY s.actualizado_en DESC, s.id DESC
               LIMIT %s OFFSET %s''',
            (employee['id'], limite, offset),
        ).fetchall()


@router.get('/portal/notificaciones', dependencies=[Depends(require_employee)])
def employee_notificaciones(
    db: Db,
    employee: Employee,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    # Solo avisos propios de seguimiento; se excluye la bandeja de aprobadores.
    with actor_transaction(db, employee['id']):
        audit_access(db, employee['id'], 'CONSULTA_BANDEJA')
        return db.execute(
            '''SELECT n.id, n.solicitud_id, n.tipo, n.asunto, n.mensaje,
                      n.creada_en, n.leida_en,
                      t.nombre AS tipo_ausencia, s.fecha_inicio, s.fecha_fin,
                      h.estado_anterior, anterior.nombre AS estado_anterior_nombre,
                      h.estado_nuevo, nuevo.nombre AS estado_nuevo_nombre,
                      h.ocurrido_en AS fecha_cambio
               FROM notificaciones n
               JOIN solicitudes s ON s.id = n.solicitud_id
               JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id
               JOIN historial_solicitud h
                 ON h.id = n.historial_id AND h.solicitud_id = s.id
               LEFT JOIN estados anterior ON anterior.codigo = h.estado_anterior
               JOIN estados nuevo ON nuevo.codigo = h.estado_nuevo
               WHERE n.destinatario_id = %s AND s.solicitante_id = %s
                 AND n.tipo = 'CAMBIO_ESTADO'
                 AND h.evento = 'CAMBIO_ESTADO' AND s.eliminado_en IS NULL
               ORDER BY n.creada_en DESC, n.id DESC
               LIMIT %s OFFSET %s''',
            (employee['id'], employee['id'], limite, offset),
        ).fetchall()