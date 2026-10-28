import os
import uuid
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ADMIN_TOKEN = os.getenv('ADMIN_API_TOKEN')

# --- Datos base para pruebas ---

def unique_cedula():
    return str(uuid.uuid4())[:10]

def unique_email():
    return f"test_{uuid.uuid4().hex[:8]}@example.com"

# --- HU-007: Portal Empleado ---

# HU-007-CA-01: Validación exitosa y creación solicitud

def test_hu_007_ca_01_crear_solicitud_valida():
    cedula = unique_cedula()
    payload = {
        "cedula": cedula,
        "nombres": "Juan Perez",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),  # 30 años
        "nivel_estudios": "Bachillerato"
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["estado"] == "Pendiente"

# HU-007-CA-02: Datos incompletos o invalidos bloquean envío

def test_hu_007_ca_02_datos_incompletos():
    # Omite nombres
    payload = {
        "cedula": unique_cedula(),
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),
        "nivel_estudios": "Bachillerato"
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 422

# HU-007-CA-03: Validaciones específicas de edad y nivel de estudios

def test_hu_007_ca_03_nivel_estudios_invalido():
    payload = {
        "cedula": unique_cedula(),
        "nombres": "Ana Gomez",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),
        "nivel_estudios": "Primaria"  # inferior a bachillerato
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 422
    assert "Nivel de estudios mínimo: bachillerato" in response.text


def test_hu_007_ca_03_edad_invalida():
    payload = {
        "cedula": unique_cedula(),
        "nombres": "Luis Martinez",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*23)).isoformat(),  # 23 años exactos
        "nivel_estudios": "Bachillerato"
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 422
    assert "La edad debe ser mayor a 23 años" in response.text

# --- HU-009: Panel Aprobadores ---

# Para pruebas administrativas se requiere token

# HU-009-CA-01: Visualizar datos solicitante y aprobador

def test_hu_009_ca_01_visualizar_solicitud_admin():
    # Crear solicitud para obtener id
    cedula = unique_cedula()
    payload = {
        "cedula": cedula,
        "nombres": "Carlos Lopez",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),
        "nivel_estudios": "Bachillerato"
    }
    create_resp = client.post("/api/solicitudes", json=payload)
    assert create_resp.status_code == 201
    solicitud_id = create_resp.json()["id"]

    # Acceso sin token debe fallar
    resp_no_token = client.get(f"/api/admin/solicitudes/{solicitud_id}")
    assert resp_no_token.status_code in (401, 403)

    # Acceso con token
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    resp = client.get(f"/api/admin/solicitudes/{solicitud_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == solicitud_id
    assert data["cedula"] == cedula
    assert "lider_area" in data
    assert "nombres" in data["lider_area"]

# --- HU-010: Aprobar solicitud ---

def test_hu_010_ca_01_aprobar_solicitud():
    # Crear solicitud
    cedula = unique_cedula()
    payload = {
        "cedula": cedula,
        "nombres": "Marta Ruiz",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),
        "nivel_estudios": "Bachillerato"
    }
    create_resp = client.post("/api/solicitudes", json=payload)
    solicitud_id = create_resp.json()["id"]

    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    # Aprobar solicitud
    decision_payload = {"aprobar": True}
    resp = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json=decision_payload, headers=headers)
    assert resp.status_code == 200
    assert "Solicitud aprobada" in resp.json().get("mensaje", "")

# --- HU-011: Rechazar solicitud con motivo obligatorio ---

def test_hu_011_ca_01_rechazar_solicitud_con_motivo():
    # Crear solicitud
    cedula = unique_cedula()
    payload = {
        "cedula": cedula,
        "nombres": "Pedro Sanchez",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),
        "nivel_estudios": "Bachillerato"
    }
    create_resp = client.post("/api/solicitudes", json=payload)
    solicitud_id = create_resp.json()["id"]

    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    # Rechazar sin motivo debe fallar
    decision_payload = {"aprobar": False}
    resp_fail = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json=decision_payload, headers=headers)
    assert resp_fail.status_code == 422

    # Rechazar con motivo
    decision_payload = {"aprobar": False, "motivo_rechazo": "Datos incompletos"}
    resp = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json=decision_payload, headers=headers)
    assert resp.status_code == 200
    assert "Solicitud rechazada" in resp.json().get("mensaje", "") or "Solicitud aprobada" not in resp.json().get("mensaje", "")

# --- Ruta pública health ---
def test_get_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}

# --- Acceso sin token a rutas admin ---
def test_admin_routes_require_token():
    urls = [
        "/api/admin/solicitudes",
        "/api/admin/solicitudes/1",
        "/api/admin/solicitudes/1/decidir"
    ]
    for url in urls:
        resp = client.get(url) if 'decidir' not in url else client.post(url, json={})
        assert resp.status_code in (401, 403)

# --- Acceso con token a rutas admin ---
def test_admin_routes_with_token():
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    resp = client.get("/api/admin/solicitudes", headers=headers)
    assert resp.status_code == 200

    # Crear solicitud para detalle
    cedula = unique_cedula()
    payload = {
        "cedula": cedula,
        "nombres": "Test User",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),
        "nivel_estudios": "Bachillerato"
    }
    create_resp = client.post("/api/solicitudes", json=payload)
    solicitud_id = create_resp.json()["id"]

    resp_detail = client.get(f"/api/admin/solicitudes/{solicitud_id}", headers=headers)
    assert resp_detail.status_code == 200

    decision_payload = {"aprobar": True}
    resp_decidir = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json=decision_payload, headers=headers)
    assert resp_decidir.status_code == 200