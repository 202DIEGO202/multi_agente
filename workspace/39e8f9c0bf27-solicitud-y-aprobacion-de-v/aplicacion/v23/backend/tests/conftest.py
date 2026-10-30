import os
import secrets

import pytest


@pytest.fixture(autouse=True)
def configurar_credencial_empleado(monkeypatch):
    # Docker solo garantiza ADMIN_API_TOKEN y DATABASE_URL.
    # La credencial efímera se configura en el entorno, sin sustituir autenticación.
    if not os.environ.get('EMPLOYEE_API_TOKEN'):
        credential = secrets.token_urlsafe(48)
        while credential == os.environ.get('ADMIN_API_TOKEN'):
            credential = secrets.token_urlsafe(48)
        monkeypatch.setenv('EMPLOYEE_API_TOKEN', credential)
    # Una credencial existente se conserva; también su validación de aislamiento.
    yield