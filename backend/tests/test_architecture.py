"""Fase 4 sin llamadas al modelo: reglas, archivos derivados y grafo con agentes simulados."""

import asyncio
import sys
from copy import deepcopy
from types import SimpleNamespace

from langgraph.checkpoint.memory import InMemorySaver

from app.agents.architecture_team import ArchitectureTeam
from app.config import Settings
from app.models.architecture import ArchitectureReview, InfraProposal, Plan, SoftwareProposal
from app.services.architecture_service import assess_architecture, compact_context
from app.services.diagrams import build_views, compose, drawio, files, kubernetes

ALLOWED = Settings().architecture_technologies


def run(coro):
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
    with asyncio.Runner(loop_factory=factory) as runner:
        return runner.run(coro)

CONTEXT = {
    "proyecto": "Creación de usuario",
    "requisitos": [
        {"id": "RF-001", "tipo": "requisito_funcional", "descripcion": "Enviar solicitud"},
        {"id": "RNF-001", "tipo": "requisito_no_funcional", "descripcion": "Responder en 2 s"},
    ],
    "actores": [{"id": "ACT-001", "nombre": "Empleado"}, {"id": "ACT-002", "nombre": "Líder"}],
    "reglas_negocio": [{"id": "RN-001", "descripcion": "Requiere aprobación"}],
    "restricciones": [],
    "decisiones_funcionales": [],
    "historias": [
        {
            "id": "HU-001",
            "titulo": "Solicitar",
            "quiero": "x",
            "criterios": [],
            "requisitos": ["RF-001"],
        },
        {
            "id": "HU-002",
            "titulo": "Rechazar",
            "quiero": "x",
            "criterios": [],
            "requisitos": ["RN-001"],
        },
    ],
    "pantallas": [],
}


def software():
    return SoftwareProposal.model_validate(
        {
            "resumen": "Monolito modular con portal Angular.",
            "estilo": "monolito_modular",
            "atributos_calidad": [
                {
                    "id": "AC-001",
                    "atributo": "rendimiento",
                    "escenario": "Al enviar una solicitud el sistema responde",
                    "medida": "p95 < 2 s",
                    "prioridad": "alta",
                    "ids_requisitos": ["RNF-001"],
                },
                {
                    "id": "AC-002",
                    "atributo": "seguridad",
                    "escenario": "Solo el líder aprueba",
                    "medida": "100 % de aprobaciones con rol líder",
                    "prioridad": "alta",
                    "ids_requisitos": ["RN-001"],
                },
            ],
            "decisiones": [
                {
                    "id": "ADR-001",
                    "titulo": "Monolito modular",
                    "contexto": "Equipo pequeño",
                    "decision": "Una API FastAPI",
                    "alternativas": ["Microservicios"],
                    "ventajas": ["Despliegue simple"],
                    "desventajas": ["Escala como un todo"],
                    "ids_atributos": ["AC-001"],
                }
            ],
            "contenedores": [
                {
                    "id": "CT-001",
                    "nombre": "Portal web",
                    "tipo": "aplicacion_web",
                    "tecnologia": "Angular",
                    "responsabilidad": "UI",
                },
                {
                    "id": "CT-002",
                    "nombre": "API",
                    "tipo": "api",
                    "tecnologia": "Python FastAPI",
                    "responsabilidad": "Reglas",
                },
                {
                    "id": "CT-003",
                    "nombre": "Base de datos",
                    "tipo": "base_datos",
                    "tecnologia": "PostgreSQL",
                    "responsabilidad": "Datos",
                },
                {
                    "id": "CT-004",
                    "nombre": "Active Directory",
                    "tipo": "servicio_externo",
                    "tecnologia": "AD",
                    "responsabilidad": "Cuentas",
                },
            ],
            "componentes": [
                {
                    "id": "CM-001",
                    "contenedor": "CT-001",
                    "nombre": "Módulo solicitud",
                    "tipo": "modulo_ui",
                    "responsabilidad": "Formulario",
                    "ids_historias": ["HU-001"],
                    "operaciones": [],
                },
                {
                    "id": "CM-002",
                    "contenedor": "CT-002",
                    "nombre": "Solicitudes",
                    "tipo": "controlador",
                    "responsabilidad": "CRUD",
                    "ids_historias": ["HU-001", "HU-002"],
                    "operaciones": ["POST /api/solicitudes"],
                },
            ],
            "relaciones": [
                {
                    "origen": "ACT-001",
                    "destino": "CT-001",
                    "descripcion": "Usa",
                    "protocolo": "HTTPS",
                },
                {
                    "origen": "CM-001",
                    "destino": "CM-002",
                    "descripcion": "Envía",
                    "protocolo": "REST",
                },
                {
                    "origen": "CT-002",
                    "destino": "CT-003",
                    "descripcion": "Persiste",
                    "protocolo": "SQL",
                },
                {
                    "origen": "CT-002",
                    "destino": "CT-004",
                    "descripcion": "Notifica",
                    "protocolo": "SMTP",
                },
            ],
            "flujos": [
                {
                    "id": "SQ-001",
                    "titulo": "Aprobar o rechazar",
                    "ids_historias": ["HU-002"],
                    "pasos": [
                        {"de": "ACT-002", "a": "CT-001", "mensaje": "Abre solicitud"},
                        {"de": "CT-001", "a": "CT-002", "mensaje": "POST aprobación"},
                    ],
                    "condicion_alternativa": "¿Aprueba?",
                    "paso_desvio": 1,
                    "alternativa": [
                        {"de": "CT-001", "a": "CT-002", "mensaje": "POST rechazo con motivo"}
                    ],
                }
            ],
            "preguntas": [],
        }
    ).model_dump(mode="json")


