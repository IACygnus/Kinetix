"""Las letras del informe de horas, incrustadas (ETAPA D1, D-D1 · decisión A).

El informe tiene que verse igual **sin red**: el HTML se descarga y se abre
donde sea, y el PDF lo imprime WeasyPrint, que no va a buscar una fuente a
internet. Por eso las dos familias viajan dentro del documento en base64 y
**no hay ni una referencia a la red** — ni un `<link>`, ni un `@import`.

Son Exo 2 (titulares y cifras) y Montserrat (todo lo demás), las mismas de la
referencia que aprobó Fredy. Licencia **SIL Open Font License 1.1**, que
permite incrustarlas y redistribuirlas; el texto de la licencia va al lado de
los `.woff2`, en `assets/fuentes/`.

Solo los pesos que se usan de verdad y solo el **subconjunto latino** —el que
cubre las tildes, la eñe y los signos de apertura—. Son instancias estáticas
cortadas de la fuente variable con `fontTools`: WeasyPrint elige el peso por
`@font-face`, sin depender de que sepa manejar un eje variable.

    Exo2-600       17.084 B      Montserrat-400   18.492 B
    Exo2-800       17.076 B      Montserrat-500   18.604 B
                                 Montserrat-600   18.492 B
                                 Montserrat-700   18.612 B
    ------------------------------------------------------
    108.360 B en disco · 144.480 B ya en base64

Si falta un archivo **no es una parada**, igual que con el logo (H-D54): esa
cara no se declara y el navegador cae en la pila del sistema.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

RUTA_FUENTES = Path(__file__).resolve().parents[2] / "assets" / "fuentes"

# (familia, peso, archivo). El orden es el del documento de diseño.
CARAS: Tuple[Tuple[str, int, str], ...] = (
    ("Exo 2", 600, "Exo2-600.woff2"),
    ("Exo 2", 800, "Exo2-800.woff2"),
    ("Montserrat", 400, "Montserrat-400.woff2"),
    ("Montserrat", 500, "Montserrat-500.woff2"),
    ("Montserrat", 600, "Montserrat-600.woff2"),
    ("Montserrat", 700, "Montserrat-700.woff2"),
)


@lru_cache(maxsize=1)
def bloque_font_face() -> str:
    """Las seis `@font-face` con la fuente dentro, listas para el `<style>`.

    Se calcula una vez por proceso: son 144 KB de base64 y no cambian.
    """
    piezas = []
    for familia, peso, archivo in CARAS:
        ruta = RUTA_FUENTES / archivo
        try:
            if not ruta.is_file():
                continue
            datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
        except OSError:
            continue
        piezas.append(
            f"@font-face{{font-family:'{familia}';font-style:normal;"
            f"font-weight:{peso};font-display:block;"
            f"src:url(data:font/woff2;base64,{datos}) format('woff2')}}")
    return "".join(piezas)


def caras_disponibles() -> int:
    """Cuántas de las seis caras se encontraron. Para las pruebas y el reporte."""
    return sum(1 for _, _, a in CARAS if (RUTA_FUENTES / a).is_file())


# ===================== MEDIR UN TEXTO (ETAPA D1) =====================
#
# Hace falta para las gráficas, y no es un lujo: **WeasyPrint recorta los
# descendentes de un `<text>` con `text-anchor="end"`**. Comprobado imprimiendo
# la misma frase con los dos anclajes en la misma línea: la de `start` sale
# entera y la de `end` pierde las colas de la «y», la «g» y la «p».
#
# La vuelta es no usar `end` en ninguna parte y colocar el texto a mano, lo que
# exige saber cuánto mide. Se mide con las métricas de la propia fuente que se
# está incrustando, así que es exacto y no una estimación.

_ANCHOS: Dict[Tuple[str, int], Dict[int, int]] = {}
_UNIDADES: Dict[Tuple[str, int], int] = {}
# Si la fuente no se puede leer, se cae a esto: el ancho medio de una letra de
# Montserrat, en ems. Peor, pero nada se rompe.
ANCHO_POR_DEFECTO = 0.58


def _metricas(familia: str, peso: int):
    """Los anchos de avance de cada carácter, en unidades de la fuente."""
    clave = (familia, peso)
    if clave in _ANCHOS:
        return _ANCHOS[clave], _UNIDADES[clave]
    anchos: Dict[int, int] = {}
    unidades = 0
    archivo = next((a for f, p, a in CARAS if f == familia and p == peso), None)
    if archivo:
        try:
            from fontTools.ttLib import TTFont            # llega con WeasyPrint
            tf = TTFont(RUTA_FUENTES / archivo, lazy=True)
            unidades = tf["head"].unitsPerEm
            hmtx, cmap = tf["hmtx"], tf.getBestCmap()
            for codigo, nombre in cmap.items():
                if nombre in hmtx.metrics:
                    anchos[codigo] = hmtx.metrics[nombre][0]
            tf.close()
        except Exception:                                 # noqa: BLE001
            anchos, unidades = {}, 0
    _ANCHOS[clave], _UNIDADES[clave] = anchos, unidades
    return anchos, unidades


def ancho_texto(texto: str, tam: float, familia: str = "Montserrat",
                peso: int = 400) -> float:
    """Cuánto ocupa `texto` a ese tamaño, en las mismas unidades que `tam`."""
    anchos, unidades = _metricas(familia, peso)
    if not anchos or not unidades:
        return len(texto) * tam * ANCHO_POR_DEFECTO
    por_defecto = anchos.get(ord("n"), int(unidades * ANCHO_POR_DEFECTO))
    total = sum(anchos.get(ord(c), por_defecto) for c in texto)
    return total * tam / unidades
