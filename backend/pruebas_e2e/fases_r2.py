"""ETAPA R2 — ¿en que fase de la prueba cae cada momento que citan las conclusiones?

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/fases_r2.py <id8> [<id8> ...]

Para cada ejecucion lee su JTL (solo lectura) y saca las fases con
`services/ai/fases.py` (BLOQUE 2.1: una sola definicion), por hilos activos:
  - rampa de subida: desde el inicio hasta que se alcanza el 95 % del maximo;
  - meseta: mientras se esta en el 95 % o mas;
  - rampa de bajada: desde la ultima vez en el 95 % hasta el final.
Despues busca en las conclusiones del «despues» (/tmp/r2/corrida_despues_<id8>.json)
cada momento citado —«min M:SS» o una hora del reloj— y dice en que fase cae.
No imprime frases: solo el momento y su fase (el reporte no copia textos de clientes).
"""
import asyncio
import json
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models.test import TestExecution
from app.api.v1.endpoints.upload import _parse_execution_df
from app.services.ai import fases as F

MIN = re.compile(r"\bmin(?:uto)?s?\.?\s*(\d{1,3})(?::(\d{2}))?\b", re.I)
RELOJ = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])")
INICIO = re.compile(r"la prueba va de (\d{1,2}):(\d{2}):(\d{2})")


def fmt(s):
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


async def _ejecucion(id8):
    motor = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        connect_args={"server_settings": {"default_transaction_read_only": "on"}})
    sesion = async_sessionmaker(motor, class_=AsyncSession, autoflush=False)
    async with sesion() as db:
        ex = (await db.execute(select(TestExecution).where(
            TestExecution.id.cast(__import__("sqlalchemy").String).like(f"{id8}%")))).scalar_one()
        _, df = _parse_execution_df(ex)
        await db.rollback()
    await motor.dispose()
    return df


_NOMBRE = {"subida": "rampa de subida", "sostenida": "meseta", "bajada": "rampa de bajada"}


def fases(df):
    """BLOQUE 2.1: la definicion vive en `services/ai/fases.py`; aqui solo se lee."""
    x = F.calcular(df)
    if not x.disponible:
        raise SystemExit(f"fases no disponibles: {x.motivo}")
    return {"duracion": x.duracion_s, "max_hilos": x.max_hilos,
            "subida_hasta": x.subida_hasta_s, "bajada_desde": x.bajada_desde_s, "_fases": x}


def fase_de(seg, f):
    return _NOMBRE[f["_fases"].fase_de(seg)]


def main(ids):
    out = []
    for id8 in ids:
        f = fases(asyncio.run(_ejecucion(id8)))
        d = json.load(open(f"/tmp/r2/corrida_despues_{id8}.json", encoding="utf-8"))
        conc = (d.get("general") or {}).get("ai_conclusions") or ""
        prompts = " ".join(c["prompt"] for c in d["detalle"])
        m0 = INICIO.search(prompts)
        inicio = timedelta(hours=int(m0[1]), minutes=int(m0[2]), seconds=int(m0[3])) if m0 else None
        momentos = []
        usados = []
        for m in MIN.finditer(conc):
            seg = int(m[1]) * 60 + int(m[2] or 0)
            momentos.append({"citado": m[0], "seg": seg, "fase": fase_de(seg, f)})
            usados.append(m.span())
        for m in RELOJ.finditer(conc):
            if any(a <= m.start() < b for a, b in usados):
                continue   # el «5:02» de «min 5:02» ya esta contado
            if m[3] is None:
                # «M:SS» suelto es el final de un intervalo: «entre min 10:18 y 10:19»,
                # «de min 2:01 a 2:07». Es un minuto de la prueba, no una hora.
                seg = int(m[1]) * 60 + int(m[2])
                momentos.append({"citado": f"… {m[0]} (fin de intervalo)", "seg": seg, "fase": fase_de(seg, f)})
                continue
            if inicio is None:
                momentos.append({"citado": m[0], "seg": None, "fase": "sin hora de inicio"})
                continue
            hora = timedelta(hours=int(m[1]), minutes=int(m[2]), seconds=int(m[3] or 0))
            seg = (hora - inicio).total_seconds()
            if seg < 0:
                seg += 86400
            fase = fase_de(seg, f) if 0 <= seg <= f["duracion"] + 1 else "fuera de la prueba (¿no es una hora?)"
            momentos.append({"citado": m[0], "seg": seg, "fase": fase})
        out.append({"id": id8, "fases": {"duracion": fmt(f["duracion"]), "max_hilos": f["max_hilos"],
                                          "subida_hasta": fmt(f["subida_hasta"]), "bajada_desde": fmt(f["bajada_desde"])},
                    "momentos": [{**m, "min": fmt(m["seg"]) if m["seg"] is not None else None} for m in momentos]})
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
