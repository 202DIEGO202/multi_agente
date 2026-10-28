"""Contrato declarativo: el navegador nunca ejecuta HTML o código producido por IA."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.schemas import Contract


class Control(Contract):
    clave: str = Field(min_length=1, max_length=80)
    # ficha: datos de solo lectura; cada opción es "Campo: valor de ejemplo".
    tipo: Literal["texto", "entrada", "selector", "boton", "aviso", "casilla", "ficha"]
    etiqueta: str = Field(min_length=1, max_length=500)
    ayuda: str = Field(default="", max_length=800)
    obligatorio: bool = False
    opciones: list[str] = Field(default_factory=list, max_length=12)
    destino: str | None = None
    ids_criterios: list[str] = Field(default_factory=list, max_length=40)
    ids_requisitos: list[str] = Field(default_factory=list, max_length=40)


class Screen(Contract):
    id: str = Field(pattern=r"^PA-[0-9]{3,}$")
    version: int = Field(default=1, ge=1)
    titulo: str = Field(min_length=3, max_length=200)
    descripcion: str = Field(min_length=3, max_length=1500)
    ids_historias: list[str] = Field(min_length=1, max_length=40)
    ids_criterios_visuales: list[str] = Field(default_factory=list, max_length=40)
    ids_requisitos_visuales: list[str] = Field(default_factory=list, max_length=40)
    controles: list[Control] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def unique_controls(self):
        keys = [i.clave for i in self.controles]
        if len(keys) != len(set(keys)):
            raise ValueError("Claves de controles duplicadas")
        return self


class Palette(Contract):
    fondo: str = Field(default="#FFF8F0", pattern=r"^#[0-9A-Fa-f]{6}$")
    superficie: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    texto: str = Field(default="#30251F", pattern=r"^#[0-9A-Fa-f]{6}$")
    acento: str = Field(default="#944526", pattern=r"^#[0-9A-Fa-f]{6}$")
    texto_boton: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")


class NonVisualCriterion(Contract):
    id_criterio: str = Field(pattern=r"^HU-[0-9]{3,}-CA-[0-9]{2,}$")
    justificacion: str = Field(min_length=15, max_length=1500)


class Design(Contract):
    paleta: Palette = Field(default_factory=Palette)
    pantallas: list[Screen] = Field(min_length=1, max_length=20)
    preguntas: list[str] = Field(default_factory=list, max_length=10)
    criterios_no_visuales: list[NonVisualCriterion] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_screens(self):
        if len({i.id for i in self.pantallas}) != len(self.pantallas):
            raise ValueError("Identificadores de pantalla duplicados")
        return self


class DesignFinding(Contract):
    severidad: Literal["error", "advertencia"]
    descripcion: str = Field(min_length=3, max_length=1500)
    ids_elementos: list[str] = Field(default_factory=list, max_length=40)


class DesignReview(Contract):
    observaciones: list[DesignFinding] = Field(default_factory=list, max_length=40)


class GenerateMockups(Contract):
    version_backlog: int = Field(ge=1)
    id_solicitud: UUID
    instrucciones: str = Field(default="", max_length=4000)
    version_base: int | None = Field(default=None, ge=1)
    pantalla_id: str | None = Field(default=None, pattern=r"^PA-[0-9]{3,}$")


class ReviewMockups(Contract):
    accion: Literal["aprobar", "rechazar"]
    nota: str = Field(min_length=3, max_length=2000)


class ViewScreen(Contract):
    pantalla_id: str = Field(pattern=r"^PA-[0-9]{3,}$")
