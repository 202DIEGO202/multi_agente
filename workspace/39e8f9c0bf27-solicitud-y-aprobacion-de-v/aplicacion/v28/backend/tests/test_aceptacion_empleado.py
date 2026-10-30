import os
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import get_employee_identity
from .test_aceptacion_ausencias import correcto, validacion
from .test_aceptacion_ausencias import e as escenario_admin


@pytest.fixture
def empleado(escenario_admin):
    return SesionesEmpleado(escenario_admin)


class SesionesEmpleado:
    def __init__(self, escenario):
        self.e = escenario

    @contextmanager
    def sesion(self, actor='empleado'):
        # Solo se sustituye el proveedor externo; permisos y PostgreSQL son reales.
        identity = self.e.usuarios[actor]['identidad_externa']

        def identidad_verificada():
            return identity

        original = dict(app.dependency_overrides)
        app.dependency_overrides[get_employee_identity] = identidad_verificada
        try:
            with TestClient(app) as client:
                yield client
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(original)

    def api(self, method, path, actor='empleado', **kwargs):
        with self.sesion(actor) as client:
            return client.request(method, '/api/empleado' + path, **kwargs)

    def crear(self, tipo=None, actor='empleado', **changes):
        tipo = tipo or self.e.tipo()
        return correcto(self.api('POST', '/solicitudes', actor=actor,
                                 json=self.e.datos_solicitud(tipo, **changes)), 201)


RUTAS_EMPLEADO = [
    ('GET', '/identidad'),
    ('GET', '/tipos-ausencia'),
    ('POST', '/solicitudes'),
    ('GET', '/solicitudes'),
    ('GET', '/solicitudes/1'),
    ('GET', '/solicitudes/1/historial'),
    ('GET', '/notificaciones'),
]


@pytest.mark.parametrize('method,path', RUTAS_EMPLEADO)
def test_hu_001_ca_04_hu_002_ca_01_sesion_obligatoria_sin_token_administrativo(method, path):
    # HU-001-CA-04 y HU-002-CA-01.
    with TestClient(app) as client:
        response = client.request(method, '/api/empleado' + path, json={})
        assert response.status_code == 401, response.text
        response = client.request(method, '/api/empleado' + path, json={},
                                  headers={'Authorization': 'Bearer ' + os.environ['ADMIN_API_TOKEN']})
        assert response.status_code == 401, response.text


@pytest.mark.parametrize('origen', ['PORTAL', 'FORMATO_OFICIAL'])
def test_hu_001_ca_01_registro_empleado_sin_credenciales_administrativas(empleado, origen):
    e = empleado.e
    tipo = e.tipo()
    extra = {'origen': origen}
    if origen == 'FORMATO_OFICIAL':
        extra['referencia_formato'] = 'QA-' + uuid4().hex
    solicitud = empleado.crear(tipo, **extra)
    assert solicitud['estado_codigo'] == 'EN_REVISION'
    assert solicitud['solicitante_id'] == e.usuarios['empleado']['id']
    assert solicitud['origen'] == origen
    assert e.revision(solicitud)['aprobador_id'] == e.usuarios['jefe']['id']
    e.modificaciones('empleado', 'solicitudes', solicitud['id'], 'INSERT')
    body = e.datos_solicitud(tipo, solicitante_id=e.usuarios['otro']['id'])
    validacion(empleado.api('POST', '/solicitudes', json=body), 'solicitante_id')
    validacion(empleado.api('POST', '/solicitudes',
                           json=e.datos_solicitud(tipo, origen='FORMATO_OFICIAL')), 'referencia_formato')
    identidad = correcto(empleado.api('GET', '/identidad',
                                     params={'identidad_externa': e.usuarios['otro']['identidad_externa']}))
    assert identidad == {'id': e.usuarios['empleado']['id'], 'nombre': e.usuarios['empleado']['nombre']}
    assert empleado.api('GET', '/identidad', actor='th').status_code == 403


