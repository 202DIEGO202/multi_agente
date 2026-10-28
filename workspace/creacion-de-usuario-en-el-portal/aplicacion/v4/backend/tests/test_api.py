import os
import uuid
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ADMIN_TOKEN = os.getenv('ADMIN_API_TOKEN', 'token')
AUTH_HEADER = {'Authorization': f'Bearer {ADMIN_TOKEN}'}

# Datos base para pruebas

def unique_cedula():
    return str(uuid.uuid4())[:20]

def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

# --- PR-001 HU-007 CA-01: Envío correcto de solicitud con datos válidos ---
def test_pr_001_hu_007_ca_01_crear_solicitud_valida():
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Juan Pérez",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),  # 30 años
        "nivel_estudios": "Bachillerato"
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["estado"] == "Pendiente"

# --- PR-002 HU-007 CA-02: Error por datos incompletos o inválidos ---
def test_pr_002_hu_007_ca_02_error_datos_incompletos():
    # Omite nombres_completos
    payload = {
        "cedula": unique_cedula(),
        # "nombres_completos": "Juan Pérez",  # omitido
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),
        "nivel_estudios": "Bachillerato"
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 422

# --- PR-003 HU-007 CA-03: Error nivel de estudios inferior a bachillerato ---
def test_pr_003_hu_007_ca_03_error_nivel_estudios_inferior():
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Ana Gómez",
        "telefono": "0987654321",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*30)).isoformat(),
        "nivel_estudios": "Primaria"  # inferior a bachillerato
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 422
    assert "Nivel de estudios mínimo" in response.text

# --- PR-004 HU-007 CA-03: Error edad menor o igual a 23 años ---
def test_pr_004_hu_007_ca_03_error_edad_menor():
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Luis Martínez",
        "telefono": "111222333",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*23)).isoformat(),  # 23 años exactos
        "nivel_estudios": "Bachillerato"
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 422
    assert "La edad debe ser mayor a 23 años" in response.text

# --- PR-005 HU-009 CA-01: Líder de área visualiza datos de solicitud y aprobador ---
def test_pr_005_hu_009_ca_01_visualizar_solicitud_admin():
    # Primero crear solicitud válida
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Carlos Ruiz",
        "telefono": "555666777",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*40)).isoformat(),
        "nivel_estudios": "Universitario"
    }
    post_resp = client.post("/api/solicitudes", json=payload)
    assert post_resp.status_code == 200
    solicitud_id = post_resp.json()["id"]

    # Sin token debe fallar
    get_resp_unauth = client.get(f"/api/admin/solicitudes/{solicitud_id}")
    assert get_resp_unauth.status_code in (401, 403)

    # Con token debe pasar
    get_resp = client.get(f"/api/admin/solicitudes/{solicitud_id}", headers=AUTH_HEADER)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "solicitud" in data
    assert data["solicitud"]["cedula"] == payload["cedula"]
    assert "lider_area" in data
    assert "nombre" in data["lider_area"]

# --- PR-006 HU-010 CA-01: Líder aprueba solicitud y notifica admin ---
def test_pr_006_hu_010_ca_01_aprobar_solicitud():
    # Crear solicitud
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Marta López",
        "telefono": "444555666",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*35)).isoformat(),
        "nivel_estudios": "Técnico"
    }
    post_resp = client.post("/api/solicitudes", json=payload)
    assert post_resp.status_code == 200
    solicitud_id = post_resp.json()["id"]

    # Aprobar sin token falla
    resp_unauth = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json={"aprobar": True})
    assert resp_unauth.status_code in (401, 403)

    # Aprobar con token
    resp = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json={"aprobar": True}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert "Solicitud aprobada" in resp.json().get("mensaje", "")

# --- PR-007 HU-011 CA-01: Líder rechaza solicitud con motivo obligatorio ---
def test_pr_007_hu_011_ca_01_rechazar_solicitud_con_motivo():
    # Crear solicitud
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Pedro Sánchez",
        "telefono": "777888999",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*45)).isoformat(),
        "nivel_estudios": "Posgrado"
    }
    post_resp = client.post("/api/solicitudes", json=payload)
    assert post_resp.status_code == 200
    solicitud_id = post_resp.json()["id"]

    # Rechazar sin motivo debe fallar
    resp_fail = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json={"aprobar": False}, headers=AUTH_HEADER)
    assert resp_fail.status_code == 422

    # Rechazar con motivo
    motivo = "Datos incompletos"
    resp = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json={"aprobar": False, "motivo_rechazo": motivo}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert "Solicitud rechazada" in resp.json().get("mensaje", "")

# --- PR-008 Ruta pública GET /api/health ---
def test_pr_008_api_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"estado": "ok"}

# --- PR-009 Acceso sin token a rutas admin ---
def test_pr_009_admin_routes_without_token():
    urls = [
        "/api/admin/solicitudes",
        "/api/admin/solicitudes/1",
        "/api/admin/solicitudes/1/decidir"
    ]
    for url in urls:
        resp = client.get(url) if 'decidir' not in url else client.post(url, json={})
        assert resp.status_code in (401, 403)

# --- PR-010 Acceso con token a rutas admin ---
def test_pr_010_admin_routes_with_token():
    # GET /api/admin/solicitudes
    resp = client.get("/api/admin/solicitudes", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # Crear solicitud para detalle y decidir
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Laura Méndez",
        "telefono": "222333444",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": (date.today() - timedelta(days=365*50)).isoformat(),
        "nivel_estudios": "Universitario"
    }
    post_resp = client.post("/api/solicitudes", json=payload)
    solicitud_id = post_resp.json()["id"]

    # GET detalle
    resp_detalle = client.get(f"/api/admin/solicitudes/{solicitud_id}", headers=AUTH_HEADER)
    assert resp_detalle.status_code == 200

    # POST decidir aprobar
    resp_decidir = client.post(f"/api/admin/solicitudes/{solicitud_id}/decidir", json={"aprobar": True}, headers=AUTH_HEADER)
    assert resp_decidir.status_code == 200