from fastapi import APIRouter, Depends, HTTPException, Query
from .common import get_db, require_admin, require_hr, admin_request, audit, history, CATALOG_SQL
from .models import Decision, TipoAusencia, Flujo, Estado

router = APIRouter(prefix='/api/admin', tags=['Administración'])

@router.get('/solicitudes')
def listar(estado: Estado | None = None, pendientes: bool = True,
           limite: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
           user=Depends(require_admin), conn=Depends(get_db)):
    audit(conn, 'CONSULTA_BANDEJA')
    return conn.execute('''SELECT s.*, e.nombre AS solicitante, a.nombre AS area, t.nombre AS tipo_ausencia
        FROM solicitudes s JOIN empleados e ON e.id = s.solicitante_id
        JOIN areas a ON a.id = e.area_id JOIN tipos_ausencia t ON t.id = s.tipo_ausencia_id
        WHERE s.solicitante_id <> %s AND (%s::text IS NULL OR s.estado_codigo = %s)
        AND EXISTS (SELECT 1 FROM revisiones r JOIN empleado_roles er
            ON er.rol_codigo = r.rol_codigo AND er.empleado_id = %s
            WHERE r.solicitud_id = s.id AND (r.aprobador_id IS NULL OR r.aprobador_id = %s)
              AND (NOT %s OR r.estado = 'PENDIENTE'))
        ORDER BY s.creado_en, s.id LIMIT %s OFFSET %s''',
        (user['id'], estado, estado, user['id'], user['id'], pendientes, limite, offset)).fetchall()

@router.get('/solicitudes/{solicitud_id}')
def detalle(solicitud_id: int, user=Depends(require_admin), conn=Depends(get_db)):
    row = admin_request(conn, user, solicitud_id)
    audit(conn, 'CONSULTA_DETALLE', solicitud_id)
    row['solicitante'] = conn.execute('''SELECT e.id, e.nombre, e.documento, a.nombre AS area, c.nombre AS cargo
        FROM empleados e JOIN areas a ON a.id = e.area_id JOIN cargos c ON c.id = e.cargo_id
        WHERE e.id = %s''', (row['solicitante_id'],)).fetchone()
    row['revisiones'] = conn.execute('SELECT * FROM revisiones WHERE solicitud_id = %s ORDER BY orden', (solicitud_id,)).fetchall()
    return row

@router.get('/solicitudes/{solicitud_id}/historial')
def historial(solicitud_id: int, user=Depends(require_admin), conn=Depends(get_db)):
    admin_request(conn, user, solicitud_id)
    audit(conn, 'CONSULTA_HISTORIAL', solicitud_id)
    return history(conn, solicitud_id)

@router.post('/solicitudes/{solicitud_id}/decisiones', status_code=201)
def decidir(solicitud_id: int, data: Decision, user=Depends(require_admin), conn=Depends(get_db)):
    admin_request(conn, user, solicitud_id)
    with conn.transaction():
        row = admin_request(conn, user, solicitud_id, lock=True)
        if row['version'] != data.version:
            raise HTTPException(409, 'La versión cambió; actualice la bandeja')
        if row['estado_codigo'] not in ('ENVIADA', 'EN_REVISION'):
            raise HTTPException(409, 'La solicitud ya está finalizada')
        revision = conn.execute("SELECT * FROM revisiones WHERE solicitud_id = %s AND estado = 'PENDIENTE' ORDER BY orden LIMIT 1 FOR UPDATE", (solicitud_id,)).fetchone()
        if not revision:
            raise HTTPException(409, 'No hay una revisión pendiente')
        if revision['rol_codigo'] not in user['roles'] or revision['aprobador_id'] not in (None, user['id']):
            raise HTTPException(403, 'Esta revisión corresponde a otro aprobador')
        if data.accion in ('VALIDAR', 'VALIDAR_Y_APROBAR') and revision['rol_codigo'] != 'TALENTO_HUMANO':
            raise HTTPException(422, 'La validación solo corresponde al paso de Talento Humano')
        if data.accion == 'VALIDAR' and revision['validada_en'] is not None:
            raise HTTPException(409, 'La revisión ya fue validada')
        if data.accion == 'APROBAR' and revision['rol_codigo'] == 'TALENTO_HUMANO' and revision['validada_en'] is None:
            raise HTTPException(422, 'Primero valide o use VALIDAR_Y_APROBAR')
        approval = conn.execute('''INSERT INTO aprobaciones
            (revision_id, solicitud_id, actor_id, accion, version_esperada, version_resultante)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''',
            (revision['id'], solicitud_id, user['id'], data.accion, data.version, data.version + 1)).fetchone()
        if data.observacion:
            observation_type = {'VALIDAR': 'VALIDACION', 'APROBAR': 'APROBACION', 'RECHAZAR': 'RECHAZO', 'VALIDAR_Y_APROBAR': 'APROBACION'}[data.accion]
            conn.execute('''INSERT INTO observaciones (solicitud_id, aprobacion_id, actor_id, tipo, texto)
                VALUES (%s,%s,%s,%s,%s)''', (solicitud_id, approval['id'], user['id'], observation_type, data.observacion))
        return {'decision': approval, 'solicitud': conn.execute('SELECT * FROM solicitudes WHERE id = %s', (solicitud_id,)).fetchone()}

