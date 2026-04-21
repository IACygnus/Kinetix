"""
Endpoints de JTL Upload y Analisis - v2.0
Multi-JTL upload, test types, redirect separation, enhanced Gemini AI
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, status
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
from app.core.security import get_current_active_user
from app.services.jtl.jtl_parser import JTLParser, validate_jtl_compatibility
from app.services.ai.gemini import get_gemini_analyzer, prepare_insights_for_prompt, FallbackAnalyzer, load_ai_config_from_db, update_ai_usage_in_db, compute_verdict
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

        # ===== AI STATUS TRACKING =====
        ai_status = {"provider": "fallback", "model": None, "success": False, "error": None}

        # ===== DEFAULTS — AI fields start empty =====
        ai_analysis_summary = ""
        ai_analysis_errors = ""
        ai_analysis_response_times = ""
        ai_analysis_response_time_over_time = ""
        ai_analysis_throughput = ""
        ai_analysis_latency = ""
        ai_analysis_error_rate = ""
        ai_analysis_codes_per_second = ""
        ai_analysis_transactions_per_second = ""
        ai_analysis_active_threads = ""
        ai_analysis_redirects = ""
        ai_conclusions = ""
        ai_recommendations = ""

        # ===== ANALISIS IA (non-fatal) =====
        # If anything here crashes, we still save the execution with empty AI fields.
        try:
            # Load AI config from DB (provider, model, api_key)
            ai_conf = await load_ai_config_from_db(db)
            if ai_conf.get("limit_reached"):
                ai_status["error"] = f"AI {ai_conf['limit_reached']} limit reached"
                logger.warning(f"AI {ai_conf['limit_reached']} limit reached, skipping AI analysis")
                raise RuntimeError(f"AI {ai_conf['limit_reached']} limit reached")
            gemini = get_gemini_analyzer(
                provider=ai_conf.get("provider", ""),
                model_name=ai_conf.get("model_name", ""),
                api_key=ai_conf.get("api_key", ""),
            )
            ai_status["provider"] = ai_conf.get("provider", "gemini")
            ai_status["model"] = ai_conf.get("model_name", "gemini-2.5-flash")
            fallback = FallbackAnalyzer()

            # Extract test date for executive headers
            test_date = metrics.get('start_time').strftime('%d/%m/%Y') if metrics.get('start_time') else 'N/A'

            # Pre-compute summary data
            summary_df = parser.get_summary_table_data()
            insights = prepare_insights_for_prompt(summary_df)
            logger.info(f"Insights: {insights['total_transactions']} transacciones clasificadas en tiers")

            # Build stats_summary for fallback
            stats_summary = {
                "avg_rt": float(metrics.get('avg_response_time', 0)),
                "min_rt": float(metrics.get('min_response_time', 0)),
                "max_rt": float(metrics.get('max_response_time', 0)),
                "p95": float(metrics.get('p95_response_time', 0)),
                "p99": float(metrics.get('p99_response_time', 0)),
                "throughput": float(metrics.get('throughput', 0)),
                "total_requests": int(metrics.get('total_requests', 0)),
                "total_errors": int(metrics.get('total_errors', 0)),
                "error_rate": float(metrics.get('error_rate', 0)),
                "duration": float(metrics.get('duration_seconds', 0)),
                "avg_latency": float(metrics.get('avg_latency', 0)),
                "kb_received": float(metrics.get('kb_per_sec_received', 0)),
                "kb_sent": float(metrics.get('kb_per_sec_sent', 0)),
                "num_transactions": len(summary_df),
            }

            # 1. Tabla resumen
            logger.info("[1/12] Analizando tabla resumen...")
            ai_analysis_summary = gemini.analyze_summary_table(
                summary_df, metrics, test_type=test_type,
                acceptance_criteria=acceptance_criteria_dict, insights=insights,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_summary is None:
                logger.info("Using FALLBACK for summary_table")
                ai_analysis_summary = fallback.analyze_summary_table(summary_df, insights)
            else:
                ai_status["success"] = True  # Gemini responded for the primary analysis
            time.sleep(1)

            # 2. Errores
            logger.info("[2/12] Analizando errores...")
            errors_for_analysis: List[dict] = []
            error_codes_df = parser.df[~parser.df['success']].copy() if parser.df is not None else None
            if error_codes_df is not None and len(error_codes_df) > 0:
                error_grouped = error_codes_df.groupby(['label', 'responseCode']).size().reset_index(name='count')
                for _, row in error_grouped.iterrows():
                    errors_for_analysis.append({
                        'label': row['label'],
                        'count': int(row['count']),
                        'code': str(row['responseCode']),
                        'message': '',
                    })

            ai_analysis_errors = gemini.analyze_errors(
                errors_for_analysis, metrics['total_requests'], test_type=test_type,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_errors is None:
                logger.info("Using FALLBACK for errors")
                ai_analysis_errors = fallback.analyze_errors(errors_for_analysis, metrics['total_requests'])
            time.sleep(1)

            # 3-10. Graficos individuales
            logger.info("[3-10/12] Analizando 8 graficos...")

            # Response Times por Transaccion
            rt_lines = []
            for _, row in summary_df.iterrows():
                rt_lines.append(
                    f"- {row['label']}: promedio {row['promedio']:.0f}ms, "
                    f"P90 {row['p90']:.0f}ms, P95 {row['p95']:.0f}ms, "
                    f"P99 {row['p99']:.0f}ms, min {row['min']:.0f}ms, max {row['max']:.0f}ms"
                )
            logger.info(f"Response times: enviando {len(rt_lines)} transacciones a Gemini")
            ai_analysis_response_times = gemini.analyze_chart(
                'response_times', "\n".join(rt_lines), test_type=test_type, insights=insights,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_response_times is None:
                logger.info("Using FALLBACK for response_times")
                ai_analysis_response_times = fallback.analyze_chart("response_times", stats_summary)
            time.sleep(1)

            # Response Time Over Time
            charts_data = parser.get_all_charts_data(interval_seconds=10)
            timeline_df = charts_data['timeline']
            rt_over_time_summary = (
                f"Tiempo promedio: {metrics['avg_response_time']:.0f}ms, "
                f"Rango: {metrics['min_response_time']:.0f}ms - {metrics['max_response_time']:.0f}ms, "
                f"P95: {metrics['p95_response_time']:.0f}ms, "
                f"Duracion: {metrics['duration_seconds']:.0f}s, "
                f"Puntos de datos: {len(timeline_df)}"
            )
            ai_analysis_response_time_over_time = gemini.analyze_chart(
                'response_time_over_time', rt_over_time_summary, test_type=test_type,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_response_time_over_time is None:
                logger.info("Using FALLBACK for response_time_over_time")
                ai_analysis_response_time_over_time = fallback.analyze_chart("response_time_over_time", stats_summary)
            time.sleep(1)

            # Throughput
            ai_analysis_throughput = gemini.analyze_chart(
                'throughput',
                f"Throughput promedio: {metrics['throughput']:.2f} req/s, "
                f"Duracion: {metrics['duration_seconds']:.0f}s, "
                f"Total requests: {metrics['total_requests']:,}",
                test_type=test_type,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_throughput is None:
                logger.info("Using FALLBACK for throughput")
                ai_analysis_throughput = fallback.analyze_chart("throughput", stats_summary)
            time.sleep(1)

            # Latency
            ai_analysis_latency = gemini.analyze_chart(
                'latency',
                f"Latencia promedio: {metrics.get('avg_latency', 0):.2f}ms, "
                f"KB/s recibidos: {metrics.get('kb_per_sec_received', 0):.2f}, "
                f"KB/s enviados: {metrics.get('kb_per_sec_sent', 0):.2f}",
                test_type=test_type,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_latency is None:
                logger.info("Using FALLBACK for latency")
                ai_analysis_latency = fallback.analyze_chart("latency", stats_summary)
            time.sleep(1)

            # Error Rate
            ai_analysis_error_rate = gemini.analyze_chart(
                'error_rate',
                f"Tasa de error: {metrics['error_rate']:.2f}% "
                f"({metrics['total_errors']:,} de {metrics['total_requests']:,} requests)",
                test_type=test_type,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_error_rate is None:
                logger.info("Using FALLBACK for error_rate")
                ai_analysis_error_rate = fallback.analyze_chart("error_rate", stats_summary)
            time.sleep(1)

            # Codes per Second
            code_dist = parser.get_response_code_distribution()
            codes_summary = ", ".join(
                f"HTTP {row['responseCode']}: {int(row['count']):,}"
                for _, row in code_dist.iterrows()
            )
            ai_analysis_codes_per_second = gemini.analyze_chart(
                'codes_per_second',
                f"Codigos HTTP: {codes_summary}",
                test_type=test_type,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_codes_per_second is None:
                logger.info("Using FALLBACK for codes_per_second")
                ai_analysis_codes_per_second = fallback.analyze_chart("codes_per_second", stats_summary)
            time.sleep(1)

            # TPS
            tps_lines = []
            for _, row in summary_df.iterrows():
                tps_lines.append(f"- {row['label']}: {row['rendimiento']:.2f} req/s")
            logger.info(f"TPS: enviando {len(tps_lines)} transacciones a Gemini")
            ai_analysis_transactions_per_second = gemini.analyze_chart(
                'transactions_per_second',
                f"TPS total: {metrics['throughput']:.2f} req/s en {len(summary_df)} transacciones:\n" + "\n".join(tps_lines),
                test_type=test_type,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_transactions_per_second is None:
                logger.info("Using FALLBACK for transactions_per_second")
                ai_analysis_transactions_per_second = fallback.analyze_chart("transactions_per_second", stats_summary)
            time.sleep(1)

            # Active Threads
            ai_analysis_active_threads = gemini.analyze_chart(
                'active_threads',
                f"Concurrencia durante {metrics['duration_seconds']:.0f}s de prueba",
                test_type=test_type,
                test_date=test_date, metric_unit=metric_unit,
            )
            if ai_analysis_active_threads is None:
                logger.info("Using FALLBACK for active_threads")
                ai_analysis_active_threads = fallback.analyze_chart("active_threads", stats_summary)
            time.sleep(1)

            logger.info("Analisis individuales completados")

            # 11. Redirecciones (si existen)
            redirect_summary = parser.get_redirect_summary_data()
            if redirect_summary is not None and len(redirect_summary) > 0:
                logger.info("[11/12] Analizando redirecciones...")
                ai_analysis_redirects = gemini.analyze_redirects(
                    redirect_summary, metrics, test_type=test_type,
                    test_date=test_date, metric_unit=metric_unit,
                )
                if ai_analysis_redirects is None:
                    logger.info("Using FALLBACK for redirects")
                    ai_analysis_redirects = fallback.analyze_redirects(
                        int(metrics.get('total_redirects', 0)),
                        int(metrics.get('total_main_samples', metrics['total_requests'])),
                    )
                time.sleep(1)

            # 12. Sintesis: Conclusiones + Recomendaciones
            logger.info("[11-12/12] Sintetizando conclusiones y recomendaciones...")

            ai_conclusions = gemini.generate_conclusions(
                metrics=metrics,
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
                ai_analysis_redirects=ai_analysis_redirects,
                test_type=test_type,
                insights=insights,
                test_date=test_date,
                acceptance_criteria=acceptance_criteria_dict,
                metric_unit=metric_unit,
            )
            if ai_conclusions is None:
                logger.info("Using FALLBACK for conclusions")
                ai_conclusions = fallback.generate_conclusions(stats_summary, acceptance_criteria=acceptance_criteria_dict)
            time.sleep(1)

            ai_recommendations = gemini.generate_recommendations(
                metrics=metrics,
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
                ai_analysis_redirects=ai_analysis_redirects,
                test_type=test_type,
                insights=insights,
                test_date=test_date,
                acceptance_criteria=acceptance_criteria_dict,
                metric_unit=metric_unit,
            )
            if ai_recommendations is None:
                logger.info("Using FALLBACK for recommendations")
                ai_recommendations = fallback.generate_recommendations(stats_summary, acceptance_criteria=acceptance_criteria_dict)

            logger.info("Sintesis completada")

        except Exception as ai_err:
            logger.exception(f"AI analysis failed (non-fatal, execution will be saved without AI): {ai_err}")
            if not ai_status.get("error"):
                ai_status["error"] = str(ai_err)[:200]

        # ===== COMPUTE VERDICT =====
        if acceptance_criteria_dict and not acceptance_criteria_dict.get('raw_text'):
            # P4: If per_scenario criteria exist for this test_type, merge into effective criteria
            per_scenario = acceptance_criteria_dict.get('per_scenario', {})
            effective_criteria = dict(acceptance_criteria_dict)
            # Normalize: match test_type case-insensitively against per_scenario keys
            test_type_lower = (test_type or '').lower().strip()
            for sc_key, sc_vals in per_scenario.items():
                if sc_key.lower().strip() == test_type_lower and isinstance(sc_vals, dict):
                    for k, v in sc_vals.items():
                        if v is not None and v != '':
                            effective_criteria[k] = v
                    break
            verdict = compute_verdict(metrics, effective_criteria)
            acceptance_criteria_dict['verdict'] = verdict
            # KNX-09: Per-transaction verdicts
            from app.services.ai.gemini import compute_per_transaction_verdicts
            per_txn_result = compute_per_transaction_verdicts(summary_df, acceptance_criteria_dict)
            if per_txn_result:
                acceptance_criteria_dict['verdicts_per_transaction'] = per_txn_result.get('verdicts_per_transaction', {})
                # Override global verdict if per-txn is stricter
                acceptance_criteria_dict['verdict'] = per_txn_result.get('verdict', verdict)
            logger.info(f"Verdict computed: {acceptance_criteria_dict['verdict']}")

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
    current_user: User = Depends(get_current_active_user),
):
    """Eliminar una ejecucion (con verificacion de acceso)"""
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
            for _, row in label_df.iterrows():
                response_times_by_label.append(TimeSeriesPoint(
                    timestamp=row['timestamp'].isoformat(),
                    value=float(row['value']),
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
