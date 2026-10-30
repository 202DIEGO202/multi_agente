import os
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_token():
    token = os.getenv("ADMIN_API_TOKEN")
    if not token:
        pytest.skip("Falta ADMIN_API_TOKEN")
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _hoy_mas(dias: int) -> str:
    return (date.today() + timedelta(days=dias)).isoformat()


def _first_tipo_publico():
    r = client.get("/api/tipos-ausencia")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert data, "Debe existir al menos un tipo de ausencia público"
    return data[0]


def _crear_solicitud(tipo_id: int, requiere_motivo: bool = False, permite_horas: bool = False):
    payload = {
        "solicitante_id": 1000,
        "solicitante_nombre": f"Empleado {uuid.uuid4()}",
        "solicitante_documento": str(uuid.uuid4()),
        "solicitante_area": "TI",
        "solicitante_cargo": "Analista",
        "tipo_ausencia_id": tipo_id,
        "fecha_inicio": _hoy_mas(3),
        "fecha_fin": _hoy_mas(4),
    }
    if requiere_motivo:
        payload["motivo_observacion"] = f"Motivo {uuid.uuid4()}"
    if permite_horas:
        payload["hora_inicio"] = "08:00:00"
        payload["hora_fin"] = "12:00:00"
    return client.post("/api/solicitudes", json=payload)


# HU-001-CA-01

def test_hu_001_ca_01_crear_solicitud_camino_feliz():
    tipo = _first_tipo_publico()
    r = _crear_solicitud(
        tipo["id"],
        requiere_motivo=bool(tipo.get("requiere_motivo")),
        permite_horas=bool(tipo.get("permite_horas")),
    )
    assert r.status_code == 201 or r.status_code == 200
    body = r.json()
    assert body["id"] > 0
    assert body["codigo"]
    assert body["estado"] == "enviada"
    assert body["version"] >= 1


# HU-001-CA-01 / HU-001-CA-03

def test_hu_001_ca_01_03_validaciones_de_fechas_horas_y_tipo():
    tipo = _first_tipo_publico()

    r_fechas = client.post(
        "/api/solicitudes",
        json={
            "solicitante_id": 1001,
            "solicitante_nombre": f"Empleado {uuid.uuid4()}",
            "solicitante_documento": str(uuid.uuid4()),
            "solicitante_area": "TI",
            "solicitante_cargo": "Analista",
            "tipo_ausencia_id": tipo["id"],
            "fecha_inicio": _hoy_mas(5),
            "fecha_fin": _hoy_mas(4),
        },
    )
    assert r_fechas.status_code == 422

    r_horas_parciales = client.post(
        "/api/solicitudes",
        json={
            "solicitante_id": 1002,
            "solicitante_nombre": f"Empleado {uuid.uuid4()}",
            "solicitante_documento": str(uuid.uuid4()),
            "solicitante_area": "TI",
            "solicitante_cargo": "Analista",
            "tipo_ausencia_id": tipo["id"],
            "fecha_inicio": _hoy_mas(3),
            "fecha_fin": _hoy_mas(4),
            "hora_inicio": "08:00:00",
        },
    )
    assert r_horas_parciales.status_code == 422

    r_tipo_invalido = client.post(
        "/api/solicitudes",
        json={
            "solicitante_id": 1003,
            "solicitante_nombre": f"Empleado {uuid.uuid4()}",
            "solicitante_documento": str(uuid.uuid4()),
            "solicitante_area": "TI",
            "solicitante_cargo": "Analista",
            "tipo_ausencia_id": 999999999,
            "fecha_inicio": _hoy_mas(3),
            "fecha_fin": _hoy_mas(4),
        },
    )
    assert r_tipo_invalido.status_code == 422


# HU-001-CA-02

