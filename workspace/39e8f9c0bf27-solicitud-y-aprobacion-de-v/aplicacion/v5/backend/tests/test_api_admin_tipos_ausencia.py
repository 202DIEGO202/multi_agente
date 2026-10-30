from __future__ import annotations

import os
import uuid
from datetime import datetime

import psycopg
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
HEADERS_ADMIN = {"Authorization": f"Bearer {ADMIN_API_TOKEN}"}


def _crear_tipo_ausencia(cursor, nombre: str, **kwargs):
    tipo_id = uuid.uuid4()
    cursor.execute(
        """
        INSERT INTO tipo_ausencia (
            id, nombre, descripcion, requiere_motivo, requiere_observacion,
            permite_horas, activo, version, creado_en, actualizado_en
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), now())
        """,
        (
            tipo_id,
            nombre,
            kwargs.get("descripcion"),
            kwargs.get("requiere_motivo", False),
            kwargs.get("requiere_observacion", False),
            kwargs.get("permite_horas", False),
            kwargs.get("activo", True),
            kwargs.get("version", 1),
        ),
    )
    return tipo_id


def test_hu_005_ca_01_publico_solo_id_y_nombre():
    # HU-005-CA-01: el catálogo público debe ser limitado
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            nombre = f"Tipo publico {uuid.uuid4()}"
            tipo_id = _crear_tipo_ausencia(cur, nombre, descripcion="desc", requiere_motivo=True, requiere_observacion=True, permite_horas=True)
    resp = client.get("/api/tipos-ausencia")
    assert resp.status_code == 200
    data = resp.json()
    item = next((x for x in data if x["id"] == str(tipo_id)), None)
    assert item is not None
    assert set(item.keys()) == {"id", "nombre"}
    assert item["nombre"] == nombre


def test_hu_005_ca_01_admin_requiere_token():
    resp = client.get("/api/admin/tipos-ausencia")
    assert resp.status_code in (401, 403)


def test_hu_005_ca_01_admin_devuelve_registro_completo_con_token():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            nombre = f"Tipo admin {uuid.uuid4()}"
            tipo_id = _crear_tipo_ausencia(cur, nombre, descripcion="desc admin", requiere_motivo=True, requiere_observacion=False, permite_horas=True)
    resp = client.get("/api/admin/tipos-ausencia", headers=HEADERS_ADMIN)
    assert resp.status_code == 200
    data = resp.json()
    item = next((x for x in data if x["id"] == str(tipo_id)), None)
    assert item is not None
    assert {"id", "nombre", "descripcion", "requiere_motivo", "requiere_observacion", "permite_horas", "activo", "version", "creado_en", "actualizado_en"}.issubset(item.keys())
    assert item["descripcion"] == "desc admin"
    assert isinstance(datetime.fromisoformat(item["creado_en"].replace("Z", "+00:00")), datetime)


def test_hu_005_ca_01_admin_token_incorrecto_deniega_acceso():
    resp = client.get("/api/admin/tipos-ausencia", headers={"Authorization": "Bearer incorrecto"})
    assert resp.status_code in (401, 403)