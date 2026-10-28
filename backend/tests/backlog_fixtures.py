from copy import deepcopy
from datetime import UTC, datetime

from app.models.backlog import Organization, SemanticReview, Stories
from app.models.schemas import FunctionalItem
from app.services.backlog_logic import prepare_generated, validate_backlog


def baseline_fixture():
    def item(item_id, kind, text):
        return FunctionalItem(
            id=item_id,
            tipo=kind,
            descripcion=text,
            version=1,
            estado="validado_automaticamente",
            id_mensaje="mensaje-prueba",
            id_ejecucion="ejecucion-prueba",
            fecha_modificacion=datetime.now(UTC),
        ).model_dump(mode="json")

    return {
        "id_proyecto": "proyecto-prueba",
        "nombre_proyecto": "Soporte de prueba",
        "version_esquema": "1.0",
        "version_linea_base": 1,
        "estado": "validado_automaticamente",
        "requisitos": [
            item(
                "RF-001", "requisito_funcional", "Registrar solicitudes de soporte con descripción"
            )
        ],
        "actores": [item("ACT-001", "actor", "Empleado")],
        "objetivos": [],
        "decisiones": [],
        "reglas_negocio": [],
        "restricciones": [],
        "preguntas_pendientes": [],
        "supuestos": [],
        "artefactos": [],
    }


def organization_fixture():
    return Organization.model_validate(
        {
            "epicas": [
                {
                    "clave": "e1",
                    "id_existente": None,
                    "titulo": "Gestión de soporte",
                    "descripcion": "Organizar el registro de solicitudes",
                    "ids_requisitos": ["RF-001"],
                }
            ],
            "features": [
                {
                    "clave": "f1",
                    "id_existente": None,
                    "titulo": "Registro de solicitudes",
                    "descripcion": "Registrar solicitudes con descripción",
                    "clave_epica": "e1",
                    "ids_requisitos": ["RF-001"],
                }
            ],
            "requisitos_sin_asignar": [],
            "preguntas_pendientes": [],
        }
    )


def stories_fixture():
    return Stories.model_validate(
        {
            "historias": [
                {
                    "clave": "h1",
                    "id_existente": None,
                    "titulo": "Registrar solicitud de soporte",
                    "clave_feature": "f1",
                    "id_actor": "ACT-001",
                    "quiero": "registrar una solicitud con descripción",
                    "para": "comunicar mi necesidad de soporte",
                    "ids_requisitos": ["RF-001"],
                    "criterios_aceptacion": [
                        {
                            "dado": "un empleado con una descripción de su necesidad",
                            "cuando": "registra la solicitud",
                            "entonces": "la solicitud conserva la descripción ingresada",
                        }
                    ],
                }
            ],
            "preguntas_pendientes": [],
        }
    )


def context_fixture():
    return {
        "project": {
            "id": "proyecto-prueba",
            "mode": "supervisado",
            "state_revision": 2,
            "counters": {},
        },
        "baseline": baseline_fixture(),
        "previous": None,
        "known": {},
        "head": 0,
        "instructions": "",
    }


def content_fixture(context=None, run_id="ejecucion-prueba"):
    context = deepcopy(context or context_fixture())
    candidate, counters = prepare_generated(
        context, organization_fixture(), stories_fixture(), run_id
    )
    content = validate_backlog(candidate, context["baseline"], SemanticReview())
    return content.model_dump(mode="json"), counters
