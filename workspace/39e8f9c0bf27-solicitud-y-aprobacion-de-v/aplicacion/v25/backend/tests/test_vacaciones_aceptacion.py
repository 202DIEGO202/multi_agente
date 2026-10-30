import base64
import hashlib
import json
import math
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.main import app


def der(tag, value):
    length = len(value)
    size = length.to_bytes(max(1, (length.bit_length() + 7) // 8), 'big')
    return bytes([tag]) + (bytes([length]) if length < 128 else bytes([128 + len(size)]) + size) + value


def der_integer(value):
    encoded = value.to_bytes((value.bit_length() + 7) // 8, 'big')
    if encoded[0] & 128:
        encoded = b'\x00' + encoded
    return der(2, encoded)


def prime():
    # Claves efímeras de prueba, sin dependencias criptográficas adicionales.
    while True:
        candidate = secrets.randbits(1024) | (1 << 1023) | 1
        if any(candidate % divisor == 0 for divisor in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)):
            continue
        odd = candidate - 1
        power = 0
        while odd % 2 == 0:
            odd //= 2
            power += 1
        for _ in range(40):
            witness = pow(secrets.randbelow(candidate - 3) + 2, odd, candidate)
            if witness in (1, candidate - 1):
                continue
            for _ in range(power - 1):
                witness = pow(witness, 2, candidate)
                if witness == candidate - 1:
                    break
            else:
                break
        else:
            return candidate


@pytest.fixture(scope='session')
def signing_material():
    exponent = 65537
    while True:
        p, q = prime(), prime()
        modulus = p * q
        phi = (p - 1) * (q - 1)
        if p != q and modulus.bit_length() == 2048 and math.gcd(exponent, phi) == 1:
            break
    private = pow(exponent, -1, phi)
    rsa_public = der(48, der_integer(modulus) + der_integer(exponent))
    algorithm = der(48, bytes.fromhex('06092a864886f70d0101010500'))
    public = base64.b64encode(der(48, algorithm + der(3, b'\x00' + rsa_public))).decode()
    pem = '-----BEGIN PUBLIC KEY-----\n' + '\n'.join(public[i:i + 64] for i in range(0, len(public), 64)) + '\n-----END PUBLIC KEY-----\n'
    return modulus, private, pem


def encode_identity(subject):
    def segment(value):
        return base64.urlsafe_b64encode(value).rstrip(b'=')

    now = int(time.time())
    claims = {'sub': subject, 'iat': now, 'exp': now + 3600,
              'iss': os.environ['IDENTITY_JWT_ISSUER'],
              'aud': os.environ['IDENTITY_JWT_AUDIENCE']}
    message = segment(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode()) + b'.' + segment(json.dumps(claims).encode())
    material = json.loads(os.environ['QA_SIGNING_MATERIAL'])
    digest = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(message).digest()
    size = (material['n'].bit_length() + 7) // 8
    encoded = b'\x00\x01' + b'\xff' * (size - len(digest) - 3) + b'\x00' + digest
    signature = pow(int.from_bytes(encoded, 'big'), material['d'], material['n']).to_bytes(size, 'big')
    return (message + b'.' + segment(signature)).decode()


@pytest.fixture
def db():
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as connection:
        yield connection


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance


@pytest.fixture
def entorno(db, monkeypatch, signing_material):
    # Identidades locales; se conserva la auditoría inmutable de cada ejecución.
    assert os.environ['ADMIN_API_TOKEN'], 'ADMIN_API_TOKEN debe estar configurado'
    modulus, private, public = signing_material
    monkeypatch.setenv('QA_SIGNING_MATERIAL', json.dumps({'n': modulus, 'd': private}))
    monkeypatch.setenv('IDENTITY_JWT_PUBLIC_KEY', public)
    monkeypatch.setenv('IDENTITY_JWT_ISSUER', 'pytest-' + uuid4().hex)
    monkeypatch.setenv('IDENTITY_JWT_AUDIENCE', 'pytest-' + uuid4().hex)

    def usuario(roles, jefe=None, actor=None):
        unique = uuid4().hex
        identifier = db.execute(
            "SELECT nextval(pg_get_serial_sequence('usuarios', 'id')) AS id"
        ).fetchone()['id']
        with db.transaction():
            db.execute("SELECT set_config('app.usuario_id', %s, true)",
                       (str(actor or identifier),))
            row = db.execute(
                'INSERT INTO usuarios (id, identidad_externa, nombre, documento, correo, '
                'area, cargo, jefe_inmediato_id) OVERRIDING SYSTEM VALUE '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                (identifier, unique, 'Prueba ' + unique, unique,
                 unique + '@example.invalid', 'QA', 'QA', jefe),
            ).fetchone()
            for role in roles:
                db.execute('INSERT INTO usuario_roles (usuario_id, rol_codigo) VALUES (%s,%s)',
                           (identifier, role))
        identity = encode_identity(unique)
        row['portal'] = {'Authorization': 'Bearer ' + identity}
        row['admin'] = {
            'Authorization': 'Bearer ' + os.environ['ADMIN_API_TOKEN'],
            'X-Identity-Token': 'Bearer ' + identity,
        }
        return row

    hr = usuario(['EMPLEADO', 'TALENTO_HUMANO'])
    boss = usuario(['EMPLEADO', 'JEFE_INMEDIATO'], actor=hr['id'])
    other_boss = usuario(['EMPLEADO', 'JEFE_INMEDIATO'], actor=hr['id'])
    employee = usuario(['EMPLEADO'], jefe=boss['id'], actor=hr['id'])
    other = usuario(['EMPLEADO'], jefe=other_boss['id'], actor=hr['id'])
    monkeypatch.setenv('TALENTO_HUMANO_ID', str(hr['id']))
    return {'hr': hr, 'boss': boss, 'other_boss': other_boss,
            'employee': employee, 'other': other}


def respuesta(response, status):
    assert response.status_code == status, response.text
    return response.json()


def invalido(response, field=None, model=False):
    assert response.status_code == 422, response.text
    detail = response.json()['detail']
    # Errores de esquema y reglas de servicio pueden tener envolturas diferentes.
    if isinstance(detail, list):
        assert detail
        assert all(isinstance(error.get('type'), str) and error['type'] for error in detail)
        assert all(isinstance(error.get('loc'), list) for error in detail)
        if field:
            assert any(field in error['loc'] or (model and error['loc'] == ['body'])
                       for error in detail), detail
    else:
        assert isinstance(detail, str) and detail.strip()


def tipo(client, entorno, **changes):
    body = {'nombre': 'QA-' + uuid4().hex, 'estado': 'ACTIVO',
            'flujo_codigo': 'JEFE_INMEDIATO', 'requiere_motivo': False,
            'modalidad_horas': 'OPCIONAL'}
    body.update(changes)
    result = respuesta(client.post('/api/admin/tipos-ausencia',
                                   headers=entorno['hr']['admin'], json=body), 201)
    for field, value in body.items():
        assert result[field] == value
    return result, body


def datos_solicitud(absence_type, **changes):
    body = {'tipo_ausencia_id': absence_type['id'], 'fecha_inicio': '2035-06-10',
            'fecha_fin': '2035-06-10', 'motivo': 'Motivo ' + uuid4().hex}
    body.update(changes)
    return body


def crear(client, entorno, absence_type=None, actor='employee', **changes):
    if absence_type is None:
        absence_type, _ = tipo(client, entorno)
    body = datos_solicitud(absence_type, **changes)
    row = respuesta(client.post('/api/solicitudes', headers=entorno[actor]['portal'],
                               json=body), 201)
    assert row['solicitante_id'] == entorno[actor]['id']
    assert row['estado_codigo'] == 'EN_REVISION'
    assert row['version'] > 0
    return row, body


def detalle(client, entorno, row, actor='boss'):
    return respuesta(client.get('/api/admin/solicitudes/' + str(row['id']),
                               headers=entorno[actor]['admin']), 200)


def decision_body(detail, accion, observacion=None, rol=None):
    revisions = [r for r in detail['revisiones']
                 if r['estado'] == 'PENDIENTE' and (rol is None or r['rol_codigo'] == rol)]
    assert len(revisions) == 1
    body = {'revision_id': revisions[0]['id'], 'version_esperada': detail['version'],
            'accion': accion}
    if observacion is not None:
        body['observacion'] = observacion
    return body


def decidir(client, entorno, row, accion, actor='boss', observacion=None):
    detail = detalle(client, entorno, row, actor)
    body = decision_body(detail, accion, observacion)
    response = client.post('/api/admin/solicitudes/' + str(row['id']) + '/decisiones',
                           headers=entorno[actor]['admin'], json=body)
    return response, body


def pagina_completa(client, path, headers, **params):
    items = []
    offset = 0
    while True:
        page = respuesta(client.get(path, headers=headers,
                                   params={**params, 'limite': 100, 'desplazamiento': offset}), 200)
        assert page['limite'] == 100 and page['desplazamiento'] == offset
        assert len(page['items']) <= 100
        items.extend(page['items'])
        if len(page['items']) < 100:
            return items
        offset += 100


def auditar_acceso(db, response, actor, operation=None, solicitud=None, autorizado=True):
    rows = db.execute(
        'SELECT * FROM auditoria_acceso WHERE identificador_peticion=%s AND actor_id=%s '
        'AND autorizado=%s',
        (response.headers['X-Request-ID'], actor['id'], autorizado),
    ).fetchall()
    if operation:
        rows = [r for r in rows if r['operacion'] == operation]
    if solicitud is not None:
        rows = [r for r in rows if r['solicitud_id'] == solicitud]
    assert rows
    assert all(r['ocurrido_en'] and r['operacion'] for r in rows)


def auditar_modificacion(db, actor, entity, identifier, operation):
    rows = db.execute(
        "SELECT * FROM auditoria_modificacion WHERE actor_id=%s AND entidad=%s "
        "AND entidad_clave->>'id'=%s AND operacion=%s",
        (actor['id'], entity, str(identifier), operation),
    ).fetchall()
    assert rows
    assert all(r['ocurrido_en'] for r in rows)
    if operation != 'DELETE':
        assert all(r['datos_nuevos']['id'] == identifier for r in rows)
    if operation != 'INSERT':
        assert all(r['datos_anteriores']['id'] == identifier for r in rows)


def sin_creacion(db, actor, body, response, field=None, model=False):
    before = db.execute('SELECT count(*) AS n FROM solicitudes WHERE solicitante_id=%s',
                        (actor['id'],)).fetchone()['n']
    invalido(response, field, model)
    after = db.execute('SELECT count(*) AS n FROM solicitudes WHERE solicitante_id=%s',
                       (actor['id'],)).fetchone()['n']
    assert before == after
    if isinstance(body.get('tipo_ausencia_id'), int) and body['tipo_ausencia_id'] > 0:
        assert not db.execute(
            'SELECT id FROM solicitudes WHERE solicitante_id=%s AND tipo_ausencia_id=%s',
            (actor['id'], body['tipo_ausencia_id']),
        ).fetchone()


def test_hu_001_ca_01_health(client):
    assert respuesta(client.get('/api/health'), 200) == {'estado': 'ok'}


ADMIN_ROUTES = [
    ('GET', '/api/admin/'),
    ('GET', '/api/admin/solicitudes'),
    ('GET', '/api/admin/solicitudes/1'),
    ('GET', '/api/admin/solicitudes/1/historial'),
    ('POST', '/api/admin/solicitudes/1/decisiones'),
    ('GET', '/api/admin/tipos-ausencia'),
    ('GET', '/api/admin/tipos-ausencia/1'),
    ('POST', '/api/admin/tipos-ausencia'),
    ('PUT', '/api/admin/tipos-ausencia/1'),
    ('PUT', '/api/admin/tipos-ausencia/1/flujo'),
    ('DELETE', '/api/admin/tipos-ausencia/1'),
]


@pytest.mark.parametrize('method,path', ADMIN_ROUTES)
def test_hu_005_ca_01_todas_rutas_admin_sin_token(client, method, path):
    response = client.request(method, path)
    assert response.status_code in (401, 403), response.text


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/empleado/tipos-ausencia'),
    ('POST', '/api/solicitudes'),
    ('GET', '/api/empleado/solicitudes'), ('GET', '/api/empleado/solicitudes/1'),
    ('GET', '/api/empleado/solicitudes/1/historial'), ('GET', '/api/notificaciones'),
    ('PATCH', '/api/notificaciones/1/leida'),
])
def test_hu_001_ca_04_portal_requiere_identidad(client, method, path):
    assert client.request(method, path).status_code == 401


