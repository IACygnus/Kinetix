# SQA Kinetix Pro — Project Reference (CLAUDE.md)

> Documento de referencia única del proyecto para cualquier sesión futura de
> desarrollo. **No editar a la ligera.** Reemplaza memoria a corto plazo entre
> sesiones de Claude Code.

---

## 1. IDENTIDAD DEL PROYECTO

- **Nombre:** SQA Kinetix Pro
- **Propietario:** Fredy Bonilla — COE Leader, Performance Testing, SQA Colombia
- **Propósito:** Plataforma interna de análisis automatizado de pruebas JMeter
  con asistencia de IA (Gemini / OpenAI). Cubre todo el ciclo: diseño de
  scripts, ejecución (motor propio), parseo de JTL, dashboards, reportes
  HTML/PDF integrados, monitoreo Grafana/InfluxDB y configuración dinámica de
  IA.
- **Repositorio:** Git local, branch principal `main`. Último tag publicado: **v3.1.0**.

---

## 2. STACK TÉCNICO COMPLETO

### Backend — Python 3.11 / FastAPI

`backend/requirements.txt`:

| Dependencia | Versión | Uso |
|---|---|---|
| fastapi | 0.104.1 | Framework HTTP |
| uvicorn[standard] | 0.24.0 | ASGI server |
| pydantic | 2.5.0 | Schemas |
| pydantic-settings | 2.1.0 | Config tipada |
| sqlalchemy | 2.0.23 | ORM (async) |
| asyncpg | 0.29.0 | Driver async Postgres |
| psycopg2-binary | 2.9.9 | Driver sync (Alembic-style) |
| python-jose[cryptography] | 3.3.0 | JWT |
| passlib[bcrypt] | 1.7.4 | Hash de contraseñas |
| **bcrypt** | **4.0.1** | **PIN — passlib incompatible con 5.x** |
| cryptography | >=41.0.0 | Fernet (encripta API keys) |
| python-multipart | 0.0.6 | Uploads |
| pandas | 2.1.4 | Análisis de JTL |
| lxml | 4.9.3 | Parseo XML |
| numpy | 1.24.3 | Numérico |
| google-generativeai | 0.3.1 | SDK Gemini |
| openai | >=1.0.0 | SDK OpenAI |
| tzdata | >=2024.1 | Zoneinfo containers |
| python-dotenv | 1.0.0 | .env loader |
| httpx | 0.27.0 | Cliente HTTP async |
| python-dateutil | 2.8.2 | Fechas |
| aiofiles | 23.2.1 | I/O async |
| email-validator | 2.1.0.post1 | Validación email |
| matplotlib | 3.8.2 | Gráficas PDF |
| pillow | 10.1.0 | Imágenes |
| pytesseract | >=0.3.10 | OCR (fallback Vision) |
| **weasyprint** | **61.2** | **PDF render** |
| **pydyf** | **0.10.0** | **PIN — WeasyPrint 61.2 incompatible con 0.12.x** |
| PyYAML | 6.0.1 | Importer OpenAPI YAML |

### Frontend — React 18 / TypeScript / Vite

`frontend/package.json` (versión `3.0.0`):

| Dependencia | Versión |
|---|---|
| react | ^18.2.0 |
| react-dom | ^18.2.0 |
| react-router-dom | ^6.20.0 |
| axios | ^1.6.2 |
| lucide-react | ^0.294.0 |
| recharts | ^2.15.4 |
| @dnd-kit/core | ^6.3.1 |
| @dnd-kit/sortable | ^10.0.0 |
| @dnd-kit/utilities | ^3.2.2 |
| html2canvas | ^1.4.1 |
| jspdf | ^3.0.4 |
| uuid | ^13.0.0 |
| @types/uuid | ^10.0.0 |
| typescript | ^5.2.2 (dev) |
| vite | ^5.0.8 (dev) |
| tailwindcss | ^3.3.6 (dev) |
| autoprefixer | ^10.4.16 (dev) |
| postcss | ^8.4.32 (dev) |
| @vitejs/plugin-react | ^4.2.1 (dev) |

### Servicios Docker (`docker-compose.yml`)

| Container | Imagen | Puerto host | Función |
|---|---|---|---|
| `jmeter_postgres` | postgres:15-alpine | 5432 | DB primaria |
| `jmeter_backend` | local build `./backend` | 8001 | FastAPI |
| `jmeter_frontend` | local build `./frontend` target `builder` | 5173 | Vite dev server |
| `jmeter_influxdb` | influxdb:2.7-alpine | 8086 | Métricas tiempo real |
| `jmeter_grafana` | grafana/grafana:10.2.3 | 3000 | Dashboards |

Network bridge: `jmeter_network`. Volúmenes nombrados: `postgres_data`,
`uploads_data`, `influxdb_data`, `influxdb_config`, `grafana_data`.

### Diferencias con producción (`docker-compose.prod.yml`)

- `restart: always` en todos los servicios (vs `unless-stopped`).
- `postgres`, `influxdb`, `grafana` con `ports: []` → puertos cerrados al host.
- `backend`: `--workers 2`, sin `--reload`, `ENVIRONMENT=production`, sin
  defaults — todos los secretos deben venir de `.env`.
- `frontend`: usa target **production** del Dockerfile (nginx interno,
  expone `5173:80`), volúmenes vacíos, sin `npm run dev`.
- `grafana`: `GF_AUTH_ANONYMOUS_ENABLED=false`, cookie `samesite=strict`.

---

## 3. ESTRUCTURA DEL PROYECTO

### Backend (`backend/app/`)

