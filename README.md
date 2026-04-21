# SQA Kinetix Pro

**Plataforma interna de análisis automatizado de pruebas de performance con IA**

![Version](https://img.shields.io/badge/version-3.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![React](https://img.shields.io/badge/react-18-61dafb)
![License](https://img.shields.io/badge/license-Internal-red)

Desarrollado por el COE de Performance Testing de **SQA Colombia** (sqasa.co).

---

## Descripción

SQA Kinetix Pro es una plataforma web que automatiza el análisis de pruebas de carga JMeter mediante procesamiento de archivos JTL e inteligencia artificial (Google Gemini + OpenAI). Además incluye un diseñador de scripts propio, motor de ejecución independiente de JMeter, informes integrados con drag-and-drop, y exportación a HTML interactivo y PDF.

---

## Features

### Análisis
- Parsing de archivos JTL/CSV de JMeter (hasta millones de samples)
- 8+ gráficas de performance (response times, throughput, latencia, errores, códigos, TPS, threads activos)
- Análisis IA por gráfica con síntesis inteligente y recomendaciones priorizadas
- Análisis de imágenes con OCR + Vision API (Gemini Vision + OpenAI Vision)

### IA
- **Google Gemini 2.5-flash** (proveedor primario)
- **OpenAI GPT-4o** (proveedor alternativo con Vision API)
- Endpoint dinámico `/models/live` con cache 5min
- Configuración por usuario admin con selector de proveedor

### Script Designer
- Diseñador visual de scripts de performance (18 componentes React)
- Import desde HAR, Postman, OpenAPI, WSDL, Chrome Extension
- Motor de ejecución propio (httpx + asyncio, **sin dependencia de JMeter**)
- Variables dinámicas, data files, correlación asistida por IA
- Smoke test + Load test (SteppingController)

### Reportes
- Exportación HTML standalone (Plotly.js interactivo)
- Exportación HTML integrado (drag-and-drop de secciones)
- Exportación PDF (WeasyPrint) con cover full-bleed
- Reportes comparativos entre ejecuciones
- Persistencia en DB de informes integrados

### Monitoreo
- Integración Grafana + InfluxDB en tiempo real
- WebSocket de métricas live durante ejecución
- Attachments de monitoreo (evidencias de infraestructura)

### Seguridad
- JWT con httpOnly cookies + CSRF
- bcrypt para passwords
- Fernet encryption para API keys y monitoring tokens
- Role-based access (admin/user)

---

## Stack Técnico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI 0.104 + Python 3.11 |
| Frontend | React 18 + TypeScript + Vite |
| Base de datos | PostgreSQL 15 |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| IA | google-generativeai + openai |
| PDF | WeasyPrint 61.2 + matplotlib |
| Monitoreo | Grafana 10.2 + InfluxDB 2.7 |
| Containerización | Docker Compose |
| Reverse Proxy | Nginx (producción) |

---

## Quick Start (Desarrollo)

### Prerrequisitos
- Docker Desktop
- Git
- 8 GB RAM mínimo

### Instalación

```bash
# 1. Clonar
git clone https://PlataformasSQA@dev.azure.com/PlataformasSQA/COE/_git/COE
cd COE

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales (Gemini API key, OpenAI API key, etc.)

# 3. Levantar servicios
docker compose up -d

# 4. Verificar que todos los contenedores estén corriendo
docker compose ps
```

### Acceso

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8001
- **Swagger**: http://localhost:8001/docs
- **Grafana**: http://localhost:3000
- **Credenciales dev**: `admin / sqa2024`

---

## Estructura del Proyecto

```
COE/
├── backend/          FastAPI + SQLAlchemy + servicios IA/export
├── frontend/         React + TypeScript + Vite
├── docker-compose.yml              (desarrollo)
├── docker-compose.prod.yml         (producción)
├── CHANGELOG.md
├── README.md
└── INFORME_PROYECTO_KINETIX.md     (handoff técnico completo, local)
```

Detalle completo de arquitectura en `DOCUMENTACION_TECNICA.md`.

---

## Documentación

| Documento | Propósito |
|---|---|
| `README.md` | Este archivo |
| `CHANGELOG.md` | Historial de versiones |
| `DOCUMENTACION_TECNICA.md` | Arquitectura y diseño detallado |
| `GUIA_INICIO.md` | Onboarding para nuevos desarrolladores |
| `RESUMEN_EJECUTIVO.md` | Overview para stakeholders |
| `TROUBLESHOOTING.md` | Problemas comunes y soluciones |
| `GRAFANA_SETUP.md` | Configuración de monitoreo |
| `DEPLOY.md` | Despliegue a producción _(pendiente v3.1.0)_ |

---

## Producción

Target de producción: **kinetix.sqasa.co** (Azure VM con Nginx + HTTPS).

Documentación de deploy pendiente para v3.1.0 (ver `DEPLOY.md`).

---

## Versión

**v3.0.0** — Abril 2026

Ver `CHANGELOG.md` para el detalle completo de cambios.

---

## Mantenedor

**Fredy Bonilla** — COE Leader, Performance Testing
SQA Colombia (sqasa.co)

---

*Proyecto interno de SQA Colombia. No distribuir sin autorización.*
