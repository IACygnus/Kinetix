"""ETAPA 5b.1 — que criterios recibe HOY cada prompt (read-only).

    docker exec jmeter_backend python3 /tmp/e2e/criterios_en_prompts.py [exec_id]

Construye los diecinueve prompts de una ejecucion REAL con un STUB que cuenta las
llamadas y LANZA, de modo que no puede escaparse ni una peticion a la IA, y
vuelca literalmente el bloque de criterios de cada uno.

Ejecucion por defecto: E5-panel, que tiene "1. Auth" con 300 ms propios y el
resto con el global de 2.000 ms — justo el caso que hay que poder distinguir.
"""
import asyncio
import re
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.test import TestExecution
from app.services.jtl.jtl_parser import JTLParser
import app.services.ai.gemini as G
from app.services.ai.transaction_report import build_section_prompts, SECTIONS_GENERADAS

EID = sys.argv[1] if len(sys.argv) > 1 else "c33488cb-5f1c-499b-86b3-4b58642c31cb"

# ---- STUB: cuenta y lanza. Ni una llamada real puede salir de aqui. ----
capturado = []      # (section_name, prompt)
LLAMADAS = {"n": 0}


class LlamadaIABloqueada(RuntimeError):
    pass


def _stub_generate(self, prompt, section_name="?", **kw):
    LLAMADAS["n"] += 1
    capturado.append((section_name, prompt))
    raise LlamadaIABloqueada(f"stub 5b.1: no se llama a la IA ({section_name})")


G.GeminiAnalyzer._generate = _stub_generate


def bloque_criterios(prompt):
    """El trozo del prompt que habla de criterios, literal."""
    trozos = []
    for m in re.finditer(r"^.*CRITERIO.*$", prompt, re.M | re.I):
        ini = m.start()
        # Hasta la primera linea en blanco doble o 12 lineas, lo que llegue antes.
        fin = prompt.find("\n\n", ini)
        if fin == -1 or fin - ini > 900:
            fin = ini + 900
        trozos.append(prompt[ini:fin].strip())
    return trozos


def menciona(prompt, *textos):
    return {t: (t in prompt) for t in textos}


async def main():
    async with AsyncSessionLocal() as db:
        ex = (await db.execute(select(TestExecution).where(TestExecution.id == EID))).scalar_one()
        crit = ex.acceptance_criteria_json or {}
        print(f"Ejecucion: {ex.name}  ({ex.test_type})")
        print(f"Criterios globales: response_time={crit.get('response_time')} ms, "
              f"availability={crit.get('availability')}%, concurrency={crit.get('concurrency')}")
        per = crit.get("per_transaction") or {}
        print(f"Criterios PROPIOS por transaccion: {list(per.keys()) or 'ninguno'}")
        for lb, c in per.items():
            print(f"    {lb}: response_time={c.get('response_time')} ms, "
                  f"availability={c.get('availability')}%")
        print()

        from pathlib import Path
        jtl = sorted(Path("/app/uploads").glob(f"*{ex.jtl_filename}"))
        parser = JTLParser(str(jtl[0]))
        _df, metrics = parser.parse()
        summary_df = parser.get_summary_table_data()

        # ================= 1. LOS 6 PROMPTS POR TRANSACCION =================
        print("=" * 78)
        print("1. LOS 6 PROMPTS POR TRANSACCION  (transaction_report.build_section_prompts)")
        print("=" * 78)
        fila = summary_df[summary_df["label"] == "1. Auth"]
        m = fila.iloc[0].to_dict() if len(fila) else {}
        series = {"interval_seconds": 1, "response_times": [], "latency": [],
                  "error_rate": [], "codes": [], "tps": []}
        prompts_tx = build_section_prompts("1. Auth", m, series, ex.test_type)
        print(f"firma: build_section_prompts(label, m, series, test_type)  "
              f"-> SIN parametro de criterios\n")
        for sec in SECTIONS_GENERADAS:
            p = prompts_tx[sec]
            bl = bloque_criterios(p)
            print(f"  [{sec}] {len(p)} chars")
            print(f"     bloque de criterios: {bl if bl else 'NINGUNO'}")
            print(f"     menciona: {menciona(p, '300', '2.000', 'criterio', 'limite')}")
        print()

        # ================= 2. LOS PROMPTS DEL INFORME GENERAL =================
        print("=" * 78)
        print("2. LOS PROMPTS DEL INFORME GENERAL  (GeminiAnalyzer, via stub)")
        print("=" * 78)
        an = G.GeminiAnalyzer(provider="openai", model_name="gpt-5.5", api_key="stub")
        insights = G.prepare_insights_for_prompt(summary_df)

        def probar(nombre, fn, *a, **kw):
            antes = len(capturado)
            try:
                fn(*a, **kw)
            except Exception:
                pass
            if len(capturado) == antes:
                print(f"  [{nombre}] NO llego a construir prompt")
                return
            sec, p = capturado[-1]
            bl = bloque_criterios(p)
            print(f"  [{nombre}] ({sec}) {len(p)} chars")
            print(f"     bloque de criterios:")
            if bl:
                for t in bl:
                    for ln in t.splitlines():
                        print(f"        | {ln}")
            else:
                print("        | NINGUNO")
            print(f"     menciona per_transaction: {menciona(p, '1. Auth', '300')}")

        probar("summary_table", an.analyze_summary_table, summary_df, metrics,
               test_type=ex.test_type, acceptance_criteria=crit, insights=insights)
        probar("errors", an.analyze_errors, [{"label": "x", "count": 1, "code": "500", "message": ""}],
               metrics["total_requests"], test_type=ex.test_type)
        probar("chart response_times", an.analyze_chart, "response_times", "datos",
               test_type=ex.test_type, insights=insights)
        probar("conclusions", an.generate_conclusions, metrics, "s", "e", "rt", "", "", "l",
               "er", "cps", "tps", "at", "", test_type=ex.test_type,
               acceptance_criteria=crit)
        probar("recommendations", an.generate_recommendations, metrics, "s", "e", "rt", "", "",
               "l", "er", "cps", "tps", "at", "", test_type=ex.test_type,
               acceptance_criteria=crit)

        print()
        print("=" * 78)
        print(f"LLAMADAS REALES A LA IA: 0   (el stub conto {LLAMADAS['n']} intentos y lanzo en todos)")
        print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