@router.get('/tipos-ausencia')
def tipos(user=Depends(require_admin), conn=Depends(get_db)):
    require_hr(conn, user)
    audit(conn, 'CONSULTA_CATALOGO')
    return conn.execute(CATALOG_SQL + ' ORDER BY t.nombre').fetchall()

@router.get('/tipos-ausencia/{tipo_id}')
def tipo_detalle(tipo_id: int, user=Depends(require_admin), conn=Depends(get_db)):
    require_hr(conn, user)
    audit(conn, 'CONSULTA_CATALOGO')
    row = conn.execute(CATALOG_SQL + ' WHERE t.id = %s', (tipo_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Tipo de ausencia inexistente')
    return row

@router.get('/flujos')
def flujos(user=Depends(require_admin), conn=Depends(get_db)):
    require_hr(conn, user)
    audit(conn, 'CONSULTA_CATALOGO')
    return conn.execute('''SELECT f.id, f.codigo, f.nombre,
        jsonb_agg(jsonb_build_object('orden', p.orden, 'rol_codigo', p.rol_codigo) ORDER BY p.orden) AS pasos
        FROM flujo_aprobacion f JOIN pasos_flujo p ON p.flujo_id = f.id GROUP BY f.id ORDER BY f.id''').fetchall()


def flow_id(conn, code):
    row = conn.execute('SELECT id FROM flujo_aprobacion WHERE codigo = %s', (code,)).fetchone()
    if not row:
        raise HTTPException(422, 'Flujo no disponible')
    return row['id']

@router.post('/tipos-ausencia', status_code=201)
def crear_tipo(data: TipoAusencia, user=Depends(require_admin), conn=Depends(get_db)):
    require_hr(conn, user)
    with conn.transaction():
        return conn.execute('''INSERT INTO tipos_ausencia (nombre, estado, requiere_motivo, permite_horas, flujo_id)
            VALUES (%s,%s,%s,%s,%s) RETURNING *''',
            (data.nombre, data.estado, data.requiere_motivo, data.permite_horas, flow_id(conn, data.flujo_codigo))).fetchone()

@router.put('/tipos-ausencia/{tipo_id}')
def editar_tipo(tipo_id: int, data: TipoAusencia, user=Depends(require_admin), conn=Depends(get_db)):
    require_hr(conn, user)
    with conn.transaction():
        row = conn.execute('''UPDATE tipos_ausencia SET nombre = %s, estado = %s, requiere_motivo = %s,
            permite_horas = %s, flujo_id = %s WHERE id = %s RETURNING *''',
            (data.nombre, data.estado, data.requiere_motivo, data.permite_horas, flow_id(conn, data.flujo_codigo), tipo_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Tipo de ausencia inexistente')
        return row

@router.put('/tipos-ausencia/{tipo_id}/flujo')
def asignar_flujo(tipo_id: int, data: Flujo, user=Depends(require_admin), conn=Depends(get_db)):
    require_hr(conn, user)
    with conn.transaction():
        row = conn.execute('UPDATE tipos_ausencia SET flujo_id = %s WHERE id = %s RETURNING *', (flow_id(conn, data.flujo_codigo), tipo_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Tipo de ausencia inexistente')
        return row

@router.delete('/tipos-ausencia/{tipo_id}')
def borrar_tipo(tipo_id: int, user=Depends(require_admin), conn=Depends(get_db)):
    require_hr(conn, user)
    with conn.transaction():
        row = conn.execute('SELECT id FROM tipos_ausencia WHERE id = %s FOR UPDATE', (tipo_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Tipo de ausencia inexistente')
        if conn.execute('SELECT 1 FROM solicitudes WHERE tipo_ausencia_id = %s LIMIT 1', (tipo_id,)).fetchone():
            raise HTTPException(409, 'El tipo está en uso; desactívelo en lugar de eliminarlo')
        conn.execute('DELETE FROM tipos_ausencia WHERE id = %s', (tipo_id,))
        return {'eliminado': True}

@router.get('/notificaciones')
def notificaciones(limite: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   user=Depends(require_admin), conn=Depends(get_db)):
    audit(conn, 'CONSULTA_BANDEJA')
    return conn.execute('''SELECT n.id, n.solicitud_id, n.tipo, n.prioridad, n.creado_en, n.leida_en
        FROM notificaciones n JOIN revisiones r ON r.id = n.revision_id
        JOIN solicitudes s ON s.id = n.solicitud_id
        WHERE n.destinatario_id = %s AND n.tipo = 'PENDIENTE_REVISION'
        AND s.solicitante_id <> %s AND EXISTS (SELECT 1 FROM empleado_roles er
            WHERE er.empleado_id = %s AND er.rol_codigo = r.rol_codigo)
        AND (r.aprobador_id IS NULL OR r.aprobador_id = %s)
        ORDER BY n.creado_en DESC, n.id DESC LIMIT %s OFFSET %s''',
        (user['id'], user['id'], user['id'], user['id'], limite, offset)).fetchall()