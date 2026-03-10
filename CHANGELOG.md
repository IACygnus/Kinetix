# Changelog

Todos los cambios notables de JMeter Analyzer Pro se documentan aqui.

---

## [2.0.0] - 2026-02-25

### Phase 1 — Autenticacion, Usuarios y Roles
- Sistema de autenticacion JWT (login, token refresh)
- CRUD de usuarios con roles: admin, tester, viewer
- Pagina de perfil con edicion de datos y cambio de contrasena
- Dashboard Home con estadisticas generales (total ejecuciones, errores, promedios)
- Historial de ejecuciones de performance con busqueda y paginacion
- Proteccion de rutas por rol (ProtectedRoute)
- Contexto de autenticacion global (AuthContext)

### Phase 2 — Multi-JTL, Redirecciones y Gemini Mejorado
- Upload de multiples archivos JTL (1-5 archivos por ejecucion)
- Endpoint de validacion de compatibilidad entre JTLs (`POST /validate-jtl`)
- Consolidacion temporal de datos multi-JTL con elapsed time
- Separacion automatica de redirecciones (patron `TransactionName-N`)
- Tabla de metricas de redirecciones separada
- Tipos de prueba: load, stress, endurance, spike, scalability
- Criterios de aceptacion configurables (concurrencia, response time, disponibilidad)
- 12 metodos de analisis Gemini AI + 2 de sintesis (conclusiones, recomendaciones)
- Cada seccion de AI almacenada en columna independiente en BD
- Modelo `gemini-1.5-pro` con `max_output_tokens=8192`
- Frontend multi-file con validacion previa y modal de advertencias

### Phase 3 — Graficos y Exportacion
- 8 graficos interactivos con Chart.js (Response Times, Throughput, Latency, Error Rate, Codes/s, TPS, Active Threads, Pie de Codigos)
- Configuracion de colores centralizada (`chartConfig.ts`)
- Exportacion HTML profesional con graficos embebidos (base64)
- Exportacion PDF con WeasyPrint + matplotlib (portada SQA, KPIs, tablas, graficos, analisis IA)

### Phase 4 — Monitoreo en Tiempo Real (Grafana + InfluxDB)
- Integracion Grafana via iframe (MonitoringRealtime)
- Panel de configuracion de monitoreo (MonitoringSettings, admin only)
- Modelo MonitoringConfig con token InfluxDB encriptado (Fernet)
- Health checks de conectividad Grafana/InfluxDB
- Grafana provisioning automatico (datasource + dashboards)

### Phase 5 — QA, Seguridad y Documentacion
- Eliminado atributo `version` obsoleto de docker-compose.yml
- Healthchecks para backend en docker-compose.yml
- `docker-compose.prod.yml` con configuracion de produccion
- Credenciales movidas a variables de entorno (no hardcoded en codigo)
- CORS configurable: wildcard en dev, origenes especificos en produccion
- Admin seed password configurable via `ADMIN_DEFAULT_PASSWORD`
- Fernet key auto-generada si no se configura
- Eliminados imports no utilizados y statements de debug
- Respuestas de error sin stack traces
- `.env.example` completo con todas las variables
- README.md, CHANGELOG.md y INICIO_RAPIDO.md actualizados

---

## [1.3.0] - 2024-12-22

### Monitoreo en Tiempo Real
- Grafana 10.2.3 agregado al stack con Docker
- InfluxDB 2.7 como base de datos de series temporales
- Auto-provisioning de datasource InfluxDB en Grafana
- Dashboard profesional con 9 paneles de metricas en tiempo real
- Guia de configuracion para JMeter Backend Listener
- Docker Compose ahora con 5 servicios

---

## [1.2.0] - 2024-12-15

### Sintesis Inteligente con IA
- Campo `ai_conclusions` en modelo TestExecution
- Funciones `generate_conclusions()` y `generate_recommendations()` en Gemini
- Priorizacion automatica: CRITICO / ALTO / MEDIO
- Visualizacion en Dashboard de conclusiones y recomendaciones

---

## [1.1.0] - 2024-11-20

### Analisis Completo de Graficos
- 8 analisis IA individuales por grafico de performance
- Exportacion PDF con html2canvas + jsPDF
- Edicion inline de analisis IA
- Branding SQA (logo, colores corporativos)

---

## [1.0.0] - 2024-10-15

### Release Inicial
- API REST con FastAPI 0.104+
- PostgreSQL 15 como base de datos (SQLAlchemy Async)
- Parser JTL con Pandas (avg, min, max, p90, p95, p99, throughput, error rate)
- Servicio Gemini para analisis IA
- React 18 + TypeScript + Vite + Tailwind CSS
- Dashboard interactivo con 8 graficos (Recharts)
- Upload de archivos JTL
- Exportacion HTML con graficos embebidos
- Docker Compose con 3 servicios (backend, frontend, postgres)
