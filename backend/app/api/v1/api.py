# api.py (DESPUÉS - CORREGIDO)
from fastapi import APIRouter

from app.api.v1.endpoints import upload
from app.api.v1.endpoints import export_html
from app.api.v1.endpoints import export_pdf
from app.api.v1.endpoints import auth  # ✅ AGREGADO

api_router = APIRouter()

# Autenticación
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])  # ✅ AGREGADO

# Resto de routers (sin cambios)
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(export_html.router, tags=["export"])
api_router.include_router(export_pdf.router, tags=["export"])