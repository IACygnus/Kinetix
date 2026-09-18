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

# Los estados de §5.1 (v1.3). La clave interna `en_rango` se conserva —la usan las
# tres pantallas y el informe— y lo que cambia es lo que se lee: «En ejecución»
# dice lo que pasa; «en rango» no decía nada.
EN_RANGO = "en_rango"
POR_AGOTARSE = "por_agotarse"
TERMINADO = "terminado"
DESFASADO = "desfasado"
CERRADO = "cerrado"

TEXTOS = {
    EN_RANGO: "En ejecución",
    POR_AGOTARSE: "Por agotarse",
    TERMINADO: "Terminado",
    CERRADO: "Cerrado",
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


def estado(consumido: Decimal, estimado: Decimal, cerrado: bool = False) -> str:
    """El estado de §5.1 (v1.3). Los bordes, uno a uno:

    - **exactamente 90 %** ya es `por_agotarse`: el aviso llega al llegar al
      umbral, no un cuarto de hora después;
    - **exactamente 100 %** es `terminado`, no desfase: se consumió lo estimado,
      ni una hora más. Es el caso que Fredy echaba de menos;
    - **por encima del 100 %**, `desfasado`;
    - **sin estimación**, `en_rango`: no hay contra qué comparar.

    `cerrado` manda sobre todo lo demás: un proyecto que se cerró a mano ya no
    está «en ejecución» aunque le sobren horas.

    El consumo que llega aquí es **el de siempre**, no el del periodo que se esté
    mirando (H-D67): lo calculan así la consulta, el informe y el listado.
    """
    if cerrado:
        return CERRADO
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


def etiqueta(consumido: Decimal, estimado: Decimal, cerrado: bool = False) -> str:
    """El texto que ve el usuario, ya en formato español.

    >>> etiqueta(Decimal("49"), Decimal("40"))
    'Desfasado +9 h'
    >>> etiqueta(Decimal("40"), Decimal("40"))
    'Terminado'
    """
    e = estado(consumido, estimado, cerrado)
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