@pytest.mark.parametrize('requiere', [False, True])
def test_hu_001_ca_02_motivo_y_reglas_backend_en_ruta_empleado(empleado, requiere):
    tipo = empleado.e.tipo(requiere_motivo=requiere)
    motivo = 'Observación ' + uuid4().hex
    solicitud = empleado.crear(tipo, motivo=motivo)
    detalle = correcto(empleado.api('GET', f"/solicitudes/{solicitud['id']}"))
    assert detalle['motivo'] == motivo
    body = empleado.e.datos_solicitud(tipo)
    if requiere:
        validacion(empleado.api('POST', '/solicitudes', json=body), 'motivo')
    else:
        assert empleado.crear(tipo)['motivo'] is None
    validacion(empleado.api('POST', '/solicitudes', json=dict(body, motivo='   ')), 'motivo')


@pytest.mark.parametrize('modalidad', ['NO_APLICA', 'OPCIONAL', 'OBLIGATORIA'])
def test_hu_001_ca_03_catalogo_autorizado_fechas_y_horas(empleado, modalidad):
    e = empleado.e
    tipo = e.tipo(nombre='!QA-' + uuid4().hex, modalidad_horas=modalidad)
    catalogo = correcto(empleado.api('GET', '/tipos-ausencia', params={'limit': 100}))
    elegido = next(row for row in catalogo if row['id'] == tipo['id'])
    assert set(elegido) == {'id', 'nombre', 'requiere_motivo', 'modalidad_horas'}
    assert elegido['modalidad_horas'] == modalidad
    horas = {} if modalidad == 'NO_APLICA' else {'hora_inicio': '00:00:00', 'hora_fin': '23:59:59'}
    solicitud = empleado.crear(tipo, **horas)
    detalle = correcto(empleado.api('GET', f"/solicitudes/{solicitud['id']}"))
    assert detalle['tipo_ausencia_id'] == tipo['id']
    assert detalle['fecha_inicio'] == detalle['fecha_fin'] == '2037-06-10'
    for campo, valor in horas.items():
        assert detalle[campo] == valor
    body = e.datos_solicitud(tipo)
    if modalidad == 'NO_APLICA':
        validacion(empleado.api('POST', '/solicitudes',
                               json=dict(body, hora_inicio='08:00:00', hora_fin='09:00:00')), 'hora_inicio')
    elif modalidad == 'OBLIGATORIA':
        validacion(empleado.api('POST', '/solicitudes', json=body), 'hora_inicio')
    else:
        assert empleado.crear(tipo)['hora_inicio'] is None
    validacion(empleado.api('POST', '/solicitudes',
                           json=dict(body, fecha_fin='2037-06-09')), 'fecha_fin')
    validacion(empleado.api('POST', '/solicitudes',
                           json=dict(body, hora_inicio='08:00:00', hora_fin='08:00:00')), 'hora_fin')


def test_hu_001_ca_04_seguimiento_propio_historial_sin_identidades_ajenas(empleado):
    e = empleado.e
    solicitud = empleado.crear()
    ajena = empleado.crear(actor='otro')
    correcto(e.decidir(solicitud, 'APROBAR'))
    detalle = correcto(empleado.api('GET', f"/solicitudes/{solicitud['id']}"))
    assert detalle['estado_codigo'] == 'APROBADA'
    historial = correcto(empleado.api('GET', f"/solicitudes/{solicitud['id']}/historial"))
    assert historial[-1]['estado_nuevo'] == 'APROBADA'
    assert all(row['creado_en'] and row['operacion'] for row in historial)
    assert all('actor_id' not in row and 'aprobador_id' not in row for row in historial)
    assert len({row['version'] for row in historial}) == len(historial)
    propias = correcto(empleado.api('GET', '/solicitudes',
                                   params={'estado': 'APROBADA', 'solicitante_id': e.usuarios['otro']['id']}))
    assert solicitud['id'] in {row['id'] for row in propias}
    assert ajena['id'] not in {row['id'] for row in propias}
    assert all(row['solicitante_id'] == e.usuarios['empleado']['id'] for row in propias)
    for suffix in ('', '/historial'):
        assert empleado.api('GET', f"/solicitudes/{ajena['id']}" + suffix).status_code == 404
        assert empleado.api('GET', f"/solicitudes/{solicitud['id']}" + suffix, actor='otro').status_code == 404
    e.acceso('empleado', solicitud, 'CONSULTA_DETALLE')
    e.acceso('empleado', solicitud, 'CONSULTA_HISTORIAL')
    validacion(empleado.api('GET', '/solicitudes', params={'estado': 'INVALIDO'}), 'estado')
    validacion(empleado.api('GET', '/solicitudes/0'), 'solicitud_id')


