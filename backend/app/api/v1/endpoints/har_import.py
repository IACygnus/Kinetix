# backend/app/api/v1/endpoints/har_import.py
"""
Endpoint para importar archivos HAR al Script Designer.
El HAR se convierte al Script Model interno y se retorna para previsualizacion
antes de que el usuario decida guardar.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.engine.har_importer import HARImporter

router = APIRouter()


class HARImportResponse(BaseModel):
    script_model: dict
    stats: dict


@router.post("/preview", response_model=HARImportResponse)
async def preview_har(
    file: UploadFile = File(..., description="Archivo .har exportado desde Chrome/Firefox DevTools"),
    base_url_filter: Optional[str] = Form(None, description="Filtrar solo requests a esta URL base"),
    current_user=Depends(get_current_user)
):
    """
    Parsear un archivo HAR y retornar el Script Model resultante para previsualizacion.
    No guarda nada en DB — el usuario decide si guardar el script despues.
    """
    if not file.filename or not file.filename.endswith(".har"):
        raise HTTPException(status_code=400, detail="El archivo debe tener extension .har")

    content = await file.read()

    # Verificar tamano (maximo 50MB)
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo HAR supera el limite de 50MB")

    try:
        har_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="El archivo HAR debe estar en UTF-8")

    importer = HARImporter()
    try:
        script_model, stats = importer.import_har(har_text, base_url_filter=base_url_filter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if stats["imported"] == 0:
        raise HTTPException(
            status_code=422,
            detail=f"No se importaron requests. {stats['total_entries']} entradas analizadas, "
                   f"{stats['filtered_static']} filtradas como estaticas, "
                   f"{stats['filtered_tracker']} como trackers."
        )

    return HARImportResponse(script_model=script_model, stats=stats)
