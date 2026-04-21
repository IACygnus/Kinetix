"""
ExecutionAttachment model — files associated to a TestExecution.
Types: 'monitoring' (KNX-13) and 'evidence' (KNX-14).
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class ExecutionAttachment(Base):
    __tablename__ = "execution_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("test_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type: 'monitoring' or 'evidence'
    attachment_type = Column(String(50), nullable=False)

    # Metadata
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)

    # File info
    filename = Column(String(500), nullable=False)
    filepath = Column(String(1000), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=True)

    sort_order = Column(Integer, default=0)

    # Per-image AI analysis (Sprint P1-A)
    ai_analysis = Column(Text, nullable=True)
    ai_analysis_updated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
