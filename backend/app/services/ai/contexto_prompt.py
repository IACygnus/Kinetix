"""
BLOQUE 2.2 — el bloque de la ejecucion: lo que es igual en TODAS las llamadas
de un informe, y va justo detras del mensaje de sistema.

Nace del reporte 137 §6 y del 136 §4: OpenAI reutiliza la cache por bloques
desde el principio del mensaje, asi que lo comun va delante y siempre en el
mismo orden, y lo propio de cada seccion, detras:

    1. SISTEMA (uno solo, `gemini.SYSTEM_PROMPT`)
    2. BLOQUE DE LA EJECUCION (este modulo): unidad, tipo de prueba, cifras
       globales, criterios, linea de tiempo con fases y hechos
    3. [por transaccion: su cabecera]  ·  LECTURA BASE, cuando ya existe
    4. LO PROPIO DE LA SECCION: sus datos, su serie y su instruccion

Una sola definicion para el informe general y para el de cada transaccion: las
seis secciones de cada transaccion llevan EXACTAMENTE el mismo bloque que las
diez del general, byte a byte. Por eso se construye desde el parser, que es lo
que tienen los dos caminos, y los criterios se leen solo por sus claves
numericas (`criterios.bloque_completo`): el veredicto que se les anade despues
no cambia el bloque.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.services.ai import fases as F
from app.services.ai import resumen_serie
from app.services.ai.criterios import bloque_completo
from app.services.ai.estilo import ms, num, pct, percentil_frase
from app.services.analista import prompt as PA   # BLOQUE 5


def _unidad(metric_unit: str) -> str:
    from app.services.ai.gemini import METRIC_UNIT_NAMES
    nombre = METRIC_UNIT_NAMES.get(metric_unit, METRIC_UNIT_NAMES["TPS"])
    return (f"UNIDAD DE MEDIDA: cuando hables de carga o rendimiento, usa siempre "
            f"'{nombre}'. No mezcles TPS con UVC.")


def _tipo(test_type: str) -> str:
    from app.services.ai.gemini import TEST_TYPE_DESCRIPTIONS
    return "TIPO DE PRUEBA: " + TEST_TYPE_DESCRIPTIONS.get(test_type, f"Tipo de prueba: {test_type}")


def bloque_ejecucion(metrics: Dict[str, Any], test_type: str, metric_unit: str,
                     acceptance_criteria: Optional[Dict[str, Any]],
                     df_todo=None, fases: Optional[F.Fases] = None, hechos: str = "",
                     tabla: str = "") -> str:
    """El bloque comun. `df_todo` es `parser.df` (para la linea de tiempo);
    `hechos` es `resumen_serie.hechos_de_la_prueba`, que ya lleva las fases."""
    total = metrics.get("total_requests", 0) or 0
    errores = metrics.get("total_errors", 0) or 0
    lineas = [
        "DATOS DE LA EJECUCION (los mismos en todas las secciones de este informe)",
        _unidad(metric_unit),
        _tipo(test_type),
        "",
        "CIFRAS GLOBALES:",
        f"- Peticiones: {num(total)}, con {num(errores)} errores ({pct(metrics.get('error_rate', 0))})",
        f"- Tiempo promedio de respuesta: {ms(metrics.get('avg_response_time', 0))}",
        f"- Caudal global: {num(metrics.get('throughput', 0), 2)} por segundo",
        f"- Duracion: {num(metrics.get('duration_seconds', 0))} segundos",
    ]
    if metrics.get("total_redirects"):
        lineas.append(f"- Redirecciones, aparte del trafico principal: {num(metrics['total_redirects'])}")
    lineas.append("- Percentiles globales (dato de apoyo; si alguno hace falta, uno solo y contado en personas): "
                  + "; ".join(percentil_frase(p, metrics.get(k, 0)) for p, k in (
                      (50, "median_response_time"), (90, "p90_response_time"),
                      (95, "p95_response_time"), (99, "p99_response_time"))))
    # BLOQUE 2.5 (reporte 140 §3): la tabla por transaccion es igual en todas las
    # llamadas y alarga el tramo comun lo bastante para que las secciones generales
    # alcancen el corte de cache de 2.816 tokens; antes se quedaban a ~200.
    if tabla:
        lineas += ["", "TABLA DE RESULTADOS POR TRANSACCION:", tabla]
    # BLOQUE 5: con el «Analista IA», sus criterios (con el resultado que calculo
    # el servidor) sustituyen al bloque de los tres fijos; sin el, nada cambia.
    analista = acceptance_criteria.get("analista") if isinstance(acceptance_criteria, dict) else None
    if isinstance(analista, dict):
        crit = PA.seccion_criterios(analista)
        if crit:
            lineas += ["", crit]
    else:
        crit = bloque_completo(acceptance_criteria).strip()
        lineas += ["", crit if crit else "CRITERIOS DE ACEPTACION: no se definieron."]
    if df_todo is not None and len(df_todo):
        lineas += ["", linea_de_tiempo(df_todo)]
    if hechos:
        lineas += ["", hechos.strip()]
    elif fases is not None:
        lineas += ["", fases.linea()]
    if isinstance(analista, dict):
        for seccion in (PA.seccion_relato(analista), PA.seccion_errores(analista)):
            if seccion:   # vacias, no aparecen
                lineas += ["", seccion]
    return "\n".join(lineas)


def linea_de_tiempo(df_todo, con_fecha: bool = False) -> str:
    """Cuando empezo y acabo la prueba. `con_fecha` para quien la cruza con
    capturas de otras herramientas (el global de monitoreo), que miran el reloj."""
    t0, t1 = df_todo["timestamp"].min(), df_todo["timestamp"].max()
    fecha = f" del {t0.strftime('%d/%m/%Y')}" if con_fecha else ""
    return (f"LINEA DE TIEMPO: la prueba va de {t0.strftime('%H:%M:%S')} a "
            f"{t1.strftime('%H:%M:%S')}{fecha} ({num((t1 - t0).total_seconds() / 60, 1)} minutos). "
            f"Cada momento se da como «min M:SS» desde el inicio de la prueba, con la "
            f"hora del reloj entre parentesis.")


def metricas_de_parser(parser) -> Dict[str, Any]:
    """Las metricas de la ejecucion como las calcula `/upload` (`parser.parse()`),
    sin volver a leer el JTL: las principales mas las redirecciones."""
    m = parser._calculate_metrics(parser.df_main)
    m["total_redirects"] = len(parser.df_redirects) if parser.df_redirects is not None else 0
    return m


def contexto_de_parser(parser, test_type: str, metric_unit: str,
                       acceptance_criteria: Optional[Dict[str, Any]],
                       metrics: Optional[Dict[str, Any]] = None) -> Tuple[str, F.Fases]:
    """(bloque, fases) desde un parser ya parseado. Lo usan el informe general y
    los de transaccion, asi que los dos mandan el mismo bloque."""
    df_main = parser.df_main if getattr(parser, "df_main", None) is not None and len(parser.df_main) else parser.df
    intervalo = parser._calculate_adaptive_interval() if hasattr(parser, "_calculate_adaptive_interval") else 1
    fases = F.calcular(df_main)
    hechos = resumen_serie.hechos_de_la_prueba(df_main, intervalo, fases)
    m = metrics if metrics is not None else metricas_de_parser(parser)
    return bloque_ejecucion(m, test_type, metric_unit, acceptance_criteria, parser.df, fases, hechos,
                            tabla_de(parser.get_summary_table_data())), fases


def tabla_de(summary_df) -> str:
    """La tabla por transaccion y su agrupacion por tiempo de respuesta, con el
    mismo formato que ya usaban el resumen y la grafica de tiempos."""
    from app.services.ai.gemini import (GeminiAnalyzer, build_tier_summary,
                                        prepare_insights_for_prompt)
    return (GeminiAnalyzer._build_transactions_table(None, summary_df)
            + "\n\nLAS TRANSACCIONES AGRUPADAS POR SU TIEMPO DE RESPUESTA:\n"
            + build_tier_summary(prepare_insights_for_prompt(summary_df)))


def nota_intervalo(intervalo: int) -> str:
    """Lo unico de la linea de tiempo que cambia de una grafica a otra."""
    return f"Cada punto de la grafica agrupa {num(intervalo)} s."
