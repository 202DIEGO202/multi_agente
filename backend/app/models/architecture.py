"""Contratos de fase 4: arquitectura de software, infraestructura y plan técnico.

Los agentes solo devuelven datos declarativos. Diagramas, docker-compose y manifiestos
Kubernetes los genera el servidor a partir de este modelo canónico (cero tokens).
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.models.schemas import Contract, Text

Name = Field(min_length=2, max_length=160)
Short = Field(min_length=2, max_length=600)


class QualityAttribute(Contract):
    id: str = Field(pattern=r"^AC-[0-9]{3,}$")
    atributo: Literal[
        "rendimiento",
        "seguridad",
        "disponibilidad",
        "mantenibilidad",
        "usabilidad",
        "escalabilidad",
        "trazabilidad",
        "portabilidad",
        "confiabilidad",
    ]
    escenario: Text
    medida: str = Short
    prioridad: Literal["alta", "media", "baja"]
    ids_requisitos: list[str] = Field(min_length=1, max_length=20)


class Decision(Contract):
    """ADR: la decisión y su tradeoff explícito."""

    id: str = Field(pattern=r"^ADR-[0-9]{3,}$")
    titulo: str = Name
    contexto: Text
    decision: Text
    alternativas: list[str] = Field(min_length=1, max_length=6)
    ventajas: list[str] = Field(min_length=1, max_length=8)
    desventajas: list[str] = Field(min_length=1, max_length=8)
    ids_atributos: list[str] = Field(min_length=1, max_length=10)


class SoftwareContainer(Contract):
    """Nivel 2 de C4: unidad desplegable o sistema externo."""

    id: str = Field(pattern=r"^CT-[0-9]{3,}$")
    nombre: str = Name
    tipo: Literal["aplicacion_web", "api", "base_datos", "servicio_externo"]
    tecnologia: str = Name
    responsabilidad: str = Short


class Component(Contract):
    """Nivel 3 de C4: módulo interno de un contenedor."""

    id: str = Field(pattern=r"^CM-[0-9]{3,}$")
    contenedor: str
    nombre: str = Name
    tipo: Literal[
        "modulo_ui", "controlador", "servicio", "repositorio", "integracion", "esquema_datos"
    ]
    responsabilidad: str = Short
    ids_historias: list[str] = Field(default_factory=list, max_length=30)
    operaciones: list[str] = Field(default_factory=list, max_length=12)


class Relation(Contract):
    origen: str
    destino: str
    descripcion: str = Short
    protocolo: str = Field(min_length=2, max_length=80)


class Step(Contract):
    de: str
    a: str
    mensaje: str = Short


class Flow(Contract):
    """Secuencia de una historia; la alternativa cubre el camino de error o rechazo."""

    id: str = Field(pattern=r"^SQ-[0-9]{3,}$")
    titulo: str = Name
    ids_historias: list[str] = Field(min_length=1, max_length=10)
    pasos: list[Step] = Field(min_length=2, max_length=20)
    condicion_alternativa: str | None = Field(default=None, max_length=300)
    paso_desvio: int | None = Field(default=None, ge=1)
    alternativa: list[Step] = Field(default_factory=list, max_length=12)


class SoftwareProposal(Contract):
    resumen: Text
    estilo: Literal["monolito_modular", "monolito_en_capas"]
    atributos_calidad: list[QualityAttribute] = Field(min_length=1, max_length=15)
    decisiones: list[Decision] = Field(min_length=1, max_length=12)
    contenedores: list[SoftwareContainer] = Field(min_length=2, max_length=12)
    componentes: list[Component] = Field(min_length=1, max_length=40)
    relaciones: list[Relation] = Field(min_length=1, max_length=60)
    flujos: list[Flow] = Field(min_length=1, max_length=15)
    preguntas: list[str] = Field(default_factory=list, max_length=10)


class InfraNode(Contract):
    id: str = Field(pattern=r"^IN-[0-9]{3,}$")
    entorno: Literal["local", "nube"]
    tipo: Literal[
        "contenedor",
        "base_datos",
        "balanceador",
        "secreto",
        "registro_imagenes",
        "monitoreo",
        "servicio_externo",
    ]
    nombre: str = Name
    tecnologia: str = Name
    aloja: list[str] = Field(default_factory=list, max_length=10)
    puerto: int | None = Field(default=None, ge=1, le=65535)
    replicas: int = Field(default=1, ge=1, le=10)
    configuracion: list[str] = Field(default_factory=list, max_length=15)
    explicacion: str = Short


class InfraProposal(Contract):
    resumen: Text
    estrategia_despliegue: Text
    seguridad: Text
    observabilidad: Text
    nodos: list[InfraNode] = Field(min_length=2, max_length=30)
    conexiones: list[Relation] = Field(default_factory=list, max_length=40)


class ArchitectureFinding(Contract):
    severidad: Literal["error", "advertencia"]
    codigo: str = Field(min_length=2, max_length=60)
    agente: Literal["arquitecto_software", "arquitecto_infraestructura", "planificador"]
    descripcion: str = Field(min_length=3, max_length=1500)
    ids_elementos: list[str] = Field(default_factory=list, max_length=30)


class ArchitectureReview(Contract):
    observaciones: list[ArchitectureFinding] = Field(default_factory=list, max_length=30)


class TechnicalTask(Contract):
    id: str = Field(pattern=r"^TT-[0-9]{3,}$")
    titulo: str = Name
    rol: Literal["frontend", "backend", "datos", "devops", "qa"]
    descripcion: str = Field(min_length=3, max_length=1500)
    ids_componentes: list[str] = Field(min_length=1, max_length=10)
    ids_historias: list[str] = Field(default_factory=list, max_length=20)
    depende_de: list[str] = Field(default_factory=list, max_length=10)
    criterios_terminado: list[str] = Field(min_length=1, max_length=8)
    esfuerzo: Literal["S", "M", "L"]


class Plan(Contract):
    resumen: Text
    tareas: list[TechnicalTask] = Field(min_length=1, max_length=40)


class GenerateArchitecture(Contract):
    version_backlog: int = Field(ge=1)
    id_solicitud: UUID
    instrucciones: str = Field(default="", max_length=4000)


class ReviewArchitecture(Contract):
    accion: Literal["aprobar", "rechazar"]
    nota: str = Field(min_length=3, max_length=2000)