def test_hu_002_ca_01_notificaciones_empleado_aisladas_por_sesion(empleado):
    e = empleado.e
    solicitud = empleado.crear()
    correcto(e.decidir(solicitud, 'RECHAZAR', observacion='QA ' + uuid4().hex))
    avisos = correcto(empleado.api('GET', '/notificaciones'))
    propios = [row for row in avisos if row['solicitud_id'] == solicitud['id']]
    assert {'EN_REVISION', 'RECHAZADA'} <= {row['estado_notificado'] for row in propios}
    assert all(row['tipo'] == 'CAMBIO_ESTADO' and row['creado_en'] for row in propios)
    assert all('destinatario_id' not in row and 'correo' not in row for row in avisos)
    otros = correcto(empleado.api('GET', '/notificaciones', actor='otro',
                                 params={'destinatario_id': e.usuarios['empleado']['id']}))
    assert not any(row['solicitud_id'] == solicitud['id'] for row in otros)
    validacion(empleado.api('GET', '/notificaciones', params={'limit': 101}), 'limit')


def test_hu_002_ca_02_registro_empleado_notifica_al_aprobador_activo(empleado):
    e = empleado.e
    solicitud = empleado.crear(e.tipo(flujo='JEFE_TH'))
    avisos = correcto(e.api('GET', '/mis-notificaciones', actor='jefe'))
    assert any(row['solicitud_id'] == solicitud['id'] and row['tipo'] == 'PENDIENTE_REVISION' for row in avisos)
    assert not any(row['solicitud_id'] == solicitud['id'] for row in correcto(e.api('GET', '/mis-notificaciones')))
    correcto(e.decidir(solicitud, 'APROBAR'))
    avisos_th = correcto(e.api('GET', '/mis-notificaciones'))
    assert any(row['solicitud_id'] == solicitud['id'] and row['tipo'] == 'PENDIENTE_REVISION' for row in avisos_th)
    revision = e.revision(solicitud, 2)
    rows = e.filas('SELECT id FROM notificaciones WHERE aprobacion_id = %s AND destinatario_id = %s',
                   (revision['id'], e.usuarios['th']['id']))
    assert len(rows) == 1
    assert empleado.api('GET', '/notificaciones', actor='jefe').status_code == 403


@pytest.mark.parametrize('params,campo', [({'limit': 0}, 'limit'), ({'limit': 101}, 'limit'), ({'offset': -1}, 'offset')])
def test_hu_001_ca_03_ca_04_hu_002_ca_01_limites_listas_empleado(empleado, params, campo):
    # HU-001-CA-03, HU-001-CA-04 y HU-002-CA-01.
    solicitud = empleado.crear()
    for ruta in ('/tipos-ausencia', '/solicitudes', '/notificaciones',
                 f"/solicitudes/{solicitud['id']}/historial"):
        validacion(empleado.api('GET', ruta, params=params), campo)
        for limit in (1, 100):
            rows = correcto(empleado.api('GET', ruta, params={'limit': limit, 'offset': 0}))
            assert isinstance(rows, list) and len(rows) <= limit


def test_hu_005_ca_01_ca_02_catalogo_empleado_no_administrable(empleado):
    # HU-005-CA-01 y HU-005-CA-02: administración exclusiva del panel.
    e = empleado.e
    tipo = e.tipo()
    body = {'nombre': 'QA-' + uuid4().hex, 'flujo': 'TH', 'version': tipo['version']}
    with empleado.sesion() as client:
        for method, ruta in [('POST', '/api/empleado/tipos-ausencia'),
                             ('PUT', f"/api/empleado/tipos-ausencia/{tipo['id']}"),
                             ('DELETE', f"/api/empleado/tipos-ausencia/{tipo['id']}"),
                             ('PUT', f"/api/empleado/tipos-ausencia/{tipo['id']}/flujo")]:
            response = client.request(method, ruta, json=body)
            assert response.status_code in (404, 405), response.text
        for method, ruta in [('GET', '/api/admin/flujos'),
                             ('POST', '/api/admin/tipos-ausencia'),
                             ('PUT', f"/api/admin/tipos-ausencia/{tipo['id']}/flujo")]:
            response = client.request(method, ruta, json=body)
            assert response.status_code in (401, 403), response.text
    assert correcto(e.api('GET', f"/tipos-ausencia/{tipo['id']}"))['version'] == tipo['version']