"""
Modelo de configuracion de IA
Soporta Gemini y OpenAI. Limites diarios y mensuales.
"""
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, date
import uuid

from app.db.base_class import Base


class AIConfig(Base):
    __tablename__ = "ai_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Provider: "gemini" or "openai"
    provider = Column(String(50), nullable=False, default="gemini")

    # Model name (e.g. "gemini-2.5-flash", "gpt-4o-mini")
    model_name = Column(String(100), nullable=False, default="gemini-2.5-flash")

    # Fernet-encrypted API key
    api_key_encrypted = Column(Text, nullable=True)

    # Active flag
    is_active = Column(Boolean, default=True, nullable=False)

    # Rate limits
    daily_request_limit = Column(Integer, default=1000, nullable=False)
    monthly_request_limit = Column(Integer, default=20000, nullable=False)

    # Usage counters
    daily_requests_used = Column(Integer, default=0, nullable=False)
    monthly_requests_used = Column(Integer, default=0, nullable=False)

    # Auto-reset dates
    last_reset_daily = Column(Date, default=date.today, nullable=False)
    last_reset_monthly = Column(Date, default=date.today, nullable=False)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
