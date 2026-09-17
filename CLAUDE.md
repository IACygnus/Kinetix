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
- **Repositorio:** Git local. Último tag publicado: **v3.1.0** — las Etapas 1 a 7
  del plan de corrección **no están etiquetadas**.
- **Ruta local de trabajo:** `C:\proyectos\Kinetix` (el proyecto se migró de PC;
  cualquier ruta anterior que aparezca en documentos viejos está obsoleta).
- **Estado del informe:** el plan de corrección contra
  `docs/ESPECIFICACION-informe.md` **v1.3** está **completo**. Etapas 2, 3 y 5
  validadas por Fredy; **5b, 6 y 7** implementadas y pendientes de validación.
  No hay Etapa 4: el plan saltó de la 3 a la 5. Estado vivo y pendientes en
  `PROJECT_STATUS.md`; deuda de despliegue en
  `docs/reporte_claude_code/53_checklist_despliegue.md` y su **versión corregida**
  en `docs/reporte_claude_code/59_handoff_despliegue_analisis.md` §4.

### 1.1 REMOTOS GIT

| Remoto | URL | Rol |
|---|---|---|
| `github` | `https://github.com/IACygnus/Kinetix.git` | **Repositorio real y ÚNICO destino de push.** |
| `azure` | `https://dev.azure.com/PlataformasSQA/COE/_git/COE` | **NO recibe commits.** |

- **`github` es el único remoto al que se pushea.** Todo commit va ahí.
- **`azure` NO recibe commits.** Su push está bloqueado **a propósito** (el
  remoto de push apunta al placeholder `NO-PUSH-USAR-COMANDO-EXPLICITO` para
  que un `git push azure` falle en vez de subir algo por error). Más adelante
  recibirá **solo una parte del producto**, no el repositorio completo.
- **No existe un remoto llamado `origin`.** Los comandos deben nombrar
  `github` explícitamente (`git push github <rama>`).
- **Todo el trabajo vive en la rama `backup-trabajo-local`.** La rama `main`
  sigue en su commit `Initial commit` y no contiene el producto.

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
- `backend`: `--workers 2`, sin `--reload`, `ENVIRONMENT=production`, sin
  defaults — todos los secretos deben venir de `.env`.
- `grafana`: `GF_AUTH_ANONYMOUS_ENABLED=false`, cookie `samesite=strict`.

