from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"} if ADMIN_TOKEN else {}


# HU-003-CA-02 y HU-003-CA-03: rechazar requiere motivo/observación y token.
def test_hu_003_ca_02_rechazar_requiere_observacion_y_token():
    r_sin = client.post(
        "/api/admin/solicitudes/123/rechazar",
        json={"version": 1, "observacion": "Motivo"},
    )
    assert r_sin.status_code in (401, 403)

    r_sin_obs = client.post(
        "/api/admin/solicitudes/123/rechazar",
        json={"version": 1, "observacion": ""},
        headers=ADMIN_HEADERS,
    )
    assert r_sin_obs.status_code in (400, 422)