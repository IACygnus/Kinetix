# backend/app/api/v1/endpoints/scripts.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.db.models.script_design import ScriptDesign

router = APIRouter()


class ScriptCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    client_id: Optional[str] = None  # UUID as string
    client_name: Optional[str] = None
    script_model: dict = {}
    script_type: Optional[str] = "api"
    origin: str = "manual"


class ScriptUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    script_model: Optional[dict] = None
    script_type: Optional[str] = None
    client_name: Optional[str] = None


class ScriptResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    client_id: Optional[UUID]
    client_name: Optional[str]
    user_id: UUID
    script_model: dict
    script_type: Optional[str]
    origin: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/")
async def list_scripts(
    search: Optional[str] = None,
    client_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Listar todos los scripts del usuario actual con filtros opcionales."""
    query = select(ScriptDesign).where(ScriptDesign.user_id == current_user.id)

    if search:
        query = query.where(ScriptDesign.name.ilike(f"%{search}%"))
    if client_id:
        import uuid as uuid_mod
        try:
            cid = uuid_mod.UUID(client_id)
            query = query.where(ScriptDesign.client_id == cid)
        except ValueError:
            pass

    query = query.order_by(ScriptDesign.updated_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    scripts = result.scalars().all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "client_id": str(s.client_id) if s.client_id else None,
            "client_name": s.client_name,
            "user_id": str(s.user_id),
            "script_model": s.script_model,
            "script_type": getattr(s, 'script_type', None) or 'api',
            "origin": s.origin,
            "request_count": len((s.script_model or {}).get("requests", [])),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in scripts
    ]


@router.post("/", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    payload: ScriptCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Crear un nuevo script de diseno."""
    import uuid as uuid_mod
    client_id = None
    if payload.client_id:
        try:
            client_id = uuid_mod.UUID(payload.client_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="client_id invalido")

    script = ScriptDesign(
        name=payload.name,
        description=payload.description,
        client_id=client_id,
        client_name=payload.client_name,
        user_id=current_user.id,
        script_model=payload.script_model,
        script_type=payload.script_type or "api",
        origin=payload.origin,
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return script


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(ScriptDesign).where(ScriptDesign.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script no encontrado")
    return script


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: int,
    payload: ScriptUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(ScriptDesign).where(ScriptDesign.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script no encontrado")

    if payload.name is not None:
        script.name = payload.name
    if payload.description is not None:
        script.description = payload.description
    if payload.script_model is not None:
        script.script_model = payload.script_model
    if payload.script_type is not None:
        script.script_type = payload.script_type
    if payload.client_name is not None:
        script.client_name = payload.client_name
    script.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(script)
    return script


@router.delete("/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    # SEC-2: borrar es exclusivo de admin en toda la plataforma.
    current_user=Depends(require_role(["admin"])),
):
    result = await db.execute(select(ScriptDesign).where(ScriptDesign.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script no encontrado")
    await db.delete(script)
    await db.commit()


@router.post("/{script_id}/export-jmx")
async def export_jmx(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Exportar el script al formato .jmx de JMeter.
    Solo exportacion — el motor propio no usa JMX para ejecutar.
    """
    from fastapi.responses import Response
    from app.services.engine.jmx_exporter import JMXExporter

    result = await db.execute(select(ScriptDesign).where(ScriptDesign.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script no encontrado")

    exporter = JMXExporter()
    jmx_content = exporter.export(script.script_model, script_name=script.name)

    filename = f"{script.name.replace(' ', '_')}_{script_id}.jmx"
    return Response(
        content=jmx_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
