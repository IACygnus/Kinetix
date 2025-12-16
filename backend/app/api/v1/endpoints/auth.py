"""
Endpoints de autenticación
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta

from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import Token, UserResponse

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login con usuario hardcodeado"""
    # Usuario demo
    if form_data.username == "admin@jmeter.com" and form_data.password == "admin123":
        access_token = create_access_token(
            data={"sub": form_data.username},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": access_token, "token_type": "bearer"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales incorrectas",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Obtener usuario actual"""
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "admin@jmeter.com",
        "full_name": "Administrator"
    }