```
backend/app/
├── main.py
├── __init__.py
├── api/v1/
│   ├── api.py                            # Router central
│   └── endpoints/
│       ├── ai_config.py                  # Config dinámica IA
│       ├── analysis_ai.py                # Monitoring + evidence + image analysis
│       ├── attachments.py                # Upload imagenes monitoring/evidence
│       ├── auth.py                       # Login / refresh / logout / me
│       ├── clients.py                    # Clientes y asignaciones
│       ├── compare.py                    # Reporte comparativo carga vs estres
│       ├── dashboard.py                  # /dashboard/stats
│       ├── data_files.py                 # CSVs para Script Designer
│       ├── executions.py                 # Motor propio (smoke, start, control)
│       ├── export_html.py                # Reporte HTML standalone (Plotly)
│       ├── export_pdf.py                 # Reporte PDF (WeasyPrint)
│       ├── har_import.py                 # Importar HAR de Chrome
│       ├── import_script.py              # Postman / OpenAPI / WSDL / Chrome
│       ├── integrated_report.py          # Reporte integrado drag-and-drop
│       ├── monitoring.py                 # Config Grafana + InfluxDB
│       ├── performance_executions.py     # Historial motor propio
│       ├── profile.py                    # Perfil usuario logueado
│       ├── scenarios.py                  # Escenarios load/stress/spike/soak
│       ├── script_ai.py                  # AI Script Designer (JMX desde prompt)
│       ├── script_variables.py           # Variables del Script Designer
│       ├── scripts.py                    # ScriptDesign CRUD + export-jmx
│       ├── upload.py                     # Upload + parse JTL + análisis IA
│       ├── users.py                      # Gestión usuarios
│       └── ws_metrics.py                 # WebSocket métricas live
├── config/
│   └── chart_config.py                   # Constantes de chartConfig backend
├── core/
│   ├── config.py                         # pydantic-settings
│   └── security.py                       # JWT, require_role, CSRF
├── db/
│   ├── base_class.py
│   ├── session.py                        # get_db dependency
│   └── models/
│       ├── ai_config.py
│       ├── attachment.py
│       ├── client.py
│       ├── data_file.py
│       ├── integrated_report.py
│       ├── monitoring.py
│       ├── performance_execution.py
│       ├── scenario.py
│       ├── script_design.py
│       ├── test.py
│       └── user.py
├── schemas/                              # Pydantic schemas (auth, ai_config, …)
└── services/
    ├── ai/gemini.py                      # GeminiAnalyzer + Fallback + analyze_image
    ├── engine/                           # Motor propio de performance testing
    │   ├── ai_correlation.py
    │   ├── data_file_service.py
    │   ├── execution_manager.py
    │   ├── har_importer.py
    │   ├── jmx_exporter.py
    │   ├── jtl_writer.py
    │   ├── metrics_collector.py
    │   ├── openapi_importer.py
    │   ├── postman_importer.py
    │   ├── protocols/{base.py,http_handler.py}
    │   ├── smoke_test.py
    │   ├── stepping_controller.py
    │   ├── variable_engine.py
    │   ├── virtual_user.py               # Ejecutor por usuario virtual
    │   └── wsdl_importer.py
    ├── export/
    │   ├── high_cardinality_strategy.py
    │   └── report_generator.py           # build_pdf_html
    ├── jmx_parser.py
    ├── jtl/jtl_parser.py                 # CSV + XML JTL → DataFrames
    └── parsers/
        ├── format_detector.py
        ├── locust_parser.py
        └── wapt_parser.py
```

> **Nota:** No existe `backend/app/services/script-designer/`. El motor propio
> de Script Designer vive bajo `backend/app/services/engine/`.

### Frontend (`frontend/src/`)

```
frontend/src/
├── App.tsx                               # Router + rutas protegidas
├── main.tsx
├── vite-env.d.ts
├── api/
│   ├── executionApi.ts
│   └── scriptDesignerApi.ts
├── components/
│   ├── admin/AIConfigPage.tsx
│   ├── analysis/{EditableAttachmentTitle, ImageAnalysisCard}.tsx
│   ├── auth/Login.tsx
│   ├── charts/{ByLabelChart, StatsTable, TimelineChart}.tsx
│   ├── clients/{ClientsPage, AssignmentsPage}.tsx
│   ├── common/{LoadingSpinner, ProtectedRoute}.tsx
│   ├── dashboard/
│   │   ├── AttachmentSection.tsx
│   │   ├── CapacityAnalysis.tsx
│   │   ├── ChartYAxisZoom.tsx
│   │   ├── ComparisonReport.tsx
│   │   ├── Dashboard.tsx                 # ⚠ Protegido — 1177 líneas
│   │   ├── DashboardHome.tsx
│   │   └── UploadJTL.tsx
│   ├── execution/{ScenarioForm, LiveMetricsChart, ExecutionHistory}.tsx
│   ├── integrated/{ConsolidatedAnalysisSection, DashboardEmbed,
│   │                ExecutionReportSection, MonitoringReportSection}.tsx
│   ├── layout/{Footer, Layout, Sidebar}.tsx
│   ├── monitoring/{MonitoringRealtime, MonitoringSettings}.tsx
│   ├── performance/History.tsx
│   ├── profile/Profile.tsx
│   ├── script-designer/                  # 15 componentes (RequestEditor, …)
│   └── users/{UserForm, UserList}.tsx
├── config/chartConfig.ts
├── context/AuthContext.tsx               # cookies httpOnly + sliding session
├── hooks/usePDFExport.ts
├── pages/
│   ├── AIScriptDesigner.tsx              # Generador de JMX con IA
│   ├── EvidencePage.tsx
│   ├── ExecutionDashboard.tsx
│   ├── IntegratedReportPage.tsx
│   ├── MonitoringPage.tsx
│   ├── ReportView.tsx
│   ├── ScriptDesigner.tsx                # ⚠ Protegido — 967 líneas
│   └── ScriptHistory.tsx
├── services/api.ts                       # axios + CSRF interceptor
└── types/index.ts
```

