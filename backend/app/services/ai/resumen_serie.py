"""
ETAPA R2 (R-D9, R-D10) — la serie de tiempo de cada grafica, resumida para el prompt.

Hasta R2, cinco de las ocho secciones de graficas del informe general recibian
solo agregados (reporte 120 §3) y aun asi se les preguntaba por el
comportamiento a lo largo de la prueba. El modelo, que tiene prohibido inventar
cifras, contestaba lo unico honesto: «con la informacion agregada no es
posible...». Este modulo le da con que contestar.

Una sola definicion para el informe general y para el de cada transaccion. Lee
el DataFrame YA parseado —no toca `jtl_parser.py`, que esta protegido— y agrupa
con el MISMO criterio que la grafica de la que habla cada seccion: `floor` del
`timestamp` al intervalo de esa grafica (el adaptativo del dashboard para las
generales, 1 s para Response Times y para las de una transaccion).

EL FORMATO (R-D10), igual para todas las series:
  1. Extremos con su momento: minimo, maximo y promedio. El momento va como
     «min M:SS» desde el inicio de la prueba y la hora del reloj entre
     parentesis, que es lo que lee quien mira la grafica.
  2. Lo habitual: entre que valores estuvo 8 de cada 10 puntos.
  3. Tramos: la prueba partida en seis ventanas iguales, con el valor de cada
     una calculado sobre sus MUESTRAS (no promediando porcentajes de puntos).
  4. Episodios sostenidos: rachas de puntos seguidos fuera de lo habitual. Es
     lo que distingue un problema puntual de uno sostenido.
  5. Tendencia: primer tercio contra ultimo tercio.

Todas las cifras salen de `estilo.py` (regla 22): el modelo las copia.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from app.services.ai.estilo import ms, num, pct

logger = logging.getLogger(__name__)

TRAMOS = 6            # ventanas iguales en que se parte la prueba
RACHA_MINIMA = 3      # puntos seguidos para que un episodio cuente como sostenido
MAX_EPISODIOS = 3
MAX_PICOS = 3
MAX_LABELS_RT = 10    # Response Times: transacciones con detalle; el resto se nombra


# ====================================================================
# Utilidades de tiempo
# ====================================================================

def _reloj(ts) -> str:
    return pd.Timestamp(ts).strftime("%H:%M:%S")


def _minuto(ts, t0) -> str:
    s = max(0, int(round((pd.Timestamp(ts) - t0).total_seconds())))
    return f"{s // 60}:{s % 60:02d}"


def _cuando(ts, t0) -> str:
    return f"min {_minuto(ts, t0)} ({_reloj(ts)})"


def momento(ts, t0) -> str:
    """Publico: «min M:SS (HH:MM:SS)». Lo usa el pipeline para la tabla de errores."""
    return _cuando(ts, t0)


def _ventana(a, b, t0) -> str:
    return f"min {_minuto(a, t0)} a {_minuto(b, t0)} ({_reloj(a)} a {_reloj(b)})"


def _tps(v) -> str:
    return f"{num(v, 2)} por segundo"


def _hilos(v) -> str:
    return "1 hilo" if int(v) == 1 else f"{num(v)} hilos"


def cabecera(df: pd.DataFrame, intervalo: int) -> str:
    """Una linea que explica como leer los momentos. Va una vez por prompt."""
    t0, t1 = df["timestamp"].min(), df["timestamp"].max()
    dur = (t1 - t0).total_seconds()
    return (f"LINEA DE TIEMPO: la prueba va de {_reloj(t0)} a {_reloj(t1)} "
            f"({num(dur / 60, 1)} minutos). Cada momento se da como «min M:SS» desde el "
            f"inicio de la prueba, con la hora del reloj entre parentesis. Cada punto de "
            f"la grafica agrupa {num(intervalo)} s.")


# ====================================================================
# El nucleo: una serie por puntos + sus muestras
# ====================================================================

def _puntos(df: pd.DataFrame, intervalo: int, agg: Callable[[pd.DataFrame], pd.Series]) -> pd.Series:
    """La serie tal como la pinta la grafica: un valor por bucket."""
    b = df["timestamp"].dt.floor(f"{max(1, int(intervalo))}s")
    return agg(df.assign(_b=b).groupby("_b")).astype(float).sort_index()


def _cortes(t0, t1, n: int) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
    paso = (t1 - t0) / n
    return [(t0 + paso * i, t0 + paso * (i + 1)) for i in range(n)]


def _en(df, a, b, ultima: bool):
    ts = df["timestamp"]
    return df[(ts >= a) & ((ts <= b) if ultima else (ts < b))]


def _episodios(serie: pd.Series, fuera: pd.Series) -> List[Tuple]:
    """Rachas de puntos seguidos donde `fuera` es True, de mayor a menor."""
    rachas, ini, prev = [], None, None
    for ts, f in fuera.items():
        if f and ini is None:
            ini = ts
        if not f and ini is not None:
            rachas.append((ini, prev))
            ini = None
        prev = ts
    if ini is not None:
        rachas.append((ini, prev))
    out = []
    for a, b in rachas:
        tramo = serie[(serie.index >= a) & (serie.index <= b)]
        if len(tramo) >= RACHA_MINIMA:
            out.append((a, b, len(tramo), float(tramo.mean()), float(tramo.max()), float(tramo.min())))
    out.sort(key=lambda e: -e[2])
    return out[:MAX_EPISODIOS]


def resumir(
    df: pd.DataFrame,
    intervalo: int,
    nombre: str,
    fmt: Callable[[float], str],
    por_punto: Callable,
    por_muestras: Callable[[pd.DataFrame], float],
    t0=None,
    alto_es_malo: bool = True,
    habitual: bool = True,
    episodios: bool = True,
    tramos: int = TRAMOS,
) -> str:
    """El bloque de una serie en el formato de R-D10.

    `por_punto` agrega un groupby por bucket (lo que pinta la grafica);
    `por_muestras` calcula el valor de un trozo de la prueba sobre sus muestras,
    para que los tramos no promedien porcentajes de puntos con pesos distintos.
    """
    if df is None or len(df) == 0:
        return f"{nombre}: sin muestras."
    t0 = df["timestamp"].min() if t0 is None else t0
    t1 = df["timestamp"].max()
    serie = _puntos(df, intervalo, por_punto)
    if len(serie) == 0:
        return f"{nombre}: sin puntos."

    lineas = [f"{nombre} ({num(len(serie))} puntos):"]

    # 1. Extremos con su momento
    vmin, vmax = serie.min(), serie.max()
    imin, imax = serie.idxmin(), serie.idxmax()
    n_min, n_max = int((serie == vmin).sum()), int((serie == vmax).sum())
    txt_min = f"minimo {fmt(vmin)} " + (
        f"(en {num(n_min)} de los {num(len(serie))} puntos; el primero {_cuando(imin, t0)})"
        if n_min > 1 else _cuando(imin, t0))
    txt_max = f"maximo {fmt(vmax)} " + (
        f"(en {num(n_max)} puntos; el primero {_cuando(imax, t0)})"
        if n_max > 1 else _cuando(imax, t0))
    lineas.append(f"- Extremos: {txt_max}; {txt_min}; valor de toda la prueba {fmt(por_muestras(df))}.")

    # 2. Lo habitual
    q10, q90 = float(serie.quantile(0.1)), float(serie.quantile(0.9))
    if habitual:
        lineas.append(f"- Lo habitual: 8 de cada 10 puntos entre {fmt(q10)} y {fmt(q90)}.")

    # 3. Tramos, calculados sobre las muestras
    cortes = _cortes(t0, t1, tramos) if t1 > t0 else [(t0, t1)]
    partes = []
    for i, (a, b) in enumerate(cortes):
        trozo = _en(df, a, b, i == len(cortes) - 1)
        if len(trozo) == 0:
            partes.append(f"min {_minuto(a, t0)}-{_minuto(b, t0)} sin muestras")
            continue
        pico = serie[(serie.index >= a.floor(f"{intervalo}s")) & (serie.index <= b)]
        extra = f" (punto mas alto {fmt(pico.max())})" if alto_es_malo and len(pico) else (
            f" (punto mas bajo {fmt(pico.min())})" if len(pico) else "")
        partes.append(f"min {_minuto(a, t0)}-{_minuto(b, t0)}: {fmt(por_muestras(trozo))}{extra}")
    lineas.append("- Por tramos: " + "; ".join(partes) + ".")

    # 4. Episodios sostenidos fuera de lo habitual
    mediana = float(serie.median())
    if alto_es_malo:
        umbral = max(q90, 2 * mediana)
        fuera = serie > umbral
        sentido = "por encima de"
    else:
        umbral = min(q10, 0.5 * mediana)
        fuera = serie < umbral
        sentido = "por debajo de"
    n_fuera = int(fuera.sum())
    if umbral <= 0 and alto_es_malo:
        # Serie casi siempre en cero (p. ej. tasa de error de una transaccion sana)
        fuera = serie > 0
        n_fuera = int(fuera.sum())
        sentido, umbral = "por encima de", 0.0
    eps = _episodios(serie, fuera) if n_fuera else []
    if not episodios:
        pass
    elif eps:
        txt = "; ".join(
            f"{_ventana(a, b, t0)}, {num(n)} puntos seguidos, promedio {fmt(m)}, "
            + (f"maximo {fmt(mx)}" if alto_es_malo else f"minimo {fmt(mn)}")
            for a, b, n, m, mx, mn in eps)
        lineas.append(f"- Episodios sostenidos {sentido} {fmt(umbral)}: {txt}. "
                      f"En total, {num(n_fuera)} de {num(len(serie))} puntos quedan {sentido} ese valor.")
    elif n_fuera:
        lineas.append(f"- Sin episodios sostenidos {sentido} {fmt(umbral)}: los {num(n_fuera)} puntos "
                      f"que lo cruzan estan aislados (ninguna racha de {RACHA_MINIMA} o mas puntos seguidos).")
    else:
        lineas.append(f"- Ningun punto {sentido} {fmt(umbral)}.")

    # 5. Tendencia: primer tercio contra ultimo tercio
    if t1 > t0:
        tercio = (t1 - t0) / 3
        ini, fin = df[df["timestamp"] < t0 + tercio], df[df["timestamp"] >= t1 - tercio]
        if len(ini) and len(fin):
            v_ini, v_fin = por_muestras(ini), por_muestras(fin)
            base = max(abs(v_ini), 1e-9)
            cambio = (v_fin - v_ini) / base
            if abs(cambio) < 0.2 or abs(v_fin - v_ini) < 1e-6:
                t = "se mantiene"
            else:
                t = "sube" if cambio > 0 else "baja"
            lineas.append(f"- Tendencia: {t} (primer tercio {fmt(v_ini)}, ultimo tercio {fmt(v_fin)}).")
    return "\n".join(lineas)


def _picos(df: pd.DataFrame, t0, n: int = MAX_PICOS) -> str:
    """Los n tiempos maximos, separados al menos 10 s entre si, con su momento."""
    top = df.nlargest(n * 20, "elapsed")[["timestamp", "elapsed"]]
    elegidos: List[Tuple] = []
    for ts, v in zip(top["timestamp"], top["elapsed"]):
        if all(abs((ts - e[0]).total_seconds()) >= 10 for e in elegidos):
            elegidos.append((ts, v))
        if len(elegidos) == n:
            break
    return "; ".join(f"{ms(v)} {_cuando(ts, t0)}" for ts, v in elegidos)


# ====================================================================
# Las series de cada grafica
# ====================================================================

def _ok(df) -> pd.Series:
    s = df["success"]
    if s.dtype != bool:
        s = s.astype(str).str.strip().str.lower().isin(("true", "1", "yes"))
    return s


def _tasa_error(d) -> float:
    return float(100.0 * (1.0 - _ok(d).mean())) if len(d) else 0.0


def serie_tiempos(df, intervalo, nombre, t0=None) -> str:
    return resumir(df, intervalo, nombre, ms, lambda g: g["elapsed"].mean(),
                   lambda d: float(d["elapsed"].mean()), t0=t0)


def serie_latencia(df, intervalo, nombre, t0=None) -> str:
    if "Latency" not in df.columns:
        return f"{nombre}: el JTL no trae la columna de latencia."
    bloque = resumir(df, intervalo, nombre, ms, lambda g: g["Latency"].mean(),
                     lambda d: float(d["Latency"].mean()), t0=t0)
    total, lat = float(df["elapsed"].mean()), float(df["Latency"].mean())
    return bloque + (f"\n- Frente al tiempo total: el tiempo total medio de la prueba es {ms(total)}; "
                     f"la descarga del cuerpo (total menos latencia) suma {ms(max(0.0, total - lat))} de media.")


def serie_error(df, intervalo, nombre, t0=None) -> str:
    if "success" not in df.columns:
        return f"{nombre}: el JTL no trae la columna de exito."
    t0 = df["timestamp"].min() if t0 is None else t0
    # Con pocas peticiones por punto (una transaccion a 2 por segundo) la tasa de
    # un punto salta entre 0%, 50% y 100%: lo habitual y las rachas por punto no
    # dicen nada. En ese caso esas dos lecturas se hacen por MINUTO.
    muestras_por_punto = len(df) / max(1, df["timestamp"].dt.floor(f"{intervalo}s").nunique())
    denso = muestras_por_punto >= 10
    bloque = resumir(
        df, intervalo, nombre, pct,
        lambda g: g.apply(_tasa_error), _tasa_error, t0=t0,
        habitual=denso, episodios=denso)
    if not denso:
        # Minutos contados desde el inicio de la prueba, no del reloj: si no, el
        # primero seria un trozo de 5 s con la hora anterior al arranque.
        minuto = t0 + pd.to_timedelta(((df["timestamp"] - t0).dt.total_seconds() // 60) * 60, unit="s")
        por_min = df.groupby(minuto).apply(_tasa_error).astype(float)
        if len(por_min) >= 3:
            bloque += (f"\n- Por minuto ({num(len(por_min))} minutos, porque cada punto de "
                       f"{num(intervalo)} s tiene muy pocas peticiones): 8 de cada 10 minutos entre "
                       f"{pct(por_min.quantile(0.1))} y {pct(por_min.quantile(0.9))}; el peor minuto "
                       f"{_cuando(por_min.idxmax(), t0)} con {pct(por_min.max())}, el mejor "
                       f"{_cuando(por_min.idxmin(), t0)} con {pct(por_min.min())}.")
    err = df[~_ok(df)]
    if len(err) == 0:
        return bloque + "\n- No hubo ni un fallo en toda la prueba."
    b = df["timestamp"].dt.floor(f"{intervalo}s")
    con_fallo = err["timestamp"].dt.floor(f"{intervalo}s").nunique()
    return bloque + (
        f"\n- Fallos: el primero {_cuando(err['timestamp'].min(), t0)} y el ultimo "
        f"{_cuando(err['timestamp'].max(), t0)}; {num(con_fallo)} de los {num(b.nunique())} "
        f"puntos tienen al menos un fallo.")


def serie_caudal(df, intervalo, nombre, t0=None) -> str:
    iv = max(1, int(intervalo))

    def _por_muestras(d):
        seg = (d["timestamp"].max() - d["timestamp"].min()).total_seconds()
        return float(len(d) / seg) if seg > 0 else float(len(d))

    # Mismo criterio que la tasa de error: con 1 a 4 peticiones por punto, las
    # rachas «por debajo de lo habitual» son ruido de redondeo, no caidas.
    denso = len(df) / max(1, df["timestamp"].dt.floor(f"{iv}s").nunique()) >= 10
    return resumir(df, iv, nombre, _tps, lambda g: g.size() / iv, _por_muestras,
                   t0=t0, alto_es_malo=False, episodios=denso)


def serie_codigos(df, intervalo, t0=None) -> str:
    """Un renglon por codigo: cuantas, cuando aparece y cuando deja de aparecer,
    su pico por segundo y como se reparte por tramos. Es la dimension tiempo que
    los totales acumulados tiraban."""
    if "responseCode" not in df.columns or len(df) == 0:
        return "Codigos de respuesta: el JTL no trae la columna de codigo."
    t0 = df["timestamp"].min() if t0 is None else t0
    t1 = df["timestamp"].max()
    iv = max(1, int(intervalo))
    cortes = _cortes(t0, t1, TRAMOS) if t1 > t0 else [(t0, t1)]
    lineas = ["Codigos de respuesta en el tiempo:"]
    codigos = df["responseCode"].astype(str)
    for code, n in codigos.value_counts().items():
        sub = df[codigos == code]
        por_s = sub.groupby(sub["timestamp"].dt.floor(f"{iv}s")).size() / iv
        reparto = ", ".join(
            num(len(_en(sub, a, b, i == len(cortes) - 1))) for i, (a, b) in enumerate(cortes))
        lineas.append(
            f"- HTTP {code}: {num(n)} respuestas ({pct(100 * n / len(df))} del total). "
            f"Primera {_cuando(sub['timestamp'].min(), t0)}, ultima {_cuando(sub['timestamp'].max(), t0)}; "
            f"pico de {num(por_s.max(), 2)} por segundo {_cuando(por_s.idxmax(), t0)}. "
            f"Por tramos de {num((t1 - t0).total_seconds() / 60 / len(cortes), 1)} minutos: {reparto}.")
    return "\n".join(lineas)


def serie_hilos(df, intervalo, t0=None) -> str:
    """R-D16: la concurrencia de verdad —cuantos hilos, cuando— y como se
    portaron tiempos y errores con cada nivel."""
    col = "allThreads" if "allThreads" in df.columns else ("grpThreads" if "grpThreads" in df.columns else None)
    if col is None:
        return "Hilos activos: el JTL no trae el numero de hilos (allThreads)."
    t0 = df["timestamp"].min() if t0 is None else t0
    iv = max(1, int(intervalo))
    serie = df.groupby(df["timestamp"].dt.floor(f"{iv}s"))[col].max().astype(float).sort_index()
    tope = serie.max()
    en_tope = serie[serie == tope]
    lineas = [
        f"Hilos activos ({num(len(serie))} puntos):",
        f"- Maximo {_hilos(tope)}, alcanzado por primera vez {_cuando(en_tope.index.min(), t0)} "
        f"y por ultima vez {_cuando(en_tope.index.max(), t0)}; {num(len(en_tope))} de "
        f"{num(len(serie))} puntos estan en el maximo.",
        f"- Arranque con {_hilos(serie.iloc[0])} {_cuando(serie.index[0], t0)}; "
        f"final con {_hilos(serie.iloc[-1])} {_cuando(serie.index[-1], t0)}.",
    ]
    # Como respondio el sistema en cada nivel de concurrencia (por muestra).
    niveles = []
    for nivel, d in df.groupby(df[col]):
        niveles.append(f"{_hilos(nivel)}: {num(len(d))} peticiones, tiempo medio "
                       f"{ms(d['elapsed'].mean())}, error {pct(_tasa_error(d))}")
    lineas.append("- Por nivel de concurrencia: " + "; ".join(niveles) + ".")
    return "\n".join(lineas)


# ====================================================================
# Lo que recibe cada seccion
# ====================================================================

def bloques_generales(df_todo: pd.DataFrame, df_main: pd.DataFrame, intervalo: int) -> Dict[str, str]:
    """Las series del informe general (R-D9). `df_todo` es `parser.df` —lo que
    usan las graficas de linea de tiempo, codigos y hilos— y `df_main` las
    transacciones principales —las de Response Times y TPS por transaccion—."""
    t0 = df_todo["timestamp"].min()
    cab = cabecera(df_todo, intervalo)

    # Response Times: 1 s por transaccion, como su grafica (GRAF1).
    rt = []
    labels = (df_main.groupby("label")["elapsed"].max().sort_values(ascending=False).index.tolist())
    for label in labels[:MAX_LABELS_RT]:
        sub = df_main[df_main["label"] == label]
        rt.append(serie_tiempos(sub, 1, f"«{label}», tiempo medio por segundo", t0=t0)
                  + f"\n- Sus tres tiempos mas altos: {_picos(sub, t0)}.")
    if len(labels) > MAX_LABELS_RT:
        rt.append(f"(Sin detalle de tiempo, por espacio: {', '.join(labels[MAX_LABELS_RT:])}.)")

    tps = [serie_caudal(df_main, intervalo, "Caudal total", t0=t0)]
    for label in sorted(df_main["label"].unique()):
        sub = df_main[df_main["label"] == label]
        por_s = sub.groupby(sub["timestamp"].dt.floor(f"{intervalo}s")).size() / intervalo
        tps.append(f"- «{label}»: minimo {_tps(por_s.min())} {_cuando(por_s.idxmin(), t0)}, "
                   f"maximo {_tps(por_s.max())} {_cuando(por_s.idxmax(), t0)}.")

    return {
        "cabecera": cab,
        "response_times": "\n\n".join(rt),
        "latency": serie_latencia(df_todo, intervalo, "Latencia media", t0=t0),
        "error_rate": serie_error(df_todo, intervalo, "Tasa de error", t0=t0),
        "codes_per_second": serie_codigos(df_todo, intervalo, t0=t0),
        "transactions_per_second": "\n".join(tps),
        "active_threads": serie_hilos(df_todo, intervalo, t0=t0),
    }


def bloques_transaccion(df_tx: pd.DataFrame, intervalo: int = 1) -> Dict[str, str]:
    """Las 5 series de UNA transaccion, con la clave de su seccion."""
    t0 = df_tx["timestamp"].min()
    return {
        "cabecera": cabecera(df_tx, intervalo),
        "chart_response_times": serie_tiempos(df_tx, intervalo, "Tiempo medio por segundo", t0=t0)
                                + f"\n- Sus tres tiempos mas altos: {_picos(df_tx, t0)}.",
        "chart_latency": serie_latencia(df_tx, intervalo, "Latencia media", t0=t0),
        "chart_error_rate": serie_error(df_tx, intervalo, "Tasa de error", t0=t0),
        "chart_codes": serie_codigos(df_tx, intervalo, t0=t0),
        "chart_tps": serie_caudal(df_tx, intervalo, "Caudal", t0=t0),
    }


# ====================================================================
# R-D15: los mensajes de error reales
# ====================================================================

def mensajes_de_error(df_err: pd.DataFrame, top: int = 2) -> Dict[Tuple[str, str], str]:
    """(label, codigo) -> los mensajes mas frecuentes con su conteo.

    Usa `failureMessage` (lo que dijo la asercion) y, si viene vacio,
    `responseMessage` (lo que dijo el servidor). Si el JTL no trae ninguno de
    los dos, la clave no aparece y el prompt lo dice.
    """
    out: Dict[Tuple[str, str], str] = {}
    if df_err is None or len(df_err) == 0:
        return out
    cols = [c for c in ("failureMessage", "responseMessage") if c in df_err.columns]
    if not cols:
        return out
    msg = pd.Series("", index=df_err.index)
    for c in reversed(cols):   # failureMessage manda si tiene texto
        v = df_err[c].fillna("").astype(str).str.strip()
        msg = v.where(v != "", msg)
    tmp = df_err.assign(_msg=msg.str.slice(0, 120))
    for (label, code), g in tmp.groupby(["label", "responseCode"]):
        vc = g["_msg"][g["_msg"] != ""].value_counts().head(top)
        if len(vc):
            out[(str(label), str(code))] = "; ".join(f"«{m}» ({num(n)})" for m, n in vc.items())
    return out


# ====================================================================
# R-D17: los hechos de la prueba, calculados, para la lectura base
# ====================================================================

def hechos_de_la_prueba(df_main: pd.DataFrame, intervalo: int) -> str:
    """Hechos que no dependen de la redaccion: que transaccion concentra los
    fallos, si el fallo es puntual o sostenido y cual es la mas lenta. Van al
    resumen, que es la primera llamada y fija la lectura que las demas reciben."""
    if df_main is None or len(df_main) == 0:
        return ""
    ok = _ok(df_main)
    total_err = int((~ok).sum())
    t0 = df_main["timestamp"].min()
    lineas = ["HECHOS DE LA PRUEBA (calculados sobre el JTL; son la base de la lectura):"]
    if total_err:
        por_label = (~ok).groupby(df_main["label"]).agg(["sum", "count"])
        por_label = por_label[por_label["sum"] > 0].sort_values("sum", ascending=False)
        for label, fila in por_label.iterrows():
            lineas.append(
                f"- «{label}» tiene {num(fila['sum'])} fallos de {num(fila['count'])} peticiones "
                f"({pct(100 * fila['sum'] / fila['count'])} de las suyas) y concentra el "
                f"{pct(100 * fila['sum'] / total_err)} de todos los fallos de la prueba.")
        err = df_main[~ok]
        b = df_main["timestamp"].dt.floor(f"{intervalo}s")
        n_puntos = b.nunique()
        con_fallo = err["timestamp"].dt.floor(f"{intervalo}s").nunique()
        cobertura = con_fallo / max(1, n_puntos)
        forma = ("repartidos a lo largo de toda la prueba" if cobertura >= 0.5 else
                 "presentes en una parte de la prueba" if cobertura >= 0.15 else
                 "concentrados en pocos momentos")
        lineas.append(
            f"- Los fallos aparecen en {num(con_fallo)} de los {num(n_puntos)} puntos de "
            f"{num(intervalo)} s ({pct(100 * cobertura, 1)}): {forma}. Primero "
            f"{_cuando(err['timestamp'].min(), t0)}, ultimo {_cuando(err['timestamp'].max(), t0)}.")
    else:
        lineas.append("- No hubo ni un fallo en toda la prueba.")
    medias = df_main.groupby("label")["elapsed"].agg(["mean", "max"])
    lenta, pico = medias["mean"].idxmax(), medias["max"].idxmax()
    lineas.append(f"- La transaccion mas lenta en promedio es «{lenta}» ({ms(medias.loc[lenta, 'mean'])}); "
                  f"el tiempo mas alto de la prueba es de «{pico}» ({ms(medias.loc[pico, 'max'])}).")
    return "\n".join(lineas)
