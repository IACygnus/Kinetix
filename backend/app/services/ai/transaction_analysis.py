"""
N3.4 — Registro de las transacciones marcadas como criticas.

N4.6 le quito el analisis IA. El texto por transaccion pasa a generarse bajo
demanda en `transaction_report.py` (8 secciones, tabla `transaction_chart_analyses`)
y este modulo se queda con lo que hacia gratis: dejar constancia de QUE
transacciones se marcaron y con que metricas, durante el upload.

Consecuencias, tal como se documento en el reporte 039 §3:
  - La fila de `transaction_analyses` se sigue creando, ahora con
    `ai_analysis` en NULL. Es lo que la UI necesita para ofrecer el boton
    "generar mini-informe".
  - `transaction_analyses.ai_analysis` queda LEGACY de solo lectura: las
    ejecuciones ya analizadas conservan su texto y el bloque N3.5 de los
    reportes viejos lo sigue mostrando. Nadie vuelve a escribir esa columna.
  - El upload deja de gastar IA aqui: cero llamadas y cero segundos anadidos
    por transaccion marcada.
"""
import logging
from typing import Dict, List, Optional

from app.db.models.transaction_analysis import TransactionAnalysis

logger = logging.getLogger(__name__)

# D4: tope blando heredado. Ya no protege tiempo de IA (no la hay), pero sigue
# acotando cuantas transacciones se registran desde un solo upload.
MAX_TRANSACTIONS = 10


async def analyze_critical_transactions(
    db,
    execution_id,
    summary_df,
    acceptance_criteria: Optional[Dict],
    test_type: str = "load",   # N4.6: sin uso desde que no hay IA aqui; se conserva
    analyzer=None,             # la firma para no tocar la llamada del upload
) -> Dict[str, int]:
    """Registra las transacciones marcadas con sus metricas. Nunca lanza.

    Devuelve contadores {requested, registered, skipped}. `analyzed` y `failed`
    desaparecieron con la IA en N4.6. Si no hay transacciones marcadas no toca
    la base: coste cero, igual que antes.
    """
    counters = {"requested": 0, "registered": 0, "skipped": 0}
    labels: List[str] = list((acceptance_criteria or {}).get("critical_transactions") or [])
    if not labels:
        return counters

    counters["requested"] = len(labels)
    if len(labels) > MAX_TRANSACTIONS:
        counters["skipped"] = len(labels) - MAX_TRANSACTIONS
        logger.warning(
            f"N3.4: {len(labels)} transacciones marcadas, se registran las primeras "
            f"{MAX_TRANSACTIONS} y se omiten {counters['skipped']}"
        )

    # Metricas por label desde el summary ya calculado (no se re-parsea el JTL)
    by_label = {str(r["label"]): r for _, r in summary_df.iterrows()} if summary_df is not None else {}

    for i, label in enumerate(labels[:MAX_TRANSACTIONS]):
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

        counters["registered"] += 1
        # N4.6: `ai_analysis` se deja en NULL a proposito. El texto de esta
        # transaccion se genera bajo demanda y vive en `transaction_chart_analyses`.
        db.add(TransactionAnalysis(
            execution_id=execution_id, label=label, is_critical=True, marked_by="user",
            metrics_json=metrics, ai_analysis=None,
            ai_analysis_updated_at=None,
            sort_order=i,
        ))

    try:
        await db.commit()
    except Exception as e:
        logger.error(f"N3.4: no se pudieron persistir los analisis por transaccion: {e}")
        await db.rollback()

    logger.info(f"N3.4: transacciones criticas {counters}")
    return counters
