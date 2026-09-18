"""Schemas del MÓDULO DE HORAS (ETAPA H1.3).

Mismo estilo que `schemas/client.py`: `XCreate` / `XUpdate` / `XResponse` con
`ConfigDict(from_attributes=True)`.

La validación de las horas en pasos de 0,25 (H-D8) vive aquí además de en la
base: el schema devuelve un **422 con mensaje legible** y la restricción de la
base es la última red, que devolvería un 500 feo si llegara a saltar.
"""
from datetime import date, datetime
from datetime import date as DateOnly
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
    # §4.2.4: marca de desfase, para pintarla en color sin recalcular en la
    # pantalla. El nombre interno se conserva (H-D27): lo que cambia es el texto.
    over_estimate: bool = False
    # ETAPA H2b (§5.1): el mismo estado por actividad, para ver CUÁL es la que
    # está tirando del proyecto, no solo que el proyecto va mal.
    consumed_pct: Decimal = Decimal("0")
    overrun_status: str = "en_rango"
    overrun_hours: Decimal = Decimal("0")
    overrun_label: str = "En rango"


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
    # ETAPA H2b (§5.1). Campos AÑADIDOS: el contrato que cerraron H1 y H2 no
    # cambia, así que nada de lo que ya consumía esta respuesta se entera.
    consumed_pct: Decimal = Decimal("0")
    overrun_status: str = "en_rango"      # en_rango | por_agotarse | desfasado
    overrun_hours: Decimal = Decimal("0")
    overrun_label: str = "En rango"

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


# ===================== REGISTRO DE HORAS (ETAPA H2) =====================

class TimeEntryCreate(BaseModel):
    """§1.1. `user_id` solo lo manda el admin al registrar por otra persona
    (H-D13); si no viene, son las horas de quien registra."""
    user_id: Optional[UUID] = None
    date: DateOnly
    project_id: UUID
    activity_id: UUID
    hours: Decimal
    billable: bool
    overtime: bool = False
    notes: Optional[str] = None

    @field_validator("hours")
    @classmethod
    def _paso(cls, v):
        return validar_paso(v)

    @field_validator("date")
    @classmethod
    def _sin_futuro(cls, v):
        """H-D21: hacia atrás sin límite —§4.2.3 habla del olvido—, pero no se
        adelantan horas que todavía no se han trabajado."""
        if v > date.today():
            raise ValueError("No se pueden registrar horas con fecha futura")
        return v


class TimeEntryUpdate(BaseModel):
    date: Optional[DateOnly] = None
    project_id: Optional[UUID] = None
    activity_id: Optional[UUID] = None
    hours: Optional[Decimal] = None
    billable: Optional[bool] = None
    overtime: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("hours")
    @classmethod
    def _paso(cls, v):
        return validar_paso(v) if v is not None else v

    @field_validator("date")
    @classmethod
    def _sin_futuro(cls, v):
        if v is not None and v > date.today():
            raise ValueError("No se pueden registrar horas con fecha futura")
        return v


class TimeEntryResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str = ""
    created_by: Optional[UUID] = None
    created_by_name: str = ""
    date: DateOnly
    client_id: Optional[UUID] = None
    client_name: str = ""
    project_id: UUID
    project_name: str = ""
    project_status: str = "activo"
    activity_id: UUID
    activity_name: str = ""
    hours: Decimal
    billable: bool
    overtime: bool
    notes: Optional[str] = None
    source: str = "manual"
    # H-D16: si esta actividad, en este proyecto, ya pasó de lo estimado. Se
    # calcula en el backend para que la pantalla no sume por su cuenta.
    over_estimate: bool = False

    model_config = ConfigDict(from_attributes=True)


class DiaResponse(BaseModel):
    """Un día ya resuelto por `services/horas/calendario.py`. La pantalla lo
    pinta tal cual: no recalcula ni la jornada ni el 'incompleto'."""
    date: DateOnly
    expected_hours: Decimal
    ordinary_hours: Decimal
    overtime_hours: Decimal
    total_hours: Decimal
    is_holiday: bool = False
    is_absence: bool = False
    non_working_reason: str = ""
    incomplete: bool = False
    missing_hours: Decimal = Decimal("0")
    entries: List[TimeEntryResponse] = []


