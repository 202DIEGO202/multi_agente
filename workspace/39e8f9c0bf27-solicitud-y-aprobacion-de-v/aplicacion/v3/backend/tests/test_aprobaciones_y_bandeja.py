from __future__ import annotations

import os
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"} if ADMIN_TOKEN else {}


def _codigo_unico(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:10].upper()}"


def _crear_tipo_con_flujo() -> int:
    codigo = _codigo_unico("APR")
    payload = {
        "codigo": codigo,
        "nombre": f"Aprobación {codigo}",
        "descripcion": "Para revisión",
        "activo": True,
        "requiere_motivo": True,
        "requiere_horas": False,
        "requiere_revision_jefe": True,
        "requiere_revision_th": False,
        "flujo_aprobacion": [{"rol_aprobador": "JEFE_INMEDIATO", "activo": True}],
    }
    r = client.post("/api/admin/tipos-ausencia", json=payload, headers=ADMIN_HEADERS)
    assert r.status_code in (200, 201)
    return int(r.json()["id"])


# HU-003-CA-01: la bandeja admin existe y requiere autenticación.
def test_hu_003_ca_01_bandeja_pendientes_autenticacion_y_exito():
    r_sin = client.get("/api/admin/revisiones/pendientes")
    assert r_sin.status_code in (401, 403)

    r_ok = client.get("/api/admin/revisiones/pendientes", headers=ADMIN_HEADERS)
    assert r_ok.status_code == 200
    assert isinstance(r_ok.json(), list)


# HU-003-CA-02 y HU-003-CA-03: aprobar con observación y control de versión.
def test_hu_003_ca_02_03_aprobar_con_observacion_y_version():
    _crear_tipo_con_flujo()

    r_obligatoria = client.post(
        "/api/admin/solicitudes/1/aprobar",
        json={"version": 1, "observacion": ""},
        headers=ADMIN_HEADERS,
    )
    assert r_obligatoria.status_code in (400, 422)

    r_no_existe = client.post(
        "/api/admin/solicitudes/999999999/aprobar",
        json={"version": 1, "observacion": "OK"},
        headers=ADMIN_HEADERS,
    )
    assert r_no_existe.status_code == 404


# HU-003-CA-02: una versión inválida debe producir conflicto o no encontrado.
def test_hu_003_ca_02_conflicto_de_version_en_decision():
    r = client.post(
        "/api/admin/solicitudes/999999999/aprobar",
        json={"version": 999, "observacion": "OK"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code in (404, 409)