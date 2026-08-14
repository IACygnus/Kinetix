# backend/app/api/v1/endpoints/data_files.py
"""
Endpoints para gestion de archivos de datos CSV para parametrizacion de scripts.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.db.models.data_file import DataFile
from app.db.models.script_design import ScriptDesign
from app.services.engine.data_file_service import DataFileService

router = APIRouter()


class DataFileResponse(BaseModel):
    id: int
    script_id: int
    original_filename: str
    stored_filename: str
    file_path: str
    columns: list
    row_count: Optional[int]
    variable_mapping: dict
    created_at: datetime

    class Config:
        from_attributes = True


class VariableMappingUpdate(BaseModel):
    variable_mapping: dict


@router.post("/upload", response_model=DataFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_data_file(
    script_id: int = Form(...),
    file: UploadFile = File(..., description="Archivo CSV con header en primera fila"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Subir un archivo CSV como fuente de datos para un script.
    Detecta automaticamente las columnas del header.
    """
    # Verificar que el script existe
    result = await db.execute(select(ScriptDesign).where(ScriptDesign.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script no encontrado")

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="El archivo debe ser .csv")

    content_bytes = await file.read()
    if len(content_bytes) > 10 * 1024 * 1024:  # 10MB max
        raise HTTPException(status_code=413, detail="El CSV supera el limite de 10MB")

    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content_str = content_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="No se pudo decodificar el archivo CSV")

    svc = DataFileService()

    try:
        columns, row_count = svc.parse_csv(content_str, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    stored_filename, file_path = svc.save_file(content_bytes, file.filename)

    # Variable mapping por defecto: columna -> ${columna}
    variable_mapping = {col: f"${{{col}}}" for col in columns}

    data_file = DataFile(
        script_id=script_id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=file_path,
        columns=columns,
        row_count=row_count,
        variable_mapping=variable_mapping,
    )
    db.add(data_file)
    await db.commit()
    await db.refresh(data_file)
    return data_file


@router.get("/script/{script_id}", response_model=List[DataFileResponse])
async def list_data_files(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Listar todos los data files de un script."""
    result = await db.execute(
        select(DataFile).where(DataFile.script_id == script_id)
        .order_by(DataFile.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{file_id}/preview")
async def preview_data_file(
    file_id: int,
    column: Optional[str] = None,
    rows: int = 5,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Retornar las primeras N filas del CSV para previsualizacion.
    Si se pasa `column`, retorna solo los valores de esa columna.
    """
    result = await db.execute(select(DataFile).where(DataFile.id == file_id))
    data_file = result.scalar_one_or_none()
    if not data_file:
        raise HTTPException(status_code=404, detail="Data file no encontrado")

    # Column-specific preview
    if column:
        from pathlib import Path
        import csv
        for base in ["data/uploaded_files", "backend/data/uploaded_files", "/app/data/uploaded_files"]:
            file_path = Path(base) / data_file.stored_filename
            if file_path.exists():
                break
        else:
            file_path = Path(data_file.file_path)

        values = []
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        if i >= rows:
                            break
                        if column in row:
                            values.append(row[column])
            except Exception:
                pass

        return {
            "values": values,
            "column": column,
            "filename": data_file.original_filename,
        }

    # Full preview (original behavior)
    svc = DataFileService()
    preview_rows = svc.read_preview(data_file.file_path, max_rows=rows)

    return {
        "columns": data_file.columns,
        "rows": preview_rows,
        "row_count": data_file.row_count,
        "variable_mapping": data_file.variable_mapping,
    }


@router.put("/{file_id}/mapping", response_model=DataFileResponse)
async def update_variable_mapping(
    file_id: int,
    payload: VariableMappingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Actualizar el mapeo de columnas a variables del script."""
    result = await db.execute(select(DataFile).where(DataFile.id == file_id))
    data_file = result.scalar_one_or_none()
    if not data_file:
        raise HTTPException(status_code=404, detail="Data file no encontrado")

    data_file.variable_mapping = payload.variable_mapping
    await db.commit()
    await db.refresh(data_file)
    return data_file


@router.get("/{file_id}/columns")
async def get_data_file_columns(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Retorna las columnas detectadas en la primera fila del CSV."""
    result = await db.execute(
        select(DataFile).where(DataFile.id == file_id)
    )
    data_file = result.scalar_one_or_none()
    if not data_file:
        raise HTTPException(status_code=404, detail="Data file not found")

    # Si ya tenemos columnas en la DB, retornarlas directamente
    if data_file.columns:
        return {"columns": data_file.columns}

    # Sino, leer del archivo
    from pathlib import Path
    file_path = Path(data_file.file_path)
    if not file_path.exists():
        return {"columns": []}

    try:
        import csv
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
        return {"columns": list(columns)}
    except Exception as e:
        return {"columns": [], "error": str(e)}


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    # SEC-2: borrar es exclusivo de admin en toda la plataforma.
    current_user=Depends(require_role(["admin"])),
):
    """Eliminar un data file (del disco y de la DB)."""
    result = await db.execute(select(DataFile).where(DataFile.id == file_id))
    data_file = result.scalar_one_or_none()
    if not data_file:
        raise HTTPException(status_code=404, detail="Data file no encontrado")

    # Eliminar archivo del disco
    from pathlib import Path
    file_path = Path(data_file.file_path)
    if file_path.exists():
        file_path.unlink()

    await db.delete(data_file)
    await db.commit()
