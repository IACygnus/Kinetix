"""
F1 (aviso de respaldo) — de donde salio el texto de cada seccion de un informe.

Una fila por (ejecucion, transaccion, seccion). Nace del incidente del 26 al 28
de septiembre de 2026: la clave de OpenAI dejo de valer y Kinetix siguio
generando informes con el `FallbackAnalyzer` durante dos dias sin que nadie lo
supiera. El aviso de entonces era un toast de 5 s que no se guardaba en ningun
sitio.

Tabla NUEVA a proposito: una columna en `test_executions` obligaria a un ALTER
(regla 10) y, declarada en el modelo antes de aplicarlo, romperia cada lectura
de la tabla, que es lo que paso en la Etapa 2 con `ai_config.reasoning_effort`.
Esta la crea `Base.metadata.create_all` al arrancar: nada que ejecutar a mano.

  label = ''   -> seccion del informe GENERAL (section = la columna ai_*).
  label = X    -> seccion del informe de la transaccion X (section = summary,
                  chart_*). '' y no NULL porque un UNIQUE de Postgres no ve
                  duplicados entre NULLs.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class AISectionOrigin(Base):
    __tablename__ = "ai_section_origins"
    __table_args__ = (
        UniqueConstraint("execution_id", "label", "section", name="uq_ai_origin_exec_label_section"),
        Index("ix_ai_origin_execution", "execution_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("test_executions.id", ondelete="CASCADE"),
                          nullable=False)
    label = Column(String(500), nullable=False, default="")
    section = Column(String(60), nullable=False)

    # 'ia' | 'respaldo' | 'sin_texto' | 'fijo'. Texto libre y no Enum: un valor
    # nuevo no puede exigir un ALTER TYPE (regla 10).
    origen = Column(String(16), nullable=False)
    provider = Column(String(20), nullable=True)
    model = Column(String(80), nullable=True)
    # Ver `services/ai/origen.py::MOTIVOS`: clave, cupo, limite_proveedor, ...
    motivo_tipo = Column(String(24), nullable=True)
    motivo = Column(Text, nullable=True)          # el error literal del proveedor

    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Si alguien corrigio el texto a mano despues: deja de ser «de plantilla».
    edited_at = Column(DateTime, nullable=True)
