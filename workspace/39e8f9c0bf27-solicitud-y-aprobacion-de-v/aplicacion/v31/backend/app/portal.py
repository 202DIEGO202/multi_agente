from fastapi import APIRouter, Depends, HTTPException, Query, Request
from .common import get_db, require_user, context, audit, issue_token, own_request, validate_policy, assert_editable
from .models import Acceso, TokenRespuesta, CrearSolicitud, EditarSolicitud, Version, Estado

router = APIRouter(prefix='/api', tags=['Portal'])
portal_router = APIRouter(prefix='/portal')

# El portal tiene rutas propias y exige identidad individual verificada.
CAMPOS_SOLICITUD = (
    'id', 'tipo_ausencia_id', 'origen', 'referencia_formato',
    'fecha_inicio', 'fecha_fin', 'hora_inicio', 'hora_fin', 'motivo',
    'estado_codigo', 'version', 'creado_en', 'actualizado_en'
)


def solicitud_portal(conn, row):
    result = {campo: row[campo] for campo in CAMPOS_SOLICITUD}
    tipo = conn.execute('SELECT nombre FROM tipos_ausencia WHERE id = %s',
                        (row['tipo_ausencia_id'],)).fetchone()
    result['tipo_ausencia'] = tipo['nombre'] if tipo else None
    return result


@router.post('/acceso', response_model=TokenRespuesta)
def acceso(data: Acceso, request: Request, conn=Depends(get_db)):
    user = conn.execute('SELECT id FROM empleados WHERE documento = %s AND activo', (data.documento,)).fetchone()
    if not user:
        raise HTTPException(401, 'No se pudo identificar a un empleado activo')
    token = issue_token(user['id'])
    context(conn, user['id'], request)
    audit(conn, 'ACCESO_PORTAL')
    return token


@portal_router.get('/me')
def me(user=Depends(require_user), conn=Depends(get_db)):
    return conn.execute('''SELECT e.id, e.nombre, e.documento, e.correo, e.turno,
        a.nombre AS area, c.nombre AS cargo FROM empleados e
        JOIN areas a ON a.id = e.area_id JOIN cargos c ON c.id = e.cargo_id
        WHERE e.id = %s''', (user['id'],)).fetchone()


@portal_router.get('/tipos-ausencia')
def tipos(user=Depends(require_user), conn=Depends(get_db)):
    audit(conn, 'CONSULTA_CATALOGO')
    # Solo opciones y reglas necesarias para completar el formulario.
    return conn.execute('''SELECT id, nombre, requiere_motivo, permite_horas
        FROM tipos_ausencia WHERE estado = 'ACTIVO' ORDER BY nombre''').fetchall()


