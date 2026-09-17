"""ETAPA 3.2 — Pruebas de los helpers deterministas de estilo.

Casos limite pedidos por el plan de la etapa mas los que hicieron falta para
fijar las decisiones T1-T5 del reporte 30.
"""
import pytest

from app.services.ai.estilo import (
    BLOQUE_ESTILO,
    PERMISO_VEREDICTO,
    REFERENCIA_ESTILO,
    bloque_estilo,
    detectar_estilo,
    kbs,
    mediana_frase,
    ms,
    num,
    pct,
    percentil_frase,
    percentiles_bloque,
    terminos_de,
    tiempo,
    trazar_cifras,
    veces,
)


# ==================== FORMATO ESPANOL (D32) ====================

def test_miles_con_punto():
    assert num(10075) == "10.075"


def test_porcentaje_con_coma():
    assert pct(0.2734) == "0,27%"


def test_porcentaje_de_dos_cifras():
    assert pct(28.2) == "28,20%"


def test_milisegundos_con_unidad_separada():
    assert ms(125) == "125 ms"


def test_tiempo_sobre_un_segundo_va_en_segundos():
    assert tiempo(3515) == "3,5 segundos"


def test_tiempo_bajo_un_segundo_se_queda_en_ms():
    assert tiempo(125) == "125 ms"


def test_tiempo_justo_en_mil_ms():
    assert tiempo(1000) == "1,0 segundos"


def test_ratio_en_palabras():
    assert veces(3.79) == "3,8 veces"


def test_ratio_nunca_lleva_x():
    assert "x" not in veces(21.06)


def test_kbs_con_unidad_separada():
    assert kbs(259.85) == "259,85 KB/s"


def test_num_tolera_none():
    assert num(None) == "0"


def test_num_tolera_basura():
    assert num("hola") == "hola"


# ==================== FRASES DE PERCENTIL (D33) ====================

def test_frase_p90():
    assert percentil_frase(90, 3515) == (
        "1 de cada 10 usuarios espera más de 3,5 segundos (P90: 3.515 ms)")


def test_frase_p95():
    assert percentil_frase(95, 139).startswith("1 de cada 20 usuarios")


def test_frase_p99():
    assert percentil_frase(99, 206).startswith("1 de cada 100 usuarios")


def test_frase_mediana():
    assert mediana_frase(103).startswith("la mitad de los usuarios")


def test_bloque_de_percentiles_omite_los_que_no_llegan():
    b = percentiles_bloque(p90=123, p95=139)
    assert "P90" in b and "P95" in b and "P99" not in b and "P50" not in b


# ==================== DETECTOR: JERGA (D29) ====================

def _tipos(avisos):
    return {a["tipo"] for a in avisos}


def test_tier_excelente_detectado():
    av = detectar_estilo("6 transacciones quedaron en tier excelente.", "summary_table")
    assert "jerga" in _tipos(av)
    assert any(a["termino"] == "tier" for a in av)


def test_variabilidad_detectada():
    assert "jerga" in _tipos(detectar_estilo("Auth concentra la mayor variabilidad.", "x"))


def test_dispersion_detectada_con_tilde_o_sin_ella():
    assert "jerga" in _tipos(detectar_estilo("reducir dispersión frente al resto", "x"))
    assert "jerga" in _tipos(detectar_estilo("reducir dispersion frente al resto", "x"))


def test_variacion_no_es_variabilidad():
    assert detectar_estilo("una variación puntual de procesamiento", "x") == []


def test_texto_limpio_no_deja_avisos():
    limpio = ("1.677 muestras promediaron 108 ms y la mitad de los usuarios espera "
              "mas de 103 ms. En produccion, el usuario percibira una pantalla agil.")
    assert detectar_estilo(limpio, "summary") == []


# ==================== DETECTOR: PERCENTILES (D29) ====================

def test_percentil_dentro_de_la_frase_de_usuario_no_se_marca():
    txt = "1 de cada 10 usuarios espera más de 3,5 segundos (P90: 3.515 ms)."
    assert "percentil_sin_traducir" not in _tipos(detectar_estilo(txt, "x"))


