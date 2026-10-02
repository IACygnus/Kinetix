"""Las sesiones del «Analista IA» — BLOQUE 5 (reporte 147).

Una sesion es la conversacion que lleva de un JTL a un informe: la prueba que se
cargo (cliente, proyecto, tipo, los JTL), la FICHA que se llena mientras el
analista conversa y los mensajes del chat. Al generar, apunta a la ejecucion que
salio de ella.

Las dos tablas son NUEVAS: las crea `Base.metadata.create_all` al arrancar. No
hay ni un ALTER que ejecutar (regla 10).
"""
from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base_class import Base

# abierta     se esta conversando; se puede tocar la ficha
# generando   la generacion esta en curso (una a la vez por sesion)
# generada    ya hay ejecucion; la ficha queda como estaba al generar
ESTADOS = ("abierta", "generando", "generada")


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"),
                       nullable=True)
    client_name = Column(String(255), nullable=True)
    project = Column(String(255), nullable=False)
    test_type = Column(String(30), nullable=False)
    metric_unit = Column(String(10), nullable=False, default="TPS")

    # [{"ruta": "/app/uploads/<ts>_<nombre>", "nombre": "<nombre>"}]: los JTL
    # guardados con el MISMO nombre que usa /upload, para que el informe los
    # encuentre igual que encuentra los de siempre.
    jtl = Column(JSONB, nullable=False, default=list)
    ficha = Column(JSONB, nullable=False, default=dict)
    mensajes = Column(JSONB, nullable=False, default=list)

    estado = Column(String(20), nullable=False, default="abierta")
    execution_id = Column(UUID(as_uuid=True), ForeignKey("test_executions.id", ondelete="SET NULL"),
                          nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AnalysisAttachment(Base):
    """El archivo con el detalle de los errores (CSV o XML de JMeter).

    `resumen` es el resumen determinista, YA enmascarado. El archivo original se
    guarda en disco como evidencia y no sale nunca por la API ni al log.
    Al generar, `execution_id` lo deja asociado a la ejecucion (B.8); la pantalla
    de Evidencias todavia no lo pinta.
    """
    __tablename__ = "analysis_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("test_executions.id", ondelete="SET NULL"),
                          nullable=True, index=True)
    nombre = Column(String(255), nullable=False)
    formato = Column(String(10), nullable=False)        # csv | xml
    ruta = Column(String(500), nullable=False)
    tamano = Column(BigInteger, nullable=False)
    resumen = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
