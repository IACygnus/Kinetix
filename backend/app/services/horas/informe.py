"""El documento del informe de horas (ETAPA H5.3 y H5.4, especificación v1.2 §7).

**Un solo informe** (H-D50): el HTML y el PDF son este mismo módulo con dos ramas.
Las ocho secciones se arman una sola vez, en `_secciones()`; lo que cambia entre
una rama y otra es la envoltura —los estilos y, en el HTML, los controles—, nunca
el contenido. Si cada salida montara sus tablas por su cuenta, en tres semanas
dirían cosas distintas: es exactamente lo que le pasó al informe de análisis y lo
que costó la Etapa 2 entera arreglar.

**Generador propio** (H-D51). No se toca `report_generator.py`, que está protegido
y es del módulo de análisis. Lo que sí se respeta son sus reglas, que están en
CLAUDE.md §13 y §15 y valen para cualquier PDF de este producto:

  - en la rama de impresión, **solo tablas**: ni `flex` ni `grid`, que WeasyPrint
    procesa mal;
  - medidas en `mm` y `pt`, **nunca `rem`**, que infla el PDF entre un 35 y un 42 %;
  - el PDF va **todo en vertical** desde H-D69: la única sección que giraba la
    hoja salió del informe.

**La plantilla no calcula nada.** Todo llega resuelto de `informe_datos.py`. La
única aritmética que hay aquí vive en el JavaScript del HTML, y solo para rehacer
los totales cuando el lector filtra sin servidor (H-D55); está acotada a sumar
filas del detalle, que es el mismo dato crudo que sumó el backend.
"""
import base64
import csv
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from app.schemas.time_tracking import InformeDatos

# H-D54: el logo va embebido, no enlazado, para que el documento funcione sin red.
RUTA_LOGO = Path(__file__).resolve().parents[2] / "assets" / "logo-sqa.png"

# Las ocho secciones de §7.2 (v1.3), en su orden. La clave viaja en el filtro.
SECCIONES = (
    ("resumen", "Resumen"),
    ("personas", "Ocupación por persona"),
    ("facturacion", "Facturable frente a no facturable"),
    ("clientes", "Cobertura por cliente"),
    ("actividades", "En qué se fue el tiempo"),
    ("proyectos", "Consumido frente a estimado"),
    ("mapa", "Mapa del mes"),
    # ETAPA H6 (H-D68): «Días sin registrar» y «Horas día a día» salieron del
    # informe. Sus datos se siguen calculando y se siguen viendo donde sirven —el
    # calendario y la consulta—, pero en un informe para leer no aportaban lo que
    # ocupaban. El backend los sigue devolviendo: lo que se retira es la sección.
    ("detalle", "Detalle de registros"),
)
CLAVES = tuple(k for k, _ in SECCIONES)

DIAS_CORTOS = ("L", "M", "X", "J", "V", "S", "D")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


# ===================== FORMATO ESPAÑOL (H-D60) =====================

def num(v, decimales: int = 2) -> str:
    """`8600.5` -> `8.600,5`. Sin decimales inútiles: `8` no es `8,00`."""
    d = Decimal(str(v or 0)).quantize(Decimal(10) ** -decimales)
    entero, _, dec = f"{abs(d):f}".partition(".")
    dec = dec.rstrip("0")
    miles = f"{int(entero):,}".replace(",", ".")
    signo = "-" if d < 0 else ""
    return f"{signo}{miles},{dec}" if dec else f"{signo}{miles}"


def horas(v) -> str:
    return f"{num(v)} h"


def pct(v) -> str:
    return f"{num(v, 1)} %"


def fecha_larga(f: date) -> str:
    return f"{f.day} de {MESES[f.month - 1]} de {f.year}"


def fecha_corta(f: date) -> str:
    return f"{f.day:02d}/{f.month:02d}"


