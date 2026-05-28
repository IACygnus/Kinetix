"""
Schemas Pydantic para AI Script Design.
"""
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# -------- Mensaje del chat --------

class ConversationMessage(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str
    timestamp: Optional[str] = None


# -------- Upsert (auto-save) --------

class AIScriptDesignUpsert(BaseModel):
    """Payload para auto-save / upsert por session_id."""
    session_id: UUID
    client_id: UUID
    conversation: List[ConversationMessage] = []
    current_jmx: Optional[str] = None
    reference_file_name: Optional[str] = None
    reference_file_content: Optional[str] = None
    reference_file_type: Optional[str] = None


# -------- Save As (promover draft a guardado) --------

class AIScriptDesignSaveAs(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    client_id: Optional[UUID] = None  # opcional: permitir cambiar cliente al guardar


# -------- Respuestas --------

class AIScriptDesignSummary(BaseModel):
    """Listado: solo metadata, sin conversacion ni JMX para aligerar payload."""
    id: UUID
    session_id: UUID
    name: Optional[str]
    client_id: UUID
    user_id: Optional[UUID]
    is_draft: bool
    message_count: int = 0  # se calcula en el endpoint
    has_jmx: bool = False   # se calcula en el endpoint
    reference_file_name: Optional[str]
    reference_file_type: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AIScriptDesignDetail(BaseModel):
    """Detalle completo para hidratar la pagina del disenador."""
    id: UUID
    session_id: UUID
    name: Optional[str]
    client_id: UUID
    user_id: Optional[UUID]
    is_draft: bool
    conversation: List[Any] = []  # Any para no forzar validacion estricta de mensajes legacy
    current_jmx: Optional[str]
    reference_file_name: Optional[str]
    reference_file_content: Optional[str]
    reference_file_type: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