def infra():
    node = {
        "aloja": [],
        "puerto": None,
        "replicas": 1,
        "configuracion": [],
        "explicacion": "Nodo de prueba",
    }
    return InfraProposal.model_validate(
        {
            "resumen": "Local con Compose y nube en EKS.",
            "estrategia_despliegue": "Imágenes en ECR y despliegue en EKS.",
            "seguridad": "Secretos en Secrets Manager.",
            "observabilidad": "CloudWatch.",
            "nodos": [
                {
                    **node,
                    "id": "IN-001",
                    "entorno": "local",
                    "tipo": "contenedor",
                    "nombre": "Frontend",
                    "tecnologia": "Docker Nginx",
                    "aloja": ["CT-001"],
                    "puerto": 4200,
                },
                {
                    **node,
                    "id": "IN-002",
                    "entorno": "local",
                    "tipo": "contenedor",
                    "nombre": "Backend",
                    "tecnologia": "Docker",
                    "aloja": ["CT-002"],
                    "puerto": 8000,
                    "configuracion": ["DATABASE_URL (secreto)"],
                },
                {
                    **node,
                    "id": "IN-003",
                    "entorno": "local",
                    "tipo": "base_datos",
                    "nombre": "Postgres",
                    "tecnologia": "PostgreSQL",
                    "aloja": ["CT-003"],
                    "puerto": 5432,
                },
                {
                    **node,
                    "id": "IN-004",
                    "entorno": "nube",
                    "tipo": "balanceador",
                    "nombre": "ALB",
                    "tecnologia": "AWS ALB",
                },
                {
                    **node,
                    "id": "IN-005",
                    "entorno": "nube",
                    "tipo": "contenedor",
                    "nombre": "Frontend",
                    "tecnologia": "AWS EKS",
                    "aloja": ["CT-001"],
                    "puerto": 80,
                    "replicas": 2,
                },
                {
                    **node,
                    "id": "IN-006",
                    "entorno": "nube",
                    "tipo": "contenedor",
                    "nombre": "Backend",
                    "tecnologia": "AWS EKS",
                    "aloja": ["CT-002"],
                    "puerto": 8000,
                    "replicas": 2,
                    "configuracion": ["DATABASE_URL"],
                },
                {
                    **node,
                    "id": "IN-007",
                    "entorno": "nube",
                    "tipo": "base_datos",
                    "nombre": "RDS",
                    "tecnologia": "AWS RDS PostgreSQL",
                    "aloja": ["CT-003"],
                },
            ],
            "conexiones": [
                {
                    "origen": "IN-002",
                    "destino": "IN-003",
                    "descripcion": "SQL",
                    "protocolo": "TCP 5432",
                },
                {
                    "origen": "IN-004",
                    "destino": "IN-005",
                    "descripcion": "HTTP",
                    "protocolo": "HTTP",
                },
            ],
        }
    ).model_dump(mode="json")


