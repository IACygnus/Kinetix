"""
Data Files asociados a disenos AI Script. Cada diseno puede tener N archivos CSV
que sus CSVDataSets referencian. El archivo fisico se guarda en
backend/uploads/ai_data_files/{design_id}/{filename} y el modelo guarda metadata.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


class AIDesignDataFile(Base):
    __tablename__ = "ai_design_data_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    design_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_script_designs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Metadata del archivo
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)  # uuid + .csv
    file_path = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=False, default=0)

    # CSV-specific
    delimiter = Column(String(5), nullable=False, default=",")
    encoding = Column(String(50), nullable=False, default="UTF-8")
    has_header = Column(String(10), nullable=False, default="true")
    columns = Column(JSONB, nullable=False, default=list)  # ["col1", "col2", ...]
    row_count = Column(Integer, nullable=False, default=0)

    # Mapping a variables JMeter (variable_name -> column_name)
    # Si esta vacio, las variables son los nombres de columna directos.
    variable_mapping = Column(JSONB, nullable=False, default=dict)

    # Sprint 2.5c.1 (HF2.1) — vinculacion automatica con un CSV Data Set en la
    # estructura del diseno. Al subir un CSV con variables declaradas, se
    # autocrea un CSVDataSet y se guarda aqui su id para trazabilidad.
    linked_csv_dataset_id = Column(
        String(50),
        nullable=True,
        comment="ID del CSVDataSet asociado en la estructura. Null si no vinculado.",
    )
    variable_names_declared = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="Variables JMeter declaradas por el usuario. Ej: ['firstname','lastname']",
    )

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
