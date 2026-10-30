import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.main import app


BASE = '/api/admin'


def correcto(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def validacion(response, campo=None):
    assert response.status_code == 422, response.text
    detail = response.json()['detail']
    if isinstance(detail, list):
        assert detail
        assert all(isinstance(error.get('type'), str) and error['type'] for error in detail)
        assert all(isinstance(error.get('loc'), list) for error in detail)
        if campo:
            assert any(campo in error['loc'] or error['loc'] == ['body'] for error in detail)
    else:
        # Las reglas del servicio pueden devolver una descripción no estructurada.
        assert isinstance(detail, (str, dict)) and detail


class Escenario:
    def __init__(self, db, client, monkeypatch, usuarios):
        self.db = db
        self.client = client
        self.monkeypatch = monkeypatch
        self.usuarios = usuarios

    def api(self, method, path, actor='th', **kwargs):
        self.monkeypatch.setenv('ADMIN_ACTOR_EXTERNAL_ID', self.usuarios[actor]['identidad_externa'])
        return self.client.request(method, BASE + path, **kwargs)

    def fila(self, sql, params=()):
        return self.db.execute(sql, params).fetchone()

    def filas(self, sql, params=()):
        return self.db.execute(sql, params).fetchall()

    def tipo(self, **changes):
        body = dict(nombre='QA-' + uuid4().hex, estado='ACTIVO', flujo='JEFE',
                    requiere_motivo=False, modalidad_horas='OPCIONAL')
        body.update(changes)
        return correcto(self.api('POST', '/tipos-ausencia', json=body), 201)

    def datos_solicitud(self, tipo, **changes):
        body = dict(tipo_ausencia_id=tipo['id'], origen='PORTAL',
                    fecha_inicio='2037-06-10', fecha_fin='2037-06-10')
        body.update(changes)
        return body

    def solicitud(self, tipo=None, actor='empleado', **changes):
        tipo = tipo or self.tipo()
        return correcto(self.api('POST', '/mis-solicitudes', actor=actor,
                                 json=self.datos_solicitud(tipo, **changes)), 201)

    def detalle(self, solicitud, actor='empleado'):
        return correcto(self.api('GET', f"/solicitudes/{solicitud['id']}", actor=actor))

    def revision(self, solicitud, orden=1):
        return self.fila('SELECT * FROM aprobaciones WHERE solicitud_id = %s AND orden = %s',
                         (solicitud['id'], orden))

    def versiones(self, solicitud, revision):
        s = self.fila('SELECT version FROM solicitudes WHERE id = %s', (solicitud['id'],))
        a = self.fila('SELECT version FROM aprobaciones WHERE id = %s', (revision['id'],))
        return dict(version_solicitud=s['version'], version_revision=a['version'])

    def decidir(self, solicitud, accion, actor='jefe', orden=1, **changes):
        revision = self.revision(solicitud, orden)
        body = dict(self.versiones(solicitud, revision), accion=accion)
        body.update(changes)
        return self.api('POST', f"/revisiones/{revision['id']}/decision", actor=actor, json=body)

    def acceso(self, actor, solicitud, operacion, autorizado=True):
        rows = self.filas('SELECT * FROM auditoria_acceso WHERE actor_id = %s '
                         'AND solicitud_id = %s AND operacion = %s AND autorizado = %s',
                         (self.usuarios[actor]['id'], solicitud['id'], operacion, autorizado))
        assert rows
        assert all(row['creado_en'] and row['recurso'] for row in rows)

    def modificaciones(self, actor, entidad, ident, operacion=None):
        rows = self.filas('SELECT * FROM auditoria_modificacion WHERE actor_id = %s '
                         "AND entidad = %s AND clave->>'id' = %s",
                         (self.usuarios[actor]['id'], entidad, str(ident)))
        if operacion:
            rows = [row for row in rows if row['operacion'] == operacion]
        assert rows
        assert all(row['creado_en'] for row in rows)
        return rows


@pytest.fixture
def e(monkeypatch):
    # No se sustituye la persistencia ni la autorización. Solo se evita SMTP.
    import app.routers as routers
    monkeypatch.setattr(routers, 'process_notifications', lambda limit=100: 0)
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as db:
        usuarios = {}
        with db.transaction():
            for alias, roles in [('th', ['TALENTO_HUMANO']),
                                 ('jefe', ['JEFE_INMEDIATO']),
                                 ('empleado', ['EMPLEADO']),
                                 ('otro', ['EMPLEADO'])]:
                unique = uuid4().hex
                ident = db.execute("SELECT nextval(pg_get_serial_sequence('usuarios', 'id')) AS id").fetchone()['id']
                if not usuarios:
                    db.execute("SELECT set_config('app.usuario_id', %s, true)", (str(ident),))
                jefe_id = usuarios['jefe']['id'] if alias in ('empleado', 'otro') else None
                row = db.execute('INSERT INTO usuarios '
                                 '(id, identidad_externa, nombre, documento, correo, area, cargo, jefe_inmediato_id) '
                                 'OVERRIDING SYSTEM VALUE VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *',
                                 (ident, 'qa-' + unique, 'QA ' + alias, unique,
                                  unique + '@example.invalid', 'QA', alias, jefe_id)).fetchone()
                usuarios[alias] = row
                for rol in roles:
                    db.execute('INSERT INTO usuarios_roles(usuario_id, rol_codigo) VALUES (%s, %s)', (ident, rol))
        monkeypatch.setenv('TH_APPROVER_EXTERNAL_ID', usuarios['th']['identidad_externa'])
        with TestClient(app, headers={'Authorization': 'Bearer ' + os.environ['ADMIN_API_TOKEN']}) as client:
            yield Escenario(db, client, monkeypatch, usuarios)
    # Los registros auditados se conservan; cada escenario usa identidades únicas.


def test_health_publico_200():
    with TestClient(app) as client:
        assert correcto(client.get('/api/health')) == {'estado': 'ok'}


ADMIN_OPERACIONES = [
    (route.path, method)
    for route in app.routes
    if getattr(route, 'path', '').startswith(BASE + '/')
    for method in sorted(getattr(route, 'methods', set()) - {'HEAD', 'OPTIONS'})
]


@pytest.mark.parametrize('path,method', ADMIN_OPERACIONES)
def test_todas_las_rutas_administrativas_sin_token(path, method):
    # HU-001-CA-04, HU-003-CA-04, HU-004-CA-03, HU-005-CA-01.
    path = path.replace('{tipo_id}', '1').replace('{solicitud_id}', '1').replace('{revision_id}', '1')
    with TestClient(app) as client:
        response = client.request(method, path, params={'version': 1}, json={})
    assert response.status_code in (401, 403), response.text


def test_hu_005_ca_01_catalogo_ciclo_completo_duplicados_y_versiones(e):
    identidad = correcto(e.api('GET', '/identidad'))
    assert identidad['id'] == e.usuarios['th']['id']
    assert 'TALENTO_HUMANO' in identidad['roles']
    tipo = e.tipo()
    detalle = correcto(e.api('GET', f"/tipos-ausencia/{tipo['id']}"))
    assert detalle['nombre'] == tipo['nombre']
    assert detalle['flujo'] == 'JEFE'
    body = dict(nombre=tipo['nombre'].upper(), estado='ACTIVO', flujo='JEFE',
                requiere_motivo=False, modalidad_horas='OPCIONAL')
    assert e.api('POST', '/tipos-ausencia', json=body).status_code == 409
    body.update(nombre='QA-edicion-' + uuid4().hex, estado='INACTIVO', version=tipo['version'])
    actualizado = correcto(e.api('PUT', f"/tipos-ausencia/{tipo['id']}", json=body))
    assert actualizado['version'] == tipo['version'] + 1
    assert actualizado['estado'] == 'INACTIVO'
    assert e.api('PUT', f"/tipos-ausencia/{tipo['id']}", json=body).status_code == 409
    assert e.api('DELETE', f"/tipos-ausencia/{tipo['id']}", params={'version': tipo['version']}).status_code == 409
    eliminado = correcto(e.api('DELETE', f"/tipos-ausencia/{tipo['id']}", params={'version': actualizado['version']}))
    assert eliminado == {'eliminado': True, 'id': tipo['id']}
    assert e.api('GET', f"/tipos-ausencia/{tipo['id']}").status_code == 404
    for operacion in ('INSERT', 'UPDATE', 'DELETE'):
        e.modificaciones('th', 'tipos_ausencia', tipo['id'], operacion)


@pytest.mark.parametrize('campo,valor', [('nombre', ''), ('estado', 'DESCONOCIDO'),
                                        ('flujo', 'DESCONOCIDO'), ('modalidad_horas', 'DESCONOCIDA')])
def test_hu_005_ca_01_ca_02_catalogo_validacion(e, campo, valor):
    # HU-005-CA-01 y HU-005-CA-02.
    body = dict(nombre='QA-' + uuid4().hex, estado='ACTIVO', flujo='JEFE',
                requiere_motivo=False, modalidad_horas='OPCIONAL')
    body[campo] = valor
    validacion(e.api('POST', '/tipos-ausencia', json=body), campo)


@pytest.mark.parametrize('flujo', ['JEFE', 'JEFE_TH', 'TH'])
def test_hu_005_ca_02_asignacion_de_flujos_cerrados(e, flujo):
    flujos = correcto(e.api('GET', '/flujos'))
    assert {'JEFE', 'JEFE_TH', 'TH'} <= {row['codigo'] for row in flujos}
    tipo = e.tipo()
    body = {'flujo': flujo, 'version': tipo['version']}
    nuevo = correcto(e.api('PUT', f"/tipos-ausencia/{tipo['id']}/flujo", json=body))
    assert nuevo['version'] == tipo['version'] + 1
    detalle = correcto(e.api('GET', f"/tipos-ausencia/{tipo['id']}"))
    assert detalle['flujo'] == flujo
    assert e.api('PUT', f"/tipos-ausencia/{tipo['id']}/flujo", json=body).status_code == 409
    validacion(e.api('PUT', f"/tipos-ausencia/{tipo['id']}/flujo",
                     json={'flujo': 'INVALIDO', 'version': nuevo['version']}), 'flujo')
    validacion(e.api('PUT', f"/tipos-ausencia/{tipo['id']}/flujo",
                     json={'flujo': flujo, 'version': 0}), 'version')


def test_hu_005_ca_01_tipo_utilizado_desactivacion_y_reglas_conservadas(e):
    tipo = e.tipo(requiere_motivo=True, modalidad_horas='OBLIGATORIA')
    solicitud = e.solicitud(tipo, motivo='Motivo ' + uuid4().hex,
                            hora_inicio='08:00:00', hora_fin='09:00:00')
    assert e.api('DELETE', f"/tipos-ausencia/{tipo['id']}", params={'version': tipo['version']}).status_code == 409
    body = dict(nombre=tipo['nombre'], estado='INACTIVO', flujo='TH',
                requiere_motivo=False, modalidad_horas='NO_APLICA', version=tipo['version'])
    correcto(e.api('PUT', f"/tipos-ausencia/{tipo['id']}", json=body))
    detalle = e.detalle(solicitud)
    assert detalle['flujo_id'] == solicitud['flujo_id']
    assert detalle['requiere_motivo'] is True
    assert detalle['modalidad_horas'] == 'OBLIGATORIA'
    assert detalle['aprobaciones'][0]['aprobador_id'] == e.usuarios['jefe']['id']
    before = e.fila('SELECT count(*) AS n FROM solicitudes WHERE solicitante_id = %s', (e.usuarios['empleado']['id'],))['n']
    validacion(e.api('POST', '/mis-solicitudes', actor='empleado', json=e.datos_solicitud(tipo)), 'tipo_ausencia_id')
    assert e.fila('SELECT count(*) AS n FROM solicitudes WHERE solicitante_id = %s', (e.usuarios['empleado']['id'],))['n'] == before
    assert all(row['estado'] == 'ACTIVO' for row in correcto(e.api('GET', '/tipos-ausencia', actor='empleado')))


@pytest.mark.parametrize('origen', ['PORTAL', 'FORMATO_OFICIAL'])
def test_hu_001_ca_01_registrar_y_enviar_por_ambos_origenes(e, origen):
    extra = {'origen': origen}
    if origen == 'FORMATO_OFICIAL':
        extra['referencia_formato'] = 'REF-' + uuid4().hex
    solicitud = e.solicitud(**extra)
    assert solicitud['estado_codigo'] == 'EN_REVISION'
    assert solicitud['solicitante_id'] == e.usuarios['empleado']['id']
    assert solicitud['origen'] == origen
    assert solicitud['version'] > 0
    revision = e.revision(solicitud)
    assert revision['estado'] == 'PENDIENTE'
    assert revision['aprobador_id'] == e.usuarios['jefe']['id']
    e.modificaciones('empleado', 'solicitudes', solicitud['id'], 'INSERT')
    historial = e.filas('SELECT * FROM historial_solicitud WHERE solicitud_id = %s ORDER BY version', (solicitud['id'],))
    versiones = e.filas('SELECT * FROM versiones WHERE solicitud_id = %s ORDER BY numero', (solicitud['id'],))
    assert historial[0]['operacion'] == 'CREACION'
    assert historial[-1]['estado_nuevo'] == 'EN_REVISION'
    assert [row['version'] for row in historial] == [row['numero'] for row in versiones]
    assert all(row['actor_id'] == e.usuarios['empleado']['id'] for row in historial)
    invalid = e.datos_solicitud(e.tipo(), origen='FORMATO_OFICIAL')
    validacion(e.api('POST', '/mis-solicitudes', actor='empleado', json=invalid), 'referencia_formato')


@pytest.mark.parametrize('requiere', [False, True])
def test_hu_001_ca_02_motivo_persistido_y_obligatoriedad_backend(e, requiere):
    tipo = e.tipo(requiere_motivo=requiere)
    motivo = 'Observación ' + uuid4().hex
    solicitud = e.solicitud(tipo, motivo=motivo)
    assert e.detalle(solicitud)['motivo'] == motivo
    if requiere:
        validacion(e.api('POST', '/mis-solicitudes', actor='empleado', json=e.datos_solicitud(tipo)), 'motivo')
    else:
        assert e.solicitud(tipo)['motivo'] is None
    validacion(e.api('POST', '/mis-solicitudes', actor='empleado',
                     json=e.datos_solicitud(tipo, motivo='   ')), 'motivo')


@pytest.mark.parametrize('modalidad', ['NO_APLICA', 'OPCIONAL', 'OBLIGATORIA'])
def test_hu_001_ca_03_fechas_horas_y_modalidad(e, modalidad):
    tipo = e.tipo(modalidad_horas=modalidad)
    horas = {} if modalidad == 'NO_APLICA' else {'hora_inicio': '00:00:00', 'hora_fin': '23:59:59'}
    solicitud = e.solicitud(tipo, **horas)
    detalle = e.detalle(solicitud)
    assert detalle['tipo_ausencia_id'] == tipo['id']
    assert detalle['fecha_inicio'] == detalle['fecha_fin'] == '2037-06-10'
    for campo, valor in horas.items():
        assert detalle[campo] == valor
    if modalidad == 'NO_APLICA':
        validacion(e.api('POST', '/mis-solicitudes', actor='empleado',
                         json=e.datos_solicitud(tipo, hora_inicio='08:00:00', hora_fin='09:00:00')), 'hora_inicio')
    elif modalidad == 'OBLIGATORIA':
        validacion(e.api('POST', '/mis-solicitudes', actor='empleado', json=e.datos_solicitud(tipo)), 'hora_inicio')
    else:
        assert e.solicitud(tipo)['hora_inicio'] is None


@pytest.mark.parametrize('changes,campo', [
    ({'fecha_fin': '2037-06-09'}, 'fecha_fin'),
    ({'fecha_inicio': 'no-es-fecha'}, 'fecha_inicio'),
    ({'hora_inicio': '08:00:00'}, 'hora_fin'),
    ({'hora_inicio': '08:00:00', 'hora_fin': '08:00:00'}, 'hora_fin'),
    ({'hora_inicio': '09:00:00', 'hora_fin': '08:00:00'}, 'hora_fin'),
    ({'origen': 'OTRO'}, 'origen'),
    ({'tipo_ausencia_id': 0}, 'tipo_ausencia_id'),
    ({'referencia_formato': 'REF'}, 'referencia_formato')
])
def test_hu_001_ca_01_ca_03_datos_invalidos_no_crean_registros(e, changes, campo):
    # HU-001-CA-01 y HU-001-CA-03.
    tipo = e.tipo()
    actor_id = e.usuarios['empleado']['id']
    before = e.fila('SELECT count(*) AS n FROM solicitudes WHERE solicitante_id = %s', (actor_id,))['n']
    validacion(e.api('POST', '/mis-solicitudes', actor='empleado',
                     json=e.datos_solicitud(tipo, **changes)), campo)
    assert e.fila('SELECT count(*) AS n FROM solicitudes WHERE solicitante_id = %s', (actor_id,))['n'] == before


def test_hu_001_ca_04_estado_historial_auditoria_y_aislamiento(e):
    solicitud = e.solicitud()
    ajena = e.solicitud(actor='otro')
    correcto(e.decidir(solicitud, 'APROBAR', observacion='Aprobación ' + uuid4().hex))
    detalle = e.detalle(solicitud)
    assert detalle['estado_codigo'] == 'APROBADA'
    historial = correcto(e.api('GET', f"/solicitudes/{solicitud['id']}/historial", actor='empleado'))
    assert historial[-1]['estado_nuevo'] == 'APROBADA'
    assert [row['version'] for row in historial] == sorted(row['version'] for row in historial)
    assert len({row['version'] for row in historial}) == len(historial)
    assert all(row['actor_id'] and row['creado_en'] and row['operacion'] for row in historial)
    propias = correcto(e.api('GET', '/mis-solicitudes', actor='empleado', params={'estado': 'APROBADA', 'solicitante_id': e.usuarios['otro']['id']}))
    assert solicitud['id'] in {row['id'] for row in propias}
    assert ajena['id'] not in {row['id'] for row in propias}
    assert all(row['solicitante_id'] == e.usuarios['empleado']['id'] for row in propias)
    for suffix in ('', '/historial'):
        assert e.api('GET', f"/solicitudes/{solicitud['id']}" + suffix, actor='otro').status_code == 404
    e.acceso('empleado', solicitud, 'CONSULTA_DETALLE')
    e.acceso('empleado', solicitud, 'CONSULTA_HISTORIAL')
    e.acceso('otro', solicitud, 'CONSULTA_HISTORIAL', False)
    validacion(e.api('GET', '/mis-solicitudes', actor='empleado', params={'estado': 'INVALIDO'}), 'estado')


def test_hu_002_ca_01_notifica_cambios_al_solicitante_sin_filtrar_otros(e):
    solicitud = e.solicitud()
    correcto(e.decidir(solicitud, 'RECHAZAR', observacion='Rechazo ' + uuid4().hex))
    avisos = correcto(e.api('GET', '/mis-notificaciones', actor='empleado'))
    propios = [n for n in avisos if n['solicitud_id'] == solicitud['id'] and n['tipo'] == 'CAMBIO_ESTADO']
    assert {'EN_REVISION', 'RECHAZADA'} <= {n['estado_notificado'] for n in propios}
    assert all(n['estado_envio'] in ('PENDIENTE', 'PROCESANDO', 'ENVIADA', 'ERROR') for n in propios)
    assert all('correo' not in n and 'ultimo_error' not in n for n in avisos)
    otros = correcto(e.api('GET', '/mis-notificaciones', actor='otro', params={'destinatario_id': e.usuarios['empleado']['id']}))
    assert not any(n['solicitud_id'] == solicitud['id'] for n in otros)
    validacion(e.api('GET', '/mis-notificaciones', actor='empleado', params={'limit': 101}), 'limit')
    persistidos = e.filas('SELECT * FROM notificaciones WHERE solicitud_id = %s AND tipo = %s', (solicitud['id'], 'CAMBIO_ESTADO'))
    assert all(n['destinatario_id'] == e.usuarios['empleado']['id'] for n in persistidos)
    assert len({n['historial_id'] for n in persistidos}) == len(persistidos)


def test_hu_002_ca_02_notifica_solo_al_aprobador_del_paso_activo(e):
    solicitud = e.solicitud(e.tipo(flujo='JEFE_TH'))
    avisos = correcto(e.api('GET', '/mis-notificaciones', actor='jefe'))
    assert any(n['solicitud_id'] == solicitud['id'] and n['tipo'] == 'PENDIENTE_REVISION' for n in avisos)
    avisos_th = correcto(e.api('GET', '/mis-notificaciones'))
    assert not any(n['solicitud_id'] == solicitud['id'] for n in avisos_th)
    correcto(e.decidir(solicitud, 'APROBAR'))
    avisos_th = correcto(e.api('GET', '/mis-notificaciones'))
    assert any(n['solicitud_id'] == solicitud['id'] and n['tipo'] == 'PENDIENTE_REVISION' for n in avisos_th)
    revision = e.revision(solicitud, 2)
    assert len(e.filas('SELECT id FROM notificaciones WHERE aprobacion_id = %s AND destinatario_id = %s',
                       (revision['id'], e.usuarios['th']['id']))) == 1
    assert correcto(e.api('POST', '/notificaciones/procesar')) == {'estado': 'programado'}
    assert e.api('POST', '/notificaciones/procesar', actor='empleado').status_code == 403
    validacion(e.api('GET', '/mis-notificaciones', actor='jefe', params={'offset': -1}), 'offset')


def test_hu_003_ca_01_bandeja_asignacion_y_orden_del_flujo(e):
    solicitud = e.solicitud(e.tipo(flujo='JEFE_TH'))
    pendientes = correcto(e.api('GET', '/revisiones/pendientes', actor='jefe'))
    pendiente = next(row for row in pendientes if row['solicitud_id'] == solicitud['id'])
    assert pendiente['aprobacion_id'] == e.revision(solicitud)['id']
    assert pendiente['version_solicitud'] == solicitud['version']
    assert pendiente['version_revision'] > 0
    assert not any(row['solicitud_id'] == solicitud['id'] for row in correcto(e.api('GET', '/revisiones/pendientes')))
    assert e.api('GET', '/revisiones/pendientes', actor='empleado').status_code == 403
    assert e.decidir(solicitud, 'VALIDAR_APROBAR', actor='th', orden=2).status_code == 409
    validacion(e.api('GET', '/revisiones/pendientes', actor='jefe', params={'limit': 0}), 'limit')
    correcto(e.decidir(solicitud, 'APROBAR'))
    assert not any(row['solicitud_id'] == solicitud['id'] for row in correcto(e.api('GET', '/revisiones/pendientes', actor='jefe')))
    assert any(row['solicitud_id'] == solicitud['id'] for row in correcto(e.api('GET', '/revisiones/pendientes')))


@pytest.mark.parametrize('accion,estado', [('APROBAR', 'APROBADA'), ('RECHAZAR', 'RECHAZADA')])
def test_hu_003_ca_02_ca_03_ca_04_decisiones_observaciones_y_auditoria(e, accion, estado):
    # HU-003-CA-02, HU-003-CA-03 y HU-003-CA-04.
    solicitud = e.solicitud()
    revision = e.revision(solicitud)
    nota = 'Revisión ' + uuid4().hex
    body = dict(e.versiones(solicitud, revision), contenido=nota)
    vacio = dict(body, contenido='   ')
    validacion(e.api('POST', f"/revisiones/{revision['id']}/observaciones", actor='jefe', json=vacio), 'contenido')
    observacion = correcto(e.api('POST', f"/revisiones/{revision['id']}/observaciones", actor='jefe', json=body), 201)
    assert observacion['observacion']['contenido'] == nota
    assert observacion['observacion']['autor_id'] == e.usuarios['jefe']['id']
    assert observacion['version_solicitud'] == body['version_solicitud'] + 1
    assert observacion['version_revision'] == body['version_revision'] + 1
    assert e.api('POST', f"/revisiones/{revision['id']}/observaciones", actor='jefe', json=body).status_code == 409
    validacion(e.decidir(solicitud, 'RECHAZAR'), 'observacion')
    validacion(e.decidir(solicitud, 'VALIDAR'), 'accion')
    nota_decision = 'Decisión ' + uuid4().hex
    result = correcto(e.decidir(solicitud, accion, observacion=nota_decision))
    assert result['estado_codigo'] == estado
    assert result['revision']['estado'] == estado
    assert result['revision']['decision_por'] == e.usuarios['jefe']['id']
    assert result['revision']['decidida_en']
    detalle = e.detalle(solicitud, actor='jefe')
    assert {nota, nota_decision} <= {row['contenido'] for row in detalle['observaciones']}
    assert all(row['aprobacion_id'] == revision['id'] for row in detalle['observaciones'])
    correcto(e.api('GET', f"/solicitudes/{solicitud['id']}/historial", actor='jefe'))
    e.acceso('jefe', solicitud, 'CONSULTA_DETALLE')
    e.acceso('jefe', solicitud, 'CONSULTA_HISTORIAL')
    e.acceso('jefe', solicitud, 'ACCION_SENSIBLE')
    e.modificaciones('jefe', 'aprobaciones', revision['id'], 'UPDATE')
    e.modificaciones('jefe', 'observaciones', observacion['observacion']['id'], 'INSERT')
    e.modificaciones('jefe', 'solicitudes', solicitud['id'], 'UPDATE')
    assert e.decidir(solicitud, accion, observacion=nota_decision).status_code == 409
    current = dict(e.versiones(solicitud, revision), contenido='Nueva nota')
    assert e.api('POST', f"/revisiones/{revision['id']}/observaciones", actor='jefe', json=current).status_code == 409


def test_hu_003_ca_02_control_optimista_concurrente_y_autoaprobacion(e):
    solicitud = e.solicitud()
    revision = e.revision(solicitud)
    body = dict(e.versiones(solicitud, revision), accion='APROBAR')
    assert e.api('POST', f"/revisiones/{revision['id']}/decision", actor='empleado', json=body).status_code == 404
    assert e.api('POST', f"/revisiones/{revision['id']}/decision", actor='otro', json=body).status_code == 404
    validacion(e.api('POST', f"/revisiones/{revision['id']}/decision", actor='jefe',
                     json=dict(body, version_revision=0)), 'version_revision')
    e.monkeypatch.setenv('ADMIN_ACTOR_EXTERNAL_ID', e.usuarios['jefe']['identidad_externa'])
    barrier = Barrier(2)

    def enviar():
        with TestClient(app, headers={'Authorization': 'Bearer ' + os.environ['ADMIN_API_TOKEN']}) as client:
            barrier.wait(timeout=15)
            return client.post(BASE + f"/revisiones/{revision['id']}/decision", json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: enviar(), range(2)))
    assert sorted(resultados) == [200, 409]
    assert e.fila('SELECT count(*) AS n FROM aprobaciones WHERE solicitud_id = %s AND decision_por IS NOT NULL', (solicitud['id'],))['n'] == 1
    assert e.fila("SELECT count(*) AS n FROM historial_solicitud WHERE solicitud_id = %s AND estado_nuevo = 'APROBADA'", (solicitud['id'],))['n'] == 1


@pytest.mark.parametrize('modo', ['separada', 'conjunta', 'rechazo'])
def test_hu_004_ca_01_ca_02_ca_03_validacion_decision_observaciones_y_auditoria(e, modo):
    # HU-004-CA-01, HU-004-CA-02 y HU-004-CA-03.
    solicitud = e.solicitud(e.tipo(flujo='TH'))
    revision = e.revision(solicitud)
    assert revision['aprobador_id'] == e.usuarios['th']['id']
    assert revision['requiere_validacion'] is True
    detalle = e.detalle(solicitud, actor='th')
    assert detalle['id'] == solicitud['id']
    correcto(e.api('GET', f"/solicitudes/{solicitud['id']}/historial"))
    body = dict(e.versiones(solicitud, revision), contenido='Nota TH ' + uuid4().hex)
    validacion(e.api('POST', f"/revisiones/{revision['id']}/observaciones", json=dict(body, contenido='')), 'contenido')
    observacion = correcto(e.api('POST', f"/revisiones/{revision['id']}/observaciones", json=body), 201)
    assert observacion['observacion']['autor_id'] == e.usuarios['th']['id']
    validacion(e.decidir(solicitud, 'APROBAR', actor='th'), 'accion')
    validacion(e.decidir(solicitud, 'RECHAZAR', actor='th'), 'observacion')
    notas = [body['contenido']]
    if modo == 'separada':
        nota = 'Validación ' + uuid4().hex
        notas.append(nota)
        validada = correcto(e.decidir(solicitud, 'VALIDAR', actor='th', observacion=nota))
        assert validada['estado_codigo'] == 'EN_REVISION'
        assert validada['revision']['validada_por'] == e.usuarios['th']['id']
        assert validada['revision']['validada_en']
        assert validada['revision']['decision_por'] is None
        assert e.decidir(solicitud, 'VALIDAR', actor='th').status_code == 409
        accion = 'APROBAR'
    else:
        accion = 'VALIDAR_APROBAR' if modo == 'conjunta' else 'RECHAZAR'
    nota = 'Resultado TH ' + uuid4().hex
    notas.append(nota)
    result = correcto(e.decidir(solicitud, accion, actor='th', observacion=nota))
    assert result['estado_codigo'] == ('RECHAZADA' if modo == 'rechazo' else 'APROBADA')
    assert result['revision']['decision_por'] == e.usuarios['th']['id']
    assert result['revision']['decidida_en']
    if modo != 'rechazo':
        assert result['revision']['validada_por'] == e.usuarios['th']['id']
        assert result['revision']['validada_en']
    detalle = e.detalle(solicitud, actor='th')
    assert set(notas) <= {row['contenido'] for row in detalle['observaciones']}
    assert all(row['autor_id'] == e.usuarios['th']['id'] and row['aprobacion_id'] == revision['id'] for row in detalle['observaciones'])
    e.acceso('th', solicitud, 'CONSULTA_DETALLE')
    e.acceso('th', solicitud, 'CONSULTA_HISTORIAL')
    e.acceso('th', solicitud, 'ACCION_SENSIBLE')
    e.modificaciones('th', 'aprobaciones', revision['id'], 'UPDATE')
    e.modificaciones('th', 'solicitudes', solicitud['id'], 'UPDATE')
    for row in detalle['observaciones']:
        e.modificaciones('th', 'observaciones', row['id'], 'INSERT')
    assert e.decidir(solicitud, accion, actor='th', observacion=nota).status_code == 409
    assert e.api('GET', f"/solicitudes/{solicitud['id']}/historial", actor='otro').status_code == 404


@pytest.mark.parametrize('params,campo', [({'limit': 0}, 'limit'), ({'limit': 101}, 'limit'), ({'offset': -1}, 'offset')])
def test_limites_paginacion_todas_las_listas(e, params, campo):
    # HU-001-CA-04, HU-002-CA-01, HU-002-CA-02, HU-003-CA-01,
    # HU-004-CA-03 y HU-005-CA-01.
    solicitud = e.solicitud()
    rutas = [('/tipos-ausencia', 'th'), ('/mis-solicitudes', 'empleado'),
             ('/revisiones/pendientes', 'jefe'), ('/mis-notificaciones', 'empleado'),
             (f"/solicitudes/{solicitud['id']}/historial", 'empleado')]
    for ruta, actor in rutas:
        validacion(e.api('GET', ruta, actor=actor, params=params), campo)
        for limit in (1, 100):
            rows = correcto(e.api('GET', ruta, actor=actor, params={'limit': limit, 'offset': 0}))
            assert isinstance(rows, list) and len(rows) <= limit


def test_hu_005_ca_01_autorizacion_roles_y_version_delete(e):
    tipo = e.tipo()
    body = dict(nombre='QA-' + uuid4().hex, estado='ACTIVO', flujo='JEFE',
                requiere_motivo=False, modalidad_horas='OPCIONAL')
    assert e.api('POST', '/tipos-ausencia', actor='empleado', json=body).status_code == 403
    assert e.api('GET', '/flujos', actor='jefe').status_code == 403
    assert e.api('GET', f"/tipos-ausencia/{tipo['id']}", actor='empleado').status_code == 403
    assert e.api('PUT', f"/tipos-ausencia/{tipo['id']}", actor='jefe', json=dict(body, version=tipo['version'])).status_code == 403
    assert e.api('PUT', f"/tipos-ausencia/{tipo['id']}/flujo", actor='empleado', json={'flujo': 'TH', 'version': tipo['version']}).status_code == 403
    assert e.api('DELETE', f"/tipos-ausencia/{tipo['id']}", actor='empleado', params={'version': tipo['version']}).status_code == 403
    validacion(e.api('DELETE', f"/tipos-ausencia/{tipo['id']}"), 'version')
    validacion(e.api('DELETE', f"/tipos-ausencia/{tipo['id']}", params={'version': 0}), 'version')
    assert correcto(e.api('GET', f"/tipos-ausencia/{tipo['id']}"))['version'] == tipo['version']


def test_hu_001_ca_01_identidad_servidor_no_suplantable(e):
    tipo = e.tipo()
    body = e.datos_solicitud(tipo, solicitante_id=e.usuarios['otro']['id'])
    validacion(e.api('POST', '/mis-solicitudes', actor='empleado', json=body), 'solicitante_id')
    assert e.api('POST', '/mis-solicitudes', actor='th', json=e.datos_solicitud(tipo)).status_code == 403
    identidad = correcto(e.api('GET', '/identidad', actor='empleado',
                               params={'identidad_externa': e.usuarios['th']['identidad_externa']}))
    assert identidad['id'] == e.usuarios['empleado']['id']
    assert identidad['roles'] == ['EMPLEADO']