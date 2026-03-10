"""
Endpoints de autenticacion - DB-backed con roles - v2.0
HTTPOnly cookies + rate limiting + CSRF + logout
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from datetime import timedelta
from typing import Dict, List
import time
import threading
import logging

from app.core.config import settings
from app.core.security import (
    verify_password,
    create_access_token,
    generate_csrf_token,
    get_current_active_user,
)
from app.db.session import get_db
from app.db.models.user import User
from app.schemas.auth import LoginUserResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------- Rate limiter (in-memory) ----------
_login_attempts: Dict[str, List[float]] = {}
_lock = threading.Lock()
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900  # 15 minutes


def _check_rate_limit(ip: str) -> bool:
    """Return True if the IP has remaining attempts"""
    now = time.time()
    with _lock:
        attempts = _login_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < WINDOW_SECONDS]
        _login_attempts[ip] = attempts
        return len(attempts) < MAX_ATTEMPTS


def _record_attempt(ip: str):
    with _lock:
        _login_attempts.setdefault(ip, []).append(time.time())


# ---------- Endpoints ----------

@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login con usuario de base de datos — sets httpOnly cookie"""
    ip = request.client.host if request.client else "unknown"

    # Rate limiting
    if not _check_rate_limit(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de login. Intenta en 15 minutos.",
        )

    # Buscar por username o email
    result = await db.execute(
        select(User).where(
            or_(
                User.username == form_data.username,
                User.email == form_data.username,
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        _record_attempt(ip)
        logger.warning(f"Intento de login fallido para: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado. Contacte al administrador.",
        )

    _record_attempt(ip)

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    csrf_token = generate_csrf_token()

    logger.info(f"Login exitoso: {user.username} (role: {user.role})")

    response = JSONResponse(content={
        "message": "Login exitoso",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
        },
    })

    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Frontend needs to read this
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=max_age,
        path="/",
    )

    return response


@router.post("/refresh")
async def refresh_token(
    current_user: User = Depends(get_current_active_user),
):
    """Renueva el token JWT si el usuario sigue activo (sliding session)"""
    access_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "username": current_user.username,
            "role": current_user.role,
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    csrf_token = generate_csrf_token()

    response = JSONResponse(content={"message": "Token renovado"})

    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=max_age,
        path="/",
    )

    return response


@router.post("/logout")
async def logout():
    """Logout — clear auth cookies"""
    response = JSONResponse(content={"message": "Logout exitoso"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    return response


@router.get("/me", response_model=LoginUserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """Obtener informacion del usuario actual"""
    return current_user
