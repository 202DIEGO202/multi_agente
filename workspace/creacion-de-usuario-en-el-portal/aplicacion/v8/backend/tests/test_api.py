import os
import uuid
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ADMIN_TOKEN = os.getenv('ADMIN_API_TOKEN')

# Datos base para pruebas

def unique_cedula():
    return str(uuid.uuid4())[:10]

def unique_email():
    return f"test_{uuid.uuid4().hex[:8]}@example.com"

# --- PR-001 HU-007 ---

def test_pr_001_hu_007_ca_01_crear_solicitud_valida():
    # Criterio HU-007-CA-01: Enviar solicitud con datos válidos
    # Precondición: usuario y lider deben existir en BD
    cedula = unique_cedula()
    email = unique_email()
    # Insertar usuario y lider en BD para prueba
    with client.app.dependency_overrides.get('get_db_connection', None) or client.app.dependency_overrides.setdefault('get_db_connection', lambda: None):
        pass
    # Insert usuario y lider area directamente en DB
    from psycopg import connect
    with connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            # Crear area
            cur.execute("INSERT INTO areas (nombre) VALUES ('AreaTest') RETURNING id")
            area_id = cur.fetchone()[0]
            # Crear lider
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000000', 'Lider Test', '0000000000', 'lider@example.com', date(1980,1,1), 'Universitario', area_id, 'Jefe', True))
            lider_id = cur.fetchone()[0]
            # Crear usuario empleado
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (cedula, 'Empleado Test', '1111111111', email, date(1990,1,1), 'Universitario', area_id, 'Empleado', False))

    payload = {
        "cedula": cedula,
        "nombres": "Empleado Test",
        "telefono": "1111111111",
        "correo_electronico": email,
        "fecha_nacimiento": "1990-01-01",
        "nivel_estudios": "Bachillerato"
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 'id' in data
    assert data['estado'] == 'Pendiente'


def test_pr_002_hu_007_ca_02_error_validacion_campos_incompletos():
    # Criterio HU-007-CA-02: Enviar solicitud con campos incompletos
    payload = {
        "cedula": "",
        "nombres": "",
        "telefono": "",
        "correo_electronico": "not-an-email",
        "fecha_nacimiento": "1990-01-01",
        "nivel_estudios": "Bachillerato"
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 422


def test_pr_003_hu_007_ca_03_error_nivel_estudios_y_edad():
    # Criterio HU-007-CA-03: Nivel de estudios inferior y edad menor o igual a 23
    cedula = unique_cedula()
    email = unique_email()
    # Insert usuario y lider para prueba
    from psycopg import connect
    with connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO areas (nombre) VALUES ('AreaTest2') RETURNING id")
            area_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        ('0000000001', 'Lider Test2', '0000000001', 'lider2@example.com', date(1980,1,1), 'Universitario', area_id, 'Jefe', True))
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (cedula, 'Empleado Test2', '2222222222', email, date.today().replace(year=date.today().year - 23), 'Primaria', area_id, 'Empleado', False))

    payload = {
        "cedula": cedula,
        "nombres": "Empleado Test2",
        "telefono": "2222222222",
        "correo_electronico": email,
        "fecha_nacimiento": date.today().replace(year=date.today().year - 23).isoformat(),
        "nivel_estudios": "Primaria"
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 422
    # Mensajes de error específicos
    assert 'Nivel de estudios mínimo' in response.text or 'La edad debe ser mayor a 23 años' in response.text

# --- PR-002 HU-009 ---

def test_pr_004_hu_009_ca_01_visualizar_datos_solicitud_y_lider():
    # Criterio HU-009-CA-01: Líder visualiza datos solicitante y aprobador
    # Crear solicitud para prueba
    from psycopg import connect
    with connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO areas (nombre) VALUES ('AreaTest3') RETURNING id")
            area_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000002', 'Lider Test3', '0000000002', 'lider3@example.com', date(1980,1,1), 'Universitario', area_id, 'Jefe', True))
            lider_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000003', 'Empleado Test3', '3333333333', 'empleado3@example.com', date(1990,1,1), 'Universitario', area_id, 'Empleado', False))
            usuario_id = cur.fetchone()[0]
            cur.execute("INSERT INTO solicitudes (usuario_id, lider_area_id, estado) VALUES (%s,%s,'Pendiente') RETURNING id",
                        (usuario_id, lider_id))
            solicitud_id = cur.fetchone()[0]

    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    response = client.get(f'/api/admin/solicitudes/{solicitud_id}', headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == solicitud_id
    assert 'cedula' in data
    assert 'lider_area' in data
    assert 'aprobador' in data or data['aprobador'] is None

# --- PR-003 HU-010 ---

def test_pr_005_hu_010_ca_01_aprobar_solicitud():
    # Criterio HU-010-CA-01: Líder aprueba solicitud y notifica admin
    from psycopg import connect
    with connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO areas (nombre) VALUES ('AreaTest4') RETURNING id")
            area_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000004', 'Lider Test4', '0000000004', 'lider4@example.com', date(1980,1,1), 'Universitario', area_id, 'Jefe', True))
            lider_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000005', 'Empleado Test4', '4444444444', 'empleado4@example.com', date(1990,1,1), 'Universitario', area_id, 'Empleado', False))
            usuario_id = cur.fetchone()[0]
            cur.execute("INSERT INTO solicitudes (usuario_id, lider_area_id, estado) VALUES (%s,%s,'Pendiente') RETURNING id",
                        (usuario_id, lider_id))
            solicitud_id = cur.fetchone()[0]

    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    payload = {"accion": "Aprobar"}
    response = client.post(f'/api/admin/solicitudes/{solicitud_id}/decidir', json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert 'mensaje' in data

# --- PR-004 HU-011 ---

def test_pr_006_hu_011_ca_01_rechazar_solicitud_con_motivo():
    # Criterio HU-011-CA-01: Líder rechaza solicitud con motivo obligatorio
    from psycopg import connect
    with connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO areas (nombre) VALUES ('AreaTest5') RETURNING id")
            area_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000006', 'Lider Test5', '0000000006', 'lider5@example.com', date(1980,1,1), 'Universitario', area_id, 'Jefe', True))
            lider_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000007', 'Empleado Test5', '5555555555', 'empleado5@example.com', date(1990,1,1), 'Universitario', area_id, 'Empleado', False))
            usuario_id = cur.fetchone()[0]
            cur.execute("INSERT INTO solicitudes (usuario_id, lider_area_id, estado) VALUES (%s,%s,'Pendiente') RETURNING id",
                        (usuario_id, lider_id))
            solicitud_id = cur.fetchone()[0]

    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    payload = {"accion": "Rechazar", "motivo_rechazo": "Datos incorrectos"}
    response = client.post(f'/api/admin/solicitudes/{solicitud_id}/decidir', json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert 'mensaje' in data


def test_pr_007_hu_011_ca_01_rechazar_solicitud_sin_motivo_error():
    # Intentar rechazar sin motivo debe fallar validacion
    from psycopg import connect
    with connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO areas (nombre) VALUES ('AreaTest6') RETURNING id")
            area_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000008', 'Lider Test6', '0000000008', 'lider6@example.com', date(1980,1,1), 'Universitario', area_id, 'Jefe', True))
            lider_id = cur.fetchone()[0]
            cur.execute("INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        ('0000000009', 'Empleado Test6', '6666666666', 'empleado6@example.com', date(1990,1,1), 'Universitario', area_id, 'Empleado', False))
            usuario_id = cur.fetchone()[0]
            cur.execute("INSERT INTO solicitudes (usuario_id, lider_area_id, estado) VALUES (%s,%s,'Pendiente') RETURNING id",
                        (usuario_id, lider_id))
            solicitud_id = cur.fetchone()[0]

    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    payload = {"accion": "Rechazar"}
    response = client.post(f'/api/admin/solicitudes/{solicitud_id}/decidir', json=payload, headers=headers)
    assert response.status_code == 422

# --- Seguridad ---

def test_pr_008_ruta_publica_health():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'estado': 'ok'}


def test_pr_009_rutas_admin_sin_token():
    response = client.get('/api/admin/solicitudes')
    assert response.status_code in (401, 403)

    response = client.get('/api/admin/solicitudes/1')
    assert response.status_code in (401, 403)

    response = client.post('/api/admin/solicitudes/1/decidir', json={})
    assert response.status_code in (401, 403)


def test_pr_010_rutas_admin_con_token():
    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    response = client.get('/api/admin/solicitudes', headers=headers)
    assert response.status_code == 200

    # No se asegura que exista solicitud 1, solo prueba acceso
    response = client.get('/api/admin/solicitudes/1', headers=headers)
    assert response.status_code in (200, 404)

    response = client.post('/api/admin/solicitudes/1/decidir', json={"accion": "Aprobar"}, headers=headers)
    assert response.status_code in (200, 404, 422)