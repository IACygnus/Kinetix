"""
AI analysis endpoints for monitoring metrics and evidence findings.
R3-A: Standalone pages call these to generate/retrieve AI analysis.
"""
import asyncio            # ETAPA 1.4 (H4): la IA es sincrona, va a un hilo
import uuid
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy import func
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.test import TestExecution
from app.db.models.attachment import ExecutionAttachment
# ETAPA 3 (D32/D33): formato espanol y percentiles traducidos en los prompts.
from app.services.ai.estilo import ms, num, pct, percentiles_bloque

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_capacity_data(execution) -> dict:
    """Read capacity_analysis_json safely."""
    try:
        return json.loads(execution.capacity_analysis_json or '{}')
    except (json.JSONDecodeError, TypeError):
        return {}


def _save_capacity_data(execution, data: dict) -> None:
    """Write to capacity_analysis_json."""
    execution.capacity_analysis_json = json.dumps(data)


@router.post("/{execution_id}/monitoring-analysis")
async def generate_monitoring_analysis(
    execution_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate correlated AI analysis based on monitoring metrics + execution data."""
    result = await db.execute(select(TestExecution).where(TestExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Ejecucion no encontrada")

    attachments_info = data.get('attachments', [])
    if not attachments_info:
        raise HTTPException(400, "No hay metricas para analizar")

    # Obtener analisis AI individuales de las imagenes de monitoreo
    att_result = await db.execute(
        select(ExecutionAttachment)
        .where(ExecutionAttachment.execution_id == execution_id)
        .where(ExecutionAttachment.attachment_type == "monitoring")
        .order_by(ExecutionAttachment.sort_order)
    )
    attachments = att_result.scalars().all()

    image_analyses = []
    for att in attachments:
        if att.ai_analysis:
            image_analyses.append(
                f"[{(att.category or '').upper()} - {att.title or att.filename}]: {att.ai_analysis}"
            )

    # ETAPA 3 (D32/D33): los datos de la prueba se entregan en formato espanol y
    # con los percentiles ya traducidos a personas, igual que en el informe.
    prompt = (
        f"Correlaciona las metricas de monitoreo de infraestructura con los "
        f"resultados de esta prueba de rendimiento.\n\n"
        f"DATOS DE LA PRUEBA EJECUTADA:\n"
        f"- Nombre: {execution.name}\n"
        f"- Tipo: {execution.test_type or 'No especificado'}\n"
        f"- Total de peticiones: {num(execution.total_requests)}\n"
        f"- Tasa de error: {pct(execution.error_rate)}\n"
        f"- Tiempo promedio de respuesta: {ms(execution.avg_response_time)}\n"
        f"- Latencia promedio: {ms(execution.avg_latency or 0)}\n"
        f"- Caudal: {num(execution.throughput, 2)} por segundo\n"
        f"- Duracion: {num(execution.duration_seconds or 0)} segundos\n"
        f"LECTURA DE LOS PERCENTILES (copia estas frases tal cual):\n"
        f"{percentiles_bloque(p90=execution.p90_response_time, p95=execution.p95_response_time, p99=execution.p99_response_time)}\n\n"
        f"ANALISIS INDIVIDUALES DE LAS IMAGENES DE MONITOREO:\n"
        f"{chr(10).join(image_analyses) if image_analyses else 'No hay analisis individuales de imagenes disponibles.'}\n\n"
        f"INSTRUCCIONES:\n"
        f"- Cruza los datos de la prueba con lo que muestran las metricas de monitoreo\n"
        f"- Di si los recursos de infraestructura (CPU, memoria, hilos) explican los "
        f"tiempos de respuesta o los errores, marcado como hipotesis\n"
        f"- Indica que recursos estan cerca de su limite y cuales tienen margen\n"
        f"- Relaciona los picos de consumo con los momentos de mayor carga\n"
        f"- Propon umbrales de alerta concretos a partir de lo observado\n"
        f"- Maximo 500 palabras"
    )

    analysis = ""
    try:
        from app.services.ai.gemini import GeminiAnalyzer, get_gemini_analyzer, load_ai_config_from_db
        ai_conf = await load_ai_config_from_db(db)
        gemini = get_gemini_analyzer(
            provider=ai_conf.get("provider", ""),
            model_name=ai_conf.get("model_name", ""),
            api_key=ai_conf.get("api_key", ""),
            reasoning_effort=(ai_conf.get("reasoning_effort") or ""),   # ETAPA 2 D13c
        )
        # ETAPA 3 (D34): el bloque de estilo lo pone `_generate`, una sola vez.
        analysis = await asyncio.to_thread(gemini._generate, prompt, section_name="monitoring_analysis") or ""
    except Exception as e:
        logger.error(f"Monitoring AI analysis failed: {e}")
        analysis = (
            f"No fue posible generar el analisis correlacionado. Los datos de la prueba "
            f"muestran {num(execution.total_requests)} peticiones con una tasa de error "
            f"de {pct(execution.error_rate)} y un tiempo de respuesta promedio de "
            f"{ms(execution.avg_response_time)}."
        )

    # Persist in capacity_analysis_json
    cap_data = _get_capacity_data(execution)
    cap_data['monitoring_ai_analysis'] = analysis
    _save_capacity_data(execution, cap_data)
    await db.commit()

    return {"analysis": analysis}


@router.get("/{execution_id}/monitoring-analysis")
async def get_monitoring_analysis(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get saved monitoring AI analysis."""
    result = await db.execute(select(TestExecution).where(TestExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Ejecucion no encontrada")

    data = _get_capacity_data(execution)
    return {"analysis": data.get('monitoring_ai_analysis', '')}


@router.post("/{execution_id}/evidence-analysis")
async def generate_evidence_analysis(
    execution_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate correlated AI analysis based on evidence + execution data."""
    result = await db.execute(select(TestExecution).where(TestExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Ejecucion no encontrada")

    attachments_info = data.get('attachments', [])
    if not attachments_info:
        raise HTTPException(400, "No hay evidencias para analizar")

    # Obtener analisis AI individuales de las evidencias
    att_result = await db.execute(
        select(ExecutionAttachment)
        .where(ExecutionAttachment.execution_id == execution_id)
        .where(ExecutionAttachment.attachment_type == "evidence")
        .order_by(ExecutionAttachment.sort_order)
    )
    attachments = att_result.scalars().all()

    image_analyses = []
    for att in attachments:
        if att.ai_analysis:
            image_analyses.append(
                f"[{(att.category or '').upper()} - {att.title or att.filename}]: {att.ai_analysis}"
            )

    # ETAPA 3: mismo formato espanol que el resto del informe, y sin la palabra
    # "hallazgo", que el propio bloque de estilo prohibe (reporte 30 §2).
    prompt = (
        f"Correlaciona las evidencias recogidas con los resultados de esta prueba "
        f"de rendimiento.\n\n"
        f"DATOS DE LA PRUEBA EJECUTADA:\n"
        f"- Nombre: {execution.name}\n"
        f"- Tipo: {execution.test_type or 'No especificado'}\n"
        f"- Total de peticiones: {num(execution.total_requests)}\n"
        f"- Tasa de error: {pct(execution.error_rate)}\n"
        f"- Tiempo promedio de respuesta: {ms(execution.avg_response_time)}\n"
        f"- Caudal: {num(execution.throughput, 2)} por segundo\n"
        f"- Duracion: {num(execution.duration_seconds or 0)} segundos\n"
        f"LECTURA DE LOS PERCENTILES (copia estas frases tal cual):\n"
        f"{percentiles_bloque(p90=execution.p90_response_time, p95=execution.p95_response_time)}\n\n"
        f"ANALISIS INDIVIDUALES DE LAS EVIDENCIAS:\n"
        f"{chr(10).join(image_analyses) if image_analyses else 'No hay analisis individuales de evidencias disponibles.'}\n\n"
        f"INSTRUCCIONES:\n"
        f"- Cruza los errores evidenciados con el rendimiento de la prueba\n"
        f"- Ordena los problemas por gravedad para la operacion\n"
        f"- Senala lo que se repite entre varias evidencias\n"
        f"- Relaciona cada error con la cifra de la prueba que lo respalda\n"
        f"- Propon acciones correctivas ordenadas por impacto\n"
        f"- Maximo 400 palabras"
    )

    analysis = ""
    try:
        from app.services.ai.gemini import GeminiAnalyzer, get_gemini_analyzer, load_ai_config_from_db
        ai_conf = await load_ai_config_from_db(db)
        gemini = get_gemini_analyzer(
            provider=ai_conf.get("provider", ""),
            model_name=ai_conf.get("model_name", ""),
            api_key=ai_conf.get("api_key", ""),
            reasoning_effort=(ai_conf.get("reasoning_effort") or ""),   # ETAPA 2 D13c
        )
        # ETAPA 3 (D34): el bloque de estilo lo pone `_generate`, una sola vez.
        analysis = await asyncio.to_thread(gemini._generate, prompt, section_name="evidence_analysis") or ""
    except Exception as e:
        logger.error(f"Evidence AI analysis failed: {e}")
        analysis = (
            f"No fue posible generar el analisis correlacionado. Los datos de la prueba "
            f"muestran {num(execution.total_requests)} peticiones con una tasa de error "
            f"de {pct(execution.error_rate)} y un tiempo de respuesta promedio de "
            f"{ms(execution.avg_response_time)}."
        )

    # Persist
    cap_data = _get_capacity_data(execution)
    cap_data['evidence_ai_analysis'] = analysis
    _save_capacity_data(execution, cap_data)
    await db.commit()

    return {"analysis": analysis}


@router.get("/{execution_id}/evidence-analysis")
async def get_evidence_analysis(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get saved evidence AI analysis."""
    result = await db.execute(select(TestExecution).where(TestExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Ejecucion no encontrada")

    data = _get_capacity_data(execution)
    return {"analysis": data.get('evidence_ai_analysis', '')}


@router.get("/{execution_id}/attachment-counts")
async def get_attachment_counts(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get count of attachments by type for an execution."""
    result = await db.execute(
        select(
            ExecutionAttachment.attachment_type,
            func.count(ExecutionAttachment.id),
        )
        .where(ExecutionAttachment.execution_id == execution_id)
        .group_by(ExecutionAttachment.attachment_type)
    )
    counts = {row[0]: row[1] for row in result.fetchall()}
    return {"monitoring": counts.get("monitoring", 0), "evidence": counts.get("evidence", 0)}


# ====== Sprint P1-A: Per-image AI analysis endpoints ======

def _get_image_bytes(attachment) -> bytes:
    """Read image file from disk."""
    import os
    abs_path = os.path.join("/app", attachment.filepath.lstrip("/"))
    if not os.path.exists(abs_path):
        raise HTTPException(404, f"Archivo no encontrado: {attachment.filepath}")
    with open(abs_path, "rb") as f:
        return f.read()


def _get_analyzer(ai_conf: dict):
    """Instantiate GeminiAnalyzer with DB config."""
    from app.services.ai.gemini import get_gemini_analyzer
    return get_gemini_analyzer(
        provider=ai_conf.get("provider", ""),
        model_name=ai_conf.get("model_name", ""),
        api_key=ai_conf.get("api_key", ""),
        reasoning_effort=(ai_conf.get("reasoning_effort") or ""),   # ETAPA 2 D13c
    )


@router.post("/{execution_id}/attachments/{attachment_id}/analyze-image")
async def analyze_single_image(
    execution_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Analyze a single image attachment using Gemini Vision."""
    from datetime import datetime as dt
    import asyncio
    from app.services.ai.gemini import load_ai_config_from_db

    result = await db.execute(
        select(ExecutionAttachment).where(
            ExecutionAttachment.id == attachment_id,
            ExecutionAttachment.execution_id == execution_id,
        )
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(404, "Adjunto no encontrado")
    if not att.file_type or not att.file_type.startswith("image/"):
        raise HTTPException(400, "El adjunto no es una imagen")

    image_bytes = _get_image_bytes(att)
    ai_conf = await load_ai_config_from_db(db)
    analyzer = _get_analyzer(ai_conf)

    analysis = await asyncio.to_thread(
        analyzer.analyze_image,
        image_bytes, att.file_type, att.category or "",
        att.title or "", att.description or "", att.attachment_type,
    )

    att.ai_analysis = analysis
    att.ai_analysis_updated_at = dt.utcnow()
    await db.commit()

    return {"attachment_id": str(att.id), "ai_analysis": analysis, "status": "success"}


@router.post("/{execution_id}/analyze-all-images")
async def analyze_all_images(
    execution_id: uuid.UUID,
    attachment_type: str = "monitoring",
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Analyze all image attachments of a given type for an execution."""
    from datetime import datetime as dt
    import asyncio
    from app.services.ai.gemini import load_ai_config_from_db

    result = await db.execute(
        select(ExecutionAttachment).where(
            ExecutionAttachment.execution_id == execution_id,
            ExecutionAttachment.attachment_type == attachment_type,
        ).order_by(ExecutionAttachment.sort_order)
    )
    attachments = result.scalars().all()

    images = [a for a in attachments if a.file_type and a.file_type.startswith("image/")]
    if not force:
        images = [a for a in images if not a.ai_analysis]

    if not images:
        return {"analyzed_count": 0, "failed_count": 0, "results": []}

    ai_conf = await load_ai_config_from_db(db)
    analyzer = _get_analyzer(ai_conf)

    results = []
    failed = 0
    for att in images:
        try:
            image_bytes = _get_image_bytes(att)
            analysis = await asyncio.to_thread(
                analyzer.analyze_image,
                image_bytes, att.file_type, att.category or "",
                att.title or "", att.description or "", att.attachment_type,
            )
            att.ai_analysis = analysis
            att.ai_analysis_updated_at = dt.utcnow()
            results.append({"attachment_id": str(att.id), "status": "success"})
        except Exception as e:
            logger.error(f"Failed to analyze {att.id}: {e}")
            results.append({"attachment_id": str(att.id), "status": f"error: {str(e)[:100]}"})
            failed += 1

        await asyncio.sleep(1)  # Rate limit: 1 call per second

    await db.commit()
    return {"analyzed_count": len(images) - failed, "failed_count": failed, "results": results}


@router.get("/{execution_id}/attachments/{attachment_id}/analysis")
async def get_image_analysis(
    execution_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the AI analysis for a single image attachment."""
    result = await db.execute(
        select(ExecutionAttachment).where(
            ExecutionAttachment.id == attachment_id,
            ExecutionAttachment.execution_id == execution_id,
        )
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(404, "Adjunto no encontrado")

    return {
        "attachment_id": str(att.id),
        "ai_analysis": att.ai_analysis,
        "ai_analysis_updated_at": att.ai_analysis_updated_at.isoformat() if att.ai_analysis_updated_at else None,
    }


@router.put("/{execution_id}/attachments/{attachment_id}/analysis")
async def update_image_analysis(
    execution_id: uuid.UUID,
    attachment_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update (edit) the AI analysis for a single image attachment."""
    from datetime import datetime as dt

    result = await db.execute(
        select(ExecutionAttachment).where(
            ExecutionAttachment.id == attachment_id,
            ExecutionAttachment.execution_id == execution_id,
        )
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(404, "Adjunto no encontrado")

    att.ai_analysis = data.get("ai_analysis", att.ai_analysis)
    att.ai_analysis_updated_at = dt.utcnow()
    await db.commit()

    return {"attachment_id": str(att.id), "ai_analysis": att.ai_analysis, "status": "updated"}


@router.get("/{execution_id}/image-analyses")
async def get_all_image_analyses(
    execution_id: uuid.UUID,
    attachment_type: str = "monitoring",
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all image analyses for an execution, filtered by type."""
    result = await db.execute(
        select(ExecutionAttachment).where(
            ExecutionAttachment.execution_id == execution_id,
            ExecutionAttachment.attachment_type == attachment_type,
        ).order_by(ExecutionAttachment.sort_order)
    )
    attachments = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "title": a.title,
            "category": a.category,
            "filename": a.filename,
            "filepath": a.filepath,
            "file_type": a.file_type,
            "ai_analysis": a.ai_analysis,
            "ai_analysis_updated_at": a.ai_analysis_updated_at.isoformat() if a.ai_analysis_updated_at else None,
        }
        for a in attachments
    ]
