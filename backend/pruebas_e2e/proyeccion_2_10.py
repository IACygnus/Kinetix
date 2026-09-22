"""2.10 — Proyeccion del tiempo de generacion con los recortes de la ETAPA 2.

No gasta ni una llamada a la IA: usa la telemetria REAL de las dos corridas de
linea base (etapa 1) y quita de ella exactamente las llamadas que la etapa 2 ha
retirado del producto.

Las secciones por transaccion se reconocen por el prefijo `txreport_`, que es el
que emite la telemetria.
"""
import json
from collections import defaultdict

RETIRADAS = {
    "chart_throughput": "D19 — grafica Throughput Over Time (general)",
    "txreport_conclusions": "D20 — conclusiones por transaccion",
    "txreport_recommendations": "D20 — recomendaciones por transaccion",
}

for n in (1, 2):
    d = json.load(open(f"/tmp/baseline{n}.json"))
    t = [x for x in d["telemetria"] if x.get("outcome") == "ok"]
    corr = d["corrida"]
    quitadas = [x for x in t if x["section"] in RETIRADAS]
    total = sum(x["latency_ms"] for x in t) / 1000
    quit_s = sum(x["latency_ms"] for x in quitadas) / 1000
    print(f"--- corrida {n}: {corr['etiqueta']}, {len(corr['transacciones'])} transacciones")
    print(f"  llamadas                  {len(t):3d}   ->  {len(t) - len(quitadas):3d}")
    print(f"  latencia total de IA    {total:7.1f} s ->  {total - quit_s:7.1f} s")
    print(f"  ahorro                  {quit_s:7.1f} s   ({100 * quit_s / total:.1f} %)")
    print(f"  tiempo percibido T2-T0  {corr['T2_T0_s']:7.1f} s ->  {corr['T2_T0_s'] - quit_s:7.1f} s")
    det = defaultdict(lambda: [0, 0.0])
    for x in quitadas:
        det[x["section"]][0] += 1
        det[x["section"]][1] += x["latency_ms"] / 1000
    for k, (c, s) in sorted(det.items()):
        print(f"    {RETIRADAS[k]:<48} {c} x {s / c:5.1f} s = {s:6.1f} s")
