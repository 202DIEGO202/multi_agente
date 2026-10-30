from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class TipoCreate(InputModel):
    nombre: str = Field(min_length=1, max_length=200)
    estado: Literal['Activo', 'Inactivo'] = 'Activo'
    requiere_motivo: bool = False
    permite_horas: bool = False
    flujo_codigo: Literal['JEFE', 'JEFE_TH', 'TH']


class TipoUpdate(TipoCreate):
    version_esperada: int = Field(ge=1, strict=True)


class FlujoUpdate(InputModel):
    flujo_codigo: Literal['JEFE', 'JEFE_TH', 'TH']
    version_esperada: int = Field(ge=1, strict=True)


class DecisionInput(InputModel):
    decision: Literal['APROBAR', 'RECHAZAR', 'VALIDAR_Y_APROBAR']
    version_solicitud_esperada: int = Field(ge=1, strict=True)
    version_revision_esperada: int = Field(ge=1, strict=True)
    observacion: str | None = Field(default=None, max_length=5000)
    siguiente_aprobador_id: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode='after')
    def validate_decision(self):
        if self.observacion == '':
            raise ValueError('La observación no puede estar vacía')
        if self.decision == 'RECHAZAR':
            if not self.observacion:
                raise ValueError('El motivo del rechazo es obligatorio')
            if self.siguiente_aprobador_id is not None:
                raise ValueError('Un rechazo no admite un siguiente aprobador')
        return self