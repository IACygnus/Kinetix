"""
Schemas de autenticacion - v2.0
"""
from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None


class LoginUserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
