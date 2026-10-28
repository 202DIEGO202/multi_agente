"""Contratos de fase 5: construcción por agentes, validación y despliegue en instancia."""

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models.schemas import Contract

SAFE_PATH = r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,180}$"
AGENTE = Literal[
    "desarrollador_datos",
    "desarrollador_backend",
    "desarrollador_portal",
    "desarrollador_panel",
    "agente_pruebas",
    "agente_iac",
    "validador_artefactos",
    "ejecucion",
]


class GeneratedFile(Contract):
    ruta: str = Field(pattern=SAFE_PATH)
    contenido: str = Field(min_length=1, max_length=60000)

    @field_validator("ruta")
    @classmethod
    def no_traversal(cls, value):
        if ".." in value.split("/") or "//" in value:
            raise ValueError("Ruta no permitida")
        return value


class Table(Contract):
    nombre: str = Field(min_length=1, max_length=80)
    columnas: list[str] = Field(min_length=1, max_length=40)


class DataBundle(Contract):
    archivos: list[GeneratedFile] = Field(min_length=1, max_length=4)
    tablas: list[Table] = Field(min_length=1, max_length=30)
    notas: str = Field(default="", max_length=2000)


class Endpoint(Contract):
    metodo: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    ruta: str = Field(pattern=r"^/api/[A-Za-z0-9_/{}.-]*$")
    acceso: Literal["publico", "administrador"]
    descripcion: str = Field(min_length=3, max_length=300)
    cuerpo: str = Field(default="", max_length=600)
    respuesta: str = Field(default="", max_length=600)
    ids_historias: list[str] = Field(default_factory=list, max_length=10)


class BackendBundle(Contract):
    archivos: list[GeneratedFile] = Field(min_length=1, max_length=12)
    endpoints: list[Endpoint] = Field(min_length=1, max_length=40)
    notas: str = Field(default="", max_length=2000)


class AppBundle(Contract):
    archivos: list[GeneratedFile] = Field(min_length=1, max_length=14)
    pantallas: list[str] = Field(default_factory=list, max_length=20)
    notas: str = Field(default="", max_length=2000)
    archivos_retirados: list[str] = Field(default_factory=list, max_length=14)


class QaCase(Contract):
    id: str = Field(pattern=r"^PR-[0-9]{3,}$")
    criterio: str = Field(min_length=3, max_length=40)
    archivo: str = Field(pattern=SAFE_PATH)
    descripcion: str = Field(min_length=3, max_length=400)


class QaBundle(Contract):
    archivos: list[GeneratedFile] = Field(min_length=1, max_length=8)
    casos: list[QaCase] = Field(min_length=1, max_length=60)


class IacBundle(Contract):
    archivos: list[GeneratedFile] = Field(min_length=1, max_length=8)
    notas: str = Field(default="", max_length=2000)


class ArtifactFinding(Contract):
    severidad: Literal["error", "advertencia"]
    codigo: str = Field(min_length=2, max_length=60)
    agente: AGENTE
    descripcion: str = Field(min_length=3, max_length=1500)
    archivo: str = Field(default="", max_length=200)


class ArtifactReview(Contract):
    observaciones: list[ArtifactFinding] = Field(default_factory=list, max_length=30)


class GenerateConstruction(Contract):
    version_arquitectura: int = Field(ge=1)
    id_solicitud: UUID
    instrucciones: str = Field(default="", max_length=4000)
    reutilizar_candidato: bool = False


class ReviewConstruction(Contract):
    accion: Literal["aprobar", "rechazar"]
    nota: str = Field(min_length=3, max_length=2000)


class DeployRequest(Contract):
    id_solicitud: UUID
