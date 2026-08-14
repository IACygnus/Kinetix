"""
Endpoints CRUD for execution attachments (monitoring images, evidence screenshots).
KNX-13 (monitoring) and KNX-14 (evidence).
"""
import os
import uuid
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.db.models.attachment import ExecutionAttachment

router = APIRouter()

MEDIA_ROOT = Path("/app/media/attachments")
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
ALLOWED_FILE_TYPES = ALLOWED_IMAGE_TYPES | {"text/csv", "application/vnd.ms-excel"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/{execution_id}/attachments")
async def upload_attachment(
    execution_id: uuid.UUID,
    file: UploadFile = File(...),
    attachment_type: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    sort_order: int = Form(0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload an attachment (image or CSV) for an execution."""
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            400,
            f"Tipo de archivo no permitido: {file.content_type}. "
            f"Permitidos: PNG, JPG, GIF, WebP, CSV",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"Archivo excede el limite de {MAX_FILE_SIZE // (1024 * 1024)}MB")

    exec_dir = MEDIA_ROOT / str(execution_id)
    exec_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix if file.filename else ""
    unique_name = f"{uuid.uuid4()}{ext}"
    filepath = exec_dir / unique_name

    with open(filepath, "wb") as f:
        f.write(content)

    attachment = ExecutionAttachment(
        execution_id=execution_id,
        attachment_type=attachment_type,
        title=title or file.filename,
        description=description,
        category=category,
        filename=file.filename or unique_name,
        filepath=f"/media/attachments/{execution_id}/{unique_name}",
        file_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        sort_order=sort_order,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "filepath": attachment.filepath,
        "attachment_type": attachment.attachment_type,
        "title": attachment.title,
        "category": attachment.category,
    }


@router.get("/{execution_id}/attachments")
async def list_attachments(
    execution_id: uuid.UUID,
    attachment_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List attachments for an execution, optionally filtered by type."""
    query = (
        select(ExecutionAttachment)
        .where(ExecutionAttachment.execution_id == execution_id)
        .order_by(ExecutionAttachment.sort_order, ExecutionAttachment.created_at)
    )
    if attachment_type:
        query = query.where(ExecutionAttachment.attachment_type == attachment_type)

    result = await db.execute(query)
    attachments = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "attachment_type": a.attachment_type,
            "title": a.title,
            "description": a.description,
            "category": a.category,
            "filename": a.filename,
            "filepath": a.filepath,
            "file_type": a.file_type,
            "file_size": a.file_size,
            "sort_order": a.sort_order,
        }
        for a in attachments
    ]


@router.put("/{execution_id}/attachments/{attachment_id}")
async def update_attachment(
    execution_id: uuid.UUID,
    attachment_id: uuid.UUID,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    sort_order: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update title, description, or category of an attachment."""
    result = await db.execute(
        select(ExecutionAttachment).where(
            ExecutionAttachment.id == attachment_id,
            ExecutionAttachment.execution_id == execution_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(404, "Adjunto no encontrado")

    if title is not None:
        attachment.title = title
    if description is not None:
        attachment.description = description
    if category is not None:
        attachment.category = category
    if sort_order is not None:
        attachment.sort_order = sort_order

    attachment.updated_at = datetime.utcnow()
    await db.commit()
    return {"status": "ok"}


@router.delete("/{execution_id}/attachments/{attachment_id}")
async def delete_attachment(
    execution_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    # SEC-2: borrar es exclusivo de admin en toda la plataforma.
    current_user=Depends(require_role(["admin"])),
):
    """Delete an attachment (file + DB record)."""
    result = await db.execute(
        select(ExecutionAttachment).where(
            ExecutionAttachment.id == attachment_id,
            ExecutionAttachment.execution_id == execution_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(404, "Adjunto no encontrado")

    # Delete physical file
    abs_path = Path("/app") / attachment.filepath.lstrip("/")
    if abs_path.exists():
        abs_path.unlink()

    await db.execute(
        delete(ExecutionAttachment).where(ExecutionAttachment.id == attachment_id)
    )
    await db.commit()
    return {"status": "deleted"}
