"""Fase 5 sin llamadas al modelo: reglas de separación y seguridad, grafo con corrección dirigida,
composición de la instancia local y escritura del producto."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.construction_team import ConstructionTeam
from app.models.construction import (
    AppBundle,
    ArtifactReview,
    BackendBundle,
    DataBundle,
    IacBundle,
    QaBundle,
)
from app.services.construction_rules import aplicaciones, assess, errors_of
from app.services.construction_service import ConstructionService, build_context
from app.services.instance import InstanceDeployer
from app.services.runtime_check import attribute
from app.services.scaffold import compose_file, scaffold_files


def run(coro):
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
    with asyncio.Runner(loop_factory=factory) as runner:
        return runner.run(coro)

MAIN_OK = """import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException

app = FastAPI()


def require_admin(authorization: str = Header(default="")):
    expected = os.environ.get("ADMIN_API_TOKEN", "")
    if not expected or not hmac.compare_digest(authorization, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="No autorizado")


@app.get("/api/health")
def health():
    return {"estado": "ok", "base": os.environ["DATABASE_URL"][:0]}


@app.post("/api/solicitudes", status_code=201)
def crear(cuerpo: dict):
    return {"id": 1, "estado": "pendiente"}


@app.get("/api/admin/solicitudes", dependencies=[Depends(require_admin)])
def listar():
    return []


@app.post("/api/admin/solicitudes/{solicitud_id}/decision", dependencies=[Depends(require_admin)])
def decidir(solicitud_id: int, cuerpo: dict):
    return {"id": solicitud_id}
