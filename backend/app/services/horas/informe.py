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
from app.services.horas import fuentes, graficas

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
    # ETAPA D1 (D-D7): la tabla va dentro de una tarjeta —borde fino y esquinas
    # redondeadas— que le cierra el borde de abajo y la separa de la siguiente.
    # La tarjeta es SOLO de pantalla: en el PDF una caja con borde que cruza de
    # página se dibuja partida, y el papel ya separa con el salto de hoja.
    return (f'<div class="card"><table class="{clase}">'
            f"<thead><tr>{''.join(ths)}</tr></thead>"
            f"<tbody>{cuerpo}</tbody></table></div>")


def _barra_pct(valor, pasada_de: float = 0) -> str:
    """Un porcentaje con su barra al lado (ETAPA D1, D-D6).

    Los dos en la MISMA celda, como en la referencia: la barra se lee de un
    vistazo y la cifra está ahí para quien necesite el número exacto. Con
    `pasada_de`, lo que supere ese umbral se pinta en naranja —es el caso de la
    ocupación por encima del 100 %—.

    Todo con `inline-block`: ni flex ni grid (regla 11).
    """
    v = float(valor or 0)
    clase = "barra pasada" if pasada_de and v > pasada_de else "barra"
    return (f'<span class="pct"><span class="{clase}">'
            f'<i class="barra-relleno" style="width:{min(v, 100):.1f}%"></i>'
            f"</span> {pct(valor)}</span>")


def _celdas(valores: Sequence[str], alineadas: Sequence[int] = ()) -> str:
    return "".join(
        f'<td class="num">{v}</td>' if i in alineadas else f"<td>{v}</td>"
        for i, v in enumerate(valores))


def _indicador(etiqueta: str, valor: str, clave: str = "", unidad: str = "",
               pie: str = "", tono: str = "") -> str:
    """Una casilla del resumen (ETAPA D1, D-D3).

    Tres piezas, de arriba abajo: el **rótulo** pequeño, la **cifra grande y de
    su color**, y debajo una **línea en gris con el desglose**. La unidad va
    dentro de la cifra pero en pequeño y en gris, para que el número se lea de
    lejos y no compita con la «h» o el «%».

    Sigue en tabla y no en rejilla: la rama de impresión lo exige (regla 11) y
    usar la misma estructura en las dos evita mantener dos maquetas.
    """
    ident = f' id="ind-{clave}"' if clave else ""
    uni = f'<small class="ind-uni">{esc(unidad)}</small>' if unidad else ""
    sub = f'<span class="ind-pie">{esc(pie)}</span>' if pie else ""
    clase = f"ind {tono}".strip()
    return (f'<td class="{clase}"><span class="ind-et">{esc(etiqueta)}</span>'
            f'<span class="ind-val"><span class="ind-num"{ident}>{valor}</span>'
            f"{uni}</span>{sub}</td>")


# ===================== LAS SECCIONES =====================

