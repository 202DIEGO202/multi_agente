import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.main import app


CATALOGO = '/api/admin/tipos-ausencia'


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def validation(response, field=None):
    assert response.status_code == 422, response.text
    detail = response.json().get('detail')
    assert detail
    if field is not None:
        assert isinstance(detail, list), response.text
        assert any(field in error.get('loc', []) and error.get('type') for error in detail), response.text
    elif isinstance(detail, list):
        assert all(error.get('loc') and error.get('type') for error in detail)
    else:
        assert isinstance(detail, str)


class Escenario:
    def __init__(self, db, client, monkeypatch):
        self.db = db
        self.client = client
        self.monkeypatch = monkeypatch
        self.headers = {'Authorization': 'Bearer ' + os.environ['ADMIN_API_TOKEN']}
        self.admin = self.user(['administrador', 'jefe_inmediato', 'talento_humano'])
        self.jefe = self.user(['jefe_inmediato'], actor=self.admin)
        self.th = self.user(['talento_humano'], actor=self.admin)
        self.otro = self.user(['jefe_inmediato'], actor=self.admin)
        self.empleado = self.user(['empleado'], actor=self.admin, jefe=self.jefe)
        self.empleado_otro = self.user(['empleado'], actor=self.admin, jefe=self.otro)
        # Credencial del entorno vinculada a identidades propias del escenario.
        self.monkeypatch.setenv('EMPLOYEE_API_TOKEN', os.environ['ADMIN_API_TOKEN'])
        self.monkeypatch.setenv('EMPLOYEE_USER_ID', str(self.empleado))
        self.monkeypatch.setenv('TALENTO_HUMANO_USER_ID', str(self.th))
        self.as_actor(self.admin)

    def user(self, roles, actor=None, jefe=None):
        uid = self.db.execute("SELECT nextval(pg_get_serial_sequence('usuarios', 'id')) AS id").fetchone()['id']
        unique = uuid4().hex
        with self.db.transaction():
            self.db.execute("SELECT set_config('app.usuario_id', %s, true)", (str(actor or uid),))
            self.db.execute(
                '''INSERT INTO usuarios (id, identidad_externa, nombre, documento, correo, area, cargo, jefe_inmediato_id)
                   OVERRIDING SYSTEM VALUE VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (uid, unique, 'QA ' + unique, unique, unique + '@example.invalid', 'Área QA', 'Cargo QA', jefe),
            )
            for role in roles:
                self.db.execute('INSERT INTO usuario_roles (usuario_id, rol_codigo) VALUES (%s, %s)', (uid, role))
        return uid

    def as_actor(self, uid):
        self.monkeypatch.setenv('ADMIN_USER_ID', str(uid))

    def request(self, method, path, **kwargs):
        return self.client.request(method, path, headers=self.headers, **kwargs)

    def tipo(self, flujo='JEFE', **changes):
        self.as_actor(self.admin)
        payload = {'nombre': 'QA-' + uuid4().hex, 'flujo_codigo': flujo,
                   'estado': 'Activo', 'requiere_motivo': True, 'permite_horas': True}
        payload.update(changes)
        return ok(self.request('POST', CATALOGO, json=payload), 201)

    def solicitud(self, flujo='JEFE', owner=None, approver=None, revisar=True):
        tipo = self.tipo(flujo)
        owner = owner or self.empleado
        approver = approver or (self.th if flujo == 'TH' else self.jefe)
        etapa = self.db.execute(
            'SELECT * FROM etapas_flujo WHERE flujo_id = %s ORDER BY orden LIMIT 1',
            (tipo['flujo_id'],),
        ).fetchone()
        motivo = 'Motivo QA ' + uuid4().hex
        with self.db.transaction():
            self.db.execute("SELECT set_config('app.usuario_id', %s, true)", (str(owner),))
            solicitud = self.db.execute(
                '''INSERT INTO solicitudes (solicitante_id, tipo_ausencia_id, flujo_id,
                   fecha_inicio, fecha_fin, hora_inicio, hora_fin, motivo, requiere_motivo, permite_horas)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true, true) RETURNING *''',
                (owner, tipo['id'], tipo['flujo_id'], date(2040, 6, 1), date(2040, 6, 1),
                 time(9), time(10), motivo),
            ).fetchone()
            if revisar:
                solicitud = self.db.execute(
                    "UPDATE solicitudes SET estado_codigo = 'EN_REVISION', version = version + 1 WHERE id = %s RETURNING *",
                    (solicitud['id'],),
                ).fetchone()
            revision = self.db.execute(
                '''INSERT INTO revisiones (solicitud_id, flujo_id, etapa_id, rol_codigo, aprobador_id)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *''',
                (solicitud['id'], tipo['flujo_id'], etapa['id'], etapa['rol_codigo'], approver),
            ).fetchone()
        return {'tipo': tipo, 'solicitud': solicitud, 'revision': revision, 'actor': approver}

    def decision(self, item, decision='APROBAR', **changes):
        payload = {'decision': decision,
                   'version_solicitud_esperada': item['solicitud']['version'],
                   'version_revision_esperada': item['revision']['version'],
                   'observacion': 'Revisión QA ' + uuid4().hex}
        payload.update(changes)
        self.as_actor(item['actor'])
        return self.request('POST', f"/api/admin/revisiones/{item['revision']['id']}/decision", json=payload)

    def access_mark(self):
        return self.db.execute('SELECT coalesce(max(id), 0) AS id FROM auditoria_acceso').fetchone()['id']

    def assert_access(self, mark, actor, operation, sid=None):
        rows = self.db.execute(
            '''SELECT * FROM auditoria_acceso WHERE id > %s AND actor_id = %s
               AND operacion = %s AND resultado = 'PERMITIDO' ''',
            (mark, actor, operation),
        ).fetchall()
        if sid is not None:
            rows = [row for row in rows if row['solicitud_id'] == sid]
        assert rows
        assert all(row['ocurrido_en'] for row in rows)

    def assert_modification(self, entity, uid, actor):
        rows = self.db.execute(
            "SELECT * FROM auditoria_modificacion WHERE entidad = %s AND clave->>'id' = %s AND actor_id = %s",
            (entity, str(uid), actor),
        ).fetchall()
        assert rows
        assert all(row['ocurrido_en'] and row['operacion'] for row in rows)


@pytest.fixture
def qa(monkeypatch):
    assert os.environ.get('ADMIN_API_TOKEN'), 'Falta ADMIN_API_TOKEN en el entorno de pruebas'
    assert os.environ.get('DATABASE_URL'), 'Falta DATABASE_URL en el entorno de pruebas'
    # Los históricos son inmutables; cada prueba conserva únicamente datos UUID propios.
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as db:
        with TestClient(app) as client:
            yield Escenario(db, client, monkeypatch)


def portal_payload(qa, tipo):
    # Contrato del portal, independiente del esquema generado por la implementación.
    return '/api/solicitudes', {
        'tipo_ausencia_id': tipo['id'], 'origen': 'PORTAL',
        'fecha_inicio': '2040-06-01', 'fecha_fin': '2040-06-01',
        'hora_inicio': '09:00:00', 'hora_fin': '10:00:00',
        'motivo': 'Motivo portal ' + uuid4().hex,
    }


def portal_get(qa, sid, historial=False):
    path = f'/api/solicitudes/{sid}'
    if historial:
        path += '/historial'
    return qa.request('GET', path)


def test_health_y_catalogo_no_publico():
    with TestClient(app) as client:
        assert ok(client.get('/api/health')) == {'estado': 'ok'}
        assert client.get('/api/tipos-ausencia').status_code in {401, 403, 404}


@pytest.mark.parametrize('method,path,body,params', [
    ('GET', CATALOGO, None, {}),
    ('GET', CATALOGO + '/1', None, {}),
    ('POST', CATALOGO, {'nombre': 'QA-' + uuid4().hex, 'flujo_codigo': 'JEFE'}, {}),
    ('PUT', CATALOGO + '/1', {'nombre': 'QA-' + uuid4().hex, 'flujo_codigo': 'JEFE', 'version_esperada': 1}, {}),
    ('PUT', CATALOGO + '/1/flujo', {'flujo_codigo': 'JEFE', 'version_esperada': 1}, {}),
    ('DELETE', CATALOGO + '/1', None, {'version_esperada': 1}),
    ('GET', '/api/admin/flujos-aprobacion', None, {}),
    ('GET', '/api/admin/revisiones/pendientes', None, {}),
    ('GET', '/api/admin/solicitudes/1', None, {}),
    ('GET', '/api/admin/solicitudes/1/historial', None, {}),
    ('POST', '/api/admin/revisiones/1/decision', {'decision': 'APROBAR', 'version_solicitud_esperada': 1, 'version_revision_esperada': 1}, {}),
    ('GET', '/api/admin/notificaciones', None, {}),
])
def test_todas_las_operaciones_admin_sin_token(method, path, body, params):
    with TestClient(app) as client:
        response = client.request(method, path, json=body, params=params)
        assert response.status_code in {401, 403}, response.text


def test_todas_las_rutas_admin_declaradas_estan_protegidas():
    with TestClient(app) as client:
        for path, operations in app.openapi()['paths'].items():
            if not path.startswith('/api/admin/'):
                continue
            concrete = path
            for parameter in path.split('{')[1:]:
                concrete = concrete.replace('{' + parameter.split('}')[0] + '}', '1')
            for method in operations.keys() & {'get', 'post', 'put', 'patch', 'delete'}:
                response = client.request(method, concrete, json={}, params={'version_esperada': 1})
                assert response.status_code in {401, 403}, (method, path, response.text)


def test_hu_001_ca_01_registro_para_revision_y_validacion(qa):
    tipo = qa.tipo()
    path, payload = portal_payload(qa, tipo)
    created = ok(qa.request('POST', path, json=payload), 201)
    assert isinstance(created.get('id'), int)
    assert created['estado_codigo'] == 'EN_REVISION' and created['version'] > 0
    row = qa.db.execute('SELECT * FROM solicitudes WHERE id = %s', (created['id'],)).fetchone()
    assert row['solicitante_id'] == qa.empleado
    assert row['tipo_ausencia_id'] == tipo['id']
    assert row['flujo_id'] == tipo['flujo_id']
    assert row['estado_codigo'] == 'EN_REVISION'
    validation(qa.request('POST', path, json={}), 'tipo_ausencia_id')
    assert qa.client.post(path, json=payload).status_code in {401, 403}


def test_hu_001_ca_02_motivo_obligatorio_centralizado(qa):
    tipo = qa.tipo(requiere_motivo=True)
    path, payload = portal_payload(qa, tipo)
    created = ok(qa.request('POST', path, json=payload), 201)
    row = qa.db.execute('SELECT motivo FROM solicitudes WHERE id = %s', (created['id'],)).fetchone()
    assert row['motivo'] == payload['motivo']
    for invalid in [None, '', '   ']:
        validation(qa.request('POST', path, json={**payload, 'motivo': invalid}))


def test_hu_001_ca_03_fechas_horas_tipo_y_limites(qa):
    tipo = qa.tipo()
    path, payload = portal_payload(qa, tipo)
    created = ok(qa.request('POST', path, json=payload), 201)
    row = qa.db.execute('SELECT * FROM solicitudes WHERE id = %s', (created['id'],)).fetchone()
    assert row['fecha_inicio'] == row['fecha_fin'] == date(2040, 6, 1)
    assert row['hora_inicio'] == time(9) and row['hora_fin'] == time(10)
    for change in [{'fecha_fin': '2040-05-31'}, {'hora_fin': None}, {'hora_fin': '09:00:00'}, {'fecha_inicio': 'no-fecha'}]:
        validation(qa.request('POST', path, json={**payload, **change}))
    tipo_sin_horas = qa.tipo(permite_horas=False)
    validation(qa.request('POST', path, json={**payload, 'tipo_ausencia_id': tipo_sin_horas['id']}))
    tipo_inactivo = qa.tipo(estado='Inactivo')
    validation(qa.request('POST', path, json={**payload, 'tipo_ausencia_id': tipo_inactivo['id']}))


def test_hu_001_ca_04_seguimiento_historial_auditado_y_aislamiento(qa):
    item = qa.solicitud()
    ok(qa.decision(item))
    sid = item['solicitud']['id']
    mark = qa.access_mark()
    detail = ok(portal_get(qa, sid))
    assert detail['id'] == sid and detail['estado_codigo'] == 'APROBADA'
    history = ok(portal_get(qa, sid, historial=True))
    assert history and [event['version'] for event in history] == sorted(event['version'] for event in history)
    assert all(event['actor_id'] and event['actor'] and event['ocurrido_en'] for event in history)
    assert any(event['estado_nuevo'] == 'APROBADA' for event in history)
    qa.assert_access(mark, qa.empleado, 'CONSULTA_SOLICITUD', sid)
    qa.assert_access(mark, qa.empleado, 'CONSULTA_HISTORIAL', sid)
    other = qa.solicitud(owner=qa.empleado_otro, approver=qa.otro)
    assert portal_get(qa, other['solicitud']['id']).status_code in {403, 404}
    assert portal_get(qa, other['solicitud']['id'], historial=True).status_code in {403, 404}


@pytest.mark.parametrize('decision,state', [('APROBAR', 'APROBADA'), ('RECHAZAR', 'RECHAZADA')])
def test_hu_002_ca_01_notificacion_empleado_sin_duplicados(qa, decision, state):
    item = qa.solicitud()
    result = ok(qa.decision(item, decision))
    assert result['solicitud']['estado_codigo'] == state
    notifications = qa.db.execute(
        "SELECT * FROM notificaciones WHERE solicitud_id = %s AND tipo = 'CAMBIO_ESTADO' AND destinatario_id = %s",
        (item['solicitud']['id'], qa.empleado),
    ).fetchall()
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification['asunto'] and notification['mensaje'] and notification['creada_en']
    history = qa.db.execute('SELECT * FROM historial_solicitud WHERE id = %s', (notification['historial_id'],)).fetchone()
    assert history['estado_nuevo'] == state
    assert qa.decision(item, decision).status_code == 409
    count = qa.db.execute('SELECT count(*) AS n FROM notificaciones WHERE historial_id = %s', (history['id'],)).fetchone()['n']
    assert count == 1


def test_hu_002_ca_02_notificar_siguiente_aprobador_y_aislar(qa):
    item = qa.solicitud('JEFE_TH')
    validation(qa.decision(item, siguiente_aprobador_id=qa.empleado))
    validation(qa.decision(item))
    result = ok(qa.decision(item, siguiente_aprobador_id=qa.th))
    next_review = result['siguiente_revision']
    assert next_review['aprobador_id'] == qa.th
    qa.as_actor(qa.th)
    own = ok(qa.request('GET', '/api/admin/notificaciones', params={'limite': 200}))
    matching = [notice for notice in own if notice['revision_id'] == next_review['id']]
    assert len(matching) == 1 and matching[0]['tipo'] == 'PENDIENTE_REVISION'
    assert matching[0]['creada_en'] and matching[0]['estado_envio']
    qa.as_actor(qa.otro)
    others = ok(qa.request('GET', '/api/admin/notificaciones', params={'limite': 200}))
    assert matching[0]['id'] not in {notice['id'] for notice in others}


def test_hu_003_ca_01_bandeja_campos_pa_003_y_asignaciones(qa):
    own = qa.solicitud()
    foreign = qa.solicitud(owner=qa.empleado_otro, approver=qa.otro)
    qa.as_actor(qa.jefe)
    rows = ok(qa.request('GET', '/api/admin/revisiones/pendientes', params={'limite': 200}))
    assert all(row['aprobador_id'] == qa.jefe for row in rows)
    assert foreign['revision']['id'] not in {row['revision_id'] for row in rows}
    row = next(row for row in rows if row['revision_id'] == own['revision']['id'])
    assert {'solicitante', 'area', 'tipo_ausencia', 'fecha_inicio', 'fecha_fin', 'hora_inicio',
            'hora_fin', 'observacion_empleado', 'revision_id', 'rol_codigo',
            'version_revision', 'version_solicitud'} <= row.keys()
    assert row['solicitante'] and row['area'] and row['tipo_ausencia']
    assert row['observacion_empleado'] == own['solicitud']['motivo']
    validation(qa.request('GET', '/api/admin/revisiones/pendientes', params={'limite': 0}), 'limite')


@pytest.mark.parametrize('decision,state', [('APROBAR', 'APROBADA'), ('RECHAZAR', 'RECHAZADA')])
def test_hu_003_ca_02_decisiones_estado_version_y_actor(qa, decision, state):
    item = qa.solicitud()
    validation(qa.decision(item, decision='INVALIDA'), 'decision')
    assert qa.decision(item, version_solicitud_esperada=item['solicitud']['version'] + 1).status_code == 409
    result = ok(qa.decision(item, decision))
    assert result['decision']['decision'] == decision
    assert result['decision']['actor_id'] == qa.jefe and result['decision']['decidida_en']
    assert result['solicitud']['estado_codigo'] == state
    assert result['solicitud']['version'] == item['solicitud']['version'] + 1
    assert result['revision']['estado'] == 'COMPLETADA'
    assert result['revision']['version'] == item['revision']['version'] + 1
    assert qa.decision(item, decision).status_code == 409
    not_ready = qa.solicitud(revisar=False)
    assert qa.decision(not_ready).status_code == 409


@pytest.mark.parametrize('decision,clase', [('APROBAR', 'APROBACION'), ('RECHAZAR', 'RECHAZO')])
def test_hu_003_ca_03_observaciones_y_rechazo_obligatorio(qa, decision, clase):
    item = qa.solicitud()
    for invalid in ['', '   ', 'x' * 5001]:
        validation(qa.decision(item, decision, observacion=invalid))
    if decision == 'RECHAZAR':
        validation(qa.decision(item, decision, observacion=None))
    text = 'Observación ' + uuid4().hex
    result = ok(qa.decision(item, decision, observacion=text))
    rows = qa.db.execute('SELECT * FROM observaciones WHERE aprobacion_id = %s', (result['decision']['id'],)).fetchall()
    assert len(rows) == 1
    assert rows[0]['contenido'] == text and rows[0]['clase'] == clase
    assert rows[0]['actor_id'] == qa.jefe


def assert_review_audit(qa, item, decision):
    actor = item['actor']
    sid = item['solicitud']['id']
    qa.as_actor(actor)
    mark = qa.access_mark()
    detail = ok(qa.request('GET', f'/api/admin/solicitudes/{sid}'))
    assert detail['id'] == sid and detail['revisiones']
    history = ok(qa.request('GET', f'/api/admin/solicitudes/{sid}/historial'))
    assert history and all(event['actor_id'] and event['actor'] and event['ocurrido_en'] for event in history)
    assert [event['version'] for event in history] == sorted(event['version'] for event in history)
    result = ok(qa.decision(item, decision))
    qa.assert_access(mark, actor, 'CONSULTA_SOLICITUD', sid)
    qa.assert_access(mark, actor, 'CONSULTA_HISTORIAL', sid)
    qa.assert_access(mark, actor, 'ACCION_SENSIBLE', sid)
    qa.assert_modification('aprobaciones', result['decision']['id'], actor)
    qa.assert_modification('solicitudes', sid, actor)
    qa.as_actor(qa.otro)
    for path in [f'/api/admin/solicitudes/{sid}', f'/api/admin/solicitudes/{sid}/historial']:
        assert qa.request('GET', path).status_code == 404
    payload = {'decision': 'APROBAR', 'version_solicitud_esperada': result['solicitud']['version'],
               'version_revision_esperada': result['revision']['version']}
    assert qa.request('POST', f"/api/admin/revisiones/{item['revision']['id']}/decision", json=payload).status_code in {403, 404}


def test_hu_003_ca_04_trazabilidad_y_acceso_no_asignado(qa):
    assert_review_audit(qa, qa.solicitud(), 'APROBAR')


def test_hu_004_ca_01_validacion_th_y_orden_del_flujo(qa):
    item = qa.solicitud('TH')
    validation(qa.decision(item, 'APROBAR'))
    result = ok(qa.decision(item, 'VALIDAR_Y_APROBAR'))
    assert result['solicitud']['estado_codigo'] == 'APROBADA'
    assert result['decision']['actor_id'] == qa.th
    jefe = qa.solicitud()
    validation(qa.decision(jefe, 'VALIDAR_Y_APROBAR'))
    staged = qa.solicitud('JEFE_TH')
    etapa = qa.db.execute("SELECT * FROM etapas_flujo WHERE flujo_id = %s AND rol_codigo = 'talento_humano'", (staged['tipo']['flujo_id'],)).fetchone()
    with qa.db.transaction():
        qa.db.execute("SELECT set_config('app.usuario_id', %s, true)", (str(qa.admin),))
        revision = qa.db.execute(
            '''INSERT INTO revisiones (solicitud_id, flujo_id, etapa_id, rol_codigo, aprobador_id)
               VALUES (%s, %s, %s, 'talento_humano', %s) RETURNING *''',
            (staged['solicitud']['id'], staged['tipo']['flujo_id'], etapa['id'], qa.th),
        ).fetchone()
    early = {**staged, 'revision': revision, 'actor': qa.th}
    assert qa.decision(early, 'VALIDAR_Y_APROBAR').status_code == 409
    first = ok(qa.decision(staged))
    early['solicitud'] = first['solicitud']
    assert ok(qa.decision(early, 'VALIDAR_Y_APROBAR'))['solicitud']['estado_codigo'] == 'APROBADA'


@pytest.mark.parametrize('decision,clase', [('VALIDAR_Y_APROBAR', 'VALIDACION'), ('RECHAZAR', 'RECHAZO')])
def test_hu_004_ca_02_observaciones_th(qa, decision, clase):
    item = qa.solicitud('TH')
    validation(qa.decision(item, decision, observacion='x' * 5001), 'observacion')
    if decision == 'RECHAZAR':
        validation(qa.decision(item, decision, observacion=None))
    text = 'Validación ' + uuid4().hex
    result = ok(qa.decision(item, decision, observacion=text))
    qa.as_actor(qa.th)
    detail = ok(qa.request('GET', f"/api/admin/solicitudes/{item['solicitud']['id']}"))
    assert any(row['contenido'] == text and row['clase'] == clase and row['actor_id'] == qa.th for row in detail['observaciones'])
    qa.assert_modification('aprobaciones', result['decision']['id'], qa.th)


def test_hu_004_ca_03_trazabilidad_th_y_aislamiento(qa):
    assert_review_audit(qa, qa.solicitud('TH'), 'VALIDAR_Y_APROBAR')


def test_hu_005_ca_01_catalogo_crud_duplicados_referencias_y_auditoria(qa):
    mark = qa.access_mark()
    tipo = qa.tipo()
    qa.assert_modification('tipos_ausencia', tipo['id'], qa.admin)
    detail = ok(qa.request('GET', f"{CATALOGO}/{tipo['id']}"))
    assert detail['nombre'] == tipo['nombre'] and detail['version'] == tipo['version']
    assert isinstance(ok(qa.request('GET', CATALOGO)), list)
    qa.assert_access(mark, qa.admin, 'CONSULTA_CATALOGO')
    # No existe una regla de unicidad del nombre del catálogo.
    duplicate = {'nombre': tipo['nombre'].upper(), 'flujo_codigo': 'JEFE'}
    duplicated = ok(qa.request('POST', CATALOGO, json=duplicate), 201)
    assert duplicated['id'] != tipo['id']
    assert duplicated['nombre'] == duplicate['nombre']
    update = {'nombre': 'QA-' + uuid4().hex, 'estado': 'Inactivo', 'requiere_motivo': False,
              'permite_horas': False, 'flujo_codigo': 'TH', 'version_esperada': tipo['version']}
    updated = ok(qa.request('PUT', f"{CATALOGO}/{tipo['id']}", json=update))
    assert updated['estado'] == 'Inactivo' and updated['version'] == tipo['version'] + 1
    assert not updated['requiere_motivo'] and not updated['permite_horas']
    assert qa.request('PUT', f"{CATALOGO}/{tipo['id']}", json=update).status_code == 409
    assert qa.request('DELETE', f"{CATALOGO}/{tipo['id']}", params={'version_esperada': tipo['version']}).status_code == 409
    deleted = ok(qa.request('DELETE', f"{CATALOGO}/{tipo['id']}", params={'version_esperada': updated['version']}))
    assert deleted == {'estado': 'eliminado', 'id': tipo['id']}
    assert qa.request('GET', f"{CATALOGO}/{tipo['id']}").status_code == 404
    referenced = qa.solicitud()
    tipo = referenced['tipo']
    assert qa.request('DELETE', f"{CATALOGO}/{tipo['id']}", params={'version_esperada': tipo['version']}).status_code == 409
    qa.as_actor(qa.jefe)
    assert qa.request('GET', CATALOGO).status_code == 403
    assert qa.request('POST', CATALOGO, json={'nombre': 'QA-' + uuid4().hex, 'flujo_codigo': 'JEFE'}).status_code == 403


@pytest.mark.parametrize('field,value', [('nombre', ''), ('nombre', '   '), ('nombre', 'x' * 201),
                                         ('estado', 'Desconocido'), ('flujo_codigo', 'INVALIDO')])
def test_hu_005_ca_01_validacion_catalogo(qa, field, value):
    payload = {'nombre': 'QA-' + uuid4().hex, 'flujo_codigo': 'JEFE', field: value}
    validation(qa.request('POST', CATALOGO, json=payload), field)
    tipo = qa.tipo()
    validation(qa.request('PUT', f"{CATALOGO}/{tipo['id']}", json={**payload, 'version_esperada': tipo['version']}), field)


def test_hu_005_ca_01_limite_nombre_version_borrado_y_duplicado_actualizacion(qa):
    tipo = qa.tipo(nombre='QA-' + uuid4().hex + 'x' * 165)
    assert len(tipo['nombre']) == 200
    otro = qa.tipo()
    updated = ok(qa.request('PUT', f"{CATALOGO}/{otro['id']}", json={'nombre': tipo['nombre'], 'flujo_codigo': 'JEFE', 'version_esperada': otro['version']}))
    assert updated['id'] == otro['id'] and updated['nombre'] == tipo['nombre']
    assert updated['version'] == otro['version'] + 1
    original = ok(qa.request('GET', f"{CATALOGO}/{tipo['id']}"))
    assert original['version'] == tipo['version'] and original['nombre'] == tipo['nombre']
    for value in [0, -1, '1', True]:
        validation(qa.request('PUT', f"{CATALOGO}/{tipo['id']}", json={'nombre': tipo['nombre'], 'flujo_codigo': 'JEFE', 'version_esperada': value}), 'version_esperada')
    validation(qa.request('DELETE', f"{CATALOGO}/{tipo['id']}"), 'version_esperada')
    validation(qa.request('DELETE', f"{CATALOGO}/{tipo['id']}", params={'version_esperada': 0}), 'version_esperada')


@pytest.mark.parametrize('flow', ['JEFE', 'JEFE_TH', 'TH'])
def test_hu_005_ca_02_asociacion_flujo_y_preservacion_configuracion(qa, flow):
    tipo = qa.tipo()
    flows = ok(qa.request('GET', '/api/admin/flujos-aprobacion'))
    selected = next(row for row in flows if row['codigo'] == flow)
    assert selected['etapas']
    assert [stage['orden'] for stage in selected['etapas']] == sorted(stage['orden'] for stage in selected['etapas'])
    assert all({'rol_codigo', 'requiere_validacion'} <= stage.keys() for stage in selected['etapas'])
    payload = {'flujo_codigo': flow, 'version_esperada': tipo['version']}
    updated = ok(qa.request('PUT', f"{CATALOGO}/{tipo['id']}/flujo", json=payload))
    assert updated['flujo_id'] == selected['id'] and updated['version'] == tipo['version'] + 1
    for field in ['nombre', 'estado', 'requiere_motivo', 'permite_horas']:
        assert updated[field] == tipo[field]
    assert qa.request('PUT', f"{CATALOGO}/{tipo['id']}/flujo", json=payload).status_code == 409
    validation(qa.request('PUT', f"{CATALOGO}/{tipo['id']}/flujo", json={'flujo_codigo': 'INVALIDO', 'version_esperada': updated['version']}), 'flujo_codigo')
    validation(qa.request('PUT', f"{CATALOGO}/{tipo['id']}/flujo", json={'flujo_codigo': flow, 'version_esperada': 0}), 'version_esperada')


def test_hu_005_ca_02_flujo_inactivo_rechazado(qa):
    tipo = qa.tipo('JEFE')
    flow = qa.db.execute("SELECT * FROM flujo_aprobacion WHERE codigo = 'TH'").fetchone()
    def set_active(value):
        with qa.db.transaction():
            qa.db.execute("SELECT set_config('app.usuario_id', %s, true)", (str(qa.admin),))
            qa.db.execute('UPDATE flujo_aprobacion SET activo = %s WHERE id = %s', (value, flow['id']))
    try:
        set_active(False)
        validation(qa.request('PUT', f"{CATALOGO}/{tipo['id']}/flujo", json={'flujo_codigo': 'TH', 'version_esperada': tipo['version']}))
        validation(qa.request('POST', CATALOGO, json={'nombre': 'QA-' + uuid4().hex, 'flujo_codigo': 'TH'}))
        current = ok(qa.request('GET', f"{CATALOGO}/{tipo['id']}"))
        assert current['version'] == tipo['version'] and current['flujo_id'] == tipo['flujo_id']
    finally:
        set_active(flow['activo'])


@pytest.mark.parametrize('path,criterion', [
    (CATALOGO, 'HU-005-CA-01'),
    ('/api/admin/revisiones/pendientes', 'HU-003-CA-01'),
    ('/api/admin/notificaciones', 'HU-002-CA-02'),
])
def test_paginacion_limites_y_validacion(qa, path, criterion):
    for limit in [1, 200]:
        rows = ok(qa.request('GET', path, params={'limite': limit, 'offset': 0}))
        assert isinstance(rows, list) and len(rows) <= limit
    for field, value in [('limite', 0), ('limite', 201), ('offset', -1)]:
        validation(qa.request('GET', path, params={field: value}), field)


def test_hu_003_ca_02_conflicto_concurrente_sin_doble_decision(qa):
    item = qa.solicitud()
    qa.as_actor(qa.jefe)
    path = f"/api/admin/revisiones/{item['revision']['id']}/decision"
    payload = {'decision': 'APROBAR', 'version_solicitud_esperada': item['solicitud']['version'],
               'version_revision_esperada': item['revision']['version']}
    def decide():
        with TestClient(app) as client:
            return client.post(path, headers=qa.headers, json=payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: decide(), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    rows = qa.db.execute('SELECT * FROM aprobaciones WHERE revision_id = %s', (item['revision']['id'],)).fetchall()
    assert len(rows) == 1
    current = qa.db.execute('SELECT * FROM solicitudes WHERE id = %s', (item['solicitud']['id'],)).fetchone()
    assert current['version'] == item['solicitud']['version'] + 1


@pytest.mark.parametrize('field,value', [('version_solicitud_esperada', 0), ('version_revision_esperada', 0),
                                         ('version_solicitud_esperada', '2'), ('siguiente_aprobador_id', 0)])
def test_hu_003_ca_02_validacion_versiones_y_identidades(qa, field, value):
    item = qa.solicitud()
    validation(qa.decision(item, **{field: value}), field)
    assert qa.db.execute('SELECT count(*) AS n FROM aprobaciones WHERE revision_id = %s', (item['revision']['id'],)).fetchone()['n'] == 0