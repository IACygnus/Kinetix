"""
TransactionAnalysis model (N3.4) — analisis IA individual por transaccion.

Tabla nueva, no columna nueva: la regla 10 del proyecto dice que
`Base.metadata.create_all` crea tablas nuevas solas, mientras que una columna
en una tabla existente exigiria un ALTER TABLE manual. Mismo patron que
ExecutionAttachment: una fila por elemento, FK con CASCADE al borrar la
ejecucion.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class TransactionAnalysis(Base):
    __tablename__ = "transaction_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("test_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    label = Column(String(500), nullable=False)

    # Marcada por el premarcado determinista ('ai') o por el usuario ('user')
    is_critical = Column(Boolean, default=False)
    marked_by = Column(String(20), default="ai")

    # Foto de las metricas con las que se pidio el analisis (muestras, promedio,
    # p90, p95, max, errores, tasa_error): el informe debe poder reproducirse
    # aunque el JTL ya no este.
    metrics_json = Column(JSON, nullable=True)

    ai_analysis = Column(Text, nullable=True)
    ai_analysis_updated_at = Column(DateTime, nullable=True)

    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
