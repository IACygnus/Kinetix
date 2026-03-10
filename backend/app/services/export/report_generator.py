"""
Report Generator - Shared module for PDF and HTML export
Chart generation (matplotlib → base64 PNG) and HTML building for both WeasyPrint and browser.
Visual spec: navy #0a1628 table headers, orange AI boxes, SQA branding.
"""
import io
import re
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from app.config.chart_config import (
    CHART_COLORS, HTTP_CODE_COLORS, TEST_TYPE_LABELS,
    get_color_for_index, get_code_color,
)


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def fig_to_base64(fig) -> str:
    """Convert a matplotlib figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def make_time_labels(timestamps):
    """Convert timestamps to elapsed-time strings and numeric x values."""
    if not timestamps:
        return [], []
    start = timestamps[0]
    elapsed_secs = [(t - start).total_seconds() for t in timestamps]
    labels = []
    for s in elapsed_secs:
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        labels.append(f"{h:02d}:{m:02d}:{sec:02d}")
    return elapsed_secs, labels


def _setup_axes(ax, ylabel, xlabel='Tiempo'):
    ax.set_xlabel(xlabel, fontsize=9, color='#64748b')
    ax.set_ylabel(ylabel, fontsize=9, color='#64748b')
    ax.tick_params(axis='both', labelsize=8, colors='#64748b')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#e2e8f0')
    ax.spines['bottom'].set_color('#e2e8f0')


def _set_tick_labels(ax, x_secs, x_labels, max_ticks=15):
    """Set sparse tick labels to avoid overlap."""
    n = len(x_secs)
    if n == 0:
        return
    step = max(1, n // max_ticks)
    ax.set_xticks(x_secs[::step])
    ax.set_xticklabels(
        x_labels[::step],
        rotation=45 if n > 10 else 0,
        ha='right' if n > 10 else 'center',
        fontsize=7,
    )


# ---------------------------------------------------------------------------
# Public chart functions
# ---------------------------------------------------------------------------

def chart_area(timestamps, values, color, ylabel, fill=True):
    """Single-series area/line chart → base64 PNG."""
    fig, ax = plt.subplots(figsize=(10, 3.5))
    x_secs, x_labels = make_time_labels(timestamps)
    if not x_secs:
        ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                transform=ax.transAxes, color='#94a3b8')
        return fig_to_base64(fig)

    ax.plot(x_secs, values, color=color, linewidth=1.5)
    if fill:
        ax.fill_between(x_secs, values, alpha=0.15, color=color)
    _setup_axes(ax, ylabel)
    _set_tick_labels(ax, x_secs, x_labels)
    fig.tight_layout()
    return fig_to_base64(fig)


def chart_multiline(series_list, ylabel, use_code_colors=False):
    """Multi-series line chart → base64 PNG.

    series_list: list of (label, timestamps, values)
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    if not series_list:
        ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                transform=ax.transAxes, color='#94a3b8')
        return fig_to_base64(fig)

    all_x: list = []
    all_labels: list = []
    for idx, (label, timestamps, values) in enumerate(series_list):
        x_secs, x_labels = make_time_labels(timestamps)
        if not x_secs:
            continue
        if use_code_colors:
            color = get_code_color(label.replace('HTTP ', ''))
        else:
            color = get_color_for_index(idx)
        ax.plot(x_secs, values, color=color, linewidth=1.5, label=label)
        if len(x_secs) > len(all_x):
            all_x = x_secs
            all_labels = x_labels

    _setup_axes(ax, ylabel)
    _set_tick_labels(ax, all_x, all_labels)

    ncol = min(4, len(series_list))
    ax.legend(fontsize=7, loc='upper center', bbox_to_anchor=(0.5, -0.22),
              ncol=ncol, frameon=False)
    fig.tight_layout()
    return fig_to_base64(fig)


def chart_pie(code_dist):
    """Pie chart for response-code distribution → base64 PNG."""
    fig, ax = plt.subplots(figsize=(5, 4))
    if not code_dist:
        ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                transform=ax.transAxes, color='#94a3b8')
        return fig_to_base64(fig)

    labels = [str(r['code']) for r in code_dist]
    sizes = [r['count'] for r in code_dist]
    colors = [get_code_color(str(r['code'])) for r in code_dist]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct=lambda p: f'{p:.1f}%' if p > 3 else '',
        startangle=90, textprops={'fontsize': 8},
    )
    for at in autotexts:
        at.set_fontsize(7)
        at.set_color('white')
        at.set_fontweight('bold')
    ax.set_title('Distribucion de Response Codes', fontsize=10,
                 fontweight='bold', color='#1e293b')
    fig.tight_layout()
    return fig_to_base64(fig)


