from app.services.workflow_policy import automatic_approval_allowed


def test_manual_projects_never_auto_approve():
    assert not automatic_approval_allowed("supervisado", True)


def test_automatic_approval_requires_valid_complete_result():
    assert automatic_approval_allowed("automatico", True)
    assert not automatic_approval_allowed("automatico", False)
    assert not automatic_approval_allowed("automatico", True, complete=False)


def test_construction_requires_real_runtime_verification():
    assert automatic_approval_allowed("automatico", True, runtime_verified=True)
    assert not automatic_approval_allowed("automatico", True, runtime_verified=False)


def test_pending_observations_cannot_be_auto_approved_even_with_passing_tests():
    assert not automatic_approval_allowed("automatico", True, runtime_verified=True,
                                          observations=[{"severidad": "advertencia", "descripcion": "Revisar almacenamiento de datos"}])