> ### ⚠ El override de producción NO hace lo que su texto sugiere
>
> Verificado en la Etapa 6.6 con `docker compose -f docker-compose.yml -f
> docker-compose.prod.yml config` (solo lectura). **Compose FUSIONA las listas
> en vez de reemplazarlas**, así que:
>
> **Matiz de la Etapa 7:** Fredy comprobó desde internet que 5432, 8086, 3000 y
> 8001 **no responden** — el NSG de Azure los cierra y la protección es efectiva.
> Lo de abajo sigue siendo cierto a nivel de Docker y queda como deuda, no como
> urgencia. Y ojo con el reverso: el bind `./backend:/app` que sobrevive a la
> fusión es lo único que hoy conserva `/app/media` (las capturas de monitoreo y
> evidencias). Ver `59_handoff_despliegue_analisis.md` §4.2 y §4.5.
>
> | Lo que el archivo parece decir | Lo que la fusión produce de verdad |
> |---|---|
> | `postgres`, `influxdb`, `grafana` con `ports: []` → cerrados | **5432, 8086 y 3000 publicados en `0.0.0.0`** |
> | (el backend no se menciona) | **8001 publicado en `0.0.0.0`** |
> | `frontend` con nginx interno | `target: builder` **sobrevive**: se construye la fase de Vite |
> | `frontend: volumes: []` | el bind-mount `./frontend:/app` **sigue ahí** |
> | `frontend: ports 5173:80` | **dos** mapeos peleándose por el 5173 del host |
>
> Para cerrar un puerto hay que **publicarlo en una interfaz concreta**
> (`127.0.0.1:5432:5432`), no vaciar la lista. Detalle, consecuencias y orden de
> arreglo en `docs/reporte_claude_code/53_checklist_despliegue.md` §2 y en el
> reporte 37 (HF-3).

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
│       ├── ai_config.py                   # + reasoning_effort (ETAPA 2)
│       ├── ai_design_data_file.py
│       ├── ai_script_design.py
│       ├── attachment.py
│       ├── client.py
│       ├── client_logo.py
│       ├── data_file.py
│       ├── integrated_report.py
│       ├── monitoring.py
│       ├── performance_execution.py
│       ├── scenario.py
│       ├── script_design.py
│       ├── test.py
│       ├── transaction_analysis.py        # críticas marcadas (legacy, solo lectura)
│       ├── transaction_chart_analysis.py  # ETAPA 2 — textos del informe por transacción
│       └── user.py
├── schemas/                              # Pydantic schemas (auth, ai_config, …)
└── services/
    ├── ai/
    │   ├── gemini.py                     # GeminiAnalyzer + Fallback + analyze_image
    │   ├── estilo.py                     # ETAPA 3 — formato español, bloque de estilo, detectores
    │   ├── analysis_pipeline.py          # ETAPA 2 — orquestación de las secciones
    │   ├── transaction_analysis.py       # informe por transacción
    │   ├── transaction_report.py         # ídem
    │   ├── har_chunk_router.py
    │   ├── har_flow_analyzer.py
    │   └── jmx_chunk_assembler.py
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
    │   ├── report_generator.py           # build_pdf_html
    │   ├── seleccion.py                  # ETAPA 6 — lee ?tx= y ?capa=, filtra y valida
    │   ├── capas_html.py                 # ETAPA 6 — CSS/JS/selector del control de capas
    │   └── client_logo.py                # logo del cliente en la portada
    ├── jmx_parser.py
    ├── jtl/
    │   ├── jtl_parser.py                 # CSV + XML JTL → DataFrames
    │   └── transaction_series.py         # ETAPA 2 — las 5 series de UNA transacción
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
│   ├── common/{LoadingSpinner, ProtectedRoute, AvisoEstilo}.tsx   # AvisoEstilo: ETAPA 3 (D36)
│   ├── dashboard/
│   │   ├── AttachmentSection.tsx
│   │   ├── CapacityAnalysis.tsx
│   │   ├── ChartYAxisZoom.tsx
│   │   ├── ComparisonReport.tsx
│   │   ├── Dashboard.tsx                 # ⚠ Protegido — 1045 líneas
│   │   ├── DashboardHome.tsx
│   │   ├── ReportBody.tsx                # ETAPA 2 (D21) — el cuerpo, por ALCANCE
│   │   ├── SummaryTable.tsx              # ETAPA 2 (D15) — la tabla, por ALCANCE
│   │   ├── TransactionReportSection.tsx  # ETAPA 2 — los bloques por transacción
│   │   │                                 # ETAPA 7 (D58) — overrides del integrado
│   │   ├── ExportScopeDialog.tsx         # ETAPA 6 (D50) — ¿qué incluyo al exportar?
│   │   └── UploadJTL.tsx                 # panel de selección (ETAPA 5)
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
├── hooks/{usePDFExport, useChartLayers}.ts   # useChartLayers: ETAPA 6 (D46-D48)
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
| POST | `/extract-jtl-transactions` | Filas del panel de selección (ETAPA 5): muestras, promedio, TPS, errores |
| POST | `/validate-jtl` | Valida estructura de JTL |
| POST | `/parse-jmx` | Extrae nombres de threads del JMX |
| POST | `/upload` | **Pipeline completo**: parse JTL + 12+2 análisis IA + persistencia |
| GET | `/executions` | Histórico de ejecuciones |
| DELETE | `/executions/{id}` | Eliminar ejecución |
| GET | `/executions/{id}` | Detalle |
| GET | `/executions/{id}/charts` | Datos para Dashboard |
| PUT | `/executions/{id}/analysis` | Editar análisis IA |
| GET/PUT | `/executions/{id}/capacity` | Análisis de capacidad |

#### Informe por transacción (ETAPA 2, `upload.py`)
| Verbo | Path | Función |
|---|---|---|
| GET | `/executions/{id}/transaction-analyses` | Transacciones críticas + `report_labels` (las que TIENEN informe) |
| GET | `/executions/{id}/transaction-charts?label=` | Las 5 series de UNA transacción |
| POST | `/executions/{id}/transaction-report` | Generar el informe de una transacción |
| GET | `/executions/{id}/transaction-report?label=` | Sus secciones + `style_warnings` (ETAPA 3) |
| PUT | `/executions/{id}/transaction-report/{section}` | Editar una sección |
| GET | `/executions/{id}/transaction-reports/status` | Avance de la generación automática |