# ---------------------------------------------------------------------------
# Markdown → HTML helper
# ---------------------------------------------------------------------------

def markdown_to_html(text: str) -> str:
    """Convert basic markdown to HTML for PDF/HTML rendering."""
    if not text:
        return ''
    # HTML-escape first
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Bold: **text** → <strong>text</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Split into paragraphs on double newlines
    paragraphs = text.split('\n\n')
    html_parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Single newlines within a paragraph → <br>
        p = p.replace('\n', '<br>')
        html_parts.append(f'<p style="margin:0 0 8px 0">{p}</p>')
    return '\n'.join(html_parts) if html_parts else f'<p>{text}</p>'


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def build_pdf_html(
    meta: Dict[str, Any],
    statistics: List[Dict[str, Any]],
    redirect_stats: List[Dict[str, Any]],
    ia: Dict[str, str],
    charts: Dict[str, str],
) -> str:
    """Build the complete HTML document optimized for WeasyPrint PDF rendering.

    Visual spec applied:
    - Header field order: Cliente → Nombre → Duracion → Tipo de Prueba
    - All table headers use navy ``#0a1628``
    - AI analysis boxes use orange-themed styling (border-left orange, bg #fff7ed)
    - Redirect section header uses navy (same as main tables)
    """
    duration_min = int(meta['duration'] // 60)
    duration_sec = int(meta['duration'] % 60)
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    files_list = ', '.join(meta.get('filenames', [meta['filename']]))

    # Error-rate colour
    er = meta['errorRate']
    er_color = '#10b981' if er < 1 else '#f59e0b' if er < 5 else '#ef4444'

    # Test-type badge
    tt_color = meta.get('testTypeColor', '#3b82f6')

    # Verdict badge
    criteria = meta.get('acceptanceCriteria', {})
    verdict_text = criteria.get('verdict', '') if isinstance(criteria, dict) else ''
    verdict_html = ''
    if verdict_text:
        if verdict_text == 'APTO':
            verdict_class = 'apto'
        elif verdict_text == 'NO APTO':
            verdict_class = 'no-apto'
        else:
            verdict_class = 'reservas'
        criteria_info = ''
        if isinstance(criteria, dict):
            rt_val = criteria.get('response_time', '')
            avail_val = criteria.get('availability', '')
            if rt_val or avail_val:
                parts = []
                if rt_val:
                    parts.append(f'&lt;{rt_val}ms')
                if avail_val:
                    parts.append(f'&gt;{avail_val}% disponibilidad')
                criteria_info = f'<div style="font-size:7pt;color:rgba(255,255,255,0.5)">Criterio: {", ".join(parts)}</div>'
        verdict_html = (
            f'<div class="cover-verdict-section">'
            f'<div class="cover-verdict {verdict_class}">{verdict_text}</div>'
            f'<div style="text-align:left">'
            f'<div style="font-size:8pt;color:rgba(255,255,255,0.7)">Veredicto: <strong style="color:rgba(255,255,255,0.9)">{verdict_text}</strong></div>'
            f'{criteria_info}'
            f'</div></div>'
        )

    # ----- helpers -----
    def ai_box(key, title, border='#f97316', allow_break=False):
        text = ia.get(key, '')
        if not text:
            return ''
        html_text = markdown_to_html(text)
        break_style = 'break-inside:auto;' if allow_break else ''
        return (
            f'<div class="ai-box" style="border-left-color:{border};{break_style}">'
            f'<div class="ai-title">{title}</div>'
            f'<div class="ai-text">{html_text}</div>'
            f'</div>'
        )

    # ----- stats table rows -----
    stats_rows = ''
    for s in statistics:
        err_style = ' style="color:#ef4444;font-weight:600"' if s['errorPct'] > 0 else ''
        stats_rows += f'''<tr>
            <td class="label-cell">{s['label']}</td>
            <td class="num">{s['samples']:,}</td>
            <td class="num"{err_style}>{s['errors']:,}</td>
            <td class="num"{err_style}>{s['errorPct']:.2f}%</td>
            <td class="num">{s['avg']:.2f}</td>
            <td class="num">{s['median']:.2f}</td>
            <td class="num">{s['p90']:.2f}</td>
            <td class="num">{s['p95']:.2f}</td>
            <td class="num">{s['p99']:.2f}</td>
            <td class="num">{s['min']:.2f}</td>
            <td class="num">{s['max']:.2f}</td>
            <td class="num">{s['tps']:.2f}</td>
            <td class="num">{s['kbRecv']:.2f}</td>
            <td class="num">{s['kbSent']:.2f}</td>
        </tr>'''

    total_row = f'''<tr class="total-row">
        <td class="label-cell">TOTAL PRINCIPALES</td>
        <td class="num">{meta['totalRequests']:,}</td>
        <td class="num">{meta['totalErrors']:,}</td>
        <td class="num">{meta['errorRate']:.2f}%</td>
        <td class="num">{meta['avgResponseTime']:.2f}</td>
        <td class="num">{meta['medianResponseTime']:.2f}</td>
        <td class="num">{meta['p90']:.2f}</td>
        <td class="num">{meta['p95']:.2f}</td>
        <td class="num">{meta['p99']:.2f}</td>
        <td class="num">{meta['minResponseTime']:.2f}</td>
        <td class="num">{meta['maxResponseTime']:.2f}</td>
        <td class="num">{meta['throughput']:.2f}</td>
        <td class="num">{meta['kbRecv']:.2f}</td>
        <td class="num">{meta['kbSent']:.2f}</td>
    </tr>'''

    # ----- redirect section -----
    redirect_section = ''
    if redirect_stats:
        redir_rows = ''
        for r in redirect_stats:
            redir_rows += f'''<tr>
                <td class="label-cell">{r['label']}</td>
                <td class="num">{r['samples']:,}</td>
                <td class="num">{r['errors']:,}</td>
                <td class="num">{r['errorPct']:.2f}%</td>
                <td class="num">{r['avg']:.2f}</td>
                <td class="num">{r['p90']:.2f}</td>
                <td class="num">{r['p95']:.2f}</td>
                <td class="num">{r['p99']:.2f}</td>
                <td class="num">{r['min']:.2f}</td>
                <td class="num">{r['max']:.2f}</td>
                <td class="num">{r['tps']:.2f}</td>
            </tr>'''

        # compute redirect totals
        r_total_samples = sum(r['samples'] for r in redirect_stats)
        r_total_errors = sum(r['errors'] for r in redirect_stats)
        r_total_err_pct = (r_total_errors / r_total_samples * 100) if r_total_samples > 0 else 0
        r_total_avg = (sum(r['avg'] * r['samples'] for r in redirect_stats) / r_total_samples) if r_total_samples > 0 else 0
        r_total_p90 = max((r['p90'] for r in redirect_stats), default=0)
        r_total_p95 = max((r['p95'] for r in redirect_stats), default=0)
        r_total_p99 = max((r['p99'] for r in redirect_stats), default=0)
        r_total_min = min((r['min'] for r in redirect_stats), default=0)
        r_total_max = max((r['max'] for r in redirect_stats), default=0)
        r_total_tps = sum(r['tps'] for r in redirect_stats)

        redir_total_row = f'''<tr class="total-row">
            <td class="label-cell">TOTAL REDIRECCIONES</td>
            <td class="num">{r_total_samples:,}</td>
            <td class="num">{r_total_errors:,}</td>
            <td class="num">{r_total_err_pct:.2f}%</td>
            <td class="num">{r_total_avg:.2f}</td>
            <td class="num">{r_total_p90:.2f}</td>
            <td class="num">{r_total_p95:.2f}</td>
            <td class="num">{r_total_p99:.2f}</td>
            <td class="num">{r_total_min:.2f}</td>
            <td class="num">{r_total_max:.2f}</td>
            <td class="num">{r_total_tps:.2f}</td>
        </tr>'''

        redirect_section = f'''
        <div class="section">
            <div class="section-header">
                Reporte de Redirecciones
            </div>
            <table>
                <thead><tr>
                    <th>Redireccion</th><th>Muestras</th><th>Errores</th><th>% Error</th>
                    <th>Promedio</th><th>P90</th><th>P95</th><th>P99</th>
                    <th>Min</th><th>Max</th><th>TPS</th>
                </tr></thead>
                <tbody>{redir_rows}{redir_total_row}</tbody>
            </table>
        </div>
        {ai_box('redirects', 'Analisis de Redirecciones', '#f97316')}
        '''

    # ----- full HTML -----
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
@page {{
    size: A4 landscape;
    margin: 15mm 15mm 20mm 15mm;
    @bottom-center {{
        content: "Pagina " counter(page) " de " counter(pages);
        font-size: 8pt;
        color: #94a3b8;
    }}
}}

@page :first {{
    margin-top: 0;
    @bottom-center {{ content: none; }}
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    font-size: 9pt;
    color: #1e293b;
    line-height: 1.5;
}}

/* ===== COVER PAGE ===== */
.cover {{
    page-break-after: always;
    width: 100%;
    text-align: center;
    background: linear-gradient(135deg, #0a1628 0%, #162040 50%, #1a3a7a 100%);
    color: white;
    padding: 8mm 20mm 6mm 20mm;
    margin: -15mm -15mm 0 -15mm;
}}

.cover-logo {{
    font-size: 36pt;
    font-weight: 800;
    letter-spacing: -2px;
    margin-bottom: 1mm;
}}

.cover-logo-accent {{
    color: #f5a623;
}}

.cover-subtitle {{
    font-size: 8pt;
    color: rgba(255,255,255,0.5);
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-bottom: 3mm;
}}

.cover-pretitle {{
    font-size: 10pt;
    color: rgba(255,255,255,0.6);
    margin-bottom: 1mm;
}}

.cover-title {{
    font-size: 16pt;
    font-weight: 700;
    margin-bottom: 3mm;
}}

.cover-info-box {{
    background: rgba(255,255,255,0.08);
    border-radius: 3mm;
    padding: 3mm 5mm;
    margin-bottom: 3mm;
    text-align: left;
}}

.cover-info-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1mm 8mm;
    font-size: 8pt;
    color: rgba(255,255,255,0.7);
    line-height: 1.5;
}}

