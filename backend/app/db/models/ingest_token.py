"""Los tokens de ingesta del agente — ETAPA O2e (O-D49).

El agente de un cliente (O2b) escribe sus metricas por `POST /api/v1/ingesta`,
no directamente en InfluxDB (O-D48). Para entrar necesita un token, y ese token
es de **un solo cliente**: el backend rechaza las lineas que digan ser de otro
(O-D50). InfluxDB no puede hacer esa comprobacion — sus tokens se acotan por
cubo, no por etiqueta —, y por eso el token de InfluxDB no sale nunca del
servidor.

**Aqui no se guarda el token, se guarda su huella** (SHA-256). El token se
ensena una sola vez, al crearlo; si se pierde, se revoca y se crea otro. Con
la base entera en la mano no se puede escribir en nombre de nadie.

No se borra: se revoca. Una fila revocada es la constancia de que ese token
existio y de hasta cuando valio.
"""
from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class IngestToken(Base):
    """Un token con el que el agente de un cliente escribe en el cubo `infra`."""

    __tablename__ = "ingest_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # O-D49: un token es SIEMPRE de un cliente, y solo deja escribir lineas con
    # su etiqueta `cliente`. Al borrar el cliente se van sus tokens: sin
    # cliente no hay contra que comparar.
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # SHA-256 del token en hexadecimal. Unica: es por donde se busca en cada
    # peticion. El token tiene 256 bits al azar, asi que no hace falta sal —
    # no hay diccionario que probar contra una huella de algo que no se eligio.
    huella = Column(String(64), nullable=False, unique=True)

    # Los primeros caracteres, para que la pantalla distinga dos tokens del
    # mismo cliente sin ensenar ninguno. No permiten reconstruirlo.
    prefijo = Column(String(16), nullable=False)

    creado_en = Column(DateTime, nullable=False, default=datetime.utcnow)
    creado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Lo que permite decir «este cliente dejo de enviar a las 10:14».
    ultimo_uso = Column(DateTime, nullable=True)

    # NULL = vale. Con fecha = revocado desde esa fecha, y ya no entra nada.
    revocado_en = Column(DateTime, nullable=True)
    revocado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
