"""
Endpoints del Dashboard Home - KPIs y estadisticas - v2.0
Role-based filtering: admin sees all, analyst only assigned clients.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
import logging

from app.db.session import get_db
from app.db.models.test import TestExecution
from app.db.models.user import User
from app.db.models.client import UserClient
from app.core.security import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)


class RecentReport(BaseModel):
    id: UUID
    name: str
    jtl_filename: str
    total_requests: int
    error_rate: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardStats(BaseModel):
    total_reports: int
    total_users: int
    last_analysis: Optional[datetime] = None
    recent_reports: List[RecentReport]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener estadisticas para el Dashboard Home.
    Admin ve todo; analyst/viewer solo reportes de clientes asignados.
    """
    if current_user.role == 'admin':
        # Admin: full access
        count_query = select(func.count(TestExecution.id))
        last_query = select(TestExecution.created_at).order_by(desc(TestExecution.created_at)).limit(1)
        recent_query = select(TestExecution).order_by(desc(TestExecution.created_at)).limit(10)

        users_result = await db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        total_users = users_result.scalar() or 0
    else:
        # Non-admin: filter by assigned clients
        assigned = await db.execute(
            select(UserClient.client_id).where(UserClient.user_id == current_user.id)
        )
        client_ids = [row[0] for row in assigned.fetchall()]

        if not client_ids:
            return DashboardStats(
                total_reports=0,
                total_users=0,
                last_analysis=None,
                recent_reports=[],
            )

        count_query = select(func.count(TestExecution.id)).where(
            TestExecution.client_id.in_(client_ids)
        )
        last_query = (
            select(TestExecution.created_at)
            .where(TestExecution.client_id.in_(client_ids))
            .order_by(desc(TestExecution.created_at))
            .limit(1)
        )
        recent_query = (
            select(TestExecution)
            .where(TestExecution.client_id.in_(client_ids))
            .order_by(desc(TestExecution.created_at))
            .limit(10)
        )
        total_users = 0  # Non-admin doesn't see user count

    # Execute queries
    result = await db.execute(count_query)
    total_reports = result.scalar() or 0

    result = await db.execute(last_query)
    last_analysis = result.scalar_one_or_none()

    result = await db.execute(recent_query)
    recent_executions = result.scalars().all()

    recent_reports = [
        RecentReport(
            id=exec.id,
            name=exec.name,
            jtl_filename=exec.jtl_filename,
            total_requests=exec.total_requests,
            error_rate=exec.error_rate,
            created_at=exec.created_at,
        )
        for exec in recent_executions
    ]

    return DashboardStats(
        total_reports=total_reports,
        total_users=total_users,
        last_analysis=last_analysis,
        recent_reports=recent_reports,
    )
