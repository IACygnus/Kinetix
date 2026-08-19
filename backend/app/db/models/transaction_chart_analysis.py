"""
TransactionChartAnalysis model (N4.5) — los 8 textos del mini-informe por
transaccion, uno por fila.

Diseño aprobado en el reporte 036 §4.2 (opcion C). Las dos alternativas se
descartaron ahi: columnas nuevas en `transaction_analyses` exigiria ALTER TABLE
(prohibido por la regla 10) y meter los 8 textos dentro de un JSON haria
imposible editar uno solo sin reescribir el resto — que es justo lo que F5
permite hoy con los analisis de seccion.

Una fila por texto: guardar es un INSERT, editar es un UPDATE de una fila.

Relacion con `transaction_analyses` (N3.4): la COMPLEMENTA, no la reemplaza.
  - `transaction_analyses` = registro de QUE transacciones se marcaron como
    criticas (`is_critical`, `marked_by`, `sort_order`) y la foto de metricas
    con la que se marcaron (`metrics_json`).
  - `transaction_chart_analyses` = los TEXTOS del mini-informe de esas
    transacciones.
Esa division deja limpio el camino de N4.6: cuando el analisis IA de N3.4 salga
del upload, `transaction_analyses` conserva su rol de registro (la fila la sigue
creando el premarcado determinista, con `ai_analysis` en NULL) y el texto pasa a
vivir aqui como seccion 'summary'. Nada que migrar y ninguna tabla que tocar.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, Integer, Boolean,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base
from app.services.jtl.transaction_series import CHART_TYPES

# Las 8 secciones del mini-informe. Las 5 del medio se derivan de CHART_TYPES
# (N4.3) para que el discriminador no pueda desalinearse de las series que
# realmente se calculan. Prefijo 'chart_' por legibilidad y por simetria con los
# nombres que ya usa el analisis global ('chart_latency', 'chart_error_rate'...).
SECTIONS = (
    ("summary",)
    + tuple(f"chart_{c}" for c in CHART_TYPES)
    + ("conclusions", "recommendations")
)


class TransactionChartAnalysis(Base):
    __tablename__ = "transaction_chart_analyses"
    __table_args__ = (
        # Un texto por (ejecucion, transaccion, seccion): hace el guardado
        # idempotente y bloquea duplicados si se regenera el mini-informe.
        UniqueConstraint(
            "execution_id", "label", "section",
            name="uq_txchart_execution_label_section",
        ),
        # Lectura tipica: todas las secciones de UNA transaccion.
        Index("ix_txchart_execution_label", "execution_id", "label"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("test_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    label = Column(String(500), nullable=False)
    # Uno de SECTIONS. Sin Enum de Postgres a proposito: añadir una seccion
    # nueva exigiria ALTER TYPE, y la regla 10 lo prohibe igual que un ALTER TABLE.
    section = Column(String(40), nullable=False)

    ai_analysis = Column(Text, nullable=True)

    # Patron 'edited' del consolidado (integrated_report.py:2027) que F5
    # aprovecha: cuando se genero + si el usuario lo toco despues.
    generated_at = Column(DateTime, default=datetime.utcnow)
    is_edited = Column(Boolean, default=False, nullable=False)
    ai_analysis_updated_at = Column(DateTime, nullable=True)

    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
