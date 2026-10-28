"""Contratos de fase 2: entradas de agentes, artefactos y publicaciones."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.schemas import Contract, Text


class SourceReference(Contract):
    id: str
    version: int = Field(ge=1)


class DraftEpic(Contract):
    clave: str = Field(min_length=1, max_length=80)
    id_existente: str | None = None
    titulo: str = Field(min_length=3, max_length=200)
    descripcion: Text
    ids_requisitos: list[str] = Field(min_length=1, max_length=100)


class DraftFeature(DraftEpic):
    clave_epica: str


class Organization(Contract):
    epicas: list[DraftEpic] = Field(max_length=30)
    features: list[DraftFeature] = Field(max_length=100)
    requisitos_sin_asignar: list[str] = Field(default_factory=list)
    preguntas_pendientes: list[str] = Field(default_factory=list, max_length=30)


class DraftCriterion(Contract):
    dado: Text
    cuando: Text
    entonces: Text


class DraftStory(Contract):
    clave: str = Field(min_length=1, max_length=80)
    id_existente: str | None = None
    titulo: str = Field(min_length=3, max_length=200)
    clave_feature: str
    id_actor: str
    quiero: Text
    para: Text
    ids_requisitos: list[str] = Field(min_length=1, max_length=100)
    criterios_aceptacion: list[DraftCriterion] = Field(min_length=1, max_length=20)


class Stories(Contract):
    historias: list[DraftStory] = Field(max_length=150)
    preguntas_pendientes: list[str] = Field(default_factory=list, max_length=30)


class Finding(Contract):
    severidad: Literal["error", "advertencia"]
    codigo: str
    descripcion: Text
    ids_elementos: list[str] = Field(default_factory=list)


class SemanticReview(Contract):
    observaciones: list[Finding] = Field(default_factory=list, max_length=60)


class Artifact(Contract):
    id: str
    version: int = Field(ge=1)
    titulo: str = Field(min_length=3, max_length=200)
    descripcion: Text
    requisitos_origen: list[SourceReference] = Field(min_length=1)


class Epic(Artifact):
    pass


class Feature(Artifact):
    id_epica: str


class Criterion(DraftCriterion):
    id: str


class Story(Artifact):
    id_feature: str
    actor: SourceReference
    como: Text
    quiero: Text
    para: Text
    criterios_aceptacion: list[Criterion] = Field(min_length=1)


class ValidationReport(Contract):
    estructural: bool
    semantica: Literal["completada", "pendiente"]
    observaciones: list[Finding]
    requisitos_sin_cobertura: list[str]
    puede_publicar: bool


class BacklogContent(Contract):
    version_esquema: Literal["2.0"] = "2.0"
    id_proyecto: str
    version_backlog: int = Field(ge=1)
    version_linea_base_origen: int = Field(ge=1)
    version_estado_origen: int = Field(ge=0)
    id_ejecucion: str
    fecha: datetime
    operacion: Literal["generar", "editar", "validar"]
    nota: str
    epicas: list[Epic]
    features: list[Feature]
    historias: list[Story]
    preguntas_pendientes: list[str]
    validacion: ValidationReport

    @model_validator(mode="after")
    def validate_graph(self):
        items = [*self.epicas, *self.features, *self.historias]
        ids = [item.id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Identificadores de backlog duplicados")
        epics = {item.id for item in self.epicas}
        features = {item.id for item in self.features}
        if any(item.id_epica not in epics for item in self.features):
            raise ValueError("Una feature referencia una épica inexistente")
        if any(item.id_feature not in features for item in self.historias):
            raise ValueError("Una historia referencia una feature inexistente")
        criteria = [
            criterion.id for item in self.historias for criterion in item.criterios_aceptacion
        ]
        if len(criteria) != len(set(criteria)):
            raise ValueError("Identificadores de criterios duplicados")
        return self


class GenerateBacklog(Contract):
    version_linea_base: int = Field(ge=1)
    id_solicitud: UUID
    instrucciones: str = Field(default="", max_length=5000)


class BacklogPublication(BacklogContent):
    estado: Literal["validado_automaticamente", "aprobado_por_humano"]


class EditBacklog(Contract):
    id_solicitud: UUID
    id_elemento: str
    titulo: str = Field(min_length=3, max_length=200)
    descripcion: Text
    ids_requisitos: list[str] = Field(min_length=1, max_length=100)
    id_padre: str | None = None
    id_actor: str | None = None
    quiero: str | None = Field(default=None, min_length=1, max_length=12000)
    para: str | None = Field(default=None, min_length=1, max_length=12000)
    criterios_aceptacion: list[DraftCriterion] | None = None
    nota: str = Field(min_length=3, max_length=3000)


class ValidateBacklog(Contract):
    id_solicitud: UUID


class ReviewBacklog(Contract):
    accion: Literal["aprobar", "rechazar"]
    nota: str = Field(min_length=3, max_length=3000)