### `export` (`/executions/{id}/export`)
- GET `/executions/{id}/export/html` — HTML interactivo con Plotly
- GET `/executions/{id}/export/pdf` — PDF (WeasyPrint + matplotlib)

**Parámetros de alcance y capas (ETAPA 6).** Los dos exportadores individuales —y
**solo** ellos: el integrado queda fuera por v1.2 §6— aceptan:

| Parámetro | Efecto |
|---|---|
| *(ninguno)* | todas las transacciones y las dos capas: **el documento de siempre** |
| `?tx=` (vacío) | solo el informe general |
| `?tx=<label>&tx=<label>` | el general más esas. Un label sin análisis → **400** |
| `?capa=<idGrafica>:<promedio\|maximo>` | esa gráfica se dibuja con una sola capa |

`idGrafica` es `general\|rt` o `tx:<nombre>\|rt`, **el mismo identificador que arma
`useChartLayers.idGrafica` en el frontend**. Lo que no se entienda se ignora y esa
gráfica sale con las dos capas. Los lee `services/export/seleccion.py`, una sola
definición para las dos salidas.

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
| **`transaction_chart_analyses`** | id, execution_id, label, section, ai_analysis, generated_at, is_edited, ai_analysis_updated_at, sort_order, created_at — **ETAPA 2**: los textos del informe por transacción. `SECTIONS_GENERADAS` = `summary` + `chart_response_times/latency/error_rate/codes/tps`. Las filas viejas de `conclusions`/`recommendations` siguen ahí y **se ignoran** (D20) |
| **`transaction_analyses`** | id, execution_id, label, is_critical, marked_by (ai/user), metrics_json, ai_analysis, ai_analysis_updated_at, sort_order, created_at — transacciones marcadas como críticas. **Legacy de solo lectura desde N3.4**: `ai_analysis` ya no se pinta en ninguna salida |
| **`client_logos`** | logo del cliente para la portada |
| **`ai_script_designs`** · **`ai_design_data_files`** | AI Script Designer |

**Columna añadida sin Alembic:** `ai_config.reasoning_effort VARCHAR(20)`
(`docs/sql/etapa2_reasoning_effort.sql`, idempotente). Aplicada en desarrollo,
**pendiente en producción**.

---

## 6. SISTEMA DE IA

### Modelo activo

- **Provider `openai`, modelo `gpt-5.5`.** Es el modelo en uso y es una
  **decisión de Fredy**: no se propone ni se sugiere volver a modelos
  anteriores (gpt-4o, gpt-4.1, gemini-*) en ningún diagnóstico ni refactor.
  Si un fallo parece del modelo, se investiga la causa real — no se degrada
  el modelo como atajo.
- **`reasoning_effort`** (`ai_config.reasoning_effort`: `low` / `medium` /
  `high`, `NULL` = `low`) se añadió en la Etapa 2 y **solo se envía a los
  modelos de OpenAI que lo soportan**. La columna se aplica con
  `docs/sql/etapa2_reasoning_effort.sql` (regla 10: sin Alembic).
  **Aplicada en desarrollo, PENDIENTE en producción** — sin ella la lectura de
  `ai_config` falla, el error se degrada a un `warning` y **todos los informes
  salen con texto de `FallbackAnalyzer` sin avisar**.
- **Timeouts y reintentos** (Etapa 1): `CLIENTE_TIMEOUT_S = 120.0` en el cliente
  OpenAI —el SDK trae 600 s de lectura por defecto— y reintento de errores
  transitorios a los 2 s y 4 s.

### `backend/app/services/ai/estilo.py` (480 líneas — ETAPA 3)

Un solo módulo para las cinco piezas que comparten los **19 prompts** del informe:

1. **Formato español determinista** (`num`, `pct`, `ms`, `tiempo`, `veces`). Los
   bloques de datos se le entregan al modelo **ya formateados**.
2. **Frases de percentil** (`percentil_frase`, `mediana_frase`): "1 de cada 10
   usuarios espera más de 3,5 segundos (P90: 3.515 ms)".
3. **El bloque de estilo único** (`BLOQUE_ESTILO`, `PERMISO_VEREDICTO`,
   `REFERENCIA_ESTILO`), que viaja **una sola vez** por petición. Sustituyó a
   `STYLE_REMINDER`, `UX_RULE` y `FORMATO_NUMERICO`, que se solapaban y no
   llegaban a los mismos prompts.
