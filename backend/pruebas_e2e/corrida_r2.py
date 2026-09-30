"""ETAPA R2 — una corrida COMPLETA del informe, en proceso y SIN escribir en la base.

    docker exec jmeter_backend python3 /app/pruebas_e2e/corrida_r2.py <etiqueta> [<ejecucion>]

Genera el informe general y el de cada transaccion que ya tenga informe, de la
ejecucion dada (por defecto `35ca5b92`, «Nova capa media», carga, 8,28%), con el
mismo codigo que usa /upload (`run_ai_and_verdict`) y el de las transacciones
(`generate_transaction_report`). Lo que cambia:

  - `transaction_report._upsert` se sustituye por un colector: nada se guarda.
  - La conexion es de SOLO LECTURA (`default_transaction_read_only=on`) y sin
    autoflush: cualquier escritura que se colara fallaria en vez de guardarse.
    Acaba en rollback.
  - `GeminiAnalyzer._generate` se envuelve para contar las llamadas REALES y
    guardar el prompt y la respuesta de cada una. Si devuelve None, la seccion
    salio del RESPALDO y se anota en `respaldo`.
  - `_emit_ai_telemetry` se envuelve para sumar los tokens de cada intento. Al
    primer 429 (limite o cuota) o fallo transitorio (tiempo, red, 5xx), se
    guarda lo que haya y el proceso sale con codigo 3: la corrida para ahi.

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
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models.test import TestExecution
from app.services.ai import gemini as G
from app.services.ai import transaction_report as TR
from app.services.ai.analysis_pipeline import run_ai_and_verdict
from app.services.jtl.transaction_series import build_transaction_series
from app.api.v1.endpoints.upload import _parse_execution_df, METRIC_KEYS

EJECUCION = "35ca5b92-dd0c-4fd5-abfd-f792ef695275"
SALIDA = "/tmp/r2"

# Solo lectura de verdad: la base rechaza cualquier INSERT/UPDATE de esta conexion.
_motor = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    connect_args={"server_settings": {"default_transaction_read_only": "on"}})
SesionLectura = async_sessionmaker(_motor, class_=AsyncSession, expire_on_commit=False,
                                   autocommit=False, autoflush=False)

LLAMADAS = []
TOKENS = []       # un registro por INTENTO, de la telemetria E1.2
RESPALDO = []     # secciones en las que `_generate` devolvio None
PARADA = {}       # el primer 429 o fallo de tiempo
ESTADO = {}       # etiqueta, ejecucion y transaccion en curso
_original = G.GeminiAnalyzer._generate
if os.environ.get("R2_SECO"):
    # En seco: sin IA. Para probar el recorrido entero antes de gastar llamadas.
    _original = lambda self, prompt, section_name="unknown", *a, **kw: f"[seco] {section_name}"
_tel_original = G._emit_ai_telemetry
_tel_firma = inspect.signature(_tel_original)


def _telemetria(*a, **kw):
    try:
        arg = _tel_firma.bind(*a, **kw).arguments
        u = getattr(arg.get("response"), "usage", None)
        ctd = getattr(u, "completion_tokens_details", None)
        ptd = getattr(u, "prompt_tokens_details", None)
        outcome = arg.get("outcome")
        TOKENS.append({
            "seccion": arg.get("section"), "transaccion": ESTADO.get("label"),
            "intento": arg.get("attempt"), "outcome": outcome,
            "prompt_tokens": getattr(u, "prompt_tokens", None),
            "completion_tokens": getattr(u, "completion_tokens", None),
            "reasoning_tokens": getattr(ctd, "reasoning_tokens", None),
            "cached_tokens": getattr(ptd, "cached_tokens", None),
        })
        if not PARADA and outcome in ("rate_limited", "quota_exhausted", "transient_error"):
            PARADA.update({"seccion": arg.get("section"), "transaccion": ESTADO.get("label"),
                           "outcome": outcome})
    except Exception:
        pass
    return _tel_original(*a, **kw)


def _contado(self, prompt, section_name="unknown", *a, **kw):
    t0 = time.time()
    texto = _original(self, prompt, section_name, *a, **kw)
    LLAMADAS.append({"seccion": section_name, "transaccion": ESTADO.get("label"),
                     "segundos": round(time.time() - t0, 1),
                     "prompt": prompt, "respuesta": texto})
    if not texto:
        RESPALDO.append({"seccion": section_name, "transaccion": ESTADO.get("label"),
                         "error": str(G.GeminiAnalyzer._last_error or "")[:300]})
    print(f"  [{len(LLAMADAS)}] {ESTADO.get('label') or 'general'} / {section_name}: "
          f"{time.time() - t0:.1f} s{'  RESPALDO' if not texto else ''}", flush=True)
    if PARADA:
        PARADA["error"] = str(G.GeminiAnalyzer._last_error or "")[:300]
        print(f"PARADA: {PARADA}", flush=True)
        _volcar(parcial=True)
        os._exit(3)
    return texto


G.GeminiAnalyzer._generate = _contado
G._emit_ai_telemetry = _telemetria

TRANSACCIONES = {}


async def _colector(db, execution_id, label, section, texto, orden, **kw):
    # **kw: desde F1, `_upsert` recibe tambien el origen del texto; aqui no se guarda.
    TRANSACCIONES.setdefault(label, {})[section] = texto


TR._upsert = _colector


def _volcar(parcial=False, extra=None):
    out = {
        "etiqueta": ESTADO.get("etiqueta"), "ejecucion": ESTADO.get("ejecucion"),
        "raiz": RAIZ, "parcial": parcial, "parada": PARADA or None,
        "respaldo": RESPALDO, "tokens": TOKENS,
        **(extra or {}),
        "transacciones": TRANSACCIONES, "detalle": LLAMADAS,
    }
    ruta = f"{SALIDA}/corrida_{ESTADO.get('etiqueta')}.json"
    json.dump(out, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return ruta, out


async def main(etiqueta: str, ejecucion: str) -> int:
    os.makedirs(SALIDA, exist_ok=True)
    ESTADO.update({"etiqueta": etiqueta, "ejecucion": ejecucion})
    t_total = time.time()
    async with SesionLectura() as db:
        ex = (await db.execute(select(TestExecution).where(TestExecution.id == ejecucion))).scalar_one()
        # Se lee YA: tras el rollback del final, `ex` queda expirado y leerlo lanza.
        ESTADO["ejecucion_nombre"] = ex.name
        ex_tipo, ex_unidad = ex.test_type or "load", ex.metric_unit or "TPS"
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

        print(f"{ex.name} · {len(df)} muestras · {len(labels)} transacciones · {RAIZ}", flush=True)
        t0 = time.time()
        res = await run_ai_and_verdict(parser, metrics, ex.test_type or "load",
                                       copy.deepcopy(criterios), ex.metric_unit or "TPS", db)
        t_general = time.time() - t0
        n_general = len(LLAMADAS)

        summary_df = parser.get_summary_table_data()
        por_label = {str(r["label"]): r for _, r in summary_df.iterrows()}
        t0 = time.time()
        for label in labels:
            ESTADO["label"] = label
            fila = por_label[label]
            m = {k: fila[k] for k in METRIC_KEYS}
            # El codigo de HEAD (la corrida «antes») no conoce `df_tx`.
            firma = inspect.signature(TR.generate_transaction_report).parameters
            extra = {"df_tx": df[df["label"] == label]} if "df_tx" in firma else {}
            if "contexto" in firma:   # BLOQUE 2.2: el bloque de la ejecucion y sus fases
                from app.services.ai.contexto_prompt import contexto_de_parser
                extra["contexto"], extra["fases"] = contexto_de_parser(
                    parser, ex_tipo, ex_unidad, criterios, metrics=metrics)
            elif "fases" in firma:   # BLOQUE 2.1: las fases de la prueba entera
                from app.services.ai import fases as F
                extra["fases"] = F.calcular(df)
            await TR.generate_transaction_report(
                db=db, execution_id=ex.id, label=label, metrics=m,
                series=build_transaction_series(df, label),
                test_type=ex.test_type or "load", acceptance_criteria=criterios, **extra,
            )
        t_tx = time.time() - t0
        await db.rollback()   # nada de lo leido o tocado en memoria se guarda

    general = {k: v for k, v in res.__dict__.items() if k.startswith("ai_") and k != "ai_status"}
    ruta, out = _volcar(extra={
        "ejecucion_nombre": ESTADO["ejecucion_nombre"],
        "ai_status": res.ai_status,
        "llamadas": {"total": len(LLAMADAS), "general": n_general, "transacciones": len(LLAMADAS) - n_general},
        "segundos": {"total": round(time.time() - t_total, 1), "general": round(t_general, 1),
                     "transacciones": round(t_tx, 1)},
        "general": general,
    })
    print(f"{ruta}: {out['llamadas']} en {out['segundos']} · respaldo={len(RESPALDO)}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "prueba",
                                  sys.argv[2] if len(sys.argv) > 2 else EJECUCION)))
    except Exception as e:
        # Lo generado cuesta llamadas reales: se guarda aunque algo falle al final.
        PARADA.setdefault("outcome", f"excepcion: {type(e).__name__}: {str(e)[:200]}")
        ruta, _ = _volcar(parcial=True)
        print(f"EXCEPCION, parcial en {ruta}: {e}", flush=True)
        raise
