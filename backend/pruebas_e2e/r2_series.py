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
  7. BLOQUE 2.1: las fases de las tres ejecuciones del 136 (las mismas que
     fases_r2.py), sin bajada, bajada de 1 s y sin hilos; y la concentracion.

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

    print("6. Fases de la prueba (BLOQUE 2.1a)")
    from types import SimpleNamespace
    from app.api.v1.endpoints.upload import _parse_execution_df
    from app.services.ai import fases as F
    sys.path.insert(0, "/app/pruebas_e2e")
    import fases_r2
    # Las tres ejecuciones del 136, leidas del JTL (sin base, regla 34). Esperado:
    # lo que dio fases_r2.py en el reporte 136 §6.1.
    esperado = {
        "Nova": ("resultados_general_carga_22-09-2026_200455.jtl", "3:14", "29:59",
                 "Subida 0:00–3:14 · Carga sostenida 3:14–30:00 · Sin bajada"),
        "prueba 6": ("resultados_general_carga  4-sept-2025-184018.jtl", "2:19", "4:24",
                     "Subida 0:00–2:19 · Carga sostenida 2:19–4:24 · Bajada 4:24–5:01"),
        "prueba avianca": ("View Results Tree ejecucion2.jtl", "0:27", "2:59",
                           "Subida 0:00–0:27 · Carga sostenida 0:27–2:59 · Bajada 2:59–3:00"),
    }
    for nombre, (jtl, sub, baj, linea) in esperado.items():
        _, df = _parse_execution_df(SimpleNamespace(jtl_filenames=None, jtl_filename=jtl, id=nombre))
        x = F.calcular(df)
        comprobar(x.disponible and F.mmss(x.subida_hasta_s) == sub and F.mmss(x.bajada_desde_s) == baj,
                  f"{nombre}: subida hasta {sub}, carga sostenida hasta {baj}")
        comprobar(linea in x.linea(), f"{nombre}: «{linea}»")
        r = fases_r2.fases(df)
        comprobar((r["subida_hasta"], r["bajada_desde"]) == (x.subida_hasta_s, x.bajada_desde_s),
                  f"{nombre}: fases_r2.py da lo mismo que el servicio")
    comprobar(F.INSTRUCCION_FASES in x.linea(), "la linea lleva la instruccion de las rampas")
    sin = F.calcular(df.drop(columns=[c for c in ("allThreads", "grpThreads") if c in df.columns]))
    comprobar(not sin.disponible and "no disponibles" in sin.linea() and "Subida" not in sin.linea(),
              "sin hilos en el JTL: «fases no disponibles», nada inventado")
    comprobar(F.calcular(df.iloc[0:0]).disponible is False, "sin muestras: no disponibles")

    print("7. Concentracion (BLOQUE 2.1b)")
    import numpy as np
    import pandas as pd
    t0 = pd.Timestamp("2026-09-30 10:00:00")
    fz = F.Fases(True, t0=t0, duracion_s=300.0, max_hilos=10, subida_hasta_s=10.0,
                 bajada_desde_s=289.0, ultimo_s=300.0)
    T = lambda s: pd.Series(t0 + pd.to_timedelta(s, unit="s"))
    picos = F.concentracion(T(list(np.linspace(150, 155, 80)) + list(np.linspace(20, 280, 20)) + [3, 4, 295]), fz)
    # El pico (80 fallos en 150-155 s) cae a caballo de dos ventanas de 9 s (64 + 17,
    # con 1 de fondo): la zona tiene que juntar las dos, no contar solo la primera.
    comprobar("concentrados en min 2:25–2:43" in picos and "81 de 100 (81,0%)" in picos,
              "con picos: la zona entera del pico, aunque cruce dos ventanas (81 de 100)")
    comprobar("y 3 en las rampas (subida 2, bajada 1)" in picos, "con picos: las rampas se cuentan aparte")
    parejo = F.concentracion(T(np.arange(0, 300, 0.5)), fz)
    comprobar("repartidos sin concentracion" in parejo and "si fuera parejo" in parejo,
              "repartido: «repartidos sin concentracion», con la ventana mayor frente a la pareja")
    comprobar("ventanas de 9 s" in parejo, "ventanas de duracion/30 (279 s / 30 = 9 s)")
    comprobar("primero" not in picos + parejo and "ultimo" not in picos + parejo,
              "ni el primero ni el ultimo como dato")
    solo_rampas = F.concentracion(T([1, 2, 3, 295, 296]), fz)
    comprobar(solo_rampas.startswith("ninguno en la carga sostenida"), "todo en las rampas: lo dice")
    corta = F.concentracion(T(np.arange(0, 60, 1)), F.Fases(True, t0=t0, duracion_s=60.0, max_hilos=2,
                                                            subida_hasta_s=0.0, bajada_desde_s=60.0, ultimo_s=60.0))
    comprobar("ventanas de 5 s" in corta, "prueba corta: ventana minima de 5 s")
    sinf = F.concentracion(T(np.arange(0, 300, 1)), F.Fases(False, t0=t0, duracion_s=300.0, motivo="x"))
    comprobar("fases no disponibles: se mira la prueba entera" in sinf, "sin fases: lo dice y mira la prueba entera")

    print("8. Lo que reciben los prompts del general (BLOQUE 2.1c)")
    for s in ("summary_table", "errors", "chart_response_times", "chart_latency", "chart_error_rate",
              "chart_codes_per_second", "chart_transactions_per_second", "chart_active_threads"):
        comprobar("Subida 0:00–3:14 · Carga sostenida 3:14–30:00 · Sin bajada" in por.get(s, "")
                  and F.INSTRUCCION_FASES in por.get(s, ""), f"{s} recibe las fases y su instruccion")
    comprobar("Primero min" not in por["summary_table"] and "repartidos sin concentracion" in por["summary_table"],
              "hechos: la concentracion, no el primero y el ultimo")
    comprobar("el primero min 0:05" not in por["chart_error_rate"] and "1.244 (95,2%) caen en la carga sostenida"
              in por["chart_error_rate"], "tasa de error: 1.244 de 1.307 fallos en la carga sostenida, 63 en la subida")
    comprobar("Primera min" not in por["chart_codes_per_second"], "codigos: sin «Primera… ultima…»")
    comprobar("HTTP 502: 10 respuestas" in por["chart_codes_per_second"]
              and "concentrados en min 18:32–19:26 (20:23:27–20:24:21): 7 de 10" in por["chart_codes_per_second"],
              "codigos: el 502 concentrado (7 de 10 en min 18:32-19:26)")
    comprobar("del min" not in por["errors"] and "repartidos sin concentracion; 63 en las rampas" in por["errors"],
              "tabla de errores: la concentracion de cada error en «Cuando»")
    comprobar(por["chart_response_times"].count("- Degradacion") == 4 and "- Degradacion" in por["chart_latency"],
              "tiempos (4 transacciones) y latencia llevan su degradacion")
    plano = p.df_main[p.df_main["label"] == TX].assign(elapsed=100, Latency=100)
    comprobar("sin degradacion" in R.degradacion(plano, "elapsed", F.calcular(p.df_main)),
              "sin muestras por encima del doble de la mediana: «sin degradacion», no se fabrica con el P90")

    print()
    print("R2 SERIES: TODO PASA" if not fallos else f"R2 SERIES: {len(fallos)} FALLA(N)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
