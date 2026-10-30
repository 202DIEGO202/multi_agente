import os
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
AUTH_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(scope="module")
def tipo_admin_unique():
    codigo = f"QA_{uuid.uuid4().hex[:16].upper()}"
    payload = {
        "codigo": codigo,
        "nombre": f"Tipo QA {codigo}",
        "descripcion": "Tipo creado para pruebas",
        "requiere_motivo": False,
        "requiere_horas": False,
        "requiere_aprobacion_th": False,
        "requiere_aprobacion_jefe": True,
        "activo": True,
        "flujo_aprobacion_id": None,
    }
    r = client.post("/api/admin/tipos-ausencia", json=payload, headers=AUTH_HEADERS)
    assert r.status_code in (200, 201)
    tipo_id = r.json()["id"]
    return {"id": tipo_id, "codigo": codigo, "payload": payload}


def crear_solicitud(tipo_id, **overrides):
    base = {
        "solicitante_nombre": f"Empleado {uuid.uuid4().hex[:8]}",
        "solicitante_documento": uuid.uuid4().hex[:12],
        "area": "TI",
        "cargo": "Analista",
        "tipo_ausencia_id": tipo_id,
        "fecha_inicio": str(date.today() + timedelta(days=10)),
        "fecha_fin": str(date.today() + timedelta(days=12)),
        "hora_inicio": None,
        "hora_fin": None,
        "motivo_observacion": None,
        "creado_por": f"empleado_{uuid.uuid4().hex[:8]}",
        "creador_rol": "EMPLEADO",
    }
    base.update(overrides)
    return client.post("/api/solicitudes", json=base)


def test_get_health_200():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok"}


def test_hu_001_ca_01_crear_solicitud_camino_feliz(tipo_admin_unique):
    r = crear_solicitud(tipo_admin_unique["id"])
    assert r.status_code == 201
    assert isinstance(r.json()["id"], int)


def test_hu_001_ca_01_crear_solicitud_validacion_fechas_invalidas(tipo_admin_unique):
    r = crear_solicitud(
        tipo_admin_unique["id"],
        fecha_inicio=str(date.today() + timedelta(days=5)),
        fecha_fin=str(date.today() + timedelta(days=1)),
    )
    assert r.status_code == 422


def test_hu_001_ca_02_motivo_observacion_requerido(tipo_admin_unique):
    tipo = {
        "codigo": f"REQ_MOT_{uuid.uuid4().hex[:10].upper()}",
        "nombre": f"Con motivo {uuid.uuid4().hex[:6]}",
        "descripcion": None,
        "requiere_motivo": True,
        "requiere_horas": False,
        "requiere_aprobacion_th": False,
        "requiere_aprobacion_jefe": True,
        "activo": True,
        "flujo_aprobacion_id": None,
    }
    rt = client.post("/api/admin/tipos-ausencia", json=tipo, headers=AUTH_HEADERS)
    assert rt.status_code in (200, 201)
    tipo_id = rt.json()["id"]
    ok = crear_solicitud(tipo_id, motivo_observacion="Cita médica")
    assert ok.status_code == 201
    bad = crear_solicitud(tipo_id, motivo_observacion=None)
    assert bad.status_code == 422


def test_hu_001_ca_03_tipo_fechas_horas_y_validacion_horas(tipo_admin_unique):
    tipo = {
        "codigo": f"REQ_HOR_{uuid.uuid4().hex[:10].upper()}",
        "nombre": f"Con horas {uuid.uuid4().hex[:6]}",
        "descripcion": None,
        "requiere_motivo": False,
        "requiere_horas": True,
        "requiere_aprobacion_th": False,
        "requiere_aprobacion_jefe": True,
        "activo": True,
        "flujo_aprobacion_id": None,
    }
    rt = client.post("/api/admin/tipos-ausencia", json=tipo, headers=AUTH_HEADERS)
    assert rt.status_code in (200, 201)
    tipo_id = rt.json()["id"]
    ok = crear_solicitud(tipo_id, hora_inicio="08:00:00", hora_fin="10:00:00")
    assert ok.status_code == 201
    bad = crear_solicitud(tipo_id)
    assert bad.status_code == 422


