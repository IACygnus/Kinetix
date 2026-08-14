"""
Pipeline publico de analisis IA del JTL.

Sprint 2.5d.2 — refactorizado desde upload.py para que /upload y
/analyze-with-ai compartan la misma logica de analisis IA.

Dos capas:
- ``_run_ai_and_verdict(parser, metrics, ...)`` — el bloque AI + verdict movido
  VERBATIM desde upload.py (lineas ~309-631). /upload delega aqui sin cambiar
  su parsing (formato/multi-archivo) ni su construccion de TestExecution.
- ``run_jtl_analysis_pipeline(test_execution, jtl_path, db, ...)`` — wrapper
  publico para /analyze-with-ai: parsea un unico JTL, popula las metricas
  basicas del TestExecution y mapea los campos ai_* del analisis. NO hace commit.

Este modulo NO modifica gemini.py: solo importa y llama sus funciones.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.test import TestExecution
from app.services.jtl.jtl_parser import JTLParser
from app.services.ai.gemini import (
    FallbackAnalyzer,
    compute_verdict,
    get_gemini_analyzer,
    load_ai_config_from_db,
    prepare_insights_for_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class AIAnalysisResult:
    """Resultado del bloque AI + verdict (los 13 campos ai_* + status)."""

    ai_analysis_summary: str = ""
    ai_analysis_errors: str = ""
    ai_analysis_response_times: str = ""
    ai_analysis_response_time_over_time: str = ""
    ai_analysis_throughput: str = ""
    ai_analysis_latency: str = ""
    ai_analysis_error_rate: str = ""
    ai_analysis_codes_per_second: str = ""
    ai_analysis_transactions_per_second: str = ""
    ai_analysis_active_threads: str = ""
    ai_analysis_redirects: str = ""
    ai_conclusions: str = ""
    ai_recommendations: str = ""
    ai_status: Dict[str, Any] = field(default_factory=dict)


async def run_ai_and_verdict(
    parser: Any,
    metrics: Dict[str, Any],
    test_type: str,
    acceptance_criteria_dict: Optional[Dict[str, Any]],
    metric_unit: str,
    db: AsyncSession,
) -> AIAnalysisResult:
    """Bloque AI (12 secciones + sintesis) + verdict, movido VERBATIM de upload.py.

    Args:
        parser: instancia de JTLParser (o equivalente con get_summary_table_data,
            get_all_charts_data, get_response_code_distribution,
            get_redirect_summary_data y .df) YA parseada.
        metrics: dict de metricas calculado por parser.parse().
        test_type: load/stress/...
        acceptance_criteria_dict: criterios (se MUTAN in-place con 'verdict' y
            'verdicts_per_transaction') o None.
        metric_unit: TPS/UVC.
        db: sesion async (para load_ai_config_from_db).

    Returns:
        AIAnalysisResult con los 13 campos ai_* + ai_status. acceptance_criteria_dict
        se muta in-place (el caller mantiene la referencia).
    """
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

        # 3-10. Graficos individuales
        logger.info("[3-9/12] Analizando 7 graficos...")   # UI-2: 8 -> 7 (sin Response Time Over Time)

        # Response Times por Transaccion
        rt_lines = []
        for _, row in summary_df.iterrows():
            # GRAF1-A: el maximo ya viajaba, pero pasaba desapercibido junto al promedio.
            ratio_max = (row['max'] / row['promedio']) if row['promedio'] > 0 else 0
            pico = f" [PICO: max {ratio_max:.0f}x el promedio]" if ratio_max >= 10 else ""
            rt_lines.append(
                f"- {row['label']}: promedio {row['promedio']:.0f}ms, "
                f"P90 {row['p90']:.0f}ms, P95 {row['p95']:.0f}ms, "
                f"P99 {row['p99']:.0f}ms, min {row['min']:.0f}ms, max {row['max']:.0f}ms{pico}"
            )
        logger.info(f"Response times: enviando {len(rt_lines)} transacciones a Gemini")
        ai_analysis_response_times = gemini.analyze_chart(
            'response_times', "\n".join(rt_lines), test_type=test_type, insights=insights,
            test_date=test_date, metric_unit=metric_unit,
        )
        if ai_analysis_response_times is None:
            logger.info("Using FALLBACK for response_times")
            ai_analysis_response_times = fallback.analyze_chart("response_times", stats_summary)

        # UI-2: la grafica "Response Time Over Time" se retiro de pantalla y de los
        # exports, asi que su seccion de IA ya no se genera (una llamada menos por
        # analisis). El campo queda vacio para ejecuciones nuevas; lo ya guardado en
        # DB no se toca. Se elimina tambien el get_all_charts_data() que solo servia
        # para contar los puntos de esa serie.

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

    return AIAnalysisResult(
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
        ai_conclusions=ai_conclusions,
        ai_recommendations=ai_recommendations,
        ai_status=ai_status,
    )


def _strip_tz(dt):
    """Quita tzinfo (las columnas son TIMESTAMP WITHOUT TIME ZONE)."""
    if dt is not None and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


async def run_jtl_analysis_pipeline(
    test_execution: TestExecution,
    jtl_path: str,
    db: AsyncSession,
    acceptance_criteria: Optional[Dict[str, Any]] = None,
) -> TestExecution:
    """Pipeline publico de analisis IA para un UNICO JTL (Sprint 2.5d.2).

    Usado por /analyze-with-ai sobre el JTL persistido de una PerformanceExecution.
    Parsea el JTL, popula las metricas basicas del ``test_execution`` y mapea los
    13 campos ai_*. NO hace commit (el caller decide).

    Args:
        test_execution: instancia YA CREADA con campos basicos (user_id, name,
            client, project, test_type, jtl_filename, start/end_time). Se POPULA.
        jtl_path: ruta absoluta al JTL CSV.
        db: sesion async.
        acceptance_criteria: criterios opcionales (compute_verdict los usa).

    Returns:
        El mismo ``test_execution`` populado.

    Raises:
        Exception si el JTL no se puede parsear.
    """
    from datetime import datetime as _datetime

    # === 1. Parse JTL ===
    parser = JTLParser(jtl_path)
    df, metrics = parser.parse()
    logger.info(
        f"[analysis_pipeline] {len(df)} muestras, "
        f"{metrics.get('total_main_samples', 0)} principales"
    )

    # === 2. Popular metricas basicas (mismo mapeo que upload.py) ===
    test_execution.start_time = _strip_tz(metrics.get('start_time'))
    test_execution.end_time = _strip_tz(metrics.get('end_time'))
    test_execution.duration_seconds = float(metrics.get('duration_seconds', 0))
    test_execution.total_requests = int(metrics['total_requests'])
    test_execution.total_errors = int(metrics['total_errors'])
    test_execution.error_rate = float(metrics['error_rate'])
    test_execution.avg_response_time = float(metrics['avg_response_time'])
    test_execution.median_response_time = float(metrics.get('median_response_time', 0))
    test_execution.min_response_time = float(metrics['min_response_time'])
    test_execution.max_response_time = float(metrics['max_response_time'])
    test_execution.p50_response_time = float(metrics['p50_response_time'])
    test_execution.p90_response_time = float(metrics['p90_response_time'])
    test_execution.p95_response_time = float(metrics['p95_response_time'])
    test_execution.p99_response_time = float(metrics['p99_response_time'])
    test_execution.throughput = float(metrics['throughput'])
    test_execution.avg_latency = float(metrics.get('avg_latency', 0))
    test_execution.kb_per_sec_received = float(metrics.get('kb_per_sec_received', 0))
    test_execution.kb_per_sec_sent = float(metrics.get('kb_per_sec_sent', 0))
    test_execution.total_redirects = int(metrics.get('total_redirects', 0))
    test_execution.redirect_labels = metrics.get('redirect_labels', None)

    # === 3. Bloque AI + verdict (capa compartida con /upload) ===
    acceptance_criteria_dict = acceptance_criteria
    result = await run_ai_and_verdict(
        parser=parser,
        metrics=metrics,
        test_type=getattr(test_execution, 'test_type', None) or 'load',
        acceptance_criteria_dict=acceptance_criteria_dict,
        metric_unit=getattr(test_execution, 'metric_unit', None) or 'TPS',
        db=db,
    )

    # === 4. Mapear campos ai_* ===
    test_execution.ai_analysis_summary = result.ai_analysis_summary
    test_execution.ai_analysis_errors = result.ai_analysis_errors
    test_execution.ai_analysis_response_times = result.ai_analysis_response_times
    test_execution.ai_analysis_response_time_over_time = result.ai_analysis_response_time_over_time
    test_execution.ai_analysis_throughput = result.ai_analysis_throughput
    test_execution.ai_analysis_latency = result.ai_analysis_latency
    test_execution.ai_analysis_error_rate = result.ai_analysis_error_rate
    test_execution.ai_analysis_codes_per_second = result.ai_analysis_codes_per_second
    test_execution.ai_analysis_transactions_per_second = result.ai_analysis_transactions_per_second
    test_execution.ai_analysis_active_threads = result.ai_analysis_active_threads
    test_execution.ai_analysis_redirects = result.ai_analysis_redirects if result.ai_analysis_redirects else None
    test_execution.ai_conclusions = result.ai_conclusions
    test_execution.ai_recommendations = result.ai_recommendations

    if acceptance_criteria_dict is not None:
        test_execution.acceptance_criteria_json = acceptance_criteria_dict

    if not getattr(test_execution, 'execution_date', None):
        test_execution.execution_date = _datetime.utcnow()

    return test_execution
