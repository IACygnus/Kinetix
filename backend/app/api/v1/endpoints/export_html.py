"""
Export HTML endpoint – standalone HTML with interactive Plotly.js charts.
Plotly.js loaded from CDN. Full interactivity: hover, zoom, pan, toggle series.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
from typing import List, Dict, Any
import uuid
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

import pandas as pd

from app.db.session import get_db
from app.db.models.test import TestExecution
from app.db.models.client import Client, UserClient
from app.db.models.user import User
from app.core.security import get_current_active_user
from app.services.jtl.jtl_parser import JTLParser
from app.config.chart_config import TEST_TYPE_LABELS, CHART_COLORS, HTTP_CODE_COLORS
# ExecutionAttachment removed — individual exports no longer include monitoring/evidence

router = APIRouter()
logger = logging.getLogger(__name__)

# ===================== HELPERS =====================


def _find_jtl_files(execution) -> List[str]:
    upload_dir = Path("/app/uploads")
    filenames = execution.jtl_filenames or [execution.jtl_filename]
    found = []
    for fname in filenames:
        matches = list(upload_dir.glob(f"*{fname}"))
        if matches:
            found.append(str(matches[0]))
    return found


async def _check_execution_access(db: AsyncSession, user: User, execution) -> None:
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


def _markdown_to_html(text: str) -> str:
    """Minimal markdown → HTML for AI analysis text.
    Sanitizes HTML tags to prevent underline/style injection (KNX-05)."""
    if not text:
        return ''
    # Sanitize: escape HTML tags from AI text to prevent style injection
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Convert markdown bold/italic AFTER escaping
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    paragraphs = text.strip().split('\n\n')
    html_parts = []
    for p in paragraphs:
        lines = p.strip().split('\n')
        html_parts.append('<p>' + '<br>'.join(lines) + '</p>')
    return ''.join(html_parts)


def _ts_iso_list(df, col='timestamp') -> List[str]:
    """Convert timestamps to ISO strings for Plotly."""
    if len(df) == 0:
        return []
    return [pd.Timestamp(row[col]).isoformat() for _, row in df.iterrows()]


def _float_list(df, col) -> List[float]:
    if len(df) == 0:
        return []
    return [float(row[col]) for _, row in df.iterrows()]


def _int_list(df, col) -> List[int]:
    if len(df) == 0:
        return []
    return [int(row[col]) for _, row in df.iterrows()]


def _compute_redirect_totals(redirect_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute TOTAL row for redirect table."""
    if not redirect_stats:
        return {}
    total_samples = sum(r['samples'] for r in redirect_stats)
    total_errors = sum(r['errors'] for r in redirect_stats)
    error_pct = (total_errors / total_samples * 100) if total_samples > 0 else 0
    weighted_avg = sum(r['avg'] * r['samples'] for r in redirect_stats) / total_samples if total_samples > 0 else 0
    return {
        'samples': total_samples,
        'errors': total_errors,
        'errorPct': round(error_pct, 2),
        'avg': round(weighted_avg, 2),
        'p90': round(max((r['p90'] for r in redirect_stats), default=0), 2),
        'p95': round(max((r['p95'] for r in redirect_stats), default=0), 2),
        'p99': round(max((r['p99'] for r in redirect_stats), default=0), 2),
        'min': round(min((r['min'] for r in redirect_stats), default=0), 2),
        'max': round(max((r['max'] for r in redirect_stats), default=0), 2),
        'tps': round(sum(r['tps'] for r in redirect_stats), 2),
    }


# ===================== ENDPOINT =====================


