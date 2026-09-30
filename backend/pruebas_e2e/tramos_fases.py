"""BLOQUE 2.1 — ¿cuantos tramos de la serie resumida mezclan rampa y carga sostenida?

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/tramos_fases.py <id8> [<id8> ...]

Los tramos de `resumen_serie.py` son TRAMOS (6) ventanas iguales de la prueba
entera; las fases, las de `services/ai/fases.py`. Un tramo «mezcla» si contiene
segundos de una rampa y de la carga sostenida. Sin IA; la base en solo lectura.
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from fases_r2 import _ejecucion
from app.services.ai import fases as F
from app.services.ai.resumen_serie import TRAMOS


def tramos(df):
    f = F.calcular(df)
    if not f.disponible:
        return None, f
    t0, t1 = df["timestamp"].min(), df["timestamp"].max()
    dur = (t1 - t0).total_seconds()
    out = []
    for i in range(TRAMOS):
        a, b = dur * i / TRAMOS, dur * (i + 1) / TRAMOS
        fs = {f.fase_de(s) for s in range(int(a), int(b) + (1 if i == TRAMOS - 1 else 0)) if a <= s <= b}
        out.append((a, b, fs))
    return out, f


def main(ids):
    total = mezclan = 0
    for id8 in ids:
        tr, f = tramos(asyncio.run(_ejecucion(id8)))
        if tr is None:
            print(f"{id8}: fases no disponibles")
            continue
        m = [t for t in tr if "sostenida" in t[2] and len(t[2]) > 1]
        total += len(tr)
        mezclan += len(m)
        print(f"{id8}: {f.linea().splitlines()[0]}")
        for a, b, fs in tr:
            marca = "  MEZCLA" if ("sostenida" in fs and len(fs) > 1) else ""
            print(f"   {F.mmss(a)}-{F.mmss(b)}: {', '.join(sorted(fs))}{marca}")
        print(f"   -> {len(m)} de {len(tr)} tramos mezclan rampa y carga sostenida")
    print(f"TOTAL: {mezclan} de {total}")


if __name__ == "__main__":
    main(sys.argv[1:])
