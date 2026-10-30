import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
AUTH_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"} if ADMIN_TOKEN else {}


@pytest.mark.parametrize(
    "ruta,metodo",
    [
        ("/api/admin/tipos-ausencia", "GET"),
        ("/api/admin/tipos-ausencia/1", "PUT"),
        ("/api/admin/tipos-ausencia/1/flujo", "PUT"),
    ],
)
def test_hu_005_ca_01_admin_sin_token_rechaza(ruta, metodo):
    # HU-005-CA-01: acceso administrativo exige autenticación
    response = client.request(metodo, ruta)
    assert response.status_code in (401, 403)


def test_hu_005_ca_01_listado_publico_restringido_no_exponer_campos_admin():
    # HU-005-CA-01: el público no debe ver campos administrativos
    response = client.get("/api/tipos-ausencia")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert {"id", "nombre", "descripcion", "permite_horas"}.issubset(item.keys())
        assert "codigo" not in item
        assert "requiere_motivo" not in item
        assert "requiere_observacion" not in item
        assert "requiere_validacion_th" not in item
        assert "visible_publico" not in item
        assert "visible_portal" not in item
        assert "activo" not in item
        assert "version" not in item


def test_hu_005_ca_01_listado_admin_con_token_ok_y_campos_completos():
    # HU-005-CA-01: listado administrativo completo
    response = client.get("/api/admin/tipos-ausencia", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        expected = {
            "id",
            "codigo",
            "nombre",
            "descripcion",
            "requiere_motivo",
            "requiere_observacion",
            "permite_horas",
            "requiere_validacion_th",
            "activo",
            "visible_portal",
            "visible_publico",
            "version",
        }
        assert expected.issubset(item.keys())


def test_hu_005_ca_01_crear_tipo_ausencia_valido_y_duplicado():
    # HU-005-CA-01: crear y validar duplicado
    codigo = f"TA-{uuid.uuid4().hex[:10]}"
    payload = {
        "codigo": codigo,
        "nombre": f"Tipo {codigo}",
        "descripcion": "Prueba",
        "requiere_motivo": True,
        "requiere_observacion": False,
        "permite_horas": True,
        "requiere_validacion_th": False,
        "activo": True,
        "visible_portal": True,
        "visible_publico": False,
    }
    r1 = client.post("/api/admin/tipos-ausencia", json=payload, headers=AUTH_HEADERS)
    assert r1.status_code == 201
    created = r1.json()
    assert created["codigo"] == codigo
    r2 = client.post("/api/admin/tipos-ausencia", json=payload, headers=AUTH_HEADERS)
    assert r2.status_code in (400, 409, 422)


def test_hu_005_ca_01_crear_tipo_ausencia_validacion_campos():
    # HU-005-CA-01: validación de campos obligatorios
    payload = {
        "codigo": "",
        "nombre": "",
        "descripcion": None,
        "requiere_motivo": False,
        "requiere_observacion": False,
        "permite_horas": False,
        "requiere_validacion_th": False,
        "activo": True,
        "visible_portal": True,
        "visible_publico": False,
    }
    response = client.post("/api/admin/tipos-ausencia", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_hu_005_ca_02_asignar_flujo_valido_y_error_sin_pasos():
    # HU-005-CA-02: asignación de flujo y validación de lista vacía
    codigo = f"TF-{uuid.uuid4().hex[:10]}"
    payload = {
        "codigo": codigo,
        "nombre": f"Flujo {codigo}",
        "descripcion": "Con flujo",
        "requiere_motivo": False,
        "requiere_observacion": False,
        "permite_horas": False,
        "requiere_validacion_th": True,
        "activo": True,
        "visible_portal": True,
        "visible_publico": True,
    }
    created = client.post("/api/admin/tipos-ausencia", json=payload, headers=AUTH_HEADERS)
    assert created.status_code == 201
    tipo_id = created.json()["id"]

    flujo = [{"rol_aprobador_codigo": "JEFATURA", "es_obligatorio": True, "activo": True}]
    r1 = client.put(f"/api/admin/tipos-ausencia/{tipo_id}/flujo", json=flujo, headers=AUTH_HEADERS)
    assert r1.status_code == 200
    assert "flujo_aprobacion_id" in r1.json()

    r2 = client.put(f"/api/admin/tipos-ausencia/{tipo_id}/flujo", json=[], headers=AUTH_HEADERS)
    assert r2.status_code in (400, 422)


def test_hu_005_ca_02_asignar_flujo_rol_invalido():
    # HU-005-CA-02: rol aprobador inválido rechaza
    codigo = f"TI-{uuid.uuid4().hex[:10]}"
    payload = {
        "codigo": codigo,
        "nombre": f"Invalido {codigo}",
        "descripcion": None,
        "requiere_motivo": False,
        "requiere_observacion": False,
        "permite_horas": False,
        "requiere_validacion_th": False,
        "activo": True,
        "visible_portal": True,
        "visible_publico": False,
    }
    created = client.post("/api/admin/tipos-ausencia", json=payload, headers=AUTH_HEADERS)
    assert created.status_code == 201
    tipo_id = created.json()["id"]
    r = client.put(
        f"/api/admin/tipos-ausencia/{tipo_id}/flujo",
        json=[{"rol_aprobador_codigo": "ROL-QUE-NO-EXISTE", "es_obligatorio": True, "activo": True}],
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422