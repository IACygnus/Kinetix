from fastapi import APIRouter

from app.api.v1.endpoints import upload
from app.api.v1.endpoints import export_html
from app.api.v1.endpoints import export_pdf

api_router = APIRouter()

# IMPORTANTE: El endpoint upload.router ya tiene @router.post("/upload")
# Por eso NO lleva prefix aquí, o quedaría /upload/upload
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(export_html.router, tags=["export"])
api_router.include_router(export_pdf.router, tags=["export"])