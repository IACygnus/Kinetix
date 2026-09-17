"""
KNX-12: Endpoint for generating comparison reports (Load vs Stress).
"""
import asyncio            # ETAPA 1.4 (H4): la IA es sincrona, va a un hilo
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
        from app.services.ai.gemini import load_ai_config_from_db
        from app.services.ai.estilo import ms, num, pct, percentiles_bloque

        ai_conf = await load_ai_config_from_db(db)
        gemini = get_gemini_analyzer(
            provider=ai_conf.get("provider", ""),
            model_name=ai_conf.get("model_name", ""),
            api_key=ai_conf.get("api_key", ""),
            reasoning_effort=(ai_conf.get("reasoning_effort") or ""),   # ETAPA 2 D13c
        )

        # ETAPA 3 (D32/D33/D34): sin markdown en el prompt (el bloque de estilo lo
        # prohibe en la salida y escribirlo aqui lo invitaba), cifras en espanol,
        # percentiles ya traducidos y el estilo lo pone `_generate`. Este informe
        # SI dictamina: es una comparativa completa con recomendaciones, no una
        # seccion de otro informe.
        prompt = f"""Analiza la COMPARATIVA entre estas dos pruebas del mismo sistema.

PRUEBA DE CARGA (referencia)
- Total de peticiones: {num(load_data['total_requests'])}
- Tiempo de respuesta promedio: {ms(load_data['avg_response_time'])}
- Tasa de error: {pct(load_data['error_rate'])}
- Caudal: {num(load_data['throughput'], 2)} por segundo
- Duracion: {num(load_data['duration_seconds'])} segundos
Lectura de sus percentiles (copia estas frases tal cual):
{percentiles_bloque(p90=load_data['p90_response_time'], p95=load_data['p95_response_time'], p99=load_data['p99_response_time'])}

PRUEBA DE ESTRES
- Total de peticiones: {num(stress_data['total_requests'])}
- Tiempo de respuesta promedio: {ms(stress_data['avg_response_time'])}
- Tasa de error: {pct(stress_data['error_rate'])}
- Caudal: {num(stress_data['throughput'], 2)} por segundo
- Duracion: {num(stress_data['duration_seconds'])} segundos
Lectura de sus percentiles (copia estas frases tal cual):
{percentiles_bloque(p90=stress_data['p90_response_time'], p95=stress_data['p95_response_time'], p99=stress_data['p99_response_time'])}

CUANTO CAMBIA EL ESTRES FRENTE A LA CARGA
- Tiempo de respuesta: {pct(comparison['response_time_change_pct'] or 0, 1)}
- Percentil 90: {pct(comparison['p90_change_pct'] or 0, 1)}
- Tasa de error: {pct(comparison['error_rate_change_pct'] or 0, 1)}
- Caudal: {pct(comparison['throughput_change_pct'] or 0, 1)}

Escribe la comparativa. Maximo 500 palabras.
1. Que cambia entre una prueba y otra, contado como lo vive el usuario.
2. Donde se rompe el sistema y con que cifras.
3. Si aguanta o no, y hasta donde.
4. Que hace falta en capacidad y escalabilidad.
"""
        ai_analysis = await asyncio.to_thread(
            gemini._generate, prompt, section_name="comparison_analysis",
            permite_veredicto=True) or ""
        if not ai_analysis:
            ai_analysis = (
                f"Comparativa: el sistema muestra un incremento de "
                f"{pct(comparison['response_time_change_pct'] or 0, 0)} en tiempo de respuesta "
                f"bajo estres. La tasa de error cambio un "
                f"{pct(comparison['error_rate_change_pct'] or 0, 0)}."
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