def plan():
    return Plan.model_validate(
        {
            "resumen": "Primero datos y backend.",
            "tareas": [
                {
                    "id": "TT-001",
                    "titulo": "API de solicitudes",
                    "rol": "backend",
                    "descripcion": "Endpoints CRUD",
                    "ids_componentes": ["CM-002"],
                    "ids_historias": ["HU-001"],
                    "depende_de": [],
                    "criterios_terminado": ["Pruebas pasan"],
                    "esfuerzo": "M",
                },
                {
                    "id": "TT-002",
                    "titulo": "Formulario",
                    "rol": "frontend",
                    "descripcion": "Formulario Angular",
                    "ids_componentes": ["CM-001"],
                    "ids_historias": ["HU-001"],
                    "depende_de": ["TT-001"],
                    "criterios_terminado": ["Valida edad"],
                    "esfuerzo": "S",
                },
            ],
        }
    ).model_dump(mode="json")


def test_valid_architecture_passes_all_rules():
    report = assess_architecture(CONTEXT, software(), infra(), plan(), ALLOWED)
    assert report["puede_publicar"], report["observaciones"]


def test_rules_assign_errors_to_the_responsible_agent():
    sw, inf, pl = software(), infra(), plan()
    sw["contenedores"][1]["tecnologia"] = "Java Spring"  # fuera del catálogo
    sw["componentes"][1]["ids_historias"] = ["HU-001"]  # HU-002 sin componente
    inf["nodos"] = [n for n in inf["nodos"] if n["id"] != "IN-006"]  # API sin nube
    pl["tareas"][0]["depende_de"] = ["TT-002"]  # orden inválido
    report = assess_architecture(CONTEXT, sw, inf, pl, ALLOWED)
    codes = {(f["agente"], f["codigo"]) for f in report["observaciones"]}
    assert ("arquitecto_software", "TECNOLOGIA_NO_PERMITIDA") in codes
    assert ("arquitecto_software", "HISTORIA_SIN_COMPONENTE") in codes
    assert ("arquitecto_infraestructura", "SIN_DESPLIEGUE_NUBE") in codes
    assert ("planificador", "ORDEN_INVALIDO") in codes
    assert not report["puede_publicar"]


def test_rnf_requires_quality_attribute_and_single_api():
    sw = software()
    sw["atributos_calidad"][0]["ids_requisitos"] = ["RF-001"]
    sw["contenedores"].append({**sw["contenedores"][1], "id": "CT-009"})
    codes = {
        f["codigo"]
        for f in assess_architecture(CONTEXT, sw, infra(), None, ALLOWED)["observaciones"]
    }
    assert {"RNF_SIN_ATRIBUTO", "MONOLITO_INVALIDO"} <= codes


