"""Las gráficas del informe de horas (ETAPA D1, D-D6 · decisión C).

**SVG escrito aquí, en el servidor.** Sin biblioteca nueva y **sin una línea de
JavaScript**: así la misma gráfica sale igual en el HTML descargado sin red y en
el PDF, que es papel y no ejecuta nada. Es la razón por la que no se reusó el
enfoque de la referencia, que dibuja con JavaScript en el navegador.

**No calcula nada que el informe no tenga ya.** Recibe los valores hechos y los
textos ya formateados en español; aquí solo se decide dónde va cada rectángulo.

**El color nunca es lo único que distingue.** Cada tramo lleva su cifra dentro
—o al lado, si no cabe— y la leyenda nombra cada serie con su total. Un lector
que no distinga los dos azules sigue pudiendo leer la gráfica.

### Las dos escalas

Una misma gráfica tiene que ser legible en pantalla y en papel, y el mismo
`viewBox` no vale para las dos: el SVG se estira hasta el ancho de su caja, así
que una letra de 12 unidades son 13 px en pantalla y **5,9 pt** en el PDF, por
debajo del mínimo de 8 pt que manda la regla 17.

La solución es una sola geometría con un tamaño base distinto por rama. Todo
—altura de barra, huecos, canales— se mide en múltiplos de `base`, así que la
gráfica tiene la misma forma en las dos y solo cambia lo gruesa que es:

    pantalla  base=12  ->  12 x (1085/1000) px     ~= 13 px
    papel     base=17  ->  17 x (186/1000) mm      ~=  9 pt   (> 8 pt)

`ANCHO` es el ancho del `viewBox`, no del dibujo: el navegador y WeasyPrint lo
escalan hasta el ancho disponible.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from app.services.horas import fuentes

ANCHO = 1000            # unidades del viewBox; se escala al ancho de la caja
BASE_PANTALLA = 12      # ~13 px
BASE_PAPEL = 17         # ~9 pt, por encima del mínimo de 8 pt (regla 17)


def _esc(t) -> str:
    return (str(t if t is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _texto(x: float, y: float, s: str, tam: float, color: str,
           peso: int = 400, desde: str = "izq") -> str:
    """Un texto. `desde` dice a qué se refiere la `x`: al borde izquierdo, al
    derecho o al centro.

    **Nunca se emite `text-anchor`**: WeasyPrint recorta los descendentes de un
    `<text>` anclado a `end` —se pierden las colas de la «y», la «g» y la «p»—,
    así que la posición se calcula aquí, midiendo el texto con las métricas de
    la propia fuente, y el `<text>` sale siempre alineado a la izquierda.
    """
    if desde != "izq":
        ancho = fuentes.ancho_texto(s, tam, "Montserrat", peso)
        x = x - ancho if desde == "der" else x - ancho / 2
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{tam:.1f}" fill="{color}" '
            f'font-family="Montserrat,sans-serif" font-weight="{peso}">'
            f"{_esc(s)}</text>")


def barras(filas: Sequence[Dict], series: Sequence[Dict], para_pdf: bool = False,
           descripcion: str = "") -> str:
    """Barras horizontales, apiladas si hay más de una serie.

    `filas`   — `{"nombre": str, "valores": [float], "textos": [str], "total": str}`
    `series`  — `{"nombre": str, "color": str, "total": str}`

    Devuelve la figura entera: el SVG y su leyenda. Si no hay filas, devuelve
    una frase y no un dibujo vacío.
    """
    filas = [f for f in filas if sum(f["valores"]) > 0]
    if not filas:
        return '<p class="vacio">No hay horas que dibujar en el periodo.</p>'

    base = BASE_PAPEL if para_pdf else BASE_PANTALLA
    alto_barra = base * 2.1
    hueco = base * 0.75
    tam_nombre = base * 1.04

    def mide(s: str) -> float:
        return fuentes.ancho_texto(s, tam_nombre, "Montserrat", 600)

    # El canal de la izquierda se ajusta al nombre más largo, entre un mínimo y
    # un máximo: con nombres cortos no se desperdicia la mitad del ancho, y con
    # nombres de tres apellidos no hay que recortar si cabe. Pasado el máximo sí
    # se recorta, y el nombre entero sigue estando en la tabla de debajo.
    # Se mide con las métricas reales de la fuente, así que el recorte es el
    # justo: ni deja el nombre fuera del dibujo ni corta de más.
    ancho_mayor = max(mide(f["nombre"]) for f in filas)
    canal_izq = min(max(ancho_mayor + base * 1.2, base * 9), base * 23)
    canal_der = base * 5.5         # el sitio del total, a la derecha
    dibujo = ANCHO - canal_izq - canal_der
    hueco_nombre = canal_izq - base * 0.9

    def acortar(nombre: str) -> str:
        if mide(nombre) <= hueco_nombre:
            return nombre
        corto = nombre
        while corto and mide(corto + "…") > hueco_nombre:
            corto = corto[:-1]
        return (corto.rstrip() + "…") if corto else nombre[:1]

    mayor = max(sum(f["valores"]) for f in filas)
    alto = len(filas) * (alto_barra + hueco) + hueco

    piezas = [f'<svg viewBox="0 0 {ANCHO} {alto:.0f}" role="img" '
              f'aria-label="{_esc(descripcion)}" class="svg-barras">']
    for i, fila in enumerate(filas):
        y = hueco + i * (alto_barra + hueco)
        medio = y + alto_barra / 2 + base * 0.35
        piezas.append(_texto(canal_izq - base * 0.9, medio,
                             acortar(fila["nombre"]),
                             tam_nombre, "#0E1730", 600, "der"))
        x = canal_izq
        for valor, texto, serie in zip(fila["valores"], fila["textos"], series):
            if valor <= 0:
                continue
            ancho = max(valor / mayor * dibujo, base * 0.12)
            piezas.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{ancho:.1f}" '
                f'height="{alto_barra:.1f}" fill="{serie["color"]}" rx="2"/>')
            # La cifra va DENTRO del tramo si cabe. Si no cabe, el tramo se
            # queda sin número y su valor se lee en la tabla de debajo: meterlo
            # fuera lo pegaría al del tramo siguiente y no se sabría de cuál es.
            #
            # Con UNA sola serie no se pone: el tramo es la fila entera y su
            # cifra ya va al final de la barra. Ponerla en los dos sitios era
            # escribir el mismo número dos veces.
            if len(series) > 1 and ancho > base * 4.2:
                piezas.append(_texto(x + ancho / 2, medio, texto, base * 0.95,
                                     "#FFFFFF", 700, "centro"))
            x += ancho
        piezas.append(_texto(x + base * 0.7, medio, fila["total"], base * 0.95,
                             "#0E1730", 700))
    piezas.append("</svg>")

    leyenda = "".join(
        f'<span class="clave"><i class="sw" style="background:{s["color"]}"></i>'
        f'{_esc(s["nombre"])} <b>{_esc(s["total"])}</b></span>' for s in series)
    return (f'<div class="grafica">{"".join(piezas)}'
            f'<p class="leyenda-grafica">{leyenda}</p></div>')


def facturable_por_persona(personas: Sequence, horas, para_pdf: bool = False) -> str:
    """Lo facturable frente al resto, persona a persona.

    Dibuja **las columnas de la tabla que tiene debajo**: la barra entera son
    las horas registradas de esa persona (`total_hours`) y el primer tramo son
    sus facturables (`billable_hours`). El segundo tramo es lo que queda de la
    barra; su cifra es la resta de esas dos columnas, no un dato nuevo.
    """
    filas: List[Dict] = []
    fac_total = no_total = 0.0
    for p in personas:
        total = float(p.total_hours or 0)
        fac = float(p.billable_hours or 0)
        resto = max(total - fac, 0.0)
        fac_total += fac
        no_total += resto
        filas.append({"nombre": p.user_name,
                      "valores": [fac, resto],
                      "textos": [horas(fac), horas(resto)],
                      "total": horas(total)})
    series = [{"nombre": "Facturable", "color": "#0032A7", "total": horas(fac_total)},
              {"nombre": "No facturable", "color": "#FCA311", "total": horas(no_total)}]
    return barras(filas, series, para_pdf,
                  "Horas facturables y no facturables de cada persona")


def horas_por_actividad(items: Sequence, horas, para_pdf: bool = False) -> str:
    """Las horas de cada actividad. Una sola serie: la barra es la cifra."""
    filas = [{"nombre": x.name, "valores": [float(x.hours or 0)],
              "textos": [horas(x.hours)], "total": horas(x.hours)}
             for x in items]
    total = sum(float(x.hours or 0) for x in items)
    series = [{"nombre": "Horas registradas", "color": "#03287D",
               "total": horas(total)}]
    return barras(filas, series, para_pdf, "Horas registradas por actividad")
