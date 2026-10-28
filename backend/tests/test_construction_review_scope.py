import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.construction_team import ConstructionTeam
from app.services.construction_rules import assess
from app.services.construction_service import ConstructionService


def test_review_includes_routed_screens_and_tests_without_truncation():
    async def scenario():
        team = object.__new__(ConstructionTeam)
        batches = []

        async def call(state, role, operation, payload, schema, instruction):
            batches.append(payload)
            return {"observaciones": []}, {}

        team.call = call
        content = "A" * 32000 + "B" * 32000 + "FINAL_SECURITY_RULE"
        state = {"context": {"datos": {"aplicaciones": [], "pantallas": [], "historias": [], "reglas_negocio": []}},
                 "backend": {"endpoints": [], "archivos": [{"ruta": "backend/app/domain.py", "contenido": content}]},
                 "portal": {"archivos": [{"ruta": "portal/src/screens/catalog.ts", "contenido": "real routed screen"}]},
                 "tests": {"casos": [], "archivos": [{"ruta": "tests/test_domain.py", "contenido": "actual assertions"}]}}
        result = await team.review(state)
        assert result["review_ran"]
        files = [f for b in batches for f in b["archivos"]]
        reconstructed = "".join(f["contenido"] for f in files if f["ruta"] == "backend/app/domain.py")
        assert reconstructed == content
        assert any(f["ruta"].endswith("catalog.ts") for f in files)
        assert any(f["ruta"].endswith("test_domain.py") for f in files)
        assert all(sum(len(f["contenido"]) for f in b["archivos"]) <= 40000 for b in batches)
    asyncio.run(scenario())


def test_candidate_replacement_removes_only_tracked_files(tmp_path):
    service = object.__new__(ConstructionService)
    service.settings = SimpleNamespace(workspace_dir=tmp_path)
    summary = {"proyecto": "Demo", "tiene_panel": False, "endpoints": []}
    target = Path(service.write_candidate("Demo", 1, {"backend/old.py": "old"}, summary))
    (target / ".env").write_text("TEST_SECRET=local")
    (target / "user-notes.txt").write_text("Keep")
    service.write_candidate("Demo", 1, {"backend/new.py": "new"}, summary)
    assert not (target / "backend/old.py").exists()
    assert (target / "backend/new.py").read_text() == "new"
    assert (target / ".env").read_text() == "TEST_SECRET=local"
    assert (target / "user-notes.txt").read_text() == "Keep"
    with pytest.raises(ValueError):
        service.write_candidate("Demo", 1, {"../../escape.py": "bad"}, summary)
    with pytest.raises(ValueError):
        service.write_candidate("Demo", 1, {".env": "bad"}, summary)


def test_sql_enum_values_must_fit_declared_column():
    from test_construction import valid_product
    files = valid_product()
    files["db/init.sql"] = "CREATE TABLE result (state VARCHAR(10) NOT NULL CHECK (state IN ('ok', 'requires_manual_review')));"
    context = {"has_panel": False, "screens": [], "criteria": []}
    assert any(f["codigo"] == "SQL_ENUM_TRUNCADO" for f in assess(files, context))
    files["db/init.sql"] = files["db/init.sql"].replace("VARCHAR(10)", "VARCHAR(40)")
    assert not any(f["codigo"] == "SQL_ENUM_TRUNCADO" for f in assess(files, context))


def test_missing_routed_component_is_reported_to_frontend_agent():
    from test_construction import valid_product
    files = valid_product()
    files["portal/src/app/routes.ts"] = "import { Result } from './result';"
    found = assess(files, {"has_panel": False, "screens": [], "criteria": []})
    assert any(f["codigo"] == "IMPORT_LOCAL_AUSENTE" and f["agente"] == "desarrollador_portal" for f in found)


def test_partial_correction_preserves_unmodified_screens():
    from app.agents.construction_team import PORTAL
    async def scenario():
        team = object.__new__(ConstructionTeam)
        team.payload = lambda agent, state: {}
        async def call(*args):
            return {"archivos": [{"ruta": "portal/src/app/result.ts", "contenido": "corrected result"}], "pantallas": ["PA-002"]}, {}
        team.call = call
        state = {"portal": {"archivos": [
            {"ruta": "portal/src/app/form.ts", "contenido": "existing form"},
            {"ruta": "portal/src/app/result.ts", "contenido": "old result"},
            {"ruta": "portal/src/app/routes.ts", "contenido": "existing routes"},
        ]}}
        update, _ = await team.run(state, PORTAL, [{"descripcion": "Fix result"}])
        files = {f["ruta"]: f["contenido"] for f in update["portal"]["archivos"]}
        assert len(files) == 3
        assert files["portal/src/app/form.ts"] == "existing form"
        assert files["portal/src/app/result.ts"] == "corrected result"
        assert files["portal/src/app/routes.ts"] == "existing routes"
    asyncio.run(scenario())


def test_skipped_suite_cannot_verify_runtime(tmp_path, monkeypatch):
    from app.services.runtime_check import run_check
    commands = []
    def command(args, **kwargs):
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, "2 skipped in 0.01s" if "pytest" in args else "", "")
    monkeypatch.setattr(subprocess, "run", command)
    result = asyncio.run(run_check(tmp_path, "skipped-tests", False))
    assert result["disponible"]
    assert result["errores"][0]["codigo"] == "PRUEBAS_NO_EJECUTADAS"
    assert any("down" in args for args in commands)
