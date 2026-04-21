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
from app.api.v1.endpoints import scripts
from app.api.v1.endpoints import scenarios
from app.api.v1.endpoints import performance_executions
from app.api.v1.endpoints import har_import
from app.api.v1.endpoints import data_files
from app.api.v1.endpoints import executions
from app.api.v1.endpoints import import_script
from app.api.v1.endpoints import script_variables
from app.api.v1.endpoints import attachments
from app.api.v1.endpoints import compare
from app.api.v1.endpoints import analysis_ai
from app.api.v1.endpoints import integrated_report

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

# Motor de Performance Testing (Sprint 0)
api_router.include_router(scripts.router, prefix="/scripts", tags=["Script Designer"])
api_router.include_router(scenarios.router, prefix="/scenarios", tags=["Scenarios"])
api_router.include_router(performance_executions.router, prefix="/performance-executions", tags=["Performance Executions"])

# Sprint 1 — Script Designer
api_router.include_router(har_import.router, prefix="/har-import", tags=["HAR Import"])
api_router.include_router(data_files.router, prefix="/data-files", tags=["Data Files"])

# Sprint 2 — Motor de ejecución
api_router.include_router(executions.router, prefix="/executions", tags=["Executions"])

# Sprint 5 — Unified Importers (Postman, OpenAPI, WSDL, Chrome)
api_router.include_router(import_script.router, prefix="/import", tags=["Import"])

# Sprint 7 — Variable Manager
api_router.include_router(script_variables.router, prefix="/scripts", tags=["Script Variables"])

# Sprint S3 — Attachments (monitoring images, evidence screenshots)
api_router.include_router(attachments.router, prefix="/executions", tags=["Attachments"])

# Sprint S3-B — Comparison reports (KNX-12)
api_router.include_router(compare.router, prefix="/reports", tags=["Reports"])

# Sprint R3-A — AI analysis for monitoring and evidence pages
api_router.include_router(analysis_ai.router, prefix="/executions", tags=["AI Analysis"])

# Sprint R3-B — Integrated report with drag-and-drop
api_router.include_router(integrated_report.router, prefix="/reports", tags=["Reports"])
