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

from dataclasses import dataclass
from typing import Optional

import pandas as pd

UMBRAL = 0.95   # fraccion del maximo de hilos que cuenta como carga sostenida

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
        if seg < self.subida_hasta_s:
            return "subida"
        if seg > self.bajada_desde_s:
            return "bajada"
        return "sostenida"

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
    col = next((c for c in ("allThreads", "grpThreads") if c in df.columns), None)
    if col is None:
        return Fases(False, motivo="el JTL no trae el numero de usuarios activos")
    t0 = df["timestamp"].min()
    seg = (df["timestamp"] - t0).dt.total_seconds()
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
