# Changelog

Todos los cambios notables de este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [1.3.0] - 2024-12-22

### ✨ Agregado - Monitoreo en Tiempo Real

#### Grafana + InfluxDB Integration
- **Grafana 10.2.3** agregado al stack con Docker
- **InfluxDB 2.7** como base de datos de series temporales
- **Auto-provisioning** de datasource InfluxDB en Grafana
- **Dashboard profesional** con 9 paneles de métricas en tiempo real:
  - Response Time Over Time (gráfica de líneas)
  - Active Threads (gráfica de área)
  - Error Rate (gauge con umbrales)
  - Throughput (gauge en req/s)
  - Total Requests (stat contador)
  - Total Errors (stat contador rojo)
  - Response Time Percentiles (p90/p95/p99)
  - Requests by Transaction (pie chart)
  - Transaction Details (tabla completa)

#### JMeter Backend Listener
- **Guía de configuración** para JMeter Backend Listener
- **Integración InfluxDB v1 compatibility endpoint** (`/write?db=jmeter`)
- **Autenticación con token** para envío de métricas
- **Retención de 30 días** en InfluxDB

#### Documentación
- **GRAFANA_SETUP.md** - Guía completa de instalación y configuración
- **Sección Grafana** en README.md principal
- **Troubleshooting** específico para Grafana e InfluxDB
- **Queries corregidas** para paneles Requests by Transaction y Transaction Details

#### Docker Compose
- **5 servicios** ahora (agregados `grafana` e `influxdb`)
- **Volúmenes persistentes** para Grafana e InfluxDB
- **Variables de entorno** para configuración de InfluxDB

### 🔧 Cambiado

#### Puertos
- **3000** - Grafana (nuevo)
- **8086** - InfluxDB (nuevo)
- 5173 - Frontend (sin cambios)
- 8001 - Backend (sin cambios)
- 5432 - PostgreSQL (sin cambios)

#### README.md
- **Sección actualizada** de servicios (5 en lugar de 3)
- **Tabla de acceso** con Grafana e InfluxDB
- **Arquitectura de monitoreo** documentada
- **Comandos útiles** para InfluxDB agregados

### 📝 Documentado
- Flujo de datos JMeter → InfluxDB → Grafana
- Configuración paso a paso de Backend Listener
- Queries Flux para cada panel de Grafana
- Troubleshooting de problemas comunes

---

## [1.2.0] - 2024-12-15

### ✨ Agregado - Síntesis Inteligente con IA

#### Conclusiones Generales
- **Nuevo campo `ai_conclusions`** en modelo `TestExecution`
- **Función `generate_conclusions()`** en servicio Gemini
  - Sintetiza los 10 análisis individuales
  - Genera 4-5 puntos ejecutivos máximo
  - Lenguaje claro para stakeholders
- **Visualización en Dashboard** - Sección de conclusiones generales

#### Recomendaciones Priorizadas
- **Función `generate_recommendations()`** en servicio Gemini
  - Priorización automática: CRÍTICO / ALTO / MEDIO
  - Basado en patrones detectados en análisis
- **Criterios de priorización**:
  - CRÍTICO: Error rate > 10%, p99 > 5000ms
  - ALTO: Error rate 5-10%, p99 2000-5000ms
  - MEDIO: Optimizaciones recomendadas

#### Migración de Base de Datos
- **Script SQL** para agregar columna `ai_conclusions`
- **Documentación** en TROUBLESHOOTING.md

### 🔧 Cambiado
- **Modelo Gemini** actualizado a `gemini-1.5-pro-latest`
- **Endpoint `/api/v1/executions/{id}/analysis`** ahora incluye `conclusions`
- **Schema `TestExecutionResponse`** actualizado con campo `ai_conclusions`

### 🐛 Corregido
- **Error 404** con modelo `gemini-1.5-pro` → Ahora usa `gemini-1.5-pro-latest`
- **TypeError** en schemas Pydantic por campo faltante

---

## [1.1.0] - 2024-11-20

### ✨ Agregado - Análisis Completo de Gráficos

#### Análisis IA Individual por Gráfico
- **8 análisis IA** para cada gráfico de performance:
  1. Response Times por Transacción
  2. Response Time Over Time
  3. Throughput Over Time
  4. Latency Over Time
  5. Error Rate Over Time
  6. Response Codes per Second
  7. Transactions per Second
  8. Active Threads Over Time

#### Exportación PDF
- **Hook `usePDFExport`** en frontend
- **Librería html2canvas** para captura de pantalla
- **Librería jsPDF** para generación de PDF
- **Exportación completa** del dashboard (cards + tabla + gráficos + análisis)

