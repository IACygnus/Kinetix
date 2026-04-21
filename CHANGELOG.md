# Changelog

Todos los cambios notables del proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/)
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [3.0.0] - 2026-04-21

Expansión mayor del producto. Se consolidan 6 semanas de desarrollo (10 marzo → 21 abril) con funcionalidad nueva significativa que justifica un salto de versión mayor.

### Added

#### Script Designer (nuevo módulo completo)
- Diseñador visual de scripts de performance con 18 componentes React (~5,245 líneas)
- Import desde HAR (browser network capture)
- Import desde Postman collections
- Import desde OpenAPI / Swagger specs
- Import desde WSDL (SOAP)
- Chrome Extension propia para captura de tráfico
- Editor de requests con variables dinámicas
- Data files (CSV) para parametrización
- Correlación asistida por IA (detección automática de tokens y IDs)
- Variables globales y por escenario

#### Motor de Ejecución
- VirtualUser basado en httpx + asyncio (sin dependencia de JMeter)
- ExecutionManager con control de ciclo de vida
- SteppingController para load tests con rampa configurable
- SmokeTest engine para validación pre-carga
- JTLWriter con formato compatible JMeter estándar
- JMXExporter (export a .jmx para uso externo)
- MetricsCollector con WebSocket live

#### Informes Integrados
- Generación drag-and-drop de informes consolidados
- Bloques A (Executive Summary), A.1 (Scope), B (Technical Detail)
- Persistencia en DB de informes integrados
- Cover individual por sección
- Integración con attachments de monitoreo

#### Integración OpenAI
- Proveedor alternativo a Gemini (GPT-4o)
- Endpoint dinámico `/api/v1/ai-config/models/live` con cache de 5 minutos
- OpenAI Vision API para análisis de imágenes (formato multimodal)
- `OPENAI_MAX_TOKENS` dict configurable por modelo (4096 vs 16384)
- Selector de proveedor en AIConfigPage
- Fallback automático entre proveedores

#### Attachments
- Upload de imágenes de evidencia (monitoreo, errores, dashboards)
- Análisis IA de imágenes (Gemini Vision + OpenAI Vision + OCR fallback)
- Títulos editables por attachment
- Integración en informes exportados

#### Reportes Comparativos
- Comparación side-by-side entre dos ejecuciones
- Delta de métricas (avg, P95, P99, error rate, throughput)
- Export a HTML/PDF

#### Seguridad
- Migración de JWT en body a **httpOnly cookies**
- CSRF protection
- **Fernet encryption** para API keys y monitoring tokens
- Role-based access control (admin / user)
- Password policy con bcrypt

### Changed

#### Exportación HTML
- Plotly.js interactivo (reemplaza imágenes base64)
- Anchos fijos 1400px para consistencia visual
- Controles por gráfica: Mostrar/Ocultar todas, Auto-fit, P99, Reset, Max slider
- Leyenda scrollable (maxHeight 90px) en Dashboard live
- Color primario unificado Indigo `#4f46e5`

#### Exportación PDF
- Cover full-bleed con técnica `@page :first { margin: 0 }`
- Footer sin duplicación
- Portada de 1 página (antes se extendía a 2)
- Fix de inflación tipográfica (conversión `rem → pt`, reducción de 35-42%)
- Card styles atómicos
- Strip ordering corregido (conclusions individual antes de report extras)

#### Base de Datos
- Migraciones idempotentes con `ADD COLUMN IF NOT EXISTS`
- Ejecución en startup sin Alembic (`Base.metadata.create_all`)
- Nuevas tablas: `script_designs`, `attachments`, `integrated_reports`, `comparison_reports`

#### Frontend
- React Query integrado para data fetching
- httpOnly cookies en Axios client
- Interceptors globales para refresh de token
- Rebranding completo: "JMeter Analyzer Pro" → "SQA Kinetix Pro"

### Fixed
- Crash `NotFoundError: removeChild` en Dashboard con múltiples charts
- Gemini transport gRPC causa 503 en Docker → forzado a `transport="rest"`
- `sanitize_ai_text()` aplicado a toda salida IA (limpia markdown que rompía HTML)
- EditableTextArea recreado en cada render (focus loss) → movido fuera del padre
- LoadingSpinner con overlay fijo full-screen bloqueaba UI ante fallos de API
- React hooks llamados después de early returns
- Legend toggles iteraban individualmente → batching con replace atómico del Set

### Technical Debt (reconocido, no resuelto en esta versión)
- `report_generator.py` (~1,148 líneas) → candidato a refactor modular
- `integrated_report.py` (1,852 líneas) → candidato a split
- Alta cardinalidad en gráficas multi-línea (>15 transacciones) → fix programado para v3.1.0
- Cleanup de 284 archivos `.bak` acumulados → programado para v3.1.0
- Responsive para pantallas 15"/27" 1920×1080 → programado para v3.1.0
- JMX export completo desde Script Designer → programado para v3.1.0
- Deploy producción kinetix.sqasa.co → programado para v3.1.0

### Security
- Ningún secret commiteado al historial de git (verificado)
- `.env` y `.env.bak*` cubiertos por `.gitignore` desde commit inicial
- API keys y tokens cifrados en DB con Fernet

---

## [2.0.0] - 2026-03-10

Release con integración IA avanzada y fundamentos de seguridad.

### Added
- AI Config module con proveedor Gemini
- Client management
- User management (admin + user roles)
- Mejoras en autenticación JWT
- Export fixes para HTML y PDF

### Note
Este commit (`b83f736`) nunca fue taggeado en su momento. Se documenta retroactivamente sin crear el tag (política actual).

---

## [1.3.0] - 2026-02-20

### Added
- Integración Grafana + InfluxDB para monitoreo en tiempo real
- WebSocket de métricas live

---

## [1.2.0] - 2025-12-18

### Added
- Síntesis inteligente de análisis IA
- Conclusiones generales consolidadas
- Recomendaciones priorizadas (CRÍTICO / ALTO / MEDIO)

---

## [1.0.0] - 2025-11

### Added
- Release inicial
- Upload y parsing de archivos JTL
- Dashboard con 8 gráficas
- Análisis IA básico con Gemini
- Export HTML y PDF
