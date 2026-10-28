"""El registro de fallos conserva el diagnóstico sin exponer secretos."""

from app.providers import ProviderError
from app.services.failures import failure_detail, safe_text


def test_failure_detail_keeps_message_and_http_status():
    detail = failure_detail(
        ProviderError("La API respondió con el estado 429.", status=429), "r", "fase_5"
    )
    assert detail == {
        "tipo_error": "ProviderError",
        "detalle": "La API respondió con el estado 429.",
        "estado_http": 429,
    }


def test_secrets_are_masked_in_details():
    text = safe_text("fallo con api_key=abc123 y Authorization: Bearer xyz y password=secreta")
    assert "abc123" not in text and "xyz" not in text and "secreta" not in text