4. **El detector de estilo** (`detectar_estilo`, `terminos_de`).
5. **La trazabilidad de cifras** (`trazar_cifras`).

Los dos detectores **solo detectan y reportan**: no regeneran, no reescriben, no
bloquean y no llaman a la IA. Son deterministas. Lo que encuentran sale como
aviso ámbar en pantalla (`AvisoEstilo.tsx`), nunca como corrección automática.

### `backend/app/services/ai/gemini.py` (2043 líneas)

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
  3. Las secciones del informe general, de forma **secuencial**, con
     `sanitize_ai_text()` aplicado a cada salida y el bloque de estilo de
     `estilo.py` en el prompt. **Throughput Over Time ya no se pide** (D19) y
     "Response Time Over Time" tampoco.
  4. `compute_verdict()` (cumple/no cumple acceptance criteria).
  5. `compute_per_transaction_verdicts()` (KNX-09).
  6. `update_ai_usage_in_db()` para sincronizar contadores.
  7. Los informes por transacción se generan aparte, **6 secciones cada uno**
     (resumen + 5 gráficas), con su propio sondeo de estado
     (`/transaction-reports/status`). **Sin conclusiones ni recomendaciones por
     transacción** (D20).

> **Tiempo de generación (v1.2 §5):** el informe tardaba ~40 s y hoy tarda más de
> 5 minutos con `gpt-5.5`. Retirar Throughput ahorra 1 llamada por informe y
> quitar las conclusiones por transacción ahorra 2 por transacción; **agrupar
> llamadas sigue sin medir**. El modelo no se degrada como atajo.

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

### Estructura del informe (v1.2 §1) — la misma en las CUATRO salidas

```
PORTADA
INFORME GENERAL
  Tabla resumen por transacción (todas) + su análisis
  Response Times · Latency · Error Rate · Response Codes · TPS · Active Threads
  (cada gráfica con su análisis)
[nombre de la transacción 1]        ← página nueva en el PDF
  Tabla resumen filtrada + su análisis
  Las mismas gráficas MENOS Active Threads (los hilos son de toda la prueba)
[nombre de la transacción 2]
  …
CONCLUSIONES Y RECOMENDACIONES      ← una sola vez, de toda la prueba
```

- **No existe "mini-informe".** El título de cada informe por transacción es el
  nombre de la transacción, y nada más.
- **"Throughput Over Time" salió del producto entero** (v1.2 §1.2). El escalar
  `throughput` (req/s) del KPI y de la tabla resumen **NO** se tocó.
- **"Response Time Over Time"** (promedio agregado) también salió: la fuente de
  verdad es "Response Times por Transacción" con su serie dual promedio/máximo.
- El bloque **"Análisis por Transacción Crítica"** se retiró en el HF-4 de las
  cuatro salidas; su función se borró en la Etapa 6.5.
- **Las conclusiones y recomendaciones por transacción no existen**: van una sola
  vez, al final, sobre toda la prueba.

**Control de capas (ETAPA 6, v1.2 §3).** "Response Times" es la **única** gráfica
con serie dual (promedio sólido, máximo punteado, sufijo `' (max)'` en los dos
lados del código). Lleva un selector "Ambas · Promedio · Máximo" en pantalla, en
el HTML exportado y —vía `?capa=`— en el PDF. Ninguna otra gráfica lo lleva. En
pantalla el tooltip pliega el máximo dentro de la fila de su promedio:
`Auth  405 ms (máx. 414 ms)`.

### `backend/app/services/export/report_generator.py` (1103 líneas)

Módulo central que comparte generación de gráficas (matplotlib → base64) y
construcción de HTML para el exportador PDF.

- **`build_pdf_html(...)`** — produce HTML optimizado para WeasyPrint:
  - Cover page full-bleed con `@page :first { margin: 0 }`.
  - `@page` rules con `@bottom-right` para paginación.
  - Tablas y media queries en `mm`/`pt` (NUNCA `rem` — infla 35-42% en PDF).
  - Solo layouts en `table`, **no flex/grid** (WeasyPrint los procesa mal).
  - Headers navy `#0a1628`, cajas IA naranja `#fff7ed`.
  - Accent **Indigo `#4f46e5`** (estándar visual SQA).
