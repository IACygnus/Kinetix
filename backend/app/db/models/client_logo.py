"""
N1.1 — Logo del cliente para los informes exportados.

Tabla aparte (y no columnas nuevas en `clients`) por dos razones:
- `Base.metadata.create_all` CREA tablas nuevas pero no altera las existentes,
  asi que asi no hace falta ningun ALTER TABLE manual en dev ni en produccion
  (regla 10 del proyecto: no hay Alembic).
- Los bytes van en la base y no en /app/media, que en produccion no tiene
  volumen y se pierde en cada despliegue.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.db.base_class import Base


class ClientLogo(Base):
    __tablename__ = "client_logos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # unique: un solo logo por cliente. CASCADE: al borrar el cliente se va con el.
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    data = Column(LargeBinary, nullable=False)          # PNG normalizado (N1.2)
    mime_type = Column(String(50), nullable=False, default="image/png")
    file_size = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
