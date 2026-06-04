# backend/app/api/v1/endpoints/performance_executions.py
import os
import shutil
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.db.models.performance_execution import PerformanceExecution
from app.db.models.test import TestExecution
from app.db.models.user import User
from app.services.ai.analysis_pipeline import run_jtl_analysis_pipeline
from app.services.engine.execution_tracker import execution_tracker
from app.services.engine.jmeter_runner import cancel_jmeter_process
from app.services.engine.listeners_state_service import (
    compute_listeners_state,
    cleanup_execution_cache,
)

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


# ---------------------------------------------------------------------------
# Sprint 2.5d.1 — Live metrics (polling) + stop de ejecuciones FULL
# ---------------------------------------------------------------------------


@router.get("/{execution_id}/live-metrics")
async def get_live_metrics(
    execution_id: int,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Metricas en vivo de una ejecucion FULL (polling cada ~2s del frontend).

    Lee primero el tracker en memoria (ejecucion en curso). Si no esta, cae a la
    DB para devolver el estado y las metricas finales persistidas.
    """
    tracker_data = execution_tracker.get(execution_id)
    if tracker_data:
        return {
            "execution_id": execution_id,
            "status": tracker_data.get("status"),
            "elapsed_sec": tracker_data.get("elapsed_sec", 0),
            "metrics": tracker_data.get("latest_metrics", {}),
        }

    result = await db.execute(
        select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
    )
    perf_exec = result.scalar_one_or_none()
    if not perf_exec:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")
    return {
        "execution_id": execution_id,
        "status": perf_exec.status,
        "elapsed_sec": 0,
        "metrics": perf_exec.summary_metrics or {},
    }


@router.get("/{execution_id}/listeners-state")
async def get_listeners_state(
    execution_id: int,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Estado en vivo de todos los listeners de una ejecucion FULL.

    Lee primero el tracker en memoria (ejecucion en curso); si no esta, cae a la
    DB (ejecucion terminada). Devuelve samples_tail, per_sampler_stats y
    time_buckets que los renderers del frontend (2.6c-g) consumiran.
    """
    tracker_data = execution_tracker.get(execution_id)

    if tracker_data:
        jtl_path = tracker_data.get("jtl_path")
        start_time = tracker_data.get("start_time", time.time())
        elapsed_sec = tracker_data.get("elapsed_sec", 0)
        status = tracker_data.get("status", "running")
    else:
        result = await db.execute(
            select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
        )
        perf_exec = result.scalar_one_or_none()
        if not perf_exec:
            raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

        if str(current_user.role).lower() != "admin" and perf_exec.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Sin acceso")

        jtl_path = perf_exec.jtl_file_path
        start_time = perf_exec.started_at.timestamp() if perf_exec.started_at else time.time()
        if perf_exec.completed_at and perf_exec.started_at:
            elapsed_sec = (perf_exec.completed_at - perf_exec.started_at).total_seconds()
        else:
            elapsed_sec = 0
        status = perf_exec.status

    if not jtl_path:
        raise HTTPException(status_code=400, detail="JTL no disponible para esta ejecucion")

    return compute_listeners_state(
        execution_id=execution_id,
        jtl_path=jtl_path,
        start_time=start_time,
        elapsed_sec=elapsed_sec,
        status=status,
    )


@router.delete("/{execution_id}/listeners-state-cache")
async def clear_listeners_cache(
    execution_id: int,
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Limpia el cache de listeners de una ejecucion.

    El frontend lo llama al cerrar el drawer (Opcion R hibrida: cache vive
    mientras el drawer este abierto, se libera al cerrar).
    """
    cleanup_execution_cache(execution_id)
    return {"execution_id": execution_id, "cache_cleared": True}


@router.post("/{execution_id}/stop")
async def stop_execution(
    execution_id: int,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Cancela una ejecucion FULL en curso (SIGTERM al proceso JMeter)."""
    result = await db.execute(
        select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
    )
    perf_exec = result.scalar_one_or_none()
    if not perf_exec:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    tracker_data = execution_tracker.get(execution_id)
    if not tracker_data and perf_exec.status in (
        "completed", "error", "cancelled"
    ):
        raise HTTPException(
            status_code=400,
            detail=f"La ejecucion ya termino (status={perf_exec.status})",
        )

    # Marcar stopping en el tracker para que el background task cierre como cancelled.
    execution_tracker.update(execution_id, status="stopping")

    killed = False
    pid = (tracker_data or {}).get("pid")
    if pid:
        killed = cancel_jmeter_process(pid)

    perf_exec.status = "cancelled"
    perf_exec.completed_at = datetime.utcnow()
    await db.commit()

    return {
        "execution_id": execution_id,
        "status": "cancelled",
        "process_signaled": killed,
    }


# ---------------------------------------------------------------------------
# Sprint 2.5d.2 — Analisis IA del JTL persistido (reusa el pipeline de /upload)
# ---------------------------------------------------------------------------


@router.post("/{execution_id}/analyze-with-ai")
async def analyze_execution_with_ai(
    execution_id: int,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Corre el pipeline IA publico sobre el JTL persistido de una ejecucion FULL.

    Crea un ``TestExecution`` consumible por el Dashboard de analisis (la misma
    tabla y campos que /upload). Devuelve el id + la URL del dashboard.
    """
    res = await db.execute(
        select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
    )
    perf_exec = res.scalar_one_or_none()
    if not perf_exec:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    if current_user.role != "admin" and perf_exec.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sin acceso")

    if perf_exec.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"La ejecucion esta en estado '{perf_exec.status}'. Solo se "
                   f"pueden analizar ejecuciones 'completed'.",
        )

    jtl_path = perf_exec.jtl_file_path
    if not jtl_path or not os.path.exists(jtl_path):
        raise HTTPException(status_code=400, detail=f"JTL no encontrado en disco: {jtl_path}")
    if os.path.getsize(jtl_path) < 100:
        raise HTTPException(status_code=400, detail="JTL vacio o demasiado pequeno")

    snapshot = perf_exec.scenario_snapshot or {}
    design_name = snapshot.get("design_name", "Ejecucion Editor IA")

    # El endpoint de charts del Dashboard busca el JTL con un glob NO recursivo en
    # /app/uploads ("*{jtl_filename}"). El JTL de una ejecucion FULL vive en
    # /app/uploads/jtl_results/{id}/, fuera de ese glob. Copiamos una copia con
    # nombre unico a /app/uploads para que el Dashboard (detalle + charts) funcione.
    dashboard_jtl_name = f"aiexec_{execution_id}_{os.path.basename(jtl_path)}"
    try:
        shutil.copy2(jtl_path, os.path.join("/app/uploads", dashboard_jtl_name))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo preparar el JTL para el dashboard: {e}",
        )

    test_execution = TestExecution(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=f"{design_name} - exec#{execution_id}",
        description=f"Analisis IA de la ejecucion #{execution_id} del Editor IA",
        client="Editor IA",
        project=design_name,
        test_type="load",
        jtl_filename=dashboard_jtl_name,
        start_time=perf_exec.started_at,
        end_time=perf_exec.completed_at,
    )

    try:
        test_execution = await run_jtl_analysis_pipeline(
            test_execution=test_execution,
            jtl_path=jtl_path,
            db=db,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en pipeline IA: {e}")

    db.add(test_execution)
    await db.commit()
    await db.refresh(test_execution)

    return {
        "test_execution_id": str(test_execution.id),
        "performance_execution_id": execution_id,
        # HF13: la ruta del detalle del reporte en el frontend es
        # /performance/report/:executionId (ReportWrapper -> Dashboard). La antigua
        # /dashboard/{id} no existia como ruta y caia al catch-all (lista).
        "dashboard_url": f"/performance/report/{test_execution.id}",
        "status": "ok",
    }
