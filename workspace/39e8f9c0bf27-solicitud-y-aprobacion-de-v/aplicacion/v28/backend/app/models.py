from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Health(BaseModel):
    estado: Literal['ok']


class Tipo(InputModel):
    nombre: str = Field(min_length=1, max_length=150)
    estado: Literal['ACTIVO', 'INACTIVO'] = 'ACTIVO'
    flujo: Literal['JEFE', 'JEFE_TH', 'TH']
    requiere_motivo: bool = False
    modalidad_horas: Literal['NO_APLICA', 'OPCIONAL', 'OBLIGATORIA'] = 'OPCIONAL'


class TipoUpdate(Tipo):
    version: PositiveInt


class FlujoUpdate(InputModel):
    flujo: Literal['JEFE', 'JEFE_TH', 'TH']
    version: PositiveInt


class SolicitudCreate(InputModel):
    tipo_ausencia_id: PositiveInt
    origen: Literal['PORTAL', 'FORMATO_OFICIAL'] = 'PORTAL'
    referencia_formato: str | None = Field(default=None, min_length=1, max_length=250)
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: time | None = None
    hora_fin: time | None = None
    motivo: str | None = Field(default=None, min_length=1, max_length=5000)

    @model_validator(mode='after')
    def validate_dates(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError('La fecha final debe ser igual o posterior a la inicial')
        if (self.hora_inicio is None) != (self.hora_fin is None):
            raise ValueError('Las horas deben proporcionarse juntas')
        if self.hora_inicio is not None:
            if self.hora_inicio.tzinfo is not None or self.hora_fin.tzinfo is not None:
                raise ValueError('Las horas deben ser locales, sin zona horaria')
            if datetime.combine(self.fecha_fin, self.hora_fin) <= datetime.combine(self.fecha_inicio, self.hora_inicio):
                raise ValueError('El final debe ser posterior al inicio')
        if self.origen == 'FORMATO_OFICIAL' and not self.referencia_formato:
            raise ValueError('El formato oficial requiere referencia')
        if self.origen == 'PORTAL' and self.referencia_formato is not None:
            raise ValueError('La referencia solo corresponde a un formato oficial')
        return self


class Decision(InputModel):
    version_solicitud: PositiveInt
    version_revision: PositiveInt
    accion: Literal['VALIDAR', 'APROBAR', 'RECHAZAR', 'VALIDAR_APROBAR']
    observacion: str | None = Field(default=None, min_length=1, max_length=5000)

    @model_validator(mode='after')
    def validate_reason(self):
        if self.accion == 'RECHAZAR' and not self.observacion:
            raise ValueError('El rechazo requiere un motivo')
        return self


class ObservacionCreate(InputModel):
    version_solicitud: PositiveInt
    version_revision: PositiveInt
    contenido: str = Field(min_length=1, max_length=5000)