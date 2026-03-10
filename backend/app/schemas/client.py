"""
Schemas Pydantic para Clientes - v2.2
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ClientCreate(BaseModel):
    name: str
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[bool] = None


class ClientResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserClientAssign(BaseModel):
    user_id: UUID
    client_id: UUID


class UserClientResponse(BaseModel):
    id: UUID
    user_id: UUID
    client_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserWithClients(BaseModel):
    id: UUID
    username: str
    full_name: str
    role: str
    is_active: bool
    clients: List[ClientResponse] = []

    model_config = ConfigDict(from_attributes=True)
