"""
Report Generator - Shared module for PDF and HTML export
Chart generation (matplotlib → base64 PNG) and HTML building for both WeasyPrint and browser.
Visual spec: navy #0a1628 table headers, orange AI boxes, SQA branding.
"""
import io
import re
import base64
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from app.config.chart_config import get_color_for_index, get_code_color


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

# GRAF1-C: sufijo que marca la serie de maximos (misma convencion que el dashboard)
MAX_SERIES_SUFFIX = ' (max)'

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


def chart_multiline(series_list, ylabel, use_code_colors=False, dual_max=False):
    """Multi-series line chart → base64 PNG.

    series_list: list of (label, timestamps, values)
    dual_max: GRAF1-C — las series cuyo nombre termina en MAX_SERIES_SUFFIX se
        dibujan finas y punteadas, con el color de su serie base y sin entrada
        en la leyenda. Con dual_max=False el resultado es identico al de siempre.
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    if not series_list:
        ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                transform=ax.transAxes, color='#94a3b8')
        return fig_to_base64(fig)

    all_x: list = []
    all_labels: list = []
    base_colors: dict = {}
    for label, timestamps, values in series_list:
        x_secs, x_labels = make_time_labels(timestamps)
        if not x_secs:
            continue
        is_max = dual_max and label.endswith(MAX_SERIES_SUFFIX)
        if is_max:
            color = base_colors.get(label[:-len(MAX_SERIES_SUFFIX)], '#94a3b8')
        elif use_code_colors:
            color = base_colors[label] = get_code_color(label.replace('HTTP ', ''))
        else:
            color = base_colors[label] = get_color_for_index(len(base_colors))
        if is_max:
            ax.plot(x_secs, values, color=color, linewidth=0.8, linestyle='--',
                    alpha=0.85, label='_nolegend_')
        else:
            ax.plot(x_secs, values, color=color, linewidth=1.5, label=label)
        if len(x_secs) > len(all_x):
            all_x = x_secs
            all_labels = x_labels

    _setup_axes(ax, ylabel)
    _set_tick_labels(ax, all_x, all_labels)

    ncol = min(4, max(1, len(base_colors)))
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

def transaction_analyses_html(rows: Optional[List[Dict[str, Any]]], for_pdf: bool = True) -> str:
    """N3.5: bloque 'Analisis por transaccion critica', una caja por transaccion.

    `ai_box` pinta UNA seccion desde UNA clave fija y no sirve aqui: el numero de
    cajas es variable. Sin filas devuelve cadena vacia — el documento sale
    exactamente como antes (mismo criterio que el logo en N1).

    Una fila sin analisis (la que fallo o la que paso del tope de 10) se pinta
    igual, con sus metricas y una nota: la transaccion la marco Fredy y ocultarla
    en silencio le haria creer que se analizo.
    """
    if not rows:
        return ''
    if for_pdf:
        titulo = ('<div class="section-title" style="margin-top:6mm">'
                  'Analisis por Transaccion Critica</div>')
        caja, met, txt = (
            'background:#fff7ed;border-left:1.2mm solid #4f46e5;border-radius:2mm;'
            'padding:3mm 4mm;margin:0 0 3mm 0;break-inside:avoid',
            'font-size:8pt;color:#475569;margin:1mm 0 2mm 0',
            'font-size:9pt;line-height:1.5;color:#334155')
        nom = 'font-size:11pt;font-weight:700;color:#0a1628'
    else:
        titulo = '<div class="section-title" style="margin-top:1.5rem">Analisis por Transaccion Critica</div>'
        caja, met, txt = (
            'background:#fff7ed;border-left:4px solid #4f46e5;border-radius:8px;'
            'padding:1rem 1.2rem;margin:0 0 1rem 0',
            'font-size:.8rem;color:#475569;margin:.25rem 0 .6rem 0',
            'font-size:.9rem;line-height:1.7;color:#334155')
        nom = 'font-size:1rem;font-weight:700;color:#0a1628'

    cajas = []
    for r in rows:
        m = r.get('metrics') or {}
        linea = (f"{int(m.get('muestras', 0)):,} muestras &middot; promedio {float(m.get('promedio', 0)):.0f} ms"
                 f" &middot; p90 {float(m.get('p90', 0)):.0f} ms &middot; max {float(m.get('max', 0)):.0f} ms"
                 f" &middot; {int(m.get('errores', 0)):,} errores ({float(m.get('tasa_error', 0)):.2f}%)")
        cuerpo = (markdown_to_html(r['ai_analysis']) if r.get('ai_analysis')
                  else '<em>Esta transaccion se marco como critica pero no se genero su analisis individual.</em>')
        cajas.append(f'<div style="{caja}"><div style="{nom}">{r.get("label", "")}</div>'
                     f'<div style="{met}">{linea}</div><div style="{txt}">{cuerpo}</div></div>')
    return titulo + ''.join(cajas)


def cover_meta_parts(meta: Dict[str, Any]) -> Dict[str, str]:
    """N2.3: piezas de la fila de metadatos de la portada (PDF y HTML).

    El nombre del proyecto y el tipo de prueba NO salen de aqui a proposito:
    viven solo en el titulo y en el badge de la zona superior. Repetirlos en la
    fila era la duplicacion que N2.2 no resolvio. Lo que sube a la fila es la
    informacion que antes quedaba en gris diminuto al pie: fecha, rango horario
    y criterios de aceptacion.

    ``criteria`` vuelve vacio cuando la ejecucion no tiene criterios definidos;
    quien lo consume no debe pintar la columna en ese caso.
    """
    start = str(meta.get('startTime') or '--')
    end = str(meta.get('endTime') or '--')
    date_part, _, t_ini = start.partition(' ')
    _, _, t_fin = end.partition(' ')
    crit = meta.get('acceptanceCriteria') or {}
    parts = []
    if isinstance(crit, dict):
        if crit.get('response_time'):
            parts.append(f'&lt; {crit["response_time"]} ms')
        if crit.get('availability'):
            parts.append(f'&gt; {crit["availability"]}% disponibilidad')
    return {
        'date': date_part or '--',
        'range': f'{t_ini or "--"} &rarr; {t_fin or "--"}',
        'criteria': ' &middot; '.join(parts),
    }


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
    now_str = datetime.now(ZoneInfo("America/Bogota")).strftime('%d/%m/%Y %H:%M:%S')
    files_list = ', '.join(meta.get('filenames', [meta['filename']]))

    # Error-rate colour
    er = meta['errorRate']
    er_color = '#10b981' if er < 1 else '#f59e0b' if er < 5 else '#ef4444'

    # Test-type badge
    tt_color = meta.get('testTypeColor', '#3b82f6')

    # N1.6: logo del cliente en la portada (data-URI o None). Sin logo queda una
    # cadena vacia y la portada sale exactamente igual que antes. Medidas en mm
    # (regla 17: nunca rem en PDF) y dentro de la celda de la tabla existente
    # (regla 11: WeasyPrint no maneja flex/grid).
    _client_logo = meta.get('client_logo')

    # N2.3: el bloque de metadatos son DOS zonas separadas por una linea
    # vertical (border-left del <td> derecho, no un flex: regla 11). Izquierda
    # ~62% con tres filas apiladas (ejecucion+duracion / criterios / archivo);
    # derecha ~38% dedicada al cliente, con el logo respirando y los tres
    # elementos centrados entre si. Sin logo la zona no cambia de tamano: solo
    # se queda con etiqueta + nombre centrados.
    _logo_img = (
        f'<img src="{_client_logo}" alt="Logo del cliente" '
        f'style="max-height:28mm;max-width:72mm;display:block;margin:3mm auto 2mm auto" />'
    ) if _client_logo else ''
    cover_cell_cliente = (
        f'<div class="cover-meta-label">CLIENTE</div>'
        f'{_logo_img}'
        f'<div class="cover-meta-value" style="font-size:14pt;margin-top:{"0" if _client_logo else "2mm"}">'
        f'{meta["client"] or "N/A"}</div>'
    )

    # UI-2: el badge APTO/NO APTO ya NO se emite en el PDF (se conserva en pantalla).
    # N2.3: los criterios dejan de ser un apendice del pie en gris y pasan a ser
    # una fila propia de la zona izquierda. Sin criterios definidos la fila no se
    # pinta y las otras dos se juntan, sin hueco.
    _cm = cover_meta_parts(meta)
    cover_fila_criterios = (
        f'<tr><td colspan="2" class="cover-meta-fila">'
        f'<div class="cover-meta-label">CRITERIOS DE ACEPTACION</div>'
        f'<div class="cover-meta-value">{_cm["criteria"]}</div></td></tr>'
    ) if _cm['criteria'] else ''

    # ----- helpers -----
    def ai_box(key, title, border='#4f46e5', allow_break=False):
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

    def chart_unit(title, color, img_key, ia_key, ia_title):
        """N2.1: grafica + su analisis como UNA unidad indivisible, en dos columnas.

        En A4 landscape la pila vertical (grafica de 80mm + caja de analisis) mide
        ~133mm de los 175mm utiles: solo cabe un bloque por pagina y el resto es
        blanco. Lado a lado, la unidad mide lo que el mas alto de los dos (~70mm)
        y entran dos por pagina. Tabla, no flex/grid (regla 11).
        """
        ai_html = ai_box(ia_key, ia_title, color)
        head = f'<div class="chart-title" style="border-left-color:{color}">{title}</div>'
        img = f'<img class="chart-img" src="data:image/png;base64,{charts[img_key]}" />'
        if not ai_html:   # sin analisis, la grafica ocupa el ancho completo
            return f'<table class="chart-unit"><tr><td class="chart-cell" style="width:100%">{head}{img}</td></tr></table>'
        return (
            f'<table class="chart-unit"><tr>'
            f'<td class="chart-cell">{head}{img}</td>'
            f'<td class="chart-ai-cell">{ai_html}</td>'
            f'</tr></table>'
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
        {ai_box('redirects', 'Analisis de Redirecciones', '#4f46e5')}
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
    margin: 0;
    @bottom-center {{ content: none; }}
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; text-decoration: none; }}

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
    min-height: 210mm; /* Fill entire A4 landscape page — gradient full-bleed */
    background: linear-gradient(135deg, #0a1628 0%, #1e293b 50%, #1e40af 100%);
    color: white;
    /* N2.3: 15/10mm -> 10/6mm. El bloque de metadatos paso a dos zonas con tres
       filas y crecio 13.6mm medidos; la portada tiene que seguir cabiendo en una
       sola pagina (si no, WeasyPrint parte la caja y deja una pagina 2 vacia). */
    padding: 10mm 25mm 6mm 25mm;
    margin: 0;
}}

.cover-top-table {{
    width: 100%;
    margin-bottom: 8mm;
}}

.cover-logo {{
    font-size: 36pt;
    font-weight: 800;
    letter-spacing: -1px;
}}

.cover-logo-accent {{
    color: #f5a623;
}}

.cover-subtitle {{
    font-size: 10pt;
    color: rgba(255,255,255,0.6);
    margin-top: 0;
}}

/* N2.3: la celda EJECUCION anade una segunda linea (rango horario) y la
   portada se pasaba de pagina por ~4mm — dejaba una pagina 2 en blanco. Se
   recupera ese espacio del propio ritmo vertical de la caja (padding y
   margenes), sin tocar tamanos de fuente ni el conteo de paginas del cuerpo. */
.cover-info-box {{
    background: rgba(255,255,255,0.08);
    border-radius: 4mm;
    padding: 5mm 8mm;
    margin-bottom: 4mm;
}}

.cover-pretitle {{
    font-size: 10pt;
    color: rgba(255,255,255,0.6);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 2mm;
}}

.cover-title {{
    font-size: 24pt;
    font-weight: 700;
    margin-bottom: 3mm;
}}

.cover-meta-grid {{
    width: 100%;
    margin-top: 2mm;
}}

/* N2.3: las dos zonas del bloque de metadatos. La separacion vertical es el
   border-left del <td> derecho — WeasyPrint no dibuja flex/grid (regla 11). */
.cover-zona-izq {{
    width: 62%;
    border: none;
    padding: 0 8mm 0 0;
    vertical-align: middle;
}}

.cover-zona-der {{
    width: 38%;
    border: none;
    border-left: 0.3mm solid rgba(255,255,255,0.13);   /* N2.4: hairline al 13% */
    padding: 0 2mm 0 10mm;
    vertical-align: middle;
    text-align: center;
}}

.cover-meta-inner {{
    width: 100%;
}}

.cover-meta-fila {{
    border: none;
    padding: 0 6mm 1.5mm 0;
    vertical-align: top;
}}

/* N2.4: el bloque de metadatos NO lleva zebra. La regla generica
   `tbody tr:nth-child(even)` (mas abajo en esta misma hoja) pintaba de #f8fafc
   la 2a fila de la tabla anidada — justo la de CRITERIOS DE ACEPTACION — y
   dejaba texto claro sobre fondo claro. El fondo va en el <tr>, asi que no
   basta con poner el <td> transparente: hay que anular la regla en la fila. */
.cover-meta-grid tr, .cover-meta-inner tr,
.cover-meta-grid td, .cover-meta-inner td {{
    background: none !important;
}}

.cover-meta-label {{
    font-size: 7pt;
    text-transform: uppercase;
    color: #94a3b8;   /* N2.4: todas las etiquetas del bloque, iguales entre si */
    letter-spacing: 0.5px;
}}

.cover-meta-value {{
    font-size: 12pt;
    color: #ffffff;      /* N2.4: valores principales */
    font-weight: 500;
    margin-top: 1mm;
}}

/* N2.3/N2.4: valores secundarios del bloque — rango horario y nombre del
   archivo. */
.cover-meta-sub {{
    font-size: 10pt;
    color: #cbd5e1;
    margin-top: 0.8mm;
}}

.cover-badge {{
    display: inline-block;
    padding: 1.5mm 5mm;
    border-radius: 4mm;
    font-size: 9pt;
    font-weight: 600;
    text-transform: uppercase;
    border: 0.4mm solid rgba(255,255,255,0.4);
}}

.cover-footer {{
    margin-top: 3mm;
    font-size: 7pt;
    color: rgba(255,255,255,0.4);
}}

/* Cover KPI cards — using table for WeasyPrint compatibility */
.cover-kpi-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 5px;
    /* N2.3: 5mm -> 3mm. El bloque de metadatos crecio (3 filas + logo con
       aire) y la portada debe seguir cabiendo en una sola pagina. */
    margin-top: 3mm;
}}

.cover-kpi-table td {{
    width: 25%;
    background: rgba(255,255,255,0.95);
    border-radius: 3mm;
    padding: 2.5mm 5mm;   /* N2.3: 4mm -> 2.5mm, ~6mm recuperados en las 2 filas */
    border-left: 5px solid #3b82f6;
    border-bottom: none;
    vertical-align: top;
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

/* N2.1: unidad indivisible grafica + analisis, en dos columnas */
.chart-unit {{
    width: 100%;
    margin-bottom: 4mm;
    page-break-inside: avoid;
    break-inside: avoid;
}}

.chart-unit td {{
    padding: 0;
    border-bottom: none;
    vertical-align: top;
}}

.chart-cell {{
    width: 46%;
    padding-right: 4mm !important;
}}

.chart-ai-cell {{
    width: 54%;
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

/* AI boxes — Indigo themed (Bloque A.1 visual match) */
.ai-box {{
    background: #ffffff;
    border: 0.4mm solid #4f46e5;
    border-left: 1.5mm solid #4f46e5;
    border-radius: 1.5mm;
    padding: 3mm 4mm;
    margin: 0 0 3mm 0;
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
    line-height: 1.45;
    color: #334155;
}}

.ai-text p {{
    margin: 0 0 6px 0;
}}

.ai-text strong {{
    color: #1e293b;
}}

/* Two-column grid — table for WeasyPrint */
.grid-2 {{
    width: 100%;
    margin-bottom: 5mm;
}}

/* Footer */
.report-footer {{
    text-align: center;
    font-size: 8pt;
    color: #64748b;
    padding-top: 5mm;
    border-top: 0.5mm solid #f5a623;
    margin-top: 10mm;
}}

.report-footer strong {{
    color: #0a1628;
}}
</style>
</head>
<body>

<!-- ===== COVER PAGE ===== -->
<div class="cover">
    <table class="cover-top-table"><tr>
        <td style="vertical-align:top;text-align:left">
            <div class="cover-logo">sqa<span class="cover-logo-accent">_</span></div>
            <div class="cover-subtitle">Software Quality Assurance</div>
        </td>
        <td style="vertical-align:top;text-align:right;font-size:10pt;color:rgba(255,255,255,0.7)">
            Realizado por:<br><strong style="color:rgba(255,255,255,0.95);font-size:12pt">Celula de Performance SQA</strong>
        </td>
    </tr></table>

    <div style="border-top:0.5mm solid #f5a623;margin-bottom:6mm"></div>

    <div class="cover-info-box">
        <div class="cover-pretitle">
            REPORTE DE ANALISIS DE PERFORMANCE
            &nbsp;<span class="cover-badge" style="background:{tt_color}20;border-color:{tt_color}">{meta['testTypeLabel']}</span>
        </div>
        <div class="cover-title">{meta['project'] or meta['name']}</div>
        <table class="cover-meta-grid"><tr>
            <td class="cover-zona-izq">
                <table class="cover-meta-inner">
                    <tr>
                        <td class="cover-meta-fila" style="width:52%"><div class="cover-meta-label">EJECUCION</div><div class="cover-meta-value">{_cm['date']}</div><div class="cover-meta-sub">{_cm['range']}</div></td>
                        <td class="cover-meta-fila"><div class="cover-meta-label">DURACION</div><div class="cover-meta-value">{duration_min}m {duration_sec}s</div></td>
                    </tr>
                    {cover_fila_criterios}
                    <tr><td colspan="2" class="cover-meta-fila"><div class="cover-meta-label">ARCHIVO</div><div class="cover-meta-sub" style="font-size:10.5pt">{files_list}</div></td></tr>
                </table>
            </td>
            <td class="cover-zona-der">{cover_cell_cliente}</td>
        </tr></table>
    </div>

    <table class="cover-kpi-table"><tr>
        <td style="border-left-color:#4CAF50"><div style="font-size:8pt;color:#64748b;text-transform:uppercase;font-weight:600;letter-spacing:0.3px">TOTAL REQUESTS</div><div style="font-size:22pt;font-weight:700;color:#0a1628;margin-top:2mm">{meta['totalRequests']:,}</div></td>
        <td style="border-left-color:#2196F3"><div style="font-size:8pt;color:#64748b;text-transform:uppercase;font-weight:600;letter-spacing:0.3px">AVG RESPONSE TIME</div><div style="font-size:22pt;font-weight:700;color:#0a1628;margin-top:2mm">{meta['avgResponseTime']:.0f} <span style="font-size:10pt;font-weight:400;color:#64748b">ms</span></div></td>
        <td style="border-left-color:{er_color}"><div style="font-size:8pt;color:#64748b;text-transform:uppercase;font-weight:600;letter-spacing:0.3px">ERROR RATE</div><div style="font-size:22pt;font-weight:700;color:{er_color};margin-top:2mm">{meta['errorRate']:.2f}<span style="font-size:10pt;font-weight:400">%</span></div></td>
        <td style="border-left-color:#4CAF50"><div style="font-size:8pt;color:#64748b;text-transform:uppercase;font-weight:600;letter-spacing:0.3px">THROUGHPUT</div><div style="font-size:22pt;font-weight:700;color:#0a1628;margin-top:2mm">{meta['throughput']:.2f} <span style="font-size:10pt;font-weight:400;color:#64748b">req/s</span></div></td>
    </tr><tr>
        <td style="border-left-color:#ff9800"><div style="font-size:8pt;color:#ff9800;text-transform:uppercase;font-weight:600;letter-spacing:0.3px">P90</div><div style="font-size:22pt;font-weight:700;color:#0a1628;margin-top:2mm">{meta['p90']:.0f} <span style="font-size:10pt;font-weight:400;color:#64748b">ms</span></div></td>
        <td style="border-left-color:#ff9800"><div style="font-size:8pt;color:#ff9800;text-transform:uppercase;font-weight:600;letter-spacing:0.3px">P95</div><div style="font-size:22pt;font-weight:700;color:#0a1628;margin-top:2mm">{meta['p95']:.0f} <span style="font-size:10pt;font-weight:400;color:#64748b">ms</span></div></td>
        <td style="border-left-color:#9c27b0"><div style="font-size:8pt;color:#9c27b0;text-transform:uppercase;font-weight:600;letter-spacing:0.3px">P99</div><div style="font-size:22pt;font-weight:700;color:#0a1628;margin-top:2mm">{meta['p99']:.0f} <span style="font-size:10pt;font-weight:400;color:#64748b">ms</span></div></td>
        <td style="border-left-color:#2196F3"><div style="font-size:8pt;color:#64748b;text-transform:uppercase;font-weight:600;letter-spacing:0.3px">AVG LATENCY</div><div style="font-size:22pt;font-weight:700;color:#0a1628;margin-top:2mm">{meta['avgLatency']:.0f} <span style="font-size:10pt;font-weight:400;color:#64748b">ms</span></div></td>
    </tr></table>

    <div style="margin-top:3mm;text-align:center;font-size:9pt;color:rgba(255,255,255,0.4)">
        Celula de Performance SQA
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

<!-- ===== CHARTS (N2.1: flujo denso, unidad grafica+analisis) ===== -->
{chart_unit('Response Times por Transaccion', '#8884d8', 'rt_label', 'responseTimes', 'Analisis - Response Times por Transaccion')}
{chart_unit('Throughput Over Time', '#4CAF50', 'throughput', 'throughput', 'Analisis - Throughput')}
{chart_unit('Latency Over Time', '#9c27b0', 'latency', 'latency', 'Analisis - Latency')}
{chart_unit('Error Rate Over Time', '#f44336', 'error_rate', 'errorRate', 'Analisis - Error Rate')}
{chart_unit('Response Codes per Second', '#4CAF50', 'codes', 'codesPerSecond', 'Analisis - Response Codes')}
{chart_unit('Transactions per Second', '#4CAF50', 'tps', 'tps', 'Analisis - Transactions per Second')}
{chart_unit('Active Threads Over Time', '#2196F3', 'threads', 'activeThreads', 'Analisis - Active Threads')}
{chart_unit('Distribucion de Response Codes', '#ff9800', 'pie', 'errors', 'Analisis de Errores')}

<!-- ===== N3.5: ANALISIS POR TRANSACCION CRITICA (antes de conclusiones) ===== -->
{transaction_analyses_html(meta.get('transaction_analyses'), for_pdf=True)}

<!-- ===== CONCLUSIONES Y RECOMENDACIONES ===== -->
{ai_box('conclusions', 'Conclusiones', '#4f46e5', allow_break=True)}
{ai_box('recommendations', 'Recomendaciones', '#4f46e5', allow_break=True)}

<!-- ===== FOOTER ===== -->
<div class="report-footer">
    <strong>sqa &mdash; Software Quality Assurance</strong><br>
    Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos
</div>

</body>
</html>'''