def _sec_resumen(d: InformeDatos, para_pdf: bool = False) -> str:
    r = d.resumen
    # ETAPA D1 (D-D3): los seis indicadores son los de siempre y sus cifras son
    # las de siempre. Lo que cambia es que cada uno lleva su color y, debajo, una
    # línea que dice de dónde sale el número. Los pies NO traen dato nuevo: se
    # arman con campos que el resumen ya calcula.
    extra = float(r.overtime_hours or 0)
    casillas = [
        # El desglose de esta cifra son las dos casillas de al lado, así que
        # repetirlo aquí sobraba: el pie dice de cuántos registros sale.
        _indicador("Horas registradas", num(r.total_hours), "total", "h",
                   f"en {num(r.entries_count, 0)} registros del periodo"),
        _indicador("Ordinarias", num(r.ordinary_hours), "ord", "h",
                   f"sobre una jornada de {horas(r.expected_hours)}"),
        _indicador("Horas extra", num(r.overtime_hours), "extra", "h",
                   "ninguna en el periodo" if extra <= 0 else "por encima de la jornada",
                   tono="" if extra <= 0 else "caliente"),
        _indicador("Facturables", num(r.billable_hours), "fact", "h",
                   "las que se cargan a una cuenta de cliente", tono="factura"),
        _indicador("% facturable", num(r.billable_pct, 1), "pctfact", "%",
                   f"{horas(r.billable_hours)} de {horas(r.total_hours)}", tono="factura"),
        _indicador("Días sin registrar", num(r.pending_days, 0), "pend", "",
                   f"entre {num(r.people_count, 0)} persona(s)",
                   tono="" if not r.pending_days else "pendiente"),
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
                       # La ocupación pasada del 100 % se pinta en naranja: es
                       # más jornada de la que tocaba, y eso se ve, no se busca.
                       _barra_pct(p.occupancy_pct, pasada_de=100),
                       num(p.pending_days, 0)],
                      alineadas=(1, 2, 3, 4, 5, 6))
            + "</tr>")
    # ETAPA D1 (D-D6): encima de la tabla, y dibujando DOS DE SUS COLUMNAS —las
    # horas registradas y las facturables—, no un dato de fuera. La tabla se
    # queda entera debajo.
    return (graficas.facturable_por_persona(d.personas, horas, para_pdf)
            + _tabla(["Persona", "Jornada", "Ordinarias", "Extra", "Facturables",
                      "Ocupación", "Días sin registrar"], filas,
                     alineadas=(1, 2, 3, 4, 5, 6), ordenable=True))


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
        # ETAPA D1 (D-D6): la barra y su porcentaje van en la MISMA celda, como
        # en la referencia. Antes la barra tenía columna propia, con la cabecera
        # vacía.
        filas.append(
            f'<tr data-cliente="{esc(x.name)}">'
            + _celdas([esc(x.name), horas(x.hours), _barra_pct(x.pct)],
                      alineadas=(1, 2))
            + "</tr>")
    return _tabla([titulo_col, "Horas", "%"], filas, alineadas=(1, 2), ordenable=True)


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

    # ETAPA D1 (D-D6): la leyenda nombra TODOS los colores. Faltaba el estado
    # `vacio` —un día laborable que todavía no ha llegado—, que sale en blanco:
    # sin su entrada, el lector no tenía forma de saber qué era una casilla
    # vacía, y es justo la que más se ve en un informe a mitad de mes.
    leyenda = ('<p class="nota leyenda">'
               '<span class="mini trabajado"></span> trabajado '
               '<span class="mini incompleto"></span> incompleto '
               '<span class="mini festivo"></span> festivo '
               '<span class="mini ausencia"></span> ausencia '
               '<span class="mini finde"></span> fin de semana '
               '<span class="mini vacio"></span> aún no ha llegado</p>')
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


# ===================== LOS PÁRRAFOS DE SECCIÓN (ETAPA D1, D-D4) =====================
#
# Debajo de cada título, antes de la tabla, un párrafo corto que dice QUÉ SE ESTÁ
# MIRANDO Y POR QUÉ IMPORTA. Es lo que más separa un informe de un listado de
# tablas, y es lo que le faltaba a este.
#
# Son **texto fijo, escrito una vez y sin IA**. Interpolan cifras del propio
# informe, nunca datos nuevos. Tres reglas al escribirlos:
#
#   1. de una a tres líneas, en español llano y sin markdown;
#   2. no repiten la tabla: explican el término que el lector no tiene por qué
#      saber —qué es una hora facturable, qué mide la ocupación—;
#   3. **avisan de lo que el dato NO dice**, que es lo que convierte una tabla en
#      un informe. Si una cifra se puede leer mal, se dice aquí.

def _intro_resumen(d: InformeDatos) -> str:
    r = d.resumen
    if r.pending_days:
        pista = (f" Los {num(r.pending_days, 0)} días sin registrar son la pista "
                 f"de cuántas pueden faltar.")
    else:
        pista = " En el periodo no quedó ningún día sin registrar."
    return ("Lo que el equipo apuntó en el periodo y cuánto de ello se carga a una "
            "cuenta de cliente. Mide el registro, no el esfuerzo: las horas que "
            "nadie apuntó no están en ninguna de estas cifras." + pista)


def _intro_personas(d: InformeDatos) -> str:
    cap = d.capacidad
    return ("Cuánto registró cada persona frente a la jornada que le correspondía "
            "hasta hoy, y la ocupación que sale de comparar esas dos columnas. Un "
            "porcentaje bajo puede ser trabajo sin apuntar y no tiempo libre: la "
            "última columna es la que lo dice. La jornada de aquí llega solo hasta "
            f"hoy; la capacidad del periodo completo —{horas(cap.hours_per_analyst)} "
            "por analista— está en la portada, y son cifras distintas a propósito.")


