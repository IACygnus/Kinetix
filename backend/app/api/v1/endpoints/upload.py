"""
Endpoints de JTL Upload y Analisis - v2.0
Multi-JTL upload, test types, redirect separation, enhanced Gemini AI
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, delete
from pydantic import BaseModel
from typing import Optional, List
import os
import aiofiles
from pathlib import Path
from datetime import datetime
import uuid
import json
import logging
import time

from app.db.session import get_db
from app.db.models.test import TestExecution
from app.db.models.client import UserClient
from app.db.models.user import User
from app.core.security import get_current_active_user, require_role
from app.services.jtl.jtl_parser import JTLParser, validate_jtl_compatibility
from app.services.ai.gemini import get_gemini_analyzer, prepare_insights_for_prompt, FallbackAnalyzer, load_ai_config_from_db, update_ai_usage_in_db, compute_verdict, compute_per_transaction_verdicts   # N3.2
from app.services.ai.analysis_pipeline import run_ai_and_verdict
from app.services.ai.transaction_analysis import analyze_critical_transactions   # N3.4
from app.db.models.transaction_analysis import TransactionAnalysis               # N3.4
from app.services.jtl.transaction_series import (                                # N4.4
    build_transaction_series,
    available_labels,
    DEFAULT_INTERVAL_SECONDS,
)
from app.services.ai.transaction_report import generate_transaction_report       # N4.6
from app.db.models.transaction_chart_analysis import (                           # N4.6
    TransactionChartAnalysis,
    SECTIONS,
)
from app.schemas.test import (
    TestExecutionResponse,
    ChartData,
    TimelineData,
    LabelStats,
    TimeSeriesPoint,
    ValidationResult,
    ErrorDetail,
)

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("/app/uploads")


async def _get_assigned_client_ids(db: AsyncSession, user: User) -> List:
    """Get list of client_ids assigned to a non-admin user via user_clients table."""
    result = await db.execute(
        select(UserClient.client_id).where(UserClient.user_id == user.id)
    )
    return [row[0] for row in result.fetchall()]


async def _check_execution_access(db: AsyncSession, user: User, execution) -> None:
    """Raise 403 if a non-admin user doesn't have access to this execution."""
    if user.role == 'admin':
        return
    client_ids = await _get_assigned_client_ids(db, user)
    if execution.client_id is None or execution.client_id not in client_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta ejecucion"
        )


@router.get("/gemini-test")
async def test_gemini():
    """Test Gemini API connectivity and model."""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY", "NOT SET")
    model_env = os.getenv("GEMINI_MODEL", "NOT SET")

    result = {
        "api_key_set": bool(api_key and api_key != "NOT SET"),
        "api_key_preview": api_key[:8] + "..." if api_key and len(api_key) > 8 else "MISSING",
        "model_env": model_env,
        "model_hardcoded": model_env or "gemini-2.5-flash",
        "model_actual": None,
        "test_result": None,
        "available_flash_models": [],
    }

    try:
        genai.configure(api_key=api_key, transport="rest")

        # List available flash/2.0 models
        models = []
        try:
            for m in genai.list_models():
                methods = m.supported_generation_methods if hasattr(m, 'supported_generation_methods') else []
                if "generateContent" in methods:
                    if "2.0" in m.name or "2.5" in m.name or "flash" in m.name:
                        models.append(m.name)
        except Exception as list_err:
            result["list_models_error"] = str(list_err)[:200]
        result["available_flash_models"] = models

        # Test with configured model
        test_model_name = model_env if model_env and model_env != "NOT SET" else "gemini-2.5-flash"
        model = genai.GenerativeModel(test_model_name)
        result["model_actual"] = test_model_name

        response = model.generate_content("Responde solo: OK FUNCIONANDO")
        result["test_result"] = response.text[:100]
        result["status"] = "SUCCESS"

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)[:500]

    return result