@portal_router.post('/solicitudes', status_code=201)
def crear(data: CrearSolicitud, user=Depends(require_user), conn=Depends(get_db)):
    with conn.transaction():
        policy = conn.execute("SELECT * FROM tipos_ausencia WHERE id = %s AND estado = 'ACTIVO' FOR SHARE", (data.tipo_ausencia_id,)).fetchone()
        if not policy:
            raise HTTPException(422, 'Seleccione un tipo de ausencia activo')
        validate_policy(data, policy, data.origen)
        steps = conn.execute('SELECT * FROM pasos_flujo WHERE flujo_id = %s ORDER BY orden', (policy['flujo_id'],)).fetchall()
        if not steps:
            raise HTTPException(422, 'El tipo no tiene un flujo configurado')
        for step in steps:
            if step['rol_codigo'] == 'JEFE_INMEDIATO':
                available = conn.execute('''SELECT 1 FROM empleados e JOIN empleado_roles er ON er.empleado_id = e.id
                    WHERE e.id = %s AND e.activo AND er.rol_codigo = 'JEFE_INMEDIATO' ''', (user['jefe_inmediato_id'],)).fetchone()
            else:
                available = conn.execute('''SELECT 1 FROM empleados e JOIN empleado_roles er ON er.empleado_id = e.id
                    WHERE e.activo AND e.id <> %s AND er.rol_codigo = 'TALENTO_HUMANO' LIMIT 1''', (user['id'],)).fetchone()
            if not available:
                raise HTTPException(422, 'El flujo no dispone de un aprobador activo autorizado')
        # Los disparadores persisten revisiones, versión, historial, auditoría y avisos.
        row = conn.execute('''INSERT INTO solicitudes
            (solicitante_id, tipo_ausencia_id, flujo_id, origen, referencia_formato,
             fecha_inicio, fecha_fin, hora_inicio, hora_fin, motivo, requiere_motivo, permite_horas)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (user['id'], data.tipo_ausencia_id, policy['flujo_id'], data.origen, data.referencia_formato,
             data.fecha_inicio, data.fecha_fin, data.hora_inicio, data.hora_fin, data.motivo,
             policy['requiere_motivo'], policy['permite_horas'])).fetchone()
        return solicitud_portal(conn, row)


@portal_router.get('/solicitudes')
def listar(estado: Estado | None = None, limite: int = Query(50, ge=1, le=100),
           offset: int = Query(0, ge=0), user=Depends(require_user), conn=Depends(get_db)):
    audit(conn, 'CONSULTA_BANDEJA')
    return conn.execute('''SELECT s.id, s.tipo_ausencia_id, t.nombre AS tipo_ausencia,
        s.fecha_inicio, s.fecha_fin, s.hora_inicio, s.hora_fin,
        s.estado_codigo, s.version, s.creado_en, s.actualizado_en
        FROM solicitudes s JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id
        WHERE s.solicitante_id = %s AND (%s::text IS NULL OR s.estado_codigo = %s)
        ORDER BY s.creado_en DESC, s.id DESC LIMIT %s OFFSET %s''',
        (user['id'], estado, estado, limite, offset)).fetchall()


@portal_router.get('/solicitudes/{solicitud_id}')
def detalle(solicitud_id: int, user=Depends(require_user), conn=Depends(get_db)):
    row = own_request(conn, user, solicitud_id)
    audit(conn, 'CONSULTA_DETALLE', solicitud_id)
    return solicitud_portal(conn, row)


@portal_router.get('/solicitudes/{solicitud_id}/historial')
def historial(solicitud_id: int, user=Depends(require_user), conn=Depends(get_db)):
    own_request(conn, user, solicitud_id)
    audit(conn, 'CONSULTA_HISTORIAL', solicitud_id)
    # Seguimiento propio, sin identificadores internos de los aprobadores.
    return {
        'historial': conn.execute('''SELECT version, estado_anterior, estado_nuevo,
            operacion, creado_en FROM historial_solicitud
            WHERE solicitud_id = %s ORDER BY version''', (solicitud_id,)).fetchall(),
        'observaciones': conn.execute('''SELECT tipo, texto, creado_en FROM observaciones
            WHERE solicitud_id = %s ORDER BY creado_en, id''', (solicitud_id,)).fetchall(),
        'decisiones': conn.execute('''SELECT accion, version_resultante, creado_en
            FROM aprobaciones WHERE solicitud_id = %s ORDER BY creado_en, id''',
            (solicitud_id,)).fetchall()
    }


@portal_router.put('/solicitudes/{solicitud_id}')
def editar(solicitud_id: int, data: EditarSolicitud, user=Depends(require_user), conn=Depends(get_db)):
    own_request(conn, user, solicitud_id)
    with conn.transaction():
        row = own_request(conn, user, solicitud_id, lock=True)
        assert_editable(conn, row, data.version)
        validate_policy(data, row, row['origen'])
        updated = conn.execute('''UPDATE solicitudes SET fecha_inicio = %s, fecha_fin = %s,
            hora_inicio = %s, hora_fin = %s, motivo = %s, referencia_formato = %s, version = version + 1
            WHERE id = %s AND version = %s RETURNING *''',
            (data.fecha_inicio, data.fecha_fin, data.hora_inicio, data.hora_fin, data.motivo,
             data.referencia_formato, solicitud_id, data.version)).fetchone()
        if not updated:
            raise HTTPException(409, 'Conflicto de versión')
        return solicitud_portal(conn, updated)


@portal_router.delete('/solicitudes/{solicitud_id}')
def cancelar(solicitud_id: int, data: Version, user=Depends(require_user), conn=Depends(get_db)):
    own_request(conn, user, solicitud_id)
    with conn.transaction():
        row = own_request(conn, user, solicitud_id, lock=True)
        if row['version'] != data.version or row['estado_codigo'] not in ('ENVIADA', 'EN_REVISION'):
            raise HTTPException(409, 'Versión desactualizada o solicitud finalizada')
        updated = conn.execute("UPDATE solicitudes SET estado_codigo = 'CANCELADA', version = version + 1 WHERE id = %s AND version = %s RETURNING *", (solicitud_id, data.version)).fetchone()
        if not updated:
            raise HTTPException(409, 'Conflicto de versión')
        return solicitud_portal(conn, updated)


@portal_router.get('/notificaciones')
def notificaciones(limite: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   user=Depends(require_user), conn=Depends(get_db)):
    audit(conn, 'CONSULTA_BANDEJA')
    return conn.execute('''SELECT n.id, n.solicitud_id, n.tipo, n.prioridad, n.creado_en, n.leida_en,
        h.estado_anterior, h.estado_nuevo FROM notificaciones n
        JOIN solicitudes s ON s.id = n.solicitud_id
        LEFT JOIN historial_solicitud h ON h.id = n.historial_id
        WHERE n.destinatario_id = %s AND s.solicitante_id = %s AND n.tipo = 'CAMBIO_ESTADO'
        ORDER BY n.creado_en DESC, n.id DESC LIMIT %s OFFSET %s''',
        (user['id'], user['id'], limite, offset)).fetchall()


@portal_router.patch('/notificaciones/{notificacion_id}/leida')
def leer(notificacion_id: int, user=Depends(require_user), conn=Depends(get_db)):
    audit(conn, 'CONSULTA_BANDEJA')
    row = conn.execute('''UPDATE notificaciones n SET leida_en = COALESCE(n.leida_en, CURRENT_TIMESTAMP)
        WHERE n.id = %s AND n.destinatario_id = %s AND n.tipo = 'CAMBIO_ESTADO'
        AND EXISTS (SELECT 1 FROM solicitudes s WHERE s.id = n.solicitud_id AND s.solicitante_id = %s)
        RETURNING n.id, n.leida_en''', (notificacion_id, user['id'], user['id'])).fetchone()
    if not row:
        raise HTTPException(404, 'Notificación inexistente')
    return row


router.include_router(portal_router)