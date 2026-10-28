import os
import uuid
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ADMIN_TOKEN = os.getenv('ADMIN_API_TOKEN')
HEADERS_ADMIN = {'Authorization': f'Bearer {ADMIN_TOKEN}'} if ADMIN_TOKEN else {}

# Datos base válidos para crear solicitud
def datos_solicitud_valida():
    # Edad > 23 años
    fecha_nac = date.today() - timedelta(days=365*30)
    return {
        "cedula": str(uuid.uuid4()),
        "nombres": "Juan Pérez",
        "telefono": "123456789",
        "correo_electronico": f"user{uuid.uuid4().hex[:6]}@test.com",
        "fecha_nacimiento": fecha_nac.isoformat(),
        "nivel_estudios": "Bachillerato"
    }

# --- Test GET /api/health ---
def test_pr_001_hu_007_ca_01_health_check():
    # Verifica que el endpoint de salud responde 200 con estado ok
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'estado': 'ok'}

# --- Test acceso a rutas admin sin token ---
@pytest.mark.parametrize("ruta,metodo", [
    ("/api/admin/solicitudes", "GET"),
    ("/api/admin/solicitudes/1", "GET"),
    ("/api/admin/solicitudes/1/decidir", "POST"),
])
def test_pr_002_admin_rutas_sin_token_401_o_403(ruta, metodo):
    # Sin token debe responder 401 o 403
    if metodo == "GET":
        response = client.get(ruta)
    elif metodo == "POST":
        response = client.post(ruta, json={"aprobar": True})
    else:
        pytest.skip("Método no implementado")
    assert response.status_code in (401, 403)

# --- Test acceso a rutas admin con token correcto ---
@pytest.mark.parametrize("ruta,metodo", [
    ("/api/admin/solicitudes", "GET"),
    ("/api/admin/solicitudes/1", "GET"),
    ("/api/admin/solicitudes/1/decidir", "POST"),
])
def test_pr_003_admin_rutas_con_token_200(ruta, metodo):
    if not ADMIN_TOKEN:
        pytest.skip("No hay token ADMIN_API_TOKEN configurado")
    if metodo == "GET":
        response = client.get(ruta, headers=HEADERS_ADMIN)
    elif metodo == "POST":
        response = client.post(ruta, headers=HEADERS_ADMIN, json={"aprobar": True})
    else:
        pytest.skip("Método no implementado")
    assert response.status_code == 200

# --- Test creación solicitud HU-007-CA-01 camino feliz ---
def test_pr_004_hu_007_ca_01_crear_solicitud_valida():
    datos = datos_solicitud_valida()
    response = client.post('/api/solicitudes', json=datos)
    assert response.status_code == 201
    json_resp = response.json()
    assert 'id' in json_resp
    assert json_resp['estado'] == 'Pendiente'

# --- Test creación solicitud HU-007-CA-02 datos incompletos o invalidos ---
@pytest.mark.parametrize("campo,valor,msj_esperado", [
    ("cedula", "", "field required"),
    ("nombres", "", "field required"),
    ("telefono", "", "field required"),
    ("correo_electronico", "notanemail", "value is not a valid email address"),
    ("fecha_nacimiento", "2024-01-01", "La edad debe ser mayor a 23 años"),
    ("nivel_estudios", "NoGraduado", "Nivel de estudios mínimo: bachillerato"),
])
def test_pr_005_hu_007_ca_02_validaciones_fallidas(campo, valor, msj_esperado):
    datos = datos_solicitud_valida()
    datos[campo] = valor
    response = client.post('/api/solicitudes', json=datos)
    assert response.status_code == 422
    # Verificar mensaje de error específico
    errores = response.json().get('detail', [])
    mensajes = []
    for err in errores:
        if 'msg' in err:
            mensajes.append(err['msg'])
    assert any(msj_esperado in m for m in mensajes)

# --- Test creación solicitud HU-007-CA-03 nivel de estudios y edad invalidos ---
def test_pr_006_hu_007_ca_03_nivel_estudios_y_edad_invalidos():
    datos = datos_solicitud_valida()
    datos['nivel_estudios'] = 'NoGraduado'
    datos['fecha_nacimiento'] = (date.today() - timedelta(days=365*20)).isoformat()  # 20 años
    response = client.post('/api/solicitudes', json=datos)
    assert response.status_code == 422
    errores = response.json().get('detail', [])
    mensajes = [err.get('msg', '') for err in errores]
    assert any('Nivel de estudios mínimo: bachillerato' in m for m in mensajes)
    assert any('La edad debe ser mayor a 23 años' in m for m in mensajes)

# --- Test consulta solicitud por id ---
def test_pr_007_hu_007_ca_01_consultar_solicitud():
    # Crear solicitud primero
    datos = datos_solicitud_valida()
    response = client.post('/api/solicitudes', json=datos)
    assert response.status_code == 201
    solicitud_id = response.json()['id']

    # Consultar solicitud
    response_get = client.get(f'/api/solicitudes/{solicitud_id}')
    assert response_get.status_code == 200
    json_resp = response_get.json()
    assert json_resp['id'] == solicitud_id
    assert json_resp['estado'] == 'Pendiente'

# --- Test admin lista solicitudes con token ---
def test_pr_008_hu_009_hu_010_hu_011_admin_lista_solicitudes():
    if not ADMIN_TOKEN:
        pytest.skip("No hay token ADMIN_API_TOKEN configurado")
    response = client.get('/api/admin/solicitudes', headers=HEADERS_ADMIN)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# Nota: Para pruebas de aprobación y rechazo se requiere que existan solicitudes y usuarios configurados en DB,
# y que el token admin sea válido. Estas pruebas pueden ser extendidas en integración.