---

## 4. ENDPOINTS REST

Prefijo global: `/api/v1`. Todos los endpoints de mutación requieren cookie
`csrf_token` + header `X-CSRF-Token` (middleware en `main.py`). Auth por cookie
httpOnly `access_token`.

### `auth` (`/auth`)
| Verbo | Path | Función |
|---|---|---|
| POST | `/auth/login` | Login (FormData) — sets cookies, rate-limited 5/15min/IP |
| POST | `/auth/refresh` | Refresh token (sliding session) |
| POST | `/auth/logout` | Limpia cookies |
| GET | `/auth/me` | Usuario actual |

### `dashboard` (`/dashboard`)
- GET `/dashboard/stats` — métricas agregadas para la home

### `performance` (`upload.py` — sin prefijo extra)
| Verbo | Path | Función |
|---|---|---|
| GET | `/gemini-test` | Diagnóstico de conectividad Gemini |
| POST | `/extract-jtl-labels` | Lista labels de un JTL |
| POST | `/validate-jtl` | Valida estructura de JTL |
| POST | `/parse-jmx` | Extrae nombres de threads del JMX |
| POST | `/upload` | **Pipeline completo**: parse JTL + 12+2 análisis IA + persistencia |
| GET | `/executions` | Histórico de ejecuciones |
| DELETE | `/executions/{id}` | Eliminar ejecución |
| GET | `/executions/{id}` | Detalle |
| GET | `/executions/{id}/charts` | Datos para Dashboard |
| PUT | `/executions/{id}/analysis` | Editar análisis IA |
| GET/PUT | `/executions/{id}/capacity` | Análisis de capacidad |

### `export` (`/executions/{id}/export`)
- GET `/executions/{id}/export/html` — HTML interactivo con Plotly
- GET `/executions/{id}/export/pdf` — PDF (WeasyPrint + matplotlib)

### `users` (`/users`)
CRUD completo + `PATCH /{id}/toggle` (activar/desactivar) +
`POST /{id}/reset-password`.

### `profile` (`/profile`)
- GET / PUT (`/profile`) + PUT `/profile/password`

### `clients` (`/clients`)
- CRUD `/clients/`
- `GET /clients/assignments`, `POST /clients/assignments`,
  `DELETE /clients/assignments/{user_id}/{client_id}`
- `GET /clients/user-clients` — clientes visibles para el usuario actual

### `monitoring` (`/monitoring`)
- GET / PUT `/monitoring/config` — config Grafana + InfluxDB
- GET `/monitoring/health`

### `ai-config` (`/ai-config`)
| Verbo | Path | Función |
|---|---|---|
| GET | `/ai-config` | Config activa (key enmascarada) |
| POST | `/ai-config` | Crear/actualizar config |
| GET | `/ai-config/models` | Lista hardcoded por provider |
| GET | `/ai-config/models/live` | Llama API del provider, **cache TTL 5min**, fallback a lista hardcoded |
| POST | `/ai-config/test` | Probar conexión (acepta payload o usa DB) |
| POST | `/ai-config/reset-usage` | Resetear contadores (admin) |

### Motor de Performance Testing
- `/scripts` — CRUD ScriptDesign + `POST /{id}/export-jmx`
- `/scenarios` — CRUD + `GET /scenarios/templates`
- `/performance-executions` — listar / detalle ejecuciones del motor propio
- `/har-import/preview` — preview HAR antes de importar
- `/data-files` — upload CSV, preview, mapping, columns
- `/executions` — `smoke-test`, `ai-correlate`, `ai-debug`, `start`,
  `{id}/control`, `history`, `{id}/status`, `{id}/download-jtl`,
  `{id}/generate-report`, `run-single`
- `/import/postman|openapi|wsdl|chrome/push|chrome/pending/{id}|chrome/convert/{id}`
- `/scripts/{id}/variables` (variable manager)
- WebSocket: `/ws/executions/{id}/metrics` (live metrics)

### Attachments + AI análisis (`/executions/{id}/...`)
- `POST /attachments` — subir imagen monitoring/evidence
- `GET /attachments` — listar
- `PUT /attachments/{aid}` — edit
- `DELETE /attachments/{aid}`
- `POST /attachments/{aid}/analyze-image` — Gemini/OpenAI Vision
- `GET /attachments/{aid}/analysis` + `PUT` para editar
- `POST /analyze-all-images` — batch
- `GET /attachment-counts`, `GET /image-analyses`
- `POST /monitoring-analysis`, `GET /monitoring-analysis`
- `POST /evidence-analysis`, `GET /evidence-analysis`

### Reportes (`/reports`)
- `POST /reports/compare` — comparativa carga vs estrés (con IA)
- `POST /reports/integrated` — generar HTML integrado
- `POST /reports/integrated/export-pdf`
- `POST /reports/integrated/export-html`
- `POST /reports/integrated/generate-consolidated`
- `GET /reports/integrated-reports` — listar
- `GET/PATCH/DELETE /reports/integrated-reports/{id}`

