"""Comprueba sobre el HTML real lo que pide la ETAPA 2 en el export individual."""
import re, sys
h = open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/html_2_8b.txt", encoding="utf-8").read()
i_tx = h.find("INFORME DE CADA TRANSACCION")
i_con = h.find(">Conclusiones<")
bloques = len(re.findall(r"background:#0a1628;color:white;padding:1\.1rem 1\.4rem", h))
graf_tx = len(re.findall(r"id=\"chart-tx\d+-", h))
pruebas = [
    ("sin la grafica Throughput Over Time", "Throughput Over Time" not in h),
    ("sin el div chart-throughput", "chart-throughput" not in h),
    ("el KPI Throughput sigue", "Throughput</div>" in h or ">Throughput<" in h),
    ("sin la palabra prohibida mini-informe", "mini-informe" not in h.lower()),
    ("las transacciones van ANTES de las conclusiones", 0 < i_tx < i_con),
    (f"un bloque por transaccion ({bloques})", bloques >= 1),
    (f"5 graficas por transaccion ({graf_tx} en total)", graf_tx == 5 * bloques),
    ("sin conclusiones por transaccion", "Conclusiones de la Transaccion" not in h),
    ("sin recomendaciones por transaccion", "Recomendaciones de la Transaccion" not in h),
    ("las graficas por transaccion llevan controles",
     h.count("chart-controls") >= 6 + 5 * bloques),
    ("titulos del general en el bloque por transaccion",
     h.count("Latency Over Time") >= 1 + bloques),
]
fallos = 0
for t, ok in pruebas:
    print(f"{'PASA ' if ok else 'FALLA'} | {t}")
    fallos += 0 if ok else 1
print(f"\n=== {'TODO PASA' if not fallos else f'{fallos} FALLOS'} ===")
sys.exit(1 if fallos else 0)