@router.post("/extract-jtl-transactions")
async def extract_jtl_transactions(
    files: List[UploadFile] = File(...),
    response_time: Optional[float] = Form(None),
    availability: Optional[float] = Form(None),
    current_user: User = Depends(get_current_active_user),
):
    """N3.2: transacciones del JTL con sus metricas reales y criticidad sugerida.

    A diferencia de /extract-jtl-labels (que se mantiene, D6), usa JTLParser: por
    eso entiende JTL en XML y no trunca a 10.000 lineas.

    La criticidad es determinista, sin IA (D3), y se dispara con tres senales:
      (a) el veredicto por transaccion de KNX-09 (p90 vs tiempo, tasa de error vs
          disponibilidad). Requiere criterios; sin ellos se omite.
      (b) pico relativo: max >= 10x el promedio.
      (c) pico absoluto: max >= 10000 ms.
    Cualquiera de las tres marca. (b) y (c) existen porque una transaccion puede
    cumplir p90 y error y aun asi acumular timeouts: en la ejecucion de Coomeva,
    'token' promedia 447ms y tiene picos de 21s (leccion de GRAF1).
    """
    UPLOAD_DIR.mkdir(exist_ok=True)
    temp_paths: List[str] = []
    try:
        for f in files:
            temp_path = UPLOAD_DIR / f"temp_txn_{uuid.uuid4().hex}_{f.filename or 'jtl'}"
            async with aiofiles.open(temp_path, 'wb') as out:
                await out.write(await f.read())
            temp_paths.append(str(temp_path))

        parser = JTLParser(temp_paths[0])
        parser.parse()
        summary_df = parser.get_summary_table_data()

        criteria = None
        if response_time is not None or availability is not None:
            criteria = {
                'response_time': response_time if response_time is not None else 2000,
                'availability': availability if availability is not None else 99.0,
            }
        # Se importa, no se copia: la logica de veredicto vive en gemini.py (KNX-09).
        verdicts = compute_per_transaction_verdicts(summary_df, criteria).get(
            'verdicts_per_transaction', {}) if criteria else {}

        transactions = []
        for _, row in summary_df.iterrows():
            label = str(row['label'])
            avg, mx = float(row['promedio']), float(row['max'])
            motivos = []
            veredicto = verdicts.get(label)
            if veredicto in ("NO APTO", "APTO CON RESERVAS"):
                motivos.append(f"{veredicto.lower()} por criterios (p90 {row['p90']:.0f}ms, "
                               f"{row['tasa_error']:.2f}% error)")
            if avg > 0 and mx >= 10 * avg:
                motivos.append(f"pico de {mx:.0f}ms, {mx / avg:.0f}x el promedio")
            if mx >= 10000:
                motivos.append(f"pico absoluto de {mx:.0f}ms (>=10s, posible timeout)")

            transactions.append({
                'label': label,
                'muestras': int(row['muestras']),
                'promedio': round(avg, 2),
                'p90': round(float(row['p90']), 2),
                'p95': round(float(row['p95']), 2),
                'max': round(mx, 2),
                'errores': int(row['errores']),
                'tasa_error': round(float(row['tasa_error']), 4),
                'verdict': veredicto,
                'is_critical_suggested': bool(motivos),
                'motivo': " · ".join(motivos),
            })

        transactions.sort(key=lambda t: (not t['is_critical_suggested'], -t['max']))
        return {
            "transactions": transactions,
            "count": len(transactions),
            "critical_count": sum(1 for t in transactions if t['is_critical_suggested']),
            "criteria_applied": criteria is not None,
        }

    except Exception as e:
        logger.error(f"Error extrayendo transacciones del JTL: {e}")
        raise HTTPException(400, f"No se pudieron extraer las transacciones: {e}")

    finally:
        for p in temp_paths:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/extract-jtl-labels")
async def extract_jtl_labels(
    file: UploadFile = File(...),
):
    """Extrae los labels/transacciones unicos de un archivo JTL sin procesamiento completo."""
    import csv
    import io

    content = await file.read()
    text = content.decode('utf-8', errors='replace')

    # Leer solo las primeras 10,000 lineas para ser rapido
    lines = text.split('\n')[:10000]

    labels = set()
    reader = csv.reader(io.StringIO('\n'.join(lines)))

    label_idx = None

    for i, row in enumerate(reader):
        if i == 0:
            # Buscar columna "label" en el header
            for j, col in enumerate(row):
                if col.strip().lower() == 'label':
                    label_idx = j
                    break
            if label_idx is None:
                return {"labels": [], "error": "No se encontro columna 'label' en el archivo"}
            continue

        if label_idx is not None and len(row) > label_idx:
            label = row[label_idx].strip()
            if label and not label.startswith('TOTAL'):
                labels.add(label)

    sorted_labels = sorted(list(labels))
    return {"labels": sorted_labels, "count": len(sorted_labels)}


@router.post("/validate-jtl", response_model=ValidationResult)
async def validate_jtl_files(
    files: List[UploadFile] = File(...),
):
    """Validar compatibilidad de multiples archivos JTL antes de subir"""
    if len(files) < 2:
        return ValidationResult(
            compatible=True,
            errors=[],
            warnings=[],
            summary={"total_files": len(files), "message": "Un solo archivo, no requiere validacion"},
        )

    UPLOAD_DIR.mkdir(exist_ok=True)
    temp_paths: List[str] = []

    try:
        # Guardar temporalmente para validar
        for f in files:
            if not f.filename or not f.filename.endswith(('.jtl', '.csv')):
                return ValidationResult(
                    compatible=False,
                    errors=[f"Archivo invalido: {f.filename}. Solo .jtl o .csv"],
                )
            temp_path = UPLOAD_DIR / f"temp_validate_{uuid.uuid4().hex}_{f.filename}"
            async with aiofiles.open(temp_path, 'wb') as out:
                content = await f.read()
                await out.write(content)
            temp_paths.append(str(temp_path))

        result = validate_jtl_compatibility(temp_paths)
        return ValidationResult(**result)

    except Exception as e:
        logger.error(f"Error validando JTL: {str(e)}")
        return ValidationResult(compatible=False, errors=[str(e)])

    finally:
        # Limpiar archivos temporales
        for p in temp_paths:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/parse-jmx")
