"""Criterios compartidos entre fases: actores privilegiados y filtrado de confirmaciones."""

from backlog_fixtures import context_fixture, organization_fixture, stories_fixture

from app.models.backlog import SemanticReview
from app.services.backlog_logic import prepare_generated, validate_backlog
from app.services.roles import drop_confirmations, is_confirmation, subject_is_privileged


def test_subject_is_read_from_the_start_of_the_title():
    assert subject_is_privileged("Líder de área aprueba solicitud")
    assert not subject_is_privileged("Empleado envía solicitud para que su líder la apruebe")


def test_confirmations_are_dropped_but_real_warnings_are_kept():
    findings = [
        {
            "severidad": "advertencia",
            "descripcion": "El backend valida correctamente las reglas de edad.",
        },
        {
            "severidad": "advertencia",
            "descripcion": "Falta validar el nivel de estudios en el servidor.",
        },
        {
            "severidad": "advertencia",
            "descripcion": "Cumple el criterio, pero no registra quién decide.",
        },
        {"severidad": "error", "descripcion": "Coincide el formulario con la tabla."},
    ]
    kept = drop_confirmations(findings)
    assert [f["descripcion"][:12] for f in kept] == ["Falta valida", "Cumple el cr", "Coincide el "]
    assert is_confirmation(findings[0]) and not is_confirmation(findings[3])


def test_story_with_leader_subject_and_employee_actor_is_blocked():
    context = context_fixture()
    stories = stories_fixture().model_dump()
    stories["historias"][0]["titulo"] = "Líder de área aprueba la solicitud"
    candidate, _ = prepare_generated(context, organization_fixture(), stories, "run")
    result = validate_backlog(candidate, context["baseline"], SemanticReview())
    codes = {f.codigo for f in result.validacion.observaciones}
    assert "ACTOR_INCOHERENTE" in codes and not result.validacion.puede_publicar
