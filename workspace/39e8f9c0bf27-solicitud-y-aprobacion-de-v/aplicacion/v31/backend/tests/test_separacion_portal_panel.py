import os
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.main import app


ADMIN_RUTAS = [
    (ruta.path, metodo)
    for ruta in app.routes if ruta.path.startswith('/api/admin/')
    for metodo in sorted(ruta.methods or []) if metodo not in {'HEAD', 'OPTIONS'}
]


@pytest.fixture
def escenario(monkeypatch):
    # Fixture local para no importar otro módulo de pruebas.
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
        assert any(campo in error.get('loc', []) or error.get('loc') == ['body'] for error in detalle)
        assert all(isinstance(error.get('type'), str) and error['type'] for error in detalle)
    else:
        assert isinstance(detalle, str) and detalle.strip()


@pytest.mark.parametrize('ruta,metodo', ADMIN_RUTAS)
def test_hu_003_ca_04_hu_004_ca_03_hu_005_ca_01_token_portal_no_autoriza_panel(escenario, ruta, metodo):
    s = escenario
    tipo, datos_tipo = s.tipo()
    solicitud = s.crear(tipo['id'])
    ruta = ruta.replace('{solicitud_id}', str(solicitud['id'])).replace('{tipo_id}', str(tipo['id']))
    datos = None
    if metodo in {'POST', 'PUT'}:
        datos = {**datos_tipo, 'nombre': 'QA-' + uuid4().hex}
    if ruta.endswith('/decisiones'):
        datos = {'version': solicitud['version'], 'accion': 'APROBAR'}
    elif ruta.endswith('/flujo'):
        datos = {'flujo_codigo': 'JEFE_INMEDIATO'}
    respuesta = s.client.request(metodo, ruta, headers=s.headers, json=datos)
    assert respuesta.status_code in {401, 403}, respuesta.text
    # Ninguna credencial del portal puede modificar datos administrativos.
    actual = s.client.get(f"/api/portal/solicitudes/{solicitud['id']}", headers=s.headers)
    assert actual.status_code == 200
    assert actual.json()['version'] == solicitud['version']
    detalle_tipo = s.admin('GET', f"/api/admin/tipos-ausencia/{tipo['id']}")
    assert detalle_tipo.status_code == 200
    assert detalle_tipo.json()['nombre'] == datos_tipo['nombre']


def test_hu_001_ca_04_hu_003_ca_01_listados_y_detalles_separados(escenario):
    s = escenario
    propia = s.crear()
    ajena = s.crear(usuario=s.otros_headers)
    portal = s.client.get('/api/portal/solicitudes', headers=s.headers)
    panel = s.admin('GET', '/api/admin/solicitudes', actor=s.jefe)
    assert portal.status_code == panel.status_code == 200
    assert {fila['id'] for fila in portal.json()} == {propia['id']}
    assert all('solicitante_id' not in fila for fila in portal.json())
    for fila in portal.json():
        persistida = s.db.execute('SELECT solicitante_id FROM solicitudes WHERE id=%s', (fila['id'],)).fetchone()
        assert persistida['solicitante_id'] == s.titular['id']
    assert propia['id'] in {fila['id'] for fila in panel.json()}
    assert ajena['id'] not in {fila['id'] for fila in panel.json()}
    resumen = next(fila for fila in portal.json() if fila['id'] == propia['id'])
    administrativo = next(fila for fila in panel.json() if fila['id'] == propia['id'])
    internos = {'solicitante_id', 'flujo_id', 'requiere_motivo', 'permite_horas', 'requiere_revision_adicional'}
    assert not internos & resumen.keys()
    assert internos <= administrativo.keys()
    for solicitud in [propia, ajena]:
        ruta = f"/api/portal/solicitudes/{solicitud['id']}"
        for sufijo in ['', '/historial']:
            assert s.client.get(ruta + sufijo).status_code in {401, 403}
    for sufijo in ['', '/historial']:
        assert s.client.get(f"/api/portal/solicitudes/{ajena['id']}" + sufijo, headers=s.headers).status_code == 404
        assert s.client.get(f"/api/portal/solicitudes/{propia['id']}" + sufijo, headers=s.otros_headers).status_code == 404
        autorizado = s.admin('GET', f"/api/admin/solicitudes/{propia['id']}" + sufijo, actor=s.jefe)
        assert autorizado.status_code == 200
        assert s.admin('GET', f"/api/admin/solicitudes/{ajena['id']}" + sufijo, actor=s.jefe).status_code == 404
    detalle = s.client.get(f"/api/portal/solicitudes/{propia['id']}", headers=s.headers)
    assert detalle.status_code == 200
    assert not (internos | {'solicitante', 'revisiones'}) & detalle.json().keys()
    detalle_admin = s.admin('GET', f"/api/admin/solicitudes/{propia['id']}", actor=s.jefe)
    assert detalle_admin.status_code == 200
    assert detalle_admin.json()['solicitante']['id'] == s.titular['id']
    assert detalle_admin.json()['revisiones']
    s.decidir(propia, 'APROBAR', observacion='Revisión ' + uuid4().hex)
    historia_portal = s.client.get(f"/api/portal/solicitudes/{propia['id']}/historial", headers=s.headers)
    historia_panel = s.admin('GET', f"/api/admin/solicitudes/{propia['id']}/historial", actor=s.jefe)
    assert historia_portal.status_code == historia_panel.status_code == 200
    for coleccion in ['historial', 'observaciones', 'decisiones']:
        assert historia_portal.json()[coleccion]
        assert historia_panel.json()[coleccion]
        for fila in historia_portal.json()[coleccion]:
            assert not {'id', 'actor_id', 'solicitud_id', 'revision_id', 'aprobacion_id'} & fila.keys()
        assert all('actor_id' in fila for fila in historia_panel.json()[coleccion])
    assert historia_portal.json()['decisiones'][0]['accion'] == 'APROBAR'
    assert historia_portal.json()['observaciones'][0]['texto'] == historia_panel.json()['observaciones'][0]['texto']