### AI Script Designer (`/script-designer/ai`)
- `POST /script-designer/ai/generate` — desde prompt
- `POST /script-designer/ai/generate-from-file` — multipart (Postman / Swagger / texto)
- `POST /script-designer/ai/refine` — refinamiento (acepta `file_content`)
- `POST /script-designer/ai/validate` — parse + lista de componentes
- `POST /script-designer/ai/download` — descarga `.jmx`

---

## 5. MODELOS DE BASE DE DATOS

Todos los modelos heredan de `app.db.base_class.Base`. SQLAlchemy 2.0 async.
Schema se crea con `Base.metadata.create_all` al startup (sin Alembic).

| Tabla | Columnas clave |
|---|---|
| **`users`** | id (UUID PK), username, email (unique), full_name, hashed_password, role (admin/analyst/viewer), is_active, created_at, updated_at, created_by FK→users |
| **`clients`** | id (UUID), name (unique), description, contact_name, contact_email, is_active |
| **`user_clients`** | id, user_id FK CASCADE, client_id FK CASCADE, unique(user_id, client_id) |
| **`test_executions`** | id (UUID), user_id, name, description, client (texto legacy) + client_id FK, project, test_type, jtl_filename, jtl_filenames (JSON), acceptance_criteria_json, start_time, end_time, duration_seconds, total_requests, total_errors, error_rate, avg/median/min/max + p50/p90/p95/p99 response_time, throughput, avg_latency, kb_per_sec_*, total_redirects, redirect_labels (JSON), ai_analysis_* (12+ campos), ai_recommendations, ai_conclusions, capacity_analysis_json, metric_unit (TPS/UVC) |
| **`test_results`** | id, execution_id, timestamp, elapsed_time, label, response_code, response_message, thread_name, data_type, success, failure_message, bytes_received, bytes_sent, grp_threads, all_threads, url, latency, idle_time, connect_time |
| **`ai_config`** | id (UUID), provider (gemini/openai), model_name, api_key_encrypted (Fernet), is_active, daily/monthly_request_limit, daily/monthly_requests_used, last_reset_daily, last_reset_monthly |
| **`monitoring_config`** | id, grafana_url, grafana_dashboard_uid, influxdb_url, influxdb_org, influxdb_bucket, influxdb_token_encrypted (Fernet), is_configured |
| **`execution_attachments`** | id, execution_id FK CASCADE, attachment_type (monitoring/evidence), title, description, category, filename, filepath, file_type, file_size, sort_order, ai_analysis, ai_analysis_updated_at |
| **`script_designs`** | id (Integer), name, description, user_id FK→users, client_id FK, script_model (JSON: requests/variables/extractors), script_type (api/web/both), client_name, origin (manual/har_import/proxy_capture/wsdl_import/postman/openapi) |
| **`data_files`** | id, script_id FK, original_filename, stored_filename, file_path, columns (JSON), row_count, variable_mapping (JSON) |
| **`scenarios`** | id, name, script_id FK, test_type (load/stress/spike/soak/custom), thread_group_config (JSON: initial_users/step_users/step_duration_sec/hold_duration_sec/max_users/ramp_down_sec/total_duration_sec/think_time_ms/iterations), acceptance_criteria (JSON) |
| **`performance_executions`** | id, scenario_id FK, user_id FK, status (pending/starting/running/stopping/completed/error/cancelled), jtl_file_path, jmx_file_path, output_filename, summary_metrics (JSON), scenario_snapshot (JSON), error_message, started_at, completed_at |
| **`integrated_reports`** | id (UUID), name, sections (JSONB), consolidated_analysis (JSONB), created_by FK |

---

## 6. SISTEMA DE IA

### `backend/app/services/ai/gemini.py` (1525 líneas)

- **Providers soportados:** Gemini (`google-generativeai`) y OpenAI
  (`openai >=1.0.0`). El dispatcher decide en runtime según
  `load_ai_config_from_db()` → `{provider, model_name, api_key}`.
- **GeminiAnalyzer:** clase única que encapsula ambos providers, con circuit
  breaker (`_circuit_open`), contadores de requests/errores, retries y delays
  configurables.
- **FallbackAnalyzer:** se activa cuando la IA devuelve 429 o errores
  irrecuperables; produce análisis básico estructurado.
- **Flujo de análisis (`/upload`):**
  1. Parse JTL → DataFrame.
  2. `prepare_insights_for_prompt()` (pre-clasificación en tiers).
  3. 12 secciones IA + 2 (recomendaciones, conclusiones) de forma
     **secuencial** (12 pasos escritos a mano en `run_ai_and_verdict`, uno
     detrás de otro), con `sanitize_ai_text()` aplicado a cada salida.
  4. `compute_verdict()` (cumple/no cumple acceptance criteria).
  5. `compute_per_transaction_verdicts()` (KNX-09).
  6. `update_ai_usage_in_db()` para sincronizar contadores.

#### `GENERATION_CONFIG`
```python
GENERATION_CONFIG = {
    "max_output_tokens": 8192,
    "temperature": 0.7,
}
```

#### `OPENAI_MAX_TOKENS`
```python
OPENAI_MAX_TOKENS = {
    "gpt-3.5-turbo": 4096,
    "gpt-4": 4096,
    "gpt-4-turbo": 4096,
    "gpt-4o": 16384,
    "gpt-4o-mini": 16384,
    "gpt-4.1": 32768,
    "gpt-4.1-mini": 16384,
    "gpt-4.1-nano": 8192,
    "gpt-5-mini": 16384,
    "gpt-5-nano": 8192,
    "o4-mini": 16384,
}
OPENAI_DEFAULT_MAX_TOKENS = 4096
```

