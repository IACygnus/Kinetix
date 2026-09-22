"""Vuelca el HTML que build_pdf_html genera, para comparar antes y despues.

`build_pdf_html` es una funcion pura: con la misma entrada devuelve el mismo HTML.
Esto la llama con una entrada fija y guarda el resultado, de modo que un refactor
de extraccion (condicion C1) se pueda demostrar con un diff vacio.

Uso (dentro de jmeter_backend):
    python3 /tmp/e2e/pdf_equivalencia.py /tmp/pdf_antes.html
    ...cambio de codigo...
    python3 /tmp/e2e/pdf_equivalencia.py /tmp/pdf_despues.html
    diff /tmp/pdf_antes.html /tmp/pdf_despues.html
"""
import sys
from collections import defaultdict

sys.path.insert(0, "/app")

from app.services.export.report_generator import build_pdf_html   # noqa: E402

IMG = "IMG_BASE64_FIJA"

CHARTS = {k: f"{IMG}_{k}" for k in
          ("rt_label", "throughput", "latency", "error_rate", "codes", "tps", "threads", "pie")}

IA = {k: f"Texto de analisis de {k}." for k in
      ("summary", "errors", "responseTimes", "throughput", "latency", "errorRate",
       "codesPerSecond", "tps", "activeThreads", "redirects", "conclusions", "recommendations")}


def _stat(label, i):
    return {"label": label, "samples": 100 + i, "errors": i, "errorPct": 1.5 * i,
            "avg": 120.0 + i, "median": 110.0, "p90": 200.0, "p95": 250.0, "p99": 300.0,
            "min": 50.0, "max": 900.0, "tps": 5.5, "kbRecv": 2.2, "kbSent": 1.1}


def _reporte_tx(label, i):
    return {
        "label": label,
        "criticality": "marcada por el analista",
        "metrics": _stat(label, i),
        "sections": {
            "summary": f"Resumen de {label}.",
            "chart_response_times": f"Tiempos de {label}.",
            "chart_latency": f"Latencia de {label}.",
            "chart_error_rate": f"Errores de {label}.",
            "chart_codes": f"Codigos de {label}.",
            "chart_tps": f"TPS de {label}.",
            "conclusions": f"Conclusiones de {label}.",
            "recommendations": f"Recomendaciones de {label}.",
        },
        "charts": {k: f"{IMG}_{label}_{k}" for k in
                   ("response_times", "latency", "error_rate", "codes", "tps")},
    }


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pdf.html"

    meta = defaultdict(lambda: 0.0)
    meta.update({
        "name": "Prueba de equivalencia", "client": "SQA", "project": "Kinetix",
        "testType": "carga", "startTime": "2026-09-16 10:00:00",
        "endTime": "2026-09-16 10:05:00", "duration": 300.0,
        "files": ["uno.jtl"], "filename": "uno.jtl", "filenames": ["uno.jtl"], "metricUnit": "TPS",
        "transaction_analyses": [
            {"label": "4. Get_Booking_Id", "criticality": "alta",
             "ai_analysis": "Analisis critico de Get_Booking_Id.",
             "metrics": _stat("4. Get_Booking_Id", 1)},
        ],
        "transaction_reports": [_reporte_tx("4. Get_Booking_Id", 1),
                                _reporte_tx("6. Delete_Booking_Id", 2)],
    })
    estad = [_stat("4. Get_Booking_Id", 1), _stat("6. Delete_Booking_Id", 2)]
    redir = [_stat("302 - redireccion", 3)]

    html = build_pdf_html(meta, estad, redir, IA, CHARTS)
    open(salida, "w", encoding="utf-8").write(html)
    print(f"{salida}: {len(html)} chars")


if __name__ == "__main__":
    main()