def test_hu_001_ca_03_hu_005_ca_01_catalogo_portal_solo_activo(escenario):
    s = escenario
    activo, _ = s.tipo()
    inactivo, _ = s.tipo(estado='INACTIVO')
    assert s.client.get('/api/portal/tipos-ausencia').status_code in {401, 403}
    portal = s.client.get('/api/portal/tipos-ausencia', headers=s.headers)
    panel = s.admin('GET', '/api/admin/tipos-ausencia')
    assert portal.status_code == panel.status_code == 200
    ids_portal = {tipo['id'] for tipo in portal.json()}
    ids_panel = {tipo['id'] for tipo in panel.json()}
    assert activo['id'] in ids_portal
    assert inactivo['id'] not in ids_portal
    assert {activo['id'], inactivo['id']} <= ids_panel
    assert all(set(tipo) == {'id', 'nombre', 'requiere_motivo', 'permite_horas'} for tipo in portal.json())
    estados = s.db.execute('SELECT id, estado FROM tipos_ausencia WHERE id = ANY(%s)', (list(ids_portal),)).fetchall()
    assert {fila['id'] for fila in estados} == ids_portal
    assert all(fila['estado'] == 'ACTIVO' for fila in estados)
    assert all({'estado', 'flujo_id', 'flujo_codigo'} <= tipo.keys() for tipo in panel.json())
    datos = {'tipo_ausencia_id': inactivo['id'], 'fecha_inicio': '2035-06-10', 'fecha_fin': '2035-06-10'}
    validar_422(s.client.post('/api/portal/solicitudes', headers=s.headers, json=datos), 'tipo_ausencia_id')


def test_hu_002_ca_01_ca_02_notificaciones_portal_no_son_bandeja_administrativa(escenario):
    # HU-002-CA-01, HU-002-CA-02.
    s = escenario
    solicitud = s.crear()
    pendientes = s.admin('GET', '/api/admin/notificaciones', actor=s.jefe)
    assert pendientes.status_code == 200
    avisos_revision = [aviso for aviso in pendientes.json() if aviso['solicitud_id'] == solicitud['id']]
    assert avisos_revision
    assert all(aviso['tipo'] == 'PENDIENTE_REVISION' for aviso in avisos_revision)
    s.decidir(solicitud, 'APROBAR')
    assert s.client.get('/api/portal/notificaciones').status_code in {401, 403}
    portal = s.client.get('/api/portal/notificaciones', headers=s.headers)
    otros = s.client.get('/api/portal/notificaciones', headers=s.otros_headers)
    assert portal.status_code == otros.status_code == 200
    cambios = [aviso for aviso in portal.json() if aviso['solicitud_id'] == solicitud['id']]
    assert len(cambios) == 1
    assert cambios[0]['tipo'] == 'CAMBIO_ESTADO'
    assert cambios[0]['estado_nuevo'] == 'APROBADA'
    assert all(aviso['tipo'] == 'CAMBIO_ESTADO' for aviso in portal.json())
    assert solicitud['id'] not in {aviso['solicitud_id'] for aviso in otros.json()}
    ids_revision = {aviso['id'] for aviso in avisos_revision}
    assert not ids_revision & {aviso['id'] for aviso in portal.json()}
    for aviso in avisos_revision:
        respuesta = s.client.patch(f"/api/portal/notificaciones/{aviso['id']}/leida", headers=s.headers)
        assert respuesta.status_code == 404
    respuesta = s.client.patch(f"/api/portal/notificaciones/{cambios[0]['id']}/leida", headers=s.otros_headers)
    assert respuesta.status_code == 404


@pytest.mark.parametrize('ruta,administrativa', [('/api/portal/solicitudes', False), ('/api/admin/solicitudes', True)])
def test_hu_001_ca_04_hu_003_ca_01_estado_malicioso_rechazado_sin_alterar_datos(escenario, ruta, administrativa):
    s = escenario
    solicitud = s.crear()
    parametros = {'estado': "ENVIADA' OR '1'='1"}
    if administrativa:
        respuesta = s.admin('GET', ruta, actor=s.jefe, params=parametros)
    else:
        respuesta = s.client.get(ruta, headers=s.headers, params=parametros)
    validar_422(respuesta, 'estado')
    detalle = s.client.get(f"/api/portal/solicitudes/{solicitud['id']}", headers=s.headers)
    assert detalle.status_code == 200
    assert detalle.json()['estado_codigo'] == 'ENVIADA'
    assert detalle.json()['version'] == solicitud['version']