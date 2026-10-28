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

# --- PR-001 HU-007 CA-01: Camino feliz creación solicitud válida ---
def test_pr_001_hu_007_ca_01_crear_solicitud_valida():
    # Edad > 23 años
    fecha_nac = date.today() - timedelta(days=365*30)
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Juan Pérez",
        "telefono": "1234567890",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": fecha_nac.isoformat(),
        "nivel_estudios": "Bachillerato"
    }
    # Para que la prueba funcione, el usuario debe existir en DB con area y cargo asignados
    # Se asume que el entorno de pruebas tiene datos válidos para el usuario
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["estado"] == "Pendiente"

# --- PR-002 HU-007 CA-02: Error validación datos incompletos ---
def test_pr_002_hu_007_ca_02_error_datos_incompletos():
    payload = {
        "cedula": "",
        "nombres_completos": "",
        "telefono": "",
        "correo_electronico": "not-an-email",
        "fecha_nacimiento": "2020-01-01",
        "nivel_estudios": ""
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 422

# --- PR-003 HU-007 CA-03: Error nivel estudios y edad mínima ---
def test_pr_003_hu_007_ca_03_error_nivel_estudios_y_edad():
    # Edad <= 23 años
    fecha_nac = date.today() - timedelta(days=365*20)
    payload = {
        "cedula": unique_cedula(),
        "nombres_completos": "Ana Gómez",
        "telefono": "0987654321",
        "correo_electronico": unique_email(),
        "fecha_nacimiento": fecha_nac.isoformat(),
        "nivel_estudios": "Primaria"  # inferior a bachillerato
    }
    response = client.post("/api/solicitudes", json=payload)
    assert response.status_code == 422
    # Debe contener mensajes de error específicos
    errors = response.json()
    error_msgs = str(errors)
    assert "Nivel de estudios mínimo: bachillerato" in error_msgs or "La edad debe ser mayor a 23 años" in error_msgs

# --- PR-004 HU-009 CA-01: Líder visualiza datos solicitante y aprobador ---
def test_pr_004_hu_009_ca_01_lider_visualiza_datos():
    # Se requiere token admin
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    # Obtener lista de solicitudes para tomar una
    response = client.get("/api/admin/solicitudes", headers=headers)
    assert response.status_code == 200
    solicitudes = response.json()
    if not solicitudes:
        # No hay solicitudes para probar
        return
    solicitud = solicitudes[0]
    solicitud_id = solicitud["id"]
    # Obtener detalle solicitud
    response = client.get(f"/api/admin/solicitudes/{solicitud_id}", headers=headers)
    assert response.status_code == 200
    detalle = response.json()
    # Verificar campos solicitante
    for campo in ["nombres_completos", "cedula", "area", "cargo", "fecha_nacimiento", "edad", "nivel_estudios"]:
        assert campo in detalle
    # Verificar campos aprobador (líder)
    lider = detalle.get("lider_area")
    assert lider is not None
    for campo in ["nombre", "cargo", "area", "correo_electronico"]:
        assert campo in lider

# --- PR-005 HU-010 CA-01: Líder aprueba solicitud y notifica admin ---
def test_pr_005_hu_010_ca_01_lider_aprueba_solicitud():
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    # Obtener solicitudes pendientes
    response = client.get("/api/admin/solicitudes", headers=headers)
    assert response.status_code == 200
    solicitudes = [s for s in response.json() if s["estado"] == "Pendiente"]
    if not solicitudes:
        return
    solicitud_id = solicitudes[0]["id"]
    payload = {"aprobar": True}
    response = client.patch(f"/api/admin/solicitudes/{solicitud_id}/decidir", json=payload, headers=headers)
    assert response.status_code == 200 or response.status_code == 204

# --- PR-006 HU-011 CA-01: Líder rechaza solicitud con motivo obligatorio ---
def test_pr_006_hu_011_ca_01_lider_rechaza_solicitud_con_motivo():
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    # Obtener solicitudes pendientes
    response = client.get("/api/admin/solicitudes", headers=headers)
    assert response.status_code == 200
    solicitudes = [s for s in response.json() if s["estado"] == "Pendiente"]
    if not solicitudes:
        return
    solicitud_id = solicitudes[0]["id"]
    payload = {"aprobar": False, "motivo_rechazo": "Datos incompletos"}
    response = client.patch(f"/api/admin/solicitudes/{solicitud_id}/decidir", json=payload, headers=headers)
    assert response.status_code == 200 or response.status_code == 204

# --- PR-007 HU-011 CA-01: Error rechazo sin motivo ---
def test_pr_007_hu_011_ca_01_error_rechazo_sin_motivo():
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    # Obtener solicitudes pendientes
    response = client.get("/api/admin/solicitudes", headers=headers)
    assert response.status_code == 200
    solicitudes = [s for s in response.json() if s["estado"] == "Pendiente"]
    if not solicitudes:
        return
    solicitud_id = solicitudes[0]["id"]
    payload = {"aprobar": False}
    response = client.patch(f"/api/admin/solicitudes/{solicitud_id}/decidir", json=payload, headers=headers)
    assert response.status_code == 422

# --- PR-008 Ruta pública GET /api/health ---
def test_pr_008_get_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}

# --- PR-009 Acceso sin token a rutas admin ---
def test_pr_009_admin_routes_without_token():
    urls = [
        "/api/admin/solicitudes",
        "/api/admin/solicitudes/1",
        "/api/admin/solicitudes/1/decidir"
    ]
    for url in urls:
        response = client.get(url) if 'decidir' not in url else client.patch(url, json={})
        assert response.status_code in (401, 403)

# --- PR-010 Acceso con token incorrecto a rutas admin ---
def test_pr_010_admin_routes_with_invalid_token():
    headers = {"Authorization": "Bearer invalidtoken"}
    urls = [
        "/api/admin/solicitudes",
        "/api/admin/solicitudes/1",
        "/api/admin/solicitudes/1/decidir"
    ]
    for url in urls:
        response = client.get(url, headers=headers) if 'decidir' not in url else client.patch(url, json={}, headers=headers)
        assert response.status_code in (401, 403)

# --- PR-011 Acceso con token correcto a rutas admin ---
def test_pr_011_admin_routes_with_valid_token():
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    urls = [
        "/api/admin/solicitudes",
    ]
    for url in urls:
        response = client.get(url, headers=headers)
        assert response.status_code == 200