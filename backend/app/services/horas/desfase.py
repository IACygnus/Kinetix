"""El estado de desfase de un proyecto o de una actividad (ETAPA H2b, §5.1).

Una sola función, en un solo sitio, porque el mismo cálculo lo necesitan el
listado de proyectos, el detalle de proyecto y —más adelante— los reportes. Mismo
criterio que `calendario.py` y que `criterios.py` del módulo de análisis.

Los umbrales son los de §5.1:

    < 90 %        en_rango
    90 % – 100 %  por_agotarse
    > 100 %       desfasado

**«Desfase», no «exceso»** (H-D27): la palabra describe el proyecto, que va por
encima de lo estimado, y no culpa a quien registró las horas. Los nombres
internos que ya existían —`over_estimate`— se conservan a propósito: cambiarlos
obligaría a tocar el contrato que H1 y H2 dejaron cerrado.
"""
from decimal import Decimal
from typing import Optional

CERO = Decimal("0")

# Los CUATRO valores del consumo (§5.1, v1.5).
#
# ETAPA H8 (H-D82): el rótulo vuelve a ser **«En rango»**. v1.3 lo había puesto
# como «En ejecución», pero `en_ejecucion` es ahora un ESTADO del proyecto
# (§3.1) y dos cosas distintas no pueden llamarse igual en la misma fila. La
# clave interna nunca cambió: era `en_rango` desde H2b.
#
# Y **desaparece el quinto valor, `cerrado`**: cerrar un proyecto es un estado,
# no una forma de gastar horas. Un proyecto finalizado sigue diciendo cuánto
# consumió, en su columna, que es justo lo que H-D82 quería. Quién lo cerró y
# cuándo lo cuenta `estados.py`.
EN_RANGO = "en_rango"
POR_AGOTARSE = "por_agotarse"
TERMINADO = "terminado"
DESFASADO = "desfasado"

TEXTOS = {
    EN_RANGO: "En rango",
    POR_AGOTARSE: "Por agotarse",
    TERMINADO: "Terminado",
}

# §5.1. En porcentaje, para poder compararlos sin dividir dos veces.
UMBRAL_POR_AGOTARSE = Decimal("90")
UMBRAL_DESFASADO = Decimal("100")


def porcentaje(consumido: Decimal, estimado: Decimal) -> Decimal:
    """Cuánto se lleva consumido, en porcentaje.

    Sin estimación no hay porcentaje que calcular: se devuelve 0 en vez de
    dividir por cero. Un proyecto sin horas estimadas —los que crea la
    importación (§6.2.4)— no puede estar desfasado, porque no hay contra qué.
    """
    est = Decimal(str(estimado or 0))
    if est <= 0:
        return CERO
    return (Decimal(str(consumido or 0)) / est) * Decimal("100")


def estado(consumido: Decimal, estimado: Decimal) -> str:
    """El **consumo** de §5.1 (v1.5). Los bordes, uno a uno:

    - **exactamente 90 %** ya es `por_agotarse`: el aviso llega al llegar al
      umbral, no un cuarto de hora después;
    - **exactamente 100 %** es `terminado`, no desfase: se consumió lo estimado,
      ni una hora más. Es el caso que Fredy echaba de menos;
    - **por encima del 100 %**, `desfasado`;
    - **sin estimación**, `en_rango`: no hay contra qué comparar.

    **El estado del proyecto no entra aquí** (H-D82). Hasta v1.4, un proyecto
    cerrado tapaba su consumo con la palabra «Cerrado» y ya no se sabía si se
    había pasado de horas o no. Ahora son dos columnas: esta contesta cuánto se
    gastó, y `estados.py` contesta en qué punto está el trabajo.

    El consumo que llega aquí es **el de siempre**, no el del periodo que se esté
    mirando (H-D67): lo calculan así la consulta, el informe y el listado.
    """
    est = Decimal(str(estimado or 0))
    if est <= 0:
        return EN_RANGO
    pct = porcentaje(consumido, est)
    if pct > UMBRAL_DESFASADO:
        return DESFASADO
    if pct == UMBRAL_DESFASADO:
        return TERMINADO
    if pct >= UMBRAL_POR_AGOTARSE:
        return POR_AGOTARSE
    return EN_RANGO


def horas_de_desfase(consumido: Decimal, estimado: Decimal) -> Decimal:
    """Las horas de más. Cero si no hay desfase, nunca un número negativo."""
    est = Decimal(str(estimado or 0))
    con = Decimal(str(consumido or 0))
    if est <= 0 or con <= est:
        return CERO
    return con - est


def etiqueta(consumido: Decimal, estimado: Decimal) -> str:
    """El texto que ve el usuario, ya en formato español.

    >>> etiqueta(Decimal("49"), Decimal("40"))
    'Desfasado +9 h'
    >>> etiqueta(Decimal("40"), Decimal("40"))
    'Terminado'
    >>> etiqueta(Decimal("10"), Decimal("40"))
    'En rango'
    """
    e = estado(consumido, estimado)
    if e == DESFASADO:
        de_mas = horas_de_desfase(consumido, estimado)
        return f"Desfasado +{_horas(de_mas)} h"
    return TEXTOS[e]


def _horas(valor: Decimal) -> str:
    """Horas a la española: 9 -> '9', 9.5 -> '9,5'. Sin decimales inútiles."""
    v = Decimal(str(valor)).normalize()
    texto = format(v, "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",") or "0"
