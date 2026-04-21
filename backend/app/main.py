"""
SQA Kinetix Pro - Aplicacion Principal v2.0
"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
import logging
import uuid

from app.core.config import settings
from app.db.base_class import Base
from app.db.session import engine, AsyncSessionLocal
from app.db.models.user import User
from app.db.models.test import TestExecution
from app.db.models.client import Client, UserClient
from app.db.models.monitoring import MonitoringConfig
from app.db.models.ai_config import AIConfig
from app.db.models.script_design import ScriptDesign
from app.db.models.scenario import Scenario
from app.db.models.performance_execution import PerformanceExecution
from app.db.models.data_file import DataFile
from app.db.models.attachment import ExecutionAttachment
from app.core.security import get_password_hash

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear app
app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema de analisis de reportes JMeter con IA - v2.0",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS — both dev and prod use specific origins with credentials (required for cookies)
if settings.ENVIRONMENT == "production" and settings.CORS_ORIGINS:
    _origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
else:
    _origins = [o.strip() for o in settings.CORS_ORIGINS_DEV.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-CSRF-Token"],
)

# CSRF middleware — validate double-submit cookie on mutating requests
@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        # Skip CSRF for login (no cookie yet) and OpenAPI docs
        if request.url.path.endswith("/auth/login") or request.url.path in ("/docs", "/redoc", "/openapi.json"):
            return await call_next(request)
        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("x-csrf-token")
        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
    return await call_next(request)


# Importar API router centralizado
from app.api.v1.api import api_router

# Incluir API router
app.include_router(api_router, prefix="/api/v1")

# WebSocket router (Sprint 3 — incluido directamente en app para handshake correcto)
from app.api.v1.endpoints import ws_metrics
app.include_router(ws_metrics.router, prefix="/api/v1/ws", tags=["WebSocket"])

# Mount media directory for serving attachment files (KNX-13, KNX-14)
MEDIA_ROOT = "/app/media"
os.makedirs(os.path.join(MEDIA_ROOT, "attachments"), exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")


async def create_tables():
    """Crear tablas en la base de datos"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tablas de base de datos verificadas/creadas")


async def migrate_users_table():
    """Migrar tabla users: agregar columnas faltantes de v2.0"""
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(50)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'viewer'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by UUID",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                logger.info(f"Migration OK: {sql}")
            except Exception as e:
                logger.warning(f"Migration skip: {e}")

        # Crear indice unico en username si no existe
        try:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"
            ))
            logger.info("Index ix_users_username OK")
        except Exception as e:
            logger.warning(f"Index skip: {e}")

        # Poblar username para filas existentes que lo tengan NULL
        try:
            await conn.execute(text(
                "UPDATE users SET username = split_part(email, '@', 1) WHERE username IS NULL"
            ))
            logger.info("Backfill username from email OK")
        except Exception as e:
            logger.warning(f"Backfill skip: {e}")

        # Hacer username NOT NULL despues de backfill
        try:
            await conn.execute(text(
                "ALTER TABLE users ALTER COLUMN username SET NOT NULL"
            ))
            logger.info("username SET NOT NULL OK")
        except Exception as e:
            logger.warning(f"NOT NULL skip: {e}")

    logger.info("Migracion de tabla users completada")


async def migrate_test_executions_table():
    """Migrar tabla test_executions: agregar columnas faltantes de v2.0"""
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS client VARCHAR(255)",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS project VARCHAR(255)",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS test_type VARCHAR(50) DEFAULT 'load'",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS jtl_filenames JSON",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS acceptance_criteria_json JSON",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS total_redirects INTEGER DEFAULT 0",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS redirect_labels JSON",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS ai_analysis_redirects TEXT",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS capacity_analysis_json TEXT",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception as e:
                logger.warning(f"Migration skip: {e}")
    logger.info("Migracion de tabla test_executions completada")


async def migrate_ai_config_table():
    """Migrar tabla ai_config: agregar columnas de limites diarios/mensuales"""
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            "ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS daily_request_limit INTEGER DEFAULT 1000",
            "ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS monthly_request_limit INTEGER DEFAULT 20000",
            "ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS daily_requests_used INTEGER DEFAULT 0",
            "ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS monthly_requests_used INTEGER DEFAULT 0",
            "ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS last_reset_daily DATE DEFAULT CURRENT_DATE",
            "ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS last_reset_monthly DATE DEFAULT CURRENT_DATE",
            "ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception as e:
                logger.warning(f"AI config migration skip: {e}")
    logger.info("Migracion de tabla ai_config completada")


async def migrate_clients_tables():
    """Migrar: agregar client_id FK a test_executions + campos extra en clients"""
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS client_id UUID REFERENCES clients(id)",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS description VARCHAR(500)",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS contact_name VARCHAR(200)",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS contact_email VARCHAR(200)",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                logger.info(f"Migration OK: {sql}")
            except Exception as e:
                logger.warning(f"Migration skip: {e}")
    logger.info("Migracion de tablas de clientes completada")


async def seed_admin_user():
    """Crear usuario admin por defecto si no existe"""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            existing_admin = result.scalar_one_or_none()

            if existing_admin is None:
                admin_user = User(
                    id=uuid.uuid4(),
                    username="admin",
                    email="admin@sqa.local",
                    full_name="Administrador SQA",
                    hashed_password=get_password_hash(settings.ADMIN_DEFAULT_PASSWORD),
                    role="admin",
                    is_active=True,
                )
                session.add(admin_user)
                await session.commit()
                logger.info("Usuario admin creado exitosamente")
            else:
                logger.info("Usuario admin ya existe, omitiendo seed")
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creando usuario admin: {e}")


async def migrate_script_designs_table():
    """Sprint 6 — agregar script_type y client_name a script_designs"""
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE script_designs ADD COLUMN IF NOT EXISTS script_type VARCHAR(20) DEFAULT 'api'",
            "ALTER TABLE script_designs ADD COLUMN IF NOT EXISTS client_name VARCHAR(255)",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                logger.info(f"Migration OK: {sql}")
            except Exception as e:
                logger.warning(f"Migration skip: {e}")
    logger.info("Migracion de tabla script_designs completada")


async def migrate_attachments_table():
    """Sprint P1-A — agregar ai_analysis a execution_attachments"""
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE execution_attachments ADD COLUMN IF NOT EXISTS ai_analysis TEXT",
            "ALTER TABLE execution_attachments ADD COLUMN IF NOT EXISTS ai_analysis_updated_at TIMESTAMP",
            "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS metric_unit VARCHAR(10) DEFAULT 'TPS'",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                logger.info(f"Migration OK: {sql}")
            except Exception as e:
                logger.warning(f"Migration skip: {e}")
    logger.info("Migracion de tabla execution_attachments completada")


@app.on_event("startup")
async def startup_event():
    """Inicializacion al arrancar la aplicacion"""
    logger.info(f"Iniciando {settings.APP_NAME} v2.0")
    await create_tables()
    await migrate_users_table()
    await migrate_test_executions_table()
    await migrate_clients_tables()
    await migrate_ai_config_table()
    await migrate_script_designs_table()
    await migrate_attachments_table()
    await seed_admin_user()
    logger.info("Aplicacion lista")


# Endpoints basicos
@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "app": settings.APP_NAME,
        "version": "3.0.0",
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