def test_hu_001_ca_03_catalogo_interno_sin_configuracion_administrativa(client, entorno, db):
    active, _ = tipo(client, entorno)
    inactive, _ = tipo(client, entorno, estado='INACTIVO')
    headers = entorno['employee']['portal']
    items = pagina_completa(client, '/api/empleado/tipos-ausencia', headers)
    assert active['id'] in {item['id'] for item in items}
    assert inactive['id'] not in {item['id'] for item in items}
    assert all(set(item) == {'id', 'nombre', 'requiere_motivo', 'modalidad_horas'} for item in items)
    response = client.get('/api/empleado/tipos-ausencia', headers=headers)
    respuesta(response, 200)
    auditar_acceso(db, response, entorno['employee'], 'CONSULTAR_CATALOGO')
    administrative = respuesta(client.get('/api/admin/tipos-ausencia/' + str(active['id']),
                                         headers=entorno['hr']['admin']), 200)
    assert {'estado', 'flujo_codigo', 'flujo_id'} <= set(administrative)
    assert not {'estado', 'flujo_codigo', 'flujo_id'} & set(next(item for item in items if item['id'] == active['id']))
    invalido(client.get('/api/empleado/tipos-ausencia', headers=headers, params={'limite': 0}), 'limite')


@pytest.mark.parametrize('origen', ['PORTAL_INTERNO', 'FORMATO_OFICIAL'])
def test_hu_001_ca_01_registro_transaccional_y_duplicado(client, entorno, db, origen):
    absence_type, _ = tipo(client, entorno)
    extra = {'origen': origen}
    if origen == 'FORMATO_OFICIAL':
        extra['referencia_formato'] = uuid4().hex
    row, body = crear(client, entorno, absence_type, **extra)
    stored = db.execute('SELECT * FROM solicitudes WHERE id=%s', (row['id'],)).fetchone()
    assert stored['estado_codigo'] == 'EN_REVISION'
    assert stored['flujo_id'] == absence_type['flujo_id']
    assert stored['origen'] == origen
    assert stored['referencia_formato'] == body.get('referencia_formato')
    revisions = db.execute('SELECT * FROM revisiones WHERE solicitud_id=%s', (row['id'],)).fetchall()
    assert len(revisions) == 1
    assert revisions[0]['aprobador_id'] == entorno['boss']['id']
    assert revisions[0]['estado'] == 'PENDIENTE'
    history = db.execute('SELECT * FROM historial_solicitud WHERE solicitud_id=%s', (row['id'],)).fetchall()
    assert any(h['operacion'] == 'CREAR' for h in history)
    assert any(h['estado_nuevo'] == 'EN_REVISION' for h in history)
    auditar_modificacion(db, entorno['employee'], 'solicitudes', row['id'], 'INSERT')
    counts = db.execute(
        'SELECT (SELECT count(*) FROM solicitudes WHERE solicitante_id=%s) AS solicitudes, '
        '(SELECT count(*) FROM historial_solicitud WHERE solicitud_id=%s) AS historial, '
        '(SELECT count(*) FROM notificaciones WHERE solicitud_id=%s) AS notificaciones',
        (entorno['employee']['id'], row['id'], row['id']),
    ).fetchone()
    respuesta(client.post('/api/solicitudes', headers=entorno['employee']['portal'], json=body), 409)
    assert db.execute(
        'SELECT (SELECT count(*) FROM solicitudes WHERE solicitante_id=%s) AS solicitudes, '
        '(SELECT count(*) FROM historial_solicitud WHERE solicitud_id=%s) AS historial, '
        '(SELECT count(*) FROM notificaciones WHERE solicitud_id=%s) AS notificaciones',
        (entorno['employee']['id'], row['id'], row['id']),
    ).fetchone() == counts


