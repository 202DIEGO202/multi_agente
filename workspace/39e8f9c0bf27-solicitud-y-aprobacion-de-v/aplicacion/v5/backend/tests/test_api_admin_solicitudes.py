from __future__ import annotations

import os
import uuid
from datetime import date

import psycopg
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
HEADERS_ADMIN = {"Authorization": f"Bearer {ADMIN_API_TOKEN}"}


def _setup_datos(conn):
    with conn.cursor() as cur:
        solicitante_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO usuario_aplicacion (id, correo, nombre_completo, aplicacion, es_administrador, activo)
            VALUES (%s, %s, %s, 'portal', FALSE, TRUE)
            """,
            (solicitante_id, f"solicitante-{solicitante_id}@example.com", "Solicitante Prueba"),
        )
        revisor_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO usuario_aplicacion (id, correo, nombre_completo, aplicacion, es_administrador, activo)
            VALUES (%s, %s, %s, 'panel', TRUE, TRUE)
            """,
            (revisor_id, f"revisor-{revisor_id}@example.com", "Revisor Prueba"),
        )
        tipo_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO tipo_ausencia (id, nombre, descripcion, requiere_motivo, requiere_observacion, permite_horas, activo, version)
            VALUES (%s, %s, %s, FALSE, FALSE, FALSE, TRUE, 1)
            """,
            (tipo_id, f"Tipo Solicitud {uuid.uuid4()}", "desc"),
        )
        solicitud_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO solicitud_ausencia (
                id, solicitante_id, tipo_ausencia_id, estado_id, fecha_inicio, fecha_fin,
                hora_inicio, hora_fin, motivo, observacion, version
            ) VALUES (
                %s, %s, %s,
                (SELECT id FROM estado_solicitud WHERE codigo = 'ENVIADA'),
                %s, %s, NULL, NULL, %s, %s, 1
            )
            """,
            (solicitud_id, solicitante_id, tipo_id, date.today(), date.today(), "Motivo", "Obs"),
        )
        return solicitante_id, revisor_id, tipo_id, solicitud_id


def test_hu_003_ca_01_detalle_admin_requiere_token_y_devuelve_historial():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        solicitante_id, revisor_id, tipo_id, solicitud_id = _setup_datos(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO historial_solicitud (solicitud_id, estado_id, actor_id, operacion, observacion, detalle)
                VALUES (%s, (SELECT id FROM estado_solicitud WHERE codigo = 'ENVIADA'), %s, 'CREAR', %s, '{}'::jsonb)
                """,
                (solicitud_id, solicitante_id, "Creada"),
            )
    resp = client.get(f"/api/admin/solicitudes/{solicitud_id}", headers=HEADERS_ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(solicitud_id)
    assert body["solicitante_id"] == str(solicitante_id)
    assert isinstance(body["historial"], list)
    assert len(body["historial"]) >= 1


def test_hu_003_ca_01_detalle_admin_sin_token_deniega():
    resp = client.get(f"/api/admin/solicitudes/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)


def test_hu_003_ca_02_aprobar_solicitud_exitosa():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        _, _, _, solicitud_id = _setup_datos(conn)
    resp = client.post(f"/api/admin/solicitudes/{solicitud_id}/aprobar", headers=HEADERS_ADMIN, json={"observacion": "OK"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["solicitud_id"] == str(solicitud_id)
    assert body["estado_resultante"] == "APROBADA"
    assert body["observacion"] == "OK"


def test_hu_003_ca_02_rechazar_solicitud_exitosa_y_observacion_obligatoria():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        _, _, _, solicitud_id = _setup_datos(conn)
    resp_err = client.post(f"/api/admin/solicitudes/{solicitud_id}/rechazar", headers=HEADERS_ADMIN, json={})
    assert resp_err.status_code == 422
    resp_ok = client.post(f"/api/admin/solicitudes/{solicitud_id}/rechazar", headers=HEADERS_ADMIN, json={"observacion": "No procede"})
    assert resp_ok.status_code == 200
    assert resp_ok.json()["estado_resultante"] == "RECHAZADA"


def test_hu_003_ca_02_aprobar_no_autorizado():
    resp = client.post(f"/api/admin/solicitudes/{uuid.uuid4()}/aprobar", json={"observacion": "x"})
    assert resp.status_code in (401, 403)


def test_hu_003_ca_02_rechazar_requiere_token():
    resp = client.post(f"/api/admin/solicitudes/{uuid.uuid4()}/rechazar", json={"observacion": "x"})
    assert resp.status_code in (401, 403)


def test_hu_003_ca_02_version_duplicada_o_estado_final_rechaza_segunda_decision():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        _, _, _, solicitud_id = _setup_datos(conn)
    first = client.post(f"/api/admin/solicitudes/{solicitud_id}/aprobar", headers=HEADERS_ADMIN, json={"observacion": "primera"})
    assert first.status_code == 200
    second = client.post(f"/api/admin/solicitudes/{solicitud_id}/rechazar", headers=HEADERS_ADMIN, json={"observacion": "segunda"})
    assert second.status_code in (409, 422)