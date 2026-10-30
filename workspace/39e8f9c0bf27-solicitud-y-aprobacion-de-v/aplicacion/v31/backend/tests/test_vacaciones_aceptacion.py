import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.main import app


@pytest.fixture
def escenario(monkeypatch):
    # Datos propios por caso; el historial inmutable no se elimina.
    marca = uuid4().hex
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as db:
        area = db.execute('INSERT INTO areas(nombre) VALUES (%s) RETURNING id', ('QA-area-' + marca,)).fetchone()['id']
        cargo = db.execute('INSERT INTO cargos(nombre) VALUES (%s) RETURNING id', ('QA-cargo-' + marca,)).fetchone()['id']

        def empleado(etiqueta, roles, jefe=None):
            documento = etiqueta + '-' + marca
            fila = db.execute('''INSERT INTO empleados
                (identidad_externa, nombre, documento, correo, area_id, cargo_id, jefe_inmediato_id, turno)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (documento, documento, documento, documento + '@example.invalid', area, cargo, jefe, 'DIURNO')).fetchone()
            for rol in roles:
                db.execute('INSERT INTO empleado_roles(empleado_id, rol_codigo) VALUES (%s,%s)', (fila['id'], rol))
            return fila

        jefe = empleado('jefe', ['EMPLEADO', 'JEFE_INMEDIATO'])
        hr = empleado('hr', ['EMPLEADO', 'TALENTO_HUMANO'])
        ajeno = empleado('jefe-ajeno', ['EMPLEADO', 'JEFE_INMEDIATO'])
        titular = empleado('titular', ['EMPLEADO'], jefe['id'])
        otro = empleado('otro', ['EMPLEADO'], ajeno['id'])
        monkeypatch.setenv('ADMIN_ACTOR_ID', str(hr['id']))
        with TestClient(app) as client:
            admin_headers = {'Authorization': 'Bearer ' + os.environ['ADMIN_API_TOKEN']}

            def admin(method, ruta, actor=None, **kwargs):
                monkeypatch.setenv('ADMIN_ACTOR_ID', str((actor or hr)['id']))
                return client.request(method, ruta, headers=admin_headers, **kwargs)

            def login(persona):
                respuesta = client.post('/api/acceso', json={'documento': persona['documento']})
                assert respuesta.status_code == 200, respuesta.text
                datos = respuesta.json()
                assert datos['tipo'] == 'Bearer'
                assert isinstance(datos['expira_en'], int)
                return {'Authorization': 'Bearer ' + datos['token']}

            headers = login(titular)
            otros_headers = login(otro)

            def tipo(flujo='JEFE_INMEDIATO', **cambios):
                datos = dict(nombre='QA-tipo-' + uuid4().hex, estado='ACTIVO', requiere_motivo=False,
                             permite_horas=False, flujo_codigo=flujo)
                datos.update(cambios)
                respuesta = admin('POST', '/api/admin/tipos-ausencia', json=datos)
                assert respuesta.status_code == 201, respuesta.text
                return respuesta.json(), datos

            def crear(tipo_id=None, usuario=None, **cambios):
                if tipo_id is None:
                    tipo_id = tipo()[0]['id']
                datos = dict(tipo_ausencia_id=tipo_id, fecha_inicio='2035-06-10', fecha_fin='2035-06-10', origen='PORTAL')
                datos.update(cambios)
                respuesta = client.post('/api/portal/solicitudes', headers=usuario or headers, json=datos)
                assert respuesta.status_code == 201, respuesta.text
                return respuesta.json()

            def decidir(solicitud, accion, actor=None, observacion=None):
                datos = {'version': solicitud['version'], 'accion': accion}
                if observacion is not None:
                    datos['observacion'] = observacion
                respuesta = admin('POST', f"/api/admin/solicitudes/{solicitud['id']}/decisiones", actor=actor or jefe, json=datos)
                assert respuesta.status_code == 201, respuesta.text
                resultado = respuesta.json()
                assert resultado['decision']['accion'] == accion
                assert resultado['solicitud']['version'] == solicitud['version'] + 1
                return resultado

            yield SimpleNamespace(db=db, client=client, admin=admin, tipo=tipo, crear=crear, decidir=decidir,
                                  headers=headers, otros_headers=otros_headers, jefe=jefe, hr=hr, ajeno=ajeno,
                                  titular=titular, otro=otro, admin_headers=admin_headers, monkeypatch=monkeypatch)


def validar_422(respuesta, campo):
    assert respuesta.status_code == 422, respuesta.text
    detalle = respuesta.json()['detail']
    if isinstance(detalle, list):
        # Las validaciones cruzadas pueden estar situadas en la raíz del cuerpo.
        assert any(campo in error.get('loc', []) or error.get('loc') == ['body'] for error in detalle)
        assert all(isinstance(error.get('type'), str) and error['type'] for error in detalle)
    else:
        # Las reglas de negocio no especifican un formato de error por campo.
        assert isinstance(detalle, str) and detalle.strip()


def auditoria(s, solicitud_id, actor_id, operacion):
    filas = s.db.execute('''SELECT * FROM auditoria_acceso
        WHERE solicitud_id=%s AND actor_id=%s AND operacion=%s AND autorizado''',
        (solicitud_id, actor_id, operacion)).fetchall()
    assert filas
    assert all(fila['creado_en'] is not None and fila['correlacion_id'] is not None for fila in filas)


def modificaciones(s, solicitud_id, actor_id, entidades):
    filas = s.db.execute('SELECT * FROM auditoria_modificacion WHERE solicitud_id=%s AND actor_id=%s',
                         (solicitud_id, actor_id)).fetchall()
    assert set(entidades) <= {fila['entidad'] for fila in filas}
    assert all(fila['creado_en'] is not None and fila['correlacion_id'] is not None for fila in filas)


def test_health_publico():
    with TestClient(app) as client:
        respuesta = client.get('/api/health')
    assert respuesta.status_code == 200
    assert respuesta.json() == {'estado': 'ok'}


ADMIN_RUTAS = [
    (ruta.path, metodo)
    for ruta in app.routes if ruta.path.startswith('/api/admin/')
    for metodo in sorted(ruta.methods or []) if metodo not in {'HEAD', 'OPTIONS'}
]


@pytest.mark.parametrize('ruta,metodo', ADMIN_RUTAS)
def test_hu_003_ca_04_hu_004_ca_03_hu_005_ca_01_admin_sin_token(ruta, metodo):
    ruta = ruta.replace('{solicitud_id}', '1').replace('{tipo_id}', '1')
    datos = dict(nombre='QA-' + uuid4().hex, estado='ACTIVO', requiere_motivo=False,
                 permite_horas=False, flujo_codigo='JEFE_INMEDIATO')
    if ruta.endswith('/decisiones'):
        datos = {'version': 1, 'accion': 'APROBAR'}
    elif ruta.endswith('/flujo'):
        datos = {'flujo_codigo': 'JEFE_INMEDIATO'}
    with TestClient(app) as client:
        respuesta = client.request(metodo, ruta, json=datos if metodo in {'POST', 'PUT'} else None)
    assert respuesta.status_code in {401, 403}, respuesta.text


@pytest.mark.parametrize('rol', ['jefe', 'hr'])
def test_hu_003_ca_01_hu_004_ca_01_hu_005_ca_01_entrada_panel_autorizada(escenario, rol):
    s = escenario
    respuesta = s.admin('GET', '/api/admin/', actor=getattr(s, rol))
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos['estado'] == 'ok'
    assert datos['recursos']['solicitudes'] == '/api/admin/solicitudes'
    assert datos['recursos']['notificaciones'] == '/api/admin/notificaciones'
    if rol == 'hr':
        assert datos['recursos']['tipos_ausencia'] == '/api/admin/tipos-ausencia'
        assert datos['recursos']['flujos'] == '/api/admin/flujos'
    else:
        assert not {'tipos_ausencia', 'flujos'} & datos['recursos'].keys()


@pytest.mark.parametrize('origen', ['PORTAL', 'FORMATO_OFICIAL'])
def test_hu_001_ca_01_registro_flujo_y_origen(escenario, origen):
    s = escenario
    tipo, _ = s.tipo('JEFE_Y_TALENTO_HUMANO')
    cambios = {'origen': origen}
    if origen == 'FORMATO_OFICIAL':
        cambios['referencia_formato'] = uuid4().hex
    solicitud = s.crear(tipo['id'], **cambios)
    persistida = s.db.execute('SELECT solicitante_id FROM solicitudes WHERE id=%s', (solicitud['id'],)).fetchone()
    assert persistida['solicitante_id'] == s.titular['id']
    assert 'solicitante_id' not in solicitud
    assert solicitud['estado_codigo'] == 'ENVIADA'
    assert solicitud['version'] == 1
    assert solicitud['origen'] == origen
    pasos = s.db.execute('SELECT * FROM revisiones WHERE solicitud_id=%s ORDER BY orden', (solicitud['id'],)).fetchall()
    assert [(p['rol_codigo'], p['estado']) for p in pasos] == [('JEFE_INMEDIATO', 'PENDIENTE'), ('TALENTO_HUMANO', 'BLOQUEADA')]
    assert pasos[0]['aprobador_id'] == s.jefe['id']
    modificaciones(s, solicitud['id'], s.titular['id'], ['solicitudes', 'revisiones'])
    invalido = dict(tipo_ausencia_id=tipo['id'], fecha_inicio='2035-06-10', fecha_fin='2035-06-10', origen='FORMATO_OFICIAL')
    validar_422(s.client.post('/api/portal/solicitudes', headers=s.headers, json=invalido), 'referencia_formato')


@pytest.mark.parametrize('motivo', ['x', 'm' * 4000])
def test_hu_001_ca_02_motivo_obligatorio_y_limites(escenario, motivo):
    s = escenario
    tipo, _ = s.tipo(requiere_motivo=True)
    solicitud = s.crear(tipo['id'], motivo=motivo)
    assert solicitud['motivo'] == motivo
    for invalido in [None, '', '   ', 'm' * 4001]:
        datos = dict(tipo_ausencia_id=tipo['id'], fecha_inicio='2035-06-10', fecha_fin='2035-06-10', motivo=invalido)
        antes = s.db.execute('SELECT count(*) AS n FROM solicitudes WHERE tipo_ausencia_id=%s', (tipo['id'],)).fetchone()['n']
        validar_422(s.client.post('/api/portal/solicitudes', headers=s.headers, json=datos), 'motivo')
        despues = s.db.execute('SELECT count(*) AS n FROM solicitudes WHERE tipo_ausencia_id=%s', (tipo['id'],)).fetchone()['n']
        assert despues == antes


@pytest.mark.parametrize('cambios,campo', [
    ({'fecha_fin': '2035-06-09'}, 'fecha_fin'),
    ({'fecha_inicio': 'fecha-invalida'}, 'fecha_inicio'),
    ({'hora_inicio': '10:00:00', 'hora_fin': None}, 'hora_fin'),
    ({'hora_inicio': '10:00:00', 'hora_fin': '10:00:00'}, 'hora_fin'),
    ({'hora_inicio': '11:00:00', 'hora_fin': '10:00:00'}, 'hora_fin'),
    ({'hora_inicio': '25:00:00', 'hora_fin': '12:00:00'}, 'hora_inicio'),
    ({'tipo_ausencia_id': 0}, 'tipo_ausencia_id'),
    ({'solicitante_id': 1}, 'solicitante_id'),
])
def test_hu_001_ca_03_fechas_horas_validas_e_invalidas(escenario, cambios, campo):
    s = escenario
    tipo, _ = s.tipo(permite_horas=True)
    solicitud = s.crear(tipo['id'], hora_inicio='10:00:00', hora_fin='10:01:00')
    assert solicitud['fecha_inicio'] == solicitud['fecha_fin'] == '2035-06-10'
    assert solicitud['hora_inicio'] == '10:00:00'
    assert solicitud['hora_fin'] == '10:01:00'
    datos = dict(tipo_ausencia_id=tipo['id'], fecha_inicio='2035-06-10', fecha_fin='2035-06-10', hora_inicio='10:00:00', hora_fin='11:00:00')
    datos.update(cambios)
    validar_422(s.client.post('/api/portal/solicitudes', headers=s.headers, json=datos), campo)
    sin_horas, _ = s.tipo(permite_horas=False)
    datos.update(tipo_ausencia_id=sin_horas['id'], fecha_inicio='2035-06-10', fecha_fin='2035-06-10', hora_inicio='10:00:00', hora_fin='11:00:00')
    datos.pop('solicitante_id', None)
    validar_422(s.client.post('/api/portal/solicitudes', headers=s.headers, json=datos), 'hora_inicio')


def test_hu_001_ca_04_estado_historial_edicion_y_aislamiento(escenario):
    s = escenario
    solicitud = s.crear()
    otra = s.crear(usuario=s.otros_headers)
    ruta = f"/api/portal/solicitudes/{solicitud['id']}"
    perfil = s.client.get('/api/portal/me', headers=s.headers)
    assert perfil.status_code == 200
    assert perfil.json()['id'] == s.titular['id']
    assert perfil.json()['documento'] == s.titular['documento']
    assert s.client.get('/api/portal/tipos-ausencia', headers=s.headers).status_code == 200
    datos = dict(version=1, fecha_inicio='2035-06-11', fecha_fin='2035-06-11', motivo='Actualización ' + uuid4().hex)
    editada = s.client.put(ruta, headers=s.headers, json=datos)
    assert editada.status_code == 200, editada.text
    assert editada.json()['version'] == 2
    assert editada.json()['motivo'] == datos['motivo']
    assert s.client.put(ruta, headers=s.headers, json=datos).status_code == 409
    validar_422(s.client.put(ruta, headers=s.headers, json={**datos, 'version': 2, 'fecha_fin': '2035-06-09'}), 'fecha_fin')
    for sufijo in ['', '/historial']:
        assert s.client.get(ruta + sufijo, headers=s.headers).status_code == 200
        assert s.client.get(ruta + sufijo, headers=s.otros_headers).status_code == 404
    assert s.client.put(ruta, headers=s.otros_headers, json={**datos, 'version': 2}).status_code == 404
    assert s.client.request('DELETE', ruta, headers=s.otros_headers, json={'version': 2}).status_code == 404
    listado = s.client.get('/api/portal/solicitudes', headers=s.headers)
    assert listado.status_code == 200
    filas = listado.json()
    assert solicitud['id'] in {f['id'] for f in filas}
    assert otra['id'] not in {f['id'] for f in filas}
    for fila in filas:
        assert 'solicitante_id' not in fila
        propietario = s.db.execute('SELECT solicitante_id FROM solicitudes WHERE id=%s', (fila['id'],)).fetchone()
        assert propietario['solicitante_id'] == s.titular['id']
    cancelada = s.client.request('DELETE', ruta, headers=s.headers, json={'version': 2})
    assert cancelada.status_code == 200
    assert cancelada.json()['estado_codigo'] == 'CANCELADA'
    assert cancelada.json()['version'] == 3
    assert s.client.request('DELETE', ruta, headers=s.headers, json={'version': 3}).status_code == 409
    assert s.client.put(ruta, headers=s.headers, json={**datos, 'version': 3}).status_code == 409
    historial = s.client.get(ruta + '/historial', headers=s.headers)
    assert historial.status_code == 200
    assert [h['version'] for h in historial.json()['historial']] == [1, 2, 3]
    assert historial.json()['historial'][-1]['estado_nuevo'] == 'CANCELADA'
    auditoria(s, solicitud['id'], s.titular['id'], 'CONSULTA_HISTORIAL')
    auditoria(s, solicitud['id'], s.titular['id'], 'CONSULTA_DETALLE')
    modificaciones(s, solicitud['id'], s.titular['id'], ['solicitudes'])


def test_hu_002_ca_01_notificacion_estado_leida_y_privacidad(escenario):
    s = escenario
    solicitud = s.crear()
    resultado = s.decidir(solicitud, 'APROBAR')
    avisos = s.client.get('/api/portal/notificaciones', headers=s.headers)
    assert avisos.status_code == 200
    propios = [n for n in avisos.json() if n['solicitud_id'] == solicitud['id']]
    assert len(propios) == 1
    aviso = propios[0]
    assert aviso['estado_nuevo'] == resultado['solicitud']['estado_codigo'] == 'APROBADA'
    assert not {'correo', 'ultimo_error', 'estado_envio'} & aviso.keys()
    otros = s.client.get('/api/portal/notificaciones', headers=s.otros_headers)
    assert otros.status_code == 200
    assert aviso['id'] not in {n['id'] for n in otros.json()}
    ruta = f"/api/portal/notificaciones/{aviso['id']}/leida"
    assert s.client.patch(ruta, headers=s.otros_headers).status_code == 404
    leida = s.client.patch(ruta, headers=s.headers)
    assert leida.status_code == 200
    assert leida.json()['leida_en'] is not None
    assert s.client.patch(ruta, headers=s.headers).json() == leida.json()
    assert s.client.patch('/api/portal/notificaciones/0/leida', headers=s.headers).status_code == 404
    persistidos = s.db.execute('SELECT * FROM notificaciones WHERE solicitud_id=%s AND tipo=%s', (solicitud['id'], 'CAMBIO_ESTADO')).fetchall()
    assert len(persistidos) == 1
    assert persistidos[0]['destinatario_id'] == s.titular['id']


def test_hu_002_ca_02_avisos_aprobadores_por_paso(escenario):
    s = escenario
    tipo, _ = s.tipo('JEFE_Y_TALENTO_HUMANO')
    solicitud = s.crear(tipo['id'])
    ruta = '/api/admin/notificaciones'
    respuesta = s.admin('GET', ruta, actor=s.jefe)
    assert respuesta.status_code == 200
    assert solicitud['id'] in {n['solicitud_id'] for n in respuesta.json()}
    for actor in [s.ajeno, s.hr]:
        respuesta = s.admin('GET', ruta, actor=actor)
        assert respuesta.status_code == 200
        assert solicitud['id'] not in {n['solicitud_id'] for n in respuesta.json()}
    s.decidir(solicitud, 'APROBAR')
    respuesta = s.admin('GET', ruta, actor=s.hr)
    assert respuesta.status_code == 200
    assert solicitud['id'] in {n['solicitud_id'] for n in respuesta.json()}
    filas = s.db.execute('''SELECT revision_id, destinatario_id, count(*) AS n FROM notificaciones
        WHERE solicitud_id=%s AND tipo='PENDIENTE_REVISION' GROUP BY revision_id, destinatario_id''', (solicitud['id'],)).fetchall()
    assert filas and all(f['n'] == 1 for f in filas)


def test_hu_003_ca_01_bandeja_restringida_y_validacion(escenario):
    s = escenario
    propia = s.crear()
    ajena = s.crear(usuario=s.otros_headers)
    respuesta = s.admin('GET', '/api/admin/solicitudes', actor=s.jefe)
    assert respuesta.status_code == 200
    ids = {f['id'] for f in respuesta.json()}
    assert propia['id'] in ids and ajena['id'] not in ids
    for sufijo in ['', '/historial']:
        assert s.admin('GET', f"/api/admin/solicitudes/{ajena['id']}" + sufijo, actor=s.jefe).status_code == 404
    validar_422(s.admin('GET', '/api/admin/solicitudes', actor=s.jefe, params={'estado': 'NO_EXISTE'}), 'estado')
    assert s.admin('GET', '/api/admin/tipos-ausencia', actor=s.jefe).status_code == 403


@pytest.mark.parametrize('accion,estado', [('APROBAR', 'APROBADA'), ('RECHAZAR', 'RECHAZADA')])
def test_hu_003_ca_02_ca_03_ca_04_decision_observaciones_auditoria(escenario, accion, estado):
    # HU-003-CA-02, HU-003-CA-03, HU-003-CA-04.
    s = escenario
    solicitud = s.crear()
    ruta = f"/api/admin/solicitudes/{solicitud['id']}"
    assert s.admin('GET', ruta, actor=s.jefe).status_code == 200
    invalidos = [({'version': 1, 'accion': 'NO_EXISTE'}, 'accion'),
                 ({'version': 0, 'accion': accion}, 'version'),
                 ({'version': 1, 'accion': 'RECHAZAR'}, 'observacion'),
                 ({'version': 1, 'accion': accion, 'observacion': 'x' * 4001}, 'observacion')]
    for datos, campo in invalidos:
        validar_422(s.admin('POST', ruta + '/decisiones', actor=s.jefe, json=datos), campo)
    assert s.db.execute('SELECT count(*) AS n FROM aprobaciones WHERE solicitud_id=%s', (solicitud['id'],)).fetchone()['n'] == 0
    observacion = 'Revisión ' + uuid4().hex
    resultado = s.decidir(solicitud, accion, observacion=observacion)
    assert resultado['solicitud']['estado_codigo'] == estado
    historial = s.admin('GET', ruta + '/historial', actor=s.jefe)
    assert historial.status_code == 200
    h = historial.json()
    assert h['decisiones'][0]['accion'] == accion
    assert h['observaciones'][0]['texto'] == observacion
    assert h['observaciones'][0]['aprobacion_id'] == resultado['decision']['id']
    assert h['observaciones'][0]['actor_id'] == s.jefe['id']
    auditoria(s, solicitud['id'], s.jefe['id'], 'CONSULTA_DETALLE')
    auditoria(s, solicitud['id'], s.jefe['id'], 'CONSULTA_HISTORIAL')
    modificaciones(s, solicitud['id'], s.jefe['id'], ['solicitudes', 'revisiones', 'aprobaciones', 'observaciones'])
    assert s.admin('POST', ruta + '/decisiones', actor=s.jefe, json={'version': 2, 'accion': accion, 'observacion': observacion}).status_code == 409


@pytest.mark.parametrize('accion', ['VALIDAR_Y_APROBAR', 'RECHAZAR', 'VALIDAR'])
def test_hu_004_ca_01_ca_02_ca_03_validacion_decision_y_traza(escenario, accion):
    # HU-004-CA-01, HU-004-CA-02, HU-004-CA-03.
    s = escenario
    tipo, _ = s.tipo('TALENTO_HUMANO')
    solicitud = s.crear(tipo['id'])
    ruta = f"/api/admin/solicitudes/{solicitud['id']}"
    assert s.admin('GET', ruta, actor=s.hr).status_code == 200
    validar_422(s.admin('POST', ruta + '/decisiones', actor=s.hr, json={'version': 1, 'accion': 'APROBAR'}), 'accion')
    validar_422(s.admin('POST', ruta + '/decisiones', actor=s.hr, json={'version': 1, 'accion': 'RECHAZAR', 'observacion': '   '}), 'observacion')
    texto = 'Talento Humano ' + uuid4().hex
    resultado = s.decidir(solicitud, accion, actor=s.hr, observacion=texto)
    if accion == 'VALIDAR':
        assert resultado['solicitud']['estado_codigo'] == 'EN_REVISION'
        assert s.admin('POST', ruta + '/decisiones', actor=s.hr, json={'version': 2, 'accion': 'VALIDAR'}).status_code == 409
        datos_edicion = {'version': 2, 'fecha_inicio': '2035-06-11', 'fecha_fin': '2035-06-11'}
        assert s.client.put(f"/api/portal/solicitudes/{solicitud['id']}", headers=s.headers, json=datos_edicion).status_code == 409
        resultado = s.decidir(resultado['solicitud'], 'APROBAR', actor=s.hr, observacion=texto + ' aprobada')
    assert resultado['solicitud']['estado_codigo'] == ('RECHAZADA' if accion == 'RECHAZAR' else 'APROBADA')
    h = s.admin('GET', ruta + '/historial', actor=s.hr)
    assert h.status_code == 200
    assert any(o['texto'] == texto and o['actor_id'] == s.hr['id'] for o in h.json()['observaciones'])
    assert all(o['aprobacion_id'] in {d['id'] for d in h.json()['decisiones']} for o in h.json()['observaciones'])
    auditoria(s, solicitud['id'], s.hr['id'], 'CONSULTA_DETALLE')
    auditoria(s, solicitud['id'], s.hr['id'], 'CONSULTA_HISTORIAL')
    modificaciones(s, solicitud['id'], s.hr['id'], ['solicitudes', 'revisiones', 'aprobaciones', 'observaciones'])


def test_hu_004_ca_01_flujo_secuencial_y_asignacion(escenario):
    s = escenario
    tipo, _ = s.tipo('JEFE_Y_TALENTO_HUMANO')
    solicitud = s.crear(tipo['id'])
    ruta = f"/api/admin/solicitudes/{solicitud['id']}/decisiones"
    assert s.admin('POST', ruta, actor=s.hr, json={'version': 1, 'accion': 'VALIDAR_Y_APROBAR'}).status_code == 403
    validar_422(s.admin('POST', ruta, actor=s.jefe, json={'version': 1, 'accion': 'VALIDAR'}), 'accion')
    primero = s.decidir(solicitud, 'APROBAR')
    assert primero['solicitud']['estado_codigo'] == 'EN_REVISION'
    segundo = s.decidir(primero['solicitud'], 'VALIDAR_Y_APROBAR', actor=s.hr)
    assert segundo['solicitud']['estado_codigo'] == 'APROBADA'
    assert segundo['solicitud']['version'] == 3


def test_hu_003_ca_02_conflicto_concurrente_sin_doble_decision(escenario):
    s = escenario
    solicitud = s.crear()
    s.monkeypatch.setenv('ADMIN_ACTOR_ID', str(s.jefe['id']))
    ruta = f"/api/admin/solicitudes/{solicitud['id']}/decisiones"

    def enviar(accion):
        with TestClient(app) as client:
            return client.post(ruta, headers=s.admin_headers, json={'version': 1, 'accion': accion, 'observacion': uuid4().hex}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(enviar, ['APROBAR', 'RECHAZAR']))
    assert sorted(resultados) == [201, 409]
    filas = s.db.execute('SELECT * FROM aprobaciones WHERE solicitud_id=%s', (solicitud['id'],)).fetchall()
    assert len(filas) == 1
    assert filas[0]['version_esperada'] == 1 and filas[0]['version_resultante'] == 2
    assert s.db.execute('SELECT version FROM solicitudes WHERE id=%s', (solicitud['id'],)).fetchone()['version'] == 2


def test_hu_005_ca_01_catalogo_crud_duplicados_y_estados(escenario):
    s = escenario
    tipo, datos = s.tipo(nombre='n' * 118 + uuid4().hex)
    ruta = f"/api/admin/tipos-ausencia/{tipo['id']}"
    assert len(datos['nombre']) == 150
    assert s.admin('GET', ruta).status_code == 200
    listado = s.admin('GET', '/api/admin/tipos-ausencia')
    assert listado.status_code == 200
    assert tipo['id'] in {t['id'] for t in listado.json()}
    assert s.admin('POST', '/api/admin/tipos-ausencia', json={**datos, 'nombre': '  ' + datos['nombre'].upper() + '  '}).status_code == 409
    for cambios, campo in [({'nombre': ''}, 'nombre'), ({'nombre': 'x' * 151}, 'nombre'), ({'estado': 'INVALIDO'}, 'estado')]:
        validar_422(s.admin('POST', '/api/admin/tipos-ausencia', json={**datos, **cambios}), campo)
        validar_422(s.admin('PUT', ruta, json={**datos, **cambios}), campo)
    segundo, segundo_datos = s.tipo()
    assert s.admin('PUT', ruta, json={**datos, 'nombre': segundo_datos['nombre']}).status_code == 409
    actualizado = s.admin('PUT', ruta, json={**datos, 'estado': 'INACTIVO'})
    assert actualizado.status_code == 200
    assert actualizado.json()['estado'] == 'INACTIVO'
    publico = s.client.get('/api/portal/tipos-ausencia', headers=s.headers)
    assert publico.status_code == 200
    assert tipo['id'] not in {t['id'] for t in publico.json()}
    assert tipo['id'] in {t['id'] for t in s.admin('GET', '/api/admin/tipos-ausencia').json()}
    validar_422(s.client.post('/api/portal/solicitudes', headers=s.headers, json={'tipo_ausencia_id': tipo['id'], 'fecha_inicio': '2035-06-10', 'fecha_fin': '2035-06-10'}), 'tipo_ausencia_id')
    eliminado = s.admin('DELETE', ruta)
    assert eliminado.status_code == 200
    assert eliminado.json() == {'eliminado': True}
    assert s.admin('GET', ruta).status_code == 404
    assert s.admin('PUT', ruta, json=datos).status_code == 404
    assert s.admin('DELETE', ruta).status_code == 404
    auditorias = s.db.execute("SELECT * FROM auditoria_modificacion WHERE entidad='tipos_ausencia' AND clave->>'id'=%s", (str(tipo['id']),)).fetchall()
    assert {'INSERT', 'UPDATE', 'DELETE'} <= {a['operacion'] for a in auditorias}
    assert all(a['actor_id'] == s.hr['id'] and a['creado_en'] is not None for a in auditorias)


@pytest.mark.parametrize('flujo,pasos', [
    ('JEFE_INMEDIATO', ['JEFE_INMEDIATO']),
    ('JEFE_Y_TALENTO_HUMANO', ['JEFE_INMEDIATO', 'TALENTO_HUMANO']),
    ('TALENTO_HUMANO', ['TALENTO_HUMANO']),
])
def test_hu_005_ca_02_asociacion_flujos_cerrados(escenario, flujo, pasos):
    s = escenario
    respuesta = s.admin('GET', '/api/admin/flujos')
    assert respuesta.status_code == 200
    flujos = {f['codigo']: f for f in respuesta.json()}
    assert set(flujos) == {'JEFE_INMEDIATO', 'JEFE_Y_TALENTO_HUMANO', 'TALENTO_HUMANO'}
    assert [p['rol_codigo'] for p in flujos[flujo]['pasos']] == pasos
    assert [p['orden'] for p in flujos[flujo]['pasos']] == list(range(1, len(pasos) + 1))
    tipo, datos = s.tipo(flujo)
    assert tipo['flujo_id'] == flujos[flujo]['id']
    ruta = f"/api/admin/tipos-ausencia/{tipo['id']}"
    asignado = s.admin('PUT', ruta + '/flujo', json={'flujo_codigo': flujo})
    assert asignado.status_code == 200
    assert asignado.json()['flujo_id'] == flujos[flujo]['id']
    detalle = s.admin('GET', ruta)
    assert detalle.status_code == 200
    assert detalle.json()['flujo_codigo'] == flujo
    validar_422(s.admin('PUT', ruta + '/flujo', json={'flujo_codigo': 'NO_DISPONIBLE'}), 'flujo_codigo')
    validar_422(s.admin('POST', '/api/admin/tipos-ausencia', json={**datos, 'nombre': uuid4().hex, 'flujo_codigo': 'NO_DISPONIBLE'}), 'flujo_codigo')
    assert s.admin('PUT', '/api/admin/tipos-ausencia/0/flujo', json={'flujo_codigo': flujo}).status_code == 404


def test_hu_005_ca_01_ca_02_tipo_en_uso_y_politica_capturada(escenario):
    # HU-005-CA-01, HU-005-CA-02; conserva las reglas de HU-001-CA-02.
    s = escenario
    tipo, datos = s.tipo(requiere_motivo=True, permite_horas=False)
    solicitud = s.crear(tipo['id'], motivo='Motivo original')
    politica_original = s.db.execute('SELECT * FROM solicitudes WHERE id=%s', (solicitud['id'],)).fetchone()
    ruta_tipo = f"/api/admin/tipos-ausencia/{tipo['id']}"
    assert s.admin('DELETE', ruta_tipo).status_code == 409
    cambios = {**datos, 'requiere_motivo': False, 'permite_horas': True, 'flujo_codigo': 'TALENTO_HUMANO'}
    assert s.admin('PUT', ruta_tipo, json=cambios).status_code == 200
    ruta = f"/api/portal/solicitudes/{solicitud['id']}"
    actual = s.client.get(ruta, headers=s.headers)
    assert actual.status_code == 200
    assert not {'requiere_motivo', 'permite_horas', 'flujo_id'} & actual.json().keys()
    persistida = s.db.execute('SELECT * FROM solicitudes WHERE id=%s', (solicitud['id'],)).fetchone()
    assert persistida['requiere_motivo'] is True
    assert persistida['permite_horas'] is False
    assert persistida['flujo_id'] == politica_original['flujo_id']
    edicion = {'version': 1, 'fecha_inicio': '2035-06-10', 'fecha_fin': '2035-06-10'}
    validar_422(s.client.put(ruta, headers=s.headers, json=edicion), 'motivo')
    validar_422(s.client.put(ruta, headers=s.headers, json={**edicion, 'motivo': 'Motivo', 'hora_inicio': '10:00:00', 'hora_fin': '11:00:00'}), 'hora_inicio')
    nueva = s.crear(tipo['id'], hora_inicio='10:00:00', hora_fin='11:00:00')
    politica_nueva = s.db.execute('SELECT * FROM solicitudes WHERE id=%s', (nueva['id'],)).fetchone()
    assert politica_nueva['requiere_motivo'] is False and politica_nueva['permite_horas'] is True
    assert politica_nueva['flujo_id'] != politica_original['flujo_id']
    assert s.admin('PUT', ruta_tipo, json={**cambios, 'estado': 'INACTIVO'}).status_code == 200


@pytest.mark.parametrize('ruta,administrativa', [
    ('/api/portal/solicitudes', False), ('/api/portal/notificaciones', False),
    ('/api/admin/solicitudes', True), ('/api/admin/notificaciones', True),
])
def test_hu_001_ca_04_hu_002_ca_01_hu_003_ca_01_limites_paginacion(escenario, ruta, administrativa):
    s = escenario

    def consultar(params):
        if administrativa:
            return s.admin('GET', ruta, actor=s.jefe, params=params)
        return s.client.get(ruta, headers=s.headers, params=params)

    for limite in [1, 100]:
        respuesta = consultar({'limite': limite, 'offset': 0})
        assert respuesta.status_code == 200
        assert len(respuesta.json()) <= limite
    for parametros, campo in [({'limite': 0}, 'limite'), ({'limite': 101}, 'limite'), ({'offset': -1}, 'offset')]:
        validar_422(consultar(parametros), campo)


def test_hu_001_ca_01_acceso_invalido_y_portal_sin_autenticacion(escenario):
    s = escenario
    assert s.client.post('/api/acceso', json={'documento': uuid4().hex}).status_code == 401
    validar_422(s.client.post('/api/acceso', json={'documento': ''}), 'documento')
    s.db.execute('UPDATE empleados SET activo=false WHERE id=%s', (s.otro['id'],))
    assert s.client.post('/api/acceso', json={'documento': s.otro['documento']}).status_code == 401
    assert s.client.get('/api/portal/me', headers=s.otros_headers).status_code == 401
    solicitud = s.crear()
    for ruta in ['/api/portal/me', '/api/portal/tipos-ausencia', '/api/portal/solicitudes', '/api/portal/notificaciones',
                 f"/api/portal/solicitudes/{solicitud['id']}", f"/api/portal/solicitudes/{solicitud['id']}/historial"]:
        assert s.client.get(ruta).status_code in {401, 403}
    assert s.client.get('/api/admin/solicitudes', headers=s.headers).status_code in {401, 403}