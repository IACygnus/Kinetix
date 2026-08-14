"""
Endpoints para gestion de Data Files asociados a disenos AI Script (Sprint 2.4-HF2).

Rutas montadas bajo /script-designer/ai/designs/{design_id}/data-files
"""
import csv
import io
import logging
import os
import uuid as uuid_pkg
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_role
from app.db.models.ai_design_data_file import AIDesignDataFile
from app.db.models.ai_script_design import AIScriptDesign
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.ai_design_data_file import (
    DataFileMappingUpdate,
    DataFilePreview,
    DataFileSummary,
)
from app.schemas.ai_script_structure import CSVDataSetModel, UserDefinedVariable
from app.services.engine.jmx_to_structure import parse_jmx_to_structure
from app.services.engine.structure_to_jmx import regenerate_jmx_from_structure

logger = logging.getLogger(__name__)


router = APIRouter()

UPLOAD_BASE = Path("/app/uploads/ai_data_files")
MAX_CSV_SIZE = 10 * 1024 * 1024  # 10 MB
PREVIEW_ROWS = 5


def _ensure_upload_dir(design_id: str) -> Path:
    p = UPLOAD_BASE / str(design_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _detect_delimiter(sample: str) -> str:
    """Detecta delimitador entre , ; \\t |"""
    candidates = [",", ";", "\t", "|"]
    counts = {d: sample.count(d) for d in candidates}
    return max(counts, key=counts.get) if max(counts.values()) > 0 else ","


async def _verify_design_access(
    design_id: str,
    user: User,
    db: AsyncSession,
) -> AIScriptDesign:
    """Verifica que el design exista y el usuario tenga acceso."""
    q = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    res = await db.execute(q)
    design = res.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Diseno no encontrado")
    if user.role != "admin" and design.user_id and design.user_id != user.id:
        raise HTTPException(status_code=403, detail="Sin acceso a este diseno")
    return design


@router.post(
    "/designs/{design_id}/data-files",
    response_model=DataFileSummary,
)
async def upload_data_file(
    design_id: str,
    file: UploadFile = File(...),
    delimiter: str = Form(","),
    has_header: str = Form("true"),
    encoding: str = Form("UTF-8"),
    variable_names: str = Form(
        "", description="Variables JMeter separadas por coma. Ej: 'firstname,lastname'"
    ),
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Sube un CSV y lo asocia al diseno.

    Sprint 2.5c.1 (HF2.1): si se declaran ``variable_names``, ademas de guardar
    el archivo se autocrea un CSV Data Set en la estructura del diseno apuntando
    a ``${Data}/<filename>`` (portable) y se asegura la UDV ``Data`` resoluble en
    runtime.
    """
    design = await _verify_design_access(design_id, current_user, db)

    contents = await file.read()
    if len(contents) > MAX_CSV_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo supera {MAX_CSV_SIZE // (1024 * 1024)} MB",
        )
    if len(contents) < 2:
        raise HTTPException(status_code=400, detail="Archivo vacio")

    try:
        text = contents.decode(encoding)
    except UnicodeDecodeError:
        try:
            text = contents.decode("latin-1")
            encoding = "latin-1"
        except Exception:
            raise HTTPException(
                status_code=400, detail="No se pudo decodificar el archivo"
            )

    if delimiter == "auto":
        sample = text[:2000]
        delimiter = _detect_delimiter(sample)

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="Archivo sin filas")

    if has_header.lower() == "true":
        columns = [c.strip() for c in rows[0]]
        row_count = len(rows) - 1
    else:
        columns = [f"col{i + 1}" for i in range(len(rows[0]))]
        row_count = len(rows)

    upload_dir = _ensure_upload_dir(design_id)
    stored_filename = f"{uuid_pkg.uuid4()}.csv"
    file_path = upload_dir / stored_filename
    with open(file_path, "wb") as f:
        f.write(contents)

    declared_vars = [v.strip() for v in variable_names.split(",") if v.strip()]

    record = AIDesignDataFile(
        design_id=design_id,
        user_id=current_user.id,
        original_filename=file.filename or "data.csv",
        stored_filename=stored_filename,
        file_path=str(file_path),
        file_size=len(contents),
        delimiter=delimiter,
        encoding=encoding,
        has_header=has_header,
        columns=columns,
        row_count=row_count,
        variable_mapping={},
        variable_names_declared=declared_vars,
    )
    db.add(record)

    # HF2.1 — si hay variables declaradas, autocrear el CSV Data Set en la
    # estructura del diseno (best-effort: no romper el upload si falla).
    if declared_vars:
        try:
            _autocreate_csv_dataset_in_structure(
                design=design,
                data_file=record,
                declared_vars=declared_vars,
                delimiter=delimiter,
                encoding=encoding,
                has_header=has_header.lower() == "true",
            )
        except Exception as e:  # noqa: BLE001 — best-effort, no abortar el upload
            logger.warning(
                "[data-files] no se pudo autocrear CSV Data Set para design=%s: %s",
                design_id, e,
            )

    await db.commit()
    await db.refresh(record)
    return record


def _autocreate_csv_dataset_in_structure(
    design: AIScriptDesign,
    data_file: AIDesignDataFile,
    declared_vars: List[str],
    delimiter: str,
    encoding: str,
    has_header: bool,
) -> None:
    """Autocrea un CSV Data Set en la estructura del diseno (HF2.1).

    1. Parsea el current_jmx del diseno.
    2. Si no existe UDV 'Data', la crea apuntando al directorio del design.
    3. Crea un CSVDataSet con filename=${Data}/<original_filename> (portable).
    4. Regenera el JMX y lo guarda en design.current_jmx.
    5. Vincula data_file.linked_csv_dataset_id al id del nuevo CSVDataSet.

    No persiste por si mismo (el caller hace commit). Si el diseno no tiene JMX
    todavia, no hace nada (no hay arbol donde inyectar).
    """
    if not design.current_jmx or len(design.current_jmx) < 50:
        return

    structure = parse_jmx_to_structure(design.current_jmx)

    # 1. Asegurar UDV 'Data' apuntando al folder del design en el container.
    if not any(u.name == "Data" for u in structure.user_defined_variables):
        container_data_path = f"/app/uploads/ai_data_files/{design.id}"
        structure.user_defined_variables.append(
            UserDefinedVariable(
                name="Data",
                value=container_data_path,
                metadata="=",
                is_dirty=True,
            )
        )

    # 2. Crear el CSVDataSet portable.
    new_csv = CSVDataSetModel(
        testname=f"Data {data_file.original_filename}",
        enabled=True,
        filename=f"${{Data}}/{data_file.original_filename}",
        file_encoding=encoding if encoding and encoding != "UTF-8" else None,
        variable_names=declared_vars,
        delimiter=delimiter,
        quoted_data=False,
        recycle=True,
        stop_thread=False,
        share_mode="shareMode.all",
        ignore_first_line=has_header,
        is_dirty=True,
    )
    structure.csv_data_sets.append(new_csv)

    # 3. Regenerar el JMX y persistir en el diseno.
    design.current_jmx = regenerate_jmx_from_structure(structure)

    # 4. Vincular el data file al CSV Data Set creado (trazabilidad).
    data_file.linked_csv_dataset_id = str(new_csv.id)


@router.get(
    "/designs/{design_id}/data-files",
    response_model=List[DataFileSummary],
)
async def list_data_files(
    design_id: str,
    current_user: User = Depends(require_role(["admin", "analyst", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """Lista los data files asociados al diseno."""
    await _verify_design_access(design_id, current_user, db)
    q = (
        select(AIDesignDataFile)
        .where(AIDesignDataFile.design_id == design_id)
        .order_by(AIDesignDataFile.created_at.desc())
    )
    res = await db.execute(q)
    return list(res.scalars().all())


@router.get(
    "/designs/{design_id}/data-files/{file_id}/preview",
    response_model=DataFilePreview,
)
async def preview_data_file(
    design_id: str,
    file_id: str,
    current_user: User = Depends(require_role(["admin", "analyst", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """Devuelve preview (primeras 5 filas) del archivo."""
    await _verify_design_access(design_id, current_user, db)
    q = select(AIDesignDataFile).where(
        AIDesignDataFile.id == file_id,
        AIDesignDataFile.design_id == design_id,
    )
    res = await db.execute(q)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    try:
        with open(record.file_path, "r", encoding=record.encoding) as f:
            reader = csv.reader(f, delimiter=record.delimiter)
            all_rows = list(reader)

        if record.has_header.lower() == "true":
            data_rows = all_rows[1 : PREVIEW_ROWS + 1]
        else:
            data_rows = all_rows[:PREVIEW_ROWS]

        return DataFilePreview(
            columns=record.columns,
            rows=data_rows,
            row_count_total=record.row_count,
            delimiter_detected=record.delimiter,
            encoding_detected=record.encoding,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=410, detail="Archivo fisico no encontrado en disco"
        )


@router.patch(
    "/designs/{design_id}/data-files/{file_id}",
    response_model=DataFileSummary,
)
async def update_data_file_mapping(
    design_id: str,
    file_id: str,
    payload: DataFileMappingUpdate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza el mapping de variables del data file."""
    await _verify_design_access(design_id, current_user, db)
    q = select(AIDesignDataFile).where(
        AIDesignDataFile.id == file_id,
        AIDesignDataFile.design_id == design_id,
    )
    res = await db.execute(q)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    record.variable_mapping = payload.variable_mapping
    await db.commit()
    await db.refresh(record)
    return record


@router.delete(
    "/designs/{design_id}/data-files/{file_id}",
    status_code=204,
)
async def delete_data_file(
    design_id: str,
    file_id: str,
    # SEC-2: borrar es exclusivo de admin en toda la plataforma.
    current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Elimina el data file (DB + archivo fisico)."""
    await _verify_design_access(design_id, current_user, db)
    q = select(AIDesignDataFile).where(
        AIDesignDataFile.id == file_id,
        AIDesignDataFile.design_id == design_id,
    )
    res = await db.execute(q)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    try:
        if os.path.exists(record.file_path):
            os.remove(record.file_path)
    except Exception:
        pass  # log silencioso, no fallar el delete por esto

    await db.delete(record)
    await db.commit()
    return None