@pytest.mark.parametrize('changes,field', [
    ({'origen': 'FORMATO_OFICIAL'}, 'referencia_formato'),
    ({'referencia_formato': 'Referencia indebida'}, 'referencia_formato'),
    ({'solicitante_id': 1}, 'solicitante_id'),
    ({'aprobadores': [1]}, 'aprobadores'),
    ({'tipo_ausencia_id': 0}, 'tipo_ausencia_id'),
    ({'origen': 'EXTERNO'}, 'origen'),
])
def test_hu_001_ca_01_validacion_origen_y_actor(client, entorno, db, changes, field):
    absence_type, _ = tipo(client, entorno)
    body = datos_solicitud(absence_type, **changes)
    response = client.post('/api/solicitudes', headers=entorno['employee']['portal'], json=body)
    sin_creacion(db, entorno['employee'], body, response, field, model=True)


@pytest.mark.parametrize('motivo', ['Motivo ' + uuid4().hex, 'M' * 4000])
def test_hu_001_ca_02_motivo_persistido(client, entorno, db, motivo):
    absence_type, _ = tipo(client, entorno, requiere_motivo=True)
    row, _ = crear(client, entorno, absence_type, motivo=motivo)
    assert row['motivo'] == motivo
    assert db.execute('SELECT motivo FROM solicitudes WHERE id=%s',
                      (row['id'],)).fetchone()['motivo'] == motivo


@pytest.mark.parametrize('motivo', [None, '', '   ', 'M' * 4001])
def test_hu_001_ca_02_motivo_obligatorio_validado_backend(client, entorno, db, motivo):
    absence_type, _ = tipo(client, entorno, requiere_motivo=True)
    body = datos_solicitud(absence_type, motivo=motivo)
    response = client.post('/api/solicitudes', headers=entorno['employee']['portal'], json=body)
    sin_creacion(db, entorno['employee'], body, response, 'motivo')


@pytest.mark.parametrize('modalidad,extra', [
    ('NO_APLICA', {}), ('OPCIONAL', {}),
    ('OPCIONAL', {'hora_inicio': '08:00:00', 'hora_fin': '08:01:00'}),
    ('OBLIGATORIA', {'hora_inicio': '08:00:00', 'hora_fin': '17:00:00'}),
    ('OBLIGATORIA', {'fecha_fin': '2035-06-11', 'hora_inicio': '23:00:00', 'hora_fin': '01:00:00'}),
])
def test_hu_001_ca_03_fechas_horas_y_tipo_guardados(client, entorno, db, modalidad, extra):
    absence_type, _ = tipo(client, entorno, modalidad_horas=modalidad)
    row, body = crear(client, entorno, absence_type, **extra)
    assert row['tipo_ausencia_id'] == absence_type['id']
    assert row['fecha_inicio'] == body['fecha_inicio']
    assert row['fecha_fin'] == body['fecha_fin']
    stored = db.execute('SELECT * FROM solicitudes WHERE id=%s', (row['id'],)).fetchone()
    assert stored['modalidad_horas'] == modalidad
    for field in ('hora_inicio', 'hora_fin'):
        assert (stored[field].isoformat() if stored[field] else None) == body.get(field)


