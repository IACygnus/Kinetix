"""
Schemas de configuracion de IA
"""
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date


class AIProviderInfo(BaseModel):
    """Info about a supported AI provider"""
    id: str
    name: str
    models: List[str]


class AIConfigRead(BaseModel):
    """Response schema - API key never exposed, only masked"""
    id: UUID
    provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"
    api_key_masked: str = ""
    is_active: bool = True
    daily_request_limit: int = 1000
    monthly_request_limit: int = 20000
    daily_requests_used: int = 0
    monthly_requests_used: int = 0
    last_reset_daily: Optional[date] = None
    last_reset_monthly: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AIConfigCreate(BaseModel):
    """Create/update schema"""
    provider: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    daily_request_limit: Optional[int] = None
    monthly_request_limit: Optional[int] = None


class AITestResult(BaseModel):
    """Connection test result"""
    status: str  # "ok", "error"
    message: str
    provider: str
    model: str


class LiveModelsResponse(BaseModel):
    """Response from /models/live endpoint"""
    provider: str
    models: List[str]
    is_live: bool
    message: Optional[str] = None
