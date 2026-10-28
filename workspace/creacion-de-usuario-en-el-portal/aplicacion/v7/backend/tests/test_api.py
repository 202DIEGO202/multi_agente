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
    # Criterio HU-007-CA-01: Envío válido con datos completos y correctos
    cedula = unique_cedula()
    # Insertar usuario y líder en BD para prueba
    with client.app.dependency_overrides.get('get_db_connection', lambda: None) as _:
        pass
    # Insert usuario y lider area
    from psycopg import connect
    conn = connect(os.environ['DATABASE_URL'], autocommit=True)
    with conn.cursor() as cur:
        # Crear area y cargo
        cur.execute("INSERT INTO areas (nombre) VALUES ('AreaTest') RETURNING id")
        area_id = cur.fetchone()[0]
        cur.execute("INSERT INTO cargos (nombre) VALUES ('CargoTest') RETURNING id")
        cargo_id = cur.fetchone()[0]
        # Crear lider
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING id",
                    ('9999999999', 'Lider Test', '1234567890', 'lider@test.com', '1980-01-01', area_id, cargo_id))
        lider_id = cur.fetchone()[0]
        # Crear empleado
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE) RETURNING id",
                    (cedula, 'Empleado Test', '0987654321', unique_email(), '1990-01-01', area_id, cargo_id))
        empleado_id = cur.fetchone()[0]

    payload = {
        "cedula": cedula,
        "nombres_completos": "Empleado Test",
        "telefono": "0987654321",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": "1990-01-01",
        "nivel_estudios": "Bachillerato"
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 'id' in data
    assert data['estado'] == 'Pendiente'


def test_pr_002_hu_007_ca_02_faltan_datos():
    # Criterio HU-007-CA-02: Datos incompletos o inválidos bloquean envío
    payload = {
        "cedula": "",
        "nombres_completos": "",
        "telefono": "",
        "correo_electronico": "not-an-email",
        "fecha_nacimiento": "2005-01-01",  # menor de 23
        "nivel_estudios": "Primaria"  # menor que bachillerato
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 422
    # Debe contener mensajes de error específicos
    errors = response.json()['detail']
    mensajes = [e['msg'] for e in errors]
    assert any('Nivel de estudios mínimo' in m or 'nivel_estudios' in m for m in mensajes)
    assert any('La edad debe ser mayor a 23 años' in m or 'fecha_nacimiento' in m for m in mensajes)


def test_pr_003_hu_007_ca_03_errores_especificos():
    # Criterio HU-007-CA-03: Mensajes de error específicos para nivel de estudios y edad
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Empleado Test",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=23*365)).isoformat(),  # justo 23 años
        "nivel_estudios": "Primaria"
    }
    response = client.post('/api/solicitudes', json=payload)
    assert response.status_code == 422
    errors = response.json()['detail']
    mensajes = [e['msg'] for e in errors]
    assert any('Nivel de estudios mínimo' in m for m in mensajes)
    assert any('La edad debe ser mayor a 23 años' in m for m in mensajes)

# --- PR-004 HU-009 ---

def test_pr_004_hu_009_ca_01_panel_muestra_datos_solicitante_y_lider():
    # Crear datos para solicitud aprobada
    from psycopg import connect
    conn = connect(os.environ['DATABASE_URL'], autocommit=True)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO areas (nombre) VALUES ('AreaPanel') RETURNING id")
        area_id = cur.fetchone()[0]
        cur.execute("INSERT INTO cargos (nombre) VALUES ('CargoPanel') RETURNING id")
        cargo_id = cur.fetchone()[0]
        # Lider
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING id",
                    ('8888888888', 'Lider Panel', '1111111111', 'liderpanel@test.com', '1975-01-01', area_id, cargo_id))
        lider_id = cur.fetchone()[0]
        # Empleado
        cedula_emp = unique_cedula()
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE) RETURNING id",
                    (cedula_emp, 'Empleado Panel', '2222222222', unique_email(), '1985-01-01', area_id, cargo_id))
        empleado_id = cur.fetchone()[0]
        # Solicitud
        cur.execute("INSERT INTO solicitudes (usuario_id, nivel_estudios, estado, lider_area_id, fecha_decision) VALUES (%s, %s, 'Pendiente', %s, NULL) RETURNING id",
                    (empleado_id, 'Bachillerato', lider_id))
        solicitud_id = cur.fetchone()[0]

    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    response = client.get(f'/api/admin/solicitudes/{solicitud_id}', headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == solicitud_id
    ds = data['datos_solicitante']
    dl = data['datos_lider']
    assert ds['cedula'] == cedula_emp
    assert 'edad' in ds
    assert dl['nombres_completos'] == 'Lider Panel'
    assert 'correo_electronico' in dl

# --- PR-005 HU-010 ---

def test_pr_005_hu_010_ca_01_aprobar_solicitud_registra_y_notifica():
    # Crear solicitud para aprobar
    from psycopg import connect
    conn = connect(os.environ['DATABASE_URL'], autocommit=True)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO areas (nombre) VALUES ('AreaAprobar') RETURNING id")
        area_id = cur.fetchone()[0]
        cur.execute("INSERT INTO cargos (nombre) VALUES ('CargoAprobar') RETURNING id")
        cargo_id = cur.fetchone()[0]
        # Lider
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING id",
                    ('7777777777', 'Lider Aprobar', '3333333333', 'lideraprobar@test.com', '1970-01-01', area_id, cargo_id))
        lider_id = cur.fetchone()[0]
        # Empleado
        cedula_emp = unique_cedula()
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE) RETURNING id",
                    (cedula_emp, 'Empleado Aprobar', '4444444444', unique_email(), '1980-01-01', area_id, cargo_id))
        empleado_id = cur.fetchone()[0]
        # Solicitud
        cur.execute("INSERT INTO solicitudes (usuario_id, nivel_estudios, estado, lider_area_id) VALUES (%s, %s, 'Pendiente', %s) RETURNING id",
                    (empleado_id, 'Bachillerato', lider_id))
        solicitud_id = cur.fetchone()[0]

    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    payload = {"aprobar": True}
    response = client.post(f'/api/admin/solicitudes/{solicitud_id}/decidir', json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == solicitud_id
    assert data['estado'] == 'Aprobada'

# --- PR-006 HU-011 ---

def test_pr_006_hu_011_ca_01_rechazar_solicitud_con_motivo():
    # Crear solicitud para rechazar
    from psycopg import connect
    conn = connect(os.environ['DATABASE_URL'], autocommit=True)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO areas (nombre) VALUES ('AreaRechazar') RETURNING id")
        area_id = cur.fetchone()[0]
        cur.execute("INSERT INTO cargos (nombre) VALUES ('CargoRechazar') RETURNING id")
        cargo_id = cur.fetchone()[0]
        # Lider
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING id",
                    ('6666666666', 'Lider Rechazar', '5555555555', 'liderrechazar@test.com', '1965-01-01', area_id, cargo_id))
        lider_id = cur.fetchone()[0]
        # Empleado
        cedula_emp = unique_cedula()
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE) RETURNING id",
                    (cedula_emp, 'Empleado Rechazar', '6666666666', unique_email(), '1975-01-01', area_id, cargo_id))
        empleado_id = cur.fetchone()[0]
        # Solicitud
        cur.execute("INSERT INTO solicitudes (usuario_id, nivel_estudios, estado, lider_area_id) VALUES (%s, %s, 'Pendiente', %s) RETURNING id",
                    (empleado_id, 'Bachillerato', lider_id))
        solicitud_id = cur.fetchone()[0]

    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    payload = {"aprobar": False, "motivo_rechazo": "Datos incompletos"}
    response = client.post(f'/api/admin/solicitudes/{solicitud_id}/decidir', json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == solicitud_id
    assert data['estado'] == 'Rechazada'


def test_pr_007_hu_011_ca_01_rechazar_solicitud_sin_motivo_error():
    # Intentar rechazar sin motivo debe fallar
    from psycopg import connect
    conn = connect(os.environ['DATABASE_URL'], autocommit=True)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO areas (nombre) VALUES ('AreaRechazar2') RETURNING id")
        area_id = cur.fetchone()[0]
        cur.execute("INSERT INTO cargos (nombre) VALUES ('CargoRechazar2') RETURNING id")
        cargo_id = cur.fetchone()[0]
        # Lider
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING id",
                    ('5555555555', 'Lider Rechazar2', '7777777777', 'liderrechazar2@test.com', '1960-01-01', area_id, cargo_id))
        lider_id = cur.fetchone()[0]
        # Empleado
        cedula_emp = unique_cedula()
        cur.execute("INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, area_id, cargo_id, es_lider) VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE) RETURNING id",
                    (cedula_emp, 'Empleado Rechazar2', '8888888888', unique_email(), '1970-01-01', area_id, cargo_id))
        empleado_id = cur.fetchone()[0]
        # Solicitud
        cur.execute("INSERT INTO solicitudes (usuario_id, nivel_estudios, estado, lider_area_id) VALUES (%s, %s, 'Pendiente', %s) RETURNING id",
                    (empleado_id, 'Bachillerato', lider_id))
        solicitud_id = cur.fetchone()[0]

    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    payload = {"aprobar": False}
    response = client.post(f'/api/admin/solicitudes/{solicitud_id}/decidir', json=payload, headers=headers)
    assert response.status_code == 422 or response.status_code == 400

# --- PR-008 Seguridad: acceso admin sin token ---

def test_pr_008_admin_sin_token_rechaza_acceso():
    response = client.get('/api/admin/solicitudes')
    assert response.status_code in (401, 403)


def test_pr_009_admin_con_token_accede():
    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    response = client.get('/api/admin/solicitudes', headers=headers)
    assert response.status_code == 200

# --- PR-010 Health check ---

def test_pr_010_api_health():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'estado': 'ok'}