"""ETAPA 5b.2 — los criterios efectivos YA llegan a los prompts (D55).

    docker exec jmeter_backend python3 /tmp/e2e/criterios_5b2.py [exec_id]

Mismo stub que 5b.1: cuenta las llamadas y LANZA, asi que no se escapa ninguna
peticion a la IA. Comprueba sobre E5-panel, que tiene "1. Auth" con 300 ms
propios y el resto con el global de 2.000 ms:

  - los 6 prompts de "1. Auth" traen 300 ms como SU limite y no presentan
    2.000 ms como suyo;
  - los 6 de "2. Get Booking" traen el general de 2.000 ms, dicho como general;
  - los prompts generales listan "1. Auth" con su limite propio;
  - una ejecucion SIN criterios sale con los prompts de siempre.
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

capturado = []
LLAMADAS = {"n": 0}
fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def _stub(self, prompt, section_name="?", **kw):
    LLAMADAS["n"] += 1
    capturado.append((section_name, prompt))
    raise RuntimeError(f"stub 5b.2: no se llama a la IA ({section_name})")


G.GeminiAnalyzer._generate = _stub


def bloque(prompt, cabecera):
    """El bloque que empieza en `cabecera`, hasta la linea en blanco siguiente."""
    i = prompt.find(cabecera)
    if i == -1:
        return ""
    j = prompt.find("\n\n", i)
    return prompt[i: j if j != -1 else len(prompt)]


async def main():
    async with AsyncSessionLocal() as db:
        ex = (await db.execute(select(TestExecution).where(TestExecution.id == EID))).scalar_one()
        crit = ex.acceptance_criteria_json or {}
        per = crit.get("per_transaction") or {}
        print(f"{ex.name}: global {crit.get('response_time')} ms · propios en {list(per.keys())}\n")

        from pathlib import Path
        jtl = sorted(Path("/app/uploads").glob(f"*{ex.jtl_filename}"))
        parser = JTLParser(str(jtl[0]))
        _df, metrics = parser.parse()
        sdf = parser.get_summary_table_data()
        fila = {str(r["label"]): r.to_dict() for _, r in sdf.iterrows()}
        series = {"interval_seconds": 1, "response_times": [], "latency": [],
                  "error_rate": [], "codes": [], "tps": []}

        # ============ 1. LOS 6 DE UNA TRANSACCION CON LIMITE PROPIO ============
        print("--- 1. \"1. Auth\": limite propio de 300 ms ---")
        p_auth = build_section_prompts("1. Auth", fila["1. Auth"], series, ex.test_type, crit)
        for sec in SECTIONS_GENERADAS:
            b = bloque(p_auth[sec], "CRITERIO DE ACEPTACIÓN QUE SE LE APLICA")
            bien = ("300 ms" in b and "límite propio de esta transacción" in b
                    and "2.000 ms" not in b)
            ok(bien, f"[{sec}] su limite es 300 ms y se nombra como propio")
        print("    bloque literal:")
        for ln in bloque(p_auth["summary"], "CRITERIO DE ACEPTACIÓN QUE SE LE APLICA").splitlines():
            print(f"      | {ln}")
        # Lo que NO puede pasar: que el general se le presente como suyo.
        ok(all("2.000 ms (límite propio" not in p_auth[s] for s in SECTIONS_GENERADAS),
           "en ninguna seccion se presenta 2.000 ms como su limite propio")

        # ============ 2. LOS 6 DE UNA TRANSACCION SIN LIMITE PROPIO ============
        print("\n--- 2. \"2. Get Booking\": se mide con el general ---")
        p_gb = build_section_prompts("2. Get Booking", fila["2. Get Booking"], series, ex.test_type, crit)
        for sec in SECTIONS_GENERADAS:
            b = bloque(p_gb[sec], "CRITERIO DE ACEPTACIÓN QUE SE LE APLICA")
            # Se comprueba la MARCA de origen que acompana a la cifra, no la
            # frase suelta: el aviso de esta rama dice "no tiene límite propio",
            # en negativo, y buscar el trozo de texto daria un falso fallo.
            bien = ("2.000 ms (criterio general de la prueba)" in b
                    and "(límite propio de esta transacción)" not in b)
            ok(bien, f"[{sec}] su limite es el general de 2.000 ms")
        ok("300 ms" not in bloque(p_gb["summary"], "CRITERIO DE ACEPTACIÓN"),
           "no se le cuela el limite de otra transaccion")

        # ============ 3. LOS PROMPTS DEL INFORME GENERAL ============
        print("\n--- 3. Los prompts generales listan las excepciones ---")
        an = G.GeminiAnalyzer(provider="openai", model_name="gpt-5.5", api_key="stub")
        ins = G.prepare_insights_for_prompt(sdf)

        def prompt_de(fn, *a, **kw):
            try:
                fn(*a, **kw)
            except Exception:
                pass
            return capturado[-1][1]

        casos = [
            ("resumen", lambda: prompt_de(an.analyze_summary_table, sdf, metrics,
                                          test_type=ex.test_type, acceptance_criteria=crit, insights=ins)),
            ("errores", lambda: prompt_de(an.analyze_errors,
                                          [{"label": "x", "count": 1, "code": "500", "message": ""}],
                                          metrics["total_requests"], test_type=ex.test_type,
                                          acceptance_criteria=crit)),
            ("grafica response_times", lambda: prompt_de(an.analyze_chart, "response_times", "datos",
                                                         test_type=ex.test_type, insights=ins,
                                                         acceptance_criteria=crit)),
            ("grafica error_rate", lambda: prompt_de(an.analyze_chart, "error_rate", "datos",
                                                     test_type=ex.test_type, acceptance_criteria=crit)),
            ("conclusiones", lambda: prompt_de(an.generate_conclusions, metrics, "s", "e", "rt", "", "",
                                               "l", "er", "cps", "tps", "at", "",
                                               test_type=ex.test_type, acceptance_criteria=crit)),
            ("recomendaciones", lambda: prompt_de(an.generate_recommendations, metrics, "s", "e", "rt", "", "",
                                                  "l", "er", "cps", "tps", "at", "",
                                                  test_type=ex.test_type, acceptance_criteria=crit)),
        ]
        for nombre, fn in casos:
            p = fn()
            b = bloque(p, "TRANSACCIONES CON CRITERIO PROPIO")
            bien = ('"1. Auth": tiempo de respuesta máximo 300 ms' in b)
            ok(bien, f"[{nombre}] lista \"1. Auth\" con su limite propio de 300 ms")
        print("    bloque literal (resumen):")
        for ln in bloque(casos[0][1](), "TRANSACCIONES CON CRITERIO PROPIO").splitlines():
            print(f"      | {ln}")

        # ============ 4. SIN CRITERIOS, TODO COMO ANTES ============
        print("\n--- 4. Sin criterios el prompt no cambia ---")
        for etiqueta, c in (("None", None), ("vacio", {}), ("en prosa", {"raw_text": "lo acordado"})):
            p_sin = build_section_prompts("1. Auth", fila["1. Auth"], series, ex.test_type, c)
            ok(all("CRITERIO DE ACEPTACIÓN" not in p_sin[s] for s in SECTIONS_GENERADAS),
               f"criterios {etiqueta}: ninguna seccion trae bloque de criterios")

        # ============ 5. LA TABLA DE VEREDICTOS NO SE MOVIO ============
        print("\n--- 5. Los veredictos siguen siendo los mismos ---")
        res = G.compute_per_transaction_verdicts(sdf, crit)
        guardados = crit.get("verdicts_per_transaction") or {}
        calculados = res.get("verdicts_per_transaction") or {}
        ok(calculados == guardados,
           f"los {len(calculados)} veredictos coinciden con los guardados")
        ok(calculados.get("1. Auth") == "NO APTO",
           f"\"1. Auth\" sigue NO APTO contra sus 300 ms ({calculados.get('1. Auth')})")
        ok(calculados.get("2. Get Booking") == "APTO",
           f"\"2. Get Booking\" sigue APTO contra los 2.000 ms ({calculados.get('2. Get Booking')})")

    print("\n" + "=" * 70)
    print(f"LLAMADAS REALES A LA IA: 0   (el stub conto {LLAMADAS['n']} intentos y lanzo en todos)")
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("5b.2 — LOS CRITERIOS EFECTIVOS LLEGAN A LOS PROMPTS: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
