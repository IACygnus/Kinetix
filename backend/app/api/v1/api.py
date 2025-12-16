from fastapi import APIRouter

# Importar TODOS los routers
from app.api.v1.endpoints import upload
from app.api.v1.endpoints import executions
from app.api.v1.endpoints import export_html
from app.api.v1.endpoints import export_pdf  # ← LÍNEA NUEVA

api_router = APIRouter()

# Incluir TODOS los routers
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(executions.router, prefix="/executions", tags=["executions"])
api_router.include_router(export_html.router, tags=["export"])
api_router.include_router(export_pdf.router, tags=["export"])  # ← LÍNEA NUEVA
