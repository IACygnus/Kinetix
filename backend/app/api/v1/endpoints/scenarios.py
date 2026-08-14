# backend/app/api/v1/endpoints/scenarios.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.db.models.scenario import Scenario

router = APIRouter()

# Configuraciones predefinidas por tipo de prueba
SCENARIO_TEMPLATES = {
    "load": {
        "initial_users": 1,
        "step_users": 5,
        "step_duration_sec": 30,
        "hold_duration_sec": 600,
        "max_users": 50,
        "ramp_down_sec": 60,
        "total_duration_sec": 1800,
        "think_time_ms": 1000,
    },
    "stress": {
        "initial_users": 5,
        "step_users": 10,
        "step_duration_sec": 60,
        "hold_duration_sec": 300,
        "max_users": 200,
        "ramp_down_sec": 120,
        "total_duration_sec": 3600,
        "think_time_ms": 500,
    },
    "spike": {
        "initial_users": 10,
        "step_users": 50,
        "step_duration_sec": 5,
        "hold_duration_sec": 120,
        "max_users": 100,
        "ramp_down_sec": 30,
        "total_duration_sec": 1200,
        "think_time_ms": 500,
    },
    "soak": {
        "initial_users": 20,
        "step_users": 5,
        "step_duration_sec": 300,
        "hold_duration_sec": 7200,
        "max_users": 50,
        "ramp_down_sec": 300,
        "total_duration_sec": 14400,
        "think_time_ms": 2000,
    },
}


class ScenarioCreateRequest(BaseModel):
    name: str
    script_id: int
    test_type: str = "load"
    thread_group_config: Optional[Dict[str, Any]] = None
    acceptance_criteria: Optional[Dict[str, Any]] = None


class ScenarioResponse(BaseModel):
    id: int
    name: str
    script_id: int
    test_type: str
    thread_group_config: dict
    acceptance_criteria: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/templates", response_model=Dict[str, Any])
async def get_templates():
    """Retornar las plantillas predefinidas de escenarios."""
    return SCENARIO_TEMPLATES


@router.get("/", response_model=List[ScenarioResponse])
async def list_scenarios(
    script_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = select(Scenario)
    if script_id:
        query = query.where(Scenario.script_id == script_id)
    result = await db.execute(query.order_by(Scenario.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    payload: ScenarioCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Si no se provee config manual, usar la plantilla del tipo seleccionado
    config = payload.thread_group_config
    if not config:
        config = SCENARIO_TEMPLATES.get(payload.test_type, SCENARIO_TEMPLATES["load"]).copy()

    scenario = Scenario(
        name=payload.name,
        script_id=payload.script_id,
        test_type=payload.test_type,
        thread_group_config=config,
        acceptance_criteria=payload.acceptance_criteria or {},
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: int,
    db: AsyncSession = Depends(get_db),
    # SEC-2: borrar es exclusivo de admin en toda la plataforma.
    current_user=Depends(require_role(["admin"])),
):
    result = await db.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")
    await db.delete(scenario)
    await db.commit()