def test_percentil_suelto_se_marca():
    av = detectar_estilo("Auth tuvo P99 de 696 ms y maximo de 1.013 ms.", "x")
    assert "percentil_sin_traducir" in _tipos(av)


def test_mediana_traducida_cubre_su_frase():
    txt = "La mitad de los usuarios espera más de 103 ms (P50: 103 ms)."
    assert "percentil_sin_traducir" not in _tipos(detectar_estilo(txt, "x"))


def test_percentil_escrito_con_palabra_tambien_se_marca():
    assert "percentil_sin_traducir" in _tipos(
        detectar_estilo("el percentil 95 llego a 426 ms", "x"))


def test_la_traduccion_solo_cubre_su_propia_frase():
    txt = ("1 de cada 10 usuarios espera más de 123 ms (P90: 123 ms). "
           "El P99 llego a 206 ms.")
    av = [a for a in detectar_estilo(txt, "x") if a["tipo"] == "percentil_sin_traducir"]
    assert len(av) == 1 and av[0]["termino"] == "P99"


# ==================== DETECTOR: VEREDICTO (D30) ====================

def test_listo_para_produccion_se_marca_en_una_seccion():
    av = detectar_estilo("El sistema esta listo para produccion.", "chart_latency")
    assert "veredicto_fuera_de_conclusiones" in _tipos(av)


def test_listo_para_produccion_no_se_marca_en_conclusiones():
    av = detectar_estilo("El sistema esta listo para produccion.", "conclusions")
    assert "veredicto_fuera_de_conclusiones" not in _tipos(av)


def test_no_apto_no_se_marca_en_recomendaciones():
    av = detectar_estilo("La prueba queda NO APTO frente a los criterios.", "recommendations")
    assert "veredicto_fuera_de_conclusiones" not in _tipos(av)


def test_no_deberia_liberarse_se_marca_en_el_resumen():
    av = detectar_estilo("No deberia liberarse sin corregir los errores.", "summary_table")
    assert "veredicto_fuera_de_conclusiones" in _tipos(av)


def test_el_cierre_de_impacto_no_es_veredicto():
    """T1: la frase que exige la regla 11 del estilo jamas se marca."""
    txt = ("En produccion, el usuario percibira reservas que no cargan y "
           "eliminaciones que fallan.")
    assert detectar_estilo(txt, "chart_error_rate") == []


# ==================== DETECTOR: FORMATO INGLES (D32) ====================

def test_decimal_con_punto_se_marca():
    av = detectar_estilo("promedio global de 179.73ms", "x")
    assert any(a["termino"].startswith("decimal con punto") for a in av)


def test_miles_con_coma_se_marca():
    av = detectar_estilo("2,841 errores sobre 10,075 requests", "x")
    assert len([a for a in av if a["termino"].startswith("miles con coma")]) == 2


def test_miles_a_la_espanola_no_se_marca():
    """T2: '3.515' son tres digitos -> separador de miles, no decimal ingles."""
    av = detectar_estilo("1 de cada 10 usuarios espera más de 3,5 segundos (P90: 3.515 ms)", "x")
    assert not any(a["tipo"] == "formato_ingles" for a in av)


def test_decimal_espanol_no_se_marca():
    assert detectar_estilo("un 0,27% de error y 3,9 veces mas lento", "x") == []


def test_unidad_pegada_se_marca():
    av = detectar_estilo("respondio en 108ms", "x")
    assert any(a["termino"] == "unidad pegada: 108ms" for a in av)


def test_porcentaje_pegado_no_se_marca():
    """T4: el % SI va pegado en espanol."""
    assert detectar_estilo("una tasa de 28,20% en la prueba", "x") == []


def test_ratio_con_x_se_marca():
    av = detectar_estilo("Auth fue 3.9x mas lenta que el resto", "x")
    assert any(a["termino"].startswith("ratio con x") for a in av)


# ==================== terminos_de (D36) ====================

def test_terminos_de_resume_sin_repetir():
    av = detectar_estilo("tier excelente con P99 de 696 ms y tier degradado", "x")
    t = terminos_de(av)
    assert "tier" in t and "P99 sin traducir" in t
    assert len(t) == len(set(t))


def test_terminos_de_con_lista_vacia():
    assert terminos_de([]) == []


