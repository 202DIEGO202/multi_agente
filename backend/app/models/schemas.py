import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Text = Annotated[str, Field(min_length=1, max_length=12000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ItemType(StrEnum):
    FUNCTIONAL = "requisito_funcional"
    NON_FUNCTIONAL = "requisito_no_funcional"
    OBJECTIVE = "objetivo"
    ACTOR = "actor"
    RULE = "regla_negocio"
    CONSTRAINT = "restriccion"
    DECISION = "decision"
    ASSUMPTION = "supuesto"
    QUESTION = "pregunta_pendiente"


PREFIX = {
    ItemType.FUNCTIONAL: "RF",
    ItemType.NON_FUNCTIONAL: "RNF",
    ItemType.OBJECTIVE: "OBJ",
    ItemType.ACTOR: "ACT",
    ItemType.RULE: "RN",
    ItemType.CONSTRAINT: "RES",
    ItemType.DECISION: "DEC",
    ItemType.ASSUMPTION: "SUP",
    ItemType.QUESTION: "PRE",
}


class ProjectCreate(Contract):
    nombre: Annotated[str, Field(min_length=2, max_length=160)]
    descripcion: str = Field(default="", max_length=4000)
    modo: Literal["supervisado", "automatico"] = "supervisado"


class MessageCreate(Contract):
    contenido: Text
    id_solicitud: UUID


class Change(Contract):
    operacion: Literal["crear", "modificar", "descartar"]
    tipo: ItemType
    descripcion: Text
    id_elemento: str | None = None
    version_esperada: int | None = Field(default=None, ge=1)
    referencias: list[str] = Field(default_factory=list, max_length=40)
    fuentes_documentales: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def validate_target(self):
        if self.operacion != "crear" and not (self.id_elemento and self.version_esperada):
            raise ValueError("Una modificación requiere identificador y versión vigente")
        if self.operacion == "crear" and (self.id_elemento or self.version_esperada):
            raise ValueError("Los identificadores de nuevos elementos los asigna el servidor")
        if len(set(self.referencias)) != len(self.referencias):
            raise ValueError("Referencias duplicadas")
        return self


class Interpretation(Contract):
    consultar_conocimiento: bool
    actualizar_estado: bool


class CreateChange(Change):
    operacion: Literal["crear"]
    id_elemento: None = None
    version_esperada: None = None


class UpdateChange(Change):
    operacion: Literal["modificar", "descartar"]
    id_elemento: str
    version_esperada: int = Field(ge=1)


class SuggestedUpdate(Contract):
    operacion: Literal["modificar", "descartar"]
    tipo: ItemType
    descripcion: Text
    id_elemento: str
    referencias: list[str] = Field(default_factory=list, max_length=40)
    fuentes_documentales: list[str] = Field(default_factory=list, max_length=40)


class ConflictEvidence(Contract):
    descripcion: Text
    id_fuente: str | None = None
    cita_vigente: Text
    cita_nueva: Text


class ProcedureCitation(Contract):
    id_fragmento: str
    cita: Text


class ProcedureReview(Contract):
    estado: Literal[
        "compatible",
        "requiere_aclaracion",
        "contradice",
        "sin_evidencia",
        "no_aplica",
        "decision_analista",
    ]
    motivo: Text
    fuentes: list[ProcedureCitation] = Field(default_factory=list, max_length=10)


class Extraction(Contract):
    """El modelo interpreta el cambio; el servidor fija la revisión que fue leída."""

    revision_procedimientos: ProcedureReview | None = None
    cambios: list[CreateChange | SuggestedUpdate] = Field(default_factory=list, max_length=25)
    contradicciones_criticas: list[ConflictEvidence] = Field(default_factory=list, max_length=10)
    preguntas: list[str] = Field(default_factory=list, max_length=10)


class Analysis(Contract):
    cambios: list[CreateChange | UpdateChange] = Field(default_factory=list, max_length=25)
    contradicciones_criticas: list[str] = Field(default_factory=list, max_length=10)
    preguntas: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("cambios", mode="before")
    @classmethod
    def accept_change_objects(cls, values):
        return [value.model_dump() if isinstance(value, Change) else value for value in values]


class Review(Contract):
    accion: Literal["aprobar", "rechazar"]
    descripcion: str | None = Field(default=None, min_length=1, max_length=12000)
    # Parámetros no críticos (listas, mensajes, canales) que el analista define sin documento.
    confirmar_decision_analista: bool = False


class ConflictResolution(Contract):
    resolucion: Annotated[str, Field(min_length=5, max_length=4000)]


class PublishBaseline(Contract):
    aprobacion_humana: bool = False


class Fragment(Contract):
    id_fragmento: str
    id_documento: str
    documento: str
    contenido: str
    pagina: int = Field(ge=1)
    posicion: int = Field(ge=0)
    version_documento: int = Field(ge=1)
    categoria: str
    puntuacion_vectorial: float | None = None
    posicion_vectorial: int | None = None
    puntuacion_bm25: float | None = None
    posicion_bm25: int | None = None
    puntuacion_rrf: float | None = None
    posicion_rrf: int | None = None


class RetrievalResult(Contract):
    version_esquema: Literal["1.1"] = "1.1"
    consulta_original: str
    consulta_reformulada: str
    vectoriales: list[Fragment]
    bm25: list[Fragment]
    rrf: list[Fragment]
    seleccionados: list[Fragment]
    degradaciones: list[str]
    duracion_ms: float = Field(ge=0)
    revision_conocimiento: int = Field(ge=0)
    motivo_sin_evidencia: str | None = None


class FunctionalItem(Contract):
    id: str
    tipo: ItemType
    descripcion: Text
    version: int = Field(ge=1)
    estado: Literal["validado_automaticamente", "aprobado_por_humano"]
    vigencia: Literal["vigente", "descartado"] = "vigente"
    origen: Literal["conversacion"] = "conversacion"
    id_mensaje: str
    id_ejecucion: str
    referencias: list[str] = Field(default_factory=list)
    fuentes_documentales: list[str] = Field(default_factory=list)
    elementos_afectados: list[str] = Field(default_factory=list)
    fecha_modificacion: datetime


class Baseline(Contract):
    id_proyecto: str
    nombre_proyecto: str
    version_esquema: Literal["1.0"] = "1.0"
    version_linea_base: int = Field(ge=1)
    estado: Literal["validado_automaticamente", "aprobado_por_humano"]
    requisitos: list[FunctionalItem] = Field(default_factory=list)
    objetivos: list[FunctionalItem] = Field(default_factory=list)
    actores: list[FunctionalItem] = Field(default_factory=list)
    decisiones: list[FunctionalItem] = Field(default_factory=list)
    reglas_negocio: list[FunctionalItem] = Field(default_factory=list)
    restricciones: list[FunctionalItem] = Field(default_factory=list)
    preguntas_pendientes: list[FunctionalItem] = Field(default_factory=list)
    supuestos: list[FunctionalItem] = Field(default_factory=list)
    artefactos: list[dict[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        items = [
            item
            for name in (
                "requisitos",
                "objetivos",
                "actores",
                "decisiones",
                "reglas_negocio",
                "restricciones",
                "preguntas_pendientes",
                "supuestos",
            )
            for item in getattr(self, name)
        ]
        ids = [i.id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Identificadores duplicados en la línea base")
        for item in items:
            if set(item.referencias) - set(ids):
                raise ValueError(f"Referencias inexistentes en {item.id}")
        if not self.requisitos:
            raise ValueError("Se requiere al menos un requisito consolidado")
        return self


def normalized(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


class KnowledgeLink(Contract):
    id_proyecto_origen: UUID
