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


# HU-005-CA-01: acceso administrativo requiere token.
def test_hu_005_ca_01_admin_sin_token_y_token_incorrecto():
    r_sin = client.get("/api/admin/tipos-ausencia")
    assert r_sin.status_code in (401, 403)

    r_malo = client.get("/api/admin/tipos-ausencia", headers={"Authorization": "Bearer token_incorrecto"})
    assert r_malo.status_code in (401, 403)


# HU-005-CA-01: el catálogo público debe ser distinto del administrativo.
def test_hu_005_ca_01_catalogo_publico_distinto_del_admin():
    r_publico = client.get("/api/tipos-ausencia")
    assert r_publico.status_code == 200
    assert isinstance(r_publico.json(), list)
    if r_publico.json():
        assert "activo" not in r_publico.json()[0]
        assert "flujo_aprobacion" not in r_publico.json()[0]

    r_admin = client.get("/api/admin/tipos-ausencia", headers=ADMIN_HEADERS)
    assert r_admin.status_code == 200
    assert isinstance(r_admin.json(), list)
    if r_admin.json():
        assert "activo" in r_admin.json()[0]
        assert "flujo_aprobacion" in r_admin.json()[0]


# HU-005-CA-01 y HU-005-CA-02: crear y actualizar tipo con flujo.
def test_hu_005_ca_01_02_crear_y_actualizar_tipo_con_flujo():
    codigo = _codigo_unico("VAC")
    payload = {
        "codigo": codigo,
        "nombre": f"Vacaciones {codigo}",
        "descripcion": "Prueba de administración",
        "activo": True,
        "requiere_motivo": False,
        "requiere_horas": False,
        "requiere_revision_jefe": True,
        "requiere_revision_th": False,
        "flujo_aprobacion": [{"rol_aprobador": "JEFE_INMEDIATO", "activo": True}],
    }
    r_crear = client.post("/api/admin/tipos-ausencia", json=payload, headers=ADMIN_HEADERS)
    assert r_crear.status_code in (200, 201)
    tipo_id = int(r_crear.json()["id"])

    r_admin_detalle = client.get("/api/admin/tipos-ausencia", headers=ADMIN_HEADERS)
    assert r_admin_detalle.status_code == 200
    assert any(item["id"] == tipo_id for item in r_admin_detalle.json())

    update = dict(payload)
    update["nombre"] = f"Vacaciones {codigo} actualizada"
    update["flujo_aprobacion"] = [
        {"rol_aprobador": "JEFE_INMEDIATO", "activo": True},
        {"rol_aprobador": "TALENTO_HUMANO", "activo": True},
    ]
    r_ok = client.put(f"/api/admin/tipos-ausencia/{tipo_id}", json=update, headers=ADMIN_HEADERS)
    assert r_ok.status_code in (200, 204)


# HU-005-CA-01: validación de duplicado en catálogo administrado.
def test_hu_005_ca_01_duplicado_codigo_rechazado():
    codigo = _codigo_unico("LIC")
    payload = {
        "codigo": codigo,
        "nombre": f"Licencia {codigo}",
        "descripcion": "Creación inicial",
        "activo": True,
        "requiere_motivo": True,
        "requiere_horas": False,
        "requiere_revision_jefe": True,
        "requiere_revision_th": False,
        "flujo_aprobacion": [],
    }
    r1 = client.post("/api/admin/tipos-ausencia", json=payload, headers=ADMIN_HEADERS)
    assert r1.status_code in (200, 201)

    r2 = client.post("/api/admin/tipos-ausencia", json=payload, headers=ADMIN_HEADERS)
    assert r2.status_code in (400, 409, 422)