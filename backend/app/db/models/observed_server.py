"""Los servidores que se miran durante una prueba — ETAPA O2c (O-D23).

Hasta O2b, qué servidor se observaba vivía en un fichero de configuracion del
laboratorio. Eso no escala a un cliente: hace falta poder darlos de alta desde
la pantalla, saber de quién son y guardar su credencial sin que nadie la vuelva
a leer.

**La credencial va cifrada con Fernet**, igual que la clave de IA y el token de
InfluxDB, y **no vuelve a salir nunca** (O-D26): ni en una respuesta de la API,
ni en la pantalla. Se sustituye, no se lee.
"""
from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base

# Los tipos y los modos son de la etapa, no de la base: se validan en el
# esquema de Pydantic. Aqui se dejan como texto para que anadir «mysql» en O3
# no obligue a un ALTER en una base que no usa Alembic (regla 10).
TIPOS = ("linux", "windows", "postgresql", "otro")
MODOS = ("sin_agente", "agente")


class ObservedServer(Base):
    """Un servidor que se observa durante las pruebas de un cliente."""

    __tablename__ = "observed_servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # O-D27: un servidor es SIEMPRE de un cliente. La corrida de O1 ya lleva
    # cliente, asi que al lanzar una prueba se sabe qué servidores mirar.
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name = Column(String(200), nullable=False)
    tipo = Column(String(20), nullable=False, default="linux")
    modo = Column(String(20), nullable=False, default="sin_agente")

    # Cómo se llega. El puerto se guarda aparte del host a proposito: asi la
    # pantalla puede proponer el de siempre (22, 5432) sin que nadie lo teclee.
    direccion = Column(String(255), nullable=False)
    puerto = Column(Integer, nullable=False, default=22)
    usuario = Column(String(120), nullable=True)

    # O-D26. Es una llave privada o una contrasena, cifrada con Fernet. Nunca
    # sale de aqui: los endpoints devuelven `tiene_credencial`, no el valor.
    credencial_cifrada = Column(Text, nullable=True)

    activo = Column(Boolean, nullable=False, default=True)
    notas = Column(String(1000), nullable=True)

    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow)
    creado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        # Dos servidores del mismo cliente no pueden llamarse igual: si no, en
        # el desplegable de la pantalla no habria forma de distinguirlos.
        UniqueConstraint("client_id", "name", name="uq_servidor_cliente_nombre"),
    )
