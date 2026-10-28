import pytest

from app.agents.functional_analyst import (
    explicitly_requests_definition,
    explicitly_requests_documents,
)


@pytest.mark.parametrize(
    "message",
    [
        "Según los documentos de TechRetail, ¿cómo restablezco mi contraseña corporativa?",
        "Consulta la documentación sobre VPN",
        "Busca en los PDF la política de vacaciones",
    ],
)
def test_explicit_document_request_requires_current_search(message):
    assert explicitly_requests_documents(message)


@pytest.mark.parametrize(
    "message",
    [
        "Hola",
        "¿Qué requisitos tenemos definidos?",
        "Modifica RF-001 para incluir el correo",
    ],
)
def test_state_queries_and_greetings_do_not_force_search(message):
    assert not explicitly_requests_documents(message)


def test_defining_functionality_can_search_and_propose_together():
    message = (
        "Quiero definir una funcionalidad para que un empleado restablezca su contraseña "
        "corporativa. Ayúdame a identificar el actor, los requisitos y las reglas usando "
        "los documentos disponibles. Pregúntame lo que falte."
    )
    assert explicitly_requests_definition(message)
    assert explicitly_requests_documents(message)


@pytest.mark.parametrize(
    "message",
    [
        "¿Qué requisitos tenemos definidos?",
        "Según los documentos, ¿cómo restablezco mi contraseña?",
        "Explícame cómo crear requisitos",
        "No quiero crear requisitos, solo consultar los documentos",
    ],
)
def test_informational_queries_do_not_force_proposals(message):
    assert not explicitly_requests_definition(message)