@router.get("/executions/{execution_id}/export/html")
async def export_html(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Export standalone HTML report with interactive Plotly.js charts and AI analysis."""

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
        tl = charts_data['timeline']

        logger.info(f"HTML export: parsed {len(df)} rows, building Plotly charts...")

        # ---- Build data structures ----
        statistics = []
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

        # ---- Build Plotly chart data as JSON ----
        tl_timestamps = _ts_iso_list(tl)

        # Chart 1: Response Times por Transaccion (multi-series)
        rt_by_label_traces = []
        for i, sub_df in enumerate(charts_data.get('response_times_by_label', [])):
            if len(sub_df) == 0:
                continue
            lbl = sub_df['label'].iloc[0]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            rt_by_label_traces.append({
                'x': _ts_iso_list(sub_df),
                'y': _float_list(sub_df, 'value'),
                'name': lbl,
                'type': 'scatter',
                'mode': 'lines',
                'line': {'color': color, 'width': 2},
                'hovertemplate': '%{y:,.0f} ms<extra>%{fullData.name}</extra>',
            })

        # Chart 2: Response Time Over Time (single)
        rt_over_time_traces = [{
            'x': tl_timestamps,
            'y': _float_list(tl, 'avg_response_time'),
            'name': 'Avg Response Time',
            'type': 'scatter',
            'mode': 'lines',
            'fill': 'tozeroy',
            'line': {'color': '#3b82f6', 'width': 2},
            'fillcolor': 'rgba(59,130,246,0.15)',
            'hovertemplate': '%{y:,.0f} ms<extra>%{fullData.name}</extra>',
        }]

        # Chart 3: Throughput Over Time
        throughput_traces = [{
            'x': tl_timestamps,
            'y': _float_list(tl, 'throughput'),
            'name': 'Throughput',
            'type': 'scatter',
            'mode': 'lines',
            'fill': 'tozeroy',
            'line': {'color': '#10b981', 'width': 2},
            'fillcolor': 'rgba(16,185,129,0.15)',
            'hovertemplate': '%{y:,.2f} req/s<extra>%{fullData.name}</extra>',
        }]

        # Chart 4: Latency Over Time
        latency_values = [float(row.get('avg_latency', 0)) for _, row in tl.iterrows()] if len(tl) > 0 else []
        latency_traces = [{
            'x': tl_timestamps,
            'y': latency_values,
            'name': 'Avg Latency',
            'type': 'scatter',
            'mode': 'lines',
            'fill': 'tozeroy',
            'line': {'color': '#8b5cf6', 'width': 2},
            'fillcolor': 'rgba(139,92,246,0.15)',
            'hovertemplate': '%{y:,.0f} ms<extra>%{fullData.name}</extra>',
        }]

        # Chart 5: Error Rate Over Time
        error_rate_traces = [{
            'x': tl_timestamps,
            'y': _float_list(tl, 'error_rate'),
            'name': 'Error Rate',
            'type': 'bar',
            'marker': {'color': '#ef4444'},
            'hovertemplate': '%{y:,.2f}%<extra>%{fullData.name}</extra>',
        }]

        # Chart 6: Response Codes per Second (multi-series)
        codes_traces = []
        for code_df in charts_data.get('codes_per_second', []):
            if len(code_df) == 0:
                continue
            code = str(code_df['code'].iloc[0])
            color = HTTP_CODE_COLORS.get(code, '#94a3b8')
            codes_traces.append({
                'x': _ts_iso_list(code_df),
                'y': _float_list(code_df, 'value'),
                'name': f'HTTP {code}',
                'type': 'scatter',
                'mode': 'lines',
                'line': {'color': color, 'width': 2},
                'hovertemplate': '%{y:,.0f} /s<extra>%{fullData.name}</extra>',
            })

        # Chart 7: Transactions per Second (multi-series)
        tps_traces = []
        for i, tps_df in enumerate(charts_data.get('tps_by_label', [])):
            if len(tps_df) == 0:
                continue
            lbl = tps_df['label'].iloc[0]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            tps_traces.append({
                'x': _ts_iso_list(tps_df),
                'y': _float_list(tps_df, 'value'),
                'name': lbl,
                'type': 'scatter',
                'mode': 'lines',
                'line': {'color': color, 'width': 2},
                'hovertemplate': '%{y:,.2f} tps<extra>%{fullData.name}</extra>',
            })

        # Chart 8: Active Threads Over Time
        threads_traces = [{
            'x': tl_timestamps,
            'y': _int_list(tl, 'active_threads'),
            'name': 'Active Threads',
            'type': 'scatter',
            'mode': 'lines',
            'fill': 'tozeroy',
            'line': {'color': '#6366f1', 'width': 2},
            'fillcolor': 'rgba(99,102,241,0.15)',
            'hovertemplate': '%{y:,.0f} threads<extra>%{fullData.name}</extra>',
        }]

        # Chart 9: Response Codes Pie
        pie_labels = [str(row['responseCode']) for _, row in response_codes.iterrows()]
        pie_values = [int(row['count']) for _, row in response_codes.iterrows()]
        pie_colors = [HTTP_CODE_COLORS.get(c, '#94a3b8') for c in pie_labels]

        # ---- Build HTML (individual: NO monitoring/evidence attachments) ----
        html_content = _build_plotly_html(
            meta=meta,
            statistics=statistics,
            redirect_stats=redirect_stats,
            ia=ia,
            rt_by_label_traces=rt_by_label_traces,
            rt_over_time_traces=rt_over_time_traces,
            throughput_traces=throughput_traces,
            latency_traces=latency_traces,
            error_rate_traces=error_rate_traces,
            codes_traces=codes_traces,
            tps_traces=tps_traces,
            threads_traces=threads_traces,
            pie_labels=pie_labels,
            pie_values=pie_values,
            pie_colors=pie_colors,
        )

        # KNX-17: Capacity analysis section
        capacity_html = ''
        cap_json = execution.capacity_analysis_json if hasattr(execution, 'capacity_analysis_json') else None
        if cap_json:
            import json as _json
            try:
                cap_data = _json.loads(cap_json)
                if cap_data.get('enabled') and cap_data.get('resources'):
                    cap_rows = ''
                    for r in cap_data['resources']:
                        status_badge = ''
                        if r.get('status') == 'PASS':
                            status_badge = '<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:700">PASS</span>'
                        elif r.get('status') == 'FAIL':
                            status_badge = '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:700">FAIL</span>'
                        cap_rows += f'''<tr>
                            <td style="padding:8px;font-weight:600">{r.get('name','')}</td>
                            <td style="padding:8px;text-align:center">{r.get('observed_value','')} {r.get('unit','')}</td>
                            <td style="padding:8px;text-align:center;color:#64748b">{r.get('threshold','')} {r.get('unit','')}</td>
                            <td style="padding:8px;text-align:center">{status_badge}</td>
                            <td style="padding:8px;font-size:.9rem;color:#334155">{r.get('analysis','')}</td>
                        </tr>'''
                    capacity_html = f'''
                    <div class="section" style="margin-bottom:24px">
                        <div class="section-title">Analisis de Capacidades del Sistema</div>
                        <table style="width:100%;border-collapse:collapse;font-size:.85rem">
                            <thead><tr style="background:#0a1628;color:white">
                                <th style="padding:8px;text-align:left">Recurso</th>
                                <th style="padding:8px;text-align:center">Valor</th>
                                <th style="padding:8px;text-align:center">Umbral</th>
                                <th style="padding:8px;text-align:center">Estado</th>
                                <th style="padding:8px;text-align:left">Analisis</th>
                            </tr></thead>
                            <tbody>{cap_rows}</tbody>
                        </table>
                    </div>'''
            except Exception:
                pass

        # Inject capacity section before footer (no attachments in individual export)
        if capacity_html:
            html_content = html_content.replace('</div>\n</body>', f'{capacity_html}</div>\n</body>')

        logger.info(f"HTML export: done, {len(html_content)} chars")

        # Build filename: {Client}_{project}_{date}_{time}.html
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
        filename = f"{client_part}_{project_part}_{_now.strftime('%Y-%m-%d')}_{_now.strftime('%H%M')}.html"

        return HTMLResponse(
            content=html_content,
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error exportando HTML: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exportando HTML: {str(e)}")


# ===================== HTML BUILDER =====================


def _build_plotly_html(
    meta: Dict[str, Any],
    statistics: List[Dict[str, Any]],
    redirect_stats: List[Dict[str, Any]],
    ia: Dict[str, str],
    rt_by_label_traces: list,
    rt_over_time_traces: list,
    throughput_traces: list,
    latency_traces: list,
    error_rate_traces: list,
    codes_traces: list,
    tps_traces: list,
    threads_traces: list,
    pie_labels: list,
    pie_values: list,
    pie_colors: list,
) -> str:
    """Build complete standalone HTML with Plotly.js interactive charts."""

    duration_min = int(meta['duration'] // 60)
    duration_sec = int(meta['duration'] % 60)
    now_str = datetime.now(ZoneInfo("America/Bogota")).strftime('%d/%m/%Y %H:%M:%S')
    files_list = ', '.join(meta.get('filenames', [meta['filename']]))

    er = meta['errorRate']
    er_color = '#10b981' if er < 1 else '#f59e0b' if er < 5 else '#ef4444'
    tt_color = meta.get('testTypeColor', '#3b82f6')

    test_badge = (
        f'<span class="badge" style="background:{tt_color}20;color:{tt_color};'
        f'border:1px solid {tt_color}">{meta["testTypeLabel"]}</span>'
    )

    criteria = meta.get('acceptanceCriteria', {})
    verdict_text = criteria.get('verdict', '') if isinstance(criteria, dict) else ''
    verdict_badge = ''
    if verdict_text:
        if verdict_text == 'APTO':
            vb, vc, vr = '#dcfce7', '#16a34a', '#86efac'
        elif verdict_text == 'NO APTO':
            vb, vc, vr = '#fef2f2', '#dc2626', '#fca5a5'
        else:
            vb, vc, vr = '#fffbeb', '#d97706', '#fcd34d'
        verdict_badge = (
            f'<span class="badge" style="background:{vb};color:{vc};'
            f'border:1px solid {vr};font-weight:700;margin-left:8px">{verdict_text}</span>'
        )

    # ---- AI box helper ----
    def ai_box(key, title, border='#4f46e5'):
        text = ia.get(key, '')
        if not text:
            return ''
        html_text = _markdown_to_html(text)
        # HF10h BLOQUE A: unified yellow-dark border on white background
        return (
            f'<div class="ai-box">'
            f'<div class="ai-title">{title}</div>'
            f'<div class="ai-text">{html_text}</div>'
            f'</div>'
        )

    # ---- Stats table rows ----
    stats_rows = ''
    for s in statistics:
        err_cls = ' class="err"' if s['errorPct'] > 0 else ''
        stats_rows += f'''<tr>
            <td>{s['label']}</td><td>{s['samples']:,}</td>
            <td{err_cls}>{s['errors']:,}</td><td{err_cls}>{s['errorPct']:.2f}%</td>
            <td>{s['avg']:.2f}</td><td>{s['median']:.2f}</td>
            <td>{s['p90']:.2f}</td><td>{s['p95']:.2f}</td><td>{s['p99']:.2f}</td>
            <td>{s['min']:.2f}</td><td>{s['max']:.2f}</td>
            <td>{s['tps']:.2f}</td><td>{s['kbRecv']:.2f}</td><td>{s['kbSent']:.2f}</td>
        </tr>'''

    stats_rows += f'''<tr class="total-row">
        <td>TOTAL PRINCIPALES</td><td>{meta['totalRequests']:,}</td>
        <td>{meta['totalErrors']:,}</td><td>{meta['errorRate']:.2f}%</td>
        <td>{meta['avgResponseTime']:.2f}</td><td>{meta['medianResponseTime']:.2f}</td>
        <td>{meta['p90']:.2f}</td><td>{meta['p95']:.2f}</td><td>{meta['p99']:.2f}</td>
        <td>{meta['minResponseTime']:.2f}</td><td>{meta['maxResponseTime']:.2f}</td>
        <td>{meta['throughput']:.2f}</td><td>{meta['kbRecv']:.2f}</td><td>{meta['kbSent']:.2f}</td>
    </tr>'''

    # ---- Redirect section with TOTAL row ----
    redirect_section = ''
    if redirect_stats:
        redir_rows = ''
        for r in redirect_stats:
            redir_rows += f'''<tr>
                <td>{r['label']}</td><td>{r['samples']:,}</td>
                <td>{r['errors']:,}</td><td>{r['errorPct']:.2f}%</td>
                <td>{r['avg']:.2f}</td><td>{r['p90']:.2f}</td><td>{r['p95']:.2f}</td>
                <td>{r['p99']:.2f}</td><td>{r['min']:.2f}</td><td>{r['max']:.2f}</td><td>{r['tps']:.2f}</td>
            </tr>'''

        totals = _compute_redirect_totals(redirect_stats)
        redir_rows += f'''<tr class="total-row">
            <td>TOTAL REDIRECCIONES</td><td>{totals['samples']:,}</td>
            <td>{totals['errors']:,}</td><td>{totals['errorPct']:.2f}%</td>
            <td>{totals['avg']:.2f}</td><td>{totals['p90']:.2f}</td><td>{totals['p95']:.2f}</td>
            <td>{totals['p99']:.2f}</td><td>{totals['min']:.2f}</td><td>{totals['max']:.2f}</td><td>{totals['tps']:.2f}</td>
        </tr>'''

        redirect_section = f'''
        <div class="section">
            <div class="section-title">Reporte de Redirecciones</div>
            <div class="table-wrap">
                <table>
                    <thead><tr>
                        <th>Redireccion</th><th>Muestras</th><th>Errores</th><th>% Error</th>
                        <th>Promedio</th><th>P90</th><th>P95</th><th>P99</th>
                        <th>Min</th><th>Max</th><th>TPS</th>
                    </tr></thead>
                    <tbody>{redir_rows}</tbody>
                </table>
            </div>
        </div>
        {ai_box('redirects', 'Analisis de Redirecciones', '#f97316')}
        '''

    # ---- Error bars (CSS-only, no chart needed) ----
    errs_with_errors = [s for s in statistics if s['errors'] > 0]
    error_bars_html = ''
    if errs_with_errors:
        max_e = max(s['errors'] for s in errs_with_errors)
        bars = ''
        for s in errs_with_errors:
            w = max(5, (s['errors'] / max_e) * 100)
            bars += (
                f'<div style="display:flex;align-items:center;margin-bottom:6px">'
                f'<div style="width:160px;font-size:.8rem;font-weight:600;overflow:hidden;'
                f'text-overflow:ellipsis;white-space:nowrap" title="{s["label"]}">{s["label"]}</div>'
                f'<div style="flex:1;height:24px;background:#fee2e2;border-radius:4px;'
                f'position:relative;overflow:hidden">'
                f'<div style="height:100%;width:{w:.0f}%;background:linear-gradient(90deg,#ef4444,#dc2626);'
                f'border-radius:4px"></div>'
                f'<span style="position:absolute;right:6px;top:50%;transform:translateY(-50%);'
                f'font-size:.75rem;font-weight:700;color:#991b1b">'
                f'{s["errors"]:,} ({s["errorPct"]:.2f}%)</span>'
                f'</div></div>'
            )
        error_bars_html = bars
    else:
        error_bars_html = '<p style="color:#94a3b8;text-align:center;padding:2rem">Sin errores detectados</p>'

    # ---- Plotly data as JSON ----
    def jd(obj):
        return json.dumps(obj, ensure_ascii=False)

    plotly_layout_base = {
        'paper_bgcolor': 'white',
        'plot_bgcolor': '#f8fafc',
        'font': {'family': '-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif', 'size': 12},
        'margin': {'l': 80, 'r': 30, 't': 20, 'b': 60},
        'legend': {
            'orientation': 'h', 'yanchor': 'top', 'y': -0.2, 'xanchor': 'center', 'x': 0.5,
            'itemclick': 'toggle', 'itemdoubleclick': 'toggleothers',
        },
        'xaxis': {'gridcolor': '#e2e8f0', 'linecolor': '#e2e8f0', 'type': 'date', 'tickformat': '%H:%M:%S', 'tickangle': -45, 'nticks': 20, 'fixedrange': False},
        'yaxis': {'gridcolor': '#e2e8f0', 'linecolor': '#e2e8f0', 'rangemode': 'tozero', 'nticks': 12, 'fixedrange': False},
        'hovermode': 'x unified',
        'dragmode': 'zoom',
    }

    def make_layout(ytitle='', height=500, ytickformat=',.0f'):
        layout = dict(plotly_layout_base)
        layout['height'] = height
        layout['yaxis'] = dict(layout['yaxis'], title=ytitle,
                               tickformat=ytickformat, hoverformat=ytickformat,
                               exponentformat='none', separatethousands=True)
        layout['xaxis'] = dict(layout['xaxis'], title='Tiempo')
        return layout

    plotly_config = {
        'responsive': True,
        'displayModeBar': True,
        'displaylogo': False,
        'scrollZoom': True,
        'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'toImage'],
    }

    # HF10h BLOQUE A: compute P99 and max for charts with Y-axis controls
    def _compute_trace_stats(traces):
        """Given Plotly traces list, compute overall max and P99 of all y values."""
        all_y = []
        for t in traces:
            y_vals = t.get('y', []) or []
            for v in y_vals:
                try:
                    if v is not None:
                        all_y.append(float(v))
                except (TypeError, ValueError):
                    pass
        if not all_y:
            return 100.0, 100.0
        all_y_sorted = sorted(all_y)
        max_val = all_y_sorted[-1]
        p99_idx = max(0, int(len(all_y_sorted) * 0.99) - 1)
        p99_val = all_y_sorted[p99_idx]
        return max_val, p99_val

    def _fmt_short_local(value):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return str(value)
        if v >= 1000:
            return f"{v/1000:.1f}k"
        return f"{v:.0f}"

    rt_label_max, rt_label_p99 = _compute_trace_stats(rt_by_label_traces)
    rt_time_max, rt_time_p99 = _compute_trace_stats(rt_over_time_traces)
    latency_max, latency_p99 = _compute_trace_stats(latency_traces)

    # Helper: render chart controls (show/hide all + optional Y-axis controls)
    def _ctrl_basic(chart_id):
        return (
            f'<div class="chart-controls">'
            f'<button class="ctrl-btn" onclick="hf10hShowAll(\'{chart_id}\')">Mostrar todas</button>'
            f'<button class="ctrl-btn" onclick="hf10hHideAll(\'{chart_id}\')">Ocultar todas</button>'
            f'</div>'
        )

    def _ctrl_y_axis(chart_id, p99_value, max_value):
        slider_id = f"{chart_id}-slider"
        valdisp_id = f"{chart_id}-val"
        return (
            f'<div class="chart-controls">'
            f'<button class="ctrl-btn" onclick="hf10hShowAll(\'{chart_id}\')">Mostrar todas</button>'
            f'<button class="ctrl-btn" onclick="hf10hHideAll(\'{chart_id}\')">Ocultar todas</button>'
            f'<span class="ctrl-sep">|</span>'
            f'<span class="ctrl-label">Eje Y:</span>'
            f'<button class="ctrl-btn" onclick="hf10hYAuto(\'{chart_id}\')">Auto-fit</button>'
            f'<button class="ctrl-btn" onclick="hf10hYRange(\'{chart_id}\',{p99_value})">P99</button>'
            f'<button class="ctrl-btn" onclick="hf10hYRange(\'{chart_id}\',{max_value})">Reset</button>'
            f'<span class="ctrl-label">Max:</span>'
            f'<input type="range" id="{slider_id}" min="1" max="{max_value:.0f}" value="{max_value:.0f}" '
            f'oninput="hf10hSlider(\'{chart_id}\',this.value,\'{valdisp_id}\')">'
            f'<span class="ctrl-value" id="{valdisp_id}">{_fmt_short_local(max_value)}</span>'
            f'</div>'
        )

    # ---- Full HTML ----
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Reporte Performance - {meta['name']}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;text-decoration:none}}
:root{{--navy:#0a1628;--blue:#3E5AA9;--bg:#f0f4f8;--card:#fff;--border:#e2e8f0;--success:#10b981;--warn:#f59e0b;--error:#ef4444}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:#1e293b;line-height:1.6;font-size:14px}}
.header{{background:linear-gradient(135deg,#0a1628 0%,#1e293b 50%,#1e40af 100%);color:#fff;padding:2rem;position:relative}}
.header-content{{max-width:1400px;margin:0 auto}}
.header-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem}}
.logo{{font-size:2rem;font-weight:800;letter-spacing:-1px}}
.logo-sub{{font-size:.85rem;opacity:.7}}
.header-meta{{background:rgba(255,255,255,.08);backdrop-filter:blur(10px);border-radius:12px;padding:1.5rem}}
.project-name{{font-size:1.5rem;font-weight:700;margin-bottom:.5rem}}
.meta-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-top:1rem}}
.meta-label{{font-size:.7rem;text-transform:uppercase;opacity:.7;letter-spacing:.5px}}
.meta-value{{font-family:monospace;font-size:.9rem;margin-top:2px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.75rem;font-weight:700;text-transform:uppercase;margin-left:8px}}
.container{{max-width:1400px;margin:0 auto;padding:2rem}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}
.kpi{{background:var(--card);border-radius:10px;padding:1.2rem;box-shadow:0 1px 4px rgba(0,0,0,.08);border-left:4px solid #3b82f6}}
.kpi.s{{border-left-color:var(--success)}}.kpi.w{{border-left-color:var(--warn)}}.kpi.e{{border-left-color:var(--error)}}.kpi.p{{border-left-color:#8b5cf6}}
.kpi-label{{font-size:.8rem;color:#64748b;margin-bottom:.3rem}}
.kpi-val{{font-size:1.8rem;font-weight:700;color:var(--navy)}}
.kpi-val span{{font-size:1rem;font-weight:400}}
.section{{background:var(--card);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.section-title{{font-size:1.2rem;font-weight:700;color:var(--navy);border-left:4px solid #3b82f6;padding-left:.75rem;margin-bottom:1rem}}
.table-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th{{background:var(--navy);color:#fff;padding:.6rem .5rem;text-align:left;font-size:.75rem;font-weight:600;text-transform:uppercase;white-space:nowrap}}
td{{padding:.5rem;border-bottom:1px solid var(--border);white-space:nowrap}}
tr:hover{{background:#f8fafc}}
.total-row{{background:var(--navy)!important;color:#fff;font-weight:700}}
.total-row td{{border-bottom:none}}
.err{{color:var(--error);font-weight:600}}
.chart-section{{background:var(--card);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.chart-title{{font-size:1.1rem;font-weight:700;color:var(--navy);border-left:4px solid #3b82f6;padding-left:.75rem;margin-bottom:1rem}}
.plotly-chart{{width:100%;min-height:400px}}
.chart-controls{{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem;padding:.6rem .75rem;margin-top:.5rem;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;font-size:.8rem}}
.chart-controls .ctrl-btn{{background:#f5a623;color:#0a1628;border:none;border-radius:6px;padding:.3rem .7rem;font-size:.75rem;font-weight:700;cursor:pointer;transition:background .15s}}
.chart-controls .ctrl-btn:hover{{background:#4f46e5}}
.chart-controls .ctrl-sep{{color:#cbd5e1;margin:0 .25rem}}
.chart-controls .ctrl-label{{color:#64748b;font-weight:600}}
.chart-controls input[type=range]{{accent-color:#f5a623;width:140px}}
.chart-controls .ctrl-value{{color:#0a1628;font-weight:700;min-width:50px;text-align:right}}
.ai-box{{background:#ffffff;border:2px solid #4f46e5;border-left:6px solid #4f46e5;border-radius:8px;padding:1.2rem;margin:1rem 0}}
.ai-title{{font-size:1rem;font-weight:700;color:var(--navy);margin-bottom:.5rem}}
.ai-text{{font-size:.9rem;line-height:1.8;color:#334155}}
.ai-text p{{margin:0 0 8px 0}}
.ai-text strong{{color:var(--navy)}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}}
.footer{{text-align:center;padding:2rem;color:#94a3b8;font-size:.85rem;border-top:1px solid var(--border);margin-top:2rem}}
.footer strong{{color:var(--navy)}}
@media print{{body{{background:#fff}}.header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}th,.total-row{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
@media(max-width:768px){{.kpis,.meta-grid,.grid-2{{grid-template-columns:1fr}}}}
</style>
</head>
<body>

<div class="header">
<div class="header-content">
<div class="header-top">
<div><div class="logo">sqa</div><div class="logo-sub">Software Quality Assurance</div></div>
<div style="text-align:right"><div style="font-size:.8rem;opacity:.7">Realizado por:</div><div style="font-weight:600">Celula de Performance SQA</div></div>
</div>
<div class="header-meta">
<div style="font-size:.75rem;opacity:.7;text-transform:uppercase;letter-spacing:.5px">Reporte de Analisis de Performance {test_badge} {verdict_badge}</div>
<div class="project-name">{meta['name']}</div>
<div class="meta-grid">
<div><div class="meta-label">Cliente</div><div class="meta-value">{meta['client'] or 'N/A'}</div></div>
<div><div class="meta-label">Nombre del Proyecto</div><div class="meta-value">{meta['project'] or meta['name']}</div></div>
<div><div class="meta-label">Duracion</div><div class="meta-value">{duration_min}m {duration_sec}s</div></div>
<div><div class="meta-label">Tipo de Prueba</div><div class="meta-value">{meta['testTypeLabel']}</div></div>
</div>
<div style="font-size:.8rem;opacity:.6;margin-top:.75rem">
Archivo: {files_list} &nbsp;|&nbsp; Inicio: {meta['startTime']} &nbsp;|&nbsp; Fin: {meta['endTime']} &nbsp;|&nbsp; Generado: {now_str}
</div>
</div>
</div>
</div>

<div class="container">

<div class="kpis">
<div class="kpi"><div class="kpi-label">Total Requests</div><div class="kpi-val">{meta['totalRequests']:,}</div></div>
<div class="kpi s"><div class="kpi-label">Avg Response Time</div><div class="kpi-val">{meta['avgResponseTime']:.0f} <span>ms</span></div></div>
<div class="kpi {'e' if er > 5 else 'w' if er > 1 else 's'}"><div class="kpi-label">Error Rate</div><div class="kpi-val" style="color:{er_color}">{meta['errorRate']:.2f}<span>%</span></div></div>
<div class="kpi p"><div class="kpi-label">Throughput</div><div class="kpi-val">{meta['throughput']:.2f} <span>req/s</span></div></div>
</div>

<div class="kpis">
<div class="kpi"><div class="kpi-label">P90</div><div class="kpi-val">{meta['p90']:.0f} <span>ms</span></div></div>
<div class="kpi"><div class="kpi-label">P95</div><div class="kpi-val">{meta['p95']:.0f} <span>ms</span></div></div>
<div class="kpi"><div class="kpi-label">P99</div><div class="kpi-val">{meta['p99']:.0f} <span>ms</span></div></div>
<div class="kpi"><div class="kpi-label">Avg Latency</div><div class="kpi-val">{meta['avgLatency']:.0f} <span>ms</span></div></div>
</div>

<div class="section">
<div class="section-title">Reporte Resumen por Transaccion</div>
<div class="table-wrap">
<table>
<thead><tr>
<th>Transaccion</th><th>Muestras</th><th>Errores</th><th>% Error</th>
<th>Promedio</th><th>Mediana</th><th>P90</th><th>P95</th><th>P99</th>
<th>Min</th><th>Max</th><th>TPS</th><th>KB/s Recv</th><th>KB/s Sent</th>
</tr></thead>
<tbody>{stats_rows}</tbody>
</table>
</div>
</div>

{ai_box('summary', 'Analisis del Reporte Resumen')}

{redirect_section}

<!-- ===== PLOTLY INTERACTIVE CHARTS ===== -->
<p style="font-size:11px;color:#94a3b8;text-align:center;margin-bottom:8px">
Interactivo: Scroll para zoom &bull; Arrastre para seleccionar zona &bull; Doble click para resetear &bull; Click en leyenda para ocultar/mostrar series
</p>

<div class="chart-section">
<div class="chart-title" style="border-left-color:#8b5cf6">Response Times por Transaccion</div>
<div id="chart-rt-label" class="plotly-chart"></div>
{_ctrl_y_axis('chart-rt-label', rt_label_p99, rt_label_max)}
</div>
{ai_box('responseTimes', 'Analisis - Response Times por Transaccion', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#3b82f6">Response Time Over Time</div>
<div id="chart-rt-time" class="plotly-chart"></div>
{_ctrl_y_axis('chart-rt-time', rt_time_p99, rt_time_max)}
</div>
{ai_box('responseTimeOverTime', 'Analisis - Response Time Over Time', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#10b981">Throughput Over Time</div>
<div id="chart-throughput" class="plotly-chart"></div>
{_ctrl_basic('chart-throughput')}
</div>
{ai_box('throughput', 'Analisis - Throughput', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#8b5cf6">Latency Over Time</div>
<div id="chart-latency" class="plotly-chart"></div>
{_ctrl_y_axis('chart-latency', latency_p99, latency_max)}
</div>
{ai_box('latency', 'Analisis - Latency', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#ef4444">Error Rate Over Time</div>
<div id="chart-error-rate" class="plotly-chart"></div>
{_ctrl_basic('chart-error-rate')}
</div>
{ai_box('errorRate', 'Analisis - Error Rate', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#6366f1">Response Codes per Second</div>
<div id="chart-codes" class="plotly-chart"></div>
{_ctrl_basic('chart-codes')}
</div>
{ai_box('codesPerSecond', 'Analisis - Response Codes', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#10b981">Transactions per Second</div>
<div id="chart-tps" class="plotly-chart"></div>
{_ctrl_basic('chart-tps')}
</div>
{ai_box('tps', 'Analisis - Transactions per Second', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#6366f1">Active Threads Over Time</div>
<div id="chart-threads" class="plotly-chart"></div>
{_ctrl_basic('chart-threads')}
</div>
{ai_box('activeThreads', 'Analisis - Active Threads', '#f97316')}

<div class="grid-2">
<div class="chart-section">
<div class="chart-title" style="border-left-color:#f59e0b">Distribucion de Response Codes</div>
<div id="chart-pie" class="plotly-chart" style="min-height:380px"></div>
</div>
<div class="chart-section">
<div class="chart-title" style="border-left-color:#ef4444">Errores por Transaccion</div>
{error_bars_html}
</div>
</div>

{ai_box('errors', 'Analisis de Errores', '#f97316')}

{ai_box('conclusions', 'Conclusiones', '#6366f1')}
{ai_box('recommendations', 'Recomendaciones', '#10b981')}

<div class="footer">
<strong>sqa &mdash; Software Quality Assurance</strong><br>
sqa &mdash; Software Quality Assurance | Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos<br>
<span style="font-size:.75rem">Generado: {now_str}</span>
</div>

</div>

<script>
// HF10h BLOQUE A: chart control helpers (idempotent, safe to define multiple times)
if (typeof window.hf10hShowAll !== 'function') {{
  window.hf10hShowAll = function(id) {{
    var div = document.getElementById(id);
    if (!div || !div.data) return;
    var visArr = div.data.map(function() {{ return true; }});
    Plotly.restyle(div, {{'visible': visArr}});
  }};
  window.hf10hHideAll = function(id) {{
    var div = document.getElementById(id);
    if (!div || !div.data) return;
    var visArr = div.data.map(function() {{ return 'legendonly'; }});
    Plotly.restyle(div, {{'visible': visArr}});
  }};
  window.hf10hYAuto = function(id) {{
    var div = document.getElementById(id);
    if (!div) return;
    Plotly.relayout(div, {{'yaxis.autorange': true}});
  }};
  window.hf10hYRange = function(id, maxVal) {{
    var div = document.getElementById(id);
    if (!div) return;
    Plotly.relayout(div, {{'yaxis.range': [0, maxVal]}});
  }};
  window.hf10hFmtShort = function(v) {{
    v = parseFloat(v);
    if (isNaN(v)) return '0';
    if (v >= 1000) return (v/1000).toFixed(1) + 'k';
    return v.toFixed(0);
  }};
  window.hf10hSlider = function(id, val, valDispId) {{
    var div = document.getElementById(id);
    if (!div) return;
    var v = parseFloat(val);
    Plotly.relayout(div, {{'yaxis.range': [0, v]}});
    var disp = document.getElementById(valDispId);
    if (disp) disp.textContent = window.hf10hFmtShort(v);
  }};
}}

// ===== Plotly Chart Rendering =====
var plotlyConfig = {jd(plotly_config)};

// 1. Response Times por Transaccion (multi-series, toggle ON/OFF)
Plotly.newPlot('chart-rt-label', {jd(rt_by_label_traces)}, {jd(make_layout('Response Time (ms)', 420, ',.0f'))}, plotlyConfig);

// 2. Response Time Over Time
Plotly.newPlot('chart-rt-time', {jd(rt_over_time_traces)}, {jd(make_layout('Response Time (ms)', 420, ',.0f'))}, plotlyConfig);

// 3. Throughput Over Time
Plotly.newPlot('chart-throughput', {jd(throughput_traces)}, {jd(make_layout('Requests/s', 420, ',.2f'))}, plotlyConfig);

// 4. Latency Over Time
Plotly.newPlot('chart-latency', {jd(latency_traces)}, {jd(make_layout('Latencia (ms)', 420, ',.0f'))}, plotlyConfig);

// 5. Error Rate Over Time
Plotly.newPlot('chart-error-rate', {jd(error_rate_traces)}, {jd(make_layout('Error Rate (%)', 420, ',.2f'))}, plotlyConfig);

// 6. Response Codes per Second (multi-series, toggle ON/OFF)
Plotly.newPlot('chart-codes', {jd(codes_traces)}, {jd(make_layout('Codes/s', 420, ',.0f'))}, plotlyConfig);

// 7. Transactions per Second (multi-series, toggle ON/OFF)
Plotly.newPlot('chart-tps', {jd(tps_traces)}, {jd(make_layout('TPS', 420, ',.2f'))}, plotlyConfig);

// 8. Active Threads Over Time
Plotly.newPlot('chart-threads', {jd(threads_traces)}, {jd(make_layout('Threads', 420, ',.0f'))}, plotlyConfig);

// 9. Response Codes Pie
Plotly.newPlot('chart-pie', [{{
    labels: {jd(pie_labels)},
    values: {jd(pie_values)},
    type: 'pie',
    marker: {{ colors: {jd(pie_colors)} }},
    textinfo: 'label+percent',
    hoverinfo: 'label+value+percent'
}}], {{
    height: 360,
    paper_bgcolor: 'white',
    margin: {{ l: 20, r: 20, t: 10, b: 20 }},
    legend: {{ orientation: 'h', yanchor: 'top', y: -0.1, xanchor: 'center', x: 0.5 }}
}}, plotlyConfig);

// Resize all charts on window resize
window.addEventListener('resize', function() {{
    document.querySelectorAll('.plotly-chart').forEach(function(el) {{
        Plotly.Plots.resize(el);
    }});
}});
</script>

</body>
</html>'''
