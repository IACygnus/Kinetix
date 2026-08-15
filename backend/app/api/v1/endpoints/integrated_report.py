"""
Integrated Report — combines multiple executions, monitoring, and evidence into one report.
R3-B: Drag-and-drop ordering from frontend, unified AI conclusions.
"""
import uuid
import json
import os
import base64
import logging
from typing import List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from pathlib import Path

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.db.models.test import TestExecution
from app.db.models.attachment import ExecutionAttachment
from app.services.jtl.jtl_parser import JTLParser
from app.services.export.report_generator import (
    chart_area, chart_multiline, chart_pie, build_pdf_html, MAX_SERIES_SUFFIX,
    cover_meta_parts,   # N2.3
)
from app.services.export.high_cardinality_strategy import apply_top_n_aggregation
from app.services.export.client_logo import get_client_logo_b64   # N1.5
from app.config.chart_config import TEST_TYPE_LABELS, CHART_COLORS, HTTP_CODE_COLORS
import pandas as pd
import json as _json_hf10h
import re as _re_hf10h

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("/app/uploads")


def _find_jtl_files(execution) -> list:
    """Find JTL files for an execution."""
    filenames = execution.jtl_filenames or [execution.jtl_filename]
    found = []
    for fname in filenames:
        matches = list(UPLOAD_DIR.glob(f"*{fname}"))
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
    series = []
    for sub_df in dataframes:
        if len(sub_df) == 0:
            continue
        lbl = sub_df[label_col].iloc[0]
        ts = _ts_list(sub_df)
        vs = _float_list(sub_df, value_col)
        series.append((lbl, ts, vs))
        # GRAF1-C: 2a serie con los maximos; sin la columna no se anade nada.
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


async def _generate_full_execution_pdf_html(execution, db: AsyncSession, overrides=None) -> str:
    """Generate FULL PDF HTML for one execution — same quality as individual export.

    F6: `overrides` trae el texto editado en el informe integrado y pisa al de la IA.
    """
    jtl_paths = _find_jtl_files(execution)
    if not jtl_paths:
        return _build_exec_html(execution, SectionInput(order=0, type="load_test", source_id=str(execution.id), source_name=execution.name), overrides)

    try:
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
            # UI-2: 'rt_time' (Response Time Over Time) retirada del PDF integrado.
            'throughput': chart_area(tl_timestamps, _float_list(tl, 'throughput'), '#10b981', 'Requests/s'),
            'latency': chart_area(tl_timestamps, [float(row.get('avg_latency', 0)) for _, row in tl.iterrows()] if len(tl) > 0 else [], '#8b5cf6', 'Latencia (ms)'),
            'error_rate': chart_area(tl_timestamps, _float_list(tl, 'error_rate'), '#ef4444', 'Error Rate (%)'),
            'codes': chart_multiline(_build_codes_series(charts_data.get('codes_per_second', [])), 'Codes/s', use_code_colors=True),
            'tps': chart_multiline(_build_series(charts_data.get('tps_by_label', []), 'label'), 'TPS'),
            'threads': chart_area(tl_timestamps, _int_list(tl, 'active_threads'), '#6366f1', 'Threads'),
            'pie': chart_pie([{'code': str(row['responseCode']), 'count': int(row['count'])} for _, row in response_codes.iterrows()]),
        }

        # Build stats/meta dicts
        statistics = []
        for _, row in summary_df.iterrows():
            statistics.append({
                'label': row['label'], 'samples': int(row['muestras']), 'errors': int(row['errores']),
                'errorPct': round(float(row['tasa_error']), 2), 'avg': round(float(row['promedio']), 2),
                'median': round(float(row['mediana']), 2), 'p90': round(float(row['p90']), 2),
                'p95': round(float(row['p95']), 2), 'p99': round(float(row['p99']), 2),
                'min': round(float(row['min']), 2), 'max': round(float(row['max']), 2),
                'tps': round(float(row['rendimiento']), 2),
                'kbRecv': round(float(row.get('kb_received', 0)), 2),
                'kbSent': round(float(row.get('kb_sent', 0)), 2),
            })

        redirect_stats = []
        if redirect_df is not None and len(redirect_df) > 0:
            for _, row in redirect_df.iterrows():
                redirect_stats.append({
                    'label': row['label'], 'samples': int(row['muestras']), 'errors': int(row['errores']),
                    'errorPct': round(float(row['tasa_error']), 2), 'avg': round(float(row['promedio']), 2),
                    'p90': round(float(row['p90']), 2), 'p95': round(float(row['p95']), 2),
                    'p99': round(float(row['p99']), 2), 'min': round(float(row['min']), 2),
                    'max': round(float(row['max']), 2), 'tps': round(float(row['rendimiento']), 2),
                })

        ia = {
            'summary': execution.ai_analysis_summary or '', 'errors': execution.ai_analysis_errors or '',
            'responseTimes': execution.ai_analysis_response_times or '',
            'responseTimeOverTime': execution.ai_analysis_response_time_over_time or '',
            'throughput': execution.ai_analysis_throughput or '', 'latency': execution.ai_analysis_latency or '',
            'errorRate': execution.ai_analysis_error_rate or '',
            'codesPerSecond': execution.ai_analysis_codes_per_second or '',
            'tps': execution.ai_analysis_transactions_per_second or '',
            'activeThreads': execution.ai_analysis_active_threads or '',
            'redirects': execution.ai_analysis_redirects or '',
            'conclusions': execution.ai_conclusions or '', 'recommendations': execution.ai_recommendations or '',
        }
        _apply_ia_overrides(ia, overrides)   # F6

        test_type_info = TEST_TYPE_LABELS.get(execution.test_type or 'load', TEST_TYPE_LABELS['load'])

        meta = {
            'name': execution.name, 'client': execution.client or '', 'project': execution.project or '',
            'testType': execution.test_type or 'load', 'testTypeLabel': test_type_info['label'],
            'testTypeColor': test_type_info['color'], 'filename': execution.jtl_filename,
            'filenames': execution.jtl_filenames or [execution.jtl_filename],
            'startTime': execution.start_time.strftime('%d/%m/%Y %H:%M:%S') if execution.start_time else '--',
            'endTime': execution.end_time.strftime('%d/%m/%Y %H:%M:%S') if execution.end_time else '--',
            'duration': float(execution.duration_seconds or 0),
            'totalRequests': execution.total_requests, 'totalErrors': execution.total_errors,
            'errorRate': float(execution.error_rate), 'avgResponseTime': float(execution.avg_response_time),
            'medianResponseTime': float(execution.median_response_time or 0),
            'p90': float(execution.p90_response_time), 'p95': float(execution.p95_response_time),
            'p99': float(execution.p99_response_time),
            'minResponseTime': float(execution.min_response_time),
            'maxResponseTime': float(execution.max_response_time),
            'throughput': float(execution.throughput), 'avgLatency': float(execution.avg_latency or 0),
            'kbRecv': float(execution.kb_per_sec_received or 0),
            'kbSent': float(execution.kb_per_sec_sent or 0),
            'totalRedirects': execution.total_redirects or 0,
            'acceptanceCriteria': execution.acceptance_criteria_json or {},
        }

        # N1.6: logo del cliente para la portada (None si no hay: portada igual que hoy)
        meta['client_logo'] = await get_client_logo_b64(db, execution)

        # Generate the full PDF HTML using report_generator's build_pdf_html
        return build_pdf_html(meta, statistics, redirect_stats, ia, charts_b64)

    except Exception as e:
        logger.error(f"Error generating full PDF for execution {execution.id}: {e}")
        return _build_exec_html(execution, SectionInput(order=0, type="load_test", source_id=str(execution.id), source_name=execution.name), overrides)


# ═══════════════════════════════════════════════════════════════════════════════
# HF10h — Plotly interactive HTML generation for integrated reports
# ═══════════════════════════════════════════════════════════════════════════════

def _hf10h_markdown_to_html(text: str) -> str:
    """Local copy of _markdown_to_html from export_html.py (to avoid cross-module import)."""
    if not text:
        return ''
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = _re_hf10h.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = _re_hf10h.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    paragraphs = text.strip().split('\n\n')
    html_parts = []
    for p in paragraphs:
        lines = p.strip().split('\n')
        html_parts.append('<p>' + '<br>'.join(lines) + '</p>')
    return ''.join(html_parts)


def _ts_iso_list(df, col='timestamp'):
    """Convert timestamps to ISO strings for Plotly."""
    if len(df) == 0:
        return []
    return [pd.Timestamp(row[col]).isoformat() for _, row in df.iterrows()]


def _compute_redirect_totals(redirect_stats):
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