#### `analyze_image(image_bytes, mime_type, category, title, description, attachment_type)`
Bifurcación por provider:
- **Gemini Vision:** `genai.GenerativeModel.generate_content([prompt, image_part])` con `image_part = {"mime_type", "data": base64}`. `max_output_tokens=1024`, `temperature=0.3`.
- **OpenAI Vision:** formato multimodal explícito —
  ```python
  messages=[{"role": "user", "content": [
      {"type": "text", "text": prompt},
      {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
  ]}]
  ```
  con `max_tokens = min(OPENAI_MAX_TOKENS[model], 1024)`.
- **Fallback OCR (pytesseract):** si ambas vías fallan.
- Instrucciones diferenciadas según `attachment_type == "monitoring"` vs `"evidence"`.

#### `sanitize_ai_text(text)`
Limpia formato markdown del output IA antes de persistir/exportar:
- Headers `#`, `##`…
- Bold `**...**`, `__...__`
- Italic `*...*` (cuidando contracciones)
- Bullets de inicio de línea `*`, `-`
- Backticks ``` ` ` ```
- Reglas horizontales `---`
- Colapsa múltiples líneas en blanco

**Palabras prohibidas** en el SYSTEM_PROMPT (no aparecen en `sanitize_ai_text`,
pero el prompt las veda explícitamente):
`veredicto`, `hallazgo`, `se evidencia`, `cabe destacar`,
`es importante mencionar`, `en conclusion`.

### `backend/app/api/v1/endpoints/ai_config.py`

#### `PROVIDERS` dict
```python
PROVIDERS = {
    "gemini": AIProviderInfo(id="gemini", name="Google Gemini", models=[
        "gemini-3.1-flash-lite-preview", "gemini-2.5-flash",
        "gemini-2.5-flash-lite", "gemini-3-flash-preview"
    ]),
    "openai": AIProviderInfo(id="openai", name="OpenAI", models=[
        "gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"
    ]),
}
```

- **Test connection:** `POST /ai-config/test` acepta payload `(provider, model_name, api_key)` para probar antes de guardar; cae a config en DB si no se envía. Para Gemini hace `generate_content("Responde solo: OK")`; para OpenAI hace `chat.completions.create(messages=[{"role":"user","content":"Responde solo: OK"}], max_tokens=10)`. Detecta 429/quota explícitamente.
- **FERNET_KEY:** se usa para encriptar `api_key_encrypted` en DB. Si no está configurada, se auto-genera al startup (warning logueado, no persiste entre reinicios — re-guardar la key cuando cambie).
- **Models live cache:** TTL 5 minutos, keyed por `provider:api_key_prefix`, se invalida al guardar config. Fallback a la lista hardcoded en caso de error.

---

## 7. SISTEMA DE REPORTES

### `backend/app/services/export/report_generator.py` (1148 líneas)

Módulo central que comparte generación de gráficas (matplotlib → base64) y
construcción de HTML para los dos exportadores (PDF y HTML standalone).

- **`build_pdf_html(...)`** — produce HTML optimizado para WeasyPrint:
  - Cover page full-bleed con `@page :first { margin: 0 }`.
  - `@page` rules con `@bottom-right` para paginación.
  - Tablas y media queries en `mm`/`pt` (NUNCA `rem` — infla 35-42% en PDF).
  - Solo layouts en `table`, **no flex/grid** (WeasyPrint los procesa mal).
  - Headers navy `#0a1628`, cajas IA naranja `#fff7ed`.
  - Accent **Indigo `#4f46e5`** (estándar visual SQA).
- **Helpers compartidos:** `chart_area()`, `chart_multiline()`, `chart_pie()`
  retornan imágenes base64 listas para `<img src="data:image/png;base64,...">`.

### `backend/app/api/v1/endpoints/export_html.py`

- `GET /executions/{id}/export/html` — HTML interactivo con **Plotly** (CDN)
  generado en el browser; descargable como archivo único.

### `backend/app/api/v1/endpoints/export_pdf.py`

- `GET /executions/{id}/export/pdf` — WeasyPrint + matplotlib renderiza PDF
  desde el HTML de `build_pdf_html()`.

### `backend/app/api/v1/endpoints/integrated_report.py` (1866 líneas)

Reporte integrado con drag-and-drop: combina secciones de varios reportes en
un único documento.

- **`POST /reports/integrated/export-pdf`** y `…/export-html`.
- **`_build_att_html(section, attachments, ai_analysis, title_prefix, for_pdf=False)`**:
  bifurca CSS según `for_pdf` — rama PDF usa `pt`/`mm`, rama web usa unidades
  modernas. Misma plantilla, dos render targets.
- **`_strip_pdf_individual_conclusions(html)`**: elimina conclusiones por
  sección antes del PDF para que las conclusiones consolidadas no se
  dupliquen.
- **`_strip_individual_report_extras(body_html)`**: elimina headers /
  metadatos repetidos cuando varios reportes se fusionan.
- **Orden crítico:** llamar `_strip_pdf_individual_conclusions` **antes** de
  `_strip_individual_report_extras` (saltarlo invierte el resultado).
- **`_build_plotly_html_isolated(execution_data, prefix)`**: empaqueta una
  gráfica Plotly aislada con su propio script para evitar colisiones de IDs
  entre secciones embebidas.

---

## 8. AI SCRIPT DESIGNER

### `backend/app/api/v1/endpoints/script_ai.py` (866 líneas)

Endpoints (auth: `admin | analyst`):