- **Helpers compartidos:** `chart_area()`, `chart_multiline()`, `chart_pie()`
  retornan imágenes base64 listas para `<img src="data:image/png;base64,...">`.
- **`chart_multiline(..., dual_max=True, capa=…)`** — `capa` acepta `'ambas'`
  (por defecto, el gráfico de siempre), `'promedio'` o `'maximo'`. Con `'maximo'`
  la serie punteada **toma el nombre de su promedio** en la leyenda: si no, el
  gráfico saldría sin leyenda y no habría forma de saber qué transacción es cada
  línea. El color se asigna siempre, aunque la serie no se dibuje.
- **`report_body_html` / `transaction_reports_html`** — el MISMO render pinta el
  informe general y el de cada transacción (ETAPA 2, D21).
- **`BODY_CHARTS`** es la lista única de gráficas del cuerpo, con las dos formas
  de nombrar cada una. Su gemela en el HTML es `HTML_BODY_CHARTS`
  (`export_html.py`): misma idea, otro motor de gráficas.

### `backend/app/api/v1/endpoints/export_html.py`

- `GET /executions/{id}/export/html` — HTML interactivo con **Plotly** (CDN)
  generado en el browser; descargable como archivo único.

### `backend/app/api/v1/endpoints/export_pdf.py`

- `GET /executions/{id}/export/pdf` — WeasyPrint + matplotlib renderiza PDF
  desde el HTML de `build_pdf_html()`.

### `backend/app/api/v1/endpoints/integrated_report.py` (2236 líneas)

Reporte integrado con drag-and-drop: combina secciones de varios reportes en
un único documento.

> **No pasa por los endpoints individuales**: construye sus bloques por
> transacción llamando en proceso a `_build_transaction_reports` (PDF) y
> `build_transaction_reports_plotly` (HTML). Por eso el **selector de
> exportación no aplica aquí** (v1.3 §6), aunque sí hereda el control de capas
> del HTML, porque comparte `_bloque_grafica_html`.

### ETAPA 7 — el integrado, completo

- **La pantalla muestra lo mismo que el informe individual** (D57). Monta
  `DashboardEmbed` → `Dashboard embedded={true}`, que ahora **sí** renderiza
  `TransactionReportSection`. Las otras guardas `!embedded` de `Dashboard.tsx` se
  quedan: las conclusiones por ejecución las consolida el integrado (v1.3 §0), y
  los botones de exportar y el autoguardado son de la pantalla individual.
- **Editar dentro del integrado NO toca la ejecución** (D58, regla F4). La
  edición de un análisis por transacción viaja por el canal `onAnalysisEdit` que
  ya existía y se guarda como override con clave **`tx|<label>|<section>`** en
  `integrated_reports.sections[i].overrides.analysis`, junto a las claves de
  columna. `transaction_chart_analyses` no cambia.
- **Los exportados aplican esos overrides** (D59) con `_aplicar_overrides_tx`,
  que vive **aquí y no en los constructores** de `export_pdf.py` /
  `export_html.py`: esos dos están protegidos y siguen devolviendo lo que hay en
  base. El integrado decide encima.
- **Nada se migra** (D60): un integrado sin claves `tx|` se ve con los textos
  originales. Mismo criterio que `ai_analysis_throughput`, que salió del mapa en
  la Etapa 2 y cuyos overrides siguen en la base sin pintarse.
- **El consolidado no cambia** (D61): `_section_analyses_for_prompt` itera sobre
  `_SECCION_LABEL`, que son nombres de columna, así que las claves `tx|` nunca
  entran en su prompt.

> `frontend/src/components/integrated/ExecutionReportSection.tsx` (195 líneas)
> **no lo importa nadie** desde que el integrado pasó a `DashboardEmbed`. Código
> muerto señalado en el reporte 57, no retirado.

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

## 10. JTL PARSER (`backend/app/services/jtl/jtl_parser.py` — 515 líneas, **PROTEGIDO**)

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

| Archivo | Líneas (2026-09-17) |
|---|---|
| `frontend/src/components/dashboard/Dashboard.tsx` | 1045 |
| `frontend/src/pages/ScriptDesigner.tsx` | 967 |
| `backend/app/services/jtl/jtl_parser.py` | 515 |
| `backend/app/services/engine/virtual_user.py` | 194 |
| `backend/app/services/export/report_generator.py` | 1103 |
| `backend/app/api/v1/endpoints/export_html.py` | 1416 |
| `backend/app/api/v1/endpoints/export_pdf.py` | 547 |
| `backend/app/services/engine/` (carpeta completa) | — motor propio |

