"""
N3.4 — Analisis IA individual de las transacciones marcadas como criticas.

Vive aparte de `analysis_pipeline.run_ai_and_verdict` a proposito: ese pipeline
son 12 pasos fijos que devuelven un dataclass de campos fijos (§4.1 del
diagnostico 025). Meter aqui N secciones dinamicas obligaria a reescribirlo, con
el riesgo de regresion que eso implica sobre el analisis que ya funciona.

Reglas del proyecto que se respetan:
  - regla 14: `sanitize_ai_text` sobre toda respuesta antes de persistir.
  - leccion GRAF1: el prompt SIEMPRE lleva el max, para que el analisis no se
    coma los picos de una transaccion que en promedio se ve sana.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.db.models.transaction_analysis import TransactionAnalysis
from app.services.ai.gemini import (
    SYSTEM_PROMPT,
    get_gemini_analyzer,
    load_ai_config_from_db,
    sanitize_ai_text,
)

logger = logging.getLogger(__name__)

# D4: tope blando. No bloquea la seleccion de Fredy (eso es cosa del panel);
# aqui protege el tiempo del upload, que hace las llamadas en serie.
MAX_TRANSACTIONS = 10


def build_transaction_prompt(label: str, m: Dict, test_type: str = "load") -> str:
    """Prompt de una transaccion. El max es obligatorio (leccion GRAF1)."""
    avg = float(m.get("promedio", 0) or 0)
    mx = float(m.get("max", 0) or 0)
    ratio = f"{mx / avg:.0f}x el promedio" if avg > 0 else "sin promedio de referencia"
    return f"""{SYSTEM_PROMPT}

Analiza UNA transaccion concreta de una prueba de {test_type}: "{label}".

METRICAS REALES DE LA TRANSACCION:
- Muestras ejecutadas: {int(m.get('muestras', 0)):,}
- Tiempo promedio: {avg:.0f} ms
- Percentil 90: {float(m.get('p90', 0)):.0f} ms
- Percentil 95: {float(m.get('p95', 0)):.0f} ms
- Tiempo maximo observado: {mx:.0f} ms ({ratio})
- Errores: {int(m.get('errores', 0)):,} ({float(m.get('tasa_error', 0)):.2f}% de sus muestras)

Maximo 200 palabras. Interpreta el comportamiento de esta transaccion: si el
maximo se dispara respecto al promedio, explica esos picos y su causa probable
(timeouts, contencion, esperas de recursos) aunque el promedio se vea sano.
Cierra con una oracion sobre el impacto en produccion."""


async def analyze_critical_transactions(
    db,
    execution_id,
    summary_df,
    acceptance_criteria: Optional[Dict],
    test_type: str = "load",
    analyzer=None,
) -> Dict[str, int]:
    """Analiza y persiste las transacciones marcadas. Nunca lanza.

    Devuelve contadores {requested, analyzed, failed, skipped}. Si no hay
    transacciones marcadas no toca la IA ni la base: coste cero y el upload se
    comporta exactamente como antes de N3.4.
    """
    counters = {"requested": 0, "analyzed": 0, "failed": 0, "skipped": 0}
    labels: List[str] = list((acceptance_criteria or {}).get("critical_transactions") or [])
    if not labels:
        return counters

    counters["requested"] = len(labels)
    if len(labels) > MAX_TRANSACTIONS:
        counters["skipped"] = len(labels) - MAX_TRANSACTIONS
        logger.warning(
            f"N3.4: {len(labels)} transacciones marcadas, se analizan las primeras "
            f"{MAX_TRANSACTIONS} y se registran {counters['skipped']} sin analisis"
        )

    # Metricas por label desde el summary ya calculado (no se re-parsea el JTL)
    by_label = {str(r["label"]): r for _, r in summary_df.iterrows()} if summary_df is not None else {}

    if analyzer is None:
        try:
            conf = await load_ai_config_from_db(db)
            analyzer = get_gemini_analyzer(
                provider=conf.get("provider", ""),
                model_name=conf.get("model_name", ""),
                api_key=conf.get("api_key", ""),
            )
        except Exception as e:
            logger.error(f"N3.4: sin analizador disponible ({e}); se registran las filas sin analisis")
            analyzer = None

    for i, label in enumerate(labels):
        row = by_label.get(label)
        if row is None:
            logger.warning(f"N3.4: '{label}' no esta en el JTL, se omite")
            counters["skipped"] += 1
            continue

        metrics = {
            "muestras": int(row["muestras"]), "promedio": float(row["promedio"]),
            "p90": float(row["p90"]), "p95": float(row["p95"]), "max": float(row["max"]),
            "errores": int(row["errores"]), "tasa_error": float(row["tasa_error"]),
        }

        texto = None
        if analyzer is not None and i < MAX_TRANSACTIONS:
            try:
                prompt = build_transaction_prompt(label, metrics, test_type)
                texto = analyzer._generate(prompt, section_name=f"transaction_{i}")
                if texto:
                    texto = sanitize_ai_text(texto)   # regla 14
            except Exception as e:
                # Un fallo individual (429, timeout) no puede tumbar el upload:
                # se guarda la fila con sus metricas y sin analisis.
                logger.error(f"N3.4: fallo el analisis de '{label}': {e}")

        if texto:
            counters["analyzed"] += 1
        elif i < MAX_TRANSACTIONS:
            counters["failed"] += 1      # los de mas alla del tope ya cuentan como skipped

        db.add(TransactionAnalysis(
            execution_id=execution_id, label=label, is_critical=True, marked_by="user",
            metrics_json=metrics, ai_analysis=texto,
            ai_analysis_updated_at=datetime.utcnow() if texto else None,
            sort_order=i,
        ))

    try:
        await db.commit()
    except Exception as e:
        logger.error(f"N3.4: no se pudieron persistir los analisis por transaccion: {e}")
        await db.rollback()

    logger.info(f"N3.4: transacciones criticas {counters}")
    return counters
