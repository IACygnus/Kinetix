"""
KNX-12: Endpoint for generating comparison reports (Load vs Stress).
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.test import TestExecution

router = APIRouter()
logger = logging.getLogger(__name__)


def _exec_to_dict(exc) -> dict:
    return {
        "id": str(exc.id),
        "name": exc.name,
        "test_type": exc.test_type,
        "client": exc.client,
        "project": exc.project,
        "start_time": exc.start_time.isoformat() if exc.start_time else None,
        "end_time": exc.end_time.isoformat() if exc.end_time else None,
        "duration_seconds": exc.duration_seconds,
        "total_requests": exc.total_requests,
        "total_errors": exc.total_errors,
        "error_rate": float(exc.error_rate or 0),
        "avg_response_time": float(exc.avg_response_time or 0),
        "median_response_time": float(exc.median_response_time or 0),
        "p90_response_time": float(exc.p90_response_time or 0),
        "p95_response_time": float(exc.p95_response_time or 0),
        "p99_response_time": float(exc.p99_response_time or 0),
        "min_response_time": float(exc.min_response_time or 0),
        "max_response_time": float(exc.max_response_time or 0),
        "throughput": float(exc.throughput or 0),
        "ai_analysis_summary": exc.ai_analysis_summary or "",
        "ai_conclusions": exc.ai_conclusions or "",
        "ai_recommendations": exc.ai_recommendations or "",
    }


def _safe_pct(a, b):
    if a is None or b is None or a == 0:
        return None
    return round(((b - a) / abs(a)) * 100, 2)


@router.post("/compare")
async def generate_comparison(
    load_execution_id: str = Query(...),
    stress_execution_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a comparison report between a load test and a stress test."""
    try:
        load_uuid = uuid.UUID(load_execution_id)
        stress_uuid = uuid.UUID(stress_execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(400, "IDs de ejecucion invalidos")

    result = await db.execute(select(TestExecution).where(TestExecution.id == load_uuid))
    load_exec = result.scalar_one_or_none()
    if not load_exec:
        raise HTTPException(404, "Ejecucion de carga no encontrada")

    result = await db.execute(select(TestExecution).where(TestExecution.id == stress_uuid))
    stress_exec = result.scalar_one_or_none()
    if not stress_exec:
        raise HTTPException(404, "Ejecucion de estres no encontrada")

    load_data = _exec_to_dict(load_exec)
    stress_data = _exec_to_dict(stress_exec)

    comparison = {
        "response_time_change_pct": _safe_pct(load_exec.avg_response_time, stress_exec.avg_response_time),
        "p90_change_pct": _safe_pct(load_exec.p90_response_time, stress_exec.p90_response_time),
        "p95_change_pct": _safe_pct(load_exec.p95_response_time, stress_exec.p95_response_time),
        "error_rate_change_pct": _safe_pct(load_exec.error_rate, stress_exec.error_rate),
        "throughput_change_pct": _safe_pct(load_exec.throughput, stress_exec.throughput),
    }

    # Generate AI comparison analysis
    ai_analysis = ""
    try:
        from app.services.ai.gemini import GeminiAnalyzer, get_gemini_analyzer, FallbackAnalyzer
        from app.services.ai.gemini import load_ai_config_from_db, SYSTEM_PROMPT

        ai_conf = await load_ai_config_from_db(db)
        gemini = get_gemini_analyzer(
            provider=ai_conf.get("provider", ""),
            model_name=ai_conf.get("model_name", ""),
            api_key=ai_conf.get("api_key", ""),
        )

        prompt = f"""{SYSTEM_PROMPT}

Analiza la COMPARATIVA entre estas dos pruebas del mismo sistema:

## Prueba de CARGA (baseline)
- Total requests: {load_data['total_requests']:,}
- Tiempo de respuesta promedio: {load_data['avg_response_time']:.0f}ms
- P90: {load_data['p90_response_time']:.0f}ms | P95: {load_data['p95_response_time']:.0f}ms | P99: {load_data['p99_response_time']:.0f}ms
- Tasa de error: {load_data['error_rate']:.2f}%
- Throughput: {load_data['throughput']:.2f} req/s
- Duracion: {load_data['duration_seconds']:.0f}s

## Prueba de ESTRES
- Total requests: {stress_data['total_requests']:,}
- Tiempo de respuesta promedio: {stress_data['avg_response_time']:.0f}ms
- P90: {stress_data['p90_response_time']:.0f}ms | P95: {stress_data['p95_response_time']:.0f}ms | P99: {stress_data['p99_response_time']:.0f}ms
- Tasa de error: {stress_data['error_rate']:.2f}%
- Throughput: {stress_data['throughput']:.2f} req/s
- Duracion: {stress_data['duration_seconds']:.0f}s

## Cambios porcentuales (estres vs carga)
- Response time: {comparison['response_time_change_pct']}%
- P90: {comparison['p90_change_pct']}%
- Error rate: {comparison['error_rate_change_pct']}%
- Throughput: {comparison['throughput_change_pct']}%

Proporciona en espanol profesional (maximo 500 palabras):
1. Resumen ejecutivo comparando ambas pruebas
2. Analisis del punto de quiebre
3. Evaluacion de resiliencia del sistema
4. Recomendaciones de capacidad y escalabilidad
"""
        ai_analysis = gemini._generate(prompt, section_name="comparison_analysis") or ""
        if not ai_analysis:
            ai_analysis = (
                f"Comparativa: El sistema muestra un incremento del "
                f"{comparison['response_time_change_pct'] or 0:.0f}% en tiempo de respuesta "
                f"bajo estres. La tasa de error cambio un {comparison['error_rate_change_pct'] or 0:.0f}%."
            )
    except Exception as e:
        logger.error(f"AI comparison analysis failed: {e}")
        ai_analysis = f"Analisis comparativo no disponible: {str(e)[:200]}"

    return {
        "load": load_data,
        "stress": stress_data,
        "comparison": comparison,
        "ai_comparison_analysis": ai_analysis,
    }