def _intro_facturacion(d: InformeDatos) -> str:
    return ("El dato que ordena el informe. Una hora facturable está cargada a una "
            "cuenta abierta del cliente; una no facturable es trabajo igual de real "
            "que no tiene dónde cargarse, casi siempre porque el proyecto todavía no "
            "tiene código. El porcentaje dice dónde se apuntó la hora, no si el "
            "trabajo valió la pena.")


def _intro_clientes(d: InformeDatos) -> str:
    return ("En qué clientes se repartió el tiempo del periodo. El porcentaje es "
            "sobre el total registrado, lo facturable y lo que no, todo junto: un "
            "cliente puede ocupar mucho sitio en esta tabla sin haber dejado ni una "
            "hora facturable, y la sección anterior es la que lo cuenta.")


def _intro_actividades(d: InformeDatos) -> str:
    return ("El reparto por la actividad que cada persona eligió al registrar. Dice "
            "en qué se ocupó el tiempo, no cuánto rindió: una hora de preparación y "
            "una de ejecución pesan lo mismo aquí.")


def _intro_proyectos(d: InformeDatos) -> str:
    return ("Los proyectos que tuvieron horas en el periodo, y cuánto llevan "
            "gastado frente a lo estimado. Las dos columnas de horas no miden lo "
            "mismo: en el periodo son las de estas fechas, y consumidas es todo lo "
            "que lleva el proyecto desde que se abrió, que es contra lo que se mide "
            "el desfase. Un proyecto sin estimación sale igual, pero su estado no "
            "significa nada.")


def _intro_mapa(d: InformeDatos) -> str:
    return ("Día a día, quién registró y quién no. El color dice en qué estado quedó "
            "cada día y la leyenda de abajo los nombra uno a uno; las horas exactas "
            "están en el detalle. Un día en ámbar tiene horas apuntadas, solo que "
            "menos de su jornada, y los días que todavía no han llegado salen en "
            "blanco y no se reclaman.")


def _intro_detalle(d: InformeDatos) -> str:
    return (f"Los {num(d.detalle_total, 0)} registros del periodo, uno por fila. Se "
            "puede filtrar, ordenar por cualquier columna y descargar en CSV lo que "
            "quede a la vista. Es la única parte del informe donde se lee lo que "
            "cada persona escribió en las observaciones.")


_INTROS = {
    "resumen": _intro_resumen,
    "personas": _intro_personas,
    "facturacion": _intro_facturacion,
    "clientes": _intro_clientes,
    "actividades": _intro_actividades,
    "proyectos": _intro_proyectos,
    "mapa": _intro_mapa,
    "detalle": _intro_detalle,
}


_CONSTRUCTORES = {
    "resumen": _sec_resumen,
    "personas": _sec_personas,
    "facturacion": _sec_facturacion,
    "clientes": lambda d, p=False: _sec_reparto(d.por_cliente, "Cliente"),
    # ETAPA D1 (D-D6): la gráfica va ENCIMA de la tabla, no en su lugar.
    "actividades": lambda d, p=False: (
        graficas.horas_por_actividad(d.por_actividad, horas, p)
        + _sec_reparto(d.por_actividad, "Actividad")),
    "proyectos": _sec_proyectos,
    "mapa": _sec_mapa,
    "detalle": _sec_detalle,
}


def _secciones(d: InformeDatos, elegidas: Sequence[str], para_pdf: bool) -> str:
    """El cuerpo del documento. **El mismo para las dos ramas** (H-D50)."""
    partes = []
    for clave, titulo in SECCIONES:
        if clave not in elegidas:
            continue
        # H-D69: el PDF va todo en vertical. La única sección que obligaba a
        # girar la hoja era «Horas día a día», y ya no está.
        clases = "seccion"
        # ETAPA D1 (D-D5): fuera el cuadro numerado y el subrayado naranja. El
        # título va grande y en azul, y debajo su párrafo (D-D4).
        intro = _INTROS.get(clave)
        cab = (f'<div class="sec-cab"><h2>{esc(titulo)}</h2>'
               + (f'<p class="sec-intro">{esc(intro(d))}</p>' if intro else "")
               + "</div>")
        partes.append(
            f'<section class="{clases}" id="sec-{clave}">{cab}'
            f'{_CONSTRUCTORES[clave](d, para_pdf)}</section>')
    return "".join(partes)