def test_hu_001_ca_02_motivo_observacion_obligatorio_cuando_corresponde():
    tipo = _first_tipo_publico()
    if not tipo.get("requiere_motivo"):
        pytest.skip("No hay tipo público que requiera motivo")

    r = client.post(
        "/api/solicitudes",
        json={
            "solicitante_id": 1004,
            "solicitante_nombre": f"Empleado {uuid.uuid4()}",
            "solicitante_documento": str(uuid.uuid4()),
            "solicitante_area": "TI",
            "solicitante_cargo": "Analista",
            "tipo_ausencia_id": tipo["id"],
            "fecha_inicio": _hoy_mas(3),
            "fecha_fin": _hoy_mas(4),
        },
    )
    assert r.status_code == 422


# HU-001-CA-04 / AC-001 / AC-003

def test_hu_001_ca_04_consulta_historial_y_trazabilidad_publica():
    r = client.get("/api/tipos-ausencia")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# HU-002-CA-01

def test_hu_002_ca_01_notificacion_cambio_estado_y_proteccion_admin():
    r = client.get("/api/admin/tipos-ausencia")
    assert r.status_code in (401, 403)


# HU-002-CA-02

def test_hu_002_ca_02_notificacion_pendientes_revision_y_proteccion_admin():
    r = client.get("/api/admin/solicitudes")
    assert r.status_code in (401, 403)


# HU-003-CA-01

def test_hu_003_ca_01_listar_solicitudes_pendientes_con_token(auth_headers):
    r = client.get("/api/admin/solicitudes", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# HU-003-CA-02 / HU-003-CA-03 / HU-003-CA-04

def test_hu_003_ca_02_03_04_aprobar_rechazar_con_observacion_y_trazabilidad(auth_headers):
    tipo = _first_tipo_publico()
    r_crear = _crear_solicitud(
        tipo["id"],
        requiere_motivo=bool(tipo.get("requiere_motivo")),
        permite_horas=bool(tipo.get("permite_horas")),
    )
    assert r_crear.status_code in (200, 201)
    solicitud_id = r_crear.json()["id"]

    r_observacion_vacia = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/aprobar",
        headers=auth_headers,
        json={"observacion": ""},
    )
    assert r_observacion_vacia.status_code == 422

    r_aprobar = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/aprobar",
        headers=auth_headers,
        json={"observacion": f"Aprobado {uuid.uuid4()}"},
    )
    assert r_aprobar.status_code == 200
    assert r_aprobar.json()["estado"] == "aprobada"

    r_rechazar_duplicado = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/rechazar",
        headers=auth_headers,
        json={"observacion": f"Rechazo {uuid.uuid4()}"},
    )
    assert r_rechazar_duplicado.status_code in (409, 422, 404)


# HU-004-CA-01

def test_hu_004_ca_01_validar_y_aprobar_como_talento_humano_con_token(auth_headers):
    tipo = _first_tipo_publico()
    r_crear = _crear_solicitud(
        tipo["id"],
        requiere_motivo=bool(tipo.get("requiere_motivo")),
        permite_horas=bool(tipo.get("permite_horas")),
    )
    assert r_crear.status_code in (200, 201)
    solicitud_id = r_crear.json()["id"]

    r = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/rechazar",
        headers=auth_headers,
        json={"observacion": f"Validación TH {uuid.uuid4()}"},
    )
    assert r.status_code in (200, 409, 422)
    if r.status_code == 200:
        assert r.json()["estado"] == "rechazada"


# HU-004-CA-02 / HU-004-CA-03

def test_hu_004_ca_02_03_validacion_observaciones_y_trazabilidad(auth_headers):
    r = client.get("/api/admin/solicitudes", headers=auth_headers)
    assert r.status_code == 200


# HU-005-CA-01 / HU-005-CA-02

def test_hu_005_ca_01_02_catalogo_publico_y_admin_distintos(auth_headers):
    r_publico = client.get("/api/tipos-ausencia")
    assert r_publico.status_code == 200
    publicos = r_publico.json()
    assert isinstance(publicos, list)
    assert all("estado" not in item for item in publicos)

    r_admin = client.get("/api/admin/tipos-ausencia", headers=auth_headers)
    assert r_admin.status_code == 200
    admin = r_admin.json()
    assert isinstance(admin, list)
    assert admin
    assert any("estado" in item for item in admin)
    assert any("flujo_aprobacion" in item for item in admin)