| Verbo | Path | Función |
|---|---|---|
| POST | `/generate` | JMX desde prompt natural |
| POST | `/generate-from-file` | multipart: archivo + prompt opcional |
| POST | `/refine` | refina JMX actual; acepta `file_content` para reusar referencia |
| POST | `/validate` | parsea JMX, lista componentes + errores estructurales |
| POST | `/download` | retorna `.jmx` (StreamingResponse) |

**Detector de archivo (`_detect_and_format`):**
- Postman Collection v2.x: JSON con `info` + `item` → recorre carpetas
  anidadas, extrae método, URL, headers, body (`raw`/`urlencoded`/`formdata`),
  variables de colección, scripts `event.listen=test` como hints de assertion.
- OpenAPI/Swagger: JSON o YAML con `openapi`/`swagger` → enumera paths con
  summary, parameters y content-types del requestBody. Límite 80 endpoints.
- Resto: texto genérico (envuelto en `--- CONTENIDO DEL ARCHIVO ---`).
- **Cap de tamaño:** `MAX_FILE_BYTES = 500 KB` (truncación blanda; el
  frontend valida del lado cliente también).

**SYSTEM_PROMPT (resumen):** "Arquitecto experto en Apache JMeter con 15 años…"
con estructura obligatoria de 10 secciones (Test Plan → UDV → HTTP Defaults →
Cookie/Cache Manager → CSV Data Sets → Thread Group → HTTP Samplers numerados
con Header Manager + Body + Response Assertion + Regex Extractor → Listeners),
formato XML JMeter 5.6.3 estricto, reglas específicas para Postman y para
OpenAPI/Swagger, y reglas de calidad (nombres descriptivos numerados,
comentarios XML, variables para todo lo configurable, no URLs hardcodeadas).

**Dispatch IA (`_call_ai`):**
- OpenAI: `chat.completions.create(model=ai_conf.model_name, messages, temperature=0.4, max_tokens=8192)`.
- Gemini: aplana los mensajes a un único prompt con marcas `[USER]`/`[ASSISTANT]`,
  `transport="rest"` siempre (requerido en Docker).

### `frontend/src/pages/AIScriptDesigner.tsx` (1.352 líneas)

- Layout dos paneles: chat 40% / preview JMX 60%.
- Botón "Adjuntar archivo" (input file oculto, accept
  `.json,.yaml,.yml,.txt,.postman_collection`).
- Chip de archivo pendiente (bg `indigo-100`) + chip de referencia persistente
  (bg `indigo-50`, "se reusa en refinamientos").
- Flujo:
  1. Sin archivo + sin JMX → `POST /generate`
  2. Con archivo → `POST /generate-from-file` (FormData).
  3. Con JMX existente → `POST /refine` (envía `file_content` si hay
     referencia persistida).
- Validación tamaño 500 KB en cliente; backend trunca si se excede.
- Badge "JMX Válido"/"JMX Inválido" + descarga `.jmx`.
- Lista de componentes detectados (Thread Group con # usuarios, HTTP Sampler
  con método, etc.).

---

## 9. SCRIPT DESIGNER ORIGINAL

### `frontend/src/pages/ScriptDesigner.tsx` (967 líneas — **PROTEGIDO**)

Editor visual de scripts (no IA). Maneja:
- Onboarding inicial (drafts en localStorage, `DRAFT_KEY`).
- Lista de requests con `RequestTable` + edición con `RequestEditor`.
- Variable Manager (`VariableManager`) — usa `scanVariablesFromModel` y
  componentes `VariableInlineEditor`, `VariableValuePreview`,
  `VariableAutocomplete`, `VariableExtractorPanel`.
- Data Files (`DataFileManager`) — CSVs subidos, columnas, mapping a
  variables `${nombre}`.
- Modal de importación (`ImportModal`) — Postman / OpenAPI / WSDL / HAR /
  Chrome (push-pull).
- Smoke Test + Body Editor + Request Runner + Run Result Panel.
- Ejecución y resultados (`ExecutionHistoryPanel`, `JMeterResultDetail`).
- Exportación JMX desde `POST /scripts/{id}/export-jmx`.

### Backend asociado — `backend/app/services/engine/`

- **`virtual_user.py`** — ejecutor por usuario virtual (194 líneas).
- **`stepping_controller.py`** — controla el Stepping Thread Group propio.
- **`execution_manager.py`** — orquestador de ejecuciones.
- **`smoke_test.py`** — smoke test con N=1 usuario.
- **`metrics_collector.py`** — recolecta métricas en memoria + InfluxDB.
- **`jtl_writer.py`** — escribe JTL compatible con JMeter.
- **`jmx_exporter.py`** — convierte ScriptDesign → JMX nativo.
- **`variable_engine.py`** — sustitución de `${variables}` por iteración.
- **`data_file_service.py`** — lectura de CSVs (modos: all/random/sequential).
- **`ai_correlation.py`** — sugiere extractors con IA.
- **Importers:** `har_importer.py`, `postman_importer.py`,
  `openapi_importer.py`, `wsdl_importer.py`.
- **`protocols/`** — `base.py` interfaz y `http_handler.py` implementación HTTP.

---

## 10. JTL PARSER (`backend/app/services/jtl/jtl_parser.py` — 511 líneas, **PROTEGIDO**)

Soporta **CSV (default)** y **XML** nativos de JMeter.

### `_is_xml_jtl(file_path: str) -> bool`
Lee la primera línea no-vacía y devuelve `True` si empieza con `<?xml` o
`<testResults`. Decide qué pipeline usar.