.cover-info-grid strong {{
    color: rgba(255,255,255,0.9);
}}

.cover-verdict-section {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3mm;
    margin: 2mm 0 3mm 0;
}}

.cover-verdict {{
    display: inline-block;
    padding: 1.5mm 6mm;
    border-radius: 4mm;
    font-size: 9pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.cover-verdict.apto {{
    background: rgba(16,185,129,0.25);
    color: #10b981;
    border: 0.4mm solid rgba(16,185,129,0.6);
}}

.cover-verdict.no-apto {{
    background: rgba(239,68,68,0.25);
    color: #fca5a5;
    border: 0.4mm solid rgba(239,68,68,0.6);
}}

.cover-verdict.reservas {{
    background: rgba(245,158,11,0.25);
    color: #fbbf24;
    border: 0.4mm solid rgba(245,158,11,0.6);
}}

.cover-badge {{
    display: inline-block;
    padding: 1mm 5mm;
    border-radius: 4mm;
    font-size: 8pt;
    font-weight: 600;
    text-transform: uppercase;
    border: 0.4mm solid rgba(255,255,255,0.4);
}}

.cover-footer {{
    margin-top: 3mm;
    font-size: 7pt;
    color: rgba(255,255,255,0.4);
}}

/* Cover KPI cards */
.cover-kpis {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 5px;
    margin-top: 3mm;
    text-align: left;
}}

.cover-kpi {{
    background: white;
    border-radius: 4px;
    padding: 3px 7px;
    border-left: 3px solid #3b82f6;
}}

.cover-kpi-label {{
    font-size: 5.5px;
    color: #64748b;
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

.cover-kpi-val {{
    font-size: 14pt;
    font-weight: 700;
    color: #1e293b;
    margin-top: 0;
    line-height: 1.2;
}}

.cover-kpi-val span {{
    font-size: 7pt;
    font-weight: 400;
    color: #64748b;
}}

/* ===== REPORT BODY ===== */

/* Sections */
.section {{
    margin-bottom: 5mm;
}}

.section-header {{
    background: #0a1628;
    color: white;
    padding: 2.5mm 4mm;
    font-size: 11pt;
    font-weight: 700;
    border-radius: 2mm 2mm 0 0;
}}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 7.5pt;
    margin-bottom: 4mm;
    page-break-inside: auto;
}}

thead {{
    display: table-header-group;
}}

thead th {{
    background: #0a1628;
    color: white;
    padding: 2mm 1.5mm;
    text-align: center;
    font-size: 6.5pt;
    font-weight: 600;
    text-transform: uppercase;
    white-space: nowrap;
}}

thead th:first-child {{
    text-align: left;
}}

tfoot {{
    display: table-footer-group;
}}

tr {{
    page-break-inside: avoid;
    break-inside: avoid;
}}

td {{
    padding: 1.5mm 1.5mm;
    border-bottom: 0.2mm solid #e2e8f0;
}}

td.num {{
    text-align: center;
    font-family: 'Courier New', monospace;
    font-size: 7pt;
}}

td.label-cell {{
    font-weight: 600;
    min-width: 28mm;
    white-space: nowrap;
    font-size: 6.5pt;
}}

tbody tr:nth-child(even) {{
    background: #f8fafc;
}}

.total-row {{
    background: #0a1628 !important;
    color: white;
    font-weight: 700;
}}

.total-row td {{
    border-bottom: none;
}}

/* Charts */
.chart-section {{
    margin-bottom: 5mm;
    break-inside: avoid;
}}

.chart-title {{
    font-size: 10pt;
    font-weight: 700;
    color: #1e293b;
    padding: 2mm 0;
    border-left: 1mm solid #3b82f6;
    padding-left: 3mm;
    margin-bottom: 2mm;
}}

.chart-img {{
    width: 100%;
    max-height: 80mm;
}}

/* AI boxes — orange themed */
.ai-box {{
    background: #fff7ed;
    border-left: 1mm solid #f97316;
    border-radius: 1.5mm;
    padding: 3mm 4mm;
    margin: 2mm 0 5mm 0;
    break-inside: avoid;
}}

.ai-title {{
    font-size: 8.5pt;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 1.5mm;
}}

.ai-text {{
    font-size: 8pt;
    line-height: 1.6;
    color: #334155;
}}

.ai-text p {{
    margin: 0 0 6px 0;
}}

.ai-text strong {{
    color: #1e293b;
}}

/* Two-column grid */
.grid-2 {{
    display: flex;
    gap: 4mm;
    margin-bottom: 5mm;
}}

.grid-2 > div {{
    flex: 1;
}}

/* Footer */
.report-footer {{
    text-align: center;
    font-size: 8pt;
    color: #94a3b8;
    padding-top: 4mm;
    border-top: 0.3mm solid #e2e8f0;
    margin-top: 8mm;
}}

.report-footer strong {{
    color: #1e293b;
}}
</style>
</head>
<body>

<!-- ===== COVER PAGE ===== -->
<div class="cover">
    <div class="cover-logo">sqa<span class="cover-logo-accent">_</span></div>
    <div class="cover-subtitle">SOFTWARE QUALITY ASSURANCE</div>
    <div class="cover-pretitle">Reporte de Analisis de Performance</div>
    <div class="cover-title">{meta['project'] or meta['name']}</div>

    <div class="cover-info-box">
        <div class="cover-info-grid">
            <div><strong>Proyecto:</strong> {meta['project'] or meta['name']}</div>
            <div><strong>Cliente:</strong> {meta['client'] or 'N/A'}</div>
            <div><strong>Tipo:</strong> <span class="cover-badge">{meta['testTypeLabel']}</span></div>
            <div><strong>Duracion:</strong> {duration_min}m {duration_sec}s</div>
            <div><strong>Archivo:</strong> {files_list}</div>
            <div><strong>Inicio:</strong> {meta['startTime']} &nbsp; <strong>Fin:</strong> {meta['endTime']}</div>
        </div>
    </div>

    {verdict_html}

    <div class="cover-kpis">
        <div class="cover-kpi" style="border-left-color:#3b82f6"><div class="cover-kpi-label">Total Requests</div><div class="cover-kpi-val">{meta['totalRequests']:,}</div></div>
        <div class="cover-kpi" style="border-left-color:#8b5cf6"><div class="cover-kpi-label">Avg Response Time</div><div class="cover-kpi-val">{meta['avgResponseTime']:.0f} <span>ms</span></div></div>
        <div class="cover-kpi" style="border-left-color:{er_color}"><div class="cover-kpi-label">Error Rate</div><div class="cover-kpi-val" style="color:{er_color}">{meta['errorRate']:.2f}<span>%</span></div></div>
        <div class="cover-kpi" style="border-left-color:#f59e0b"><div class="cover-kpi-label">Throughput</div><div class="cover-kpi-val">{meta['throughput']:.2f} <span>req/s</span></div></div>
    </div>
    <div class="cover-kpis" style="margin-top:3px">
        <div class="cover-kpi" style="border-left-color:#06b6d4"><div class="cover-kpi-label">P90</div><div class="cover-kpi-val">{meta['p90']:.0f} <span>ms</span></div></div>
        <div class="cover-kpi" style="border-left-color:#06b6d4"><div class="cover-kpi-label">P95</div><div class="cover-kpi-val">{meta['p95']:.0f} <span>ms</span></div></div>
        <div class="cover-kpi" style="border-left-color:#06b6d4"><div class="cover-kpi-label">P99</div><div class="cover-kpi-val">{meta['p99']:.0f} <span>ms</span></div></div>
        <div class="cover-kpi" style="border-left-color:#8b5cf6"><div class="cover-kpi-label">Avg Latency</div><div class="cover-kpi-val">{meta['avgLatency']:.0f} <span>ms</span></div></div>
    </div>
    <div class="cover-footer">
        Celula de Performance SQA | Generado: {now_str}
    </div>
</div>

<!-- ===== INFORMACION DEL PROYECTO ===== -->
<div style="margin-bottom:5mm;">
    <div class="section-header">Informacion del Proyecto</div>
    <div style="display:flex;gap:3mm;padding:3mm 4mm;background:#f8fafc;border:0.3mm solid #e2e8f0;border-radius:0 0 2mm 2mm;">
        <div style="flex:1"><div style="font-size:7pt;color:#64748b;text-transform:uppercase;letter-spacing:0.5px">Cliente</div><div style="font-size:9pt;font-weight:600;margin-top:1mm">{meta['client'] or 'N/A'}</div></div>
        <div style="flex:1"><div style="font-size:7pt;color:#64748b;text-transform:uppercase;letter-spacing:0.5px">Nombre del Proyecto</div><div style="font-size:9pt;font-weight:600;margin-top:1mm">{meta['project'] or meta['name']}</div></div>
        <div style="flex:1"><div style="font-size:7pt;color:#64748b;text-transform:uppercase;letter-spacing:0.5px">Duracion</div><div style="font-size:9pt;font-weight:600;margin-top:1mm">{duration_min}m {duration_sec}s</div></div>
        <div style="flex:1"><div style="font-size:7pt;color:#64748b;text-transform:uppercase;letter-spacing:0.5px">Tipo de Prueba</div><div style="font-size:9pt;font-weight:600;margin-top:1mm"><span style="background:{tt_color}22;color:{tt_color};padding:1mm 3mm;border-radius:2mm;font-size:8pt;border:0.3mm solid {tt_color}">{meta['testTypeLabel']}</span></div></div>
    </div>
    <div style="font-size:7.5pt;color:#64748b;padding:2mm 4mm;background:#f8fafc;border:0.3mm solid #e2e8f0;border-top:none;border-radius:0 0 2mm 2mm;">
        <strong>Archivo:</strong> {files_list} &nbsp;|&nbsp; <strong>Inicio:</strong> {meta['startTime']} &nbsp;|&nbsp; <strong>Fin:</strong> {meta['endTime']}
    </div>
</div>

<!-- ===== TABLA RESUMEN ===== -->
<div class="section">
    <div class="section-header">Reporte Resumen por Transaccion</div>
    <table>
        <thead><tr>
            <th style="text-align:left">Transaccion</th><th>Muestras</th><th>Errores</th><th>% Error</th>
            <th>Promedio</th><th>Mediana</th><th>P90</th><th>P95</th><th>P99</th>
            <th>Min</th><th>Max</th><th>TPS</th><th>KB/s Recv</th><th>KB/s Sent</th>
        </tr></thead>
        <tfoot>{total_row}</tfoot>
        <tbody>{stats_rows}</tbody>
    </table>
</div>

{ai_box('summary', 'Analisis del Reporte Resumen')}

{redirect_section}

<!-- ===== CHARTS ===== -->
<div class="chart-section">
    <div class="chart-title" style="border-left-color:#8b5cf6">Response Times por Transaccion</div>
    <img class="chart-img" src="data:image/png;base64,{charts['rt_label']}" />
</div>
{ai_box('responseTimes', 'Analisis - Response Times por Transaccion', '#f97316')}

<div class="chart-section">
    <div class="chart-title" style="border-left-color:#3b82f6">Response Time Over Time</div>
    <img class="chart-img" src="data:image/png;base64,{charts['rt_time']}" />
</div>
{ai_box('responseTimeOverTime', 'Analisis - Response Time Over Time', '#f97316')}

<div class="chart-section">
    <div class="chart-title" style="border-left-color:#10b981">Throughput Over Time</div>
    <img class="chart-img" src="data:image/png;base64,{charts['throughput']}" />
</div>
{ai_box('throughput', 'Analisis - Throughput', '#f97316')}

<div class="chart-section">
    <div class="chart-title" style="border-left-color:#8b5cf6">Latency Over Time</div>
    <img class="chart-img" src="data:image/png;base64,{charts['latency']}" />
</div>
{ai_box('latency', 'Analisis - Latency', '#f97316')}

<div class="chart-section">
    <div class="chart-title" style="border-left-color:#ef4444">Error Rate Over Time</div>
    <img class="chart-img" src="data:image/png;base64,{charts['error_rate']}" />
</div>
{ai_box('errorRate', 'Analisis - Error Rate', '#f97316')}

<div class="chart-section">
    <div class="chart-title" style="border-left-color:#6366f1">Response Codes per Second</div>
    <img class="chart-img" src="data:image/png;base64,{charts['codes']}" />
</div>
{ai_box('codesPerSecond', 'Analisis - Response Codes', '#f97316')}

<div class="chart-section">
    <div class="chart-title" style="border-left-color:#10b981">Transactions per Second</div>
    <img class="chart-img" src="data:image/png;base64,{charts['tps']}" />
</div>
{ai_box('tps', 'Analisis - Transactions per Second', '#f97316')}

<div class="chart-section">
    <div class="chart-title" style="border-left-color:#6366f1">Active Threads Over Time</div>
    <img class="chart-img" src="data:image/png;base64,{charts['threads']}" />
</div>
{ai_box('activeThreads', 'Analisis - Active Threads', '#f97316')}

<!-- ===== DISTRIBUCION DE CODIGOS ===== -->
<div class="chart-section">
    <div class="chart-title" style="border-left-color:#f59e0b">Distribucion de Response Codes</div>
    <div style="text-align:center">
        <img style="max-width:100mm;max-height:80mm" src="data:image/png;base64,{charts['pie']}" />
    </div>
</div>
{ai_box('errors', 'Analisis de Errores', '#f97316')}

<!-- ===== CONCLUSIONES Y RECOMENDACIONES ===== -->
{ai_box('conclusions', 'Conclusiones', '#6366f1', allow_break=True)}
{ai_box('recommendations', 'Recomendaciones', '#10b981', allow_break=True)}

<!-- ===== FOOTER ===== -->
<div class="report-footer">
    <strong>sqa &mdash; Software Quality Assurance</strong><br>
    Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos<br>
    <span style="font-size:7pt">Powered by FastAPI + React + PostgreSQL + Gemini AI | JMeter Analyzer Pro v2.0 | Generado: {now_str}</span>
</div>

</body>
</html>'''


# ---------------------------------------------------------------------------
# Standalone HTML builder (browser-optimized, fully offline)
# ---------------------------------------------------------------------------

def build_standalone_html(
    meta: Dict[str, Any],
    statistics: List[Dict[str, Any]],
    redirect_stats: List[Dict[str, Any]],
    ia: Dict[str, str],
    charts: Dict[str, str],
) -> str:
    """Build a standalone HTML report optimized for browser viewing.

    No external dependencies (no CDN). Charts embedded as base64 PNG.
    Same visual spec as PDF: navy #0a1628 headers, orange AI boxes,
    header order: Cliente → Nombre → Duracion → Tipo de Prueba.
    """
    duration_min = int(meta['duration'] // 60)
    duration_sec = int(meta['duration'] % 60)
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    files_list = ', '.join(meta.get('filenames', [meta['filename']]))

    er = meta['errorRate']
    er_color = '#10b981' if er < 1 else '#f59e0b' if er < 5 else '#ef4444'
    tt_color = meta.get('testTypeColor', '#3b82f6')
    test_badge = (
        f'<span class="badge" style="background:{tt_color}20;color:{tt_color};'
        f'border:1px solid {tt_color}">{meta["testTypeLabel"]}</span>'
    )

    # Verdict badge for HTML
    criteria = meta.get('acceptanceCriteria', {})
    verdict_text = criteria.get('verdict', '') if isinstance(criteria, dict) else ''
    verdict_badge_html = ''
    if verdict_text:
        if verdict_text == 'APTO':
            v_bg, v_color, v_border = '#dcfce7', '#16a34a', '#86efac'
        elif verdict_text == 'NO APTO':
            v_bg, v_color, v_border = '#fef2f2', '#dc2626', '#fca5a5'
        else:
            v_bg, v_color, v_border = '#fffbeb', '#d97706', '#fcd34d'
        verdict_badge_html = (
            f'<span class="badge" style="background:{v_bg};color:{v_color};'
            f'border:1px solid {v_border};font-weight:700;margin-left:8px">{verdict_text}</span>'
        )

    # ----- helpers -----
    def ai_box(key, title, border='#f97316', allow_break=False):
        text = ia.get(key, '')
        if not text:
            return ''
        html_text = markdown_to_html(text)
        return (
            f'<div class="ai-box" style="border-left-color:{border}">'
            f'<div class="ai-title">{title}</div>'
            f'<div class="ai-text">{html_text}</div>'
            f'</div>'
        )

    # ----- stats rows -----
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

    # ----- redirect section -----
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

    # ----- error bars -----
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

    # ----- full standalone HTML -----
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Reporte Performance - {meta['name']}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
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
.chart-img{{width:100%;height:auto}}
.ai-box{{background:#fff7ed;border-left:4px solid #f97316;border-radius:8px;padding:1.2rem;margin:1rem 0}}
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
<div style="font-size:.75rem;opacity:.7;text-transform:uppercase;letter-spacing:.5px">Reporte de Analisis de Performance {test_badge} {verdict_badge_html}</div>
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

<div class="chart-section">
<div class="chart-title" style="border-left-color:#8b5cf6">Response Times por Transaccion</div>
<img class="chart-img" src="data:image/png;base64,{charts['rt_label']}" alt="Response Times por Transaccion" />
</div>
{ai_box('responseTimes', 'Analisis - Response Times por Transaccion', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#3b82f6">Response Time Over Time</div>
<img class="chart-img" src="data:image/png;base64,{charts['rt_time']}" alt="Response Time Over Time" />
</div>
{ai_box('responseTimeOverTime', 'Analisis - Response Time Over Time', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#10b981">Throughput Over Time</div>
<img class="chart-img" src="data:image/png;base64,{charts['throughput']}" alt="Throughput Over Time" />
</div>
{ai_box('throughput', 'Analisis - Throughput', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#8b5cf6">Latency Over Time</div>
<img class="chart-img" src="data:image/png;base64,{charts['latency']}" alt="Latency Over Time" />
</div>
{ai_box('latency', 'Analisis - Latency', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#ef4444">Error Rate Over Time</div>
<img class="chart-img" src="data:image/png;base64,{charts['error_rate']}" alt="Error Rate Over Time" />
</div>
{ai_box('errorRate', 'Analisis - Error Rate', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#6366f1">Response Codes per Second</div>
<img class="chart-img" src="data:image/png;base64,{charts['codes']}" alt="Response Codes per Second" />
</div>
{ai_box('codesPerSecond', 'Analisis - Response Codes', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#10b981">Transactions per Second</div>
<img class="chart-img" src="data:image/png;base64,{charts['tps']}" alt="Transactions per Second" />
</div>
{ai_box('tps', 'Analisis - Transactions per Second', '#f97316')}

<div class="chart-section">
<div class="chart-title" style="border-left-color:#6366f1">Active Threads Over Time</div>
<img class="chart-img" src="data:image/png;base64,{charts['threads']}" alt="Active Threads Over Time" />
</div>
{ai_box('activeThreads', 'Analisis - Active Threads', '#f97316')}

<div class="grid-2">
<div class="chart-section">
<div class="chart-title" style="border-left-color:#f59e0b">Distribucion de Response Codes</div>
<div style="max-width:400px;margin:0 auto">
<img class="chart-img" src="data:image/png;base64,{charts['pie']}" alt="Response Codes Pie" />
</div>
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
Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos<br>
<span style="font-size:.75rem">Powered by FastAPI + React + PostgreSQL + Gemini AI | JMeter Analyzer Pro v2.0 | Generado: {now_str}</span>
</div>

</div>

</body>
</html>'''