#### Edición Inline de Análisis
- **Componente editable** para cada análisis IA
- **Endpoint PUT `/api/v1/executions/{id}/analysis`** para guardar cambios
- **Estado local** en React para edición optimista

#### Branding
- **Logo SQA** en dashboard
- **Colores corporativos** en gráficos
- **Footer con información** de versión

### 🔧 Cambiado
- **Servicio Gemini** refactorizado para análisis por gráfico
- **Dashboard** reorganizado con pestañas/secciones

---

## [1.0.0] - 2024-10-15

### ✨ Agregado - Release Inicial

#### Backend (FastAPI)
- **API REST** con FastAPI 0.104+
- **PostgreSQL 15** como base de datos
- **SQLAlchemy Async** para ORM
- **Modelo `TestExecution`** para almacenar ejecuciones
- **Modelo `User`** para autenticación
- **JWT Authentication** con tokens
- **Parser JTL** con Pandas
  - Extracción de métricas: avg, min, max, p90, p95, p99
  - Cálculo de error rate, throughput
  - Procesamiento de 10,000+ muestras
- **Servicio Gemini** para análisis IA
  - Análisis de tabla resumen
  - Análisis de errores
- **Endpoints**:
  - `POST /api/v1/upload` - Subir JTL
  - `GET /api/v1/executions/{id}` - Obtener ejecución
  - `GET /api/v1/executions/{id}/charts` - Obtener datos de gráficos
  - `POST /api/v1/auth/login` - Login
  - `GET /api/v1/export/html/{id}` - Exportar HTML

#### Frontend (React + TypeScript)
- **React 18** con TypeScript
- **Vite** como build tool
- **Tailwind CSS** para estilos
- **Recharts** para gráficos
- **Dashboard interactivo**:
  - 4 cards de resumen
  - Tabla de estadísticas
  - 8 gráficos de performance
- **Upload de archivos JTL**
- **Login con JWT**
- **Visualización de análisis IA**

#### Gráficos (Recharts)
1. **Response Times por Transacción** - BarChart
2. **Response Time Over Time** - LineChart
3. **Throughput Over Time** - AreaChart
4. **Latency Over Time** - LineChart
5. **Error Rate Over Time** - LineChart con porcentajes
6. **Response Codes per Second** - BarChart stacked
7. **Transactions per Second** - LineChart
8. **Active Threads Over Time** - AreaChart

#### Exportación HTML
- **Template Jinja2** para generar HTML standalone
- **Gráficos embebidos** con Plotly
- **Estilos inline** para portabilidad

#### DevOps
- **Docker Compose** con 3 servicios:
  - backend (FastAPI)
  - frontend (React)
  - postgres (PostgreSQL 15)
- **Volúmenes persistentes** para PostgreSQL
- **Variables de entorno** en archivo `.env`
- **Dockerfile multi-stage** para optimización

#### Documentación
- **README.md** - Guía principal
- **GUIA_INICIO.md** - Paso a paso detallado
- **RESUMEN_EJECUTIVO.md** - Resumen del proyecto
- **TROUBLESHOOTING.md** - Solución de problemas

---

## [Unreleased] - Próximas Funcionalidades

### 🔜 Planificado

#### v1.4.0 - Comparación de Ejecuciones
- **Comparar múltiples ejecuciones** side-by-side
- **Gráficos de tendencias** entre ejecuciones
- **Análisis de regresión** con IA

#### v1.5.0 - Alertas y Notificaciones
- **Alertas configurables** en Grafana
- **Webhooks** para integración con Slack/Teams
- **Notificaciones por email** al detectar problemas

#### v2.0.0 - Multi-Proyecto
- **Organización por proyectos**
- **Dashboards personalizados** por proyecto
- **Roles y permisos** (admin, viewer, editor)

---

## Tipos de Cambios

- **✨ Agregado** - Para nuevas funcionalidades
- **🔧 Cambiado** - Para cambios en funcionalidades existentes
- **🗑️ Deprecado** - Para funcionalidades que se eliminarán pronto
- **🚫 Eliminado** - Para funcionalidades eliminadas
- **🐛 Corregido** - Para corrección de bugs
- **🔒 Seguridad** - Para vulnerabilidades de seguridad
- **📝 Documentado** - Para cambios en documentación

---

## Links de Comparación

- [1.3.0](https://github.com/tu-usuario/jmeter-analyzer/compare/v1.2.0...v1.3.0)
- [1.2.0](https://github.com/tu-usuario/jmeter-analyzer/compare/v1.1.0...v1.2.0)
- [1.1.0](https://github.com/tu-usuario/jmeter-analyzer/compare/v1.0.0...v1.1.0)
- [1.0.0](https://github.com/tu-usuario/jmeter-analyzer/releases/tag/v1.0.0)