# Plotly CSS — emitted ONCE per integrated HTML document
PLOTLY_INTEGRATED_CSS = """
<style>
*{margin:0;padding:0;box-sizing:border-box;text-decoration:none}
:root{--navy:#0a1628;--blue:#3E5AA9;--bg:#f0f4f8;--card:#fff;--border:#e2e8f0;--success:#10b981;--warn:#f59e0b;--error:#ef4444}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:#1e293b;line-height:1.6;font-size:14px}
.plotly-header{background:linear-gradient(135deg,#0a1628 0%,#1e293b 50%,#1e40af 100%);color:#fff;padding:2rem;position:relative;border-radius:12px 12px 0 0}
.plotly-header-content{max-width:1400px;margin:0 auto}
.plotly-header-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem}
.plotly-logo{font-size:2rem;font-weight:800;letter-spacing:-1px}
.plotly-logo-sub{font-size:.85rem;opacity:.7}
.plotly-header-meta{background:rgba(255,255,255,.08);backdrop-filter:blur(10px);border-radius:12px;padding:1.5rem}
.plotly-project-name{font-size:1.5rem;font-weight:700;margin-bottom:.5rem}
.plotly-meta-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-top:1rem}
.plotly-meta-block{display:flex;align-items:center;gap:2rem;margin-top:1rem}
.plotly-meta-izq{flex:1 1 62%;min-width:0}
.plotly-meta-der{flex:0 0 34%;border-left:1px solid rgba(255,255,255,.22);padding-left:2rem;text-align:center}
.plotly-meta-label{font-size:.7rem;text-transform:uppercase;opacity:.7;letter-spacing:.5px}
.plotly-meta-value{font-family:monospace;font-size:.9rem;margin-top:2px}
.plotly-badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.75rem;font-weight:700;text-transform:uppercase;margin-left:8px}
.plotly-container{max-width:1400px;margin:0 auto;padding:2rem}
.plotly-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}
.plotly-kpi{background:var(--card);border-radius:10px;padding:1.2rem;box-shadow:0 1px 4px rgba(0,0,0,.08);border-left:4px solid #3b82f6}
.plotly-kpi.s{border-left-color:var(--success)}.plotly-kpi.w{border-left-color:var(--warn)}.plotly-kpi.e{border-left-color:var(--error)}.plotly-kpi.p{border-left-color:#8b5cf6}
.plotly-kpi-label{font-size:.8rem;color:#64748b;margin-bottom:.3rem}
.plotly-kpi-val{font-size:1.8rem;font-weight:700;color:var(--navy)}
.plotly-kpi-val span{font-size:1rem;font-weight:400}
.plotly-section{background:var(--card);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.plotly-section-title{font-size:1.2rem;font-weight:700;color:var(--navy);border-left:4px solid #3b82f6;padding-left:.75rem;margin-bottom:1rem}
.plotly-table-wrap{overflow-x:auto}
.plotly-section table{width:100%;border-collapse:collapse;font-size:.85rem}
.plotly-section th{background:var(--navy);color:#fff;padding:.6rem .5rem;text-align:left;font-size:.75rem;font-weight:600;text-transform:uppercase;white-space:nowrap}
.plotly-section td{padding:.5rem;border-bottom:1px solid var(--border);white-space:nowrap}
.plotly-section tr:hover{background:#f8fafc}
.plotly-section .total-row{background:var(--navy)!important;color:#fff;font-weight:700}
.plotly-section .total-row td{border-bottom:none}
.plotly-section .err{color:var(--error);font-weight:600}
.plotly-chart-section{background:var(--card);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.plotly-chart-title{font-size:1.1rem;font-weight:700;color:var(--navy);border-left:4px solid #3b82f6;padding-left:.75rem;margin-bottom:1rem}
.plotly-chart-div{width:100%;min-height:400px}
.plotly-chart-controls{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin-top:.75rem;padding:.5rem .75rem;background:#f8fafc;border-radius:6px;font-size:.8rem}
.plotly-chart-controls .ctrl-btn{background:#fff;border:1px solid #cbd5e1;color:#334155;padding:.3rem .7rem;border-radius:4px;cursor:pointer;font-size:.75rem;font-weight:600;transition:all .15s}
.plotly-chart-controls .ctrl-btn:hover{background:#f5a623;color:#fff;border-color:#f5a623}
.plotly-chart-controls .ctrl-btn.active{background:#f5a623;color:#fff;border-color:#f5a623}
.plotly-chart-controls .ctrl-sep{color:#cbd5e1;margin:0 .25rem}
.plotly-chart-controls .ctrl-label{color:#64748b;font-weight:600}
.plotly-chart-controls input[type=range]{accent-color:#f5a623;width:140px}
.plotly-chart-controls .ctrl-value{color:#0a1628;font-weight:700;min-width:50px;text-align:right}
.plotly-ai-box{background:#ffffff;border:2px solid #4f46e5;border-left:6px solid #4f46e5;border-radius:8px;padding:1.2rem;margin:1rem 0}
.plotly-ai-title{font-size:1rem;font-weight:700;color:var(--navy);margin-bottom:.5rem}
.plotly-ai-text{font-size:.9rem;line-height:1.8;color:#334155}
.plotly-ai-text p{margin:0 0 8px 0}
.plotly-ai-text strong{color:var(--navy)}
.plotly-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
@media(max-width:768px){.plotly-kpis,.plotly-meta-grid,.plotly-grid-2{grid-template-columns:1fr}
.plotly-meta-block{flex-direction:column;align-items:stretch;gap:1.2rem}
.plotly-meta-der{border-left:none;border-top:1px solid rgba(255,255,255,.22);padding-left:0;padding-top:1rem}}
</style>
"""