"""
MAIN_UNPROTECTED = MAIN_OK.replace(
    ", dependencies=[Depends(require_admin)])\ndef listar", ")\ndef listar"
)
assert MAIN_UNPROTECTED != MAIN_OK
MAIN_PUBLIC_LIST = MAIN_OK + '\n\n@app.get("/api/solicitudes")\ndef todas():\n    return []\n'
PORTAL_APP = (
    "import { Component } from '@angular/core';\n"
    "import { RouterOutlet, Routes } from '@angular/router';\n\n"
    "@Component({ selector: 'app-root', standalone: true, imports: [RouterOutlet], template: '<router-outlet/>' })\n"
    "export class App {}\n\nexport const routes: Routes = [];\n"
)
PORTAL_SOLICITUD = (
    "import { Component, signal } from '@angular/core';\n\n"
    "@Component({ selector: 'app-solicitud', standalone: true, template: `\n"
    '  <label class="field">Cédula<input name="cedula"></label>\n'
    '  <label class="field">Nombres completos<input name="nombres"></label>\n'
    '  <label class="field">Correo electrónico<input name="correo"></label>\n`})\n'
    "export class SolicitudComponent {\n"
    "  confirmacion = signal('');\n"
    "  async enviar() {\n"
    "    const res = await fetch('/api/solicitudes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });\n"
    "    this.confirmacion.set(String((await res.json()).id));\n  }\n}\n"
)
PANEL_APP = (
    "import { Component, signal } from '@angular/core';\n"
    "import { RouterOutlet, Routes } from '@angular/router';\n\n"
    "@Component({ selector: 'app-root', standalone: true, imports: [RouterOutlet], template: '<router-outlet/>' })\n"
    "export class App {}\n\nexport const routes: Routes = [];\n\n"
    "@Component({ selector: 'app-aprobacion', standalone: true, template: `\n"
    "  <h2>Datos del solicitante</h2>\n  <button>Aprobar solicitud</button>\n"
    '  <label class="field">Motivo de rechazo<textarea></textarea></label>\n`})\n'
    "export class AprobacionComponent {\n"
    "  token = signal(sessionStorage.getItem('admin_token') ?? '');\n"
    "  async listar() {\n"
    "    return fetch('/api/admin/solicitudes', { headers: { Authorization: `Bearer ${this.token()}` } });\n  }\n}\n"
)
TESTS_OK = (
    "# Criterios: HU-007-CA-01 y HU-008-CA-01\n"
    "from fastapi.testclient import TestClient\n"
    "from app.main import app\n\n"
    "client = TestClient(app)\n\n\n"
    "def test_hu_007_ca_01_crea_solicitud():\n"
    '    assert client.post("/api/solicitudes", json={}).status_code == 201\n\n\n'
    "def test_hu_008_ca_01_admin_sin_token_responde_401():\n"
    '    assert client.get("/api/admin/solicitudes").status_code == 401\n'
)
CONTEXT = {
    "has_panel": True,
    "criteria": ["HU-007-CA-01", "HU-008-CA-01"],
    "screens": [
        {
            "id": "PA-001",
            "titulo": "Solicitud",
            "app": "portal",
            "labels": ["Cédula", "Nombres completos", "Correo electrónico"],
        },
        {
            "id": "PA-002",
            "titulo": "Aprobación",
            "app": "panel",
            "labels": ["Datos del solicitante", "Aprobar solicitud", "Motivo de rechazo"],
        },
    ],
}


def valid_product(**overrides):
    files = scaffold_files("Producto de prueba", True)
    files.update(
        {
            "db/init.sql": "CREATE TABLE solicitudes (id serial PRIMARY KEY, cedula text NOT NULL, edad int CHECK (edad > 23));\n",
            "backend/app/main.py": MAIN_OK,
            "backend/tests/test_solicitudes.py": TESTS_OK,
            "portal/src/app/app.ts": PORTAL_APP,
            "portal/src/app/solicitud.component.ts": PORTAL_SOLICITUD,
            "panel/src/app/app.ts": PANEL_APP,
            "infra/terraform/main.tf": 'provider "aws" {\n  region = var.region\n}\nmodule "eks" {\n  source = "terraform-aws-modules/eks/aws"\n}\n',
        }
    )
    files.update(overrides)
    return files


def codes(findings):
    return {(f["agente"], f["codigo"]) for f in errors_of(findings)}


def test_valid_product_passes_all_rules():
    findings = assess(valid_product(), CONTEXT)
    assert not errors_of(findings), findings


def test_admin_route_without_authentication_is_blocked():
    found = codes(assess(valid_product(**{"backend/app/main.py": MAIN_UNPROTECTED}), CONTEXT))
    assert ("desarrollador_backend", "ADMIN_SIN_PROTECCION") in found


def test_public_listing_duplicating_admin_data_is_blocked():
    found = codes(assess(valid_product(**{"backend/app/main.py": MAIN_PUBLIC_LIST}), CONTEXT))
    assert ("desarrollador_backend", "LISTADO_PUBLICO_DUPLICADO") in found


def test_employee_app_cannot_call_admin_api_or_hold_tokens():
    leaked = (
        PORTAL_SOLICITUD
        + "\nfetch('/api/admin/solicitudes', { headers: { Authorization: 'Bearer x' } });\n"
    )
    found = codes(
        assess(valid_product(**{"portal/src/app/solicitud.component.ts": leaked}), CONTEXT)
    )
    assert ("desarrollador_portal", "ADMIN_EN_EMPLEADO") in found


def test_approval_screen_inside_employee_app_is_blocked():
    leaked = (
        PORTAL_SOLICITUD
        + "\n<h2>Datos del solicitante</h2><button>Aprobar solicitud</button><label>Motivo de rechazo</label>\n"
    )
    found = codes(
        assess(valid_product(**{"portal/src/app/solicitud.component.ts": leaked}), CONTEXT)
    )
    assert ("desarrollador_portal", "PANTALLA_ADMIN_EN_EMPLEADO") in found


def test_interface_calling_missing_endpoint_is_blocked():
    broken = PORTAL_SOLICITUD + "\nfetch('/api/inexistente');\n"
    found = codes(
        assess(valid_product(**{"portal/src/app/solicitud.component.ts": broken}), CONTEXT)
    )
    assert ("desarrollador_portal", "ENDPOINT_INEXISTENTE") in found


def test_missing_mockup_fields_are_blocked():
    incomplete = "import { Component } from '@angular/core';\n@Component({ selector: 'app-solicitud', standalone: true, template: '<p>Hola</p>' })\nexport class SolicitudComponent {}\n"
    found = codes(
        assess(valid_product(**{"portal/src/app/solicitud.component.ts": incomplete}), CONTEXT)
    )
    assert ("desarrollador_portal", "PANTALLA_INCOMPLETA") in found


def test_missing_access_denied_test_is_blocked():
    tests = TESTS_OK.replace("401", "200")
    found = codes(assess(valid_product(**{"backend/tests/test_solicitudes.py": tests}), CONTEXT))
    assert ("agente_pruebas", "SIN_PRUEBA_ACCESO_DENEGADO") in found


def test_secret_literal_is_blocked():
    leaked = MAIN_OK + '\nPASSWORD = "contraseña-real-123"\n'
    found = codes(assess(valid_product(**{"backend/app/main.py": leaked}), CONTEXT))
    assert any(code == "SECRETO_EN_CODIGO" for _, code in found)


def test_applications_are_assigned_by_actor_and_story():
    actors = [
        {"id": "ACT-001", "nombre": "Empleado", "descripcion": "Empleado que crea solicitudes"},
        {"id": "ACT-002", "nombre": "Líder de área", "descripcion": "Aprueba solicitudes"},
    ]
    stories = [
        {"id": "HU-007", "actor": {"id": "ACT-001"}},
        {"id": "HU-008", "actor": {"id": "ACT-002"}},
    ]
    screens = [
        {
            "id": "PA-001",
            "titulo": "Solicitud",
            "descripcion": "Muestra el líder asignado",
            "ids_historias": ["HU-007"],
            "controles": [],
        },
        {
            "id": "PA-002",
            "titulo": "Aprobación",
            "descripcion": "",
            "ids_historias": ["HU-008"],
            "controles": [],
        },
    ]
    screen_apps, story_sides, has_panel = aplicaciones(screens, stories, actors)
    assert screen_apps == {"PA-001": "portal", "PA-002": "panel"}
    assert story_sides == {"HU-007": "portal", "HU-008": "panel"} and has_panel


def test_build_context_gives_each_app_only_its_screens():
    architecture = {
        "actores": [
            {"id": "ACT-001", "nombre": "Empleado", "descripcion": ""},
            {"id": "ACT-002", "nombre": "Líder", "descripcion": ""},
        ],
        "software": {"componentes": [], "atributos_calidad": []},
        "infraestructura": {"nodos": []},
    }
    backlog = {
        "historias": [
            {
                "id": "HU-007",
                "titulo": "t",
                "quiero": "q",
                "actor": {"id": "ACT-001"},
                "criterios_aceptacion": [],
                "requisitos_origen": [],
            },
            {
                "id": "HU-008",
                "titulo": "t",
                "quiero": "q",
                "actor": {"id": "ACT-002"},
                "criterios_aceptacion": [],
                "requisitos_origen": [],
            },
        ]
    }
    mockups = {
        "diseno": {
            "pantallas": [
                {
                    "id": "PA-001",
                    "titulo": "Solicitud",
                    "descripcion": "",
                    "ids_historias": ["HU-007"],
                    "controles": [],
                },
                {
                    "id": "PA-002",
                    "titulo": "Aprobación",
                    "descripcion": "",
                    "ids_historias": ["HU-008"],
                    "controles": [],
                },
            ]
        }
    }
    context = build_context("P", architecture, backlog, {}, mockups)
    assert context["tiene_panel"] is True
    assert {s["id"]: s["aplicacion"] for s in context["pantallas"]} == {
        "PA-001": "portal",
        "PA-002": "panel",
    }


def test_runtime_errors_are_attributed_to_the_responsible_agent():
    assert attribute("failed to build portal/Dockerfile", True) == ["desarrollador_portal"]
    assert attribute("backend unhealthy", True) == ["desarrollador_backend"]
    assert "agente_pruebas" in attribute("pytest: test_hu_007_ca_01 assert 200 == 422", True)


def test_instance_compose_uses_relative_contexts_and_publishes_only_the_edge():
    text = compose_file("ec2-demo", True, "../../../workspace/demo/aplicacion/v1", publish=True)
    data = yaml.safe_load(text)
    assert data["services"]["backend"]["build"] == "../../../workspace/demo/aplicacion/v1/backend"
    assert "127.0.0.1:${PANEL_PORT:-8101}:8081" in data["services"]["edge"]["ports"]
    assert set(data["services"]["edge"]["depends_on"]) == {"backend", "portal", "panel"}
    assert (
        "ports"
        not in yaml.safe_load(compose_file("x", True, ".", publish=False))["services"]["backend"]
    )
    assert (
        "ports"
        not in yaml.safe_load(compose_file("x", True, ".", publish=False))["services"]["edge"]
    )


def test_instance_folder_is_named_after_project_and_version(tmp_path):
    deployer = InstanceDeployer(None, tmp_path)
    assert (
        deployer.folder("demo-v2") == tmp_path / "infraestructura-local" / "instancias" / "demo-v2"
    )


def test_candidate_is_written_with_readme_and_all_files(tmp_path):
    service = ConstructionService(None, None, SimpleNamespace(workspace_dir=tmp_path))
    summary = {
        "proyecto": "Demo",
        "tiene_panel": True,
        "endpoints": [{"metodo": "GET", "ruta": "/api/health", "acceso": "publico"}],
    }
    target = Path(service.write_candidate("Demo", 1, valid_product(), summary))
    for name in (
        "docker-compose.yml",
        "backend/app/main.py",
        "portal/Dockerfile",
        "panel/Dockerfile",
        "edge/nginx.conf",
        "README.md",
    ):
        assert (target / name).exists(), name
    assert "ADMIN_API_TOKEN" in (target / ".env.example").read_text(encoding="utf-8")


class FakeEvents:
    async def emit(self, *args, **kwargs):
        pass

    async def status(self, *args, **kwargs):
        pass


class FakeModels:
    settings = SimpleNamespace(
        llm_model="simulado", llm_provider="sin-red", construction_max_tokens=12000
    )

    def __init__(self, bad_backend_first=False):
        self.calls = []
        self.bad = bad_backend_first
        self.backend_calls = 0

    async def json(self, messages, schema, usage=None, **kwargs):
        self.calls.append(schema.__name__)
        usage["entrada"], usage["salida"] = 100, 50
        instruction = messages[0]["content"]
        if schema is DataBundle:
            return DataBundle.model_validate(
                {
                    "archivos": [
                        {"ruta": "db/init.sql", "contenido": valid_product()["db/init.sql"]}
                    ],
                    "tablas": [{"nombre": "solicitudes", "columnas": ["id", "cedula"]}],
                }
            )
        if schema is BackendBundle:
            self.backend_calls += 1
            main = MAIN_UNPROTECTED if (self.bad and self.backend_calls == 1) else MAIN_OK
            return BackendBundle.model_validate(
                {
                    "archivos": [{"ruta": "backend/app/main.py", "contenido": main}],
                    "endpoints": [
                        {
                            "metodo": "GET",
                            "ruta": "/api/health",
                            "acceso": "publico",
                            "descripcion": "Salud",
                        },
                        {
                            "metodo": "POST",
                            "ruta": "/api/solicitudes",
                            "acceso": "publico",
                            "descripcion": "Crear",
                        },
                        {
                            "metodo": "GET",
                            "ruta": "/api/admin/solicitudes",
                            "acceso": "administrador",
                            "descripcion": "Listar",
                        },
                    ],
                }
            )
        if schema is AppBundle:
            if "panel administrativo" in instruction:
                return AppBundle.model_validate(
                    {
                        "archivos": [
                            {
                                "ruta": "panel/src/app/aprobacion.component.ts",
                                "contenido": PANEL_APP,
                            }
                        ],
                        "pantallas": ["PA-002"],
                    }
                )
            return AppBundle.model_validate(
                {
                    "archivos": [
                        {"ruta": "portal/src/app/app.ts", "contenido": PORTAL_APP},
                        {
                            "ruta": "portal/src/app/solicitud.component.ts",
                            "contenido": PORTAL_SOLICITUD,
                        },
                    ],
                    "pantallas": ["PA-001"],
                }
            )
        if schema is QaBundle:
            return QaBundle.model_validate(
                {
                    "archivos": [
                        {"ruta": "backend/tests/test_solicitudes.py", "contenido": TESTS_OK}
                    ],
                    "casos": [
                        {
                            "id": "PR-001",
                            "criterio": "HU-007-CA-01",
                            "archivo": "backend/tests/test_solicitudes.py",
                            "descripcion": "Crea solicitud",
                        },
                        {
                            "id": "PR-002",
                            "criterio": "HU-008-CA-01",
                            "archivo": "backend/tests/test_solicitudes.py",
                            "descripcion": "Admin sin token",
                        },
                    ],
                }
            )
        if schema is IacBundle:
            return IacBundle.model_validate(
                {
                    "archivos": [
                        {
                            "ruta": "infra/terraform/main.tf",
                            "contenido": valid_product()["infra/terraform/main.tf"],
                        }
                    ]
                }
            )
        return ArtifactReview(observaciones=[])


class FakeService:
    def __init__(self, root):
        self.root = root
        self.writes = []

    def candidate_dir(self, project, version):
        return self.root / f"v{version}"

    def write_candidate(self, project, version, files, summary):
        self.writes.append(version)
        return str(self.candidate_dir(project, version))

    async def persist(self, state):
        return {
            "puede_publicar": not errors_of(state["report"]["observaciones"]),
            "corrections": state["corrections"],
            "consumo": state["usage"],
            "validacion": state["report"],
        }


async def runtime_ok(app_dir, name, has_panel):
    return {"disponible": True, "errores": [], "resumen": "7 passed"}


def run_team(models, tmp_path, runtime=runtime_ok):
    team = ConstructionTeam(
        FakeService(tmp_path), models, FakeEvents(), InMemorySaver(), runtime=runtime
    )
    datos = {
        "proyecto": "Producto de prueba",
        "tiene_panel": True,
        "aplicaciones": {"portal": "Empleado", "panel": "Aprobadores"},
        "tecnologias": ["Python", "Angular"],
        "actores": [],
        "componentes": [],
        "historias": [
            {
                "id": "HU-007",
                "titulo": "Solicitar",
                "quiero": "q",
                "aplicacion": "portal",
                "criterios": [{"id": "HU-007-CA-01"}],
                "requisitos": [],
            },
            {
                "id": "HU-008",
                "titulo": "Aprobar",
                "quiero": "q",
                "aplicacion": "panel",
                "criterios": [{"id": "HU-008-CA-01"}],
                "requisitos": [],
            },
        ],
        "pantallas": [
            {
                "id": "PA-001",
                "titulo": "Solicitud",
                "aplicacion": "portal",
                "controles": [
                    {"tipo": "entrada", "etiqueta": "Cédula"},
                    {"tipo": "entrada", "etiqueta": "Nombres completos"},
                    {"tipo": "entrada", "etiqueta": "Correo electrónico"},
                ],
            },
            {
                "id": "PA-002",
                "titulo": "Aprobación",
                "aplicacion": "panel",
                "controles": [
                    {"tipo": "texto", "etiqueta": "Datos del solicitante"},
                    {"tipo": "boton", "etiqueta": "Aprobar solicitud"},
                    {"tipo": "entrada", "etiqueta": "Motivo de rechazo"},
                ],
            },
        ],
        "reglas": [],
        "reglas_negocio": [],
        "requisitos": [],
        "nodos_nube": [],
    }
    initial = {
        "project_id": "p",
        "execution_id": "r",
        "request": {"instrucciones": ""},
        "context": {"datos": datos, "version_candidata": 1, "version_arquitectura": 3},
    }
    return run(team.graph.ainvoke(initial, {"configurable": {"thread_id": "t"}}))["content"]


def test_graph_builds_every_layer_in_order_and_publishes_a_valid_product(tmp_path):
    models = FakeModels()
    content = run_team(models, tmp_path)
    assert models.calls[:2] == ["DataBundle", "BackendBundle"]
    assert content["puede_publicar"] and content["corrections"] == 0


def test_rule_error_returns_only_the_responsible_agent_once(tmp_path):
    models = FakeModels(bad_backend_first=True)
    content = run_team(models, tmp_path)
    assert models.backend_calls == 2  # El backend se corrige una vez con el error exacto.
    assert models.calls.count("DataBundle") == 1  # La base de datos no se toca.
    assert content["corrections"] == 1 and content["puede_publicar"]


def test_runtime_failure_is_sent_back_to_the_backend(tmp_path):
    calls = {"n": 0}

    async def flaky(app_dir, name, has_panel):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "disponible": True,
                "errores": [
                    {
                        "agente": "desarrollador_backend",
                        "codigo": "PRUEBAS_FALLIDAS",
                        "descripcion": "assert 200 == 422",
                    }
                ],
                "resumen": "1 failed",
            }
        return {"disponible": True, "errores": [], "resumen": "7 passed"}

    models = FakeModels()
    content = run_team(models, tmp_path, runtime=flaky)
    assert calls["n"] == 2 and content["corrections"] == 1 and content["puede_publicar"]


def test_docker_unavailable_is_a_warning_not_a_blocker(tmp_path):
    async def offline(app_dir, name, has_panel):
        return {"disponible": False, "errores": [], "resumen": "El servicio Docker no está activo"}

    content = run_team(FakeModels(), tmp_path, runtime=offline)
    assert content["puede_publicar"] is True
    assert any(
        f["codigo"] == "DOCKER_NO_DISPONIBLE" for f in content["validacion"]["observaciones"]
    )


def test_null_characters_are_blocked_for_the_responsible_agent():
    found = codes(assess(valid_product(**{"backend/app/main.py": MAIN_OK + "\x00"}), CONTEXT))
    assert ("desarrollador_backend", "CARACTER_NULO") in found


def test_leader_story_with_wrong_backlog_actor_still_goes_to_panel():
    actors = [{"id": "ACT-001", "nombre": "Empleado", "descripcion": ""}]
    stories = [
        {"id": "HU-010", "titulo": "Líder de área aprueba solicitud", "actor": {"id": "ACT-001"}}
    ]
    screens = [
        {
            "id": "PA-002",
            "titulo": "Aprobación",
            "descripcion": "",
            "ids_historias": ["HU-010"],
            "controles": [],
        }
    ]
    screen_apps, story_sides, has_panel = aplicaciones(screens, stories, actors)
    assert story_sides == {"HU-010": "panel"} and screen_apps == {"PA-002": "panel"} and has_panel


def test_template_expressions_in_api_paths_are_understood():
    text = PANEL_APP + "\nfetch(`/api/admin/solicitudes/${this.solicitud(id)}/decision`);\n"
    found = codes(assess(valid_product(**{"panel/src/app/app.ts": text}), CONTEXT))
    assert ("desarrollador_panel", "ENDPOINT_INEXISTENTE") not in found


def test_pydantic_v1_regex_argument_is_blocked():
    code = (
        MAIN_OK
        + '\n\nfrom pydantic import BaseModel, Field\n\n\nclass X(BaseModel):\n    a: str = Field(..., regex="^a$")\n'
    )
    found = codes(assess(valid_product(**{"backend/app/main.py": code}), CONTEXT))
    assert ("desarrollador_backend", "PYDANTIC_V1") in found


def test_docker_failure_is_attributed_to_the_container_that_failed():
    from app.services.runtime_check import attribute

    text = " Container chk-x-portal-1 Created\n Container chk-x-backend-1 Error dependency backend failed\ndependency failed to start: container chk-x-backend-1 exited (1)"
    assert attribute(text, True) == ["desarrollador_backend"]


def test_healthchecks_use_ipv4_loopback_for_alpine_wget():
    data = yaml.safe_load(compose_file("x", True, ".", publish=True))
    for name in ("portal", "panel", "edge"):
        assert "127.0.0.1" in " ".join(data["services"][name]["healthcheck"]["test"]), name


def test_static_analysis_flags_undefined_names_sql_injection_and_eval():
    from app.services.construction_rules import static_findings

    code = (
        MAIN_OK
        + "\n\ndef inseguro(cur, nombre):\n    cur.execute(f\"SELECT * FROM t WHERE n = '{nombre}'\")\n    return eval(nombre) + no_definido\n"
    )
    found = run(static_findings({"backend/app/main.py": code}))
    found_codes = {f["codigo"] for f in found}
    assert {"ESTATICO_S608", "ESTATICO_S307", "ESTATICO_F821"} <= found_codes
    assert all(
        f["agente"] == "desarrollador_backend" and f["archivo"] == "backend/app/main.py"
        for f in found
    )


def test_static_analysis_accepts_clean_code_and_test_credentials():
    from app.services.construction_rules import static_findings

    tests_code = 'PASSWORD = "contraseña-de-prueba"\n'
    found = run(
        static_findings({"backend/app/main.py": MAIN_OK, "backend/tests/test_x.py": tests_code})
    )
    assert found == []
