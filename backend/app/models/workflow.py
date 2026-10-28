from uuid import UUID

from pydantic import Field

from app.models.schemas import Contract


class StartWorkflow(Contract):
    id_solicitud: UUID
    objetivo: str = Field(min_length=15, max_length=12000)
    desplegar_local: bool = False
