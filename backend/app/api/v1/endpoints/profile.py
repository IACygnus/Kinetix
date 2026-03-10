"""
Endpoints de Perfil propio - Todos los usuarios autenticados - v2.0
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.db.session import get_db
from app.db.models.user import User
from app.core.security import get_current_active_user, verify_password, get_password_hash
from app.schemas.user import UserResponse, ProfileUpdate, PasswordChange

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Obtener mi perfil"""
    return current_user


@router.put("", response_model=UserResponse)
async def update_my_profile(
    data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Editar mi perfil (nombre y email solamente)"""
    # Verificar email unico si cambia
    if data.email is not None and data.email != current_user.email:
        existing = await db.execute(
            select(User).where(User.email == data.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="El email ya esta registrado")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(current_user, field, value)

    await db.flush()
    await db.refresh(current_user)

    logger.info(f"Perfil actualizado: {current_user.username}")
    return current_user


@router.put("/password")
async def change_my_password(
    data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cambiar mi contrasena (requiere contrasena actual)"""
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="La contrasena actual es incorrecta")

    current_user.hashed_password = get_password_hash(data.new_password)
    await db.flush()

    logger.info(f"Contrasena cambiada: {current_user.username}")
    return {"success": True, "message": "Contrasena actualizada correctamente"}