def _encabezado(d: InformeDatos) -> str:
    """La portada. Contenido de H7 (H-D73), diseño de la ETAPA D1 (D-D2).

    De arriba abajo, **sobre un bloque azul marino a sangre**: el logo con
    «Centro de Excelencia · Performance» al lado y la fecha de generación a la
    derecha; el título grande **con el periodo dentro, en amarillo**; y una fila
    con los cuatro datos —**Dirigido a**, **Período**, **Equipo** y **Capacidad
    base**—, cada uno con su rótulo pequeño arriba y su valor debajo. Cierra el
    bloque una banda de tres tramos: azul, naranja y amarillo.

    **El contenido es el mismo que aprobó Fredy** (D-D8): cambia dónde vive cada
    dato y cómo se ve, no qué dice. La capacidad base sube a la misma fila que
    los otros tres en vez de ir en una segunda fila a lo ancho.

    Todo en tablas: la misma estructura sirve para la pantalla y para el PDF, y
    la rama de impresión no admite `flex` ni `grid` (regla 11).
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

    # ETAPA D1 (D-D2): el bloque azul marino a sangre, el título con el período
    # DENTRO en amarillo, y los cuatro datos en una sola fila. La banda de tres
    # tramos cierra el bloque por abajo. Todo en tablas: la rama de impresión no
    # admite ni `flex` ni `grid` (regla 11) y así las dos salidas comparten
    # estructura.
    return (
        f'<header class="cabecera">'
        f'<div class="portada-fondo">'
        f'<table class="cab"><tr>'
        f'<td class="cab-logo">{marca}</td>'
        f'<td class="cab-coe">Centro de Excelencia<span class="coe-sep"> · </span>'
        f'<strong>Performance</strong></td>'
        f'<td class="cab-der">Generado el {fecha_larga(d.generado.date())}</td>'
        f"</tr></table>"
        f'<div class="titulo">'
        f'<h1>Informe de horas <em>{esc(d.filtros.periodo)}</em></h1>'
        f"</div>"
        f'<table class="portada"><tr>'
        + dato("Dirigido a", esc(d.filtros.dirigido_a) or "—")
        + dato("Período", esc(d.filtros.periodo))
        + dato("Equipo", equipo)
        + dato("Capacidad base", capacidad)
        + "</tr></table>"
        f"</div>"
        f'<div class="banda"><span class="b-azul"></span>'
        f'<span class="b-naranja"></span><span class="b-amarillo"></span></div>'
        f"{extra}</header>")


# ===================== LOS ESTILOS =====================

_BASE_CSS = """
/* ===== LA PALETA (ETAPA D1, decisión B) =====
   Sustituye a la de H-D73, que era provisional. Los valores están MEDIDOS del
   informe de referencia que aprobó Fredy y escritos en
   `docs/diseno-informe-horas.md`: si hay que cambiar uno, se cambia allí
   primero. Son variables y no literales para que no queden dos paletas
   conviviendo en el documento. */
:root{
  --dark:#060B29;        /* el bloque de la portada y el pie */
  --navy:#03287D;        /* títulos y cifras */
  --azul:#0032A7;        /* lo facturable, el primer tramo de la banda */
  --naranja:#FCA311;     /* lo que se pasa de la jornada, el segundo tramo */
  --amarillo:#FFC440;    /* el período dentro del título, el tercer tramo */
  --sinreg:#8E44AD;      /* lo que falta por registrar */
  --bg:#F2F5FA; --superficie:#FFFFFF; --linea:#DCE3EF;
  --tinta:#0E1730; --apagado:#5C6B8A;
  --fondo-suave:#F7F9FD; --separador:#EDF1F8; --canal:#E4EAF5;
  /* Los tres que solo viven sobre el fondo oscuro. */
  --rotulo-oscuro:#8497C0; --unidad-oscuro:#9FB0D4; --linea-oscura:#1E2A4E;
  /* Las dos familias (decisión A). La pila de respaldo es la de antes, por si
     faltara un `.woff2`: el documento se ve peor, pero se ve. */
  --titular:'Exo 2','Segoe UI',system-ui,sans-serif;
  --texto:'Montserrat','Segoe UI',system-ui,-apple-system,sans-serif;
}
*{box-sizing:border-box}
body{font-family:var(--texto);color:var(--tinta);margin:0}
h1{font-family:var(--titular);font-weight:800;font-size:26pt;color:var(--navy);
   margin:0 0 2mm}
/* ETAPA D1 (D-D5): el título va grande y en azul. Fuera el cuadro numerado y el
   subrayado naranja: numeraban ocho secciones que ya se leen en orden, y el
   subrayado partía la sección justo donde tiene que respirar. */