@pytest.mark.parametrize('modalidad,changes,field', [
    ('OPCIONAL', {'fecha_fin': '2035-06-09'}, 'fecha_fin'),
    ('OPCIONAL', {'fecha_inicio': '2035-02-30'}, 'fecha_inicio'),
    ('OPCIONAL', {'hora_inicio': '08:00:00'}, 'hora_fin'),
    ('OPCIONAL', {'hora_inicio': '08:00:00', 'hora_fin': '08:00:00'}, 'hora_fin'),
    ('OPCIONAL', {'hora_inicio': '17:00:00', 'hora_fin': '08:00:00'}, 'hora_fin'),
    ('OPCIONAL', {'hora_inicio': '08:00:00Z', 'hora_fin': '09:00:00Z'}, 'hora_inicio'),
    ('OBLIGATORIA', {}, 'hora_inicio'),
    ('NO_APLICA', {'hora_inicio': '08:00:00', 'hora_fin': '09:00:00'}, 'hora_inicio'),
])
def test_hu_001_ca_03_periodos_y_modalidades_invalidos(client, entorno, db, modalidad, changes, field):
    absence_type, _ = tipo(client, entorno, modalidad_horas=modalidad)
    body = datos_solicitud(absence_type, **changes)
    response = client.post('/api/solicitudes', headers=entorno['employee']['portal'], json=body)
    sin_creacion(db, entorno['employee'], body, response, field, model=True)


def test_hu_001_ca_04_estado_historial_auditoria_y_aislamiento(client, entorno, db):
    row, _ = crear(client, entorno)
    foreign, _ = crear(client, entorno, actor='other')
    result, _ = decidir(client, entorno, row, 'APROBAR')
    respuesta(result, 200)
    headers = entorno['employee']['portal']
    base = '/api/empleado/solicitudes'
    listing = client.get(base, headers=headers)
    items = respuesta(listing, 200)['items']
    assert {r['id'] for r in items} == {row['id']}
    assert all(not {'solicitante_id', 'flujo_id', 'revisiones', 'aprobaciones', 'solicitante'} & set(item) for item in items)
    auditar_acceso(db, listing, entorno['employee'])
    response = client.get(base + '/' + str(row['id']), headers=headers)
    own = respuesta(response, 200)
    assert own['estado_codigo'] == 'APROBADA'
    assert not {'solicitante_id', 'flujo_id', 'revisiones', 'aprobaciones', 'solicitante'} & set(own)
    auditar_acceso(db, response, entorno['employee'], 'CONSULTAR_DETALLE', row['id'])
    response = client.get(base + '/' + str(row['id']) + '/historial', headers=headers)
    history = respuesta(response, 200)['items']
    assert any(h['estado_nuevo'] == 'APROBADA' for h in history)
    assert all(h['operacion'] and h['version'] > 0 and h['ocurrido_en'] for h in history)
    assert all(not {'actor_id', 'detalle', 'solicitud_id', 'datos_nuevos', 'datos_anteriores'} & set(h) for h in history)
    auditar_acceso(db, response, entorno['employee'], 'CONSULTAR_HISTORIAL', row['id'])
    for suffix, operation in [('', 'CONSULTAR_DETALLE'), ('/historial', 'CONSULTAR_HISTORIAL')]:
        denied = client.get(base + '/' + str(foreign['id']) + suffix, headers=headers)
        respuesta(denied, 403)
        auditar_acceso(db, denied, entorno['employee'], operation, foreign['id'], False)
    invalido(client.get(base, headers=headers, params={'estado': 'CANCELADA'}), 'estado')
    assert respuesta(client.get(base, headers=headers,
                               params={'estado': 'EN_REVISION'}), 200)['items'] == []


@pytest.mark.parametrize('accion,estado', [('APROBAR', 'APROBADA'), ('RECHAZAR', 'RECHAZADA')])
def test_hu_002_ca_01_aviso_nuevo_estado_lectura_y_aislamiento(client, entorno, db, accion, estado):
    row, _ = crear(client, entorno)
    response, _ = decidir(client, entorno, row, accion, observacion='Revisión ' + uuid4().hex)
    assert respuesta(response, 200)['estado_codigo'] == estado
    items = pagina_completa(client, '/api/notificaciones', entorno['employee']['portal'])
    notices = [n for n in items if n['solicitud_id'] == row['id'] and n['tipo'] == 'CAMBIO_ESTADO']
    assert notices
    terminal = db.execute(
        'SELECT n.* FROM notificaciones n JOIN historial_solicitud h ON h.id=n.historial_id '
        'WHERE n.solicitud_id=%s AND n.destinatario_id=%s AND h.estado_nuevo=%s',
        (row['id'], entorno['employee']['id'], estado),
    ).fetchall()
    assert len(terminal) == 1
    notice = next(n for n in notices if n['id'] == terminal[0]['id'])
    assert estado in notice['contenido']
    assert notice['asunto'] and notice['creado_en']
    path = '/api/notificaciones/' + str(notice['id']) + '/leida'
    first_response = client.patch(path, headers=entorno['employee']['portal'])
    first = respuesta(first_response, 200)
    assert first['id'] == notice['id'] and first['leida_en']
    auditar_acceso(db, first_response, entorno['employee'])
    assert respuesta(client.patch(path, headers=entorno['employee']['portal']), 200) == first
    respuesta(client.patch(path, headers=entorno['other']['portal']), 404)
    assert not any(n['solicitud_id'] == row['id'] for n in
                   pagina_completa(client, '/api/notificaciones', entorno['other']['portal']))
    invalido(client.patch('/api/notificaciones/0/leida', headers=entorno['employee']['portal']),
             'notificacion_id')