def _fmt_short(value):
    """Format a number with 'k' suffix if >= 1000 (e.g., 1300 → '1.3k')."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if v >= 1000:
        return f"{v/1000:.1f}k"
    return f"{v:.0f}"


def _build_plotly_html_isolated(execution_data: dict, prefix: str = "") -> str:
    """HF10h: Build an HTML fragment with Plotly interactive charts for ONE execution.
    Unlike _build_plotly_html (in export_html.py), this returns ONLY a body fragment
    (no <html>, <head>, or Plotly CDN script) so multiple executions can be concatenated
    into an integrated report. The caller is responsible for loading Plotly.js CDN ONCE
    in the document <head>, and for injecting PLOTLY_INTEGRATED_CSS once.
    All div IDs are prefixed to avoid collisions between executions.
    """
    meta = execution_data['meta']
    statistics = execution_data['statistics']
    redirect_stats = execution_data['redirect_stats']
    ia = execution_data['ia']
    rt_by_label_traces = execution_data['rt_by_label_traces']
    throughput_traces = execution_data['throughput_traces']
    latency_traces = execution_data['latency_traces']
    error_rate_traces = execution_data['error_rate_traces']
    codes_traces = execution_data['codes_traces']
    tps_traces = execution_data['tps_traces']
    threads_traces = execution_data['threads_traces']
    pie_labels = execution_data['pie_labels']
    pie_values = execution_data['pie_values']
    pie_colors = execution_data['pie_colors']

    duration_min = int(meta['duration'] // 60)
    duration_sec = int(meta['duration'] % 60)
    now_str = datetime.now(ZoneInfo("America/Bogota")).strftime('%d/%m/%Y %H:%M:%S')
    files_list = ', '.join(meta.get('filenames', [meta['filename']]))

    er = meta['errorRate']
    er_color = '#10b981' if er < 1 else '#f59e0b' if er < 5 else '#ef4444'
    tt_color = meta.get('testTypeColor', '#3b82f6')
    test_badge = (
        f'<span class="plotly-badge" style="background:{tt_color}20;color:{tt_color};'
        f'border:1px solid {tt_color}">{meta["testTypeLabel"]}</span>'
    )

    # UI-2: sin badge de veredicto en los exports (se conserva solo en pantalla).

    def ai_box(key, title, border='#4f46e5'):
        text = ia.get(key, '')
        if not text:
            return ''
        html_text = _hf10h_markdown_to_html(text)
        # HF10h BLOQUE A: unified yellow-dark border on white background (no color override per chart)
        return (
            f'<div class="plotly-ai-box">'
            f'<div class="plotly-ai-title">{title}</div>'
            f'<div class="plotly-ai-text">{html_text}</div>'
            f'</div>'
        )

    # Stats table
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

    # Redirect section
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
        <div class="plotly-section">
            <div class="plotly-section-title">Reporte de Redirecciones</div>
            <div class="plotly-table-wrap">
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

    # Error bars
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

    # Plotly layout helpers
    def jd(obj):
        return _json_hf10h.dumps(obj, ensure_ascii=False)

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

    rt_label_max, rt_label_p99 = _compute_trace_stats(rt_by_label_traces)
    latency_max, latency_p99 = _compute_trace_stats(latency_traces)

    # Helper: render chart controls (show/hide all + optional Y-axis controls)
    def _ctrl_basic(chart_id):
        """Show/Hide all buttons only."""
        return (
            f'<div class="plotly-chart-controls">'
            f'<button class="ctrl-btn" onclick="hf10hShowAll(\'{chart_id}\')">Mostrar todas</button>'
            f'<button class="ctrl-btn" onclick="hf10hHideAll(\'{chart_id}\')">Ocultar todas</button>'
            f'</div>'
        )

    def _ctrl_y_axis(chart_id, p99_value, max_value):
        """Show/Hide buttons + Y-axis controls (Auto-fit, P99, Reset, slider)."""
        slider_id = f"{chart_id}-slider"
        valdisp_id = f"{chart_id}-val"
        return (
            f'<div class="plotly-chart-controls">'
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
            f'<span class="ctrl-value" id="{valdisp_id}">{_fmt_short(max_value)}</span>'
            f'</div>'
        )

    # Prefixed div IDs
    id_rt_label = f"{prefix}chart-rt-label"
    id_throughput = f"{prefix}chart-throughput"
    id_latency = f"{prefix}chart-latency"
    id_error_rate = f"{prefix}chart-error-rate"
    id_codes = f"{prefix}chart-codes"
    id_tps = f"{prefix}chart-tps"
    id_threads = f"{prefix}chart-threads"
    id_pie = f"{prefix}chart-pie"

    # N1.5: logo del cliente. Sin logo -> cadena vacia y la cabecera queda
    # exactamente igual que antes (ni un hueco de mas).
    _logo_uri = meta.get('client_logo')
    # N2.2-B / N2.3: el bloque de metadatos son dos zonas separadas por una
    # linea vertical. Izquierda ~62%: ejecucion + duracion, criterios, archivo.
    # Derecha ~34%: el cliente con etiqueta, logo y nombre centrados entre si.
    # El nombre del proyecto y el tipo de prueba salen del bloque (ya estan en el
    # titulo y en el badge). Sin criterios, esa fila no se pinta.
    _cm = cover_meta_parts(meta)
    fila_criterios = (
        f'<div style="margin-top:.9rem"><div class="plotly-meta-label">Criterios de Aceptacion</div>'
        f'<div class="plotly-meta-value">{_cm["criteria"]}</div></div>'
    ) if _cm['criteria'] else ''
    _logo_img = (
        f'<img src="{_logo_uri}" alt="Logo del cliente" '
        f'style="max-height:110px;max-width:100%;object-fit:contain;display:block;margin:.7rem auto .5rem auto" />'
    ) if _logo_uri else ''
    celda_cliente = (
        f'<div class="plotly-meta-label">Cliente</div>'
        f'{_logo_img}'
        f'<div class="plotly-meta-value" style="font-size:1.05rem;font-family:inherit'
        f'{"" if _logo_uri else ";margin-top:.5rem"}">{meta["client"] or "N/A"}</div>'
    )

    # Body fragment (HF10h BLOQUE A.1: cover restored)
    return f'''
<div class="plotly-header">
<div class="plotly-header-content">
<div class="plotly-header-top">
<div><div class="plotly-logo">sqa</div><div class="plotly-logo-sub">Software Quality Assurance</div></div>
<div style="text-align:right"><div style="font-size:.8rem;opacity:.7">Realizado por:</div><div style="font-weight:600">Celula de Performance SQA</div></div>
</div>
<div class="plotly-header-meta">
<div style="font-size:.75rem;opacity:.7;text-transform:uppercase;letter-spacing:.5px">Reporte de Analisis de Performance {test_badge}</div>
<div class="plotly-project-name">{meta['name']}</div>
<div class="plotly-meta-block">
<div class="plotly-meta-izq">
<div style="display:flex;gap:2rem;flex-wrap:wrap">
<div style="flex:1 1 55%"><div class="plotly-meta-label">Ejecucion</div><div class="plotly-meta-value">{_cm['date']}</div><div class="plotly-meta-value" style="opacity:.85">{_cm['range']}</div></div>
<div style="flex:1 1 30%"><div class="plotly-meta-label">Duracion</div><div class="plotly-meta-value">{duration_min}m {duration_sec}s</div></div>
</div>
{fila_criterios}
<div style="margin-top:.9rem"><div class="plotly-meta-label">Archivo</div><div class="plotly-meta-value">{files_list}</div></div>
</div>
<div class="plotly-meta-der">{celda_cliente}</div>
</div>
</div>
</div>
</div>

<div class="plotly-container">

<div class="plotly-kpis">
<div class="plotly-kpi"><div class="plotly-kpi-label">Total Requests</div><div class="plotly-kpi-val">{meta['totalRequests']:,}</div></div>
<div class="plotly-kpi s"><div class="plotly-kpi-label">Avg Response Time</div><div class="plotly-kpi-val">{meta['avgResponseTime']:.0f} <span>ms</span></div></div>
<div class="plotly-kpi {'e' if er > 5 else 'w' if er > 1 else 's'}"><div class="plotly-kpi-label">Error Rate</div><div class="plotly-kpi-val" style="color:{er_color}">{meta['errorRate']:.2f}<span>%</span></div></div>
<div class="plotly-kpi p"><div class="plotly-kpi-label">Throughput</div><div class="plotly-kpi-val">{meta['throughput']:.2f} <span>req/s</span></div></div>
</div>

<div class="plotly-kpis">
<div class="plotly-kpi"><div class="plotly-kpi-label">P90</div><div class="plotly-kpi-val">{meta['p90']:.0f} <span>ms</span></div></div>
<div class="plotly-kpi"><div class="plotly-kpi-label">P95</div><div class="plotly-kpi-val">{meta['p95']:.0f} <span>ms</span></div></div>
<div class="plotly-kpi"><div class="plotly-kpi-label">P99</div><div class="plotly-kpi-val">{meta['p99']:.0f} <span>ms</span></div></div>
<div class="plotly-kpi"><div class="plotly-kpi-label">Avg Latency</div><div class="plotly-kpi-val">{meta['avgLatency']:.0f} <span>ms</span></div></div>
</div>

<div class="plotly-section">
<div class="plotly-section-title">Reporte Resumen por Transaccion</div>
<div class="plotly-table-wrap">
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

<p style="font-size:11px;color:#94a3b8;text-align:center;margin-bottom:8px">
Interactivo: Scroll para zoom &bull; Arrastre para seleccionar zona &bull; Doble click para resetear &bull; Click en leyenda para ocultar/mostrar series
</p>

<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#8b5cf6">Response Times por Transaccion</div>
<div id="{id_rt_label}" class="plotly-chart-div"></div>
{_ctrl_y_axis(id_rt_label, rt_label_p99, rt_label_max)}
</div>
{ai_box('responseTimes', 'Analisis - Response Times por Transaccion')}

<!-- UI-2: grafica agregada de tiempos retirada (ver docs/reporte_bug/ui2-ajustes-visuales.md) -->

<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#10b981">Throughput Over Time</div>
<div id="{id_throughput}" class="plotly-chart-div"></div>
{_ctrl_basic(id_throughput)}
</div>
{ai_box('throughput', 'Analisis - Throughput')}

<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#8b5cf6">Latency Over Time</div>
<div id="{id_latency}" class="plotly-chart-div"></div>
{_ctrl_y_axis(id_latency, latency_p99, latency_max)}
</div>
{ai_box('latency', 'Analisis - Latency')}

<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#ef4444">Error Rate Over Time</div>
<div id="{id_error_rate}" class="plotly-chart-div"></div>
{_ctrl_basic(id_error_rate)}
</div>
{ai_box('errorRate', 'Analisis - Error Rate')}

<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#6366f1">Response Codes per Second</div>
<div id="{id_codes}" class="plotly-chart-div"></div>
{_ctrl_basic(id_codes)}
</div>
{ai_box('codesPerSecond', 'Analisis - Response Codes')}

<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#10b981">Transactions per Second</div>
<div id="{id_tps}" class="plotly-chart-div"></div>
{_ctrl_basic(id_tps)}
</div>
{ai_box('tps', 'Analisis - Transactions per Second')}

<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#6366f1">Active Threads Over Time</div>
<div id="{id_threads}" class="plotly-chart-div"></div>
{_ctrl_basic(id_threads)}
</div>
{ai_box('activeThreads', 'Analisis - Active Threads')}

<div class="plotly-grid-2">
<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#f59e0b">Distribucion de Response Codes</div>
<div id="{id_pie}" class="plotly-chart-div" style="min-height:380px"></div>
</div>
<div class="plotly-chart-section">
<div class="plotly-chart-title" style="border-left-color:#ef4444">Errores por Transaccion</div>
{error_bars_html}
</div>
</div>

{ai_box('errors', 'Analisis de Errores', '#f97316')}

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
(function() {{
var plotlyConfig = {jd(plotly_config)};
Plotly.newPlot('{id_rt_label}', {jd(rt_by_label_traces)}, {jd(make_layout('Response Time (ms)', 420, ',.0f'))}, plotlyConfig);
Plotly.newPlot('{id_throughput}', {jd(throughput_traces)}, {jd(make_layout('Requests/s', 420, ',.2f'))}, plotlyConfig);
Plotly.newPlot('{id_latency}', {jd(latency_traces)}, {jd(make_layout('Latencia (ms)', 420, ',.0f'))}, plotlyConfig);
Plotly.newPlot('{id_error_rate}', {jd(error_rate_traces)}, {jd(make_layout('Error Rate (%)', 420, ',.2f'))}, plotlyConfig);
Plotly.newPlot('{id_codes}', {jd(codes_traces)}, {jd(make_layout('Codes/s', 420, ',.0f'))}, plotlyConfig);
Plotly.newPlot('{id_tps}', {jd(tps_traces)}, {jd(make_layout('TPS', 420, ',.2f'))}, plotlyConfig);
Plotly.newPlot('{id_threads}', {jd(threads_traces)}, {jd(make_layout('Threads', 420, ',.0f'))}, plotlyConfig);
Plotly.newPlot('{id_pie}', [{{
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
}})();
</script>
'''


async def _generate_full_execution_plotly_html(execution, db: AsyncSession, prefix: str = "", overrides=None) -> str:
    """HF10h: Generate interactive Plotly HTML fragment for ONE execution.
    Mirrors _generate_full_execution_pdf_html but builds Plotly traces instead of matplotlib base64.
    Returns a body fragment (no <html>/<head>) ready to be concatenated in an integrated report."""
    jtl_paths = _find_jtl_files(execution)
    if not jtl_paths:
        logger.warning(f"No JTL files for execution {execution.id}, falling back to basic exec HTML")
        return _build_exec_html(execution, SectionInput(order=0, type="load_test", source_id=str(execution.id), source_name=execution.name), overrides)

    try:
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

        # statistics
        statistics = []
        for _, row in summary_df.iterrows():
            statistics.append({
                'label': row['label'], 'samples': int(row['muestras']), 'errors': int(row['errores']),
                'errorPct': round(float(row['tasa_error']), 2), 'avg': round(float(row['promedio']), 2),
                'median': round(float(row['mediana']), 2), 'p90': round(float(row['p90']), 2),
                'p95': round(float(row['p95']), 2), 'p99': round(float(row['p99']), 2),
                'min': round(float(row['min']), 2), 'max': round(float(row['max']), 2),
                'tps': round(float(row['rendimiento']), 2),
                'kbRecv': round(float(row.get('kb_received', 0)), 2),
                'kbSent': round(float(row.get('kb_sent', 0)), 2),
            })

        # redirect_stats
        redirect_stats = []
        if redirect_df is not None and len(redirect_df) > 0:
            for _, row in redirect_df.iterrows():
                redirect_stats.append({
                    'label': row['label'], 'samples': int(row['muestras']), 'errors': int(row['errores']),
                    'errorPct': round(float(row['tasa_error']), 2), 'avg': round(float(row['promedio']), 2),
                    'p90': round(float(row['p90']), 2), 'p95': round(float(row['p95']), 2),
                    'p99': round(float(row['p99']), 2), 'min': round(float(row['min']), 2),
                    'max': round(float(row['max']), 2), 'tps': round(float(row['rendimiento']), 2),
                })

        # ia
        ia = {
            'summary': execution.ai_analysis_summary or '', 'errors': execution.ai_analysis_errors or '',
            'responseTimes': execution.ai_analysis_response_times or '',
            'responseTimeOverTime': execution.ai_analysis_response_time_over_time or '',
            'throughput': execution.ai_analysis_throughput or '', 'latency': execution.ai_analysis_latency or '',
            'errorRate': execution.ai_analysis_error_rate or '',
            'codesPerSecond': execution.ai_analysis_codes_per_second or '',
            'tps': execution.ai_analysis_transactions_per_second or '',
            'activeThreads': execution.ai_analysis_active_threads or '',
            'redirects': execution.ai_analysis_redirects or '',
            'conclusions': execution.ai_conclusions or '', 'recommendations': execution.ai_recommendations or '',
        }
        _apply_ia_overrides(ia, overrides)   # F6

        test_type_info = TEST_TYPE_LABELS.get(execution.test_type or 'load', TEST_TYPE_LABELS['load'])
        meta = {
            'name': execution.name, 'client': execution.client or '', 'project': execution.project or '',
            'testType': execution.test_type or 'load', 'testTypeLabel': test_type_info['label'],
            'testTypeColor': test_type_info['color'], 'filename': execution.jtl_filename,
            'filenames': execution.jtl_filenames or [execution.jtl_filename],
            'startTime': execution.start_time.strftime('%d/%m/%Y %H:%M:%S') if execution.start_time else '--',
            'endTime': execution.end_time.strftime('%d/%m/%Y %H:%M:%S') if execution.end_time else '--',
            'duration': float(execution.duration_seconds or 0),
            'totalRequests': execution.total_requests, 'totalErrors': execution.total_errors,
            'errorRate': float(execution.error_rate), 'avgResponseTime': float(execution.avg_response_time),
            'medianResponseTime': float(execution.median_response_time or 0),
            'p90': float(execution.p90_response_time), 'p95': float(execution.p95_response_time),
            'p99': float(execution.p99_response_time),
            'minResponseTime': float(execution.min_response_time),
            'maxResponseTime': float(execution.max_response_time),
            'throughput': float(execution.throughput), 'avgLatency': float(execution.avg_latency or 0),
            'kbRecv': float(execution.kb_per_sec_received or 0),
            'kbSent': float(execution.kb_per_sec_sent or 0),
            'totalRedirects': execution.total_redirects or 0,
            'acceptanceCriteria': execution.acceptance_criteria_json or {},
        }
        # N1.5: logo del cliente para la cabecera. None si el cliente no tiene
        # logo o no se puede resolver: la plantilla entonces no pinta nada.
        meta['client_logo'] = await get_client_logo_b64(db, execution)

        # Build Plotly traces
        tl_timestamps = _ts_iso_list(tl)

        _rt_integrated_filtered, _rt_int_suffix = apply_top_n_aggregation(
            charts_data.get('response_times_by_label', []),
            summary_df,
        )
        rt_by_label_traces = []
        for i, sub_df in enumerate(_rt_integrated_filtered):
            if len(sub_df) == 0:
                continue
            lbl = sub_df['label'].iloc[0]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            rt_by_label_traces.append({
                'x': _ts_iso_list(sub_df),
                'y': [float(row['value']) for _, row in sub_df.iterrows()],
                'name': lbl, 'type': 'scatter', 'mode': 'lines',
                'line': {'color': color, 'width': 2},
                'hovertemplate': '%{y:,.0f} ms<extra>%{fullData.name}</extra>',
            })
            # GRAF1-C: 2o trace con los maximos (mismo criterio que el HTML individual)
            if 'value_max' in sub_df.columns:
                rt_by_label_traces.append({
                    'x': _ts_iso_list(sub_df),
                    'y': [float(row['value_max']) for _, row in sub_df.iterrows()],
                    'name': f'{lbl}{MAX_SERIES_SUFFIX}', 'type': 'scatter', 'mode': 'lines',
                    'line': {'color': color, 'width': 1, 'dash': 'dot'},
                    'opacity': 0.85, 'showlegend': False,
                    'hovertemplate': '%{y:,.0f} ms<extra>%{fullData.name}</extra>',
                })

        # UI-2: traces de "Response Time Over Time" retirados del export.

        throughput_traces = [{
            'x': tl_timestamps,
            'y': [float(row['throughput']) for _, row in tl.iterrows()] if len(tl) > 0 else [],
            'name': 'Throughput', 'type': 'scatter', 'mode': 'lines', 'fill': 'tozeroy',
            'line': {'color': '#10b981', 'width': 2}, 'fillcolor': 'rgba(16,185,129,0.15)',
            'hovertemplate': '%{y:,.2f} req/s<extra>%{fullData.name}</extra>',
        }]

        latency_values = [float(row.get('avg_latency', 0)) for _, row in tl.iterrows()] if len(tl) > 0 else []
        latency_traces = [{
            'x': tl_timestamps, 'y': latency_values, 'name': 'Avg Latency',
            'type': 'scatter', 'mode': 'lines', 'fill': 'tozeroy',
            'line': {'color': '#8b5cf6', 'width': 2}, 'fillcolor': 'rgba(139,92,246,0.15)',
            'hovertemplate': '%{y:,.0f} ms<extra>%{fullData.name}</extra>',
        }]

        error_rate_traces = [{
            'x': tl_timestamps,
            'y': [float(row['error_rate']) for _, row in tl.iterrows()] if len(tl) > 0 else [],
            'name': 'Error Rate', 'type': 'bar', 'marker': {'color': '#ef4444'},
            'hovertemplate': '%{y:,.2f}%<extra>%{fullData.name}</extra>',
        }]

        codes_traces = []
        for code_df in charts_data.get('codes_per_second', []):
            if len(code_df) == 0:
                continue
            code = str(code_df['code'].iloc[0])
            color = HTTP_CODE_COLORS.get(code, '#94a3b8')
            codes_traces.append({
                'x': _ts_iso_list(code_df),
                'y': [float(row['value']) for _, row in code_df.iterrows()],
                'name': f'HTTP {code}', 'type': 'scatter', 'mode': 'lines',
                'line': {'color': color, 'width': 2},
                'hovertemplate': '%{y:,.0f} /s<extra>%{fullData.name}</extra>',
            })

        tps_traces = []
        for i, tps_df in enumerate(charts_data.get('tps_by_label', [])):
            if len(tps_df) == 0:
                continue
            lbl = tps_df['label'].iloc[0]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            tps_traces.append({
                'x': _ts_iso_list(tps_df),
                'y': [float(row['value']) for _, row in tps_df.iterrows()],
                'name': lbl, 'type': 'scatter', 'mode': 'lines',
                'line': {'color': color, 'width': 2},
                'hovertemplate': '%{y:,.2f} tps<extra>%{fullData.name}</extra>',
            })

        threads_traces = [{
            'x': tl_timestamps,
            'y': [int(row['active_threads']) for _, row in tl.iterrows()] if len(tl) > 0 else [],
            'name': 'Active Threads', 'type': 'scatter', 'mode': 'lines', 'fill': 'tozeroy',
            'line': {'color': '#6366f1', 'width': 2}, 'fillcolor': 'rgba(99,102,241,0.15)',
            'hovertemplate': '%{y:,.0f} threads<extra>%{fullData.name}</extra>',
        }]

        pie_labels = [str(row['responseCode']) for _, row in response_codes.iterrows()]
        pie_values = [int(row['count']) for _, row in response_codes.iterrows()]
        pie_colors = [HTTP_CODE_COLORS.get(c, '#94a3b8') for c in pie_labels]

        execution_data = {
            'meta': meta,
            'statistics': statistics,
            'redirect_stats': redirect_stats,
            'ia': ia,
            'rt_by_label_traces': rt_by_label_traces,
            'throughput_traces': throughput_traces,
            'latency_traces': latency_traces,
            'error_rate_traces': error_rate_traces,
            'codes_traces': codes_traces,
            'tps_traces': tps_traces,
            'threads_traces': threads_traces,
            'pie_labels': pie_labels,
            'pie_values': pie_values,
            'pie_colors': pie_colors,
        }

        return _build_plotly_html_isolated(execution_data, prefix=prefix)

    except Exception as e:
        logger.error(f"Error generating Plotly HTML for execution {execution.id}: {e}")
        return _build_exec_html(execution, SectionInput(order=0, type="load_test", source_id=str(execution.id), source_name=execution.name), overrides)


class SectionInput(BaseModel):
    order: int
    type: str
    source_id: str
    source_name: str


class IntegratedReportRequest(BaseModel):
    sections: List[SectionInput]
    unified_conclusions: str = ""
    # F1: identidad del registro en integrated_reports (reusar si el informe ya existe)
    report_id: Optional[str] = None
    name: Optional[str] = None


# F6: columna de test_executions -> clave del dict `ia` que consumen las plantillas
_IA_KEY_BY_COLUMN = {
    "ai_analysis_summary": "summary",
    "ai_analysis_errors": "errors",
    "ai_analysis_response_times": "responseTimes",
    "ai_analysis_response_time_over_time": "responseTimeOverTime",
    "ai_analysis_throughput": "throughput",
    "ai_analysis_latency": "latency",
    "ai_analysis_error_rate": "errorRate",
    "ai_analysis_codes_per_second": "codesPerSecond",
    "ai_analysis_transactions_per_second": "tps",
    "ai_analysis_active_threads": "activeThreads",
    "ai_analysis_redirects": "redirects",
    "ai_conclusions": "conclusions",
    "ai_recommendations": "recommendations",
}


def _apply_ia_overrides(ia: dict, overrides) -> dict:
    """F6: pisa el texto de la IA con lo editado en el informe integrado.

    Solo modifica el dict en memoria que se va a renderizar; la ejecucion
    original NUNCA se toca (Opcion B).
    """
    for column, text in ((overrides or {}).get("analysis") or {}).items():
        key = _IA_KEY_BY_COLUMN.get(column)
        if key and text is not None:
            ia[key] = text
    return ia


async def _load_section_overrides(db: AsyncSession, report_id) -> dict:
    """F6: overrides guardados, leidos de la DB: {source_id: {analysis, images}}.

    Se lee del registro y no del request, para que exportar desde el historial
    (sin haber editado en esta sesion) salga igual de correcto.
    """
    if not report_id:
        return {}
    from app.db.models.integrated_report import IntegratedReport
    try:
        report = await db.get(IntegratedReport, uuid.UUID(str(report_id)))
    except (ValueError, AttributeError):
        return {}
    if not report:
        return {}
    # Una misma ejecucion puede aparecer en varias secciones (reporte + monitoreo
    # + evidencias): se FUSIONAN sus overrides en vez de quedarse con el ultimo.
    out: dict = {}
    for s in (report.sections or []):
        if not isinstance(s, dict) or not s.get("overrides"):
            continue
        ov = s["overrides"]
        dst = out.setdefault(s.get("source_id"), {"analysis": {}, "images": {}})
        dst["analysis"].update(ov.get("analysis") or {})
        dst["images"].update(ov.get("images") or {})
    return out


def _merge_overrides(prev_sections, new_sections):
    """F4: conserva los overrides ya guardados al reescribir `sections`.

    Regenerar el informe o el consolidado manda solo punteros; sin esto el
    texto editado por el usuario se perderia en silencio.
    """
    prev = {
        s.get("source_id"): s.get("overrides")
        for s in (prev_sections or [])
        if isinstance(s, dict) and s.get("overrides")
    }
    if not prev:
        return new_sections
    for s in new_sections:
        ov = prev.get(s.get("source_id"))
        if ov and not s.get("overrides"):
            s["overrides"] = ov
    return new_sections


async def _get_attachments(db: AsyncSession, execution_id: uuid.UUID, att_type: str):
    result = await db.execute(
        select(ExecutionAttachment)
        .where(ExecutionAttachment.execution_id == execution_id, ExecutionAttachment.attachment_type == att_type)
        .order_by(ExecutionAttachment.sort_order)
    )
    return result.scalars().all()


def _img_to_b64(filepath: str, file_type: str) -> str:
    abs_path = os.path.join("/app", filepath.lstrip("/"))
    if os.path.exists(abs_path):
        with open(abs_path, "rb") as f:
            return f'<img src="data:{file_type};base64,{base64.b64encode(f.read()).decode()}" style="max-width:100%;border-radius:8px;margin:8px 0" />'
    return ""


def _build_exec_html(execution, section: SectionInput, overrides=None) -> str:
    label = "Prueba de Carga" if section.type == "load_test" else "Prueba de Estres"
    # F6: fallback sin JTL — tambien respeta el texto editado (solo en memoria)
    _ov = (overrides or {}).get("analysis") or {}
    _summary = _ov.get("ai_analysis_summary", execution.ai_analysis_summary)
    _errors = _ov.get("ai_analysis_errors", execution.ai_analysis_errors)
    _rt = _ov.get("ai_analysis_response_times", execution.ai_analysis_response_times)
    _concl = _ov.get("ai_conclusions", execution.ai_conclusions)
    _recs = _ov.get("ai_recommendations", execution.ai_recommendations)
    er = execution.error_rate or 0
    er_color = '#4caf50' if er < 1 else '#ff9800' if er < 5 else '#f44336'
    # UI-2: sin badge de veredicto en los exports (se conserva solo en pantalla).
    return f"""
    <div style="margin-bottom:24px;page-break-inside:avoid">
        <h2 style="color:#0a1628;border-left:4px solid #f5a623;padding-left:12px">{label}: {section.source_name}</h2>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0">
            <div style="background:#eff6ff;padding:10px;border-radius:8px;border-left:3px solid #3b82f6;text-align:center"><div style="font-size:10px;color:#6b7280;text-transform:uppercase">Total Requests</div><div style="font-size:18px;font-weight:700;color:#0a1628">{execution.total_requests or 0:,}</div></div>
            <div style="background:#{'fef2f2' if er > 1 else 'f0fdf4'};padding:10px;border-radius:8px;border-left:3px solid {er_color};text-align:center"><div style="font-size:10px;color:#6b7280;text-transform:uppercase">Error Rate</div><div style="font-size:18px;font-weight:700;color:{er_color}">{er:.2f}%</div></div>
            <div style="background:#f0fdf4;padding:10px;border-radius:8px;border-left:3px solid #10b981;text-align:center"><div style="font-size:10px;color:#6b7280;text-transform:uppercase">Avg RT</div><div style="font-size:18px;font-weight:700;color:#0a1628">{(execution.avg_response_time or 0):.0f} ms</div></div>
            <div style="background:#faf5ff;padding:10px;border-radius:8px;border-left:3px solid #8b5cf6;text-align:center"><div style="font-size:10px;color:#6b7280;text-transform:uppercase">Throughput</div><div style="font-size:18px;font-weight:700;color:#0a1628">{(execution.throughput or 0):.2f} req/s</div></div>
        </div>
        <table style="width:100%;border-collapse:collapse;margin:12px 0">
            <tr style="background:#0a1628;color:white"><th style="padding:8px;text-align:left">Metrica</th><th style="padding:8px;text-align:right">Valor</th></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee">Total Requests</td><td style="padding:6px;text-align:right;border-bottom:1px solid #eee">{execution.total_requests or 0:,}</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee">Tasa de Error</td><td style="padding:6px;text-align:right;border-bottom:1px solid #eee">{(execution.error_rate or 0):.2f}%</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee">Tiempo Respuesta Promedio</td><td style="padding:6px;text-align:right;border-bottom:1px solid #eee">{(execution.avg_response_time or 0):.0f} ms</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee">P90</td><td style="padding:6px;text-align:right;border-bottom:1px solid #eee">{(execution.p90_response_time or 0):.0f} ms</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee">P95</td><td style="padding:6px;text-align:right;border-bottom:1px solid #eee">{(execution.p95_response_time or 0):.0f} ms</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee">P99</td><td style="padding:6px;text-align:right;border-bottom:1px solid #eee">{(execution.p99_response_time or 0):.0f} ms</td></tr>
            <tr><td style="padding:6px">Throughput</td><td style="padding:6px;text-align:right">{(execution.throughput or 0):.2f} req/s</td></tr>
        </table>
        <div style="background:#fff7ed;border-left:4px solid #f97316;padding:12px;border-radius:8px;margin:8px 0">
            <h3 style="color:#0a1628;margin:0 0 8px 0;font-size:13px">Analisis General</h3>
            <p style="font-size:13px;line-height:1.6;color:#334155">{_summary or 'Sin analisis disponible.'}</p>
        </div>
        {f'<div style="background:#fff7ed;border-left:4px solid #f97316;padding:12px;border-radius:8px;margin:8px 0"><h3 style="color:#0a1628;margin:0 0 8px 0;font-size:13px">Analisis de Errores</h3><p style="font-size:13px;line-height:1.6;color:#334155">{_errors}</p></div>' if _errors else ''}
        {f'<div style="background:#fff7ed;border-left:4px solid #f97316;padding:12px;border-radius:8px;margin:8px 0"><h3 style="color:#0a1628;margin:0 0 8px 0;font-size:13px">Tiempos de Respuesta</h3><p style="font-size:13px;line-height:1.6;color:#334155">{_rt}</p></div>' if _rt else ''}
        {f'<div style="background:#fff7ed;border-left:4px solid #f97316;padding:12px;border-radius:8px;margin:8px 0"><h3 style="color:#0a1628;margin:0 0 8px 0;font-size:13px">Conclusiones</h3><p style="font-size:13px;line-height:1.6;color:#334155">{_concl}</p></div>' if _concl else ''}
        {f'<div style="background:#fff7ed;border-left:4px solid #f97316;padding:12px;border-radius:8px;margin:8px 0"><h3 style="color:#0a1628;margin:0 0 8px 0;font-size:13px">Recomendaciones</h3><p style="font-size:13px;line-height:1.6;color:#334155">{_recs}</p></div>' if _recs else ''}
    </div>"""


def _strip_individual_report_extras(body_html: str) -> str:
    """Strip conclusions, recommendations and footer from individual report body.
    These are added separately by the integrated report at the end."""
    import re as _re
    original_len = len(body_html)

    # Strip the comment + conclusions ai-box (border-left-color:#6366f1)
    body_html = _re.sub(
        r'<!-- ===== CONCLUSIONES Y RECOMENDACIONES ===== -->.*?'
        r'<div class="ai-box"[^>]*style="[^"]*#6366f1[^"]*"[^>]*>.*?</div>\s*</div>\s*</div>',
        '', body_html, flags=_re.DOTALL
    )
    # Strip recommendations ai-box (border-left-color:#10b981)
    body_html = _re.sub(
        r'<div class="ai-box"[^>]*style="[^"]*#10b981[^"]*"[^>]*>.*?</div>\s*</div>\s*</div>',
        '', body_html, flags=_re.DOTALL
    )
    # Strip report-footer
    body_html = _re.sub(
        r'<div class="report-footer">.*?</div>',
        '', body_html, flags=_re.DOTALL
    )

    stripped = original_len - len(body_html)
    if stripped == 0:
        logger.warning("_strip_individual_report_extras: nothing stripped — markers may have changed")
    else:
        logger.info(f"_strip_individual_report_extras: stripped {stripped} chars of duplicated content")
    return body_html


def _strip_pdf_individual_conclusions(html: str) -> str:
    """B.1 Fix 1: Strip the per-execution 'Conclusiones y Recomendaciones' block
    from an individual PDF HTML produced by build_pdf_html.
    The consolidated unified block is added separately at the end of the integrated PDF,
    so individual per-execution conclusions/recommendations must not appear in the integrated flow.
    Standalone PDF exports (export_pdf.py) do NOT call this function — they preserve their blocks.

    Strategy: build_pdf_html emits the block between two well-known comment markers:
        <!-- ===== CONCLUSIONES Y RECOMENDACIONES ... ===== -->
        ... (conclusions-block div)
        <!-- ===== FOOTER ===== -->
    We strip everything between the CONCLUSIONES comment and the FOOTER comment.
    """
    import re as _re
    original_len = len(html)

    # Primary strategy: comment-boundary strip
    html = _re.sub(
        r'<!--\s*=+\s*CONCLUSIONES Y RECOMENDACIONES.*?(?=<!--\s*=+\s*FOOTER)',
        '', html, flags=_re.DOTALL | _re.IGNORECASE,
    )
    # Fallback: if comment boundary is missing, strip a whole <div class="conclusions-block">
    # using tag-balanced matching (up to the div that contains 2 ai-box children)
    if '<div class="conclusions-block"' in html:
        html = _re.sub(
            r'<div\s+class="conclusions-block"[^>]*>(?:[^<]|<(?!/?div))*'
            r'(?:<div[^>]*>(?:[^<]|<(?!/?div))*(?:<div[^>]*>[^<]*(?:<[^/][^>]*>[^<]*</[^>]*>)*[^<]*</div>\s*)*[^<]*</div>\s*)*'
            r'\s*</div>',
            '', html, flags=_re.DOTALL | _re.IGNORECASE,
        )
    # Final fallback: orphan h2 headers
    html = _re.sub(r'<h[23][^>]*>\s*Conclusiones\s+y\s+Recomendaciones\s*</h[23]>', '', html, flags=_re.IGNORECASE)
    html = _re.sub(r'<h[23][^>]*>\s*Conclusiones\s*</h[23]>', '', html, flags=_re.IGNORECASE)
    html = _re.sub(r'<h[23][^>]*>\s*Recomendaciones\s*</h[23]>', '', html, flags=_re.IGNORECASE)

    stripped = original_len - len(html)
    if stripped == 0:
        logger.warning("_strip_pdf_individual_conclusions: nothing stripped — markers may have changed")
    else:
        logger.info(f"_strip_pdf_individual_conclusions: stripped {stripped} chars of duplicated conclusions")
    return html


def _flatten_consolidated(consolidated: dict) -> str:
    """N2.2-A: aplana el consolidado al texto plano que consumen los exports.
    Mismo formato que flattenConsolidated() en IntegratedReportPage.tsx."""
    parts = []
    for tt, d in (consolidated or {}).items():
        if tt.startswith("_") or not isinstance(d, dict):
            continue
        concl = (d.get("conclusions") or "").strip()
        recs = (d.get("recommendations") or "").strip()
        if not concl and not recs:
            continue
        label = "PRUEBA DE CARGA" if tt == "load" else "PRUEBA DE ESTRES"
        parts.append(f"{label}\n\nConclusiones:\n{concl}\n\nRecomendaciones:\n{recs}")
    return "\n\n---\n\n".join(parts)


async def _resolve_unified_conclusions(db: AsyncSession, request) -> str:
    """N2.2-A: el consolidado vive en integrated_reports.consolidated_analysis,
    pero los exports solo pintaban request.unified_conclusions — un estado de
    React que cualquier regeneracion del informe puede dejar vacio. Cuando eso
    pasaba, el PDF salia sin el bloque y sin avisar. Si el request llega vacio se
    lee de la DB, igual que F6 hace con los textos editados de cada seccion.
    """
    text = (request.unified_conclusions or "").strip()
    if text or not getattr(request, "report_id", None):
        return text
    try:
        from app.db.models.integrated_report import IntegratedReport
        report = await db.get(IntegratedReport, uuid.UUID(request.report_id))
    except (ValueError, AttributeError):
        return ""
    text = _flatten_consolidated((report.consolidated_analysis or {}) if report else {}).strip()
    if text:
        logger.info(f"_resolve_unified_conclusions: {len(text)} chars recuperados del consolidado en DB")
    else:
        logger.warning("_resolve_unified_conclusions: el informe no tiene consolidado generado")
    return text


def _extract_style_from_individual_report(full_html: str) -> str:
    """Extract <style> CSS from build_pdf_html output for injection into integrated report."""
    import re as _re
    style_match = _re.search(r'<style[^>]*>(.*?)</style>', full_html, _re.DOTALL | _re.IGNORECASE)
    if style_match:
        css = style_match.group(1)
        logger.info(f"_extract_style: extracted {len(css)} chars of CSS")
        return css
    logger.warning("_extract_style: NO <style> block found")
    return ""


def _build_att_html(section: SectionInput, attachments, ai_analysis: str, title_prefix: str, for_pdf: bool = False, image_overrides=None) -> str:
    """Build HTML for monitoring/evidence sections.
    Works for both HTML (browser, Plotly integrated) and PDF (WeasyPrint).
    - B4.1: title_prefix is used as-is (no duplicated source_name)
    - B4.3: AI boxes use unified Indigo (#4f46e5) style
    - B3/B4.2: outer wrapper gets monitoreo-block/evidencias-block class (visual separator in PDF)
    - WeasyPrint compat: no display:flex — uses text-align:center / block margin:0 auto
    - B.1 Fix 4: when for_pdf=True, images use explicit width:100%;max-width:800px for proper PDF sizing
    """
    # Pick wrapper/title class based on section type (for PDF page-break rules via CSS)
    if section.type == "monitoring":
        wrapper_class = "monitoreo-block"
        title_class = "monitoreo-title"
    elif section.type == "evidence":
        wrapper_class = "evidencias-block"
        title_class = "evidencias-title"
    else:
        wrapper_class = ""
        title_class = ""

    # Fix 7.3: PDF uses pt/mm matching build_pdf_html standalone; HTML keeps rem for browser rendering.
    _font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"
    if for_pdf:
        ai_box_style = (
            "background:#ffffff;border:2px solid #4f46e5;border-left:6px solid #4f46e5;"
            f"border-radius:1.5mm;padding:3mm 4mm;margin:2mm 0 4mm 0;"
            f"page-break-inside:avoid;break-inside:avoid;font-family:{_font};text-align:left"
        )
        ai_title_style = f"font-size:8.5pt;font-weight:700;color:#0a1628;margin-bottom:1.5mm;font-family:{_font}"
        ai_text_style = f"font-size:8pt;line-height:1.6;color:#334155;font-family:{_font}"
        card_style = (
            "background:#ffffff;border-radius:2mm;padding:3mm 4mm;margin:2mm 0;"
            f"page-break-inside:avoid;break-inside:avoid;font-family:{_font}"
        )
        card_title_style = (
            "font-size:10pt;font-weight:700;color:#0a1628;"
            f"border-left:1mm solid #0a1628;padding-left:3mm;margin-bottom:2mm;"
            f"text-align:left;font-family:{_font}"
        )
        img_wrapper_style = "margin:2mm 0"
        img_style = (
            "display:block;margin:0 auto;max-width:100%;max-height:60mm;"
            "width:auto;height:auto;object-fit:contain;border-radius:1.5mm"
        )
    else:
        ai_box_style = (
            "background:#ffffff;border:2px solid #4f46e5;border-left:6px solid #4f46e5;"
            f"border-radius:8px;padding:1.2rem;margin:1rem 0;"
            f"page-break-inside:avoid;break-inside:avoid;font-family:{_font};text-align:left"
        )
        ai_title_style = f"font-size:1rem;font-weight:700;color:#0a1628;margin-bottom:.5rem;font-family:{_font}"
        ai_text_style = f"font-size:.9rem;line-height:1.8;color:#334155;font-family:{_font}"
        card_style = (
            "background:#ffffff;border-radius:10px;padding:1.5rem;margin:1rem 0;"
            f"box-shadow:0 1px 4px rgba(0,0,0,.08);text-align:center;"
            f"page-break-inside:avoid;break-inside:avoid;font-family:{_font}"
        )
        card_title_style = (
            "font-size:1.1rem;font-weight:700;color:#0a1628;"
            f"border-left:4px solid #0a1628;padding-left:.75rem;margin-bottom:1rem;"
            f"display:inline-block;text-align:left;font-family:{_font}"
        )
        img_wrapper_style = "text-align:center;margin:1rem 0"
        img_style = "max-width:100%;max-height:800px;border-radius:8px;display:block;margin:0 auto"

    items = ""
    for att in attachments:
        img_html = ""
        if att.file_type and att.file_type.startswith("image/"):
            abs_path = os.path.join("/app", att.filepath.lstrip("/"))
            if os.path.exists(abs_path):
                with open(abs_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                img_html = (
                    f'<div style="{img_wrapper_style}">'
                    f'<img src="data:{att.file_type};base64,{b64}" style="{img_style}" />'
                    f'</div>'
                )
        per_img_ai = ""
        # F6: el texto editado en el informe integrado gana sobre el de la IA
        att_text = (image_overrides or {}).get(str(att.id)) or getattr(att, 'ai_analysis', None)
        if att_text:
            per_img_ai = (
                f'<div style="{ai_box_style}">'
                f'<div style="{ai_title_style}">Analisis</div>'
                f'<div style="{ai_text_style}">{att_text}</div>'
                f'</div>'
            )
        items += (
            f'<div style="{card_style}">'
            f'<div style="{card_title_style}">{att.title or att.filename}</div>'
            f'{img_html}'
            f'{per_img_ai}'
            f'</div>'
        )

    analysis_html = ""
    if ai_analysis:
        analysis_html = (
            f'<div style="{ai_box_style}">'
            f'<div style="{ai_title_style}">Analisis Global</div>'
            f'<div style="{ai_text_style}">{ai_analysis}</div>'
            f'</div>'
        )

    # Section title — PDF uses pt/mm, HTML uses rem
    if for_pdf:
        section_header_style = (
            "font-size:11pt;font-weight:700;color:#0a1628;"
            f"border-left:1mm solid #4f46e5;padding-left:3mm;margin:3mm 0 2mm 0;"
            f"text-align:left;page-break-after:avoid;break-after:avoid;font-family:{_font}"
        )
        wrapper_inline = f"margin:4mm 0;font-family:{_font}"
    else:
        section_header_style = (
            "font-size:1.3rem;font-weight:700;color:#0a1628;"
            f"border-left:4px solid #4f46e5;padding-left:.75rem;margin:1.5rem 0 1rem 0;"
            f"text-align:left;page-break-after:avoid;break-after:avoid;font-family:{_font}"
        )
        wrapper_inline = f"margin:2rem 0;font-family:{_font}"
    return (
        f'<div class="{wrapper_class}" style="{wrapper_inline}">'
        f'<div class="{title_class}" style="{section_header_style}">{title_prefix}</div>'
        f'{items}'
        f'{analysis_html}'
        f'</div>'
    )


@router.post("/integrated")
async def generate_integrated_report(
    request: IntegratedReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate integrated report from multiple sections in user-defined order."""
    sections_html = []
    all_conclusions = []

    for section in sorted(request.sections, key=lambda s: s.order):
        try:
            exec_id = uuid.UUID(section.source_id)
        except (ValueError, AttributeError):
            continue

        result = await db.execute(select(TestExecution).where(TestExecution.id == exec_id))
        execution = result.scalar_one_or_none()
        if not execution:
            continue

        if section.type in ("load_test", "stress_test"):
            sections_html.append(_build_exec_html(execution, section))
            if execution.ai_conclusions:
                all_conclusions.append(f"[{section.source_name}]: {execution.ai_conclusions}")

        elif section.type == "monitoring":
            atts = await _get_attachments(db, exec_id, "monitoring")
            cap_data = json.loads(execution.capacity_analysis_json or "{}")
            global_ai = cap_data.get("monitoring_ai_analysis", "")
            # Monitoring section: show images + per-image AI. Global analysis goes to conclusions only.
            sections_html.append(_build_att_html(section, atts, "", "Metricas de Monitoreo"))
            # Collect individual image analyses + global analysis for conclusions
            for att in atts:
                if att.ai_analysis:
                    all_conclusions.append(f"[Monitoreo — {att.category or ''}: {att.title or att.filename}]: {att.ai_analysis}")
            if global_ai:
                all_conclusions.append(f"[Analisis Global Monitoreo — {section.source_name}]: {global_ai}")

        elif section.type == "evidence":
            atts = await _get_attachments(db, exec_id, "evidence")
            cap_data = json.loads(execution.capacity_analysis_json or "{}")
            global_ai = cap_data.get("evidence_ai_analysis", "")
            # Evidence section: show images + per-image AI. Global analysis goes to conclusions only.
            sections_html.append(_build_att_html(section, atts, "", "Evidencias y Hallazgos"))
            for att in atts:
                if att.ai_analysis:
                    all_conclusions.append(f"[Evidencia — {att.category or ''}: {att.title or att.filename}]: {att.ai_analysis}")
            if global_ai:
                all_conclusions.append(f"[Analisis Global Evidencias — {section.source_name}]: {global_ai}")

    # Generate unified conclusions with AI — includes execution, monitoring and evidence analyses
    unified = ""
    if all_conclusions:
        try:
            from app.services.ai.gemini import get_gemini_analyzer, load_ai_config_from_db, SYSTEM_PROMPT
            ai_conf = await load_ai_config_from_db(db)
            gemini = get_gemini_analyzer(
                provider=ai_conf.get("provider", ""),
                model_name=ai_conf.get("model_name", ""),
                api_key=ai_conf.get("api_key", ""),
            )
            prompt = f"""{SYSTEM_PROMPT}

A partir de los siguientes analisis de diferentes pruebas de performance del mismo sistema,
incluyendo datos de ejecucion, metricas de monitoreo de infraestructura y evidencias recopiladas,
redacta conclusiones y recomendaciones UNIFICADAS que correlacionen TODOS los hallazgos.

{chr(10).join(all_conclusions)}

Instrucciones:
- Resumen ejecutivo de 2-3 parrafos sintetizando TODAS las pruebas y correlacionando con el monitoreo.
- Luego conclusiones consolidadas como puntos numerados (maximo 7).
- Luego recomendaciones prioritarias como puntos numerados (maximo 7).
- Correlaciona las metricas de infraestructura (CPU, memoria, threads) con el rendimiento observado.
- Elimina duplicados. Prioriza por impacto. No repitas lo de las secciones individuales.
"""
            unified = gemini._generate(prompt, section_name="unified_conclusions") or ""
        except Exception as e:
            logger.error(f"Unified conclusions AI failed: {e}")
            unified = "Conclusiones unificadas no disponibles."

    # F1: crear (o reusar) el registro en integrated_reports apenas se genera el
    # informe, para que las ediciones tengan una fila destino desde el minuto cero.
    # No se toca consolidated_analysis: lo escribe generate-consolidated.
    from app.db.models.integrated_report import IntegratedReport
    from sqlalchemy.orm.attributes import flag_modified

    report_id = None
    report_name = None
    try:
        sections_json = [s.dict() for s in sorted(request.sections, key=lambda s: s.order)]
        existing = None
        if request.report_id:
            try:
                existing = await db.get(IntegratedReport, uuid.UUID(request.report_id))
            except (ValueError, AttributeError):
                existing = None

        if existing:
            # F4: regenerar NO puede borrar el texto editado ya guardado
            existing.sections = _merge_overrides(existing.sections, sections_json)
            flag_modified(existing, "sections")
            if request.name:
                existing.name = request.name
            await db.commit()
            await db.refresh(existing)
            report_id, report_name = str(existing.id), existing.name
        else:
            default_name = request.name or (
                f"Informe Integrado - {datetime.now(ZoneInfo('America/Bogota')).strftime('%d/%m/%Y %H:%M')}"
            )
            new_report = IntegratedReport(
                name=default_name,
                sections=sections_json,
                consolidated_analysis={},
                created_by=current_user.id,
            )
            db.add(new_report)
            await db.commit()
            await db.refresh(new_report)
            report_id, report_name = str(new_report.id), new_report.name
    except Exception as e:
        # El informe generado se devuelve igual; el frontend avisa que no hay
        # registro donde persistir las ediciones.
        logger.exception(f"F1: no se pudo crear el registro del informe integrado: {e}")
        await db.rollback()

    return {
        "report_html": "\n".join(sections_html),
        "unified_conclusions": unified,
        "sections_count": len(sections_html),
        "report_id": report_id,
        "report_name": report_name,
    }


@router.post("/integrated/export-pdf")
async def export_integrated_pdf(
    request: IntegratedReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export integrated report to PDF — FULL quality with charts, same as individual export."""
    now_str = datetime.now(ZoneInfo("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S")
    import re

    # Collect execution info for cover page
    exec_info_list = []
    html_parts = []
    extracted_style = ""  # HF10g: collected once from first build_pdf_html call
    # F6: texto editado, leido de la DB (no del request)
    overrides_by_exec = await _load_section_overrides(db, request.report_id)

    for section in sorted(request.sections, key=lambda s: s.order):
        try:
            exec_id = uuid.UUID(section.source_id)
        except (ValueError, AttributeError):
            continue

        result = await db.execute(select(TestExecution).where(TestExecution.id == exec_id))
        execution = result.scalar_one_or_none()
        if not execution:
            continue

        if section.type in ("load_test", "stress_test"):
            exec_info_list.append({
                'name': execution.name,
                'client': execution.client or '—',
                'test_type': (execution.test_type or 'load').upper(),
                'date': execution.execution_date.strftime('%d/%m/%Y') if execution.execution_date else '—',
            })
            full_html = await _generate_full_execution_pdf_html(execution, db, overrides_by_exec.get(section.source_id))
            # HF10g: extract <style> ONCE from first individual report
            if not extracted_style:
                extracted_style = _extract_style_from_individual_report(full_html)
            body_match = re.search(r'<body[^>]*>(.*)</body>', full_html, re.DOTALL)
            body_content = body_match.group(1) if body_match else full_html
            # Fix 7: strip conclusions FIRST (needs <!-- FOOTER --> comment as regex anchor)
            body_content = _strip_pdf_individual_conclusions(body_content)
            # Then strip footer + stale extras (footer comment already consumed by above)
            body_content = _strip_individual_report_extras(body_content)
            html_parts.append(f'<div style="page-break-before:always">{body_content}</div>')

        elif section.type == "monitoring":
            atts = await _get_attachments(db, exec_id, "monitoring")
            _imgs = (overrides_by_exec.get(section.source_id) or {}).get("images")
            html_parts.append(_build_att_html(section, atts, "", "Metricas de Monitoreo", for_pdf=True, image_overrides=_imgs))

        elif section.type == "evidence":
            atts = await _get_attachments(db, exec_id, "evidence")
            _imgs = (overrides_by_exec.get(section.source_id) or {}).get("images")
            html_parts.append(_build_att_html(section, atts, "", "Evidencias y Hallazgos", for_pdf=True, image_overrides=_imgs))

    # B2: integrated PDF header removed. PDF starts directly with the first
    # execution's compact cover (from build_pdf_html via _generate_full_execution_pdf_html).

    # Unified conclusions (B1+B3: forced new page via .conclusions-block, boxes don't split)
    conclusions_html = ""
    unified_text = await _resolve_unified_conclusions(db, request)   # N2.2-A
    if unified_text:
        conclusions_html = f'''
        <div class="conclusions-block" style="padding:20px">
        <h2 class="conclusions-title">Conclusiones y Recomendaciones</h2>
        <div class="ai-box"><div class="ai-text" style="white-space:pre-wrap">{unified_text}</div></div>
        </div>'''

    full_pdf_html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8">
<style>
{extracted_style}
@page {{ size: A4 landscape; margin: 1.5cm; }}
@page :first {{ margin: 0; }}
/* PDF-1: la portada mide ~210mm y solo cabe en una pagina sin margenes. Con
   `:first` eso solo valia para la pagina 1, asi que en un integrado con varias
   ejecuciones la 2a portada en adelante se partia en dos. Con pagina nombrada,
   TODA portada cae en su propia pagina sin margen. */
@page cover {{ margin: 0; @bottom-center {{ content: none; }} }}
.cover {{ page: cover; }}
img {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
{''.join(html_parts)}
{conclusions_html}
<div style="text-align:center;margin-top:30px;padding:12px;border-top:0.5mm solid #4f46e5;font-size:8px;color:#666">
<strong style="color:#0a1628">sqa &mdash; Software Quality Assurance</strong><br>
Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos
</div>
</body></html>"""

    try:
        from weasyprint import HTML as WeasyprintHTML
        pdf_bytes = WeasyprintHTML(string=full_pdf_html).write_pdf()
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=informe_integrado.pdf"})
    except Exception as e:
        logger.exception(f"PDF generation failed: {e}")
        raise HTTPException(500, f"Error generando PDF: {str(e)}")


@router.post("/integrated/export-html")
async def export_integrated_html(
    request: IntegratedReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export integrated report as standalone HTML with Plotly interactive charts (HF10h)."""
    now_str = datetime.now(ZoneInfo("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S")

    exec_info_list = []
    html_parts = []
    # F6: texto editado, leido de la DB (no del request)
    overrides_by_exec = await _load_section_overrides(db, request.report_id)

    for idx, section in enumerate(sorted(request.sections, key=lambda s: s.order)):
        try:
            exec_id = uuid.UUID(section.source_id)
        except (ValueError, AttributeError):
            continue
        result = await db.execute(select(TestExecution).where(TestExecution.id == exec_id))
        execution = result.scalar_one_or_none()
        if not execution:
            continue

        if section.type in ("load_test", "stress_test"):
            exec_info_list.append({
                'name': execution.name,
                'client': execution.client or '—',
                'test_type': (execution.test_type or 'load').upper(),
                'date': execution.execution_date.strftime('%d/%m/%Y') if execution.execution_date else '—',
            })
            # HF10h: Use Plotly interactive fragment with unique prefix per execution
            fragment = await _generate_full_execution_plotly_html(execution, db, prefix=f"sec{idx}_", overrides=overrides_by_exec.get(section.source_id))
            html_parts.append(f'<div style="border-top:3px solid #f5a623;margin-top:40px;padding-top:20px">{fragment}</div>')
        elif section.type == "monitoring":
            atts = await _get_attachments(db, exec_id, "monitoring")
            _imgs = (overrides_by_exec.get(section.source_id) or {}).get("images")
            html_parts.append(f'<div class="att-wrap">{_build_att_html(section, atts, "", "Metricas de Monitoreo", image_overrides=_imgs)}</div>')
        elif section.type == "evidence":
            atts = await _get_attachments(db, exec_id, "evidence")
            _imgs = (overrides_by_exec.get(section.source_id) or {}).get("images")
            html_parts.append(f'<div class="att-wrap">{_build_att_html(section, atts, "", "Evidencias y Hallazgos", image_overrides=_imgs)}</div>')

    # HF10h BLOQUE A.1: Integrated header removed. Report starts directly with
    # the yellow separator + individual execution cover (restored in _build_plotly_html_isolated).
    # N2.2-A: mismo fallback a DB que el PDF. Ademas el bloque pasa a ser
    # condicional: sin consolidado ya no se emite una caja vacia con titulo.
    conclusions_text = await _resolve_unified_conclusions(db, request)
    conclusions_html = f'''<div class="conclusions-wrap">
    <h2>Conclusiones y Recomendaciones</h2>
    <div class="conclusions-box">{conclusions_text}</div>
</div>''' if conclusions_text else ''
    full_html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Informe Integrado - SQA Kinetix Pro</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
{PLOTLY_INTEGRATED_CSS}
<style>
body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f4f8; }}
img {{ max-width: 100%; height: auto; }}
.integrated-wrap {{ max-width: 1400px; margin: 0 auto; padding: 0; }}
.att-wrap {{ max-width: 1400px; margin: 0 auto; padding: 2rem; box-sizing: border-box; }}
.conclusions-wrap {{ max-width: 1400px; margin: 40px auto 0 auto; padding: 2rem; box-sizing: border-box; border-top: 3px solid #f5a623; }}
.conclusions-wrap h2 {{ color: #0a1628; font-size: 1.5rem; margin-bottom: 15px; text-align: left; }}
.conclusions-box {{ background: #ffffff; border: 2px solid #4f46e5; border-left: 6px solid #4f46e5; border-radius: 8px; padding: 1.2rem; line-height: 1.8; color: #333; white-space: pre-wrap; }}
.integrated-footer {{ max-width: 1400px; margin: 40px auto 0 auto; padding: 15px 2rem; box-sizing: border-box; border-top: 2px solid #f5a623; text-align: center; font-size: 12px; color: #666; }}
.integrated-footer strong {{ color: #0a1628; }}
</style>
</head>
<body>
<div class="integrated-wrap">
{''.join(html_parts)}
</div>
{conclusions_html}
<div class="integrated-footer">
    <strong>sqa &mdash; Software Quality Assurance</strong><br>
    Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos
</div>
</body></html>"""

    return Response(
        content=full_html.encode("utf-8"),
        media_type="text/html",
        headers={"Content-Disposition": "attachment; filename=informe_integrado.html"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HF9 — Consolidated Analysis (dual Load/Stress support)
# ═══════════════════════════════════════════════════════════════════════════════

class ConsolidatedRequest(BaseModel):
    sections: List[SectionInput]
    report_id: Optional[str] = None
    name: Optional[str] = None


@router.post("/integrated/generate-consolidated")
async def generate_consolidated_analysis(
    request: ConsolidatedRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate consolidated analysis separated by test type (Load/Stress)."""
    from app.services.ai.gemini import get_gemini_analyzer, load_ai_config_from_db, SYSTEM_PROMPT, sanitize_ai_text

    BOGOTA_TZ = ZoneInfo("America/Bogota")

    # HF9.1: Extract __meta section for report_id if present
    real_sections = [s for s in request.sections if s.type != '__meta']
    meta_section = next((s for s in request.sections if s.type == '__meta'), None)
    if meta_section and not request.report_id:
        request.report_id = meta_section.source_id
    if meta_section and not request.name:
        request.name = meta_section.source_name or None
    # Use real_sections for processing
    request_sections = real_sections

    # F5 (B4): el consolidado se redacta sobre el texto EDITADO por el usuario,
    # no sobre el original de la IA. Misma fuente que usan los exports (F6).
    overrides_by_exec = await _load_section_overrides(db, request.report_id)

    # Group executions by test_type
    executions_by_type: dict = {}  # { "load": [...], "stress": [...] }

    for section in sorted(request_sections, key=lambda s: s.order):
        try:
            exec_id = uuid.UUID(section.source_id)
        except (ValueError, AttributeError):
            continue

        result = await db.execute(select(TestExecution).where(TestExecution.id == exec_id))
        execution = result.scalar_one_or_none()
        if not execution:
            continue

        if section.type in ("load_test", "stress_test"):
            tt = "load" if section.type == "load_test" else "stress"
            if tt not in executions_by_type:
                executions_by_type[tt] = []

            # Collect KPIs + AI analyses
            kpis = (
                f"Total Requests: {execution.total_requests}, "
                f"Error Rate: {execution.error_rate}%, "
                f"Avg RT: {execution.avg_response_time}ms, "
                f"P90: {execution.p90_response_time}ms, "
                f"P95: {execution.p95_response_time}ms, "
                f"P99: {execution.p99_response_time}ms, "
                f"Throughput: {execution.throughput} req/s, "
                f"Avg Latency: {execution.avg_latency or 0}ms, "
                f"Duration: {execution.duration_seconds or 0}s"
            )

            # Get verdict
            verdict = ""
            if isinstance(execution.acceptance_criteria_json, dict):
                verdict = execution.acceptance_criteria_json.get("verdict", "")

            # F5 (B4): si el usuario corrigio el texto de esta seccion, la version
            # corregida es la que alimenta el prompt. Sin overrides, identico a antes.
            _ov = (overrides_by_exec.get(section.source_id) or {}).get("analysis") or {}
            executions_by_type[tt].append({
                "name": execution.name,
                "kpis": kpis,
                "verdict": verdict,
                "conclusions": _ov.get("ai_conclusions", execution.ai_conclusions) or "",
                "recommendations": _ov.get("ai_recommendations", execution.ai_recommendations) or "",
            })

        elif section.type == "monitoring":
            atts = await _get_attachments(db, exec_id, "monitoring")
            cap_data = json.loads(execution.capacity_analysis_json or "{}")
            global_ai = cap_data.get("monitoring_ai_analysis", "")
            # Determine which test_type this execution belongs to
            tt = "stress" if (execution.test_type or "").lower() in ("stress", "spike") else "load"
            if tt not in executions_by_type:
                executions_by_type[tt] = []
            monitoring_texts = []
            for att in atts:
                if att.ai_analysis:
                    monitoring_texts.append(f"[{att.category or ''}: {att.title or att.filename}]: {att.ai_analysis}")
            if global_ai:
                monitoring_texts.append(f"[Global]: {global_ai}")
            if monitoring_texts:
                # Append to existing entries or create a monitoring-only entry
                for entry in executions_by_type[tt]:
                    if "monitoring_analysis" not in entry:
                        entry["monitoring_analysis"] = "\n".join(monitoring_texts)
                        break
                else:
                    executions_by_type[tt].append({"monitoring_analysis": "\n".join(monitoring_texts)})

        elif section.type == "evidence":
            atts = await _get_attachments(db, exec_id, "evidence")
            cap_data = json.loads(execution.capacity_analysis_json or "{}")
            global_ai = cap_data.get("evidence_ai_analysis", "")
            tt = "stress" if (execution.test_type or "").lower() in ("stress", "spike") else "load"
            if tt not in executions_by_type:
                executions_by_type[tt] = []
            evidence_texts = []
            for att in atts:
                if att.ai_analysis:
                    evidence_texts.append(f"[{att.category or ''}: {att.title or att.filename}]: {att.ai_analysis}")
            if global_ai:
                evidence_texts.append(f"[Global]: {global_ai}")
            if evidence_texts:
                for entry in executions_by_type[tt]:
                    if "evidence_analysis" not in entry:
                        entry["evidence_analysis"] = "\n".join(evidence_texts)
                        break
                else:
                    executions_by_type[tt].append({"evidence_analysis": "\n".join(evidence_texts)})

    if not executions_by_type:
        raise HTTPException(400, "No se encontraron ejecuciones para analizar")

    # Generate consolidated analysis per test type
    ai_conf = await load_ai_config_from_db(db)
    gemini = get_gemini_analyzer(
        provider=ai_conf.get("provider", ""),
        model_name=ai_conf.get("model_name", ""),
        api_key=ai_conf.get("api_key", ""),
    )

    consolidated = {}
    for test_type, entries in executions_by_type.items():
        type_label = "CARGA (LOAD)" if test_type == "load" else "ESTRES (STRESS)"

        # Compile all data for this test type
        all_kpis = "\n".join(e.get("kpis", "") for e in entries if e.get("kpis"))
        all_verdicts = ", ".join(e.get("verdict", "N/A") for e in entries if e.get("verdict"))
        all_conclusions = "\n".join(e.get("conclusions", "") for e in entries if e.get("conclusions"))
        all_recommendations = "\n".join(e.get("recommendations", "") for e in entries if e.get("recommendations"))
        all_monitoring = "\n".join(e.get("monitoring_analysis", "") for e in entries if e.get("monitoring_analysis"))
        all_evidence = "\n".join(e.get("evidence_analysis", "") for e in entries if e.get("evidence_analysis"))

        prompt = f"""{SYSTEM_PROMPT}

Eres un ingeniero senior de performance testing en SQA Colombia. Genera un analisis consolidado
de la prueba de tipo {type_label} correlacionando KPIs, conclusiones previas, monitoreo y evidencias.

DATOS DE LA PRUEBA ({type_label}):

KPIs principales:
{all_kpis or 'No disponibles'}

Veredictos: {all_verdicts or 'No determinados'}

Conclusiones originales del reporte:
{all_conclusions or 'Sin conclusiones previas.'}

Recomendaciones originales del reporte:
{all_recommendations or 'Sin recomendaciones previas.'}

Analisis del monitoreo de infraestructura:
{all_monitoring or 'Sin analisis de monitoreo disponible.'}

Analisis de evidencias visuales:
{all_evidence or 'Sin analisis de evidencias disponible.'}

INSTRUCCIONES:
1. Genera DOS bloques separados con estos encabezados EXACTOS:
   ===CONCLUSIONES_CONSOLIDADAS===
   (conclusiones correlacionando KPIs con monitoreo y evidencias, maximo 400 palabras)
   ===RECOMENDACIONES_CONSOLIDADAS===
   (recomendaciones accionables priorizadas por impacto, maximo 400 palabras)

2. Correlaciona los KPIs con lo observado en monitoreo y evidencias.
3. NO repitas literalmente las conclusiones originales, refinalas y enriquecelas.
4. Las recomendaciones deben ser accionables y priorizadas (Critica, Alta, Media).
5. Tono profesional tecnico en espanol de Colombia.
6. Sin markdown, sin asteriscos, sin las palabras prohibidas.
"""

        try:
            raw = gemini._generate(prompt, section_name=f"consolidated_{test_type}") or ""
            raw = sanitize_ai_text(raw)

            # Parse conclusions and recommendations
            conclusions_text = ""
            recommendations_text = ""
            if "===CONCLUSIONES_CONSOLIDADAS===" in raw and "===RECOMENDACIONES_CONSOLIDADAS===" in raw:
                parts = raw.split("===RECOMENDACIONES_CONSOLIDADAS===")
                conclusions_text = parts[0].split("===CONCLUSIONES_CONSOLIDADAS===")[-1].strip()
                recommendations_text = parts[1].strip() if len(parts) > 1 else ""
            else:
                midpoint = len(raw) // 2
                conclusions_text = raw[:midpoint].strip()
                recommendations_text = raw[midpoint:].strip()

            consolidated[test_type] = {
                "conclusions": sanitize_ai_text(conclusions_text),
                "recommendations": sanitize_ai_text(recommendations_text),
                "generated_at": datetime.now(BOGOTA_TZ).isoformat(),
                "edited": False,
            }
        except Exception as e:
            logger.error(f"Consolidated analysis for {test_type} failed: {e}")
            consolidated[test_type] = {
                "conclusions": f"No fue posible generar las conclusiones consolidadas para {type_label}.",
                "recommendations": "",
                "generated_at": datetime.now(BOGOTA_TZ).isoformat(),
                "edited": False,
            }

    # HF9.1: Auto-save to DB
    from app.db.models.integrated_report import IntegratedReport
    from sqlalchemy.orm.attributes import flag_modified

    sections_json = [s.dict() for s in request_sections]
    BOGOTA_TZ_SAVE = ZoneInfo("America/Bogota")

    if request.report_id:
        # Update existing
        existing = await db.get(IntegratedReport, uuid.UUID(request.report_id))
        if existing:
            # F4: idem — el consolidado tampoco puede llevarse los overrides
            existing.sections = _merge_overrides(existing.sections, sections_json)
            existing.consolidated_analysis = consolidated
            flag_modified(existing, "sections")
            flag_modified(existing, "consolidated_analysis")
            await db.commit()
            await db.refresh(existing)
            # Embed __report_id and __report_name in consolidated for frontend hydration
            return {"consolidated_analysis": {**consolidated, "__report_id": str(existing.id), "__report_name": existing.name}}

    # Create new
    default_name = request.name or f"Informe Integrado - {datetime.now(BOGOTA_TZ_SAVE).strftime('%d/%m/%Y %H:%M')}"
    new_report = IntegratedReport(
        name=default_name,
        sections=sections_json,
        consolidated_analysis=consolidated,
        created_by=current_user.id,
    )
    db.add(new_report)
    await db.commit()
    await db.refresh(new_report)

    return {"consolidated_analysis": {**consolidated, "__report_id": str(new_report.id), "__report_name": default_name}}


# ═══════════════════════════════════════════════════════════════════════════════
# HF9.1 — CRUD Endpoints for Integrated Reports persistence
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/integrated-reports")
async def list_integrated_reports(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all integrated reports for the current user."""
    from app.db.models.integrated_report import IntegratedReport
    from sqlalchemy import desc

    result = await db.execute(
        select(IntegratedReport)
        .where(IntegratedReport.created_by == current_user.id)
        .order_by(desc(IntegratedReport.updated_at))
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "has_consolidated": bool(r.consolidated_analysis and len(r.consolidated_analysis) > 0),
            "section_count": len(r.sections or []),
        }
        for r in reports
    ]


@router.get("/integrated-reports/{report_id}")
async def get_integrated_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a single integrated report by ID."""
    from app.db.models.integrated_report import IntegratedReport

    report = await db.get(IntegratedReport, uuid.UUID(report_id))
    if not report:
        raise HTTPException(404, "Informe integrado no encontrado")
    return {
        "id": str(report.id),
        "name": report.name,
        "sections": report.sections or [],
        "consolidated_analysis": report.consolidated_analysis or {},
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


@router.patch("/integrated-reports/{report_id}")
async def update_integrated_report(
    report_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Partial update of an integrated report (name, sections, consolidated_analysis)."""
    from app.db.models.integrated_report import IntegratedReport
    from sqlalchemy.orm.attributes import flag_modified

    report = await db.get(IntegratedReport, uuid.UUID(report_id))
    if not report:
        raise HTTPException(404, "Informe integrado no encontrado")

    if "name" in payload:
        report.name = payload["name"]
    if "sections" in payload:
        report.sections = payload["sections"]
        flag_modified(report, "sections")
    if "consolidated_analysis" in payload:
        report.consolidated_analysis = payload["consolidated_analysis"]
        flag_modified(report, "consolidated_analysis")

    await db.commit()
    await db.refresh(report)
    return {
        "id": str(report.id),
        "name": report.name,
        "sections": report.sections or [],
        "consolidated_analysis": report.consolidated_analysis or {},
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


@router.delete("/integrated-reports/{report_id}", status_code=204)
async def delete_integrated_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    # SEC-2: borrar es exclusivo de admin en toda la plataforma.
    current_user=Depends(require_role(["admin"])),
):
    """Delete an integrated report."""
    from app.db.models.integrated_report import IntegratedReport

    report = await db.get(IntegratedReport, uuid.UUID(report_id))
    if not report:
        raise HTTPException(404, "Informe integrado no encontrado")
    await db.delete(report)
    await db.commit()
    return None