**NO refactorizar sin autorización explícita de Fredy.**

### Cómo se trabajó un protegido en el plan de corrección

Las Etapas 2 a 6 tocaron varios de estos archivos con autorización explícita y
alcance escrito. El método que funcionó, por si hace falta repetirlo:

1. **Un diagnóstico read-only fija una estimación de líneas por archivo**, y una
   condición de parada: superar la estimación en más de un 50 % obliga a avisar
   antes de seguir.
2. **La lógica nueva vive en módulos nuevos, no protegidos.** `Dashboard.tsx`
   pasó de 1304 a 1045 líneas *ganando* funcionalidad, porque el cuerpo del
   informe, la tabla y el diálogo de exportación salieron a `ReportBody.tsx`,
   `SummaryTable.tsx` y `ExportScopeDialog.tsx`.
3. **Cuando el umbral se cruza, se mira qué está engordando el archivo.** En la
   Etapa 6.4, `export_html.py` se pasó por llevar dentro 25 líneas de JavaScript y
   8 de CSS; salieron a `services/export/capas_html.py` y el archivo volvió a
   entrar en presupuesto. Reporte 49.
4. **Si hay que mover código, primero una extracción pura** con equivalencia
   comprobada (condición C1), y los cambios funcionales después, en otro paso.

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
19. **Los reportes de Claude Code van SIEMPRE a `docs/reporte_claude_code/`**,
    numerados **desde `01` de forma consecutiva** (sin huecos), con **hash de
    commit y fecha en la primera línea** del archivo. **No se crean otras
    carpetas de reportes.** (`docs/reporte_bug/` y `docs/reports/` son
    históricas: se conservan, no se amplían.)
20. **`docs/ESPECIFICACION-informe.md` es la referencia única de cómo debe
    quedar el informe.** Todo cambio del informe se valida contra ese
    documento; si el cambio pedido contradice la especificación, se avisa
    antes de implementarlo. Versión vigente: **v1.3**.
21. **`sanitize_ai_text()` no basta: los textos pasan además por
    `services/ai/estilo.py`** (ETAPA 3). El bloque de estilo único viaja **una
    sola vez** por petición y los dos detectores —`detectar_estilo` y
    `trazar_cifras`— **solo detectan y reportan**: no regeneran, no reescriben,
    no bloquean y no llaman a la IA. Lo que encuentran sale como aviso ámbar en
    pantalla (`AvisoEstilo.tsx`), no como corrección automática.
22. **Las cifras se formatean en Python, no se le piden al modelo.** Los bloques
    de datos se le entregan ya en formato español (`8.600` · `0,27%` ·
    `1,1 segundos`): copiar es más fácil que reformatear.
23. **El informe por transacción es el general, filtrado — y se pinta con el
    MISMO componente.** `ReportBody.tsx` y `SummaryTable.tsx` se parametrizan por
    alcance (`{kind:'general'}` o `{kind:'transaction', label}`). No se crea una
    plantilla paralela: fue el origen del problema que la Etapa 2 vino a corregir.
24. **Cada alcance guarda en su canal (condición C2).** El informe general en
    `test_executions`; el de transacción en `transaction_chart_analyses`; el
    integrado en los `overrides` de su sección. Cualquier cambio en la edición o
    el autoguardado se valida con `cableado_c2.py` y `cableado_c2_integrado.py`.
25. **Al probar, primero mirar si el endpoint persiste.** Si persiste, se usan
    ejecuciones `E*` creadas para la prueba, nunca datos de Fredy (regla del
    reporte 38). Y se trabaja sobre informes **ya generados** siempre que se
    pueda: cada generación cuesta llamadas de IA reales.
26. **`/auth/login` está limitado a 5 intentos por 15 minutos y por IP, y los
    logins correctos TAMBIÉN consumen cupo.** Nunca reintentar en bucle: los
    scripts reutilizan la sesión de `/tmp/e2e_sesion.json`. Ver el HF-3 (reporte
    37) para lo que esto significa en producción.