def test_hu_002_ca_02_notifica_solo_etapa_pendiente_y_aprobador(client, entorno, db):
    absence_type, _ = tipo(client, entorno, flujo_codigo='JEFE_Y_TALENTO_HUMANO')
    row, _ = crear(client, entorno, absence_type)
    revisions = detalle(client, entorno, row)['revisiones']
    hr_revision = next(r for r in revisions if r['rol_codigo'] == 'TALENTO_HUMANO')
    assert hr_revision['estado'] == 'EN_ESPERA'
    boss_notices = pagina_completa(client, '/api/notificaciones', entorno['boss']['portal'])
    assert len([n for n in boss_notices if n['solicitud_id'] == row['id']
                and n['tipo'] == 'REVISION_PENDIENTE']) == 1
    assert not db.execute('SELECT id FROM notificaciones WHERE revision_id=%s',
                          (hr_revision['id'],)).fetchone()
    response, _ = decidir(client, entorno, row, 'APROBAR')
    assert respuesta(response, 200)['estado_codigo'] == 'EN_REVISION'
    hr_notices = pagina_completa(client, '/api/notificaciones', entorno['hr']['portal'])
    assert len([n for n in hr_notices if n['solicitud_id'] == row['id']
                and n['tipo'] == 'REVISION_PENDIENTE']) == 1
    stored = db.execute('SELECT * FROM notificaciones WHERE revision_id=%s',
                        (hr_revision['id'],)).fetchall()
    assert len(stored) == 1 and stored[0]['destinatario_id'] == entorno['hr']['id']
    assert not any(n['solicitud_id'] == row['id'] for n in
                   pagina_completa(client, '/api/notificaciones', entorno['other_boss']['portal']))
    invalido(client.get('/api/notificaciones', headers=entorno['boss']['portal'],
                       params={'limite': 0}), 'limite')


def test_hu_003_ca_01_bandeja_pendientes_asignados(client, entorno, db):
    row, _ = crear(client, entorno)
    foreign, _ = crear(client, entorno, actor='other')
    path = '/api/admin/solicitudes'
    items = pagina_completa(client, path, entorno['boss']['admin'])
    assert row['id'] in {r['id'] for r in items}
    assert foreign['id'] not in {r['id'] for r in items}
    alias = client.get('/api/admin/', headers=entorno['boss']['admin'])
    assert {r['id'] for r in respuesta(alias, 200)['items']} == {r['id'] for r in items}
    auditar_acceso(db, alias, entorno['boss'], 'CONSULTAR_BANDEJA')
    invalido(client.get('/api/admin/', headers=entorno['boss']['admin'],
                       params={'limite': 0}), 'limite')
    response = client.get(path, headers=entorno['boss']['admin'])
    auditar_acceso(db, response, entorno['boss'], 'CONSULTAR_BANDEJA')
    response, _ = decidir(client, entorno, row, 'APROBAR')
    respuesta(response, 200)
    assert row['id'] not in {r['id'] for r in pagina_completa(client, path, entorno['boss']['admin'])}
    assert row['id'] in {r['id'] for r in pagina_completa(
        client, path, entorno['boss']['admin'], pendientes='false', estado='APROBADA')}
    invalido(client.get(path, headers=entorno['boss']['admin'],
                       params={'estado': 'CANCELADA'}), 'estado')


@pytest.mark.parametrize('accion,estado', [('APROBAR', 'APROBADA'), ('RECHAZAR', 'RECHAZADA')])
def test_hu_003_ca_02_decision_persistida_y_estado_terminal(client, entorno, db, accion, estado):
    row, _ = crear(client, entorno)
    response, body = decidir(client, entorno, row, accion, observacion='Decisión ' + uuid4().hex)
    updated = respuesta(response, 200)
    assert updated['estado_codigo'] == estado and updated['version'] > body['version_esperada']
    approval = db.execute('SELECT * FROM aprobaciones WHERE id=%s',
                         (updated['aprobacion_id'],)).fetchone()
    assert approval['decision'] == accion and approval['actor_id'] == entorno['boss']['id']
    assert approval['revision_id'] == body['revision_id']
    assert approval['version_esperada'] == body['version_esperada'] and approval['decidido_en']
    path = '/api/admin/solicitudes/' + str(row['id']) + '/decisiones'
    respuesta(client.post(path, headers=entorno['boss']['admin'], json=body), 409)
    body['version_esperada'] = updated['version']
    respuesta(client.post(path, headers=entorno['boss']['admin'], json=body), 409)
    assert db.execute('SELECT count(*) AS n FROM aprobaciones WHERE revision_id=%s',
                      (body['revision_id'],)).fetchone()['n'] == 1
    if accion == 'RECHAZAR':
        recreated = respuesta(client.post('/api/solicitudes', headers=entorno['employee']['portal'],
                                          json=datos_solicitud({'id': row['tipo_ausencia_id']})), 201)
        assert recreated['id'] != row['id']


@pytest.mark.parametrize('changes,field', [
    ({'accion': 'RECHAZAR'}, 'observacion'),
    ({'accion': 'RECHAZAR', 'observacion': '   '}, 'observacion'),
    ({'accion': 'INVALIDA'}, 'accion'),
    ({'accion': 'VALIDAR'}, 'accion'),
    ({'accion': 'VALIDAR_APROBAR'}, 'accion'),
    ({'version_esperada': 0}, 'version_esperada'),
    ({'revision_id': 0}, 'revision_id'),
])
def test_hu_003_ca_02_decisiones_invalidas_no_modifican(client, entorno, db, changes, field):
    row, _ = crear(client, entorno)
    detail = detalle(client, entorno, row)
    body = decision_body(detail, 'APROBAR')
    body.update(changes)
    response = client.post('/api/admin/solicitudes/' + str(row['id']) + '/decisiones',
                           headers=entorno['boss']['admin'], json=body)
    invalido(response, field, model=True)
    current = db.execute('SELECT * FROM solicitudes WHERE id=%s', (row['id'],)).fetchone()
    assert current['version'] == row['version'] and current['estado_codigo'] == 'EN_REVISION'
    assert not db.execute('SELECT a.id FROM aprobaciones a JOIN revisiones r ON r.id=a.revision_id '
                          'WHERE r.solicitud_id=%s', (row['id'],)).fetchone()


@pytest.mark.parametrize('accion', ['APROBAR', 'RECHAZAR'])
def test_hu_003_ca_03_observaciones_asociadas_a_decision(client, entorno, db, accion):
    row, _ = crear(client, entorno)
    text = 'Observación ' + uuid4().hex
    response, body = decidir(client, entorno, row, accion, observacion=text)
    result = respuesta(response, 200)
    observation = db.execute('SELECT * FROM observaciones WHERE solicitud_id=%s',
                             (row['id'],)).fetchone()
    assert observation['texto'] == text and observation['autor_id'] == entorno['boss']['id']
    assert observation['revision_id'] == body['revision_id']
    assert observation['aprobacion_id'] == result['aprobacion_id']
    assert any(o['texto'] == text for o in detalle(client, entorno, row)['observaciones'])
    auditar_modificacion(db, entorno['boss'], 'observaciones', observation['id'], 'INSERT')


