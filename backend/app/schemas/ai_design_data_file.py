"""
Schemas Pydantic para AI Design Data Files (Sprint 2.4-HF2).
"""
from datetime import datetime
from typing import Dict, List
from uuid import UUID

from pydantic import BaseModel, Field


class DataFilePreview(BaseModel):
    """Preview de las primeras N filas + columnas detectadas."""
    columns: List[str]
    rows: List[List[str]]  # primeras 5 filas
    row_count_total: int
    delimiter_detected: str
    encoding_detected: str


class DataFileSummary(BaseModel):
    id: UUID
    design_id: UUID
    original_filename: str
    file_size: int
    delimiter: str
    encoding: str
    columns: List[str]
    row_count: int
    variable_mapping: Dict[str, str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DataFileMappingUpdate(BaseModel):
    """PATCH para actualizar el mapping de variables."""
    variable_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping variable_jmeter -> column_csv. Vacio = usar nombres de columna directos.",
    )
