"""
Export PDF endpoint – thin wrapper around report_generator.
Parses JTL, builds charts + HTML via the shared module, renders PDF with WeasyPrint.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
from typing import List
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import logging

import pandas as pd

from app.db.session import get_db
from app.db.models.test import TestExecution
from app.db.models.client import Client, UserClient
from app.db.models.user import User
from app.core.security import get_current_active_user
from app.services.jtl.jtl_parser import JTLParser
from app.config.chart_config import TEST_TYPE_LABELS
# ExecutionAttachment removed — individual exports no longer include monitoring/evidence
from app.services.export.report_generator import (
    chart_area, chart_multiline, chart_pie, build_pdf_html, MAX_SERIES_SUFFIX,
)
from app.services.export.high_cardinality_strategy import apply_top_n_aggregation

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)


def _find_jtl_files(execution) -> List[str]:
    upload_dir = Path("/app/uploads")
    filenames = execution.jtl_filenames or [execution.jtl_filename]
    found = []
    for fname in filenames:
        matches = list(upload_dir.glob(f"*{fname}"))
        if matches:
            found.append(str(matches[0]))
    return found


def _ts_list(df, col='timestamp'):
    return [pd.Timestamp(row[col]) for _, row in df.iterrows()] if len(df) > 0 else []


def _float_list(df, col):
    return [float(row[col]) for _, row in df.iterrows()] if len(df) > 0 else []


def _int_list(df, col):
    return [int(row[col]) for _, row in df.iterrows()] if len(df) > 0 else []


def _build_series(dataframes, label_col, value_col='value', with_max=False):
    """Build (label, timestamps, values) tuples for chart_multiline."""
    series = []
    for sub_df in dataframes:
        if len(sub_df) == 0:
            continue
        lbl = sub_df[label_col].iloc[0]
        ts = _ts_list(sub_df)
        vs = _float_list(sub_df, value_col)
        series.append((lbl, ts, vs))
        # GRAF1-C: 2a serie con los maximos. Sin la columna (datos previos a
        # GRAF1-A) no se anade nada y el grafico queda como hoy.
        if with_max and 'value_max' in sub_df.columns:
            series.append((f"{lbl}{MAX_SERIES_SUFFIX}", ts, _float_list(sub_df, 'value_max')))
    return series


def _build_codes_series(dataframes):
    series = []
    for code_df in dataframes:
        if len(code_df) == 0:
            continue
        code = str(code_df['code'].iloc[0])
        ts = _ts_list(code_df)
        vs = _float_list(code_df, 'value')
        series.append((f"HTTP {code}", ts, vs))
    return series


async def _check_execution_access(db: AsyncSession, user: User, execution) -> None:
    """Raise 403 if a non-admin user doesn't have access to this execution."""
    if user.role == 'admin':
        return
    result = await db.execute(
        select(UserClient.client_id).where(UserClient.user_id == user.id)
    )
    client_ids = [row[0] for row in result.fetchall()]
    if execution.client_id is None or execution.client_id not in client_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta ejecucion"
        )