@pytest.mark.parametrize('actor', ['boss', 'hr'])
def test_hu_003_ca_04_hu_004_ca_03_accesos_y_modificaciones_auditados(client, entorno, db, actor):
    # HU-003-CA-04 y HU-004-CA-03.
    flow = 'JEFE_INMEDIATO' if actor == 'boss' else 'TALENTO_HUMANO'
    absence_type, _ = tipo(client, entorno, flujo_codigo=flow)
    row, _ = crear(client, entorno, absence_type)
    base = '/api/admin/solicitudes/' + str(row['id'])
    for suffix, operation in [('', 'CONSULTAR_DETALLE'), ('/historial', 'CONSULTAR_HISTORIAL')]:
        response = client.get(base + suffix, headers=entorno[actor]['admin'])
        respuesta(response, 200)
        auditar_acceso(db, response, entorno[actor], operation, row['id'])
        denied = client.get(base + suffix, headers=entorno['other_boss']['admin'])
        respuesta(denied, 403)
        auditar_acceso(db, denied, entorno['other_boss'], operation, row['id'], False)
    action = 'APROBAR' if actor == 'boss' else 'VALIDAR_APROBAR'
    response, body = decidir(client, entorno, row, action, actor=actor,
                             observacion='Auditoría ' + uuid4().hex)
    result = respuesta(response, 200)
    auditar_acceso(db, response, entorno[actor], 'ACCESO', row['id'])
    auditar_modificacion(db, entorno[actor], 'solicitudes', row['id'], 'UPDATE')
    auditar_modificacion(db, entorno[actor], 'revisiones', body['revision_id'], 'UPDATE')
    auditar_modificacion(db, entorno[actor], 'aprobaciones', result['aprobacion_id'], 'INSERT')
    invalido(client.get(base + '/historial', headers=entorno[actor]['admin'],
                       params={'desplazamiento': -1}), 'desplazamiento')


@pytest.mark.parametrize('combined', [False, True])
def test_hu_004_ca_01_validacion_y_aprobacion_talento_humano(client, entorno, db, combined):
    absence_type, _ = tipo(client, entorno, flujo_codigo='TALENTO_HUMANO')
    row, _ = crear(client, entorno, absence_type)
    path = '/api/admin/solicitudes/' + str(row['id']) + '/decisiones'
    detail = detalle(client, entorno, row, 'hr')
    invalid = decision_body(detail, 'APROBAR')
    invalido(client.post(path, headers=entorno['hr']['admin'], json=invalid), 'accion')
    assert db.execute('SELECT version FROM solicitudes WHERE id=%s',
                      (row['id'],)).fetchone()['version'] == row['version']
    if not combined:
        response, body = decidir(client, entorno, row, 'VALIDAR', actor='hr',
                                 observacion='Validación ' + uuid4().hex)
        validated = respuesta(response, 200)
        assert validated['estado_codigo'] == 'EN_REVISION'
        assert validated['aprobacion_id'] is None
        assert validated['revision']['validada_por_id'] == entorno['hr']['id']
        assert validated['revision']['validada_en']
        body['version_esperada'] = validated['version']
        respuesta(client.post(path, headers=entorno['hr']['admin'], json=body), 409)
        assert db.execute("SELECT id FROM historial_solicitud WHERE solicitud_id=%s AND operacion='VALIDAR'",
                          (row['id'],)).fetchone()
    response, _ = decidir(client, entorno, row, 'VALIDAR_APROBAR' if combined else 'APROBAR',
                          actor='hr', observacion='Aprobación ' + uuid4().hex)
    approved = respuesta(response, 200)
    assert approved['estado_codigo'] == 'APROBADA'
    assert approved['revision']['validada_por_id'] == entorno['hr']['id']
    assert approved['revision']['validada_en']


@pytest.mark.parametrize('accion', ['VALIDAR', 'VALIDAR_APROBAR', 'RECHAZAR'])
def test_hu_004_ca_02_observaciones_talento_humano(client, entorno, db, accion):
    absence_type, _ = tipo(client, entorno, flujo_codigo='TALENTO_HUMANO')
    row, _ = crear(client, entorno, absence_type)
    detail = detalle(client, entorno, row, 'hr')
    invalid = decision_body(detail, accion, '   ')
    invalido(client.post('/api/admin/solicitudes/' + str(row['id']) + '/decisiones',
                        headers=entorno['hr']['admin'], json=invalid), 'observacion', model=True)
    assert not db.execute('SELECT id FROM observaciones WHERE solicitud_id=%s', (row['id'],)).fetchone()
    text = 'Revisión TH ' + uuid4().hex
    response, body = decidir(client, entorno, row, accion, actor='hr', observacion=text)
    result = respuesta(response, 200)
    observations = detalle(client, entorno, row, 'hr')['observaciones']
    assert len(observations) == 1
    observed = observations[0]
    assert observed['texto'] == text and observed['autor_id'] == entorno['hr']['id']
    assert observed['revision_id'] == body['revision_id']
    assert observed['aprobacion_id'] == result['aprobacion_id']
    auditar_modificacion(db, entorno['hr'], 'observaciones', observed['id'], 'INSERT')


def test_hu_004_ca_01_etapas_secuenciales_y_decision_no_asignada(client, entorno, db):
    absence_type, _ = tipo(client, entorno, flujo_codigo='JEFE_Y_TALENTO_HUMANO')
    row, _ = crear(client, entorno, absence_type)
    detail = detalle(client, entorno, row, 'hr')
    hr_revision = next(r for r in detail['revisiones'] if r['rol_codigo'] == 'TALENTO_HUMANO')
    body = {'revision_id': hr_revision['id'], 'version_esperada': row['version'],
            'accion': 'VALIDAR_APROBAR'}
    path = '/api/admin/solicitudes/' + str(row['id']) + '/decisiones'
    respuesta(client.post(path, headers=entorno['hr']['admin'], json=body), 409)
    respuesta(client.post(path, headers=entorno['boss']['admin'], json=body), 403)
    respuesta(client.post(path, headers=entorno['other_boss']['admin'], json=body), 403)
    assert db.execute('SELECT version FROM solicitudes WHERE id=%s',
                      (row['id'],)).fetchone()['version'] == row['version']
    response, _ = decidir(client, entorno, row, 'APROBAR')
    assert respuesta(response, 200)['estado_codigo'] == 'EN_REVISION'
    response, _ = decidir(client, entorno, row, 'VALIDAR_APROBAR', actor='hr')
    assert respuesta(response, 200)['estado_codigo'] == 'APROBADA'


