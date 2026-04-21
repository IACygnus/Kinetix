# backend/app/api/v1/endpoints/executions.py
"""
Endpoints de ejecución del motor de performance testing.

Sprint 2: Smoke Test (1 VU, 1 iteración) + AI Correlation + AI Debug
Sprint 3: Load/Stress/Spike/Soak (multiples VUs, stepping controller)
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path

from app.db.session import get_db, AsyncSessionLocal
from app.core.security import get_current_user
from app.db.models.script_design import ScriptDesign
from app.db.models.scenario import Scenario
from app.db.models.performance_execution import PerformanceExecution
from app.db.models.test import TestExecution
from app.db.models.client import Client
from app.services.engine.stepping_controller import SteppingController
from app.services.engine.execution_manager import execution_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class SmokeTestRequest(BaseModel):
    script_id: Optional[int] = None
    script_model: Optional[dict] = None   # tiene prioridad sobre script_id
    scenario_id: Optional[int] = None


class SmokeTestResponse(BaseModel):
    execution_id: int
    success: bool
    total_requests: int
    passed_requests: int
    failed_requests: int
    duration_ms: int
    jtl_file_path: str
    request_details: list
    unresolved_variables: list
    error_message: str


class AICorrelateRequest(BaseModel):
    script_id: int


class AICorrelateResponse(BaseModel):
    correlations: list
    analysis_summary: str
    error: Optional[str] = None


class AIDebugRequest(BaseModel):
    script_id: int


class AIDebugResponse(BaseModel):
    requests_to_remove: list
    reasons: dict
    analysis_summary: str
    error: Optional[str] = None


# Sprint 3 models
class StartExecutionRequest(BaseModel):
    scenario_id: int
    script_id: int


class StartExecutionResponse(BaseModel):
    execution_id: int
    status: str
    jtl_file_path: str
    ws_url: str


class ExecutionControlRequest(BaseModel):
    action: str  # "stop" | "pause" | "resume"


class ExecutionStatusResponse(BaseModel):
    execution_id: int
    status: str
    active_vus: int
    total_requests: int
    error_rate_percent: float
    avg_response_time_ms: float
    started_at: Optional[str] = None
    duration_sec: Optional[float] = None


# ─── Smoke Test (Sprint 2) ────────────────────────────────────────────────────

@router.post("/smoke-test", response_model=SmokeTestResponse)
async def run_smoke_test_endpoint(
    payload: SmokeTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Ejecutar smoke test: 1 VU, 1 iteración completa del script.
    Prioridad: script_model del payload > script_model de la BD.
    """
    # Resolver script_model: prioridad al enviado en el payload
    script = None
    script_model_to_run = None
    script_name = "Script"

    if payload.script_model:
        # El frontend envía el modelo actual del editor (puede no estar guardado)
        script_model_to_run = payload.script_model
        # Intentar cargar el script de BD para metadata (client, name)
        if payload.script_id:
            script_result = await db.execute(
                select(ScriptDesign).where(ScriptDesign.id == payload.script_id)
            )
            script = script_result.scalar_one_or_none()
            if script:
                script_name = script.name
    elif payload.script_id:
        script_result = await db.execute(
            select(ScriptDesign).where(ScriptDesign.id == payload.script_id)
        )
        script = script_result.scalar_one_or_none()
        if not script:
            raise HTTPException(status_code=404, detail="Script no encontrado")
        script_model_to_run = script.script_model
        script_name = script.name
    else:
        raise HTTPException(status_code=400, detail="Debe enviar script_id o script_model")

    requests_count = len(script_model_to_run.get("requests", []))
    if requests_count == 0:
        raise HTTPException(status_code=422, detail="El script no tiene requests definidos")

    client_name = "cliente"
    if script and script.client_id:
        client_result = await db.execute(
            select(Client).where(Client.id == script.client_id)
        )
        client = client_result.scalar_one_or_none()
        if client:
            client_name = client.name

    # Necesitamos un script_id válido para el Scenario (FK NOT NULL)
    # Si no hay script guardado, guardar primero un script temporal
    script_id_for_scenario = payload.script_id or (script.id if script else None)
    if not script_id_for_scenario:
        # Crear script temporal para mantener la integridad referencial
        temp_script = ScriptDesign(
            name=f"Smoke Temp — {script_name}",
            user_id=current_user.id,
            script_model=script_model_to_run,
            script_type="api",
            origin="manual",
        )
        db.add(temp_script)
        await db.flush()
        script_id_for_scenario = temp_script.id

    scenario_id = payload.scenario_id
    if not scenario_id:
        smoke_scenario = Scenario(
            name=f"Smoke Test — {script_name}",
            script_id=script_id_for_scenario,
            test_type="smoke",
            thread_group_config={
                "initial_users": 1,
                "max_users": 1,
                "iterations": 1,
            },
        )
        db.add(smoke_scenario)
        await db.flush()
        scenario_id = smoke_scenario.id

    execution = PerformanceExecution(
        scenario_id=scenario_id,
        user_id=current_user.id,
        status="running",
        started_at=datetime.utcnow(),
        scenario_snapshot={
            "type": "smoke_test",
            "script_id": payload.script_id,
            "script_name": script_name,
        }
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    from app.services.engine.smoke_test import run_smoke_test as _run_smoke_test

    smoke_result = await _run_smoke_test(
        script_model=script_model_to_run,
        execution_id=execution.id,
        client_name=client_name,
        project_name=script_name,
    )

    execution.status = "completed" if smoke_result.success else "error"
    execution.completed_at = datetime.utcnow()
    execution.jtl_file_path = smoke_result.jtl_file_path
    execution.output_filename = smoke_result.jtl_file_path.split("/")[-1] if smoke_result.jtl_file_path else None
    execution.error_message = smoke_result.error_message or None
    execution.summary_metrics = {
        "smoke_test": True,
        "total_requests": smoke_result.total_requests,
        "passed": smoke_result.passed_requests,
        "failed": smoke_result.failed_requests,
        "duration_ms": smoke_result.duration_ms,
    }
    await db.commit()

    return SmokeTestResponse(
        execution_id=execution.id,
        **smoke_result.to_dict()
    )


# ─── AI Correlation (Sprint 2) ────────────────────────────────────────────────

@router.post("/ai-correlate", response_model=AICorrelateResponse)
async def ai_correlate(
    payload: AICorrelateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Analizar el script con IA y sugerir extractores de correlación."""
    script_result = await db.execute(
        select(ScriptDesign).where(ScriptDesign.id == payload.script_id)
    )
    script = script_result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script no encontrado")

    requests_count = len(script.script_model.get("requests", []))
    if requests_count == 0:
        raise HTTPException(status_code=422, detail="El script no tiene requests para analizar")

    from app.services.engine.ai_correlation import AICorrelationService
    svc = AICorrelationService()
    result = await svc.correlate(script.script_model)

    return AICorrelateResponse(**result)


@router.post("/ai-debug", response_model=AIDebugResponse)
async def ai_debug(
    payload: AIDebugRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Analizar el script con IA y detectar recursos estáticos/duplicados."""
    script_result = await db.execute(
        select(ScriptDesign).where(ScriptDesign.id == payload.script_id)
    )
    script = script_result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script no encontrado")

    from app.services.engine.ai_correlation import AICorrelationService
    svc = AICorrelationService()
    result = await svc.debug_script(script.script_model)

    return AIDebugResponse(**result)


# ─── Start Full Load Test (Sprint 3) ──────────────────────────────────────────

@router.post("/start", response_model=StartExecutionResponse)
async def start_execution(
    payload: StartExecutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Lanzar una ejecución de load testing completa en background.

    Crea el registro en DB, lanza el SteppingController como background task,
    y retorna inmediatamente con el execution_id y la URL del WebSocket.
    """
    scenario_result = await db.execute(
        select(Scenario).where(Scenario.id == payload.scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario no encontrado")

    script_result = await db.execute(
        select(ScriptDesign).where(ScriptDesign.id == payload.script_id)
    )
    script = script_result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script no encontrado")

    if not script.script_model.get("requests"):
        raise HTTPException(status_code=422, detail="El script no tiene requests definidos")

    # Obtener nombre de cliente para JTL filename
    client_name = "cliente"
    if script.client_id:
        client_result = await db.execute(
            select(Client).where(Client.id == script.client_id)
        )
        client = client_result.scalar_one_or_none()
        if client:
            client_name = client.name

    # Crear registro de ejecución
    execution = PerformanceExecution(
        scenario_id=payload.scenario_id,
        user_id=current_user.id,
        status="running",
        started_at=datetime.utcnow(),
        scenario_snapshot={
            "type": scenario.test_type,
            "script_id": payload.script_id,
            "script_name": script.name,
            "scenario_name": scenario.name,
            "thread_group_config": scenario.thread_group_config,
        }
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Construir ruta JTL
    from app.services.engine.jtl_writer import JTLWriter
    jtl_path = JTLWriter.build_filepath(client_name, script.name, execution.id)

    execution.jtl_file_path = jtl_path
    execution.output_filename = jtl_path.split("/")[-1]
    await db.commit()

    # Crear SteppingController
    thread_group_config = scenario.thread_group_config or {}
    controller = SteppingController(
        execution_id=execution.id,
        script_model=script.script_model,
        scenario_config=thread_group_config,
        jtl_path=jtl_path,
        client_name=client_name,
    )

    execution_manager.register(execution.id, controller)

    # Capture execution_id for the background task closure
    exec_id = execution.id

    async def run_and_cleanup():
        try:
            metrics = await controller.run()
            # Use independent DB session for background update
            async with AsyncSessionLocal() as session:
                exec_result = await session.execute(
                    select(PerformanceExecution).where(PerformanceExecution.id == exec_id)
                )
                exc = exec_result.scalar_one_or_none()
                if exc:
                    exc.status = "completed" if controller.status == "completed" else "error"
                    exc.completed_at = datetime.utcnow()
                    exc.summary_metrics = metrics.get_summary()
                    exc.error_message = controller.error_message or None
                    await session.commit()
        except Exception as e:
            logger.error(f"Background execution {exec_id} failed: {e}")
            try:
                async with AsyncSessionLocal() as session:
                    exec_result = await session.execute(
                        select(PerformanceExecution).where(PerformanceExecution.id == exec_id)
                    )
                    exc = exec_result.scalar_one_or_none()
                    if exc:
                        exc.status = "error"
                        exc.completed_at = datetime.utcnow()
                        exc.error_message = str(e)[:500]
                        await session.commit()
            except Exception:
                pass
        finally:
            execution_manager.unregister(exec_id)

    background_tasks.add_task(run_and_cleanup)

    return StartExecutionResponse(
        execution_id=execution.id,
        status="running",
        jtl_file_path=jtl_path,
        ws_url=f"/api/v1/ws/executions/{execution.id}/metrics",
    )


# ─── Execution Control (Sprint 3) ─────────────────────────────────────────────

@router.post("/{execution_id}/control")
async def control_execution(
    execution_id: int,
    payload: ExecutionControlRequest,
    current_user=Depends(get_current_user)
):
    """Controlar una ejecución activa: stop | pause | resume."""
    controller = execution_manager.get(execution_id)
    if not controller:
        raise HTTPException(
            status_code=404,
            detail=f"Ejecución {execution_id} no encontrada o ya finalizada"
        )

    action = payload.action.lower()
    if action == "stop":
        await controller.stop()
        return {"execution_id": execution_id, "action": "stop", "status": "stopping"}
    elif action == "pause":
        controller.pause()
        return {"execution_id": execution_id, "action": "pause", "status": "paused"}
    elif action == "resume":
        controller.resume()
        return {"execution_id": execution_id, "action": "resume", "status": "running"}
    else:
        raise HTTPException(status_code=422, detail=f"Acción no válida: {action}. Use stop, pause o resume")


# ─── Execution History (Sprint 3) — BEFORE /{execution_id} routes ─────────────

@router.get("/history")
async def list_execution_history(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Historial de ejecuciones del usuario actual."""
    result = await db.execute(
        select(PerformanceExecution)
        .where(PerformanceExecution.user_id == current_user.id)
        .order_by(desc(PerformanceExecution.started_at))
        .limit(limit)
        .offset(offset)
    )
    executions = result.scalars().all()

    items = []
    for exc in executions:
        summary = exc.summary_metrics or {}
        is_active = execution_manager.get(exc.id) is not None

        items.append({
            "id": exc.id,
            "status": exc.status,
            "is_active": is_active,
            "started_at": exc.started_at.isoformat() if exc.started_at else None,
            "completed_at": exc.completed_at.isoformat() if exc.completed_at else None,
            "scenario_name": exc.scenario_snapshot.get("scenario_name", "") if exc.scenario_snapshot else "",
            "script_name": exc.scenario_snapshot.get("script_name", "") if exc.scenario_snapshot else "",
            "test_type": exc.scenario_snapshot.get("type", "") if exc.scenario_snapshot else "",
            "total_requests": summary.get("total_requests", 0),
            "error_rate_percent": summary.get("error_rate_percent", 0.0),
            "avg_response_time_ms": summary.get("avg_response_time_ms", 0.0),
            "duration_sec": summary.get("duration_sec"),
            "jtl_file_path": exc.jtl_file_path,
            "output_filename": exc.output_filename,
        })

    return {"items": items, "total": len(items), "has_more": len(items) == limit}


# ─── Execution Status (Sprint 3) ──────────────────────────────────────────────

@router.get("/{execution_id}/status", response_model=ExecutionStatusResponse)
async def get_execution_status(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Estado actual de una ejecución (activa o terminada)."""
    controller = execution_manager.get(execution_id)

    if controller:
        summary = controller.metrics_collector.get_summary()
        started_at = controller.started_at.isoformat() if controller.started_at else None
        duration_sec = (datetime.utcnow() - controller.started_at).total_seconds() if controller.started_at else None
        return ExecutionStatusResponse(
            execution_id=execution_id,
            status=controller.status,
            active_vus=controller.active_vu_count,
            total_requests=summary.get("total_requests", 0),
            error_rate_percent=summary.get("error_rate_percent", 0.0),
            avg_response_time_ms=summary.get("avg_response_time_ms", 0.0),
            started_at=started_at,
            duration_sec=duration_sec,
        )

    exec_result = await db.execute(
        select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
    )
    execution = exec_result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")

    summary = execution.summary_metrics or {}
    started_at = execution.started_at.isoformat() if execution.started_at else None
    duration_sec = None
    if execution.started_at and execution.completed_at:
        duration_sec = (execution.completed_at - execution.started_at).total_seconds()

    return ExecutionStatusResponse(
        execution_id=execution_id,
        status=execution.status,
        active_vus=0,
        total_requests=summary.get("total_requests", 0),
        error_rate_percent=summary.get("error_rate_percent", 0.0),
        avg_response_time_ms=summary.get("avg_response_time_ms", 0.0),
        started_at=started_at,
        duration_sec=duration_sec,
    )


# ─── JTL Download (Sprint 2) ─────────────────────────────────────────────────

@router.get("/{execution_id}/download-jtl")
async def download_jtl(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Descargar el archivo JTL de una ejecución completada."""
    exec_result = await db.execute(
        select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
    )
    execution = exec_result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")

    if not execution.jtl_file_path:
        raise HTTPException(status_code=404, detail="No hay archivo JTL para esta ejecución")

    jtl_path = Path(execution.jtl_file_path)
    if not jtl_path.exists():
        raise HTTPException(status_code=404, detail="El archivo JTL no existe en disco")

    filename = execution.output_filename or jtl_path.name
    return FileResponse(
        path=str(jtl_path),
        filename=filename,
        media_type="text/csv",
    )


# ─── Generate Report (Sprint 4) ─────────────────────────────────────────────

@router.post("/{execution_id}/generate-report")
async def generate_report_from_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Generate analysis report from a completed engine execution.

    Parses the JTL file generated by the motor, creates a TestExecution record
    (same model used by the manual upload pipeline), and returns its UUID so
    the frontend can navigate to /performance/report/{id}.
    """
    import uuid as _uuid

    exec_result = await db.execute(
        select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
    )
    execution = exec_result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    if execution.status != "completed":
        raise HTTPException(
            status_code=422,
            detail=f"Solo se puede generar reporte de ejecuciones completadas. Estado actual: {execution.status}"
        )

    if not execution.jtl_file_path:
        raise HTTPException(status_code=422, detail="No hay archivo JTL para esta ejecucion")

    jtl_path = Path(execution.jtl_file_path)
    if not jtl_path.exists():
        raise HTTPException(status_code=404, detail=f"Archivo JTL no encontrado en disco: {execution.jtl_file_path}")

    try:
        from app.services.jtl.jtl_parser import JTLParser

        parser = JTLParser(str(jtl_path))
        df, metrics = parser.parse()

        snapshot = execution.scenario_snapshot or {}
        project_name = snapshot.get("script_name", f"Execution #{execution_id}")
        test_type = snapshot.get("type", "load")

        # Resolve client name
        client_name = ""
        script_id = snapshot.get("script_id")
        if script_id:
            from app.db.models.script_design import ScriptDesign as SD
            sr = await db.execute(select(SD).where(SD.id == script_id))
            script = sr.scalar_one_or_none()
            if script and script.client_id:
                cr = await db.execute(select(Client).where(Client.id == script.client_id))
                c = cr.scalar_one_or_none()
                if c:
                    client_name = c.name

        # Create TestExecution record (same model used by upload + export pipeline)
        test_exec = TestExecution(
            id=_uuid.uuid4(),
            user_id=current_user.id,
            name=project_name,
            description=f"Generated from engine execution #{execution_id}",
            jtl_filename=jtl_path.name,
            client=client_name or None,
            client_id=None,
            project=snapshot.get("scenario_name", project_name),
            test_type=test_type,
            # Strip tzinfo for TIMESTAMP WITHOUT TIME ZONE (value already in COT)
            start_time=metrics.get('start_time').replace(tzinfo=None) if hasattr(metrics.get('start_time'), 'tzinfo') and metrics.get('start_time') is not None else metrics.get('start_time'),
            end_time=metrics.get('end_time').replace(tzinfo=None) if hasattr(metrics.get('end_time'), 'tzinfo') and metrics.get('end_time') is not None else metrics.get('end_time'),
            duration_seconds=float(metrics.get('duration_seconds', 0)),
            total_requests=int(metrics['total_requests']),
            total_errors=int(metrics['total_errors']),
            error_rate=float(metrics['error_rate']),
            avg_response_time=float(metrics['avg_response_time']),
            median_response_time=float(metrics.get('median_response_time', 0)),
            min_response_time=float(metrics['min_response_time']),
            max_response_time=float(metrics['max_response_time']),
            p50_response_time=float(metrics['p50_response_time']),
            p90_response_time=float(metrics['p90_response_time']),
            p95_response_time=float(metrics['p95_response_time']),
            p99_response_time=float(metrics['p99_response_time']),
            throughput=float(metrics['throughput']),
            avg_latency=float(metrics.get('avg_latency', 0)),
            kb_per_sec_received=float(metrics.get('kb_per_sec_received', 0)),
            kb_per_sec_sent=float(metrics.get('kb_per_sec_sent', 0)),
            total_redirects=int(metrics.get('total_redirects', 0)),
            redirect_labels=metrics.get('redirect_labels', None),
            execution_date=datetime.utcnow(),
        )

        # Copy the JTL to /app/uploads so the export endpoints can find it
        import shutil
        uploads_dir = Path("/app/uploads")
        uploads_dir.mkdir(exist_ok=True)
        dest = uploads_dir / jtl_path.name
        if not dest.exists():
            shutil.copy2(str(jtl_path), str(dest))

        db.add(test_exec)
        await db.commit()
        await db.refresh(test_exec)

        logger.info(f"Report generated: TestExecution {test_exec.id} from PerformanceExecution {execution_id}")

        return {
            "analysis_id": str(test_exec.id),
            "status": "completed",
            "report_url": f"/performance/report/{test_exec.id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating report from execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


# ─── Run Single Request (Sprint 7.1) ─────────────────────────────────────────

class SingleRunRequest(BaseModel):
    request: dict
    variables: List[dict] = []
    data_files: List[dict] = []


@router.post("/run-single")
async def run_single_request(
    payload: SingleRunRequest,
    current_user=Depends(get_current_user),
):
    """
    Ejecuta UN solo request con las variables actuales del editor.
    Usa VariableEngine (misma logica que smoke_test) para resolver variables.
    Retorna status_code, headers, body y tiempo real de respuesta.
    NO requiere script guardado en BD.
    """
    import time
    import httpx
    from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
    from app.services.engine.variable_engine import VariableEngine

    req = payload.request

    # ── 1. Inicializar VariableEngine (misma logica que smoke_test/VirtualUser) ─
    ve = VariableEngine(thread_name="run-single")
    ve.initialize(
        script_variables=payload.variables,
        datafile_row=None,
    )

    # Si hay data_files con sample_row, usar la primera fila como datafile_row
    for df in payload.data_files:
        sample = df.get("sample_row") or {}
        if sample:
            for col, val in sample.items():
                ve.set(col.strip(), str(val))
            break

    def resolve(text: str) -> str:
        if not text:
            return text or ""
        return ve.substitute(str(text))

    # ── 2. Resolver campos del request ─────────────────────────────────────
    method = req.get("method", "GET").upper()

    # URL base
    raw_url = req.get("url", "")
    resolved_url = resolve(raw_url)

    # Query params — merge con params que ya estan en la URL
    params_dict = req.get("params") or {}
    if isinstance(params_dict, dict) and params_dict:
        parsed = urlparse(resolved_url)
        existing_params = {}
        if parsed.query:
            existing_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        for k, v in params_dict.items():
            if k and str(v):
                existing_params[resolve(str(k))] = resolve(str(v))
        new_query = urlencode(existing_params)
        resolved_url = urlunparse(parsed._replace(query=new_query))

    # Headers — filtrar headers que httpx no debe enviar manualmente
    SKIP_HEADERS = {
        "host", "content-length", "postman-token",
        "user-agent", "accept-encoding", "connection"
    }
    raw_headers = req.get("headers") or {}
    resolved_headers = {}
    for k, v in raw_headers.items():
        k_stripped = k.strip()
        if k_stripped and k_stripped.lower() not in SKIP_HEADERS:
            resolved_headers[k_stripped] = resolve(str(v))

    # Body
    resolved_body: Optional[bytes] = None
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        raw_body = req.get("body") or ""
        if raw_body and raw_body.strip():
            resolved_body = resolve(raw_body).encode("utf-8")

    # ── 3. Ejecutar el request real ─────────────────────────────────────────
    t_start = time.time()
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            verify=False,
            follow_redirects=True,
        ) as client:
            response = await client.request(
                method=method,
                url=resolved_url,
                headers=resolved_headers,
                content=resolved_body,
            )

        duration_ms = int((time.time() - t_start) * 1000)

        try:
            body_text = response.text
        except Exception:
            body_text = response.content.decode("utf-8", errors="replace")

        resp_headers = dict(response.headers)

        # Apply extractors from the request definition to extract variables from response
        extracted_variables = {}
        extractors = req.get("extractors", [])
        if extractors and body_text:
            ve.apply_extractors(extractors, body_text, resp_headers)
            # Collect only the variables that were actually extracted
            for ext in extractors:
                var_name = ext.get("variable_name", "").strip()
                if var_name:
                    extracted_variables[var_name] = ve.get(var_name, "")

        # Build JMeter-style petition and response details
        body_sent = resolved_body.decode("utf-8") if resolved_body else ""
        petition_text = f"{method} {resolved_url}"
        if body_sent:
            petition_text += f"\n\n{method} data:\n{body_sent}"
        sent_headers_text = "\n".join(f"{k}: {v}" for k, v in resolved_headers.items())
        resp_headers_raw = f"HTTP/1.1 {response.status_code} {response.reason_phrase}\n"
        resp_headers_raw += "\n".join(f"{k}: {v}" for k, v in response.headers.items())

        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "resolved_url": resolved_url,
            "method": method,
            # Petition data (JMeter-style)
            "petition_text": petition_text,
            "sent_headers": sent_headers_text,
            "sent_body": body_sent,
            # Response data
            "response_headers": resp_headers,
            "response_headers_raw": resp_headers_raw,
            "response_body": body_text[:10000],
            "extracted_variables": extracted_variables,
            "error": None,
        }

    except httpx.ConnectError:
        return _run_single_error(method, resolved_url, int((time.time() - t_start) * 1000),
            f"No se pudo conectar a: {resolved_url}. Verifica que el servicio este disponible.")
    except httpx.TimeoutException:
        return _run_single_error(method, resolved_url, 30000,
            "Timeout: el servicio tardo mas de 30 segundos en responder.")
    except httpx.InvalidURL as e:
        return _run_single_error(method, resolved_url, 0,
            f"URL invalida: {resolved_url}. Detalle: {str(e)}")
    except Exception as e:
        logger.exception(f"run-single error: {e}")
        return _run_single_error(method, resolved_url, int((time.time() - t_start) * 1000),
            f"Error inesperado: {str(e)}")


def _run_single_error(method: str, url: str, duration_ms: int, error: str) -> dict:
    return {
        "success": False, "status_code": None, "duration_ms": duration_ms,
        "method": method, "resolved_url": url,
        "petition_text": f"{method} {url}", "sent_headers": "", "sent_body": "",
        "response_body": "", "response_headers": {}, "response_headers_raw": "",
        "error": error,
    }
