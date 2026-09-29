"""ETAPA R2 — una corrida COMPLETA del informe, en proceso y SIN escribir en la base.

    docker exec jmeter_backend python3 /app/pruebas_e2e/corrida_r2.py <etiqueta>

Genera el informe general y el de cada transaccion que ya tenga informe, de la
ejecucion `35ca5b92` («Nova capa media», carga, 8,28%), con el mismo codigo que
usa /upload (`run_ai_and_verdict`) y el de las transacciones
(`generate_transaction_report`). Lo que cambia:

  - `transaction_report._upsert` se sustituye por un colector: nada se guarda.
  - La sesion de base solo lee (config de IA y la ejecucion) y acaba en rollback.
  - `GeminiAnalyzer._generate` se envuelve para contar las llamadas REALES y
    guardar el prompt y la respuesta de cada una.

Salida: /tmp/r2/corrida_<etiqueta>.json. Decision de Fredy (R2): las corridas de
comparacion de informes se hacen asi, nunca por los endpoints que persisten.
"""
import asyncio
import copy
import inspect
import json
import os
import sys
import time

RAIZ = os.environ.get("R2_RAIZ", "/app")   # /tmp/r2_antes/backend = el codigo de HEAD
sys.path.insert(0, RAIZ)

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.test import TestExecution
from app.services.ai import gemini as G
from app.services.ai import transaction_report as TR
from app.services.ai.analysis_pipeline import run_ai_and_verdict
from app.services.jtl.transaction_series import build_transaction_series
from app.api.v1.endpoints.upload import _parse_execution_df, METRIC_KEYS

EJECUCION = "35ca5b92-dd0c-4fd5-abfd-f792ef695275"
SALIDA = "/tmp/r2"

LLAMADAS = []
_original = G.GeminiAnalyzer._generate


def _contado(self, prompt, section_name="unknown", *a, **kw):
    t0 = time.time()
    texto = _original(self, prompt, section_name, *a, **kw)
    LLAMADAS.append({"seccion": section_name, "segundos": round(time.time() - t0, 1),
                     "prompt": prompt, "respuesta": texto})
    print(f"  [{len(LLAMADAS)}] {section_name}: {time.time() - t0:.1f} s", flush=True)
    return texto


G.GeminiAnalyzer._generate = _contado

TRANSACCIONES = {}


async def _colector(db, execution_id, label, section, texto, orden):
    TRANSACCIONES.setdefault(label, {})[section] = texto


TR._upsert = _colector


async def main(etiqueta: str) -> int:
    os.makedirs(SALIDA, exist_ok=True)
    t_total = time.time()
    async with AsyncSessionLocal() as db:
        ex = (await db.execute(select(TestExecution).where(TestExecution.id == EJECUCION))).scalar_one()
        criterios = copy.deepcopy(ex.acceptance_criteria_json or {})
        criterios.pop("verdict", None)
        criterios.pop("verdicts_per_transaction", None)
        labels = list(criterios.get("critical_transactions") or [])
        labels.sort()

        parser, df = _parse_execution_df(ex)
        _, metrics = parser.df, parser._calculate_metrics(parser.df_main)
        # Lo mismo que /upload: metricas de las principales + las de redireccion.
        metrics["total_redirects"] = len(parser.df_redirects)
        metrics["redirect_labels"] = sorted(parser.redirect_labels)
        metrics["total_all_samples"] = len(parser.df)
        metrics["total_main_samples"] = len(parser.df_main)

        print(f"{ex.name} · {len(df)} muestras · {len(labels)} transacciones", flush=True)
        t0 = time.time()
        res = await run_ai_and_verdict(parser, metrics, ex.test_type or "load",
                                       copy.deepcopy(criterios), ex.metric_unit or "TPS", db)
        t_general = time.time() - t0
        n_general = len(LLAMADAS)

        summary_df = parser.get_summary_table_data()
        por_label = {str(r["label"]): r for _, r in summary_df.iterrows()}
        t0 = time.time()
        for label in labels:
            fila = por_label[label]
            m = {k: fila[k] for k in METRIC_KEYS}
            # El codigo de HEAD (la corrida «antes») no conoce `df_tx`.
            extra = ({"df_tx": df[df["label"] == label]}
                     if "df_tx" in inspect.signature(TR.generate_transaction_report).parameters else {})
            await TR.generate_transaction_report(
                db=db, execution_id=ex.id, label=label, metrics=m,
                series=build_transaction_series(df, label),
                test_type=ex.test_type or "load", acceptance_criteria=criterios, **extra,
            )
        t_tx = time.time() - t0
        await db.rollback()   # nada de lo leido o tocado en memoria se guarda

    general = {k: v for k, v in res.__dict__.items() if k.startswith("ai_") and k != "ai_status"}
    out = {
        "etiqueta": etiqueta, "ejecucion": EJECUCION,
        "ai_status": res.ai_status,
        "llamadas": {"total": len(LLAMADAS), "general": n_general, "transacciones": len(LLAMADAS) - n_general},
        "segundos": {"total": round(time.time() - t_total, 1), "general": round(t_general, 1),
                     "transacciones": round(t_tx, 1)},
        "general": general, "transacciones": TRANSACCIONES, "detalle": LLAMADAS,
    }
    ruta = f"{SALIDA}/corrida_{etiqueta}.json"
    json.dump(out, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"{ruta}: {out['llamadas']} en {out['segundos']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "prueba")))
