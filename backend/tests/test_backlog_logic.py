from copy import deepcopy

import pytest
from backlog_fixtures import content_fixture, context_fixture, organization_fixture, stories_fixture

from app.models.backlog import SemanticReview
from app.services.backlog_logic import (
    all_items,
    criteria,
    prepare_existing,
    prepare_generated,
    validate_backlog,
)


def test_generation_has_stable_ids_source_versions_and_coverage():
    content, counters = content_fixture()
    assert [item["id"] for item in all_items(content)] == ["EP-001", "FE-001", "HU-001"]
    assert counters == {"EP": 1, "FE": 1, "HU": 1}
    assert content["historias"][0]["actor"] == {"id": "ACT-001", "version": 1}
    assert content["historias"][0]["criterios_aceptacion"][0]["id"] == "HU-001-CA-01"
    assert all(
        i["requisitos_origen"] == [{"id": "RF-001", "version": 1}] for i in all_items(content)
    )
    assert content["validacion"]["puede_publicar"]
    assert content["version_esquema"] == "2.0"


def test_regeneration_keeps_identity_and_increments_only_changed_artifacts():
    before, counters = content_fixture()
    context = context_fixture()
    context.update(previous=before, known={i["id"]: i for i in all_items(before)}, head=1)
    context["project"]["counters"] = counters
    stories = stories_fixture().model_dump()
    stories["historias"][0].update(
        id_existente="HU-001", quiero="registrar mi solicitud de soporte con su descripción"
    )
    candidate, later_counters = prepare_generated(
        context, organization_fixture(), stories, "otra-ejecucion"
    )
    assert candidate["version_backlog"] == 2
    assert candidate["epicas"][0]["version"] == 1
    assert candidate["features"][0]["version"] == 1
    assert candidate["historias"][0]["id"] == "HU-001"
    assert candidate["historias"][0]["version"] == 2
    assert later_counters == counters
    assert before["historias"][0]["version"] == 1


def test_missing_coverage_and_pending_questions_block_publication():
    context = context_fixture()
    stories = stories_fixture().model_dump()
    stories["historias"] = []
    stories["preguntas_pendientes"] = ["Falta aclarar quién registra las solicitudes"]
    candidate, _ = prepare_generated(context, organization_fixture(), stories, "run")
    result = validate_backlog(candidate, context["baseline"], SemanticReview())
    assert result.validacion.requisitos_sin_cobertura == ["RF-001"]
    assert not result.validacion.puede_publicar


def test_unknown_actor_foreign_requirement_and_invented_identity_are_rejected():
    context = context_fixture()
    stories = stories_fixture().model_dump()
    stories["historias"][0]["id_actor"] = "ACT-999"
    with pytest.raises(ValueError, match="actor"):
        prepare_generated(context, organization_fixture(), stories, "run")
    organization = organization_fixture().model_dump()
    organization["features"][0]["ids_requisitos"] = ["RF-999"]
    with pytest.raises(ValueError, match="Referencias"):
        prepare_generated(context, organization, stories_fixture(), "run")
    organization = organization_fixture().model_dump()
    organization["epicas"][0]["id_existente"] = "EP-999"
    with pytest.raises(ValueError, match="identificador"):
        prepare_generated(context, organization, stories_fixture(), "run")


def test_criteria_ids_survive_reordering_and_removal():
    first = [
        {"dado": "empleado A", "cuando": "registra solicitud A", "entonces": "se conserva A"},
        {"dado": "empleado B", "cuando": "registra solicitud B", "entonces": "se conserva B"},
    ]
    old = criteria(first, "HU-001")
    reordered = criteria(list(reversed(first)), "HU-001", old)
    assert [item["id"] for item in reordered] == ["HU-001-CA-02", "HU-001-CA-01"]
    assert criteria([first[1]], "HU-001", old)[0]["id"] == "HU-001-CA-02"
    remaining = criteria([first[0]], "HU-001", old)
    later = criteria(
        [
            first[0],
            {"dado": "empleado C", "cuando": "registra solicitud C", "entonces": "se conserva C"},
        ],
        "HU-001",
        remaining,
        old,
    )
    assert later[1]["id"] == "HU-001-CA-03"


