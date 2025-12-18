"""
JMeter Analyzer Pro - Aplicación Principal
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings, CORS_ORIGINS

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear app
app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema de análisis de reportes JMeter con IA",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Importar API router centralizado
from app.api.v1.api import api_router

# Incluir API router
app.include_router(api_router, prefix="/api/v1")

# Endpoints básicos
@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check para Docker"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME
    }

@app.get("/api/test")
async def test_endpoint():
    """Endpoint de prueba"""
    return {
        "message": "Backend funcionando correctamente",
        "port": settings.BACKEND_PORT,
        "gemini_configured": bool(settings.GEMINI_API_KEY)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )