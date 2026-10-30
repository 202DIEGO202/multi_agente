import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


OPERACIONES = [
    ('GET', '/api/admin/tipos-ausencia', None, {}, 'HU-005-CA-01'),
    ('GET', '/api/admin/tipos-ausencia/1', None, {}, 'HU-005-CA-01'),
    ('POST', '/api/admin/tipos-ausencia', {'nombre': None, 'flujo_codigo': 'JEFE'}, {}, 'HU-005-CA-01'),
    ('PUT', '/api/admin/tipos-ausencia/1', {'nombre': None, 'flujo_codigo': 'JEFE', 'version_esperada': 1}, {}, 'HU-005-CA-01'),
    ('PUT', '/api/admin/tipos-ausencia/1/flujo', {'flujo_codigo': 'JEFE', 'version_esperada': 1}, {}, 'HU-005-CA-02'),
    ('DELETE', '/api/admin/tipos-ausencia/1', None, {'version_esperada': 1}, 'HU-005-CA-01'),
    ('GET', '/api/admin/flujos-aprobacion', None, {}, 'HU-005-CA-02'),
    ('GET', '/api/admin/revisiones/pendientes', None, {}, 'HU-003-CA-01'),
    ('GET', '/api/admin/solicitudes/1', None, {}, 'HU-003-CA-04'),
    ('GET', '/api/admin/solicitudes/1/historial', None, {}, 'HU-004-CA-03'),
    ('POST', '/api/admin/revisiones/1/decision', {'decision': 'APROBAR', 'version_solicitud_esperada': 1, 'version_revision_esperada': 1}, {}, 'HU-003-CA-02'),
    ('GET', '/api/admin/notificaciones', None, {}, 'HU-002-CA-02'),
]


@pytest.mark.parametrize('method,path,body,params,criterio', OPERACIONES)
@pytest.mark.parametrize('credencial', ['ausente', 'esquema_incorrecto', 'bearer_incorrecto'])
def test_autorizacion_administrativa_regresion(method, path, body, params, criterio, credencial):
    # El parámetro criterio identifica la aceptación protegida por cada operación.
    headers = {}
    if credencial != 'ausente':
        expected = os.environ.get('ADMIN_API_TOKEN')
        assert expected, 'Falta ADMIN_API_TOKEN en el entorno de pruebas'
        if credencial == 'esquema_incorrecto':
            headers['Authorization'] = 'Basic ' + expected
        else:
            headers['Authorization'] = 'Bearer ' + expected + uuid4().hex
    payload = dict(body) if body is not None else None
    if payload is not None and 'nombre' in payload:
        payload['nombre'] = 'QA-' + uuid4().hex
    with TestClient(app) as client:
        response = client.request(method, path, headers=headers, json=payload, params=params)
    # No incluir credenciales ni el cuerpo de respuesta en diagnósticos.
    assert response.status_code in {401, 403}, (criterio, method, path, response.status_code)


@pytest.mark.parametrize('path', ['/api/tipos-ausencia', '/api/tipos-ausencia/1', '/api/flujos-aprobacion'])
def test_hu_005_ca_01_catalogo_interno_sin_copia_anonima(path):
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code in {401, 403, 404}, (path, response.status_code)


def test_health_publico_tras_rechazar_autorizacion():
    with TestClient(app) as client:
        denied = client.get('/api/admin/tipos-ausencia')
        assert denied.status_code in {401, 403}
        health = client.get('/api/health')
    assert health.status_code == 200
    assert health.json() == {'estado': 'ok'}