def test_generated_files_run_locally_and_in_eks():
    sw, inf = software(), infra()
    views = build_views("Creación de usuario", CONTEXT["actores"], sw, inf)
    kinds = {v["id"] for v in views}
    assert {
        "c4-contexto",
        "c4-contenedores",
        "c4-componentes",
        "despliegue-local",
        "despliegue-nube",
    } <= kinds
    sequence = next(v for v in views if v["tipo"] == "secuencia")
    assert "alt ¿Aprueba?" in sequence["mermaid"] and any(
        p["alternativa"] for p in sequence["pasos"]
    )
    assert all("x" in n and "y" in n for v in views if v["tipo"] == "grafo" for n in v["nodos"])
    compose_file = compose(sw, inf)
    assert "image: postgres:16" in compose_file and "context: ./backend" in compose_file
    assert (
        "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?" in compose_file
    )  # sin contraseñas en el archivo
    manifests = kubernetes("Creación de usuario", sw, inf)
    assert "kind: Deployment" in manifests and "replicas: 2" in manifests
    assert "secretKeyRef" in manifests and "ingressClassName: alb" in manifests
    assert manifests.index("path: /api") < manifests.index("path: /\n")
    xml = drawio(views)
    assert xml.startswith("<?xml") and xml.count("<diagram ") == sum(
        v["tipo"] == "grafo" for v in views
    )
    content = {
        "nombre_proyecto": "Creación de usuario",
        "version_arquitectura": 1,
        "version_backlog_origen": 3,
        "version_linea_base_origen": 2,
        "software": sw,
        "infraestructura": inf,
        "plan": plan(),
        "vistas": views,
    }
    generated = files(content)
    assert {
        "README.md",
        "docker-compose.yml",
        "k8s.yaml",
        "arquitectura.drawio",
        ".env.example",
    } <= set(generated)
    assert (
        "docker compose up --build" in generated["README.md"]
        and "ADR-001" in generated["README.md"]
    )


def test_compact_context_omits_history_and_long_text():
    baseline = {
        "requisitos": [{"id": "RF-001", "tipo": "requisito_funcional", "descripcion": "x" * 900}],
        "actores": [{"id": "ACT-001", "descripcion": "Empleado"}],
        "reglas_negocio": [],
        "restricciones": [],
        "decisiones": [],
    }
    backlog = {
        "historias": [
            {
                "id": "HU-001",
                "titulo": "Solicitar",
                "quiero": "y",
                "criterios_aceptacion": [{"entonces": "ok", "dado": "a", "cuando": "b"}],
                "requisitos_origen": [{"id": "RF-001", "version": 1}],
                "version": 4,
            }
        ]
    }
    data = compact_context("P", baseline, backlog, None)
    assert len(data["requisitos"][0]["descripcion"]) == 400
    assert data["historias"][0] == {
        "id": "HU-001",
        "titulo": "Solicitar",
        "quiero": "y",
        "criterios": ["ok"],
        "requisitos": ["RF-001"],
    }


class FakeModels:
    settings = SimpleNamespace(
        llm_model="simulado", llm_provider="sin-red", architecture_max_tokens=6144
    )

    def __init__(self, broken_tech=False):
        self.calls, self.broken_tech = [], broken_tech

    async def json(self, messages, schema, usage=None, **kwargs):
        self.calls.append(schema.__name__)
        usage["entrada"], usage["salida"] = 100, 50
        if schema is SoftwareProposal:
            value = software()
            if self.broken_tech and self.calls.count("SoftwareProposal") == 1:
                value["contenedores"][1]["tecnologia"] = "Java Spring"
            return SoftwareProposal.model_validate(value)
        if schema is InfraProposal:
            return InfraProposal.model_validate(infra())
        if schema is ArchitectureReview:
            return ArchitectureReview(observaciones=[])
        return Plan.model_validate(plan())


class FakeService:
    async def persist(self, state):
        return {
            "software": state["software"],
            "plan": state["plan"],
            "validacion": state["report"],
            "consumo": state["usage"],
            "correcciones": state["corrections"],
        }


class FakeEvents:
    def __init__(self):
        self.items = []

    async def emit(self, *args):
        self.items.append(args)


def run_team(models):
    team = ArchitectureTeam(FakeService(), models, FakeEvents(), InMemorySaver())
    initial = {
        "project_id": "p",
        "execution_id": "r",
        "request": {"instrucciones": ""},
        "context": {
            "datos": deepcopy(CONTEXT),
            "tecnologias_permitidas": ALLOWED,
            "version_backlog": 3,
            "version_linea_base": 2,
            "version_mockups": None,
            "decision_anterior": None,
        },
    }
    return run(team.graph.ainvoke(initial, {"configurable": {"thread_id": "t"}}))["content"]