27. **Para acentuar archivos desde la línea de órdenes, `perl` en modo bytes.**
    Con `-CSD` trata los bytes del argumento `-e` como Latin-1 y los vuelve a
    codificar: deja `TransacciÃ³n`. Comprobar siempre después con
    `grep -c "Ã" <archivos>`.

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

- `restart: always` en todos los servicios.
- CORS exacto sin wildcards; `ENVIRONMENT=production`.
- El frontend de producción tiene que salir de la **última fase** del
  `frontend/Dockerfile` (`FROM nginx:alpine`, **sin nombre**: no existe ningún
  stage llamado `production`) y exponer `5173:80`. El override commiteado **no lo
  consigue** — ver el aviso de §2. Que en el servidor funcione indica que alguien
  lo editó a mano allí; ese cambio no está en el repositorio.

> ### ⚠ Los puertos NO están cerrados
>
> `postgres` (5432), `influxdb` (8086), `grafana` (3000) **y `backend` (8001)**
> quedan publicados en `0.0.0.0` tras la fusión de los dos compose. Comprobar en
> el servidor con `docker port <contenedor>` y con las reglas del NSG de Azure.
> Mientras siga así, `X-Forwarded-For` es falsificable por cualquiera que alcance
> el 8001.

### Antes de desplegar: leer el checklist

`docs/reporte_claude_code/53_checklist_despliegue.md` reúne toda la deuda
operativa de las Etapas 1 a 6. Lo bloqueante, en orden:

1. `docs/sql/etapa2_reasoning_effort.sql` en la base del servidor. **Sin esa
   columna los informes salen en modo respaldo y no avisan.**
2. Arreglar los puertos y el `target` del frontend en `docker-compose.prod.yml`,
   verificando con `docker compose … config`.
3. `up -d --build`: las Etapas 2, 3, 5 y 6 cambian backend **y** frontend.
4. HF-3 (reporte 37) si el despliegue es multiusuario: hoy **cinco entradas en
   quince minutos dejan a toda la plataforma sin acceso**.

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
- **Frontend Dockerfile:** dev usa `target: builder` (Vite con HMR); producción
  necesita la **última fase**, `FROM nginx:alpine`, que **no tiene nombre** (no
  existe ningún stage `production`). El `docker-compose.prod.yml` commiteado no
  la selecciona — ver el aviso de §2.
- **Compose FUSIONA las listas, no las reemplaza.** `ports: []` y `volumes: []`
  en un override **no borran nada**. Para cerrar un puerto hay que publicarlo en
  una interfaz concreta (`127.0.0.1:5432:5432`). Verificar siempre con
  `docker compose -f a.yml -f b.yml config` antes de creerse un override.

### Del plan de corrección (Etapas 1-6)

- **En desarrollo NO hace falta rebuild**: el backend corre `uvicorn --reload`
  con `./backend` montado y el frontend es el dev server de Vite con `./frontend`
  montado. Basta **Ctrl + Shift + R**. En el servidor **sí** hace falta.
- **Una plantilla paralela siempre acaba divergiendo.** El informe por
  transacción tenía la suya y por eso no se parecía al general; se arregló
  parametrizando por *alcance* el MISMO componente. Vale igual en el backend:
  `seleccion.py` y `capas_html.py` existen para que PDF y HTML no puedan
  interpretar distinto el mismo parámetro.
- **Meter JavaScript y CSS dentro de un endpoint lo engorda sin que se note.**
  Si un archivo protegido se pasa de presupuesto, mirar primero *qué* lo está
  engordando: en la Etapa 6 la respuesta era texto de JS y CSS, y sacarlo a un
  módulo resolvió las dos cosas a la vez.
- **Contar lo que se ve, no lo que se supone.** Las pruebas cuentan trazos del
  SVG y comparan los PNG del PDF byte a byte. Tres comprobaciones de la Etapa 6
  pasaban sin mirar nada: una buscaba una cadena que era un comentario HTML, otra
  leía `inner_text` de nodos SVG (siempre vacío) y otra usaba una clave de
  diccionario no única.
- **Los scripts de prueba también dependen del producto.** Al acentuar los
  títulos hubo que actualizar `hf4_check.py`, que los comparaba sin tilde.
- **`perl -CSD` destroza el UTF-8** al sustituir desde la línea de órdenes: modo
  bytes, y `grep -c "Ã"` después.
