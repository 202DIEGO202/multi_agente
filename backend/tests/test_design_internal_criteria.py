from test_mockups import design_fixture

from app.services.mockup_service import assess_design, normalize_design_references


def context():
    return {"historias": [
        {"id": "HU-001", "criterios_aceptacion": [{"id": "HU-001-CA-01"}], "requisitos_origen": [{"id": "RNF-001"}]},
        {"id": "HU-002", "criterios_aceptacion": [{"id": "HU-002-CA-01"}], "requisitos_origen": [{"id": "RF-002"}]},
    ]}


def test_internal_persistence_has_traceability_without_fictitious_screen():
    design = design_fixture()
    design["criterios_no_visuales"] = [{"id_criterio": "HU-002-CA-01", "justificacion": "Persistir el resultado y su fecha en el servidor, sin interacción adicional."}]
    report = assess_design(design, context(), {})
    assert report["puede_publicar"]
    assert report["criterios_no_visuales"] == design["criterios_no_visuales"]


def test_missing_criteria_remain_blocked_and_unknown_exclusions_rejected():
    design = design_fixture()
    assert not assess_design(design, context(), {})["puede_publicar"]
    design["criterios_no_visuales"] = [{"id_criterio": "HU-999-CA-01", "justificacion": "Persistencia en servidor sin interacción adicional."}]
    report = assess_design(design, context(), {})
    assert not report["puede_publicar"]
    assert "HU-002-CA-01" in report["criterios_sin_representacion"]


def test_visual_requirement_is_typed_without_inventing_acceptance_links():
    design = design_fixture()
    design["pantallas"][0]["ids_criterios_visuales"] = ["RNF-001"]
    result = normalize_design_references(design, context())
    assert result["pantallas"][0]["ids_requisitos_visuales"] == ["RNF-001"]
    assert result["pantallas"][0]["ids_criterios_visuales"] == []


def test_semantic_validator_can_reject_abusive_nonvisual_classification():
    design = design_fixture()
    design["criterios_no_visuales"] = [{"id_criterio": "HU-002-CA-01", "justificacion": "Clasificación incorrecta de un resultado que debe ser visible."}]
    report = assess_design(design, context(), {"observaciones": [{"severidad": "error", "descripcion": "El resultado debe mostrarse al usuario", "ids_elementos": ["HU-002-CA-01"]}]})
    assert not report["puede_publicar"]
