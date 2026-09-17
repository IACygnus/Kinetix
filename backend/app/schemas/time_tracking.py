"""Schemas del MÓDULO DE HORAS (ETAPA H1.3).

Mismo estilo que `schemas/client.py`: `XCreate` / `XUpdate` / `XResponse` con
`ConfigDict(from_attributes=True)`.

La validación de las horas en pasos de 0,25 (H-D8) vive aquí además de en la
base: el schema devuelve un **422 con mensaje legible** y la restricción de la
base es la última red, que devolvería un 500 feo si llegara a saltar.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

# H-D8: paso de las horas. En Decimal para no arrastrar el error del binario.
PASO_HORAS = Decimal("0.25")


def validar_paso(valor: Decimal, campo: str = "Las horas") -> Decimal:
    """Horas > 0 y múltiplo de 0,25 (H-D8)."""
    if valor is None:
        return valor
    v = Decimal(str(valor))
    if v <= 0:
        raise ValueError(f"{campo} tienen que ser mayores que cero")
    if (v % PASO_HORAS) != 0:
        raise ValueError(f"{campo} van en pasos de 0,25 (recibido: {v})")
    return v


# ===================== ACTIVIDADES =====================

class ActivityCreate(BaseModel):
    name: str


class ActivityUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class ActivityResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool
    created_at: datetime
    # Cuántos proyectos la usan: es lo que decide si se puede borrar (H-D4) y lo
    # que la pantalla necesita para explicar por qué no.
    projects_count: int = 0
    # Si tiene horas registradas. Con horas NO se borra nunca, ni siendo admin.
    has_entries: bool = False

    model_config = ConfigDict(from_attributes=True)


# ===================== PROYECTOS =====================

class ProjectActivityInput(BaseModel):
    activity_id: UUID
    estimated_hours: Decimal

    @field_validator("estimated_hours")
    @classmethod
    def _paso(cls, v):
        return validar_paso(v, "Las horas estimadas")


class ProjectCreate(BaseModel):
    client_id: UUID
    name: str
    description: Optional[str] = None
    # §3: al crear hace falta al menos una actividad con horas.
    activities: List[ProjectActivityInput]

    @field_validator("activities")
    @classmethod
    def _al_menos_una(cls, v):
        if not v:
            raise ValueError("Un proyecto necesita al menos una actividad con horas estimadas")
        vistas = {a.activity_id for a in v}
        if len(vistas) != len(v):
            raise ValueError("Hay una actividad repetida en la lista")
        return v


class ProjectUpdate(BaseModel):
    """Editar el proyecto. Las actividades se gestionan por su propio endpoint,
    para que cada cambio de estimación escriba su historial (H-D11)."""
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectActivityResponse(BaseModel):
    activity_id: UUID
    activity_name: str
    estimated_hours: Decimal
    # H1.3: `consumed_hours` es 0 mientras no exista el registro de horas (H2).
    # El contrato se fija YA para que H2 y H3 no tengan que cambiarlo.
    consumed_hours: Decimal = Decimal("0")
    remaining_hours: Decimal = Decimal("0")
    # §4.2.4: marca de exceso, para pintarla en color sin recalcular en la pantalla.
    over_estimate: bool = False


class ProjectResponse(BaseModel):
    id: UUID
    client_id: UUID
    client_name: str = ""
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    total_estimated_hours: Decimal = Decimal("0")
    total_consumed_hours: Decimal = Decimal("0")
    activities_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailResponse(ProjectResponse):
    activities: List[ProjectActivityResponse] = []


class ProjectActivityUpsert(BaseModel):
    """Añadir una actividad al proyecto o cambiar su estimación (H-D11/H-D12)."""
    activity_id: UUID
    estimated_hours: Decimal

    @field_validator("estimated_hours")
    @classmethod
    def _paso(cls, v):
        return validar_paso(v, "Las horas estimadas")


class ProjectActivityChangeResponse(BaseModel):
    id: UUID
    activity_id: UUID
    activity_name: str = ""
    previous_hours: Optional[Decimal] = None
    new_hours: Optional[Decimal] = None
    change_type: str
    changed_by_name: str = ""
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)
