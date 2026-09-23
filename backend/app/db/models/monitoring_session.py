"""Las sesiones de monitoreo — ETAPA O2d (O-D35).

Hasta O2c, «una corrida» era una cadena de texto que Kinetix generaba y que
alguien tenia que copiar antes de cambiar de pestana. Si te ibas, se perdia.

Una sesion es esa corrida **guardada**: con su nombre, su cliente, su proyecto,
los servidores que se estan mirando, su estado y sus fechas. Sales, vuelves, y
sigue ahi con sus metricas (O-D40).
"""
from datetime import datetime
import uuid

from sqlalchemy import (
    Column, DateTime, ForeignKey, String, Table, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base

# Los tres estados de una sesion, en el orden en que ocurren.
#
#   preparada  se creo, todavia no ha llegado ni una metrica suya
#   en_curso   estan llegando metricas con su corrida
#   terminada  se cerro, o llevaba un rato sin recibir nada
ESTADOS = ("preparada", "en_curso", "terminada")


# Que servidores mira cada sesion. Tabla de union y no una lista en JSON: asi
# borrar un servidor no deja sesiones apuntando a un id que ya no existe.
sesion_servidores = Table(
    "monitoring_session_servers", Base.metadata,
    Column("session_id", UUID(as_uuid=True),
           ForeignKey("monitoring_sessions.id", ondelete="CASCADE"),
           primary_key=True),
    Column("server_id", UUID(as_uuid=True),
           ForeignKey("observed_servers.id", ondelete="CASCADE"),
           primary_key=True),
)


class MonitoringSession(Base):
    """Una prueba que se esta mirando, o que se miro."""

    __tablename__ = "monitoring_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    nombre = Column(String(200), nullable=False)
    client_id = Column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True)
    proyecto = Column(String(200), nullable=False)

    # La misma cadena de O-D4 que viaja en la etiqueta `application` del Backend
    # Listener y en la etiqueta `corrida` del recolector. Es la llave de todo:
    # por ella se buscan las metricas de la prueba y las del servidor.
    corrida = Column(String(255), nullable=False, unique=True, index=True)

    estado = Column(String(20), nullable=False, default="preparada")
    notas = Column(Text, nullable=True)

    creada_en = Column(DateTime, default=datetime.utcnow)
    # Cuando llego su primera metrica y cuando la ultima. Con esas dos fechas,
    # una sesion terminada sabe que rango pedirle a InfluxDB sin que nadie se
    # acuerde de cuando fue (O-D40).
    empezo_en = Column(DateTime, nullable=True)
    termino_en = Column(DateTime, nullable=True)

    creada_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("client_id", "nombre", name="uq_sesion_cliente_nombre"),
    )
