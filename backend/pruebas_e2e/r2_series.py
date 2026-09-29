"""ETAPA R2 — lo que recibe cada prompt, comprobado SIN llamar a la IA.

    docker exec jmeter_backend python3 /app/pruebas_e2e/r2_series.py

Sobre el JTL de «Nova capa media» (carga, 15.786 peticiones), de solo lectura:

  1. R-D9/R-D10: las siete series del general y las cinco de una transaccion
     salen, con momentos «min M:SS».
  2. R-D15: la seccion de errores recibe el mensaje real.
  3. R-D16: Active Threads recibe el numero de hilos.
  4. R-D17: los hechos calculados dicen 32,89% y 99,39%, y la lectura base (el
     texto del resumen) llega a las secciones que vienen detras, en el general y
     en la transaccion.
  5. R-D14: el detector marca las dos disculpas del informe de referencia y no
     marca una frase con serie.
  6. R-D11: el numero de llamadas no cambia (10 + 6 por transaccion).

`_generate` se sustituye por un stub que devuelve un texto marcado: ni una
peticion sale a la IA. `_upsert` se sustituye por un colector: nada se escribe.
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from app.services.ai import gemini as G
from app.services.ai import transaction_report as TR
from app.services.ai import resumen_serie as R
from app.services.ai.analysis_pipeline import run_ai_and_verdict
from app.services.ai.estilo import detectar_estilo
from app.services.jtl.jtl_parser import JTLParser
from app.services.jtl.transaction_series import build_transaction_series
from app.api.v1.endpoints.upload import METRIC_KEYS

JTL = "/app/uploads/20260925_142338_resultados_general_carga_22-09-2026_200455.jtl"
TX = "1. ConsultaContratosCliente-HU5344"
MARCA = "LECTURA-DE-PRUEBA-R2"

fallos = []


def comprobar(cond, texto):
    print(("  ok   " if cond else "  FALLA ") + texto)
    if not cond:
        fallos.append(texto)


LLAMADAS = []


def _stub(self, prompt, section_name="?", *a, **kw):
    LLAMADAS.append((section_name, prompt))
    return f"{MARCA} de {section_name}: 32,89% en el min 0:05."


async def _colector(*a, **kw):
    return None


G.GeminiAnalyzer._generate = _stub
TR._upsert = _colector


class _SinBase:
    async def execute(self, *a, **kw):
        raise RuntimeError("r2_series no toca la base")


async def main():
    p = JTLParser(JTL)
    _, metrics = p.parse()
    iv = p._calculate_adaptive_interval()

    print("1. Las series")
    g = R.bloques_generales(p.df, p.df_main, iv)
    for k in ("response_times", "latency", "error_rate", "codes_per_second",
              "transactions_per_second", "active_threads"):
        comprobar("min " in g[k] and len(g[k]) > 200, f"general · {k}: {len(g[k])} caracteres, con momentos")
    comprobar("8 de cada 10 puntos entre 3,21% y 14,29%" in g["error_rate"], "tasa de error: lo habitual 3,21%-14,29%")
    comprobar("maximo 33,33% min 0:11" in g["error_rate"], "tasa de error: pico 33,33% en el min 0:11")
    comprobar("Sin episodios sostenidos" in g["error_rate"], "tasa de error: sin rachas sostenidas (intermitente)")
    tx = R.bloques_transaccion(p.df_main[p.df_main["label"] == TX])
    for k in ("chart_response_times", "chart_latency", "chart_error_rate", "chart_codes", "chart_tps"):
        comprobar("min " in tx[k], f"transaccion · {k}")
    comprobar("Por minuto" in tx["chart_error_rate"], "transaccion: tasa de error por minuto (puntos de 1 s poco densos)")

    print("2-3. Mensajes e hilos")
    msgs = R.mensajes_de_error(p.df[~p.df["success"]])
    comprobar(msgs.get((TX, "500"), "").startswith("«Internal Server Error» (1.297)"), "mensaje real del 500")
    comprobar("Maximo 4 hilos" in g["active_threads"], "Active Threads: maximo 4 hilos")

    print("4. Hechos y lectura base (general)")
    hechos = R.hechos_de_la_prueba(p.df_main, iv)
    comprobar("32,89% de las suyas" in hechos and "99,39% de todos los fallos" in hechos, "hechos: 32,89% y 99,39%")
    res = await run_ai_and_verdict(p, metrics, "load", {"concurrency": 4, "response_time": 2000, "availability": 99.5},
                                   "TPS", _SinBase())
    por = {s: pr for s, pr in LLAMADAS}
    comprobar("HECHOS DE LA PRUEBA" in por.get("summary_table", ""), "el resumen recibe los hechos")
    for s in ("errors", "chart_response_times", "chart_latency", "chart_error_rate",
              "chart_codes_per_second", "chart_transactions_per_second", "chart_active_threads"):
        comprobar(f"{MARCA} de summary_table" in por.get(s, ""), f"{s} recibe la lectura base")
    comprobar("Internal Server Error" in por.get("errors", ""), "errors recibe el mensaje real")
    comprobar("Maximo 4 hilos" in por.get("chart_active_threads", ""), "chart_active_threads recibe los hilos")
    comprobar("si crecen con la carga" not in por.get("chart_error_rate", ""), "R-D13: fuera «si crecen con la carga»")
    comprobar("problemas de red" not in por.get("chart_latency", ""), "R-D13: fuera «picos que apuntan a problemas de red»")
    n_general = len(LLAMADAS)
    comprobar(n_general == 10, f"R-D11: general con {n_general} llamadas (eran 10)")

    print("4b. Lectura base (transaccion)")
    LLAMADAS.clear()
    fila = {str(r["label"]): r for _, r in p.get_summary_table_data().iterrows()}[TX]
    await TR.generate_transaction_report(
        db=_SinBase(), execution_id=None, label=TX, metrics={k: fila[k] for k in METRIC_KEYS},
        series=build_transaction_series(p.df_main, TX), analyzer=G.GeminiAnalyzer.__new__(G.GeminiAnalyzer),
        df_tx=p.df_main[p.df_main["label"] == TX])
    comprobar(len(LLAMADAS) == 6, f"R-D11: transaccion con {len(LLAMADAS)} llamadas (eran 6)")
    comprobar(LLAMADAS[0][0] == "txreport_summary", "el resumen va primero")
    for s, pr in LLAMADAS[1:]:
        comprobar(f"{MARCA} de txreport_summary" in pr, f"{s} recibe la lectura base")
    comprobar(LLAMADAS[0][1].count("LINEA DE TIEMPO") == 1, "la linea de tiempo va una sola vez")
    comprobar("pesa la red" not in " ".join(pr for _, pr in LLAMADAS), "R-D13: fuera «cuanto pesa la red»")

    print("5. Detector de disculpas")
    for frase in ("Con la información agregada no es posible atribuir los errores a una falla constante, "
                  "intermitente o creciente minuto a minuto.",
                  "Con la información entregada no hay máximos ni saltos puntuales para asociar demoras."):
        comprobar(any(a["tipo"] == "disculpa" for a in detectar_estilo(frase, "chart_error_rate")), f"marca: {frase[:50]}...")
    limpia = "La tasa de error se movió entre 3,21% y 14,29% la mayor parte del tiempo, con un pico de 33,33% en el min 0:11."
    comprobar(not any(a["tipo"] == "disculpa" for a in detectar_estilo(limpia, "chart_error_rate")), "no marca una frase con serie")

    print()
    print("R2 SERIES: TODO PASA" if not fallos else f"R2 SERIES: {len(fallos)} FALLA(N)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
