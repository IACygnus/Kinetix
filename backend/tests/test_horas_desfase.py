"""ETAPA H2b.2 — El estado de desfase (§5.1).

Los umbrales son 90 % y 100 %, y lo que importa de verdad son **los bordes**: es
donde una comparación mal puesta pasa desapercibida durante meses.

Decisiones que estos tests fijan, para que nadie las cambie sin darse cuenta:

  - **exactamente 90 % ya es «por agotarse»** — el aviso llega al llegar al
    umbral, no un céntimo después;
  - **exactamente 100 % NO es desfase** — consumir justo lo estimado es cumplir,
    no pasarse;
  - **sin estimación no hay desfase posible** — los proyectos que crea la
    importación (§6.2.4) nacen sin horas y no pueden estar desfasados.
"""
from decimal import Decimal as D

import pytest

from app.services.horas.desfase import (
    CERRADO, DESFASADO, EN_RANGO, POR_AGOTARSE, TERMINADO,
    estado, etiqueta, horas_de_desfase, porcentaje,
)


# ==================== EL PORCENTAJE ====================

def test_porcentaje_normal():
    assert porcentaje(D("20"), D("40")) == D("50")


def test_porcentaje_por_encima_de_cien():
    assert porcentaje(D("50"), D("40")) == D("125")


def test_sin_estimacion_no_se_divide_por_cero():
    assert porcentaje(D("5"), D("0")) == D("0")


def test_sin_consumo_es_cero():
    assert porcentaje(D("0"), D("40")) == D("0")


# ==================== LOS BORDES DE §5.1 ====================

@pytest.mark.parametrize("consumido,esperado", [
    ("0",      EN_RANGO),
    ("20",     EN_RANGO),
    ("35.75",  EN_RANGO),       # 89,375 %
    ("35.9",   EN_RANGO),       # 89,75 %
])
def test_por_debajo_del_noventa_esta_en_rango(consumido, esperado):
    assert estado(D(consumido), D("40")) == esperado


def test_exactamente_el_noventa_ya_avisa():
    """36 de 40 es el 90 % justo: el aviso llega AL llegar al umbral."""
    assert porcentaje(D("36"), D("40")) == D("90")
    assert estado(D("36"), D("40")) == POR_AGOTARSE


@pytest.mark.parametrize("consumido", ["36", "38", "39.75"])
def test_entre_noventa_y_cien_esta_por_agotarse(consumido):
    assert estado(D(consumido), D("40")) == POR_AGOTARSE


def test_exactamente_el_cien_es_TERMINADO():
    """ETAPA H6 (H-D66): consumir justo lo estimado no es «por agotarse» ni
    desfase — es haber terminado. Es el caso que Fredy echaba de menos."""
    assert porcentaje(D("40"), D("40")) == D("100")
    assert estado(D("40"), D("40")) == TERMINADO
    assert etiqueta(D("40"), D("40")) == "Terminado"
    assert horas_de_desfase(D("40"), D("40")) == D("0")


def test_un_pelo_por_debajo_del_cien_sigue_por_agotarse():
    assert estado(D("39.96"), D("40")) == POR_AGOTARSE


def test_un_pelo_por_encima_del_cien_ya_es_desfase():
    assert estado(D("40.04"), D("40")) == DESFASADO


# ==================== EL PROYECTO CERRADO (H-D66) ====================

def test_un_proyecto_cerrado_dice_cerrado_pase_lo_que_pase():
    """Manda sobre cualquier estado de consumo: ya no está «en ejecución»."""
    for con, est in [("0", "40"), ("38", "40"), ("40", "40"), ("49", "40"), ("5", "0")]:
        assert estado(D(con), D(est), cerrado=True) == CERRADO
        assert etiqueta(D(con), D(est), cerrado=True) == "Cerrado"


def test_sin_cerrar_el_estado_es_el_de_siempre():
    assert estado(D("49"), D("40"), cerrado=False) == DESFASADO


@pytest.mark.parametrize("consumido", ["40.25", "41", "49", "80"])
def test_por_encima_del_cien_es_desfase(consumido):
    assert estado(D(consumido), D("40")) == DESFASADO


def test_sin_estimacion_nunca_hay_desfase():
    """Un proyecto creado por importación nace sin horas estimadas (§6.2.4):
    no hay contra qué compararlo."""
    assert estado(D("100"), D("0")) == EN_RANGO
    assert horas_de_desfase(D("100"), D("0")) == D("0")


# ==================== LAS HORAS DE MÁS ====================

def test_las_horas_de_desfase_son_la_diferencia():
    assert horas_de_desfase(D("49"), D("40")) == D("9")


def test_nunca_devuelve_negativo():
    assert horas_de_desfase(D("10"), D("40")) == D("0")


def test_con_decimales():
    assert horas_de_desfase(D("40.75"), D("40")) == D("0.75")


# ==================== LA ETIQUETA (H-D27) ====================

def test_la_etiqueta_dice_desfasado_con_las_horas():
    assert etiqueta(D("49"), D("40")) == "Desfasado +9 h"


def test_la_etiqueta_usa_coma_decimal():
    assert etiqueta(D("40.5"), D("40")) == "Desfasado +0,5 h"


def test_la_etiqueta_no_arrastra_ceros():
    """9,00 se lee «9», no «9,00»."""
    assert etiqueta(D("49.00"), D("40")) == "Desfasado +9 h"


def test_las_otras_etiquetas():
    """H-D66: «En rango» no decía nada; «En ejecución» sí."""
    assert etiqueta(D("38"), D("40")) == "Por agotarse"
    assert etiqueta(D("10"), D("40")) == "En ejecución"
    assert etiqueta(D("40"), D("40")) == "Terminado"


def test_la_palabra_exceso_no_aparece_en_ninguna_etiqueta():
    """H-D27: en todo el producto se dice «desfase»."""
    for con, est in [("0", "40"), ("38", "40"), ("40", "40"), ("49", "40"), ("5", "0")]:
        assert "exceso" not in etiqueta(D(con), D(est)).lower()
        assert "exceso" not in etiqueta(D(con), D(est), cerrado=True).lower()


def test_la_palabra_en_rango_ya_no_se_lee_en_ninguna_etiqueta():
    """H-D66: se retiró del producto."""
    for con, est in [("0", "40"), ("38", "40"), ("40", "40"), ("49", "40"), ("5", "0")]:
        assert "en rango" not in etiqueta(D(con), D(est)).lower()
