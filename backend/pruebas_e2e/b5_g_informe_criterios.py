"""Reporte 150, parte 4 — el informe USA los criterios. Sin IA (colector) y sin base.

    docker exec -w /app -e PYTHONPATH=/app/pruebas_e2e:/app jmeter_backend python3 /app/pruebas_e2e/b5_g_informe_criterios.py

Sobre el JTL sintético de Fredy que deja `b5_f_criterios_v2.py` (corre antes en
`cierre_b5.sh`), con los criterios de su sesión ya corregidos:
  tiempo máximo ≤ 5 s en cada servicio · 32.000 correctas por servicio en A y B
  en 30 min · 8.000 en C · 28 usuarios en A y B.
Comprueba, con el mismo arnés que `estructura_prompts.py`:
  1. el veredicto que se guarda es el de los CRITERIOS (y coherente por transacción);
  2. el bloque común lleva el resultado frente a los criterios;
  3. el resumen recibe la instrucción de abrir con los criterios y el permiso de
     dictamen; las conclusiones, el resultado de los criterios (no el del promedio)
     y la lista de incumplidos; las recomendaciones, la suya;
  4. cada gráfica recibe los criterios que toca su dato; cada transacción, los suyos;
  5. sin criterios del analista (Nuevo Reporte) nada de eso aparece.
"""
import asyncio
import copy
import os
import sys
from types import SimpleNamespace

import b5_comun as B
from b5_comun import ok

sys.path.insert(0, "/app")
from app.services.ai import gemini as G   # noqa: E402
from app.services.ai import analysis_pipeline as AP   # noqa: E402
from app.services.ai import transaction_report as TR   # noqa: E402
from app.services.ai.contexto_prompt import contexto_de_parser   # noqa: E402
from app.services.ai.estilo import PERMISO_VEREDICTO   # noqa: E402
from app.services.jtl.jtl_parser import JTLParser   # noqa: E402
from app.services.jtl.transaction_series import build_transaction_series   # noqa: E402
from app.api.v1.endpoints.upload import METRIC_KEYS   # noqa: E402
from app.services.analista import ficha as FI, prompt as PA   # noqa: E402

JTL = "/app/uploads/ZZTEST-B5_fredy.jtl"
A_, B_, C_ = "1. ZZ_AsegurarFondos", "3. ZZ_Originator", "1. ZZ_Receptor"
if not os.path.exists(JTL):
    sys.exit("Falta el JTL sintético: corre antes b5_f_criterios_v2.py (lo hace cierre_b5.sh)")

LLAMADAS = []
ESTADO = {"s": None}


def _falso(client, model_name, messages, limit, **kw):
    LLAMADAS.append((ESTADO["s"], messages[1]["content"]))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Texto."), finish_reason="stop")],
                           usage=None)


_gen = G.GeminiAnalyzer._generate


def _generate(self, prompt, section_name="unknown", *a, **kw):
    ESTADO["s"] = section_name
    return _gen(self, prompt, section_name, *a, **kw)


class _SinBase:
    async def execute(self, *a, **kw):
        raise RuntimeError("sin base")


CRITERIOS = [
    {"texto": "5 segundos de tiempo máximo en cada servicio", "tipo": "tiempo_respuesta", "metrica": "max",
     "operador": "<=", "valor": 5, "unidad": "s", "cada_transaccion": True},
    {"texto": "32.000 por servicio en asegurar fondos y originador en 30 minutos", "tipo": "volumen",
     "valor": 32000, "transacciones": [A_, B_], "ventana_valor": 30, "ventana_unidad": "min"},
    {"texto": "8.000 para receptor en 30 minutos", "tipo": "volumen", "valor": 8000, "transacciones": [C_],
     "ventana_valor": 30, "ventana_unidad": "min"},
    {"texto": "28 usuarios concurrentes en esos dos servicios", "tipo": "concurrencia", "valor": 28,
     "transacciones": [A_, B_]},
]