@router.get("/executions/{execution_id}/export/pdf")
async def export_pdf(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Export professional PDF report with charts and AI analysis."""

    if not WEASYPRINT_AVAILABLE:
        raise HTTPException(status_code=500, detail="WeasyPrint no disponible en el servidor")

    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID invalido")

    result = await db.execute(select(TestExecution).where(TestExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    await _check_execution_access(db, current_user, execution)

    jtl_paths = _find_jtl_files(execution)
    if not jtl_paths:
        raise HTTPException(status_code=404, detail="Archivo JTL no encontrado")

    try:
        # ---- Parse JTL ----
        if len(jtl_paths) == 1:
            parser = JTLParser(jtl_paths[0])
            df, _ = parser.parse()
        else:
            df, _, parser = JTLParser.parse_multiple(jtl_paths)

        summary_df = parser.get_summary_table_data()
        redirect_df = parser.get_redirect_summary_data()
        response_codes = parser.get_response_code_distribution()
        charts_data = parser.get_all_charts_data(interval_seconds=10)

        logger.info(f"PDF: parsed {len(df)} rows, generating charts...")

        # ---- Generate matplotlib charts ----
        tl = charts_data['timeline']
        tl_timestamps = _ts_list(tl)

        charts_b64 = {
            'rt_label': chart_multiline(
                _build_series(
                    apply_top_n_aggregation(
                        charts_data.get('response_times_by_label', []),
                        summary_df,
                    )[0],
                    'label',
                    with_max=True,          # GRAF1-C
                ),
                'Response Time (ms)',
                dual_max=True,              # GRAF1-C
            ),
            # UI-2: 'rt_time' (Response Time Over Time) retirada del PDF — ya no se renderiza.
            'throughput': chart_area(tl_timestamps, _float_list(tl, 'throughput'), '#10b981', 'Requests/s'),
            'latency': chart_area(tl_timestamps, [float(row.get('avg_latency', 0)) for _, row in tl.iterrows()] if len(tl) > 0 else [], '#8b5cf6', 'Latencia (ms)'),
            'error_rate': chart_area(tl_timestamps, _float_list(tl, 'error_rate'), '#ef4444', 'Error Rate (%)'),
            'codes': chart_multiline(
                _build_codes_series(charts_data.get('codes_per_second', [])),
                'Codes/s', use_code_colors=True,
            ),
            'tps': chart_multiline(
                _build_series(charts_data.get('tps_by_label', []), 'label'),
                'TPS',
            ),
            'threads': chart_area(tl_timestamps, _int_list(tl, 'active_threads'), '#6366f1', 'Threads'),
            'pie': chart_pie([
                {'code': str(row['responseCode']), 'count': int(row['count'])}
                for _, row in response_codes.iterrows()
            ]),
        }

        logger.info("PDF: all charts generated, building HTML...")

        # ---- Build data dicts ----
        statistics = []
        logger.info(f"PDF stats_data: {len(summary_df)} rows, columns={list(summary_df.columns)}")
        if len(summary_df) > 0:
            logger.info(f"PDF first row label: {summary_df.iloc[0]['label']}")
        for _, row in summary_df.iterrows():
            statistics.append({
                'label': row['label'],
                'samples': int(row['muestras']),
                'errors': int(row['errores']),
                'errorPct': round(float(row['tasa_error']), 2),
                'avg': round(float(row['promedio']), 2),
                'median': round(float(row['mediana']), 2),
                'p90': round(float(row['p90']), 2),
                'p95': round(float(row['p95']), 2),
                'p99': round(float(row['p99']), 2),
                'min': round(float(row['min']), 2),
                'max': round(float(row['max']), 2),
                'tps': round(float(row['rendimiento']), 2),
                'kbRecv': round(float(row['kb_received']), 2),
                'kbSent': round(float(row['kb_sent']), 2),
            })

        redirect_stats = []
        if redirect_df is not None and len(redirect_df) > 0:
            for _, row in redirect_df.iterrows():
                redirect_stats.append({
                    'label': row['label'],
                    'samples': int(row['muestras']),
                    'errors': int(row['errores']),
                    'errorPct': round(float(row['tasa_error']), 2),
                    'avg': round(float(row['promedio']), 2),
                    'p90': round(float(row['p90']), 2),
                    'p95': round(float(row['p95']), 2),
                    'p99': round(float(row['p99']), 2),
                    'min': round(float(row['min']), 2),
                    'max': round(float(row['max']), 2),
                    'tps': round(float(row['rendimiento']), 2),
                })

        ia = {
            'summary': execution.ai_analysis_summary or '',
            'errors': execution.ai_analysis_errors or '',
            'responseTimes': execution.ai_analysis_response_times or '',
            'responseTimeOverTime': execution.ai_analysis_response_time_over_time or '',
            'throughput': execution.ai_analysis_throughput or '',
            'latency': execution.ai_analysis_latency or '',
            'errorRate': execution.ai_analysis_error_rate or '',
            'codesPerSecond': execution.ai_analysis_codes_per_second or '',
            'tps': execution.ai_analysis_transactions_per_second or '',
            'activeThreads': execution.ai_analysis_active_threads or '',
            'redirects': execution.ai_analysis_redirects or '',
            'conclusions': execution.ai_conclusions or '',
            'recommendations': execution.ai_recommendations or '',
        }

        test_type_info = TEST_TYPE_LABELS.get(execution.test_type or 'load', TEST_TYPE_LABELS['load'])

        meta = {
            'name': execution.name,
            'client': execution.client or '',
            'project': execution.project or '',
            'testType': execution.test_type or 'load',
            'testTypeLabel': test_type_info['label'],
            'testTypeColor': test_type_info['color'],
            'filename': execution.jtl_filename,
            'filenames': execution.jtl_filenames or [execution.jtl_filename],
            'startTime': execution.start_time.strftime('%d/%m/%Y %H:%M:%S') if execution.start_time else '--',
            'endTime': execution.end_time.strftime('%d/%m/%Y %H:%M:%S') if execution.end_time else '--',
            'duration': float(execution.duration_seconds or 0),
            'totalRequests': execution.total_requests,
            'totalErrors': execution.total_errors,
            'errorRate': float(execution.error_rate),
            'avgResponseTime': float(execution.avg_response_time),
            'medianResponseTime': float(execution.median_response_time or 0),
            'p90': float(execution.p90_response_time),
            'p95': float(execution.p95_response_time),
            'p99': float(execution.p99_response_time),
            'minResponseTime': float(execution.min_response_time),
            'maxResponseTime': float(execution.max_response_time),
            'throughput': float(execution.throughput),
            'avgLatency': float(execution.avg_latency or 0),
            'kbRecv': float(execution.kb_per_sec_received or 0),
            'kbSent': float(execution.kb_per_sec_sent or 0),
            'totalRedirects': execution.total_redirects or 0,
            'acceptanceCriteria': execution.acceptance_criteria_json or {},
        }

        # ---- Render PDF (individual: NO monitoring/evidence attachments) ----
        # N1.6: logo del cliente para la portada (None si no hay: portada igual que hoy)
        from app.services.export.client_logo import get_client_logo_b64
        meta['client_logo'] = await get_client_logo_b64(db, execution)

        # N3.5: transacciones criticas de ESTA ejecucion. Sin filas, el bloque no
        # se pinta y el PDF sale identico al de siempre.
        from app.db.models.transaction_analysis import TransactionAnalysis
        _txn = await db.execute(
            select(TransactionAnalysis)
            .where(TransactionAnalysis.execution_id == execution.id)
            .order_by(TransactionAnalysis.sort_order)
        )
        meta['transaction_analyses'] = [
            {'label': r.label, 'metrics': r.metrics_json, 'ai_analysis': r.ai_analysis}
            for r in _txn.scalars().all()
        ]

        html_content = build_pdf_html(meta, statistics, redirect_stats, ia, charts_b64)

        # KNX-17: Capacity analysis for PDF
        capacity_pdf = ''
        cap_json = execution.capacity_analysis_json if hasattr(execution, 'capacity_analysis_json') else None
        if cap_json:
            try:
                cap_data = json.loads(cap_json)
                if cap_data.get('enabled') and cap_data.get('resources'):
                    cap_rows = ''
                    for r in cap_data['resources']:
                        st = r.get('status', '')
                        st_html = f'<span style="color:{"#166534" if st == "PASS" else "#991b1b"};font-weight:700">{st}</span>' if st else '--'
                        cap_rows += f'''<tr>
                            <td style="padding:2mm 1.5mm;font-weight:600;font-size:7.5pt">{r.get('name','')}</td>
                            <td style="padding:2mm 1.5mm;text-align:center;font-size:7.5pt">{r.get('observed_value','')} {r.get('unit','')}</td>
                            <td style="padding:2mm 1.5mm;text-align:center;font-size:7.5pt;color:#64748b">{r.get('threshold','')} {r.get('unit','')}</td>
                            <td style="padding:2mm 1.5mm;text-align:center;font-size:7.5pt">{st_html}</td>
                            <td style="padding:2mm 1.5mm;font-size:7pt;color:#334155">{r.get('analysis','')}</td>
                        </tr>'''
                    capacity_pdf = f'''
                    <div style="margin-bottom:5mm">
                        <div style="background:#0a1628;color:white;padding:2.5mm 4mm;font-size:10pt;font-weight:700;border-radius:2mm 2mm 0 0">
                            Analisis de Capacidades del Sistema
                        </div>
                        <table style="width:100%;border-collapse:collapse;font-size:7.5pt;margin-bottom:4mm">
                            <thead><tr style="background:#0a1628;color:white">
                                <th style="padding:2mm 1.5mm;text-align:left;font-size:6.5pt">Recurso</th>
                                <th style="padding:2mm 1.5mm;text-align:center;font-size:6.5pt">Valor</th>
                                <th style="padding:2mm 1.5mm;text-align:center;font-size:6.5pt">Umbral</th>
                                <th style="padding:2mm 1.5mm;text-align:center;font-size:6.5pt">Estado</th>
                                <th style="padding:2mm 1.5mm;text-align:left;font-size:6.5pt">Analisis</th>
                            </tr></thead>
                            <tbody>{cap_rows}</tbody>
                        </table>
                    </div>'''
            except Exception:
                pass

        # Inject capacity analysis before closing </body> (no attachments in individual export)
        if capacity_pdf:
            html_content = html_content.replace('</body>', f'{capacity_pdf}</body>')

        logger.info("PDF: rendering with WeasyPrint...")
        pdf_bytes = HTML(string=html_content).write_pdf()
        logger.info(f"PDF: done, {len(pdf_bytes)} bytes")

        # Build filename: {Client}_{project}_{date}_{time}.pdf
        _client_name = execution.client or ''
        if not _client_name and execution.client_id:
            _cr = await db.execute(select(Client.name).where(Client.id == execution.client_id))
            _client_name = _cr.scalar_one_or_none() or ''
        _safe = lambda t: ''.join(c if c.isalnum() or c in '-_' else '_' for c in t.replace(' ', '_')).strip('_')
        client_part = _safe(_client_name).lower() if _client_name.strip() else 'reporte'
        if client_part:
            client_part = client_part[0].upper() + client_part[1:]
        project_part = _safe(execution.name).lower()
        _now = datetime.now(ZoneInfo("America/Bogota"))
        filename = f"{client_part}_{project_part}_{_now.strftime('%Y-%m-%d')}_{_now.strftime('%H%M')}.pdf"

        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(pdf_bytes)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generando PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")
