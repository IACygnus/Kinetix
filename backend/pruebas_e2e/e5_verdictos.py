"""ETAPA 5.3 — los criterios del panel llegan al veredicto del informe.

Comprueba sobre E5-panel que:
  1. `per_transaction` quedo guardado tal como lo arma el panel (D44).
  2. El veredicto por transaccion del informe (tabla KNX-09) usa el criterio
     PROPIO donde lo hay y el GLOBAL donde no.
  3. Ese veredicto es EXACTAMENTE el que calculo el panel: se vuelve a correr la
     regla sobre las mismas metricas y tiene que dar lo mismo.
  4. Y se deja escrito el caso que lo demuestra: con el global, `1. Auth` seria
     APTO; con su criterio propio es NO APTO.

CERO llamadas a la IA.

    python3 /tmp/e2e/e5_verdictos.py <execution_id>
"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")

EID = sys.argv[1] if len(sys.argv) > 1 else "c33488cb-5f1c-499b-86b3-4b58642c31cb"
SALIDA_TS = "/tmp/e3/e5_metricas_para_ts.json"

fallos = []


def comprobar(ok, texto):
    print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
    if not ok:
        fallos.append(texto)


async def main():
    import pandas as pd
    from sqlalchemy import select

    from app.db.models.test import TestExecution
    from app.db.session import AsyncSessionLocal
    from app.services.ai.gemini import compute_per_transaction_verdicts
    from app.services.jtl.jtl_parser import JTLParser

    async with AsyncSessionLocal() as db:
        ej = (await db.execute(select(TestExecution).where(TestExecution.id == EID))).scalar_one()
        criterios = dict(ej.acceptance_criteria_json or {})
        jtl = f"/app/uploads/{ej.jtl_filename}"

    guardados = criterios.get("verdicts_per_transaction") or {}
    per_txn = criterios.get("per_transaction") or {}
    print(f"ejecucion: {ej.name}")
    print(f"globales: {criterios.get('response_time')} ms · {criterios.get('availability')}%")
    print(f"per_transaction: {json.dumps(per_txn, ensure_ascii=False)}")

    comprobar(bool(per_txn), "los criterios propios del panel quedaron guardados")
    comprobar("1. Auth" in per_txn, "'1. Auth' tiene criterios propios")
    comprobar(float(per_txn.get("1. Auth", {}).get("response_time", 0)) == 300,
              "su tiempo de respuesta propio es 300 ms")
    comprobar("2. Get Booking" not in per_txn,
              "'2. Get Booking' NO tiene criterios propios: va con los globales")

    # --- 3. Se vuelve a correr la regla sobre las mismas metricas ---
    import glob
    encontrados = glob.glob(f"/app/uploads/*{ej.jtl_filename}")
    parser = JTLParser(encontrados[0] if encontrados else jtl)
    parser.parse()
    resumen = parser.get_summary_table_data()
    recalculado = compute_per_transaction_verdicts(
        resumen, criterios)["verdicts_per_transaction"]

    distintos = {k: (v, recalculado.get(k)) for k, v in guardados.items()
                 if recalculado.get(k) != v}
    comprobar(not distintos,
              "el veredicto guardado coincide con el que da la regla"
              + (f" — difieren {distintos}" if distintos else ""))

    comprobar(guardados.get("1. Auth") == "NO APTO",
              f"'1. Auth' es NO APTO por su criterio propio ({guardados.get('1. Auth')})")
    comprobar(guardados.get("2. Get Booking") == "APTO",
              f"'2. Get Booking' es APTO por los globales ({guardados.get('2. Get Booking')})")

    # --- 4. La demostracion: con el global, Auth cumpliria ---
    solo_globales = {k: v for k, v in criterios.items() if k != "per_transaction"}
    con_globales = compute_per_transaction_verdicts(
        resumen, solo_globales)["verdicts_per_transaction"]
    comprobar(con_globales.get("1. Auth") == "APTO",
              f"con el criterio GLOBAL '1. Auth' seria APTO ({con_globales.get('1. Auth')}): "
              f"la diferencia la hace el criterio propio")

    # Las metricas de esas dos, para que el lado TS corra los mismos casos.
    casos = []
    for _, fila in resumen.iterrows():
        etiqueta = str(fila["label"])
        if etiqueta not in ("1. Auth", "2. Get Booking"):
            continue
        propios = per_txn.get(etiqueta, {})
        casos.append({
            "nombre": f"{etiqueta} (informe E5-panel)",
            "metricas": {"promedio": float(fila["promedio"]), "p90": float(fila["p90"]),
                         "max": float(fila["max"]), "tasa_error": float(fila["tasa_error"])},
            "criterios": {
                "response_time": propios.get("response_time", criterios.get("response_time")),
                "availability": propios.get("availability", criterios.get("availability")),
            },
            "esperado": guardados[etiqueta],
        })
    json.dump({"casos": casos, "senales": []}, open(SALIDA_TS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\ncasos para el lado TS -> {SALIDA_TS}")
    for c in casos:
        print(f"  {c['nombre']}: p90={c['metricas']['p90']:.0f} ms, "
              f"limite={c['criterios']['response_time']} ms -> {c['esperado']}")

    print("\n" + "=" * 62)
    if fallos:
        print(f"{len(fallos)} FALLOS:")
        for f in fallos:
            print("  -", f)
        return 1
    print("LOS CRITERIOS DEL PANEL LLEGAN AL VEREDICTO DEL INFORME")
    return 0


sys.exit(asyncio.run(main()))