h2{font-family:var(--titular);font-weight:600;font-size:15pt;color:var(--navy);
   margin:0 0 1.5mm;letter-spacing:-.2pt}
/* El párrafo de sección (D-D4): dice qué se está mirando y por qué importa. */
.sec-cab{margin-bottom:4mm;max-width:76ch}
.sec-intro{font-size:9pt;color:var(--apagado);margin:0;line-height:1.5}
.sub{font-size:13pt;color:var(--apagado);margin:0 0 1mm}
.filtros{font-size:10pt;color:var(--apagado);margin:2mm 0 0}
/* ===== LA PORTADA (contenido H-D73, diseño D-D2) =====
   Un bloque azul marino a sangre. Dentro, de arriba abajo: el logo con la
   unidad al lado y la fecha a la derecha; el título con el período DENTRO, en
   amarillo; y los cuatro datos en una fila. Cierra por abajo la banda de tres
   tramos. Todo en tablas (regla 11). */
.cabecera{margin-bottom:7mm}
.portada-fondo{background:var(--dark);color:#fff;padding:8mm 8mm 2mm}
.cab{width:100%;margin-bottom:6mm}
/* `width:1%` encoge la columna del logo a lo que ocupa la imagen: con un ancho
   fijo se comía el sitio y la fecha de la derecha partía en dos líneas. */
.cab-logo{width:1%;padding-right:7mm;vertical-align:middle}
.cab-coe{font-size:10pt;color:var(--unidad-oscuro);vertical-align:middle;
         letter-spacing:.3pt}
.cab-coe strong{color:var(--amarillo)}
.coe-sep{color:var(--amarillo);font-weight:700}
.cab-der{text-align:right;font-size:8.5pt;color:var(--rotulo-oscuro);
         vertical-align:middle;white-space:nowrap}
.logo{height:18mm}
.marca{font-family:var(--titular);font-size:22pt;color:#fff;letter-spacing:.5pt;
       font-weight:800}
.marca b{color:var(--amarillo)}
.titulo h1{font-size:30pt;color:#fff;margin:0;letter-spacing:-.5pt;line-height:1.05}
.titulo h1 em{font-style:normal;color:var(--amarillo);display:block}
.portada{width:100%;border-top:.5pt solid var(--linea-oscura);margin-top:6mm}
.portada td.dato{width:25%;padding:4mm 4mm 4mm 0;vertical-align:top}
.dato-rot{display:block;font-size:8pt;color:var(--rotulo-oscuro);margin-bottom:1mm}
.dato-val{display:block;font-size:10pt;color:#fff;font-weight:600}
/* La banda: tres tramos en tres spans y no en un degradado, que WeasyPrint
   dibuja de forma desigual. El reparto es el de la referencia. */
.banda{height:1.8mm;font-size:0;width:100%;margin-bottom:6mm}
.banda span{display:inline-block;height:1.8mm}
.b-azul{background:var(--azul);width:62%}
.b-naranja{background:var(--naranja);width:26%}
.b-amarillo{background:var(--amarillo);width:12%}
table{border-collapse:collapse;width:100%}
/* ETAPA D1 (D-D7): la cabecera sale de las versalitas. A 8,5 pt, en mayúsculas
   se lee peor y ocupa más, y la referencia la tiene en caja normal. Igual en
   pantalla y en papel: no hay razón para que difieran. */
th{background:var(--fondo-suave);color:var(--apagado);font-size:8.5pt;
   font-weight:600;text-align:left;padding:2.4mm 2mm;
   border-bottom:1pt solid var(--linea)}
td{padding:1.8mm 2mm;border-bottom:.5pt solid var(--separador);font-size:9.5pt}
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
/* ===== LOS INDICADORES (D-D3) =====
   Rótulo pequeño arriba, cifra grande y de su color, y debajo una línea en gris
   con el desglose. La unidad va dentro de la cifra, en pequeño y en gris, para
   que el número se lea de lejos y no compita con la «h» o el «%». */
.indicadores td.ind{width:33.33%;border:.5pt solid var(--linea);padding:4mm;
                    background:var(--superficie);vertical-align:top}
.ind-et{display:block;font-size:8pt;color:var(--apagado);font-weight:600;
        line-height:1.3;margin-bottom:2mm}
.ind-val{display:block;font-family:var(--titular);font-weight:800;font-size:22pt;
         color:var(--navy);line-height:1;letter-spacing:-.4pt}
.ind-num{font-variant-numeric:tabular-nums}
.ind-uni{font-family:var(--texto);font-size:10pt;font-weight:600;
         color:var(--apagado);letter-spacing:0;margin-left:.8mm}
.ind-pie{display:block;font-size:8pt;color:var(--apagado);margin-top:2mm;
         line-height:1.4}
.ind.factura .ind-val{color:var(--azul)}
.ind.caliente .ind-val{color:var(--naranja)}
.ind.pendiente .ind-val{color:var(--sinreg)}
.nota{font-size:9pt;color:var(--apagado);margin:2mm 0 0}
.vacio{font-size:10pt;color:var(--apagado);padding:4mm 0;margin:0}
/* La barra y su porcentaje, en la misma celda (D-D6). Todo `inline-block`:
   la rama de impresión no admite flex (regla 11). */
.pct{white-space:nowrap}
.barra{display:inline-block;vertical-align:middle;width:16mm;height:1.6mm;
       background:var(--canal);border-radius:.8mm;overflow:hidden;margin-right:1.8mm}
.barra-relleno{display:block;background:var(--azul);height:100%}
.barra.pasada .barra-relleno{background:var(--naranja)}
/* ===== LAS GRÁFICAS (D-D6) =====
   El SVG lo escribe `graficas.py` y se estira al ancho de su caja. La leyenda
   es HTML y no SVG, para que pueda partir en varias líneas si hace falta. */
.grafica{margin:0 0 5mm}
.svg-barras{width:100%;height:auto;display:block}
.leyenda-grafica{font-size:8pt;color:var(--apagado);margin:2.5mm 0 0;
                 border-top:.5pt solid var(--separador);padding-top:2mm}
.clave{display:inline-block;margin-right:6mm;white-space:nowrap}
.clave b{color:var(--tinta);font-weight:700}
.sw{display:inline-block;width:2.6mm;height:2.6mm;border-radius:.5mm;
    vertical-align:middle;margin-right:1.6mm}
.mapa th.dia,.diaria th.dia{text-align:center;padding:1mm .4mm;font-size:8pt}
.dsem{display:block;color:var(--apagado)}
.dnum{display:block;font-weight:700}
.mapa td.casilla,.diaria td.celda{text-align:center;font-size:8pt;padding:1mm .4mm;
                                  font-variant-numeric:tabular-nums}
td.casilla.trabajado{background:#dcfce7}
td.casilla.incompleto{background:#fef3c7}
td.casilla.festivo{background:#e0e7ff}
td.casilla.ausencia{background:#f3e8ff}
td.casilla.finde{background:#f3f4f6}
.mini{display:inline-block;width:3.5mm;height:3.5mm;vertical-align:middle;
      border:.5pt solid var(--linea);margin:0 1mm 0 3mm}
.mini.trabajado{background:#dcfce7}.mini.incompleto{background:#fef3c7}
.mini.festivo{background:#e0e7ff}.mini.ausencia{background:#f3e8ff}
.mini.vacio{background:#fff}
.mini.finde{background:#f3f4f6}
"""

_PDF_CSS = """
@page{size:A4 portrait;margin:14mm 12mm 16mm;
      @bottom-right{content:"Página " counter(page) " de " counter(pages);
                    font-size:8pt;color:var(--apagado)}}
/* ===== LA PORTADA A SANGRE (ETAPA D1.4, D-D2 · D-D9) =====
   `@page :first{margin:0}` es la única forma fiable de que un fondo de color
   llegue al borde del papel; es la misma que usa el informe de análisis
   (CLAUDE.md §15). Como deja SIN MÁRGENES la primera hoja entera, la portada
   tiene que ocuparla toda: por eso lleva alto fijo y salto de página detrás.
   Una portada de color que se queda a 12 mm del borde parece un fallo de
   impresión, no un diseño.

   Las medidas suman 296 de los 297 mm del A4. El milímetro que sobra es a
   propósito: con 297 exactos, un redondeo de nada empuja la banda a la hoja
   siguiente y sale una página en blanco. */
/* Sin márgenes no hay caja de margen, pero el número de página se sigue
   dibujando y cae encima de la banda. En la portada no pinta nada. */
@page:first{margin:0;@bottom-right{content:none}}
.cabecera{page-break-after:always;margin:0}
.portada-fondo{height:289mm;padding:22mm 16mm 0}
.banda,.banda span{height:7mm}
/* En una hoja entera el título puede respirar: baja hasta pasada la mitad y
   sube de cuerpo. La fila de datos lo sigue, y debajo queda el azul hasta la
   banda. */
.titulo{padding-top:78mm}
.titulo h1{font-size:40pt}
.portada td.dato{padding:5mm 4mm 5mm 0}
.dato-rot{font-size:9pt}
.dato-val{font-size:11pt}
body{font-size:9.5pt}
.seccion{margin-bottom:7mm}
/* Que ninguna tabla se corte a media fila. */
tr{page-break-inside:avoid}
thead{display:table-header-group}
h2{page-break-after:avoid}
/* ETAPA D1: la gráfica no se parte entre hojas, y el título con su párrafo no
   se quedan solos al final de una. */
.grafica{page-break-inside:avoid}
.sec-cab{page-break-after:avoid;page-break-inside:avoid}
/* Ningun texto por debajo de 8 pt: en papel, menos de eso no se lee. */
.diaria td.celda,.diaria th.dia{font-size:8pt;padding:.8mm .3mm}
/* El mapa, en el PDF, habla por color: con 31 columnas en vertical, meter la
   cifra obligaria a bajar de 8 pt, y la leyenda ya dice lo que significa cada uno. */
.mapa td.casilla{font-size:8pt}
"""

_WEB_CSS = """
/* ===== LA RAMA DE PANTALLA (ETAPA D1) =====
   Hasta aquí, `_BASE_CSS` es una hoja de IMPRESIÓN: todo en `pt` y en `mm`. La
   pantalla la heredaba entera, y por eso el informe salía con cuerpo de 12,7 px
   y celdas de 6,8 px de alto. Este bloque le da a la pantalla su propia
   tipografía y su propio aire, en `px`, con los valores medidos de la
   referencia (`docs/diseno-informe-horas.md`). El papel no se entera. */
body{background:var(--bg);padding:0 0 40px;font-size:13.5px;line-height:1.55;
     -webkit-font-smoothing:antialiased}
.hoja{max-width:1240px;margin:0 auto;background:var(--superficie);padding:0 0 30px;
      box-shadow:0 1px 3px rgba(6,11,41,.08)}
/* La portada va a sangre: ocupa la hoja de borde a borde, y es el cuerpo el que
   lleva el margen lateral. */
.cuerpo{padding:0 40px}
.seccion{margin-bottom:34px}
h1{font-size:44px;margin:0 0 16px}
/* --- El título de sección y su párrafo (D-D5, D-D4) --- */
h2{font-size:22px;margin:0 0 6px;letter-spacing:-.01em}
.sec-cab{margin-bottom:22px}
.sec-intro{font-size:13.5px;line-height:1.6}
/* --- Las tablas respiran (D-D7) --- */
/* La cabecera deja las mayúsculas: a 11,5 px con versalitas se lee peor que en
   caja normal, y la referencia la tiene normal. */
.card{border:1px solid var(--linea);border-radius:10px;overflow:hidden;
      background:var(--superficie)}
table{font-size:13.5px}
th{font-size:11.5px;padding:12px 14px;
   border-bottom:1px solid var(--linea)}
td{padding:13px 14px;border-bottom:1px solid var(--separador)}
tbody tr:last-child td{border-bottom:0}
tbody td:first-child{font-weight:600}
/* --- Las gráficas (D-D6) --- */
.grafica{margin:0 0 22px}
.leyenda-grafica{font-size:12px;margin:16px 0 0;padding-top:15px;
                 border-top:1px solid var(--separador)}
.clave{margin-right:18px}
.sw{width:11px;height:11px;border-radius:2px;margin-right:7px}
/* --- La portada (D-D2) --- */
.cabecera{margin:0 0 30px}
.portada-fondo{padding:38px 40px 0}
.cab{margin-bottom:26px}
.cab-logo{width:1%;padding-right:22px}
.logo{height:44px}
.marca{font-size:26px;letter-spacing:.03em}
.cab-coe{font-size:12.5px;letter-spacing:0;padding-left:14px;
         border-left:1px solid #33406B}
.cab-der{font-size:12px}
.titulo h1{font-size:44px;letter-spacing:-.015em;max-width:20ch}
.portada{margin-top:26px}
.portada td.dato{padding:22px 34px 34px 0}
.dato-rot{font-size:11.5px;margin-bottom:3px}
.dato-val{font-size:14px}
.banda{height:5px;margin-bottom:0}
.banda span{height:5px}
/* --- Los indicadores (D-D3) --- */
/* El fondo de la tabla asoma por el `border-spacing`: eso es la línea de 2 px
   que separa las casillas en la referencia, sin pintar seis bordes. */
.indicadores{border-collapse:separate;border-spacing:2px;background:var(--linea);
             border:2px solid var(--linea);border-radius:10px}
.indicadores td.ind{padding:20px;border:0}
.ind-et{font-size:11.5px;line-height:1.35;margin-bottom:9px;min-height:30px}
.ind-val{font-size:32px;letter-spacing:-.02em}
.ind-uni{font-size:13px;margin-left:3px}
.ind-pie{font-size:11.5px;margin-top:8px}
.nota{font-size:12px;line-height:1.6;margin:10px 0 0}
.filtros{font-size:12px;margin:14px 0 0}
.vacio{font-size:13.5px;padding:16px 0}
/* --- La barra dentro de la celda (D-D6) --- */
.barra{width:48px;height:6px;border-radius:3px;margin-right:8px}
.mini{width:13px;height:13px;border:1px solid var(--linea);margin:0 4px 0 12px}
/* --- La barra de controles --- */
/* Clara, como en la referencia: con la portada oscura debajo, una barra oscura
   se fundía con ella y no se veía dónde empezaba el documento. */
.controles{position:sticky;top:0;z-index:5;background:var(--superficie);
           color:var(--tinta);padding:13px 34px;
           border-bottom:1px solid var(--linea);box-shadow:0 1px 0 rgba(6,11,41,.04)}
.controles .fila{max-width:1240px;margin:0 auto;display:flex;flex-wrap:wrap;
                 gap:10px;align-items:center}
.controles label{font-size:11.5px;color:var(--apagado);font-weight:600}
.controles select,.controles input[type=search]{font-family:var(--texto);
   padding:8px 11px;border-radius:7px;border:1px solid var(--linea);
   background:#fff;color:var(--tinta);font-size:12.5px;min-height:36px}
.controles select:focus,.controles input:focus{outline:2px solid var(--azul);
   outline-offset:-1px;border-color:var(--azul)}
.btn{font-family:var(--texto);padding:8px 14px;border-radius:7px;
     border:1px solid var(--linea);background:#fff;color:var(--navy);
     font-weight:600;font-size:12.5px;cursor:pointer;min-height:36px}
.btn:hover{border-color:var(--azul);background:#F5F8FF}
.btn:focus-visible{outline:2px solid var(--naranja);outline-offset:2px}
.btn.persona{background:#EDF1F8;border-color:#EDF1F8;color:var(--apagado)}
.btn.persona.activo{background:var(--navy);border-color:var(--navy);color:#fff}
th[data-col]{cursor:pointer;user-select:none}
th[data-col]:hover{color:var(--azul)}
th[data-col]::after{content:" \\2195";color:var(--apagado);font-size:9px}
tr.oculta{display:none}
.detalle td{font-size:13px}
@media print{.controles{display:none}
  .hoja{box-shadow:none;max-width:none;padding:0}
  .cuerpo{padding:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
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
    // ETAPA D1 (D-D3): la unidad ya no va en el texto de la cifra, va en su
    // propio <small> al lado. Aqui se escribe SOLO el numero.
    poner('ind-total', esp(t));
    poner('ind-ord', esp(t - extra));
    poner('ind-extra', esp(extra));
    poner('ind-fact', esp(fact));
    poner('ind-pctfact', t > 0 ? esp(fact / t * 100, 1) : '0');
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
             "estimaciones enseñan solo las filas que coinciden; no se recalculan. "
             "Las gráficas tampoco: están dibujadas en el servidor y siguen "
             "enseñando el periodo entero."
             "</p>")
    return (
        "<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(nombre_archivo(d, 'html'))}</title>"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>{fuentes.bloque_font_face()}{_BASE_CSS}{_WEB_CSS}</style>"
        "</head><body>"
        + _controles(d)
        + '<div class="hoja">'
        + _encabezado(d)
        + '<div class="cuerpo">' + aviso
        + _secciones(d, elegidas, para_pdf=False)
        + "</div></div>"
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
        f"<style>{fuentes.bloque_font_face()}{_BASE_CSS}{css}</style></head><body>"
        + _encabezado(d)
        + '<div class="cuerpo">'
        + _secciones(d, elegidas, para_pdf=True)
        + "</div></body></html>")


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
