"""Criterios compartidos entre fases: roles privilegiados y filtrado de hallazgos.

Backlog y construcción deben clasificar a los actores igual; antes cada fase tenía su propio
criterio y un actor mal asignado en el backlog se propagaba hasta la aplicación generada.
"""

import re
import unicodedata

PRIVILEGED = {
    "lider",
    "administrador",
    "admin",
    "aprobador",
    "supervisor",
    "jefe",
    "gestor",
    "director",
    # "Talento Humano" (RR. HH.) aprueba/valida solicitudes como segundo nivel, pero ninguna
    # palabra anterior lo detectaba: la historia caía como actor no privilegiado y su pantalla
    # terminaba asignada al portal del empleado en vez de al panel de aprobadores.
    "talento",
    "rrhh",
}

# Un validador con modelo a veces "reporta" lo que está bien. Eso no es un hallazgo: es ruido que
# oculta los defectos reales. Solo se descartan advertencias afirmativas sin señal de defecto.
_AFFIRMATIVE = re.compile(
    r"(?i)\b(correctamente|adecuadamente|cumple|cumpliendo|coincide|coinciden|conforme a|asegurando|garantizando|est[aá]n? (?:bien|correctamente))\b"
)
_DEFECT = re.compile(
    r"(?i)\b(falta|faltan|no\s|sin\s|debe|deber[ií]a|incumple|error|riesgo|recomienda|incompleto|inconsisten|ausente|omite|mejorar|revisar|verificar)"
)


def norm(text):
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def is_privileged(text):
    return bool(set(norm(text).split()) & PRIVILEGED)


def is_confirmation(finding):
    text = finding.get("descripcion", "")
    return (
        finding.get("severidad") == "advertencia"
        and bool(_AFFIRMATIVE.search(text))
        and not _DEFECT.search(text)
    )


def drop_confirmations(findings):
    return [f for f in findings if not is_confirmation(f)]


def subject_is_privileged(title, words=4):
    """El sujeto de una historia está al inicio del título ("Líder de área aprueba ...").
    Mirar solo esas palabras evita confundir "Empleado envía ... para que su líder apruebe"."""
    return bool(set(norm(title).split()[:words]) & PRIVILEGED)
