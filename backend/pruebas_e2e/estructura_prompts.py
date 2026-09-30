"""BLOQUE 2.2 — la estructura comun de los prompts, comprobada SIN llamar a la IA.

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/estructura_prompts.py

Corre el informe general de Nova y el de dos de sus transacciones con el cliente
de OpenAI sustituido por un colector: `_generate` hace todo su camino (sistema,
permiso de dictamen, saneado) y lo que se habria mandado se guarda. Comprueba:

  1. un solo mensaje de sistema, identico en todas las llamadas;
  2. el bloque de la ejecucion, identico y justo detras del sistema, en las diez
     secciones generales Y en las seis de cada transaccion;
  3. las seis de una transaccion comparten ademas su cabecera;
  4. conclusiones y recomendaciones comparten todo hasta su «SECCION:»;
  5. el permiso de dictamen, solo en conclusiones y recomendaciones, y al final;
  6. la linea de tiempo y las fases, en el bloque y no repetidas en cada seccion.
No escribe en la base ni imprime textos de clientes: solo recuentos.
"""
import asyncio
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, "/app")

from app.services.ai import gemini as G
from app.services.ai import analysis_pipeline as AP
from app.services.ai import transaction_report as TR
from app.services.ai.contexto_prompt import contexto_de_parser
from app.services.ai.estilo import PERMISO_VEREDICTO
from app.services.jtl.jtl_parser import JTLParser
from app.services.jtl.transaction_series import build_transaction_series
from app.api.v1.endpoints.upload import METRIC_KEYS

JTL = "/app/uploads/20260925_142338_resultados_general_carga_22-09-2026_200455.jtl"
CRITERIOS = {"concurrency": 4, "response_time": 2000, "availability": 99.5}
LLAMADAS = []   # (seccion, sistema, usuario)
ESTADO = {"seccion": None}
FALLOS = []


def ok(cond, msg):
    print(("  ok   " if cond else "  FALLA ") + msg)
    if not cond:
        FALLOS.append(msg)
    return cond


def _falso_openai(client, model_name, messages, limit, **kw):
    LLAMADAS.append((ESTADO["seccion"], messages[0]["content"], messages[1]["content"]))
    texto = os.environ.get("KX_TEXTO_FALSO", "Texto de prueba de la seccion.")
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=texto),
                                                    finish_reason="stop")], usage=None)


_gen = G.GeminiAnalyzer._generate


def _generate(self, prompt, section_name="unknown", *a, **kw):
    ESTADO["seccion"] = section_name
    return _gen(self, prompt, section_name, *a, **kw)


def _analizador():
    an = G.GeminiAnalyzer.__new__(G.GeminiAnalyzer)
    an.provider, an.model_name, an.reasoning_effort = "openai", "gpt-5.5", "medium"
    an._openai_client = object()
    return an


class _SinBase:
    async def execute(self, *a, **kw):
        raise RuntimeError("sin base")


def comun(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


async def main():
    G.openai_chat_completion = _falso_openai
    G.GeminiAnalyzer._generate = _generate
    G.GeminiAnalyzer._circuito_bloquea = classmethod(lambda cls: (False, False))
    an = _analizador()

    async def _conf(db):
        return {"provider": "openai", "model_name": "gpt-5.5", "api_key": "x", "reasoning_effort": "medium"}
    AP.load_ai_config_from_db = _conf
    AP.get_gemini_analyzer = lambda **kw: an

    async def _colector(*a, **kw):
        return None
    TR._upsert = _colector

    p = JTLParser(JTL)
    _, metrics = p.parse()
    await AP.run_ai_and_verdict(p, metrics, "load", dict(CRITERIOS), "TPS", _SinBase())
    n_general = len(LLAMADAS)

    contexto, fases = contexto_de_parser(p, "load", "TPS", dict(CRITERIOS))
    resumen = {str(r["label"]): r for _, r in p.get_summary_table_data().iterrows()}
    txs = sorted(resumen)[:2]
    for tx in txs:
        await TR.generate_transaction_report(
            db=_SinBase(), execution_id=None, label=tx,
            metrics={k: resumen[tx][k] for k in METRIC_KEYS},
            series=build_transaction_series(p.df_main, tx), analyzer=an,
            acceptance_criteria=dict(CRITERIOS), df_tx=p.df_main[p.df_main["label"] == tx],
            fases=fases, contexto=contexto)

    general = LLAMADAS[:n_general]
    por_tx = [LLAMADAS[n_general + 6 * i:n_general + 6 * (i + 1)] for i in range(len(txs))]
    print(f"{n_general} llamadas generales, {len(LLAMADAS) - n_general} de transaccion")

    print("1. Sistema")
    ok(len({s for _, s, _ in LLAMADAS}) == 1, "un solo mensaje de sistema en todas las llamadas")
    ok(PERMISO_VEREDICTO not in LLAMADAS[0][1], "el permiso de dictamen no esta en el sistema")

    print("2. Bloque de la ejecucion")
    ok(all(u.startswith(contexto) for _, _, u in LLAMADAS),
       f"las {len(LLAMADAS)} llamadas empiezan por el mismo bloque ({len(contexto)} caracteres)")
    ok(contexto.startswith("DATOS DE LA EJECUCION"), "y el bloque va el primero")
    for marca in ("UNIDAD DE MEDIDA", "TIPO DE PRUEBA", "CIFRAS GLOBALES", "CRITERIOS DE ACEP",
                  "LINEA DE TIEMPO", "FASES DE LA PRUEBA", "HECHOS DE LA PRUEBA"):
        ok(marca in contexto, f"el bloque lleva {marca}")
    ok(all(u.count("LINEA DE TIEMPO") == 1 and u.count("FASES DE LA PRUEBA") == 1 for _, _, u in LLAMADAS),
       "linea de tiempo y fases, una sola vez por prompt")

    print("3. Transacciones")
    for tx, grupo in zip(txs, por_tx):
        pref = min(comun(grupo[0][2], g[2]) for g in grupo[1:])
        cab = grupo[0][2].index("SECCION:")
        ok(pref >= grupo[0][2].index(f'"{tx}"'), f"«{tx[:12]}…»: sus 6 secciones comparten su cabecera ({pref} caracteres)")
    ok(comun(por_tx[0][0][2], por_tx[1][0][2]) >= len(contexto), "dos transacciones comparten el bloque entero")

    print("4. Conclusiones y recomendaciones")
    conc = next(u for s, _, u in general if s == "conclusions")
    reco = next(u for s, _, u in general if s == "recommendations")
    ok(comun(conc, reco) >= conc.index("SECCION: CONCLUSIONES"),
       f"comparten todo hasta su SECCION ({comun(conc, reco)} de {len(conc)} caracteres)")

    print("5. Permiso de dictamen")
    con_permiso = sorted(s for s, _, u in LLAMADAS if PERMISO_VEREDICTO in u)
    ok(con_permiso == ["conclusions", "recommendations"], f"solo en {con_permiso}")
    ok(conc.rstrip().endswith(PERMISO_VEREDICTO.rstrip()), "y al final del mensaje")

    print("6. Lectura base detras del bloque")
    graf = [u for s, _, u in general if s.startswith("chart_")]
    ok(all(u.index("LECTURA BASE") > len(contexto) for u in graf), "en las graficas, detras del bloque")
    ok(all(u.index("LECTURA BASE") < u.index("SECCION:") for u in graf), "y delante de lo propio")

    print()
    print("ESTRUCTURA: TODO PASA" if not FALLOS else f"ESTRUCTURA: {len(FALLOS)} FALLOS")
    return 0 if not FALLOS else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
