# backend/app/db/models/data_file.py
"""
Modelo DataFile — Archivos de datos (CSV) asociados a un ScriptDesign.
Almacena columnas detectadas y mapeo de variables para parametrizacion.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base


class DataFile(Base):
    __tablename__ = "data_files"

    id = Column(Integer, primary_key=True, index=True)

    script_id = Column(Integer, ForeignKey("script_designs.id"), nullable=False)

    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)   # nombre en disco
    file_path = Column(String(500), nullable=False)

    # Columnas detectadas automaticamente al parsear el archivo
    # ["username", "password", "email"]
    columns = Column(JSON, nullable=False, default=list)

    row_count = Column(Integer, nullable=True)

    # Asignacion de columnas a variables del script
    # {"username": "${username}", "password": "${password}"}
    variable_mapping = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    script = relationship("ScriptDesign", back_populates="data_files")
