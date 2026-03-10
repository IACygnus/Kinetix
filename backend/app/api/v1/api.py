"""
Router API centralizado - v2.0
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth
from app.api.v1.endpoints import upload
from app.api.v1.endpoints import export_html
from app.api.v1.endpoints import export_pdf
from app.api.v1.endpoints import users
from app.api.v1.endpoints import profile
from app.api.v1.endpoints import dashboard
from app.api.v1.endpoints import monitoring
from app.api.v1.endpoints import clients
from app.api.v1.endpoints import ai_config

api_router = APIRouter()

# Autenticacion
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Dashboard
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# Performance (upload, executions, charts, exports)
api_router.include_router(upload.router, tags=["performance"])
api_router.include_router(export_html.router, tags=["export"])
api_router.include_router(export_pdf.router, tags=["export"])

# Usuarios
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Perfil
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])

# Clientes
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])

# Monitoreo (Grafana + InfluxDB)
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])

# Configuracion de IA (Phase 7)
api_router.include_router(ai_config.router, prefix="/ai-config", tags=["ai-config"])
