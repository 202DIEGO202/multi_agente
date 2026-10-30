from datetime import date, time, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Acceso(Input):
    documento: str = Field(min_length=1, max_length=100)

class TokenRespuesta(BaseModel):
    token: str
    tipo: str = 'Bearer'
    expira_en: int

class Fechas(Input):
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: time | None = None
    hora_fin: time | None = None
    motivo: str | None = Field(default=None, min_length=1, max_length=4000)
    referencia_formato: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode='after')
    def validar_fechas(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError('La fecha final debe ser igual o posterior a la inicial')
        if (self.hora_inicio is None) != (self.hora_fin is None):
            raise ValueError('Indique ambas horas o ninguna')
        if self.hora_inicio is not None:
            if self.hora_inicio.tzinfo is not None or self.hora_fin.tzinfo is not None:
                raise ValueError('Las horas deben ser locales, sin zona horaria')
            if datetime.combine(self.fecha_inicio, self.hora_inicio) >= datetime.combine(self.fecha_fin, self.hora_fin):
                raise ValueError('El intervalo horario debe ser positivo')
        return self

class CrearSolicitud(Fechas):
    tipo_ausencia_id: int = Field(gt=0)
    origen: Literal['PORTAL', 'FORMATO_OFICIAL'] = 'PORTAL'

    @model_validator(mode='after')
    def validar_origen(self):
        if self.origen == 'PORTAL' and self.referencia_formato is not None:
            raise ValueError('La referencia solo corresponde al formato oficial')
        if self.origen == 'FORMATO_OFICIAL' and not self.referencia_formato:
            raise ValueError('Indique la referencia del formato oficial')
        return self

class EditarSolicitud(Fechas):
    version: int = Field(gt=0)

class Version(Input):
    version: int = Field(gt=0)

class Decision(Input):
    version: int = Field(gt=0)
    accion: Literal['VALIDAR', 'APROBAR', 'RECHAZAR', 'VALIDAR_Y_APROBAR']
    observacion: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode='after')
    def validar_rechazo(self):
        if self.accion == 'RECHAZAR' and not self.observacion:
            raise ValueError('El motivo del rechazo es obligatorio')
        return self

class TipoAusencia(Input):
    nombre: str = Field(min_length=1, max_length=150)
    estado: Literal['ACTIVO', 'INACTIVO'] = 'ACTIVO'
    requiere_motivo: bool = False
    permite_horas: bool = False
    flujo_codigo: Literal['JEFE_INMEDIATO', 'JEFE_Y_TALENTO_HUMANO', 'TALENTO_HUMANO']

class Flujo(Input):
    flujo_codigo: Literal['JEFE_INMEDIATO', 'JEFE_Y_TALENTO_HUMANO', 'TALENTO_HUMANO']

Estado = Literal['ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA', 'CANCELADA']