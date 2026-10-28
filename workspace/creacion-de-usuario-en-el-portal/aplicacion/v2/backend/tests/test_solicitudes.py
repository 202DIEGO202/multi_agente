import uuid
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Datos base para pruebas
NIVEL_ESTUDIOS_VALIDO = 'bachillerato'
NIVEL_ESTUDIOS_INVALIDO = 'primaria'

# Fecha para edad mayor a 23 años
fecha_nacimiento_valida = (date.today() - timedelta(days=365*24)).isoformat()  # 24 años
fecha_nacimiento_invalida = (date.today() - timedelta(days=365*20)).isoformat()  # 20 años

# Generar datos únicos con uuid

def generar_datos_unicos(nivel_estudios=NIVEL_ESTUDIOS_VALIDO, fecha_nacimiento=fecha_nacimiento_valida):
    uid = str(uuid.uuid4())
    return {
        "cedula": f"{uid[:10]}",
        "nombres": f"Test User {uid[:8]}",
        "telefono": "1234567890",
        "correo_electronico": f"test_{uid[:8]}@example.com",
        "fecha_nacimiento": fecha_nacimiento,
        "nivel_estudios": nivel_estudios
    }

# PR-001 HU-007-CA-01: Validar creación solicitud con datos correctos

def test_pr_001_hu_007_ca_01_crear_solicitud_valida():
    datos = generar_datos_unicos()
    response = client.post("/api/solicitudes", json=datos)
    assert response.status_code == 200
    data = response.json()
    assert data["cedula"] == datos["cedula"]
    assert data["nombres"] == datos["nombres"]
    assert data["correo_electronico"] == datos["correo_electronico"]
    assert data["nivel_estudios"] == datos["nivel_estudios"]
    assert data["estado"] == "Pendiente"

# PR-002 HU-007-CA-02: Validar error por datos incompletos (falta nombres)

def test_pr_002_hu_007_ca_02_error_datos_incompletos():
    datos = generar_datos_unicos()
    del datos["nombres"]
    response = client.post("/api/solicitudes", json=datos)
    assert response.status_code == 422
    assert "nombres" in response.text

# PR-003 HU-007-CA-02: Validar error por edad menor o igual a 23 años

def test_pr_003_hu_007_ca_02_error_edad():
    datos = generar_datos_unicos(fecha_nacimiento=fecha_nacimiento_invalida)
    response = client.post("/api/solicitudes", json=datos)
    assert response.status_code == 422
    assert "La edad debe ser mayor a 23 años" in response.text

# PR-004 HU-007-CA-03: Validar error por nivel de estudios menor a bachillerato

def test_pr_004_hu_007_ca_03_error_nivel_estudios():
    datos = generar_datos_unicos(nivel_estudios=NIVEL_ESTUDIOS_INVALIDO)
    response = client.post("/api/solicitudes", json=datos)
    assert response.status_code == 422
    assert "Nivel de estudios mínimo: bachillerato" in response.text

# PR-005 HU-009-CA-01: Visualizar datos de solicitud creada

def test_pr_005_hu_009_ca_01_visualizar_solicitud():
    datos = generar_datos_unicos()
    # Crear solicitud
    response = client.post("/api/solicitudes", json=datos)
    assert response.status_code == 200
    solicitud_id = response.json()["id"]

    # Obtener solicitud
    response_get = client.get(f"/api/solicitudes/{solicitud_id}")
    assert response_get.status_code == 200
    data = response_get.json()
    assert data["cedula"] == datos["cedula"]
    assert data["nombres"] == datos["nombres"]
    assert data["nivel_estudios"] == datos["nivel_estudios"]
    assert data["estado"] == "Pendiente"

# PR-006 HU-010-CA-01: Aprobar solicitud y verificar respuesta

def test_pr_006_hu_010_ca_01_aprobar_solicitud():
    datos = generar_datos_unicos()
    # Crear solicitud
    response = client.post("/api/solicitudes", json=datos)
    solicitud_id = response.json()["id"]

    # Aprobar solicitud
    patch_data = {"aprobado": True}
    response_patch = client.patch(f"/api/solicitudes/{solicitud_id}/estado", json=patch_data)
    assert response_patch.status_code == 200
    assert "actualizado correctamente" in response_patch.json().get("mensaje", "").lower()

# PR-007 HU-011-CA-01: Rechazar solicitud con motivo obligatorio

def test_pr_007_hu_011_ca_01_rechazar_solicitud_con_motivo():
    datos = generar_datos_unicos()
    # Crear solicitud
    response = client.post("/api/solicitudes", json=datos)
    solicitud_id = response.json()["id"]

    # Rechazar sin motivo debe fallar
    patch_data_sin_motivo = {"aprobado": False}
    response_patch_fail = client.patch(f"/api/solicitudes/{solicitud_id}/estado", json=patch_data_sin_motivo)
    assert response_patch_fail.status_code == 422
    assert "motivo de rechazo es obligatorio" in response_patch_fail.text.lower()

    # Rechazar con motivo debe pasar
    patch_data = {"aprobado": False, "motivo_rechazo": "Datos incompletos"}
    response_patch = client.patch(f"/api/solicitudes/{solicitud_id}/estado", json=patch_data)
    assert response_patch.status_code == 200
    assert "actualizado correctamente" in response_patch.json().get("mensaje", "").lower()

# PR-008 HU-011-CA-01: Verificar estado 'Rechazada' y motivo en solicitud

def test_pr_008_hu_011_ca_01_estado_rechazada_y_motivo():
    datos = generar_datos_unicos()
    # Crear solicitud
    response = client.post("/api/solicitudes", json=datos)
    solicitud_id = response.json()["id"]

    # Rechazar con motivo
    motivo = "Error en datos"
    patch_data = {"aprobado": False, "motivo_rechazo": motivo}
    client.patch(f"/api/solicitudes/{solicitud_id}/estado", json=patch_data)

    # Obtener solicitud y verificar
    response_get = client.get(f"/api/solicitudes/{solicitud_id}")
    data = response_get.json()
    assert data["estado"].lower() == "rechazada"
    assert data["motivo_rechazo"] == motivo