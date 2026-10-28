"""Registro uniforme de fallos en ejecuciones de fondo.

Cada fallo deja la traza completa en el log del servidor y, en los eventos que ve el usuario, un
detalle legible y sin secretos. Antes solo se guardaba el tipo de excepción, lo que hacía imposible
diagnosticar errores como un carácter rechazado por la base de datos.
"""

import logging
import re

logger = logging.getLogger("trama")

_SECRET = re.compile(
    r"(?i)\b(api[-_]?key|token|password|passwd|secret|authorization|bearer)\b(\s*[:=]?\s*)(?:bearer\s+)?\S+"
)


def safe_text(text, size=400):
    return _SECRET.sub(r"\1\2***", str(text))[:size]


def failure_detail(exc, run_id, phase):
    """Registra la traza y devuelve los datos seguros del fallo para el evento."""
    logger.error("Fallo en %s (ejecución %s)", phase, run_id, exc_info=exc)
    detail = {"tipo_error": type(exc).__name__, "detalle": safe_text(exc)}
    status = getattr(exc, "status", None)
    if status:
        detail["estado_http"] = status
    return detail
