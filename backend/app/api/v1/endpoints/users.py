"""
Endpoints CRUD de Usuarios - Admin only - v2.0
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import uuid
import logging

from app.db.session import get_db
from app.db.models.user import User
from app.core.security import get_password_hash, require_role
from app.schemas.user import UserCreate, UserUpdate, UserResponse, PasswordReset

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_ROLES = {"admin", "analyst", "viewer"}


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Crear nuevo usuario - Solo admin"""
    # Validar rol
    if user_data.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Rol invalido. Opciones: {', '.join(VALID_ROLES)}"
        )

    # Verificar username unico
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="El username ya existe")

    # Verificar email unico
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="El email ya esta registrado")

    new_user = User(
        id=uuid.uuid4(),
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        is_active=user_data.is_active,
        created_by=current_user.id,
    )

    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    logger.info(f"Usuario creado: {new_user.username} (role: {new_user.role}) por {current_user.username}")
    return new_user


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Listar todos los usuarios - Solo admin"""
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Obtener detalle de usuario - Solo admin"""
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID de usuario invalido")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Editar usuario - Solo admin"""
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID de usuario invalido")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar rol si se esta actualizando
    if user_data.role is not None and user_data.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Rol invalido. Opciones: {', '.join(VALID_ROLES)}"
        )

    # Verificar username unico si cambia
    if user_data.username is not None and user_data.username != user.username:
        existing = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="El username ya existe")

    # Verificar email unico si cambia
    if user_data.email is not None and user_data.email != user.email:
        existing = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="El email ya esta registrado")

    # Aplicar cambios
    update_fields = user_data.model_dump(exclude_unset=True)
    if "password" in update_fields:
        password = update_fields.pop("password")
        if password:
            user.hashed_password = get_password_hash(password)

    for field, value in update_fields.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)

    logger.info(f"Usuario actualizado: {user.username} por {current_user.username}")
    return user


@router.patch("/{user_id}/toggle", response_model=UserResponse)
async def toggle_user_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Activar/Desactivar usuario - Solo admin"""
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID de usuario invalido")

    # No permitir desactivarse a si mismo
    if uid == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = not user.is_active
    await db.flush()
    await db.refresh(user)

    status_text = "activado" if user.is_active else "desactivado"
    logger.info(f"Usuario {status_text}: {user.username} por {current_user.username}")
    return user


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    data: PasswordReset,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Reset de contrasena - Solo admin"""
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID de usuario invalido")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.hashed_password = get_password_hash(data.new_password)
    await db.flush()

    logger.info(f"Password reseteado para: {user.username} por {current_user.username}")
    return {"success": True, "message": f"Contrasena de {user.username} reseteada correctamente"}