def esc(t) -> str:
    """Escapa lo que va dentro del HTML. Los nombres de proyecto los escribe
    gente, y un `&` o un `<` no pueden romper el documento."""
    return (str(t if t is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def sin_tildes(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(t))
                   if unicodedata.category(c) != "Mn")


def nombre_archivo(d: InformeDatos, extension: str) -> str:
    """H-D61: `informe-horas-<periodo>-<persona o equipo>.<ext>`, sin tildes."""
    periodo = f"{d.filtros.desde:%Y-%m-%d}_{d.filtros.hasta:%Y-%m-%d}"
    if d.filtros.desde.day == 1 and d.filtros.hasta.month == d.filtros.desde.month:
        periodo = f"{d.filtros.desde:%Y-%m}"
    alcance = sin_tildes(d.filtros.alcance).lower().replace(" ", "-")
    limpio = "".join(c for c in alcance if c.isalnum() or c == "-")
    return f"informe-horas-{periodo}-{limpio or 'equipo'}.{extension}"


def _logo() -> Optional[str]:
    """El logo en base64, o `None` si el archivo no está (H-D54: no es parada)."""
    try:
        if RUTA_LOGO.is_file():
            return base64.b64encode(RUTA_LOGO.read_bytes()).decode("ascii")
    except OSError:
        pass
    return None


# ===================== PIEZAS =====================

def _tabla(cabeceras: Sequence[str], filas: Iterable[str], clase: str = "",
           alineadas: Sequence[int] = (), ordenable: bool = False) -> str:
    """Una tabla. `alineadas` son las columnas que van a la derecha (son cifras)."""
    ths = []
    for i, c in enumerate(cabeceras):
        clases = " num" if i in alineadas else ""
        orden = f' data-col="{i}"' if ordenable else ""
        ths.append(f'<th class="{clases.strip()}"{orden}>{esc(c)}</th>')
    cuerpo = "".join(filas)
    return (f'<table class="{clase}">'
            f"<thead><tr>{''.join(ths)}</tr></thead>"
            f"<tbody>{cuerpo}</tbody></table>")


def _celdas(valores: Sequence[str], alineadas: Sequence[int] = ()) -> str:
    return "".join(
        f'<td class="num">{v}</td>' if i in alineadas else f"<td>{v}</td>"
        for i, v in enumerate(valores))


def _indicador(etiqueta: str, valor: str, clave: str = "") -> str:
    """Una casilla del resumen. En tabla, no en rejilla: la rama de impresión lo
    exige (regla 11) y usar la misma estructura en las dos evita dos maquetas."""
    ident = f' id="ind-{clave}"' if clave else ""
    return (f'<td class="ind"><span class="ind-et">{esc(etiqueta)}</span>'
            f'<span class="ind-val"{ident}>{valor}</span></td>')


# ===================== LAS SECCIONES =====================

def _sec_resumen(d: InformeDatos, para_pdf: bool = False) -> str:
    r = d.resumen
    casillas = [
        _indicador("Horas registradas", horas(r.total_hours), "total"),
        _indicador("Ordinarias", horas(r.ordinary_hours), "ord"),
        _indicador("Horas extra", horas(r.overtime_hours), "extra"),
        _indicador("Facturables", horas(r.billable_hours), "fact"),
        _indicador("% facturable", pct(r.billable_pct), "pctfact"),
        _indicador("Días sin registrar", num(r.pending_days, 0), "pend"),
    ]
    return (f'<table class="indicadores"><tr>{"".join(casillas[:3])}</tr>'
            f'<tr>{"".join(casillas[3:])}</tr></table>'
            f'<p class="nota">Jornada del periodo hasta hoy: '
            f'<strong>{horas(r.expected_hours)}</strong> · '
            f'{num(r.people_count, 0)} persona(s) · {num(r.entries_count, 0)} registros.</p>')


def _sec_personas(d: InformeDatos, para_pdf: bool = False) -> str:
    filas = []
    for p in d.personas:
        filas.append(
            f'<tr data-persona="{esc(p.user_name)}">'
            + _celdas([esc(p.user_name), horas(p.expected_hours), horas(p.ordinary_hours),
                       horas(p.overtime_hours), horas(p.billable_hours),
                       pct(p.occupancy_pct), num(p.pending_days, 0)],
                      alineadas=(1, 2, 3, 4, 5, 6))
            + "</tr>")
    return _tabla(["Persona", "Jornada", "Ordinarias", "Extra", "Facturables",
                   "Ocupación", "Días sin registrar"], filas,
                  alineadas=(1, 2, 3, 4, 5, 6), ordenable=True)


def _sec_facturacion(d: InformeDatos, para_pdf: bool = False) -> str:
    filas = []
    for f in d.facturacion:
        filas.append(
            f'<tr data-cliente="{esc(f.client_name)}">'
            + _celdas([esc(f.client_name), horas(f.billable_hours),
                       horas(f.non_billable_hours), horas(f.total_hours),
                       pct(f.billable_pct)], alineadas=(1, 2, 3, 4))
            + "</tr>")
    return _tabla(["Cliente", "Facturable", "No facturable", "Total", "% facturable"],
                  filas, alineadas=(1, 2, 3, 4), ordenable=True)


def _sec_reparto(items, titulo_col: str) -> str:
    filas = []
    for x in items:
        # La barra va en una celda de tabla con un div de ancho porcentual: se ve
        # igual en pantalla y en papel, y no necesita ni flex ni grid.
        barra = (f'<div class="barra"><div class="barra-relleno" '
                 f'style="width:{min(float(x.pct), 100):.1f}%"></div></div>')
        filas.append(
            f'<tr data-cliente="{esc(x.name)}">'
            + _celdas([esc(x.name), horas(x.hours), pct(x.pct), barra],
                      alineadas=(1, 2))
            + "</tr>")
    return _tabla([titulo_col, "Horas", "%", ""], filas, alineadas=(1, 2), ordenable=True)


def _sec_proyectos(d: InformeDatos, para_pdf: bool = False) -> str:
    filas = []
    for p in d.proyectos:
        marca = {"desfasado": "mal", "por_agotarse": "ojo"}.get(p.overrun_status, "bien")
        filas.append(
            f'<tr data-cliente="{esc(p.client_name)}" data-proyecto="{esc(p.project_name)}" '
            f'class="{marca}">'
            + _celdas([esc(p.client_name), esc(p.project_name),
                       horas(p.hours_in_range), horas(p.estimated_hours),
                       horas(p.consumed_hours), horas(p.remaining_hours),
                       f'<span class="pill {marca}">{esc(p.overrun_label)}</span>'],
                      alineadas=(2, 3, 4, 5))
            + "</tr>")
    return _tabla(["Cliente", "Proyecto", "En el periodo", "Estimadas", "Consumidas",
                   "Restantes", "Estado"], filas, alineadas=(2, 3, 4, 5), ordenable=True)


def _sec_mapa(d: InformeDatos, para_pdf: bool = False) -> str:
    cab = ['<th class="izq">Persona</th>']
    for f in d.dias:
        cab.append(f'<th class="dia"><span class="dsem">{DIAS_CORTOS[f.weekday()]}</span>'
                   f'<span class="dnum">{f.day}</span></th>')
    cab.append('<th class="num">Total</th>')

    filas = []
    for p in d.mapa:
        celdas = [f'<td class="izq">{esc(p.user_name)}</td>']
        for h, estado in zip(p.por_dia, p.estados):
            # En papel el mapa habla por color y no lleva cifras: con 31 columnas
            # en una hoja vertical, meter «8,5» obligaría a bajar de 8 pt, y por
            # debajo de eso no se lee. La leyenda dice lo que significa cada color
            # y las horas exactas están en la sección 9.
            texto = "" if para_pdf else (num(h) if h and float(h) > 0 else "")
            celdas.append(f'<td class="casilla {estado}">{texto}</td>')
        celdas.append(f'<td class="num">{horas(p.total_hours)}</td>')
        filas.append(f'<tr data-persona="{esc(p.user_name)}">{"".join(celdas)}</tr>')

    leyenda = ('<p class="nota leyenda">'
               '<span class="mini trabajado"></span> trabajado '
               '<span class="mini incompleto"></span> incompleto '
               '<span class="mini festivo"></span> festivo '
               '<span class="mini ausencia"></span> ausencia '
               '<span class="mini finde"></span> fin de semana</p>')
    return (f'<table class="mapa"><thead><tr>{"".join(cab)}</tr></thead>'
            f'<tbody>{"".join(filas)}</tbody></table>{leyenda}')


def _sec_pendientes(d: InformeDatos, para_pdf: bool = False) -> str:
    if not d.pendientes:
        return '<p class="vacio">No hay días sin registrar en el periodo.</p>'
    filas = []
    for p in d.pendientes:
        filas.append(
            f'<tr data-persona="{esc(p.user_name)}">'
            + _celdas([esc(p.user_name), f"{DIAS_CORTOS[p.date.weekday()]} {fecha_corta(p.date)}",
                       horas(p.expected_hours), horas(p.ordinary_hours),
                       f'<strong class="mal">{horas(p.missing_hours)}</strong>'],
                      alineadas=(2, 3, 4))
            + "</tr>")
    return _tabla(["Persona", "Día", "Jornada", "Registradas", "Faltan"], filas,
                  alineadas=(2, 3, 4), ordenable=True)


def _sec_diarias(d: InformeDatos, para_pdf: bool = False) -> str:
    """Sección 9. Es la tabla que obliga a girar la hoja en el PDF (H-D56)."""
    cab = ['<th class="izq">Cliente</th>', '<th class="izq">Proyecto</th>',
           '<th class="izq">Actividad</th>']
    for f in d.dias:
        cab.append(f'<th class="dia"><span class="dsem">{DIAS_CORTOS[f.weekday()]}</span>'
                   f'<span class="dnum">{f.day}</span></th>')
    cab.append('<th class="num">Total</th>')

    filas = []
    for x in d.diarias:
        celdas = [f'<td class="izq">{esc(x.client_name)}</td>',
                  f'<td class="izq">{esc(x.project_name)}</td>',
                  f'<td class="izq">{esc(x.activity_name)}</td>']
        for h in x.por_dia:
            celdas.append(f'<td class="celda">{num(h) if h and float(h) > 0 else ""}</td>')
        celdas.append(f'<td class="num">{horas(x.total_hours)}</td>')
        filas.append(f'<tr data-cliente="{esc(x.client_name)}" '
                     f'data-proyecto="{esc(x.project_name)}">{"".join(celdas)}</tr>')
    if not filas:
        return '<p class="vacio">No hay horas registradas en el periodo.</p>'
    return (f'<table class="diaria"><thead><tr>{"".join(cab)}</tr></thead>'
            f'<tbody>{"".join(filas)}</tbody></table>')


def _sec_detalle(d: InformeDatos, para_pdf: bool = False) -> str:
    filas = []
    for r in d.detalle:
        marcas = []
        if r.overtime:
            marcas.append('<span class="pill ojo">extra</span>')
        if r.over_estimate:
            marcas.append('<span class="pill mal">desfase</span>')
        filas.append(
            f'<tr data-persona="{esc(r.user_name)}" data-cliente="{esc(r.client_name)}" '
            f'data-proyecto="{esc(r.project_name)}" '
            f'data-facturable="{"si" if r.billable else "no"}" '
            f'data-horas="{r.hours}">'
            + _celdas([f"{DIAS_CORTOS[r.date.weekday()]} {fecha_corta(r.date)}",
                       esc(r.user_name), esc(r.client_name), esc(r.project_name),
                       esc(r.activity_name), num(r.hours),
                       "Sí" if r.billable else "No",
                       " ".join(marcas), esc(r.notes or "")],
                      alineadas=(5,))
            + "</tr>")
    if not filas:
        return '<p class="vacio">No hay registros en el periodo.</p>'
    aviso = ""
    if d.detalle_total > len(d.detalle):
        aviso = (f'<p class="nota">Se muestran {num(len(d.detalle), 0)} de '
                 f'{num(d.detalle_total, 0)} registros.</p>')
    return _tabla(["Día", "Persona", "Cliente", "Proyecto", "Actividad", "Horas",
                   "¿Se cobra?", "", "Observaciones"], filas,
                  clase="detalle", alineadas=(5,), ordenable=True) + aviso


_CONSTRUCTORES = {
    "resumen": _sec_resumen,
    "personas": _sec_personas,
    "facturacion": _sec_facturacion,
    "clientes": lambda d, p=False: _sec_reparto(d.por_cliente, "Cliente"),
    "actividades": lambda d, p=False: _sec_reparto(d.por_actividad, "Actividad"),
    "proyectos": _sec_proyectos,
    "mapa": _sec_mapa,
    "detalle": _sec_detalle,
}


def _secciones(d: InformeDatos, elegidas: Sequence[str], para_pdf: bool) -> str:
    """El cuerpo del documento. **El mismo para las dos ramas** (H-D50)."""
    partes = []
    for i, (clave, titulo) in enumerate(SECCIONES, start=1):
        if clave not in elegidas:
            continue
        # H-D69: el PDF va todo en vertical. La única sección que obligaba a
        # girar la hoja era «Horas día a día», y ya no está.
        clases = "seccion"
        partes.append(
            f'<section class="{clases}" id="sec-{clave}">'
            f'<h2><span class="numsec">{i}</span>{esc(titulo)}</h2>'
            f'{_CONSTRUCTORES[clave](d, para_pdf)}</section>')
    return "".join(partes)


def _encabezado(d: InformeDatos) -> str:
    """La portada (ETAPA H7, H-D73), la que aprobó Fredy.

    De arriba abajo: el logo con «Centro de Excelencia · Performance» al lado y la
    fecha de generación a la derecha; una banda azul y naranja; el título con el
    periodo en naranja; y una fila con **Dirigido a**, **Período** y **Equipo**,
    más la **capacidad base** del periodo.

    Todo en tablas y en `mm`/`pt`: la misma estructura sirve para la pantalla y
    para el PDF, y la rama de impresión no admite `flex` ni `grid` (regla 11).
    """
    logo = _logo()
    marca = (f'<img class="logo" src="data:image/png;base64,{logo}" alt="SQA Kinetix">'
             if logo else '<span class="marca">SQA<b>Kinetix</b></span>')

    filtros = []
    if d.filtros.client_name:
        filtros.append(f"Cliente: {esc(d.filtros.client_name)}")
    if d.filtros.project_name:
        filtros.append(f"Proyecto: {esc(d.filtros.project_name)}")
    if d.filtros.solo_facturables:
        filtros.append("Solo horas facturables")
    extra = f'<p class="filtros">{" · ".join(filtros)}</p>' if filtros else ""

    # El equipo, con los nombres completos. Si son muchos, se dice cuántos: una
    # portada con veinte nombres deja de ser una portada.
    nombres = d.filtros.personas
    if not nombres:
        equipo = "Sin personas en el periodo"
    elif len(nombres) <= 4:
        equipo = " · ".join(esc(n) for n in nombres)
    else:
        equipo = f"{esc(' · '.join(nombres[:3]))} y {len(nombres) - 3} más"

    cap = d.capacidad
    capacidad = (f"{num(cap.working_days, 0)} días hábiles · "
                 f"{horas(cap.hours_per_analyst)} por analista")
    if cap.people_count > 1:
        capacidad += f" · {horas(cap.total_hours)} del equipo"

    def dato(rotulo: str, valor: str) -> str:
        return (f'<td class="dato"><span class="dato-rot">{esc(rotulo)}</span>'
                f'<span class="dato-val">{valor}</span></td>')

    return (
        f'<header class="cabecera">'
        f'<table class="cab"><tr>'
        f'<td class="cab-logo">{marca}</td>'
        f'<td class="cab-coe">Centro de Excelencia<span class="coe-sep"> · </span>'
        f'<strong>Performance</strong></td>'
        f'<td class="cab-der">Generado el {fecha_larga(d.generado.date())}</td>'
        f"</tr></table>"
        f'<div class="banda"><span class="banda-naranja"></span></div>'
        f'<div class="titulo">'
        f"<h1>Informe de horas</h1>"
        f'<p class="sub">{esc(d.filtros.periodo)}</p>'
        f"</div>"
        f'<table class="portada"><tr>'
        + dato("Dirigido a", esc(d.filtros.dirigido_a) or "—")
        + dato("Período", esc(d.filtros.periodo))
        + dato("Equipo", equipo)
        + "</tr><tr>"
        + f'<td class="dato" colspan="3"><span class="dato-rot">Capacidad base</span>'
          f'<span class="dato-val">{capacidad}</span></td>'
        + "</tr></table>"
        f"{extra}</header>")


# ===================== LOS ESTILOS =====================

_BASE_CSS = """
*{box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:#1f2937;margin:0}
h1{font-size:26pt;color:#0a1628;margin:0 0 2mm}
h2{font-size:13pt;color:#0a1628;margin:0 0 3mm;border-bottom:2px solid #f5a623;
   padding-bottom:1.5mm}
.numsec{display:inline-block;background:#0a1628;color:#fff;width:7mm;height:7mm;
        line-height:7mm;text-align:center;border-radius:1mm;margin-right:2.5mm;
        font-size:10pt}
.sub{font-size:13pt;color:#4b5563;margin:0 0 1mm}
.filtros{font-size:10pt;color:#6b7280;margin:0}
/* ===== La portada (H-D73). Los colores del logo: azul marino y naranja. ===== */
.cabecera{margin-bottom:7mm}
.cab{width:100%;margin-bottom:2.5mm}
.cab-logo{width:40mm;vertical-align:middle}
.cab-coe{font-size:11pt;color:#0a1628;vertical-align:middle;letter-spacing:.3pt}
.cab-coe strong{color:#f5a623}
.coe-sep{color:#f5a623;font-weight:700}
.cab-der{text-align:right;font-size:9pt;color:#6b7280;vertical-align:middle}
.logo{height:22mm}                 /* que se lea: 14 mm se quedaba corto */
.marca{font-size:22pt;color:#0a1628;letter-spacing:.5pt;font-weight:700}
.marca b{color:#f5a623}
/* La banda: azul de lado a lado y el naranja encima, a la izquierda. En dos
   divs y no en un degradado, que WeasyPrint dibuja de forma desigual. */
.banda{background:#0a1628;height:2.2mm;margin-bottom:5mm;font-size:0}
.banda-naranja{display:inline-block;background:#f5a623;height:2.2mm;width:38%}
.titulo h1{font-size:26pt;color:#0a1628;margin:0;letter-spacing:-.3pt}
.titulo .sub{font-size:16pt;color:#f5a623;font-weight:700;margin:1mm 0 5mm}
/* La fila de datos de la portada: Dirigido a · Período · Equipo, y debajo la
   capacidad base. En tabla, que es lo único que la rama de impresión admite. */
.portada{width:100%;border-top:.5pt solid #e5e7eb}
.portada td.dato{width:33.33%;padding:3mm 4mm 3mm 0;vertical-align:top;
                 border-bottom:.5pt solid #e5e7eb}
.dato-rot{display:block;font-size:8pt;color:#6b7280;text-transform:uppercase;
          letter-spacing:.4pt;margin-bottom:1mm}
.dato-val{display:block;font-size:11pt;color:#0a1628;font-weight:600}
table{border-collapse:collapse;width:100%}
th{background:#f3f4f6;color:#374151;font-size:8.5pt;text-transform:uppercase;
   text-align:left;padding:2mm;border-bottom:1.5pt solid #d1d5db}
td{padding:1.8mm 2mm;border-bottom:.5pt solid #e5e7eb;font-size:9.5pt}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
td.izq{text-align:left}
tr.mal td{background:#fef2f2}
tr.ojo td{background:#fffbeb}
.pill{display:inline-block;padding:.6mm 2mm;border-radius:3mm;font-size:8pt;
      font-weight:700}
.pill.bien{background:#f3f4f6;color:#4b5563}
.pill.ojo{background:#fef3c7;color:#92400e}
.pill.mal{background:#fee2e2;color:#991b1b}
strong.mal{color:#991b1b}
.indicadores td.ind{width:33%;border:.5pt solid #e5e7eb;padding:3mm;
                    background:#f9fafb}
.ind-et{display:block;font-size:8pt;color:#6b7280;text-transform:uppercase}
.ind-val{display:block;font-size:17pt;font-weight:700;color:#0a1628;
         font-variant-numeric:tabular-nums}
.nota{font-size:9pt;color:#6b7280;margin:2mm 0 0}
.vacio{font-size:10pt;color:#9ca3af;padding:4mm 0;margin:0}
.barra{background:#e5e7eb;height:3mm;border-radius:2mm;overflow:hidden;min-width:25mm}
.barra-relleno{background:#4f46e5;height:100%}
.mapa th.dia,.diaria th.dia{text-align:center;padding:1mm .4mm;font-size:8pt}
.dsem{display:block;color:#9ca3af}
.dnum{display:block;font-weight:700}
.mapa td.casilla,.diaria td.celda{text-align:center;font-size:8pt;padding:1mm .4mm;
                                  font-variant-numeric:tabular-nums}
td.casilla.trabajado{background:#dcfce7}
td.casilla.incompleto{background:#fef3c7}
td.casilla.festivo{background:#e0e7ff}
td.casilla.ausencia{background:#f3e8ff}
td.casilla.finde{background:#f3f4f6}
.mini{display:inline-block;width:3.5mm;height:3.5mm;vertical-align:middle;
      border:.5pt solid #d1d5db;margin:0 1mm 0 3mm}
.mini.trabajado{background:#dcfce7}.mini.incompleto{background:#fef3c7}
.mini.festivo{background:#e0e7ff}.mini.ausencia{background:#f3e8ff}
.mini.finde{background:#f3f4f6}
"""

_PDF_CSS = """
@page{size:A4 portrait;margin:14mm 12mm 16mm;
      @bottom-right{content:"Página " counter(page) " de " counter(pages);
                    font-size:8pt;color:#9ca3af}}
body{font-size:9.5pt}
.seccion{margin-bottom:7mm}
/* Que ninguna tabla se corte a media fila. */
tr{page-break-inside:avoid}
thead{display:table-header-group}
h2{page-break-after:avoid}
/* Ningun texto por debajo de 8 pt: en papel, menos de eso no se lee. */
.diaria td.celda,.diaria th.dia{font-size:8pt;padding:.8mm .3mm}
/* El mapa, en el PDF, habla por color: con 31 columnas en vertical, meter la
   cifra obligaria a bajar de 8 pt, y la leyenda ya dice lo que significa cada uno. */
.mapa td.casilla{font-size:8pt}
"""

_WEB_CSS = """
body{background:#f3f4f6;padding:0 0 40px}
.hoja{max-width:1180px;margin:0 auto;background:#fff;padding:28px 34px;
      box-shadow:0 1px 3px rgba(0,0,0,.1)}
.seccion{margin-bottom:26px}
.controles{position:sticky;top:0;z-index:5;background:#0a1628;color:#fff;
           padding:12px 34px;margin-bottom:0}
.controles .fila{max-width:1180px;margin:0 auto;display:flex;flex-wrap:wrap;
                 gap:10px;align-items:center}
.controles label{font-size:13px;color:#cbd5e1}
.controles select,.controles input[type=search]{padding:8px 10px;border-radius:8px;
   border:1px solid #334155;background:#fff;font-size:14px;min-height:38px}
.btn{padding:9px 16px;border-radius:8px;border:2px solid #f5a623;background:#f5a623;
     color:#0a1628;font-weight:700;font-size:14px;cursor:pointer;min-height:40px}
.btn.sec{background:transparent;color:#f5a623}
.btn.persona{border-color:#475569;background:transparent;color:#e2e8f0;font-weight:600}
.btn.persona.activo{background:#f5a623;border-color:#f5a623;color:#0a1628}
th[data-col]{cursor:pointer;user-select:none}
th[data-col]:hover{background:#e5e7eb}
th[data-col]::after{content:" \\2195";color:#9ca3af;font-size:9px}
tr.oculta{display:none}
.detalle td{font-size:13px}
@media print{.controles{display:none}.hoja{box-shadow:none;max-width:none;padding:0}}
"""


# ===================== EL JAVASCRIPT (H-D55) =====================

_JS = r"""
(function(){
  var D = window.__INFORME__;
  function esp(n, dec){
    if (dec === undefined) dec = 2;
    var s = Math.abs(n).toFixed(dec).replace('.', ',');
    var p = s.split(',');
    p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    var t = p[1] ? (p[0] + ',' + p[1].replace(/0+$/, '')) : p[0];
    if (t.slice(-1) === ',') t = t.slice(0, -1);
    return (n < 0 ? '-' : '') + t;
  }
  var F = {persona:'', cliente:'', proyecto:'', facturable:false, texto:''};

  function coincide(tr){
    if (F.persona && tr.dataset.persona && tr.dataset.persona !== F.persona) return false;
    if (F.cliente && tr.dataset.cliente && tr.dataset.cliente !== F.cliente) return false;
    if (F.proyecto && tr.dataset.proyecto && tr.dataset.proyecto !== F.proyecto) return false;
    if (F.facturable && tr.dataset.facturable === 'no') return false;
    return true;
  }

  function aplicar(){
    // Las filas se filtran por sus propios datos; ninguna tabla se rehace.
    document.querySelectorAll('tbody tr').forEach(function(tr){
      var ok = coincide(tr);
      if (ok && F.texto && tr.closest('table.detalle')){
        ok = tr.textContent.toLowerCase().indexOf(F.texto) !== -1;
      }
      tr.classList.toggle('oculta', !ok);
    });
    recalcular();
  }

  // Los seis indicadores se rehacen SUMANDO LAS FILAS VISIBLES DEL DETALLE, que
  // es el mismo dato crudo que sumo el servidor. No se inventa ninguna regla: lo
  // que depende de la jornada o de las estimaciones (secciones 2, 6, 7 y 8) se
  // filtra por fila y no se recalcula, porque esos datos no viajan en el detalle.
  function recalcular(){
    var det = document.querySelector('table.detalle');
    if (!det) return;
    var t=0, extra=0, fact=0, n=0;
    det.querySelectorAll('tbody tr').forEach(function(tr){
      if (tr.classList.contains('oculta')) return;
      var h = parseFloat(tr.dataset.horas || '0');
      t += h; n += 1;
      if (tr.querySelector('.pill.ojo')) extra += h;
      if (tr.dataset.facturable === 'si') fact += h;
    });
    poner('ind-total', esp(t) + ' h');
    poner('ind-ord', esp(t - extra) + ' h');
    poner('ind-extra', esp(extra) + ' h');
    poner('ind-fact', esp(fact) + ' h');
    poner('ind-pctfact', (t > 0 ? esp(fact / t * 100, 1) : '0') + ' %');
    var av = document.getElementById('aviso-filtro');
    if (av) av.style.display = (F.persona||F.cliente||F.proyecto||F.facturable) ? '' : 'none';
  }
  function poner(id, v){ var e = document.getElementById(id); if (e) e.textContent = v; }

  document.querySelectorAll('[data-persona-btn]').forEach(function(b){
    b.addEventListener('click', function(){
      document.querySelectorAll('[data-persona-btn]').forEach(function(x){
        x.classList.remove('activo'); });
      b.classList.add('activo');
      F.persona = b.dataset.personaBtn;
      aplicar();
    });
  });
  var sc = document.getElementById('f-cliente');
  if (sc) sc.addEventListener('change', function(){ F.cliente = sc.value; aplicar(); });
  var sp = document.getElementById('f-proyecto');
  if (sp) sp.addEventListener('change', function(){ F.proyecto = sp.value; aplicar(); });
  var cf = document.getElementById('f-facturable');
  if (cf) cf.addEventListener('change', function(){ F.facturable = cf.checked; aplicar(); });
  var bs = document.getElementById('f-busqueda');
  if (bs) bs.addEventListener('input', function(){
    F.texto = bs.value.trim().toLowerCase(); aplicar(); });

  // Ordenar por cabecera. Numerico si toda la columna lo es; si no, alfabetico.
  document.querySelectorAll('th[data-col]').forEach(function(th){
    th.addEventListener('click', function(){
      var tabla = th.closest('table'), i = +th.dataset.col;
      var cuerpo = tabla.tBodies[0];
      var filas = Array.prototype.slice.call(cuerpo.rows);
      var asc = tabla.dataset.orden !== String(i) || tabla.dataset.dir === 'desc';
      var numerico = filas.every(function(f){
        var t = (f.cells[i] ? f.cells[i].textContent : '').replace(/[^\d,.-]/g, '');
        return t === '' || !isNaN(parseFloat(t.replace(/\./g,'').replace(',','.')));
      });
      filas.sort(function(a, b){
        var x = a.cells[i] ? a.cells[i].textContent.trim() : '';
        var y = b.cells[i] ? b.cells[i].textContent.trim() : '';
        if (numerico){
          var nx = parseFloat(x.replace(/[^\d,.-]/g,'').replace(/\./g,'').replace(',','.')) || 0;
          var ny = parseFloat(y.replace(/[^\d,.-]/g,'').replace(/\./g,'').replace(',','.')) || 0;
          return asc ? nx - ny : ny - nx;
        }
        return asc ? x.localeCompare(y, 'es') : y.localeCompare(x, 'es');
      });
      filas.forEach(function(f){ cuerpo.appendChild(f); });
      tabla.dataset.orden = i;
      tabla.dataset.dir = asc ? 'asc' : 'desc';
    });
  });

  var bc = document.getElementById('b-csv');
  if (bc) bc.addEventListener('click', function(){
    var det = document.querySelector('table.detalle');
    if (!det) return;
    var lineas = [];
    var cab = Array.prototype.slice.call(det.tHead.rows[0].cells)
      .map(function(c){ return c.textContent.trim(); }).filter(function(c){ return c !== ''; });
    lineas.push(cab);
    det.querySelectorAll('tbody tr').forEach(function(tr){
      if (tr.classList.contains('oculta')) return;
      var f = Array.prototype.slice.call(tr.cells).map(function(c){
        return c.textContent.trim(); });
      f.splice(7, 1);                       // la columna de marcas no va al CSV
      lineas.push(f);
    });
    var csv = lineas.map(function(f){
      return f.map(function(v){ return '"' + String(v).replace(/"/g, '""') + '"'; }).join(',');
    }).join('\r\n');
    // BOM: sin el, Excel en espanol se come las tildes (H-D59).
    var blob = new Blob(['﻿' + csv], {type:'text/csv;charset=utf-8;'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = D.archivo_csv;
    a.click();
    URL.revokeObjectURL(a.href);
  });

  var bp = document.getElementById('b-imprimir');
  if (bp) bp.addEventListener('click', function(){ window.print(); });

  aplicar();
})();
"""


def _controles(d: InformeDatos) -> str:
    """La barra de H-D55. Solo existe en el HTML."""
    personas = [f'<button class="btn persona activo" data-persona-btn="">Equipo</button>']
    for p in d.personas:
        personas.append(f'<button class="btn persona" data-persona-btn="{esc(p.user_name)}">'
                        f"{esc(p.user_name)}</button>")
    clientes = "".join(f'<option value="{esc(c.name)}">{esc(c.name)}</option>'
                       for c in d.por_cliente)
    proyectos = "".join(f'<option value="{esc(p.project_name)}">{esc(p.project_name)}</option>'
                        for p in d.proyectos)
    return (
        '<div class="controles"><div class="fila">'
        + "".join(personas)
        + '<label for="f-cliente">Cliente</label>'
        f'<select id="f-cliente"><option value="">Todos</option>{clientes}</select>'
        '<label for="f-proyecto">Proyecto</label>'
        f'<select id="f-proyecto"><option value="">Todos</option>{proyectos}</select>'
        '<label><input type="checkbox" id="f-facturable"> Solo facturables</label>'
        '<input type="search" id="f-busqueda" placeholder="Buscar en el detalle…">'
        '<button class="btn sec" id="b-csv">Descargar CSV</button>'
        '<button class="btn sec" id="b-imprimir">Imprimir</button>'
        "</div></div>")


# ===================== LAS DOS SALIDAS =====================

def documento_html(d: InformeDatos, secciones: Optional[Sequence[str]] = None) -> str:
    """El HTML interactivo y **autocontenido**: ni una petición a la red (H-D55)."""
    elegidas = list(secciones) if secciones else list(CLAVES)
    datos_js = json.dumps({"archivo_csv": nombre_archivo(d, "csv")})
    aviso = ('<p class="nota" id="aviso-filtro" style="display:none">'
             "Vista filtrada. Las secciones que dependen de la jornada o de las "
             "estimaciones enseñan solo las filas que coinciden; no se recalculan."
             "</p>")
    return (
        "<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(nombre_archivo(d, 'html'))}</title>"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>{_BASE_CSS}{_WEB_CSS}</style></head><body>"
        + _controles(d)
        + '<div class="hoja">'
        + _encabezado(d) + aviso
        + _secciones(d, elegidas, para_pdf=False)
        + "</div>"
        f"<script>window.__INFORME__={datos_js};</script>"
        f"<script>{_JS}</script>"
        "</body></html>")


def documento_pdf_html(d: InformeDatos, secciones: Optional[Sequence[str]] = None) -> str:
    """El HTML de impresión, **todo en vertical** (H-D69).

    Ya no hay selector de orientación: la única sección que giraba la hoja era
    «Horas día a día», y salió del informe en H-D68. Sin ella no hay nada que
    girar, así que la `@page` con nombre también se retiró.

    H-D58: el detalle **no entra por defecto**; si viene en `secciones`, entra.
    """
    elegidas = list(secciones) if secciones is not None else [c for c in CLAVES
                                                             if c != "detalle"]
    css = _PDF_CSS
    return (
        "<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        f"<style>{_BASE_CSS}{css}</style></head><body>"
        + _encabezado(d)
        + _secciones(d, elegidas, para_pdf=True)
        + "</body></html>")


def csv_detalle(d: InformeDatos) -> bytes:
    """H-D59: solo el detalle, con encabezados, coma y **UTF-8 con BOM**.

    El BOM no es un capricho: sin él, Excel en español abre el archivo en su
    página de códigos y las tildes salen rotas.
    """
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(["Día", "Persona", "Cliente", "Proyecto", "Actividad", "Horas",
                "¿Se cobra?", "¿Extra?", "¿Desfase?", "Observaciones"])
    for r in d.detalle:
        w.writerow([
            r.date.isoformat(), r.user_name, r.client_name, r.project_name,
            r.activity_name, num(r.hours),
            "Sí" if r.billable else "No",
            "Sí" if r.overtime else "No",
            "Sí" if r.over_estimate else "No",
            (r.notes or ""),
        ])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
