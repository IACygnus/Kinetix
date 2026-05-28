"""
AI Script Design — sesiones de diseno de scripts JMX con IA.

Cada registro representa una conversacion con el asistente IA para generar
un script JMeter. Puede estar en estado borrador (auto-guardado tras cada
turno) o guardado formalmente con nombre.
"""
import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.db.base_class import Base


class AIScriptDesign(Base):
    __tablename__ = "ai_script_designs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ID generado en el cliente al abrir la pagina; estable durante toda la sesion.
    # Permite UPSERT en cada auto-save sin duplicar registros.
    session_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)

    # Nullable mientras es draft; obligatorio tras "Guardar como..."
    name = Column(String(255), nullable=True)

    # Cliente obligatorio desde el inicio (se selecciona antes de entrar al disenador).
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Usuario creador.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Estado: true = auto-guardado sin nombre formal; false = guardado por el usuario.
    is_draft = Column(Boolean, nullable=False, default=True)

    # Conversacion completa: [{role: 'user'|'assistant', content: '...', timestamp: '...'}]
    conversation = Column(JSONB, nullable=False, default=list)

    # Ultimo JMX generado/refinado.
    current_jmx = Column(Text, nullable=True)

    # Archivo de referencia (Postman/Swagger/HAR/JMX/texto) adjuntado por el usuario.
    reference_file_name = Column(String(255), nullable=True)
    reference_file_content = Column(Text, nullable=True)
    reference_file_type = Column(String(50), nullable=True)  # postman | openapi | swagger | har | jmx | text

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
