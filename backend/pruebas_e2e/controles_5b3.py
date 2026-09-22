"""ETAPA 5b.3 — controles sobre la corrida real `E5b-criterios`.

    docker exec jmeter_backend python3 /tmp/e2e/controles_5b3.py [exec_id]

Solo LEE lo que la corrida dejo guardado: 0 llamadas a la IA.

  1. La ejecucion existe, con sus criterios y su veredicto.
  2. Los seis textos de "1. Auth" se generaron.
  3. Hablan de SU limite de 300 ms y NO afirman que cumple por estar bajo los
     2.000 ms generales.
  4. El detector de estilo (ETAPA 3) sigue en 0 avisos.
  5. El informe general no contradice la tabla de veredictos.
"""
import asyncio
import re
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.test import TestExecution
from app.db.models.transaction_chart_analysis import (
    SECTIONS_GENERADAS, TransactionChartAnalysis)
from app.services.ai.estilo import detectar_estilo, terminos_de, avisos_de_ejecucion

try:
    EID = sys.argv[1]
except IndexError:
    EID = open("/tmp/e5b_eid.txt").read().strip()

LABEL = "1. Auth"
fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


async def main():
    async with AsyncSessionLocal() as db:
        ex = (await db.execute(select(TestExecution).where(TestExecution.id == EID))).scalar_one_or_none()
        if not ok(ex is not None, f"la ejecucion {EID} existe"):
            return 1
        crit = ex.acceptance_criteria_json or {}
        print(f"{ex.name}  ·  veredicto global {crit.get('verdict')}")

        print("\n--- 1. Los criterios quedaron guardados ---")
        per = (crit.get("per_transaction") or {}).get(LABEL) or {}
        ok(float(per.get("response_time", 0)) == 300.0,
           f"\"{LABEL}\" guardo su limite propio de 300 ms ({per.get('response_time')})")
        ok(float(crit.get("response_time", 0)) == 2000.0,
           f"el global sigue en 2.000 ms ({crit.get('response_time')})")
        vpt = crit.get("verdicts_per_transaction") or {}
        ok(vpt.get(LABEL) == "NO APTO",
           f"la tabla marca \"{LABEL}\" como NO APTO contra sus 300 ms ({vpt.get(LABEL)})")
        print(f"    veredictos: {vpt}")

        print("\n--- 2. Los seis textos de la transaccion se generaron ---")
        filas = (await db.execute(
            select(TransactionChartAnalysis)
            .where(TransactionChartAnalysis.execution_id == ex.id,
                   TransactionChartAnalysis.label == LABEL)
        )).scalars().all()
        textos = {f.section: (f.ai_analysis or "") for f in filas}
        con_texto = [s for s in SECTIONS_GENERADAS if textos.get(s, "").strip()]
        ok(len(con_texto) == len(SECTIONS_GENERADAS),
           f"{len(con_texto)}/{len(SECTIONS_GENERADAS)} secciones con texto")

        print("\n--- 3. Hablan de SU limite, no del general ---")
        todo = "\n".join(textos.get(s, "") for s in SECTIONS_GENERADAS)
        menciona_300 = len(re.findall(r"\b300\b", todo))
        ok(menciona_300 > 0, f"el bloque menciona 300 en {menciona_300} sitio(s)")
        # Lo prohibido: presentar los 2.000 ms como el limite de ESTA transaccion.
        malos = re.findall(r"[^.]*2\.000[^.]*\.", todo)
        ok(not malos, f"no presenta 2.000 ms como su limite: {malos[:2]}")
        for s in SECTIONS_GENERADAS:
            t = textos.get(s, "")
            print(f"    [{s}] {len(t)} chars · 300 aparece {len(re.findall(r'.300.', t))} vez/veces")

        print("\n--- 4. El detector de estilo sigue en 0 ---")
        avisos_tx = {}
        for s in SECTIONS_GENERADAS:
            t = textos.get(s, "")
            if t:
                terms = terminos_de(detectar_estilo(t, s))
                if terms:
                    avisos_tx[s] = terms
        ok(not avisos_tx, f"bloque por transaccion sin avisos de estilo: {avisos_tx}")
        avisos_gen = avisos_de_ejecucion(ex)
        ok(not avisos_gen, f"informe general sin avisos de estilo: {avisos_gen}")

        print("\n--- 5. El informe general no contradice la tabla ---")
        general = "\n".join(filter(None, [
            ex.ai_analysis_summary or "", ex.ai_analysis_response_times or "",
            ex.ai_conclusions or "", ex.ai_recommendations or ""]))
        ok(len(general) > 200, f"hay texto general que revisar ({len(general)} chars)")
        # El modelo narra el flujo de negocio y suele quitar el prefijo numerico:
        # escribe "Auth", no "1. Auth". Buscar la etiqueta literal daba 0 frases y
        # la comprobacion pasaba en vacio.
        nombre = re.sub(r"^\s*\d+\.\s*", "", LABEL)
        frases = [f.strip() for f in re.split(r"(?<=\.)\s+", general)
                  if re.search(rf"\b{re.escape(nombre)}\b", f)]
        print(f"    frases que nombran a \"{nombre}\": {len(frases)}")
        for f in frases[:6]:
            print(f"      · {f[:190]}")
        ok(len(frases) > 0, f"el informe general habla de \"{nombre}\"")
        # Lo que hay que demostrar: que al juzgarla usa SU limite.
        con_propio = [f for f in frases if re.search(r"300\s*ms", f)]
        ok(len(con_propio) > 0,
           f"al menos una frase la juzga contra sus 300 ms ({len(con_propio)})")
        # Y lo prohibido: darla por buena contra el umbral general.
        malas = [f for f in frases
                 if re.search(r"2\.000", f) and re.search(r"cumpl|dentro del|por debajo", f, re.I)]
        ok(not malas, f"ninguna dice que cumple por estar bajo 2.000 ms: {malas}")

    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("5b.3 — LA CORRIDA REAL PASA TODOS LOS CONTROLES")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