def test_graph_runs_agents_in_order_and_records_usage():
    models = FakeModels()
    content = run_team(models)
    assert models.calls == ["SoftwareProposal", "InfraProposal", "ArchitectureReview", "Plan"]
    assert content["validacion"]["puede_publicar"] and content["plan"]["tareas"]
    assert content["consumo"]["arquitecto_software"] == {
        "entrada": 100,
        "salida": 50,
        "ms": content["consumo"]["arquitecto_software"]["ms"],
        "llamadas": 1,
    }


def test_rule_error_triggers_one_targeted_correction_before_semantic_review():
    models = FakeModels(broken_tech=True)
    content = run_team(models)
    # Software se corrige y la infraestructura se recalcula; el validador LLM corre una sola vez.
    assert models.calls == [
        "SoftwareProposal",
        "InfraProposal",
        "SoftwareProposal",
        "InfraProposal",
        "ArchitectureReview",
        "Plan",
    ]
    assert content["correcciones"] == 1 and content["validacion"]["puede_publicar"]


def test_actor_names_are_short_and_parallel_edges_merge():
    from app.services.architecture_service import actor_name

    assert (
        actor_name("Empleado que accede al portal de la empresa para crear su usuario.")
        == "Empleado"
    )
    assert actor_name("Líder de área, responsable de aprobar") == "Líder de área"
    sw = software()
    sw["relaciones"].append(
        {"origen": "ACT-001", "destino": "CT-001", "descripcion": "Consulta", "protocolo": "HTTPS"}
    )
    view = next(
        v for v in build_views("P", CONTEXT["actores"], sw, infra()) if v["id"] == "c4-contenedores"
    )
    pairs = [(e["origen"], e["destino"]) for e in view["aristas"]]
    assert len(pairs) == len(set(pairs)) and any("(+1)" in e["etiqueta"] for e in view["aristas"])


def test_names_are_normalized_to_ids_without_model_calls():
    from app.services.architecture_service import normalize_infra, normalize_software

    sw = software()
    sw["relaciones"][0]["destino"] = "Portal web"
    sw["flujos"][0]["pasos"][0]["de"] = "Líder"
    sw["componentes"][0]["contenedor"] = "CT-001 Portal web"
    fixed = normalize_software(sw, CONTEXT)
    assert fixed["relaciones"][0]["destino"] == "CT-001"
    assert fixed["flujos"][0]["pasos"][0]["de"] == "ACT-002"
    assert fixed["componentes"][0]["contenedor"] == "CT-001"
    inf = infra()
    inf["nodos"][1]["aloja"] = ["API"]
    inf["conexiones"][0]["destino"] = "Postgres"
    fixed_infra = normalize_infra(inf, fixed)
    assert fixed_infra["nodos"][1]["aloja"] == ["CT-002"]
    assert fixed_infra["conexiones"][0]["destino"] == "IN-003"
    assert assess_architecture(CONTEXT, fixed, fixed_infra, None, ALLOWED)["puede_publicar"]


def test_compose_never_depends_on_undefined_services_and_k8s_has_no_empty_documents():
    inf = infra()
    inf["nodos"].append(
        {
            "id": "IN-009",
            "entorno": "local",
            "tipo": "servicio_externo",
            "nombre": "SMTP",
            "tecnologia": "SMTP",
            "aloja": [],
            "puerto": None,
            "replicas": 1,
            "configuracion": [],
            "explicacion": "Correo",
        }
    )
    inf["conexiones"].append(
        {"origen": "IN-002", "destino": "IN-009", "descripcion": "Correo", "protocolo": "SMTP"}
    )
    compose_file = compose(software(), inf)
    assert "- smtp" not in compose_file and "- postgres" in compose_file
    documents = kubernetes("P", software(), inf).split("\n---\n")
    assert all(any(line and not line.startswith("#") for line in d.splitlines()) for d in documents)