### `_parse_xml_jtl_to_df(file_path: str) -> pd.DataFrame`
- Itera con `xml.etree.ElementTree.iterparse(events=('start','end'))`.
- Solo procesa `httpSample`/`sample` a **depth=1** (ignora samples anidados
  para no doblar conteos).
- **Mapeo XML attr → columna CSV** (mismas claves que `pd.read_csv` produciría
  sobre un JTL CSV):

  | XML attr | CSV col |
  |---|---|
  | `ts` | `timeStamp` |
  | `t` | `elapsed` |
  | `lb` | `label` |
  | `rc` | `responseCode` |
  | `rm` | `responseMessage` |
  | `tn` | `threadName` |
  | `dt` | `dataType` |
  | `s` | `success` |
  | `by` | `bytes` |
  | `sby` | `sentBytes` |
  | `ng` | `grpThreads` |
  | `na` | `allThreads` |
  | `lt` | `Latency` |
  | `it` | `IdleTime` |
  | `ct` | `Connect` |

  Adicionalmente: `URL = elem.get('u', '')`, `failureMessage = ''`.

- `elem.clear()` después de cada sample para liberar memoria.
- Castea columnas numéricas con `pd.to_numeric(errors='coerce').fillna(0).astype(int)`.

### Flujo de `parse()`
1. Detecta formato (`_is_xml_jtl`).
2. CSV → `pd.read_csv` con dtypes específicos; XML → `_parse_xml_jtl_to_df`.
3. Separa main vs redirects por label (302/30x).
4. Retorna `(df_main, df_redirects, redirect_labels)` que el endpoint
   `/upload` consume.

---

## 11. ARCHIVOS PROTEGIDOS

> **Norma:** estos archivos no se refactorizan sin autorización explícita de
> Fredy. Cualquier cambio debe ser quirúrgico (1 fix por prompt, diff
> mínimo, validación visual previa).

| Archivo | Líneas |
|---|---|
| `frontend/src/components/dashboard/Dashboard.tsx` | 1177 |
| `frontend/src/pages/ScriptDesigner.tsx` | 967 |
| `backend/app/services/jtl/jtl_parser.py` | 511 |
| `backend/app/services/engine/virtual_user.py` | 194 |
| `backend/app/services/export/report_generator.py` | 1148 |
| `backend/app/services/engine/` (carpeta completa) | — motor propio |

**NO refactorizar sin autorización explícita de Fredy.**

---

## 12. VARIABLES DE ENTORNO

Lectas desde `os.environ` / `os.getenv` y desde `.env` (vía
`python-dotenv` y `pydantic-settings`).

### Backend
| Variable | Default | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_db` | Conexión PG |
| `POSTGRES_USER` | `jmeter_user` | DB user |
| `POSTGRES_PASSWORD` | `jmeter_secure_2024` (dev) | DB password |
| `POSTGRES_DB` | `jmeter_analyzer_db` | DB name |
| `POSTGRES_PORT` | `5432` | Puerto host |
| `SECRET_KEY` | `change-me-in-production` | JWT signing |
| `GEMINI_API_KEY` | (vacío) | Fallback si no hay config en DB |
| `GEMINI_MODEL` | `gemini-2.0-flash` (compose) / `gemini-2.5-flash` (gemini.py) | Modelo default |
| `BACKEND_PORT` | `8001` | Uvicorn port |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | CORS prod requiere lista explícita |
| `CORS_ORIGINS_DEV` | `localhost:5173,3000` | Dev override |
| `FERNET_KEY` | (auto-gen warning) | Fernet para `api_key_encrypted` / `influxdb_token_encrypted` |
| `ADMIN_DEFAULT_PASSWORD` | `sqa2024` | Password admin creado al startup |
| `ENVIRONMENT` | `development` | Habilita CORS estricto si `production` |
| `COOKIE_SECURE` | `False` | `True` en prod (HTTPS) |

### InfluxDB
| Variable | Default |
|---|---|
| `INFLUXDB_PORT` | `8086` |
| `INFLUXDB_ADMIN_USER` | `admin` |
| `INFLUXDB_ADMIN_PASSWORD` | `admin123` |
| `INFLUXDB_ORG` | `performance` |
| `INFLUXDB_BUCKET` | `jmeter` |
| `INFLUXDB_TOKEN` | `jmeter-token-2024-super-secret` |

### Grafana
| Variable | Default |
|---|---|
| `GRAFANA_PORT` | `3000` |
| `GRAFANA_ADMIN_USER` | `admin` |
| `GRAFANA_ADMIN_PASSWORD` | `admin` |
| `GF_AUTH_ANONYMOUS_ENABLED` | `true` (dev) / `false` (prod) |
| `GF_SECURITY_ALLOW_EMBEDDING` | `true` (requerido para iframe) |
| `GF_SECURITY_COOKIE_SAMESITE` | `lax` (dev) / `strict` (prod) |

### Frontend
| Variable | Default |
|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8001/api/v1` |

---

## 13. REGLAS DE DESARROLLO (NO NEGOCIABLES)

1. **NO usar `ask_user_input_v0`.**
2. **Diagnóstico read-only ANTES de cada fix.** Leer el código actual, mostrar
   el problema, luego proponer.
3. **Plan línea por línea en chat para aprobación de Fredy** antes de tocar
   código no trivial.
4. **Si la tarea afecta >3 archivos o >50 líneas → avisar antes** y dividir.
5. **NUNCA asumir, preguntar explícitamente.** Si falta información, parar
   y preguntar.