async def parse_jmx_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Parse a .jmx file and return test metadata for form pre-population."""
    if not file.filename or not file.filename.endswith('.jmx'):
        raise HTTPException(400, "El archivo debe ser .jmx")

    content = await file.read()
    try:
        from app.services.jmx_parser import parse_jmx
        return parse_jmx(content)
    except Exception as e:
        logger.error(f"Error parsing JMX: {e}")
        raise HTTPException(400, f"Error parseando .jmx: {str(e)}")


@router.post("/upload")
async def upload_jtl(
    files: List[UploadFile] = File(...),
    name: str = Query("Test Execution"),
    description: str = Query(""),
    test_type: str = Query("load"),
    client: str = Query(""),
    project: str = Query(""),
    client_id: str = Query(""),
    acceptance_criteria: str = Query(""),
    metric_unit: str = Query("TPS"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload y procesar archivos JTL con analisis IA completo v2.0"""

    # Validar archivos
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Se requiere al menos un archivo JTL")

    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximo 5 archivos JTL permitidos")

    valid_types = {"load", "stress", "endurance", "scalability", "spike", "smoke"}
    if test_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"test_type invalido. Opciones: {valid_types}")

    for f in files:
        if not f.filename or not f.filename.endswith(('.jtl', '.csv', '.xml')):
            raise HTTPException(status_code=400, detail=f"Solo archivos .jtl, .csv o .xml: {f.filename}")

    # Guardar archivos
    UPLOAD_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    saved_paths: List[str] = []
    original_filenames: List[str] = []

    try:
        for i, f in enumerate(files):
            suffix = f"_{i}" if len(files) > 1 else ""
            file_path = UPLOAD_DIR / f"{timestamp}{suffix}_{f.filename}"
            async with aiofiles.open(file_path, 'wb') as out:
                content = await f.read()
                await out.write(content)
            saved_paths.append(str(file_path))
            original_filenames.append(f.filename or f"file_{i}.jtl")

        logger.info(f"Iniciando procesamiento de {len(files)} archivo(s)")

        # KNX-16: Detect file format and parse accordingly
        from app.services.parsers.format_detector import detect_file_format
        file_format = detect_file_format(original_filenames[0], saved_paths[0])
        logger.info(f"Formato detectado: {file_format} para {original_filenames[0]}")

        parser = None
        if file_format == 'jtl':
            if len(saved_paths) == 1:
                parser = JTLParser(saved_paths[0])
                df, metrics = parser.parse()
            else:
                df, metrics, parser = JTLParser.parse_multiple(saved_paths)
        elif file_format == 'locust':
            from app.services.parsers.locust_parser import parse_locust_csv
            with open(saved_paths[0], 'rb') as f_content:
                df = parse_locust_csv(f_content.read())
            # Use JTLParser on normalized DataFrame to compute metrics
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as tmp:
                df.to_csv(tmp.name, index=False)
                parser = JTLParser(tmp.name)
                df, metrics = parser.parse()
        elif file_format in ('wapt_csv', 'wapt_xml'):
            from app.services.parsers.wapt_parser import parse_wapt_csv, parse_wapt_xml
            with open(saved_paths[0], 'rb') as f_content:
                raw = f_content.read()
            df = parse_wapt_csv(raw) if file_format == 'wapt_csv' else parse_wapt_xml(raw)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as tmp:
                df.to_csv(tmp.name, index=False)
                parser = JTLParser(tmp.name)
                df, metrics = parser.parse()
        else:
            raise HTTPException(status_code=400, detail=f"Formato no soportado: {original_filenames[0]}")

        logger.info(f"Parseado ({file_format}): {len(df)} muestras totales, {metrics.get('total_main_samples', 0)} principales")

        # Parse acceptance criteria JSON
        acceptance_criteria_dict = None
        if acceptance_criteria:
            try:
                acceptance_criteria_dict = json.loads(acceptance_criteria)
            except json.JSONDecodeError:
                # Formato texto legacy - convertir a dict
                acceptance_criteria_dict = {"raw_text": acceptance_criteria}

        # ===== ANALISIS IA + VERDICT (Sprint 2.5d.2) =====
        # Logica movida VERBATIM a app.services.ai.analysis_pipeline.run_ai_and_verdict.
        # /upload conserva intactos su parsing (formato/multi-archivo) y la construccion
        # de TestExecution; aqui solo delega el bloque AI + verdict.
        ai_result = await run_ai_and_verdict(
            parser=parser,
            metrics=metrics,
            test_type=test_type,
            acceptance_criteria_dict=acceptance_criteria_dict,
            metric_unit=metric_unit,
            db=db,
        )
        ai_status = ai_result.ai_status
        ai_analysis_summary = ai_result.ai_analysis_summary
        ai_analysis_errors = ai_result.ai_analysis_errors
        ai_analysis_response_times = ai_result.ai_analysis_response_times
        ai_analysis_response_time_over_time = ai_result.ai_analysis_response_time_over_time
        ai_analysis_throughput = ai_result.ai_analysis_throughput
        ai_analysis_latency = ai_result.ai_analysis_latency
        ai_analysis_error_rate = ai_result.ai_analysis_error_rate
        ai_analysis_codes_per_second = ai_result.ai_analysis_codes_per_second
        ai_analysis_transactions_per_second = ai_result.ai_analysis_transactions_per_second
        ai_analysis_active_threads = ai_result.ai_analysis_active_threads
        ai_analysis_redirects = ai_result.ai_analysis_redirects
        ai_conclusions = ai_result.ai_conclusions
        ai_recommendations = ai_result.ai_recommendations

        # ===== CREAR REGISTRO EN BD =====
        execution = TestExecution(
            id=uuid.uuid4(),
            user_id=current_user.id,
            name=name,
            description=description,
            jtl_filename=original_filenames[0],

            # v2.0 metadata
            client=client if client else None,
            client_id=uuid.UUID(client_id) if client_id else None,
            project=project if project else None,
            test_type=test_type,
            metric_unit=metric_unit,
            jtl_filenames=original_filenames if len(original_filenames) > 1 else None,
            acceptance_criteria_json=acceptance_criteria_dict,

            # Info del archivo — strip tzinfo for TIMESTAMP WITHOUT TIME ZONE column
            # (values are already in COT from jtl_parser, just remove the tz marker)
            start_time=metrics.get('start_time').replace(tzinfo=None) if hasattr(metrics.get('start_time'), 'tzinfo') and metrics.get('start_time') is not None else metrics.get('start_time'),
            end_time=metrics.get('end_time').replace(tzinfo=None) if hasattr(metrics.get('end_time'), 'tzinfo') and metrics.get('end_time') is not None else metrics.get('end_time'),
            duration_seconds=float(metrics.get('duration_seconds', 0)),

            # Metricas basicas
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

            # Metricas adicionales
            avg_latency=float(metrics.get('avg_latency', 0)),
            kb_per_sec_received=float(metrics.get('kb_per_sec_received', 0)),
            kb_per_sec_sent=float(metrics.get('kb_per_sec_sent', 0)),

            # Redirecciones v2.0
            total_redirects=int(metrics.get('total_redirects', 0)),
            redirect_labels=metrics.get('redirect_labels', None),

            # Analisis IA
            ai_analysis_summary=ai_analysis_summary,
            ai_analysis_errors=ai_analysis_errors,
            ai_analysis_response_times=ai_analysis_response_times,
            ai_analysis_response_time_over_time=ai_analysis_response_time_over_time,
            ai_analysis_throughput=ai_analysis_throughput,
            ai_analysis_latency=ai_analysis_latency,
            ai_analysis_error_rate=ai_analysis_error_rate,
            ai_analysis_codes_per_second=ai_analysis_codes_per_second,
            ai_analysis_transactions_per_second=ai_analysis_transactions_per_second,
            ai_analysis_active_threads=ai_analysis_active_threads,
            ai_analysis_redirects=ai_analysis_redirects if ai_analysis_redirects else None,
            ai_conclusions=ai_conclusions,
            ai_recommendations=ai_recommendations,

            execution_date=datetime.utcnow(),
        )

        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        # N3.4: analisis IA individual de las transacciones marcadas en el panel.
        # Va DESPUES del pipeline de 12 pasos y de guardar la ejecucion (necesita
        # su id). Sin transacciones marcadas no hace nada: ni IA ni escrituras.
        # No lanza nunca; si falla, la ejecucion ya esta guardada igualmente.
        try:
            await analyze_critical_transactions(
                db=db,
                execution_id=execution.id,
                summary_df=parser.get_summary_table_data(),
                acceptance_criteria=acceptance_criteria_dict,
                test_type=test_type,
            )
        except Exception as txn_err:
            logger.error(f"N3.4: analisis por transaccion omitido: {txn_err}")

        # Update AI usage counters in DB (non-fatal)
        try:
            await update_ai_usage_in_db(db)
            await db.commit()
        except Exception as usage_err:
            logger.warning(f"Could not update AI usage counters: {usage_err}")

        logger.info(f"Ejecucion guardada: {execution.id} (ai_status: {ai_status['provider']}, success={ai_status['success']})")
        response = TestExecutionResponse.model_validate(execution).model_dump(mode='json')
        response['ai_status'] = ai_status
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error procesando JTL: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando archivo JTL: {str(e)}",
        )