async def correr(crit, p, metrics, tx_label=None):
    LLAMADAS.clear()
    c = copy.deepcopy(crit)
    await AP.run_ai_and_verdict(p, metrics, "load", c, "TPS", _SinBase())
    if tx_label:
        contexto, fases = contexto_de_parser(p, "load", "TPS", c)
        fila = {str(r["label"]): r for _, r in p.get_summary_table_data().iterrows()}[tx_label]
        an = G.GeminiAnalyzer.__new__(G.GeminiAnalyzer)
        an.provider, an.model_name, an.reasoning_effort, an._openai_client = "openai", "gpt-5.5", "medium", object()
        await TR.generate_transaction_report(
            db=_SinBase(), execution_id=None, label=tx_label, metrics={k: fila[k] for k in METRIC_KEYS},
            series=build_transaction_series(p.df_main, tx_label), analyzer=an, acceptance_criteria=c,
            df_tx=p.df_main[p.df_main["label"] == tx_label], fases=fases, contexto=contexto)
    return c, {s: u for s, u in LLAMADAS}, list(LLAMADAS)


async def main():
    G.openai_chat_completion = _falso
    G.GeminiAnalyzer._generate = _generate
    G.GeminiAnalyzer._circuito_bloquea = classmethod(lambda cls: (False, False))
    an = G.GeminiAnalyzer.__new__(G.GeminiAnalyzer)
    an.provider, an.model_name, an.reasoning_effort, an._openai_client = "openai", "gpt-5.5", "medium", object()

    async def _conf(db):
        return {"provider": "openai", "model_name": "gpt-5.5", "api_key": "x", "reasoning_effort": "medium"}
    AP.load_ai_config_from_db = _conf
    AP.get_gemini_analyzer = lambda **kw: an

    async def _nada(*a, **kw):
        return None
    TR._upsert = _nada

    p = JTLParser(JTL)
    _, metrics = p.parse()
    ficha = FI.construir(p, metrics, cliente=None, cliente_id=None, proyecto="ZZTEST-B5 informe", tipo="load",
                         unidad="TPS", jtl=["ZZTEST-B5_fredy.jtl"])
    FI.agregar_criterios(ficha, CRITERIOS, "chat")
    FI.agregar_relato(ficha, ["Desarrollo confirmó que AsegurarFondos depende de un catálogo lento."], "chat")
    FI.recalcular(ficha, lambda: p.df_main)
    crit = PA.criterios_para_generar(ficha, [], "zztest")

    print("== 1. El veredicto que se guarda")
    c, por, todas = await correr(crit, p, metrics, A_)
    ok(c["verdict"] == "NO APTO", f"NO APTO por los criterios ({c['verdict']})")
    ok(c["verdicts_per_transaction"] == {A_: "NO APTO", B_: "NO APTO", C_: "NO APTO"},
       f"coherente por transacción: {c['verdicts_per_transaction']}")
    ok(c["verdict"] == ficha["criterios"]["veredicto"]["verdict"], "el mismo que enseña la ficha")

    print("== 2. El bloque común")
    contexto, _ = contexto_de_parser(p, "load", "TPS", crit)
    ok("RESULTADO DE LA EJECUCIÓN FRENTE A ESTOS CRITERIOS (lo calculó Kinetix): NO APTO" in contexto,
       "lleva el resultado frente a los criterios")
    ok(all(u.startswith(contexto) for _, u in todas), "y sigue siendo el prefijo común de las 16 llamadas")
    ok(len(todas) == 16, f"10 generales + 6 de la transacción ({len(todas)})")

    print("== 3. Resumen, conclusiones, recomendaciones")
    res = por["summary_table"]
    ok(PA.INSTRUCCION_RESUMEN in res and PERMISO_VEREDICTO.strip() in res,
       "el resumen: abrir con los criterios, sin tope de 4 cifras, y con permiso de dictamen")
    ok("CRITERIOS DE ACEPTACIÓN QUE TOCA ESTE DATO" in res and "tiempo máximo ≤ 5,0 s" in res,
       "y los criterios de tiempo y volumen que le tocan")
    conc = por["conclusions"]
    ok("RESULTADO CALCULADO FRENTE A LOS CRITERIOS DE ACEPTACIÓN: NO APTO" in conc
       and "RESULTADO CALCULADO FRENTE A LOS CRITERIOS: APTO" not in conc,
       "las conclusiones: el veredicto de los criterios, no el del promedio global")
    ok("La PRIMERA viñeta es el dictamen frente a los criterios" in conc and "UNA viñeta por cada criterio" in conc,
       "primera viñeta = dictamen; una por criterio incumplido")
    ok(conc.count("\n- tiempo máximo") + conc.count("\n- volumen") >= 3, "con la lista de los incumplidos")
    ok(PA.INSTRUCCION_RECOMENDACIONES in por["recommendations"], "las recomendaciones, atadas a los incumplidos")
    ok("Mira el modelo de resumen con criterios" in res and "Servicio C alcanzó las 34.783" in G.SYSTEM_PROMPT,
       "los modelos de Fredy están en la guía")

    print("== 4. Gráficas y transacción")
    rt = por["chart_response_times"]
    ok("CRITERIOS DE ACEPTACIÓN QUE TOCA ESTE DATO" in rt and "tiempo máximo ≤ 5,0 s" in rt and "\n- volumen" not in
       rt.split("CRITERIOS DE ACEPTACIÓN QUE TOCA ESTE DATO")[1], "tiempos: el criterio de tiempo (no el de volumen)")
    tps = por["chart_transactions_per_second"].split("CRITERIOS DE ACEPTACIÓN QUE TOCA ESTE DATO")
    ok(len(tps) == 2 and "volumen ≥ 32.000" in tps[1], "caudal: el volumen esperado")
    th = por["chart_active_threads"].split("CRITERIOS DE ACEPTACIÓN QUE TOCA ESTE DATO")
    ok(len(th) == 2 and "concurrencia ≥ 28" in th[1], "usuarios: la concurrencia")
    tx = por["txreport_summary"] if "txreport_summary" in por else next(u for s, u in todas if "summary" in str(s) and s != "summary_table")
    cab = tx.split("SECCION:")[0]
    nota = cab.split("CRITERIOS DE ACEPTACIÓN QUE TOCA ESTE DATO")[-1]
    ok(f"- tiempo máximo ≤ 5,0 s: «{A_}» 9.221 ms — NO CUMPLE" in nota
       and f"- volumen ≥ 32.000 peticiones correctas en 30 min: «{A_}»" in nota
       and f"- concurrencia ≥ 28 usuarios: «{A_}» 28 usuarios — CUMPLE" in nota
       and "8.000" not in nota and C_ not in nota, "la transacción A recibe SUS criterios, con SU medida (nada de C)")
    ok("CRITERIO DE ACEPTACIÓN QUE SE LE APLICA A" not in cab, "y no el bloque viejo del motor")

    print("== 5. Sin criterios del analista, como antes")
    viejo = {"concurrency": 5, "response_time": 2000, "availability": 99.5}
    c, por, _ = await correr(viejo, p, metrics)
    ok(PA.INSTRUCCION_RESUMEN not in por["summary_table"] and PERMISO_VEREDICTO.strip() not in por["summary_table"],
       "Nuevo Reporte: el resumen sin dictamen ni instrucción nueva")
    ok("RESULTADO CALCULADO FRENTE A LOS CRITERIOS:" in por["conclusions"]
       and "DE ACEPTACIÓN:" not in por["conclusions"].split("RESULTADO CALCULADO")[1][:40],
       "y las conclusiones con el resultado de siempre")
    ok("TOCA ESTE DATO" not in "".join(por.values()), "ninguna nota de criterios")


asyncio.run(main())
B.fin("B5 G (el informe usa los criterios)")
