"""Comprueba citas sin confundir fallos técnicos con contradicciones de negocio."""

import json
import unicodedata

from app.models.schemas import ProcedureReview, normalized

TECHNICAL_PENDING = "requiere_revision"


def citation_matches(citation, content):
    """Literal tras normalizar; tolera variaciones menores (tildes, conectores) en citas largas."""

    def plain(value):
        decomposed = unicodedata.normalize("NFKD", normalized(value))
        return "".join(c for c in decomposed if not unicodedata.combining(c))

    quote, text = plain(citation), plain(content)
    if quote and quote in text:
        return True
    words = quote.split()
    if len(words) < 8:
        return False
    available = set(text.split())
    return sum(word in available for word in words) / len(words) >= 0.9


def procedure_guard(review, evidence, has_changes):
    if not has_changes:
        return [], [], {"estado": "no_aplica", "motivo": "No hay cambios funcionales"}
    if not evidence and review is None:
        return (
            [],
            [],
            {
                "estado": "sin_evidencia",
                "motivo": "No se proporcionó evidencia documental; no se certifica cumplimiento",
            },
        )
    by_id = {str(item["id_fragmento"]): item for item in evidence}
    if review is None:
        message = "Debe verificarse la compatibilidad con los procedimientos recuperados antes de consolidar estos cambios."
        return [], [], {"estado": "requiere_revision", "motivo": message}
    value = review.model_dump(mode="json")
    if review.estado == "decision_analista":
        # Parámetros no críticos: no requieren documento, quedan marcados como decisión humana.
        value["fuentes_verificadas"] = []
        return [], [], value
    verified, discarded = [], []
    for citation in review.fuentes:
        item = by_id.get(citation.id_fragmento)
        if not item or not citation_matches(citation.cita, item["contenido"]):
            # Una cita mal transcrita se descarta; las demás siguen respaldando la revisión.
            discarded.append(citation.id_fragmento)
            continue
        verified.append(
            {
                "id_fragmento": citation.id_fragmento,
                "id_documento": item["id_documento"],
                "documento": item["documento"],
                "pagina": item["pagina"],
                "version_documento": item["version_documento"],
                "cita": citation.cita,
            }
        )
    value["fuentes_verificadas"] = verified
    value["citas_descartadas"] = discarded
    if review.estado in {"compatible", "contradice"} and not verified:
        message = (
            "La revisión de procedimientos contiene una cita que no pudo verificarse. No se consolidaron los cambios."
            if discarded
            else "Falta evidencia verificable para concluir la compatibilidad con un procedimiento."
        )
        return [], [], {**value, "estado": TECHNICAL_PENDING, "motivo": message}
    if review.estado in {"contradice", "requiere_aclaracion"}:
        refs = "; ".join(
            f"{f['documento']}, p. {f['pagina']}, v{f['version_documento']}" for f in verified
        )
        message = (
            "Compatibilidad con procedimientos pendiente: "
            + review.motivo
            + (" Fuentes: " + refs if refs else "")
        )
        return [message], [review.motivo], value
    if review.estado == "sin_evidencia" and evidence:
        message = "No se pudo establecer si los procedimientos recuperados aplican al cambio. Aclare el alcance antes de consolidarlo."
        return [message], [review.motivo], value
    return [], [], value


async def review_with_citation_repair(models, events, run_id, message, changes, evidence, review):
    result = procedure_guard(review, evidence, bool(changes))
    if result[2]["estado"] != "requiere_revision":
        return result
    await events.emit(
        run_id,
        "validacion",
        "corregir_cita_procedimiento",
        "ejecutando",
        "Revisión técnica de una cita; no es una contradicción del proyecto",
        {
            "revision_original": review.model_dump(mode="json") if review else None,
            "evidencia_ids": [e["id_fragmento"] for e in evidence],
            "motivo": result[2]["motivo"],
            "limite_intentos": 1,
        },
    )
    try:
        fixed = await models.json(
            [
                {
                    "role": "system",
                    "content": "Revisa únicamente la compatibilidad de los cambios con los procedimientos aportados. No modifiques los cambios. Una cita anterior no se pudo verificar: cita SOLO texto literal continuo de un fragmento e indica su id_fragmento exacto. No uses id_documento como id_fragmento. No mezcles frases de páginas distintas en una cita. No declares contradicción por un error técnico. No asumas que la aprobación de requisitos autoriza cambiar políticas. Usa decision_analista, sin fuentes, cuando el cambio solo fija parámetros no críticos definidos por el usuario (listas de valores, textos de mensajes, canales de notificación, formatos) sin alterar roles, aprobaciones ni reglas de los documentos. Si solo se aclaran datos o se cierran preguntas sin modificar roles ni aprobaciones, distingue ese alcance. no_aplica solo si no se cambia un procedimiento operativo, con motivo explícito. No inventes políticas ni evidencias.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"mensaje": message, "cambios": changes, "evidencia": evidence},
                        ensure_ascii=False,
                        default=str,
                    ),
                },
            ],
            ProcedureReview,
            max_tokens=1536,
            max_attempts=1,
        )
        await events.emit(
            run_id,
            "validacion",
            "respuesta_revision_cita",
            "completado",
            "Respuesta de la revisión técnica conservada",
            {"revision": fixed.model_dump(mode="json")},
        )
        result = procedure_guard(fixed, evidence, bool(changes))
    except Exception as exc:
        await events.emit(
            run_id,
            "validacion",
            "corregir_cita_procedimiento",
            "error",
            "No se completó la verificación técnica; no se creó una contradicción",
            {"tipo_error": type(exc).__name__},
        )
    return result