6. **1 tarea = 1 prompt atómico.** No mezclar features en un solo cambio.
7. **Fredy controla el ciclo Docker rebuild.** No hacer `docker compose
   build`/`up` sin pedirlo.
8. **`git diff` como validación estructural** antes de reportar éxito.
9. **Validación visual de Fredy = ÚNICO criterio de éxito.** No declarar
   "listo" basado en compilación/tests.
10. **NO Alembic.** Schema se crea con `Base.metadata.create_all`. Tablas
    nuevas → automáticas; columnas en tablas existentes requieren ALTER
    manual.
11. **WeasyPrint: solo table layouts, no flex/grid.** En las ramas `for_pdf`
    de `_build_att_html` y derivados.
12. **Gemini en Docker: `transport="rest"` siempre.** El gRPC default falla
    detrás del bridge network.
13. **`bcrypt==4.0.1` pinned.** `passlib==1.7.4` es incompatible con bcrypt
    5.x. **`pydyf==0.10.0` pinned.** WeasyPrint 61.2 incompatible con 0.12.x.
14. **`sanitize_ai_text()` en TODA respuesta IA** antes de persistir o
    exportar (limpia markdown que el modelo se cuela aunque el prompt lo
    prohíba).
15. **Palabras prohibidas en output IA:** `veredicto`, `hallazgo`,
    `se evidencia`, `se observa que`, `cabe destacar`,
    `es importante mencionar`, `en conclusion`. Verificadas en el
    SYSTEM_PROMPT y en `sanitize_ai_text`.
16. **React hooks SIEMPRE antes de early returns.** Cualquier `return null`
    debe ir después de TODOS los `useState`/`useEffect`/`useMemo`, o React
    cambia el orden de hooks entre renders y crashea.
17. **`rem` en PDF causa inflación 35-42% del tamaño** → usar `pt`/`mm` en
    ramas `for_pdf`. Web (HTML standalone) sí puede usar `rem`.
18. **`_strip_pdf_individual_conclusions` ANTES de
    `_strip_individual_report_extras`.** El orden inverso elimina las
    conclusiones consolidadas en vez de las individuales.

---

## 14. DEPLOY A PRODUCCIÓN

- **Servidor:** `20.81.141.77` (Azure Ubuntu).
- **Path:** `/opt/apps/jmeter-analyzer`.
- **Acceso:** SSH como `root` vía PuTTY.
- **Dominio:** `kinetix.sqasa.co`.
- **Nginx:** `/etc/nginx/sites-available/kinetix.sqasa.co`.
  - Proxy a `localhost:5173` (frontend nginx interno) y `localhost:8001`
    (backend).
- **SSL:** Let's Encrypt vía `certbot`. Renovación automática.
- **Compose:** `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`.

### Diferencias clave en servidor

- El Dockerfile del frontend usa **target: production** (stage `AS production`
  con nginx). El compose dev usa `target: builder` (Vite dev server). Este
  cambio **vive solo en el servidor** — no se ha mergeado a `main`.
- `frontend` expone `5173:80` (nginx interno escucha en 80).
- `restart: always` en todos los servicios.
- Puertos `postgres`, `influxdb`, `grafana` cerrados al host (acceso solo
  vía red interna del compose).
- CORS exacto sin wildcards; `ENVIRONMENT=production`.

### Credenciales

- **App admin (dev):** `admin` / `sqa2024` (`ADMIN_DEFAULT_PASSWORD`).
- **Postgres:** DB `jmeter_analyzer_db`, user `jmeter_user`.
- **Containers nombrados:** `jmeter_backend`, `jmeter_frontend`,
  `jmeter_postgres`, `jmeter_influxdb`, `jmeter_grafana`.

---

## 15. LECCIONES APRENDIDAS

- **Prompts grandes → regresiones.** 1 fix por prompt, atómico, con plan
  revisado por Fredy.
- **`rem` vs `pt` en PDF infla 35-42%.** Validado experimentalmente con
  WeasyPrint 61.2 + pydyf 0.10.0.
- **`margin` negativo en CSS NO extiende la caja** del contenedor padre en
  WeasyPrint — usar `@page :first { margin: 0 }` para cover full-bleed.
- **`@page :first { margin: 0 }`** es la única forma fiable de tener una
  portada que sangra al borde sin afectar las páginas internas.
- **OpenAI `max_tokens` varía por modelo** — siempre consultar
  `OPENAI_MAX_TOKENS[model_name]` con default `OPENAI_DEFAULT_MAX_TOKENS=4096`.
- **OpenAI Vision requiere formato multimodal explícito** (`content` como lista
  de partes `{"type":"text"|"image_url", ...}`), no string plano.
- **NUNCA reportar éxito sin validación visual de Fredy.** Compilación verde
  ≠ feature funcional.
- **Gemini en Docker requiere `transport="rest"`** — el default gRPC falla
  detrás del bridge network.
- **Cache de modelos live (5 min)** se invalida al guardar config: si Fredy
  cambia el provider y no ve modelos nuevos, ha pasado <5 min y vale forzar
  refresh.
- **`Base.metadata.create_all` solo CREA tablas nuevas.** Columnas añadidas
  a tablas existentes requieren `ALTER TABLE` manual o drop+recreate dev DB.
- **`withCredentials: true` + `allow_credentials=True`** son obligatorios para
  que las cookies httpOnly + CSRF funcionen — CORS con `*` no es compatible.
- **Frontend Dockerfile target:** dev usa `builder` (Vite con HMR), prod usa
  `production` (nginx con build estático). El cambio de target es manual y
  vive en el servidor.