# ==================== ROBUSTEZ ====================

@pytest.mark.parametrize("valor", [None, "", "   "])
def test_detector_con_texto_vacio(valor):
    assert detectar_estilo(valor, "x") == []


# ==================== TRAZABILIDAD DE CIFRAS (D37) ====================

def test_cifra_espanola_es_trazable_contra_el_dato_crudo():
    r = trazar_cifras("La prueba ejecuto 10.075 transacciones.",
                      "Total de muestras: 10075")
    assert r["total"] == 1 and r["trazables"] == 1 and r["pct"] == 100.0


def test_cifra_inventada_no_es_trazable():
    r = trazar_cifras("El maximo llego a 99.999 ms.", "maximo: 438 ms")
    assert r["trazables"] == 0
    assert r["no_trazables"][0]["cifra"] == "99.999"


def test_redondeo_legitimo_sigue_siendo_trazable():
    r = trazar_cifras("promedio de 108 ms", "promedio: 108,4 ms")
    assert r["trazables"] == 1


def test_numeracion_de_lista_no_cuenta_como_cifra():
    r = trazar_cifras("1. El sistema respondio en 108 ms.", "promedio 108 ms")
    assert r["total"] == 1 and r["trazables"] == 1


def test_porcentaje_con_coma_traza_contra_el_dato_con_punto():
    r = trazar_cifras("un 41,26% de error", "tasa_error: 41.26")
    assert r["trazables"] == 1


def test_texto_vacio_devuelve_cero_sin_dividir_por_cero():
    r = trazar_cifras("", "lo que sea")
    assert r["total"] == 0 and r["pct"] is None


def test_mezcla_de_trazables_y_no_trazables():
    r = trazar_cifras("108 ms de promedio y 777 ms de pico", "promedio 108 ms, maximo 438 ms")
    assert r["total"] == 2 and r["trazables"] == 1 and r["pct"] == 50.0


# ==================== BLOQUE DE ESTILO (D28, D30, D31) ====================

def test_bloque_de_estilo_por_defecto_prohibe_el_veredicto():
    b = bloque_estilo()
    assert "EL VEREDICTO DE PRODUCCION NO VA AQUI" in b
    assert PERMISO_VEREDICTO not in b


def test_bloque_de_estilo_con_permiso_lo_anade():
    b = bloque_estilo(permite_veredicto=True)
    assert PERMISO_VEREDICTO in b
    assert b.startswith(BLOQUE_ESTILO)


def test_el_bloque_nombra_toda_la_jerga_de_d29():
    import re as _re
    b = _re.sub(r"\s+", " ", BLOQUE_ESTILO.lower())   # el salto de linea no cuenta
    for palabra in ("tier", "variabilidad", "dispersion", "latencia critica",
                    "veredicto", "hallazgo", "se evidencia", "cabe destacar",
                    "es importante mencionar", "en conclusion"):
        assert palabra in b, palabra


def test_la_referencia_lleva_su_prohibicion_de_copiar():
    assert "PROHIBIDO ABSOLUTAMENTE copiar" in REFERENCIA_ESTILO
    assert "10.075" in REFERENCIA_ESTILO   # sigue siendo el ejemplo aprobado


def test_el_bloque_ensena_las_formas_correctas():
    """Las formas que el bloque manda usar estan escritas tal cual en el.

    El bloque tambien contiene las formas PROHIBIDAS ('1.1 segundos', '3.9x'),
    a proposito y marcadas como prohibidas, asi que no se le puede pasar el
    detector entero: lo que se comprueba es que el modelo tenga delante el
    ejemplo bueno de cada regla.
    """
    for correcta in ("8.600 muestras", "0,27%", "125 ms", "3,9 veces",
                     "1 de cada 10 usuarios espera más de 3,5 segundos (P90: 3.515 ms)",
                     "1,1 segundos"):
        assert correcta in BLOQUE_ESTILO, correcta


def test_el_bloque_marca_como_prohibidas_las_formas_inglesas():
    for prohibida in ("8,600 muestras", "1.1 segundos", "179.73ms", "3.9x"):
        assert prohibida in BLOQUE_ESTILO, prohibida
