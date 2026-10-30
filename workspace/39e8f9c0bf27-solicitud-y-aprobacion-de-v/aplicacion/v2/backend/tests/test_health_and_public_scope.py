from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_hu_001_ca_01_health_ok():
    # HU-001-CA-01: salud pública
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}


def test_hu_001_ca_03_publico_no_debe_exponer_campos_administrativos():
    # HU-001-CA-03: el listado público debe estar restringido
    response = client.get("/api/tipos-ausencia")
    assert response.status_code == 200
    for item in response.json() or []:
        assert "requiere_motivo" not in item
        assert "requiere_observacion" not in item
        assert "requiere_validacion_th" not in item
        assert "visible_publico" not in item
        assert "version" not in item