def test_hu_003_ca_02_conflicto_concurrente_solo_una_decision(client, entorno, db):
    row, _ = crear(client, entorno)
    detail = detalle(client, entorno, row)
    body = decision_body(detail, 'APROBAR', 'Concurrencia ' + uuid4().hex)
    barrier = Barrier(2)
    path = '/api/admin/solicitudes/' + str(row['id']) + '/decisiones'

    def send():
        with TestClient(app, raise_server_exceptions=False) as concurrent_client:
            barrier.wait(timeout=20)
            return concurrent_client.post(path, headers=entorno['boss']['admin'], json=body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: send(), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    approvals = db.execute('SELECT * FROM aprobaciones WHERE revision_id=%s',
                           (body['revision_id'],)).fetchall()
    assert len(approvals) == 1
    assert approvals[0]['version_esperada'] == body['version_esperada']
    assert db.execute('SELECT estado_codigo FROM solicitudes WHERE id=%s',
                      (row['id'],)).fetchone()['estado_codigo'] == 'APROBADA'


def test_hu_005_ca_01_catalogo_crud_duplicados_y_auditoria(client, entorno, db):
    original, body = tipo(client, entorno)
    headers = entorno['hr']['admin']
    path = '/api/admin/tipos-ausencia/' + str(original['id'])
    response = client.get(path, headers=headers)
    assert respuesta(response, 200)['nombre'] == body['nombre']
    auditar_acceso(db, response, entorno['hr'], 'CONSULTAR_CATALOGO')
    response = client.get('/api/admin/tipos-ausencia', headers=headers)
    respuesta(response, 200)
    auditar_acceso(db, response, entorno['hr'], 'CONSULTAR_CATALOGO')
    assert original['id'] in {t['id'] for t in pagina_completa(client, '/api/admin/tipos-ausencia', headers)}
    auditar_modificacion(db, entorno['hr'], 'tipos_ausencia', original['id'], 'INSERT')
    duplicate = {**body, 'nombre': body['nombre'].upper()}
    respuesta(client.post('/api/admin/tipos-ausencia', headers=headers, json=duplicate), 409)
    second, second_body = tipo(client, entorno)
    respuesta(client.put('/api/admin/tipos-ausencia/' + str(second['id']),
                        headers=headers, json=body), 409)
    assert respuesta(client.get('/api/admin/tipos-ausencia/' + str(second['id']),
                               headers=headers), 200)['nombre'] == second_body['nombre']
    updated_body = {**body, 'nombre': 'Modificado-' + uuid4().hex,
                    'estado': 'INACTIVO', 'requiere_motivo': True, 'modalidad_horas': 'OBLIGATORIA'}
    updated = respuesta(client.put(path, headers=headers, json=updated_body), 200)
    for field, value in updated_body.items():
        assert updated[field] == value
    auditar_modificacion(db, entorno['hr'], 'tipos_ausencia', original['id'], 'UPDATE')
    assert original['id'] not in {t['id'] for t in pagina_completa(
        client, '/api/empleado/tipos-ausencia', entorno['employee']['portal'])}
    invalid = datos_solicitud(original, hora_inicio='08:00:00', hora_fin='09:00:00')
    response = client.post('/api/solicitudes', headers=entorno['employee']['portal'], json=invalid)
    sin_creacion(db, entorno['employee'], invalid, response, 'tipo_ausencia_id')
    assert respuesta(client.delete(path, headers=headers), 200) == {'id': original['id'], 'eliminado': True}
    auditar_modificacion(db, entorno['hr'], 'tipos_ausencia', original['id'], 'DELETE')
    respuesta(client.get(path, headers=headers), 404)
    respuesta(client.delete(path, headers=headers), 404)
    respuesta(client.put(path, headers=headers, json=body), 404)
    respuesta(client.put(path + '/flujo', headers=headers,
                        json={'flujo_codigo': 'TALENTO_HUMANO'}), 404)


@pytest.mark.parametrize('changes,field', [
    ({'nombre': ''}, 'nombre'), ({'nombre': '   '}, 'nombre'),
    ({'nombre': 'N' * 201}, 'nombre'), ({'estado': 'ARCHIVADO'}, 'estado'),
    ({'modalidad_horas': 'DIARIA'}, 'modalidad_horas'),
    ({'flujo_codigo': 'LIBRE'}, 'flujo_codigo'),
])
def test_hu_005_ca_01_catalogo_validaciones_no_alteran(client, entorno, db, changes, field):
    original, body = tipo(client, entorno)
    invalid = {**body, **changes}
    headers = entorno['hr']['admin']
    invalido(client.post('/api/admin/tipos-ausencia', headers=headers, json=invalid), field)
    invalido(client.put('/api/admin/tipos-ausencia/' + str(original['id']),
                       headers=headers, json=invalid), field)
    assert respuesta(client.get('/api/admin/tipos-ausencia/' + str(original['id']),
                               headers=headers), 200)['nombre'] == original['nombre']
    assert db.execute('SELECT count(*) AS n FROM tipos_ausencia WHERE nombre=%s',
                      (original['nombre'],)).fetchone()['n'] == 1


def test_hu_005_ca_01_limite_nombre_200(client, entorno):
    name = 'QA-' + uuid4().hex + 'N' * 165
    assert len(name) == 200
    row, _ = tipo(client, entorno, nombre=name)
    assert row['nombre'] == name


def test_hu_005_ca_01_tipo_utilizado_no_eliminable_y_snapshot(client, entorno, db):
    original, body = tipo(client, entorno, requiere_motivo=True, modalidad_horas='OBLIGATORIA')
    row, _ = crear(client, entorno, original, hora_inicio='08:00:00', hora_fin='09:00:00')
    path = '/api/admin/tipos-ausencia/' + str(original['id'])
    respuesta(client.delete(path, headers=entorno['hr']['admin']), 409)
    changed = {**body, 'estado': 'INACTIVO', 'requiere_motivo': False,
               'modalidad_horas': 'NO_APLICA', 'flujo_codigo': 'TALENTO_HUMANO'}
    respuesta(client.put(path, headers=entorno['hr']['admin'], json=changed), 200)
    stored = db.execute('SELECT * FROM solicitudes WHERE id=%s', (row['id'],)).fetchone()
    assert stored['flujo_id'] == original['flujo_id']
    assert stored['requiere_motivo'] is True and stored['modalidad_horas'] == 'OBLIGATORIA'
    assert stored['version'] == row['version']
    assert detalle(client, entorno, row)['revisiones'][0]['aprobador_id'] == entorno['boss']['id']
    response, _ = decidir(client, entorno, row, 'APROBAR')
    assert respuesta(response, 200)['estado_codigo'] == 'APROBADA'


@pytest.mark.parametrize('flow,roles', [
    ('JEFE_INMEDIATO', ['JEFE_INMEDIATO']),
    ('JEFE_Y_TALENTO_HUMANO', ['JEFE_INMEDIATO', 'TALENTO_HUMANO']),
    ('TALENTO_HUMANO', ['TALENTO_HUMANO']),
])
def test_hu_005_ca_02_asociar_flujo_y_materializar_etapas(client, entorno, flow, roles):
    original, _ = tipo(client, entorno)
    path = '/api/admin/tipos-ausencia/' + str(original['id']) + '/flujo'
    updated = respuesta(client.put(path, headers=entorno['hr']['admin'],
                                   json={'flujo_codigo': flow}), 200)
    assert updated['flujo_codigo'] == flow
    row, _ = crear(client, entorno, updated)
    detail = detalle(client, entorno, row, 'hr' if flow == 'TALENTO_HUMANO' else 'boss')
    assert [r['rol_codigo'] for r in detail['revisiones']] == roles
    assert [r['orden'] for r in detail['revisiones']] == list(range(1, len(roles) + 1))
    assert detail['revisiones'][0]['estado'] == 'PENDIENTE'
    for revision in detail['revisiones']:
        expected = entorno['boss']['id'] if revision['rol_codigo'] == 'JEFE_INMEDIATO' else entorno['hr']['id']
        assert revision['aprobador_id'] == expected
        assert revision['requiere_validacion'] == (revision['rol_codigo'] == 'TALENTO_HUMANO')
    invalido(client.put(path, headers=entorno['hr']['admin'],
                       json={'flujo_codigo': 'NO_CONFIGURADO'}), 'flujo_codigo')
    current = respuesta(client.get('/api/admin/tipos-ausencia/' + str(original['id']),
                                  headers=entorno['hr']['admin']), 200)
    assert current['flujo_codigo'] == flow


@pytest.mark.parametrize('method,suffix', [
    ('GET', ''), ('GET', '/id'), ('POST', ''), ('PUT', '/id'),
    ('PUT', '/id/flujo'), ('DELETE', '/id'),
])
def test_hu_005_ca_01_catalogo_exige_rol_hr(client, entorno, method, suffix):
    original, body = tipo(client, entorno)
    path = '/api/admin/tipos-ausencia' + suffix.replace('/id', '/' + str(original['id']))
    payload = {'flujo_codigo': 'TALENTO_HUMANO'} if suffix.endswith('/flujo') else body
    response = client.request(method, path, headers=entorno['boss']['admin'],
                              json=payload if method in ('POST', 'PUT') else None)
    respuesta(response, 403)
    respuesta(client.request(method, path, headers=entorno['employee']['admin'],
                             json=payload if method in ('POST', 'PUT') else None), 403)


def test_hu_003_ca_01_token_admin_no_sustituye_identidad(client, entorno):
    path = '/api/admin/solicitudes'
    respuesta(client.get(path, headers={'Authorization': 'Bearer ' + os.environ['ADMIN_API_TOKEN']}), 401)
    respuesta(client.get(path, headers={'X-Identity-Token': entorno['boss']['admin']['X-Identity-Token']}), 401)
    wrong = dict(entorno['boss']['admin'])
    wrong['Authorization'] = 'Bearer ' + uuid4().hex
    respuesta(client.get(path, headers=wrong), 401)
    assert client.get(path, headers=entorno['boss']['admin']).status_code == 200


@pytest.mark.parametrize('path,actor', [
    ('/api/empleado/tipos-ausencia', 'employee'), ('/api/empleado/solicitudes', 'employee'),
    ('/api/notificaciones', 'employee'), ('/api/admin/solicitudes', 'boss'),
    ('/api/admin/tipos-ausencia', 'hr'),
    ('/api/empleado/solicitudes/id/historial', 'employee'),
    ('/api/admin/solicitudes/id/historial', 'boss'),
])
@pytest.mark.parametrize('params,field', [
    ({'limite': 0}, 'limite'), ({'limite': 101}, 'limite'),
    ({'desplazamiento': -1}, 'desplazamiento'),
])
def test_hu_001_ca_04_hu_003_ca_01_hu_005_ca_01_paginacion_invalida(
        client, entorno, path, actor, params, field):
    row, _ = crear(client, entorno)
    path = path.replace('/id/', '/' + str(row['id']) + '/')
    headers = entorno[actor]['admin' if '/admin/' in path else 'portal']
    invalido(client.get(path, headers=headers, params=params), field)


@pytest.mark.parametrize('limit', [1, 100])
def test_hu_001_ca_04_hu_003_ca_01_hu_005_ca_01_limites_paginacion_validos(client, entorno, limit):
    row, _ = crear(client, entorno)
    routes = [
        ('/api/empleado/tipos-ausencia', entorno['employee']['portal']),
        ('/api/empleado/solicitudes', entorno['employee']['portal']),
        ('/api/notificaciones', entorno['employee']['portal']),
        ('/api/admin/solicitudes', entorno['boss']['admin']),
        ('/api/admin/tipos-ausencia', entorno['hr']['admin']),
        ('/api/empleado/solicitudes/' + str(row['id']) + '/historial', entorno['employee']['portal']),
        ('/api/admin/solicitudes/' + str(row['id']) + '/historial', entorno['boss']['admin']),
    ]
    for path, headers in routes:
        result = respuesta(client.get(path, headers=headers,
                                      params={'limite': limit, 'desplazamiento': 0}), 200)
        assert result['limite'] == limit and result['desplazamiento'] == 0
        assert len(result['items']) <= limit


def test_hu_001_ca_01_asignacion_invalida_y_tipo_inexistente(client, entorno, db):
    original, _ = tipo(client, entorno)
    with db.transaction():
        db.execute("SELECT set_config('app.usuario_id', %s, true)", (str(entorno['hr']['id']),))
        db.execute('UPDATE usuarios SET jefe_inmediato_id=NULL WHERE id=%s',
                   (entorno['employee']['id'],))
    body = datos_solicitud(original)
    response = client.post('/api/solicitudes', headers=entorno['employee']['portal'], json=body)
    sin_creacion(db, entorno['employee'], body, response, 'tipo_ausencia_id')
    missing = db.execute('SELECT coalesce(max(id),0)+1 AS id FROM tipos_ausencia').fetchone()['id']
    body = datos_solicitud({'id': missing})
    response = client.post('/api/solicitudes', headers=entorno['employee']['portal'], json=body)
    sin_creacion(db, entorno['employee'], body, response, 'tipo_ausencia_id')