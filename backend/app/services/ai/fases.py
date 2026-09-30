"""
BLOQUE 2.1 — las fases de la prueba: subida, carga sostenida y bajada.

Una sola definicion para todo el analisis (el informe general, el de cada
transaccion y las pruebas). Nace del reporte 136: 5 de los 23 momentos que
citaban las conclusiones caian en una rampa, porque ningun prompt salvo el de
usuarios activos sabia donde estaban.

Las fases salen de los USUARIOS ACTIVOS (`allThreads`, o `grpThreads` si no
esta), agrupados por segundo entero desde el inicio de la prueba:
  - subida: hasta el primer segundo en que se alcanza el 95 % del maximo;
  - carga sostenida: de ahi hasta el ultimo segundo en ese 95 % o mas;
  - bajada: lo que queda despues.
Si el JTL no trae hilos, las fases son «no disponibles»: nunca se inventan.

Se calculan SIEMPRE sobre la prueba entera, aunque la seccion sea de una sola
transaccion: el informe general y el de la transaccion tienen que decir los
mismos minutos.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

from app.services.ai.estilo import num, pct

UMBRAL = 0.95   # fraccion del maximo de hilos que cuenta como carga sostenida

# Concentracion (BLOQUE 2.1b): ventanas proporcionales a la carga sostenida.
VENTANAS = 30          # unas 30 por prueba
VENTANA_MIN_S = 5      # ninguna de menos de 5 s
MITAD = 0.5            # se busca cuantas ventanas juntan la mitad de los eventos
CONCENTRADO = 0.2      # si basta con el 20 % de las ventanas o menos, estan concentrados
MAX_ZONAS = 3          # zonas que se nombran

INSTRUCCION_FASES = (
    "Lo que ocurra en la subida o en la bajada se describe como tal (arranque o cierre de "
    "la prueba) y no se usa como hallazgo principal: el hallazgo principal es lo que pasa "
    "con la carga sostenida.")


def mmss(seg: float) -> str:
    """«M:SS» desde el inicio de la prueba."""
    s = max(0, int(round(seg)))
    return f"{s // 60}:{s % 60:02d}"


@dataclass
class Fases:
    disponible: bool
    t0: Optional[pd.Timestamp] = None
    duracion_s: float = 0.0
    max_hilos: Optional[int] = None
    subida_hasta_s: Optional[float] = None    # primer segundo en el 95 % del maximo
    bajada_desde_s: Optional[float] = None    # ultimo segundo en el 95 % del maximo
    ultimo_s: Optional[float] = None          # ultimo segundo entero con muestras
    motivo: str = ""

    @property
    def sin_subida(self) -> bool:
        return self.disponible and self.subida_hasta_s <= 0

    @property
    def sin_bajada(self) -> bool:
        return self.disponible and self.bajada_desde_s >= self.ultimo_s

    def fase_de(self, seg: float) -> Optional[str]:
        """'subida' / 'sostenida' / 'bajada' para un momento en segundos desde el
        inicio. None si las fases no estan disponibles."""
        if not self.disponible:
            return None
        s = math.floor(seg)   # por segundo entero, como se calcularon las fases
        if s < self.subida_hasta_s:
            return "subida"
        if s > self.bajada_desde_s:
            return "bajada"
        return "sostenida"

    def sostenida(self) -> Tuple[float, float]:
        """[inicio, fin) de la carga sostenida en segundos desde el inicio. Sin
        fases, la prueba entera."""
        if not self.disponible:
            return 0.0, self.duracion_s + 1e-9
        return self.subida_hasta_s, min(self.bajada_desde_s + 1, self.duracion_s + 1e-9)

    def linea(self) -> str:
        """La linea que reciben los prompts, con su instruccion."""
        if not self.disponible:
            return (f"FASES DE LA PRUEBA: no disponibles ({self.motivo}). No se distingue la "
                    f"subida ni la bajada de la carga sostenida.")
        fin = mmss(self.duracion_s)
        partes = [("Sin subida" if self.sin_subida else f"Subida 0:00–{mmss(self.subida_hasta_s)}"),
                  f"Carga sostenida {mmss(self.subida_hasta_s)}–"
                  f"{fin if self.sin_bajada else mmss(self.bajada_desde_s)}",
                  ("Sin bajada" if self.sin_bajada else f"Bajada {mmss(self.bajada_desde_s)}–{fin}")]
        hilos = "1 usuario" if self.max_hilos == 1 else f"{self.max_hilos} usuarios"
        return (f"FASES DE LA PRUEBA (por usuarios activos; carga sostenida = al menos el "
                f"{int(UMBRAL * 100)} % del maximo de {hilos}): " + " · ".join(partes) + ".\n"
                + INSTRUCCION_FASES)


def calcular(df: pd.DataFrame) -> Fases:
    """Las fases de una prueba a partir de su DataFrame (con `timestamp`)."""
    if df is None or len(df) == 0 or "timestamp" not in df.columns:
        return Fases(False, motivo="la prueba no tiene muestras")
    t0 = df["timestamp"].min()
    seg = (df["timestamp"] - t0).dt.total_seconds()
    col = next((c for c in ("allThreads", "grpThreads") if c in df.columns), None)
    if col is None:
        # Sin fases, pero con inicio y duracion: la concentracion mira la prueba entera.
        return Fases(False, t0=t0, duracion_s=float(seg.max()),
                     motivo="el JTL no trae el numero de usuarios activos")
    hilos = pd.to_numeric(df[col], errors="coerce")
    por_seg = hilos.groupby(seg.astype(int)).max().dropna().sort_index()
    if len(por_seg) == 0 or por_seg.max() <= 0:
        return Fases(False, t0=t0, duracion_s=float(seg.max()),
                     motivo="el JTL no trae el numero de usuarios activos")
    tope = por_seg.max()
    altos = por_seg[por_seg >= UMBRAL * tope]
    return Fases(True, t0=t0, duracion_s=float(seg.max()), max_hilos=int(tope),
                 subida_hasta_s=float(altos.index.min()), bajada_desde_s=float(altos.index.max()),
                 ultimo_s=float(seg.astype(int).max()))


# ====================================================================
# BLOQUE 2.1b — donde se concentran los eventos (fallos, muestras lentas)
# ====================================================================

def _reloj(f: Fases, seg: float) -> str:
    return (f.t0 + pd.Timedelta(seconds=seg)).strftime("%H:%M:%S")


def _zona(f: Fases, a: float, b: float) -> str:
    return f"min {mmss(a)}–{mmss(b)} ({_reloj(f, a)}–{_reloj(f, b)})"


def concentracion(ts: pd.Series, f: Fases, que: str = "fallos", corto: bool = False) -> str:
    """Donde se concentran unos eventos DENTRO de la carga sostenida.

    `ts` son los `timestamp` de los eventos (fallos, muestras lentas) y `f` las
    fases de la prueba entera. La carga sostenida se parte en ventanas de
    duracion/30 (minimo 5 s); se mira cuantas ventanas hacen falta para juntar
    la mitad de los eventos. Si basta con el 20 % o menos, estan concentrados y
    se nombran las zonas (ventanas contiguas unidas) con su parte del total; si
    no, «repartidos sin concentracion». Lo que cae en las rampas se cuenta
    aparte. Sin fases, se mira la prueba entera y se dice.

    No da el primer ni el ultimo evento: eso es lo que dejo de mandarse (136).
    `corto` es la forma de una celda de tabla (la de errores).
    """
    if ts is None or len(ts) == 0 or f.t0 is None:
        return ""
    seg = (pd.to_datetime(ts) - f.t0).dt.total_seconds().to_numpy()
    total = len(seg)
    a, b = f.sostenida()
    dentro = seg[(seg >= a) & (seg < b)]
    n_sub = int((seg < a).sum()) if f.disponible else 0
    n_baj = total - len(dentro) - n_sub if f.disponible else 0
    rampas = n_sub + n_baj

    if f.disponible and len(dentro) == 0:
        return (f"ninguno en la carga sostenida: los {num(total)} {que} caen en las rampas "
                f"(subida {num(n_sub)}, bajada {num(n_baj)})")

    largo = max(b - a, 1e-9)
    ancho = float(max(VENTANA_MIN_S, round(largo / VENTANAS)))   # segundos enteros: lo que se dice es lo que se cuenta
    n_ven = max(1, math.ceil(largo / ancho))
    idx = ((dentro - a) // ancho).astype(int).clip(0, n_ven - 1)
    cuenta = pd.Series(idx).value_counts().reindex(range(n_ven), fill_value=0)
    n = len(dentro)

    orden = cuenta.sort_values(ascending=False, kind="stable")
    acum, necesarias = 0, 0
    for c in orden:
        acum += c
        necesarias += 1
        if acum >= MITAD * n:
            break
    concentrado = n_ven >= 5 and necesarias <= CONCENTRADO * n_ven

    if concentrado:
        # Un pico a caballo entre dos ventanas se contaria a medias: cada zona se
        # extiende a las contiguas que tambien esten cargadas (el doble de lo parejo).
        cargada = 2 * n / n_ven
        elegidas = set(orden.index[:necesarias])
        for i in list(elegidas):
            j = i - 1
            while j >= 0 and j not in elegidas and cuenta[j] >= cargada:
                elegidas.add(j)
                j -= 1
            j = i + 1
            while j < n_ven and j not in elegidas and cuenta[j] >= cargada:
                elegidas.add(j)
                j += 1
        elegidas = sorted(elegidas)
        zonas: List[Tuple[int, int]] = []
        for i in elegidas:
            if zonas and i == zonas[-1][1] + 1:
                zonas[-1] = (zonas[-1][0], i)
            else:
                zonas.append((i, i))
        zonas.sort(key=lambda z: -int(cuenta[z[0]:z[1] + 1].sum()))
        partes = []
        for i, j in zonas[:MAX_ZONAS]:
            c = int(cuenta[i:j + 1].sum())
            partes.append(f"{_zona(f, a + i * ancho, min(b, a + (j + 1) * ancho))}: "
                          f"{num(c)} de {num(n)} ({pct(100 * c / n, 1)})")
        resto = len(zonas) - MAX_ZONAS
        cuerpo = ("concentrados en " + "; ".join(partes)
                  + (f"; y {num(resto)} zona(s) mas" if resto > 0 else ""))
    else:
        mayor = int(cuenta.max())
        cuerpo = (f"repartidos sin concentracion: la ventana de {num(ancho)} s con mas {que} "
                  f"reune el {pct(100 * mayor / n, 1)}, frente al {pct(100 / n_ven, 1)} si fuera parejo")

    if corto:
        # Celda de tabla: sin la frase de la ventana mayor, que no cabe.
        cuerpo = cuerpo if concentrado else "repartidos sin concentracion"
        extra = f"; {num(rampas)} en las rampas" if rampas else ""
        return cuerpo + extra

    if not f.disponible:
        return (f"{num(total)} {que} (fases no disponibles: se mira la prueba entera, en ventanas "
                f"de {num(ancho)} s): {cuerpo}")
    cabeza = f"de {num(total)} {que}, {num(n)} ({pct(100 * n / total, 1)}) caen en la carga sostenida"
    if rampas:
        cabeza += f" y {num(rampas)} en las rampas (subida {num(n_sub)}, bajada {num(n_baj)})"
    return f"{cabeza}. Dentro de la carga sostenida, en ventanas de {num(ancho)} s: {cuerpo}"
