from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Health(BaseModel):
    estado: Literal['ok']


class Record(RootModel[dict[str, Any]]):
    pass


class Page(BaseModel):
    items: list[Record]
    limite: int
    desplazamiento: int


class AbsenceType(InputModel):
    nombre: str = Field(min_length=1, max_length=200)
    estado: Literal['ACTIVO', 'INACTIVO'] = 'ACTIVO'
    flujo_codigo: Literal['JEFE_INMEDIATO', 'JEFE_Y_TALENTO_HUMANO', 'TALENTO_HUMANO']
    requiere_motivo: bool = False
    modalidad_horas: Literal['NO_APLICA', 'OPCIONAL', 'OBLIGATORIA'] = 'OPCIONAL'


class Flow(InputModel):
    flujo_codigo: Literal['JEFE_INMEDIATO', 'JEFE_Y_TALENTO_HUMANO', 'TALENTO_HUMANO']


class Application(InputModel):
    tipo_ausencia_id: int = Field(gt=0)
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: time | None = None
    hora_fin: time | None = None
    motivo: str | None = Field(default=None, max_length=4000)
    origen: Literal['PORTAL_INTERNO', 'FORMATO_OFICIAL'] = 'PORTAL_INTERNO'
    referencia_formato: str | None = Field(default=None, max_length=500)

    @field_validator('motivo', 'referencia_formato')
    @classmethod
    def nonempty_optional(cls, value):
        if value is not None and not value.strip():
            raise ValueError('No se admiten textos vacíos')
        return value

    @model_validator(mode='after')
    def validate_period(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError('La fecha final debe ser igual o posterior a la inicial')
        if (self.hora_inicio is None) != (self.hora_fin is None):
            raise ValueError('Debe proporcionar ambas horas')
        if self.hora_inicio is not None:
            if self.hora_inicio.tzinfo is not None or self.hora_fin.tzinfo is not None:
                raise ValueError('Las horas deben ser locales, sin zona horaria')
            if datetime.combine(self.fecha_fin, self.hora_fin) <= datetime.combine(self.fecha_inicio, self.hora_inicio):
                raise ValueError('El instante final debe ser posterior al inicial')
        if self.origen == 'FORMATO_OFICIAL' and not self.referencia_formato:
            raise ValueError('El formato oficial requiere una referencia')
        if self.origen == 'PORTAL_INTERNO' and self.referencia_formato is not None:
            raise ValueError('La referencia solo corresponde al formato oficial')
        return self


class ReviewAction(InputModel):
    revision_id: int = Field(gt=0)
    version_esperada: int = Field(gt=0)
    accion: Literal['APROBAR', 'RECHAZAR', 'VALIDAR', 'VALIDAR_APROBAR']
    observacion: str | None = Field(default=None, max_length=4000)

    @model_validator(mode='after')
    def validate_observation(self):
        if self.observacion is not None and not self.observacion:
            raise ValueError('La observación no puede estar vacía')
        if self.accion == 'RECHAZAR' and not self.observacion:
            raise ValueError('El rechazo requiere un motivo en observacion')
        return self


class ReadResult(BaseModel):
    id: int
    leida_en: datetime