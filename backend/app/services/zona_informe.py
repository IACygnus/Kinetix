"""La zona horaria de los informes — una sola definicion (reporte 146).

El `timeStamp` de un JTL son milisegundos de epoca: UTC. La base guarda
`start_time`/`end_time` en UTC sin zona, y asi se queda. Lo que se ENSENA
(cabecera, ejes de las graficas, horas de reloj de los prompts) va en la hora
de esta zona, sea cual sea la del servidor o la del navegador.

- `a_informe(x)`: UTC sin zona -> hora del informe sin zona. Es la que se pinta.
- `a_utc(x)`:     hora del informe sin zona -> UTC sin zona. Es la que se guarda
                  y la que se compara con cualquier otra fuente en UTC.

Las dos aceptan `datetime`, `pd.Timestamp`, `pd.Series` de fechas y `None`.
Sin zona a la salida a proposito: matplotlib, Plotly y `new Date()` del
navegador pintan una hora sin zona tal cual llega.

Configurable con `REPORT_TIMEZONE` (por defecto America/Bogota). No hace falta
definirla.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

ZONA_INFORMES = os.getenv("REPORT_TIMEZONE") or "America/Bogota"
_ZONA = ZoneInfo(ZONA_INFORMES)


def _convertir(x, desde, hacia):
    if x is None:
        return None
    if isinstance(x, pd.Series):
        s = pd.to_datetime(x)
        if s.dt.tz is None:
            s = s.dt.tz_localize(desde)
        return s.dt.tz_convert(hacia).dt.tz_localize(None)
    if isinstance(x, pd.Timestamp):
        if pd.isna(x):
            return x
        t = x.tz_localize(desde) if x.tzinfo is None else x
        return t.tz_convert(hacia).tz_localize(None)
    if isinstance(x, datetime):
        t = x.replace(tzinfo=desde) if x.tzinfo is None else x
        return t.astimezone(hacia).replace(tzinfo=None)
    return x


def a_informe(x):
    """UTC (sin zona o con ella) -> hora del informe, sin zona."""
    return _convertir(x, ZoneInfo("UTC"), _ZONA)


def a_utc(x):
    """Hora del informe (sin zona o con ella) -> UTC, sin zona."""
    return _convertir(x, _ZONA, ZoneInfo("UTC"))
