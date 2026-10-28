import uuid
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Utilidad para calcular fecha de nacimiento para edad dada

def fecha_nacimiento_para_edad(edad):
    hoy = date.today()
    return hoy.replace(year=hoy.year - edad)

# Datos base para crear usuario en DB para pruebas
# Se asume que el usuario debe existir en tabla usuarios para crear solicitud
# Se usará cedula única con uuid

@pytest.fixture(scope='module')
def usuario_existente():
    cedula = str(uuid.uuid4())[:20]
    nombres = f'Test User {cedula}'
    telefono = '1234567890'
    correo = f'{cedula}@example.com'
    fecha_nac = fecha_nacimiento_para_edad(30).isoformat()
    nivel_estudios = 'Bachillerato'

    # Insertar usuario en DB
    dsn = app.dependency_overrides.get('get_db')
    # No direct DB access here, so create usuario via direct SQL connection
    import os
    import psycopg
    dsn_env = os.environ.get('DATABASE_URL')
    with psycopg.connect(dsn_env, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        (cedula, nombres, telefono, correo, fecha_nac, nivel_estudios, 'Area Test', 'Cargo Test', False))
            usuario_id = cur.fetchone()[0]
    return {'id': usuario_id, 'cedula': cedula, 'nombres': nombres, 'telefono': telefono, 'correo_electronico': correo, 'fecha_nacimiento': fecha_nac, 'nivel_estudios': nivel_estudios}

# PR-001 HU-007-CA-01: Validar creación exitosa con datos correctos

def test_PR_001_crear_solicitud_valida(usuario_existente):
    payload = {
        'cedula': usuario_existente['cedula'],
        'nombres': usuario_existente['nombres'],
        'telefono': usuario_existente['telefono'],
        'correo_electronico': usuario_existente['correo_electronico'],
        'fecha_nacimiento': usuario_existente['fecha_nacimiento'],
        'nivel_estudios': 'Bachillerato'
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data['cedula'] == payload['cedula']
    assert data['nivel_estudios'] == 'Bachillerato'
    assert data['estado']['nombre'] == 'Pendiente'

# PR-002 HU-007-CA-02: Validar error por edad menor a 24

def test_PR_002_error_edad_menor(usuario_existente):
    fecha_nac = fecha_nacimiento_para_edad(22).isoformat()  # menor a 24
    payload = {
        'cedula': usuario_existente['cedula'],
        'nombres': usuario_existente['nombres'],
        'telefono': usuario_existente['telefono'],
        'correo_electronico': usuario_existente['correo_electronico'],
        'fecha_nacimiento': fecha_nac,
        'nivel_estudios': 'Bachillerato'
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 422
    assert 'La edad debe ser mayor a 23 años' in response.text

# PR-003 HU-007-CA-03: Validar error por nivel de estudios menor a bachillerato

def test_PR_003_error_nivel_estudios(usuario_existente):
    payload = {
        'cedula': usuario_existente['cedula'],
        'nombres': usuario_existente['nombres'],
        'telefono': usuario_existente['telefono'],
        'correo_electronico': usuario_existente['correo_electronico'],
        'fecha_nacimiento': usuario_existente['fecha_nacimiento'],
        'nivel_estudios': 'Primaria'
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 422
    assert 'Nivel de estudios mínimo: bachillerato' in response.text

# PR-004 HU-009-CA-01: Obtener datos detallados de solicitud incluyendo solicitante y aprobador

def test_PR_004_obtener_solicitud_detallada(usuario_existente):
    # Crear solicitud primero
    payload = {
        'cedula': usuario_existente['cedula'],
        'nombres': usuario_existente['nombres'],
        'telefono': usuario_existente['telefono'],
        'correo_electronico': usuario_existente['correo_electronico'],
        'fecha_nacimiento': usuario_existente['fecha_nacimiento'],
        'nivel_estudios': 'Bachillerato'
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 201
    solicitud_id = response.json()['id']

    # Obtener detalles
    response_get = client.get(f'/api/solicitudes/{solicitud_id}')
    assert response_get.status_code == 200
    data = response_get.json()
    assert 'solicitud' in data
    assert 'solicitante' in data
    assert 'aprobador' in data
    assert data['solicitud']['id'] == solicitud_id
    assert data['solicitante']['cedula'] == usuario_existente['cedula']

# PR-005 HU-010-CA-01: Aprobar solicitud y verificar respuesta

def test_PR_005_aprobar_solicitud(usuario_existente):
    # Crear solicitud
    payload = {
        'cedula': usuario_existente['cedula'],
        'nombres': usuario_existente['nombres'],
        'telefono': usuario_existente['telefono'],
        'correo_electronico': usuario_existente['correo_electronico'],
        'fecha_nacimiento': usuario_existente['fecha_nacimiento'],
        'nivel_estudios': 'Bachillerato'
    }
    response = client.post('/api/solicitudes', json=payload)
    solicitud_id = response.json()['id']

    # Aprobar
    patch_payload = {'aprobado': True}
    response_patch = client.patch(f'/api/solicitudes/{solicitud_id}/estado', json=patch_payload)
    assert response_patch.status_code == 200
    assert 'mensaje' in response_patch.json()

# PR-006 HU-011-CA-01: Rechazar solicitud con motivo obligatorio

def test_PR_006_rechazar_solicitud_con_motivo(usuario_existente):
    # Crear solicitud
    payload = {
        'cedula': usuario_existente['cedula'],
        'nombres': usuario_existente['nombres'],
        'telefono': usuario_existente['telefono'],
        'correo_electronico': usuario_existente['correo_electronico'],
        'fecha_nacimiento': usuario_existente['fecha_nacimiento'],
        'nivel_estudios': 'Bachillerato'
    }
    response = client.post('/api/solicitudes', json=payload)
    solicitud_id = response.json()['id']

    # Rechazar con motivo
    patch_payload = {'aprobado': False, 'motivo_rechazo': 'Datos incompletos'}
    response_patch = client.patch(f'/api/solicitudes/{solicitud_id}/estado', json=patch_payload)
    assert response_patch.status_code == 200
    assert 'mensaje' in response_patch.json()

# PR-007 HU-011-CA-01: Rechazar solicitud sin motivo debe fallar

def test_PR_007_rechazar_solicitud_sin_motivo(usuario_existente):
    # Crear solicitud
    payload = {
        'cedula': usuario_existente['cedula'],
        'nombres': usuario_existente['nombres'],
        'telefono': usuario_existente['telefono'],
        'correo_electronico': usuario_existente['correo_electronico'],
        'fecha_nacimiento': usuario_existente['fecha_nacimiento'],
        'nivel_estudios': 'Bachillerato'
    }
    response = client.post('/api/solicitudes', json=payload)
    solicitud_id = response.json()['id']

    # Rechazar sin motivo
    patch_payload = {'aprobado': False}
    response_patch = client.patch(f'/api/solicitudes/{solicitud_id}/estado', json=patch_payload)
    assert response_patch.status_code == 422
    assert 'Motivo de rechazo es obligatorio' in response_patch.text