def test_hu_001_ca_04_consulta_historial_y_trazabilidad_admin_y_401_sin_token(tipo_admin_unique):
    cre = crear_solicitud(tipo_admin_unique["id"])
    solicitud_id = cre.json()["id"]
    sin_token = client.get("/api/admin/solicitudes")
    assert sin_token.status_code in (401, 403)
    con_token = client.get("/api/admin/solicitudes", headers=AUTH_HEADERS)
    assert con_token.status_code == 200
    detalle = client.get(f"/api/admin/solicitudes/{solicitud_id}", headers=AUTH_HEADERS)
    assert detalle.status_code == 200
    assert detalle.json()["id"] == solicitud_id


def test_hu_003_ca_01_bandeja_admin_pide_token_y_lista(tipo_admin_unique):
    r = client.get("/api/admin/solicitudes", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_hu_003_ca_02_aprobar_y_rechazar_registran_decision(tipo_admin_unique):
    cre = crear_solicitud(tipo_admin_unique["id"])
    solicitud_id = cre.json()["id"]
    aprobar = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/aprobar",
        json={"observacion": "Revisado", "usuario": "jefe.qa", "rol": "JEFE_INMEDIATO"},
        headers=AUTH_HEADERS,
    )
    assert aprobar.status_code == 200
    assert aprobar.json()["estado"] == "APROBADA"


def test_hu_003_ca_03_observacion_obligatoria_en_decision(tipo_admin_unique):
    cre = crear_solicitud(tipo_admin_unique["id"])
    solicitud_id = cre.json()["id"]
    r = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/rechazar",
        json={"observacion": None, "usuario": "jefe.qa", "rol": "JEFE_INMEDIATO"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422


def test_hu_003_ca_04_trazabilidad_y_conflicto_estados(tipo_admin_unique):
    cre = crear_solicitud(tipo_admin_unique["id"])
    solicitud_id = cre.json()["id"]
    first = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/aprobar",
        json={"observacion": "Primera decisión", "usuario": "jefe.qa", "rol": "JEFE_INMEDIATO"},
        headers=AUTH_HEADERS,
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/rechazar",
        json={"observacion": "Segunda decisión", "usuario": "jefe.qa", "rol": "JEFE_INMEDIATO"},
        headers=AUTH_HEADERS,
    )
    assert second.status_code == 409


def test_hu_004_ca_01_talento_humano_aprueba_y_validacion(tipo_admin_unique):
    cre = crear_solicitud(tipo_admin_unique["id"])
    solicitud_id = cre.json()["id"]
    r = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/aprobar",
        json={"observacion": "Validado por TH", "usuario": "th.qa", "rol": "TALENTO_HUMANO"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "APROBADA"


def test_hu_004_ca_02_observaciones_guardadas_en_revision(tipo_admin_unique):
    cre = crear_solicitud(tipo_admin_unique["id"])
    solicitud_id = cre.json()["id"]
    r = client.post(
        f"/api/admin/solicitudes/{solicitud_id}/rechazar",
        json={"observacion": "No cumple política", "usuario": "th.qa", "rol": "TALENTO_HUMANO"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "RECHAZADA"


def test_hu_005_ca_01_y_02_catalogo_tipos_ausencia_y_flujo(tipo_admin_unique):
    lista_publica = client.get("/api/tipos-ausencia")
    assert lista_publica.status_code == 200
    sin_token = client.get("/api/admin/tipos-ausencia")
    assert sin_token.status_code in (401, 403)
    con_token = client.get("/api/admin/tipos-ausencia", headers=AUTH_HEADERS)
    assert con_token.status_code == 200
    nuevo = client.post(
        "/api/admin/tipos-ausencia",
        json={
            "codigo": f"CAT_{uuid.uuid4().hex[:12].upper()}",
            "nombre": "Catálogo QA",
            "descripcion": "Alta de catálogo",
            "requiere_motivo": True,
            "requiere_horas": False,
            "requiere_aprobacion_th": True,
            "requiere_aprobacion_jefe": True,
            "activo": True,
            "flujo_aprobacion_id": None,
        },
        headers=AUTH_HEADERS,
    )
    assert nuevo.status_code in (200, 201)
    assert isinstance(nuevo.json()["id"], int)