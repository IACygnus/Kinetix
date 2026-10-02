"""Reporte 151, parte 1 — el esfuerzo (y el modelo) que se ENVÍA en cada tipo de llamada.

    docker exec -w /app -e PYTHONPATH=/app/pruebas_e2e:/app jmeter_backend python3 /app/pruebas_e2e/b5_h_reparto.py

Sin IA y sin base: el cliente de OpenAI se sustituye por un colector que guarda
el modelo y el `reasoning_effort` de cada petición. Configuración simulada:
gpt-5.5 con esfuerzo MEDIO.
  - informe general: resumen, conclusiones y recomendaciones en medio; errores y
    las seis gráficas en bajo;
  - transacción: su resumen en medio; sus cinco gráficas en bajo;
  - chat del Analista IA, bajo; comparativa y conclusión única del integrado, medio;
  - capturas (imagen), bajo;
  - con `AI_MODELO_LIGERO`: el chat y las gráficas van con ese modelo; el resto,
    con el principal. Sin él, todo con el principal.
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
from app.services.ai import conclusion_unica as CU   # noqa: E402
from app.services.ai import origen   # noqa: E402
from app.services.ai.contexto_prompt import contexto_de_parser   # noqa: E402
from app.services.jtl.jtl_parser import JTLParser   # noqa: E402
from app.services.jtl.transaction_series import build_transaction_series   # noqa: E402
from app.api.v1.endpoints.upload import METRIC_KEYS   # noqa: E402
from app.services.analista import chat as CH, ficha as FI   # noqa: E402

ENVIOS = []          # (sección, modelo, esfuerzo)
ESTADO = {"s": None}
LIGERO = "gpt-5-zztest-ligero"   # nombre de prueba: solo lo ve el colector


def _falso(client, model_name, messages, limit, **kw):
    ENVIOS.append((ESTADO["s"], model_name, kw.get("reasoning_effort")))
    contenido = '{"respuesta": "ok", "criterios": []}' if ESTADO["s"] == "analista_chat" else \
        "===CONCLUSIONES===\n• a\n===RECOMENDACIONES===\n• b" if ESTADO["s"] == "consolidated_unico" else "Texto."
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=contenido),
                                                    finish_reason="stop")], usage=None)


_gen = G.GeminiAnalyzer._generate


def _generate(self, prompt, section_name="unknown", *a, **kw):
    ESTADO["s"] = section_name
    return _gen(self, prompt, section_name, *a, **kw)


class _SinBase:
    async def execute(self, *a, **kw):
        raise RuntimeError("sin base")


def analizador(ligero=None):
    an = G.GeminiAnalyzer.__new__(G.GeminiAnalyzer)
    an.provider, an.model_name, an.reasoning_effort, an._openai_client = "openai", "gpt-5.5", "medium", object()
    an.modelo_ligero = ligero
    return an


async def informe(an):
    async def _conf(db):
        return {"provider": "openai", "model_name": "gpt-5.5", "api_key": "x", "reasoning_effort": "medium"}
    AP.load_ai_config_from_db = _conf
    AP.get_gemini_analyzer = lambda **kw: an
    p = JTLParser(B.JTL_R1)
    _, metrics = p.parse()
    crit = {"concurrency": 5, "response_time": 2000, "availability": 99.5}
    await AP.run_ai_and_verdict(p, metrics, "load", copy.deepcopy(crit), "TPS", _SinBase())
    contexto, fases = contexto_de_parser(p, "load", "TPS", crit)
    tx = "6. Delete_Booking_Id"
    fila = {str(r["label"]): r for _, r in p.get_summary_table_data().iterrows()}[tx]
    await TR.generate_transaction_report(
        db=_SinBase(), execution_id=None, label=tx, metrics={k: fila[k] for k in METRIC_KEYS},
        series=build_transaction_series(p.df_main, tx), analyzer=an, acceptance_criteria=crit,
        df_tx=p.df_main[p.df_main["label"] == tx], fases=fases, contexto=contexto)
    # chat del Analista IA
    f = FI.construir(p, metrics, cliente=None, cliente_id=None, proyecto="zz", tipo="load", unidad="TPS", jtl=["x"])
    FI.recalcular(f)

    async def llamar(prompt, sistema, sanear):
        t, _ = await origen.llamar(an._generate, prompt, section_name="analista_chat", sistema=sistema, sanear=sanear)
        return t, ""
    await CH.turno(f, [CH.mensaje("analista", "hola", [])], "hola", contexto, llamar)
    # comparativa y conclusión única del integrado
    an._generate("comparativa de prueba", section_name="comparison_analysis", permite_veredicto=True)
    await CU.generar(an, [CU.Ejecucion(nombre="zz", tipo="load", bloque="bloque", tx_detalladas=[])])
    # una captura
    ESTADO["s"] = "imagen"
    an.analyze_image(b"\x89PNG", "image/png", "cpu", "CPU", "", "monitoring")


def esperado(seccion):
    return "medium" if seccion in ("summary_table", "txreport_summary", "conclusions", "recommendations",
                                   "comparison_analysis", "consolidated_unico") else "low"


async def main():
    G.openai_chat_completion = _falso
    G.GeminiAnalyzer._generate = _generate
    G.GeminiAnalyzer._circuito_bloquea = classmethod(lambda cls: (False, False))

    async def _nada(*a, **kw):
        return None
    TR._upsert = _nada

    print("== 1. El esfuerzo por tipo de llamada (sin modelo ligero)")
    await informe(analizador())
    por = {}
    for s, m, e in ENVIOS:
        por.setdefault(s, set()).add((m, e))
    for s in sorted(por):
        print(f"       {s}: {sorted(por[s])}")
    ok(len(ENVIOS) >= 20, f"{len(ENVIOS)} llamadas capturadas")
    for s, envios in por.items():
        ok(envios == {("gpt-5.5", esperado(s))}, f"{s}: {esperado(s)} con gpt-5.5")
    for s in ("summary_table", "conclusions", "recommendations", "txreport_summary", "analista_chat",
              "comparison_analysis", "consolidated_unico", "imagen", "chart_response_times", "txreport_chart_tps",
              "errors"):
        ok(s in por, f"se probó «{s}»")

    print("== 2. Con modelo ligero")
    ENVIOS.clear()
    await informe(analizador(LIGERO))
    por = {}
    for s, m, e in ENVIOS:
        por.setdefault(s, set()).add((m, e))
    ligeras = [s for s in por if s == "analista_chat" or s.startswith("chart_") or s.startswith("txreport_chart_")]
    ok(len(ligeras) == 12, f"chat + 6 gráficas + 5 de transacción ({len(ligeras)})")
    ok(all(por[s] == {(LIGERO, "low")} for s in ligeras), "el chat y las gráficas, con el modelo ligero y en bajo")
    ok(all(m == "gpt-5.5" for s in por if s not in ligeras for m, _ in por[s]),
       "el resto (resumen, conclusiones, recomendaciones, errores, capturas…) con el principal")

    print("== 3. Vacío = el mismo modelo, también por el entorno")
    os.environ["AI_MODELO_LIGERO"] = ""
    a = G.GeminiAnalyzer.__new__(G.GeminiAnalyzer)
    from app.services.ai.reparto import modelo_ligero_del_entorno, modelo_para
    ok(modelo_ligero_del_entorno() is None and modelo_para("chart_latency", "gpt-5.5", None) == "gpt-5.5",
       "sin AI_MODELO_LIGERO, las gráficas usan el principal")
    os.environ["AI_MODELO_LIGERO"] = LIGERO
    ok(modelo_ligero_del_entorno() == LIGERO, "con AI_MODELO_LIGERO, se lee del entorno")
    del os.environ["AI_MODELO_LIGERO"]


asyncio.run(main())
B.fin("B5 H (reparto del esfuerzo)")