def test_human_edit_preserves_snapshot_and_requires_new_validation():
    content, counters = content_fixture()
    context = context_fixture()
    context.update(
        previous=deepcopy(content), known={i["id"]: i for i in all_items(content)}, head=1
    )
    context["project"]["counters"] = counters
    edit = {
        "id_elemento": "FE-001",
        "titulo": "Recepción de solicitudes",
        "descripcion": "Registrar solicitudes con descripción",
        "ids_requisitos": ["RF-001"],
        "id_padre": "EP-001",
        "nota": "Aclarar el nombre de la capacidad",
    }
    candidate, _ = prepare_existing(context, "edicion", edit)
    assert candidate["features"][0]["version"] == 2
    assert candidate["features"][0]["id"] == "FE-001"
    assert "validacion" not in candidate
    assert content["features"][0]["titulo"] == "Registro de solicitudes"


def test_semantic_error_blocks_even_when_structural_rules_pass():
    context = context_fixture()
    candidate, _ = prepare_generated(context, organization_fixture(), stories_fixture(), "run")
    semantic = SemanticReview.model_validate(
        {
            "observaciones": [
                {
                    "severidad": "error",
                    "codigo": "CRITERIO_AMBIGUO",
                    "descripcion": "La condición debe ser verificable",
                    "ids_elementos": ["HU-001"],
                }
            ]
        }
    )
    content = validate_backlog(candidate, context["baseline"], semantic)
    assert content.validacion.estructural
    assert not content.validacion.puede_publicar


def test_constraints_and_rules_are_valid_versioned_sources():
    from copy import deepcopy

    from backlog_fixtures import context_fixture, organization_fixture, stories_fixture

    from app.models.backlog import SemanticReview
    from app.services.backlog_logic import prepare_generated, references, validate_backlog

    context = context_fixture()
    template = context["baseline"]["requisitos"][0]
    for group, ident, kind in [
        ("restricciones", "RES-001", "restriccion"),
        ("reglas_negocio", "RN-001", "regla_negocio"),
    ]:
        item = deepcopy(template)
        item.update(id=ident, tipo=kind, version=2)
        context["baseline"][group] = [item]
    organization = organization_fixture().model_dump()
    stories = stories_fixture().model_dump()
    for item in [*organization["epicas"], *organization["features"], *stories["historias"]]:
        item["ids_requisitos"] += ["RES-001", "RN-001", "RES-001"]
    stories["preguntas_pendientes"] = ["PRE-001"]
    context["baseline"]["preguntas_pendientes"] = [
        {"id": "PRE-001", "descripcion": "¿Cómo se verifica el nivel de estudios?", "version": 1}
    ]
    candidate, _ = prepare_generated(context, organization, stories, "prueba-fuentes")
    refs = candidate["historias"][0]["requisitos_origen"]
    assert {"id": "RES-001", "version": 2} in refs
    assert len(refs) == 3
    assert candidate["preguntas_pendientes"] == ["¿Cómo se verifica el nivel de estudios?"]
    result = validate_backlog(candidate, context["baseline"], SemanticReview())
    assert not any(f.codigo == "ORIGEN_INVALIDO" for f in result.validacion.observaciones)
    assert result.validacion.requisitos_sin_cobertura == []
    import pytest

    with pytest.raises(ValueError):
        references(["PRE-001"], context["baseline"])
    with pytest.raises(ValueError):
        references(["RES-999"], context["baseline"])


def test_resolved_questions_are_not_reopened():
    from app.services.backlog_logic import already_resolved

    resolved = [
        {
            "id": "PRE-005",
            "textos": [
                "¿Cómo debe verificarse la edad del empleado para validar que sea mayor a 23 años antes de permitir la creación del usuario? Se propone usar la fecha de nacimiento para esta verificación."
            ],
        }
    ]
    repeated = "¿Cómo debe verificarse la edad del empleado para validar que sea mayor a 23 años antes de permitir la creación del usuario?"
    assert already_resolved(repeated, resolved)
    assert already_resolved("Falta cerrar PRE-005", resolved)
    assert not already_resolved(
        "¿Qué actor aprueba la desactivación de la cuenta corporativa?", resolved
    )