class WeekResponse(BaseModel):
    user_id: UUID
    user_name: str = ""
    week_start: DateOnly
    week_end: DateOnly
    days: List[DiaResponse] = []
    total_expected: Decimal = Decimal("0")
    total_ordinary: Decimal = Decimal("0")
    total_overtime: Decimal = Decimal("0")


class MonthDayResponse(BaseModel):
    """Una casilla del calendario (ETAPA H2b, §4.1).

    Todo viene resuelto: la pantalla pinta, no calcula.
    """
    date: DateOnly
    expected_hours: Decimal
    ordinary_hours: Decimal
    overtime_hours: Decimal
    total_hours: Decimal
    is_holiday: bool = False
    is_absence: bool = False
    non_working_reason: str = ""
    incomplete: bool = False
    missing_hours: Decimal = Decimal("0")
    entries_count: int = 0
    # Si alguno de sus registros cae en una actividad desfasada (H-D27).
    has_over_estimate: bool = False


class MonthResponse(BaseModel):
    user_id: UUID
    user_name: str = ""
    year: int
    month: int
    first_day: DateOnly
    last_day: DateOnly
    days: List[MonthDayResponse] = []
    total_expected: Decimal = Decimal("0")
    total_ordinary: Decimal = Decimal("0")
    total_overtime: Decimal = Decimal("0")
    pending_days: int = 0


class PendingDayResponse(BaseModel):
    date: DateOnly
    expected_hours: Decimal
    ordinary_hours: Decimal
    missing_hours: Decimal
    # El lunes de su semana: es lo que el enlace de H-D18 necesita para abrir la
    # vista con ese día enfocado.
    week_start: DateOnly


class ActivityAvailabilityResponse(BaseModel):
    """Lo que necesita el aviso de exceso (H-D16) sin pedir el detalle entero."""
    activity_id: UUID
    activity_name: str
    estimated_hours: Decimal
    consumed_hours: Decimal
    remaining_hours: Decimal
    over_estimate: bool


# ===================== CONSULTA (ETAPA H3, §5) =====================

class ConsultaPersona(BaseModel):
    """Quién registró y cuántas horas, dentro del rango consultado (H-D32)."""
    user_id: UUID
    user_name: str = ""
    hours: Decimal = Decimal("0")
    billable_hours: Decimal = Decimal("0")
    overtime_hours: Decimal = Decimal("0")
    entries_count: int = 0


class ConsultaProyecto(BaseModel):
    """Un proyecto en la consulta.

    Ojo a las dos cifras de horas, que **no son la misma** y por eso van con
    nombres distintos:

    - `hours_in_range` es lo registrado **dentro del rango consultado**;
    - `consumed_hours` es todo lo que lleva el proyecto **desde siempre**, que es
      contra lo que se mide el desfase.

    Mezclarlas daría un proyecto «en rango» solo por haber consultado una semana
    tranquila, y contradiría a la pantalla de Proyectos.
    """
    project_id: UUID
    project_name: str = ""
    client_id: UUID
    client_name: str = ""
    status: str = "activo"
    estimated_hours: Decimal = Decimal("0")
    consumed_hours: Decimal = Decimal("0")
    remaining_hours: Decimal = Decimal("0")
    consumed_pct: Decimal = Decimal("0")
    overrun_status: str = "en_rango"
    overrun_hours: Decimal = Decimal("0")
    overrun_label: str = "En rango"
    hours_in_range: Decimal = Decimal("0")
    overtime_in_range: Decimal = Decimal("0")
    entries_in_range: int = 0
    people: List[ConsultaPersona] = []


class ConsultaResponse(BaseModel):
    desde: DateOnly
    hasta: DateOnly
    projects: List[ConsultaProyecto] = []
    total_hours: Decimal = Decimal("0")
    total_overtime: Decimal = Decimal("0")
    projects_count: int = 0
    people_count: int = 0
    # §5.1: cuántos proyectos están desfasados, para el aviso de arriba.
    overrun_count: int = 0


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