@router.get("/executions", response_model=List[TestExecutionResponse])
async def list_executions(
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Listar ejecuciones: admin ve todo, analyst solo sus clientes asignados"""
    if current_user.role == 'admin':
        query = select(TestExecution).order_by(desc(TestExecution.created_at))
        if client_id:
            try:
                cid = uuid.UUID(client_id)
                query = query.where(TestExecution.client_id == cid)
            except (ValueError, AttributeError):
                pass
    else:
        # Non-admin: only executions from assigned clients
        assigned_ids = await _get_assigned_client_ids(db, current_user)
        if not assigned_ids:
            return []
        query = select(TestExecution).where(
            TestExecution.client_id.in_(assigned_ids)
        ).order_by(desc(TestExecution.created_at))
        # Allow further filtering by specific client_id (must be in assigned list)
        if client_id:
            try:
                cid = uuid.UUID(client_id)
                if cid in assigned_ids:
                    query = select(TestExecution).where(
                        TestExecution.client_id == cid
                    ).order_by(desc(TestExecution.created_at))
                else:
                    return []
            except (ValueError, AttributeError):
                pass

    result = await db.execute(query)
    executions = result.scalars().all()
    return executions


@router.delete("/executions/{execution_id}")
async def delete_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    # SEC-1: borrar ejecuciones queda restringido a admin. Antes bastaba con
    # tener el cliente asignado, asi que un viewer podia borrarlas.
    current_user: User = Depends(require_role(["admin"])),
):
    """Eliminar una ejecucion (solo admin, con verificacion de acceso)"""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID de ejecucion invalido")

    result = await db.execute(
        select(TestExecution).where(TestExecution.id == exec_uuid)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    await _check_execution_access(db, current_user, execution)

    await db.execute(
        delete(TestExecution).where(TestExecution.id == exec_uuid)
    )
    await db.commit()
    logger.info(f"Ejecucion eliminada: {exec_uuid} por usuario {current_user.username}")
    return {"success": True, "message": "Ejecucion eliminada correctamente"}


@router.get("/executions/{execution_id}", response_model=TestExecutionResponse)
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Obtener detalles de una ejecucion (con verificacion de acceso)"""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail=f"ID de ejecucion invalido: '{execution_id}'",
        )

    result = await db.execute(
        select(TestExecution).where(TestExecution.id == exec_uuid)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    await _check_execution_access(db, current_user, execution)

    return execution


@router.get("/executions/{execution_id}/transaction-analyses")
async def get_transaction_analyses(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """N3.4: analisis IA por transaccion critica de una ejecucion.

    Lo consumen los exports (N3.5) y el dashboard. Devuelve lista vacia si la
    ejecucion no tenia transacciones marcadas.
    """
    try:
        eid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(400, "execution_id invalido")

    result = await db.execute(
        select(TransactionAnalysis)
        .where(TransactionAnalysis.execution_id == eid)
        .order_by(TransactionAnalysis.sort_order)
    )
    rows = result.scalars().all()
    # N4.7: una transaccion con mini-informe ya generado tiene que verse en la
    # pantalla aunque no figure como critica — el premarcado es del upload y hay
    # ejecuciones anteriores a N3.4 que no lo tienen.
    con_informe = (await db.execute(
        select(TransactionChartAnalysis.label)
        .where(TransactionChartAnalysis.execution_id == eid)
        .distinct()
    )).scalars().all()
    return {
        "report_labels": sorted(set(con_informe)),
        "transaction_analyses": [
            {
                "id": str(r.id),
                "label": r.label,
                "is_critical": r.is_critical,
                "marked_by": r.marked_by,
                "metrics": r.metrics_json,
                "ai_analysis": r.ai_analysis,
                "ai_analysis_updated_at": r.ai_analysis_updated_at.isoformat() if r.ai_analysis_updated_at else None,
                "sort_order": r.sort_order,
            }
            for r in rows
        ],
        "count": len(rows),
    }


def _parse_execution_df(execution):
    """N4.6: el DataFrame del JTL de una ejecucion, para las series por
    transaccion. Extraido tal cual del endpoint de N4.4, que ahora lo llama,
    para no tener dos copias de la misma busqueda de archivo."""
    upload_dir = Path("/app/uploads")
    jtl_filenames = execution.jtl_filenames or [execution.jtl_filename]
    found_paths: List[str] = []
    for filename in jtl_filenames:
        matches = list(upload_dir.glob(f"*{filename}"))
        if matches:
            found_paths.append(str(matches[0]))
    if not found_paths:
        raise HTTPException(
            404,
            f"No se encuentra el JTL de esta ejecucion ({', '.join(str(f) for f in jtl_filenames)}). "
            f"Las series por transaccion se calculan desde el archivo original.",
        )
    try:
        if len(found_paths) == 1:
            parser = JTLParser(found_paths[0])
            parser.parse()
        else:
            _, _, parser = JTLParser.parse_multiple(found_paths)
    except Exception as e:
        logger.exception(f"N4.4: fallo el parseo del JTL de {execution.id}")
        raise HTTPException(400, f"No se pudo parsear el JTL de esta ejecucion: {e}")

    df = parser.df_main if parser.df_main is not None and len(parser.df_main) > 0 else parser.df
    if df is None or len(df) == 0:
        raise HTTPException(400, "El JTL de esta ejecucion no tiene muestras utilizables")
    return parser, df


@router.get("/executions/{execution_id}/transaction-charts")
async def get_transaction_charts(
    execution_id: str,
    label: str = Query(..., description="Nombre exacto de la transaccion"),
    interval_seconds: int = Query(DEFAULT_INTERVAL_SECONDS, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """N4.4: las 5 series temporales de UNA transaccion, bajo demanda.

    Vive aparte de /charts a proposito (diagnostico 036 §3): meter estas series
    en el endpoint general le sumaria +1,26 MB en CADA apertura del dashboard,
    para un dato que solo consumen las transacciones marcadas como criticas.
    Aqui se calcula solo la transaccion pedida (~500 KB) y solo cuando se pide.
    """
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(400, f"ID de ejecucion invalido: '{execution_id}'")

    result = await db.execute(select(TestExecution).where(TestExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Ejecucion no encontrada")

    await _check_execution_access(db, current_user, execution)

    # Mismo criterio de busqueda que /charts, pero sin tocarlo: las series se
    # calculan desde el JTL original, que puede haberse borrado del disco.
    t0 = time.perf_counter()
    _, df = _parse_execution_df(execution)

    try:
        series = build_transaction_series(df, label, interval_seconds=interval_seconds)
    except ValueError as e:
        disponibles = ", ".join(available_labels(df)) or "ninguna"
        raise HTTPException(404, f"{e}. Transacciones disponibles: {disponibles}")

    series["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
    logger.info(
        f"N4.4: series de '{label}' para {exec_uuid} en {series['elapsed_ms']} ms "
        f"(bucket {series['interval_seconds']}s, {series['sample_count']} muestras)"
    )
    return series


async def _execution_or_404(db, current_user, execution_id: str):
    """N4.6: valida el id, carga la ejecucion y comprueba el acceso."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(400, f"ID de ejecucion invalido: '{execution_id}'")
    result = await db.execute(select(TestExecution).where(TestExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Ejecucion no encontrada")
    await _check_execution_access(db, current_user, execution)
    return execution


@router.post("/executions/{execution_id}/transaction-report")
async def generate_transaction_report_endpoint(
    execution_id: str,
    label: str = Query(..., description="Nombre exacto de la transaccion"),
    sections: Optional[str] = Query(None, description="N4.6b: secciones a regenerar, separadas por coma. Vacio = las 8"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """N4.6: genera las 8 secciones IA del mini-informe de UNA transaccion.

    Bajo demanda y fuera de /upload: son 8 llamadas en serie (~90 s) que solo
    valen para las transacciones que se abren. Idempotente — regenerar
    reescribe las mismas 8 filas. El progreso se sigue con el GET de esta misma
    ruta, que cuenta las filas ya persistidas.
    """
    pedidas: Optional[List[str]] = None
    if sections:
        pedidas = [s.strip() for s in sections.split(",") if s.strip()]
        invalidas = [s for s in pedidas if s not in SECTIONS]
        if invalidas:
            raise HTTPException(400, f"Secciones desconocidas: {', '.join(invalidas)}. Validas: {', '.join(SECTIONS)}")

    execution = await _execution_or_404(db, current_user, execution_id)
    parser, df = _parse_execution_df(execution)

    try:
        series = build_transaction_series(df, label)
    except ValueError as e:
        disponibles = ", ".join(available_labels(df)) or "ninguna"
        raise HTTPException(404, f"{e}. Transacciones disponibles: {disponibles}")

    # Mismas metricas por label que ve el panel de N3.4, sin re-parsear el JTL.
    summary_df = parser.get_summary_table_data(df)
    fila = {str(r["label"]): r for _, r in summary_df.iterrows()}.get(label)
    if fila is None:
        raise HTTPException(404, f"La transaccion '{label}' no tiene metricas en este JTL")
    metrics = {k: fila[k] for k in ("muestras", "promedio", "mediana", "min", "p90", "p95", "p99", "max", "errores", "tasa_error", "rendimiento")}

    t0 = time.perf_counter()
    counters = await generate_transaction_report(
        db=db, execution_id=execution.id, label=label, metrics=metrics,
        series=series, test_type=execution.test_type or "load", sections=pedidas,
    )
    counters["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
    counters["label"] = label
    # Las 8 llamadas cuentan contra el cupo igual que las del upload.
    try:
        await update_ai_usage_in_db(db)
        await db.commit()
    except Exception as usage_err:
        logger.warning(f"N4.6: contadores de IA sin sincronizar: {usage_err}")
    logger.info(f"N4.6: mini-informe de '{label}' para {execution.id} en {counters['elapsed_ms']} ms {counters}")
    return counters


@router.get("/executions/{execution_id}/transaction-report")
async def get_transaction_report(
    execution_id: str,
    label: str = Query(..., description="Nombre exacto de la transaccion"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """N4.6: las secciones ya persistidas del mini-informe, con su progreso.

    `progress.done` cuenta filas CON texto sobre las 8 de SECTIONS: es el
    indicador que consumira N4.7 sondeando esta ruta mientras corre el POST.
    """
    execution = await _execution_or_404(db, current_user, execution_id)
    rows = (await db.execute(
        select(TransactionChartAnalysis)
        .where(TransactionChartAnalysis.execution_id == execution.id,
               TransactionChartAnalysis.label == label)
        .order_by(TransactionChartAnalysis.sort_order)
    )).scalars().all()

    con_texto = sum(1 for r in rows if r.ai_analysis)
    return {
        "label": label,
        "sections": [
            {
                "section": r.section, "ai_analysis": r.ai_analysis, "is_edited": r.is_edited,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "sort_order": r.sort_order,
            }
            for r in rows
        ],
        "progress": {
            "done": con_texto, "total": len(SECTIONS), "persisted": len(rows),
            "pending": [s for s in SECTIONS if s not in {r.section for r in rows if r.ai_analysis}],
        },
    }


class TransactionSectionUpdate(BaseModel):
    ai_analysis: str


@router.put("/executions/{execution_id}/transaction-report/{section}")
async def update_transaction_report_section(
    execution_id: str,
    section: str,
    payload: TransactionSectionUpdate,
    label: str = Query(..., description="Nombre exacto de la transaccion"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """N4.7: editar a mano UNA seccion del mini-informe.

    Marca `is_edited` para que se distinga del texto de la IA, igual que hace el
    consolidado desde F5. Si la seccion no tiene fila todavia se crea: editar
    nunca debe fallar por un texto que la IA no llego a generar.
    """
    if section not in SECTIONS:
        raise HTTPException(400, f"Seccion desconocida: {section}. Validas: {', '.join(SECTIONS)}")

    execution = await _execution_or_404(db, current_user, execution_id)
    row = (await db.execute(
        select(TransactionChartAnalysis).where(
            TransactionChartAnalysis.execution_id == execution.id,
            TransactionChartAnalysis.label == label,
            TransactionChartAnalysis.section == section,
        )
    )).scalar_one_or_none()

    ahora = datetime.utcnow()
    if row is None:
        # `generated_at` lo estampa el default de la columna aunque se pase None:
        # el texto escrito a mano se distingue por `is_edited`, que es lo que mira
        # la pantalla para no atribuirselo a la IA.
        row = TransactionChartAnalysis(
            execution_id=execution.id, label=label, section=section,
            sort_order=SECTIONS.index(section),
        )
        db.add(row)
    row.ai_analysis = payload.ai_analysis
    row.is_edited = True
    row.ai_analysis_updated_at = ahora
    await db.commit()

    logger.info(f"N4.7: seccion '{section}' de '{label}' editada a mano ({len(payload.ai_analysis)} chars)")
    return {"section": section, "label": label, "is_edited": True,
            "ai_analysis_updated_at": ahora.isoformat()}


@router.get("/executions/{execution_id}/charts", response_model=ChartData)
async def get_execution_charts(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Obtener datos de graficos para una ejecucion (con verificacion de acceso)"""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail=f"ID de ejecucion invalido: '{execution_id}'",
        )

    result = await db.execute(
        select(TestExecution).where(TestExecution.id == exec_uuid)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    await _check_execution_access(db, current_user, execution)

    logger.info(f"Buscando archivo(s) JTL para ejecucion {exec_uuid}")

    # Buscar archivos JTL - soportar multi-JTL
    upload_dir = Path("/app/uploads")
    jtl_filenames = execution.jtl_filenames or [execution.jtl_filename]
    found_paths: List[str] = []

    for filename in jtl_filenames:
        matches = list(upload_dir.glob(f"*{filename}"))
        if matches:
            found_paths.append(str(matches[0]))

    if not found_paths:
        raise HTTPException(
            status_code=404,
            detail=f"Archivos JTL no encontrados: {jtl_filenames}",
        )

    logger.info(f"Archivos JTL encontrados: {len(found_paths)}")

    try:
        # Parse: single vs multi
        if len(found_paths) == 1:
            parser = JTLParser(found_paths[0])
            df, _ = parser.parse()
        else:
            df, _, parser = JTLParser.parse_multiple(found_paths)

        logger.info(f"DataFrame parseado: {len(df)} filas")

        # Obtener TODOS los datos de graficos
        charts_data = parser.get_all_charts_data(interval_seconds=10)

        # Timeline general
        tl_df = charts_data['timeline']
        timeline = [
            TimelineData(
                timestamp=row['timestamp'].isoformat(),
                avg_response_time=float(row['avg_response_time']),
                request_count=int(row['throughput']),
            )
            for _, row in tl_df.iterrows()
        ]

        # By label stats - principales
        summary_df = parser.get_summary_table_data()
        by_label = []
        for _, row in summary_df.iterrows():
            by_label.append(LabelStats(
                label=row['label'],
                count=int(row['muestras']),
                avg_time=float(row['promedio']),
                min_time=float(row['min']),
                max_time=float(row['max']),
                success_count=int(row['muestras'] - row['errores']),
                error_count=int(row['errores']),
                error_rate=float(row['tasa_error']),
                p90=float(row['p90']),
                p95=float(row['p95']),
                p99=float(row['p99']),
                throughput=float(row['rendimiento']),
                kb_received=float(row.get('kb_received', 0)),
                kb_sent=float(row.get('kb_sent', 0)),
                is_redirect=False,
            ))

        # By label stats - redirecciones
        by_label_redirects = []
        redirect_summary = parser.get_redirect_summary_data()
        if redirect_summary is not None and len(redirect_summary) > 0:
            for _, row in redirect_summary.iterrows():
                by_label_redirects.append(LabelStats(
                    label=row['label'],
                    count=int(row['muestras']),
                    avg_time=float(row['promedio']),
                    min_time=float(row['min']),
                    max_time=float(row['max']),
                    success_count=int(row['muestras'] - row['errores']),
                    error_count=int(row['errores']),
                    error_rate=float(row['tasa_error']),
                    p90=float(row['p90']),
                    p95=float(row['p95']),
                    p99=float(row['p99']),
                    throughput=float(row['rendimiento']),
                    kb_received=float(row.get('kb_received', 0)),
                    kb_sent=float(row.get('kb_sent', 0)),
                    is_redirect=True,
                ))

        # Response codes distribution
        codes_df = parser.get_response_code_distribution()
        response_codes = {
            str(row['responseCode']): int(row['count'])
            for _, row in codes_df.iterrows()
        }

        # Response Times por Transaccion
        response_times_by_label = []
        for label_df in charts_data['response_times_by_label']:
            has_max = 'value_max' in label_df.columns  # GRAF1-A
            for _, row in label_df.iterrows():
                response_times_by_label.append(TimeSeriesPoint(
                    timestamp=row['timestamp'].isoformat(),
                    value=float(row['value']),
                    value_max=float(row['value_max']) if has_max else None,
                    label=row['label'],
                ))

        # Throughput Timeline
        throughput_timeline = [
            TimeSeriesPoint(
                timestamp=row['timestamp'].isoformat(),
                value=float(row['throughput']),
            )
            for _, row in tl_df.iterrows()
        ]

        # Latency Timeline
        latency_timeline = [
            TimeSeriesPoint(
                timestamp=row['timestamp'].isoformat(),
                value=float(row['avg_latency']),
            )
            for _, row in tl_df.iterrows()
        ]

        # Error Rate Timeline
        error_rate_timeline = [
            TimeSeriesPoint(
                timestamp=row['timestamp'].isoformat(),
                value=float(row['error_rate']),
            )
            for _, row in tl_df.iterrows()
        ]

        # Active Threads Timeline
        active_threads_timeline = [
            TimeSeriesPoint(
                timestamp=row['timestamp'].isoformat(),
                value=float(row['active_threads']),
            )
            for _, row in tl_df.iterrows()
        ]

        # Response Codes per Second
        codes_per_second = []
        for code_df in charts_data['codes_per_second']:
            for _, row in code_df.iterrows():
                codes_per_second.append(TimeSeriesPoint(
                    timestamp=row['timestamp'].isoformat(),
                    value=float(row['value']),
                    code=row['code'],
                ))

        # TPS por Label
        tps_by_label = []
        for tps_df in charts_data['tps_by_label']:
            for _, row in tps_df.iterrows():
                tps_by_label.append(TimeSeriesPoint(
                    timestamp=row['timestamp'].isoformat(),
                    value=float(row['value']),
                    label=row['label'],
                ))

        # KNX-02: Error detail — real error codes per transaction from JTL
        error_detail = []
        error_df = parser.df[~parser.df['success']].copy() if parser.df is not None else None
        if error_df is not None and len(error_df) > 0:
            error_grouped = error_df.groupby(['label', 'responseCode']).size().reset_index(name='count')
            for _, row in error_grouped.iterrows():
                error_detail.append(ErrorDetail(
                    label=row['label'],
                    code=str(row['responseCode']),
                    count=int(row['count']),
                ))

        # Totales
        total_main = len(parser.df_main) if parser.df_main is not None else len(df)
        total_all = len(df)
        has_redirects = len(by_label_redirects) > 0

        logger.info(f"Charts generados para {exec_uuid}")

        return ChartData(
            timeline=timeline,
            by_label=by_label,
            by_label_redirects=by_label_redirects,
            response_codes=response_codes,
            error_detail=error_detail,
            response_times_by_label=response_times_by_label,
            throughput_timeline=throughput_timeline,
            latency_timeline=latency_timeline,
            error_rate_timeline=error_rate_timeline,
            codes_per_second=codes_per_second,
            tps_by_label=tps_by_label,
            active_threads_timeline=active_threads_timeline,
            total_main_samples=total_main,
            total_all_samples=total_all,
            has_redirects=has_redirects,
        )

    except Exception as e:
        logger.exception(f"Error generando charts para {exec_uuid}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generando datos de graficos: {str(e)}",
        )


# ====== ENDPOINT PARA ACTUALIZAR ANALISIS ======

class UpdateAnalysisRequest(BaseModel):
    """Modelo para actualizar analisis"""
    ai_analysis_summary: Optional[str] = None
    ai_analysis_errors: Optional[str] = None
    ai_analysis_response_times: Optional[str] = None
    ai_analysis_response_time_over_time: Optional[str] = None
    ai_analysis_throughput: Optional[str] = None
    ai_analysis_latency: Optional[str] = None
    ai_analysis_error_rate: Optional[str] = None
    ai_analysis_codes_per_second: Optional[str] = None
    ai_analysis_transactions_per_second: Optional[str] = None
    ai_analysis_active_threads: Optional[str] = None
    ai_analysis_redirects: Optional[str] = None
    ai_recommendations: Optional[str] = None
    ai_conclusions: Optional[str] = None


@router.put("/executions/{execution_id}/analysis")
async def update_analysis(
    execution_id: str,
    data: UpdateAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Actualizar analisis IA editados (con verificacion de acceso)"""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail=f"ID de ejecucion invalido: '{execution_id}'",
        )

    result = await db.execute(
        select(TestExecution).where(TestExecution.id == exec_uuid)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    await _check_execution_access(db, current_user, execution)

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    if update_data:
        await db.execute(
            update(TestExecution)
            .where(TestExecution.id == exec_uuid)
            .values(**update_data)
        )
        await db.commit()
        logger.info(f"Analisis actualizado para {exec_uuid} ({len(update_data)} campos)")

    return {"success": True, "message": "Analisis actualizado correctamente"}


# ====== KNX-17: CAPACITY ANALYSIS ENDPOINTS ======

@router.get("/executions/{execution_id}/capacity")
async def get_capacity_analysis(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get capacity analysis data for an execution."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(400, "ID invalido")

    result = await db.execute(select(TestExecution).where(TestExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Ejecucion no encontrada")

    await _check_execution_access(db, current_user, execution)

    data = json.loads(execution.capacity_analysis_json or '{"resources": [], "enabled": false}')
    return data


@router.put("/executions/{execution_id}/capacity")
async def update_capacity_analysis(
    execution_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update capacity analysis data for an execution."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(400, "ID invalido")

    result = await db.execute(select(TestExecution).where(TestExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Ejecucion no encontrada")

    await _check_execution_access(db, current_user, execution)

    await db.execute(
        update(TestExecution)
        .where(TestExecution.id == exec_uuid)
        .values(capacity_analysis_json=json.dumps(data))
    )
    await db.commit()
    return {"status": "ok"}
