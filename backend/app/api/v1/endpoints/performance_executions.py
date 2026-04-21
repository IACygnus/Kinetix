# backend/app/api/v1/endpoints/performance_executions.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.performance_execution import PerformanceExecution

router = APIRouter()


class ExecutionResponse(BaseModel):
    id: int
    scenario_id: int
    user_id: UUID
    status: str
    jtl_file_path: Optional[str]
    output_filename: Optional[str]
    summary_metrics: Optional[dict]
    scenario_snapshot: Optional[dict]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ExecutionResponse])
async def list_executions(
    scenario_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = select(PerformanceExecution).where(
        PerformanceExecution.user_id == current_user.id
    )
    if scenario_id:
        query = query.where(PerformanceExecution.scenario_id == scenario_id)
    result = await db.execute(query.order_by(PerformanceExecution.created_at.desc()))
    return result.scalars().all()


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")
    return execution
