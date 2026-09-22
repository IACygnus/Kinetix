"""
Router API centralizado - v2.0
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth
# OBSERVABILIDAD (ETAPA O2c): los servidores que se miran durante una prueba.
from app.api.v1.endpoints import observabilidad
# MODULO DE HORAS (ETAPA H1, H-D9): router propio bajo /time, separado del
# modulo de analisis.
from app.api.v1.endpoints import time_activities
from app.api.v1.endpoints import time_consulta
from app.api.v1.endpoints import time_entries
from app.api.v1.endpoints import time_import
from app.api.v1.endpoints import time_informe
from app.api.v1.endpoints import time_projects
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
from app.api.v1.endpoints.script_ai import router as script_ai_router
from app.api.v1.endpoints import ai_design_data_files

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

# AI Script Designer — JMX generation via OpenAI/Gemini (conversational)
api_router.include_router(script_ai_router, prefix="/script-designer/ai", tags=["Script Designer AI"])

# Sprint 2.4-HF2 — Data Files asociados a disenos AI
api_router.include_router(
    ai_design_data_files.router,
    prefix="/script-designer/ai",
    tags=["AI Design Data Files"],
)

# ===================== MODULO DE HORAS (ETAPA H1) =====================
# H-D9: todo el modulo cuelga de /time, para que se distinga de un vistazo de
# los routers del modulo de analisis y del motor.
api_router.include_router(time_activities.router, prefix="/time/activities", tags=["Horas — Actividades"])
api_router.include_router(time_projects.router, prefix="/time/projects", tags=["Horas — Proyectos"])
api_router.include_router(time_consulta.router, prefix="/time/consulta", tags=["Horas — Consulta"])
api_router.include_router(time_import.router, prefix="/time/import", tags=["Horas — Importación"])
api_router.include_router(time_informe.router, prefix="/time/informe", tags=["Horas — Informe"])
# ETAPA H2: el registro cuelga de /time directamente porque sus rutas son
# varias (/entries, /week, /pending-days, /projects/{id}/disponibilidad).
api_router.include_router(time_entries.router, prefix="/time", tags=["Horas — Registro"])

# ===================== OBSERVABILIDAD (ETAPA O2c) =====================
# Los servidores que se miran durante una prueba: alta, prueba de conexion y
# generador de configuracion. Cuelga de /observabilidad por el mismo motivo que
# el modulo de horas cuelga de /time: que se distinga de un vistazo.
api_router.include_router(
    observabilidad.router, prefix="/observabilidad", tags=["Observabilidad — Servidores"])
