"""
N4.3 — Series temporales de UNA transaccion, insumo del mini-informe por
transaccion (sprint N4).

Vive FUERA de `jtl_parser.py` a proposito. Ese archivo esta protegido y su
`get_all_charts_data()` construye el payload del dashboard completo, que ya pesa
850 KB con 3 transacciones (diagnostico 036 §3.1). Añadirle 3 series nuevas por
label lo llevaria a 2,1 MB en cada apertura del dashboard, para un dato que solo
consumen las transacciones marcadas como criticas.

Este modulo no lee el JTL ni conoce la base de datos: recibe el DataFrame ya
parseado y devuelve estructuras listas para serializar a JSON.

Las 5 series son las aprobadas para el mini-informe: response_times (avg + max),
latency, error_rate, codes y tps. Dos de ellas ya existian agrupadas por label en
el parser (response_times y tps) y se reproducen aqui con el mismo calculo; las
otras tres son nuevas — antes solo existian sumadas sobre todo el test.

Leccion GRAF1: `response_times` conserva la agregacion dual (mean + max) sobre
bucket de 1 s. Si se suaviza, el pico de 21.060 ms desaparece del grafico del que
va a hablar el analisis.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Las 5 graficas del mini-informe, en el orden en que se presentan.
CHART_TYPES = ("response_times", "latency", "error_rate", "codes", "tps")

# GRAF1: 1 s fijo. Es el mismo bucket que usa `response_times_by_label` en el
# parser. El caller puede subirlo, pero entonces los picos se promedian.
DEFAULT_INTERVAL_SECONDS = 1


def available_labels(df) -> List[str]:
    """Transacciones presentes en el DataFrame. Vacio si no hay dato util."""
    if df is None or len(df) == 0 or "label" not in df.columns:
        return []
    return [str(x) for x in df["label"].unique()]


def _as_bool(series):
    """`success` llega como bool desde JTLParser, pero los parsers de WAPT y
    Locust pueden entregarlo como texto. Sin esto, astype(bool) sobre 'false'
    devolveria True y la tasa de error saldria en cero."""
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin(("true", "1", "yes"))


def build_transaction_series(
    df,
    label: str,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> Dict[str, Any]:
    """Las 5 series de una sola transaccion.

    Args:
        df: DataFrame ya parseado. El caller pasa `parser.df_main` (o
            `parser.df` si no hay redirecciones separadas), mismo criterio que
            `get_all_charts_data()`.
        label: nombre exacto de la transaccion.
        interval_seconds: tamaño del bucket. 1 s por GRAF1.

    Returns:
        dict con las 5 series como listas de puntos serializables, mas
        `warnings` con lo que no se pudo calcular por falta de columnas.

    Raises:
        ValueError: DataFrame vacio, sin columna `label`, o label inexistente.
            El endpoint que lo consuma debe traducirlo a 400/404.
    """
    if df is None or len(df) == 0:
        raise ValueError("El DataFrame no tiene muestras")
    if "label" not in df.columns or "timestamp" not in df.columns:
        raise ValueError("El DataFrame no trae las columnas 'label' y 'timestamp'")

    sub = df[df["label"] == label]
    if len(sub) == 0:
        raise ValueError(f"La transaccion '{label}' no existe en este JTL")

    interval = max(1, int(interval_seconds or DEFAULT_INTERVAL_SECONDS))
    sub = sub.copy()
    sub["_bucket"] = sub["timestamp"].dt.floor(f"{interval}s")
    warnings: List[str] = []

    def _iso(ts) -> str:
        return ts.isoformat()

    # 1. Tiempos de respuesta — agregacion dual (GRAF1)
    rt = sub.groupby("_bucket")["elapsed"].agg(["mean", "max"]).reset_index()
    # N4.4b: zip sobre las columnas en vez de iterrows(). iterrows() construye una
    # Series de pandas por fila; con 1.666 buckets x 5 series eso es tiempo que se
    # nota al cambiar de transaccion en la pantalla de N4.7. La salida es identica.
    response_times = [
        {"timestamp": _iso(b), "value": float(v), "value_max": float(mx)}
        for b, v, mx in zip(rt["_bucket"], rt["mean"], rt["max"])
    ]

    # 2. Latencia
    latency: List[Dict[str, Any]] = []
    if "Latency" in sub.columns:
        lat = sub.groupby("_bucket")["Latency"].mean().reset_index()
        latency = [
            {"timestamp": _iso(b), "value": float(v)}
            for b, v in zip(lat["_bucket"], lat["Latency"])
        ]
    else:
        warnings.append("Sin columna 'Latency': la grafica de latencia queda vacia")

    # 3. Tasa de error (%) por bucket
    error_rate: List[Dict[str, Any]] = []
    if "success" in sub.columns:
        sub["_ok"] = _as_bool(sub["success"])
        er = sub.groupby("_bucket")["_ok"].mean().reset_index()
        error_rate = [
            {"timestamp": _iso(b), "value": float(100.0 * (1.0 - v))}
            for b, v in zip(er["_bucket"], er["_ok"])
        ]
    else:
        warnings.append("Sin columna 'success': la grafica de tasa de error queda vacia")

    # 4. Codigos de respuesta por segundo — una serie por codigo
    codes: List[Dict[str, Any]] = []
    if "responseCode" in sub.columns:
        cd = sub.groupby(["_bucket", "responseCode"]).size().reset_index(name="n")
        codes = [
            {"timestamp": _iso(b), "value": float(n) / interval, "code": str(c)}
            for b, c, n in zip(cd["_bucket"], cd["responseCode"], cd["n"])
        ]
    else:
        warnings.append("Sin columna 'responseCode': la grafica de codigos queda vacia")

    # 5. TPS de la transaccion
    tps_df = sub.groupby("_bucket").size().reset_index(name="n")
    tps = [
        {"timestamp": _iso(b), "value": float(n) / interval}
        for b, n in zip(tps_df["_bucket"], tps_df["n"])
    ]

    logger.info(
        f"N4.3: series de '{label}' — {len(sub)} muestras, bucket {interval}s, "
        f"puntos rt={len(response_times)} lat={len(latency)} err={len(error_rate)} "
        f"cod={len(codes)} tps={len(tps)}"
    )

    return {
        "label": label,
        "interval_seconds": interval,
        "sample_count": int(len(sub)),
        "response_times": response_times,
        "latency": latency,
        "error_rate": error_rate,
        "codes": codes,
        "tps": tps,
        "warnings": warnings,
    }
