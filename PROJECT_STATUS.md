# PROJECT_STATUS — SQA Kinetix Pro

> Estado vivo del proyecto. Complemento operativo de `CLAUDE.md` (que
> documenta el "qué existe"). Aquí se registra "dónde estamos y qué falta".

---

## ESTADO ACTUAL (2026-05-22)

- **Versión publicada (último tag git):** `v3.1.0` — *high cardinality chart
  optimization*.
- **Versiones previas:** `v3.0.0` (core platform consolidation), `v1.3.0`
  (Grafana + InfluxDB).
- **Branch activa:** `main`.
- **Ambiente local:** funcional — `docker compose up -d` levanta los 5
  servicios (`jmeter_postgres`, `jmeter_backend`, `jmeter_frontend`,
  `jmeter_influxdb`, `jmeter_grafana`).
- **Producción (`kinetix.sqasa.co` @ 20.81.141.77):** sincronización
  **pendiente**. La diferencia clave (`frontend Dockerfile target: production`)
  vive solo en el servidor y no se ha mergeado a `main`.

### Cambios no commiteados a la fecha

```
M backend/app/api/v1/api.py                   (+4 lines, router AI Script Designer)
M backend/app/services/ai/gemini.py           (cambios pre-existentes)
M backend/app/services/jtl/jtl_parser.py      (cambios pre-existentes)
M frontend/src/App.tsx                        (+11 lines, ruta AI Script Designer)
M frontend/src/components/layout/Sidebar.tsx  (+11 lines, link "Diseñador IA")
?? backend/app/api/v1/endpoints/script_ai.py  (nuevo, 866 lines)
?? frontend/src/pages/AIScriptDesigner.tsx    (nuevo, 532 lines)
?? CLAUDE.md                                  (nuevo)
?? PROJECT_STATUS.md                          (este archivo)
```

---

## FEATURES COMPLETADAS

### Plataforma base
- [x] **Autenticación JWT por cookie httpOnly** — login, refresh, logout, me.
      Rate-limit 5/15min/IP. CSRF double-submit cookie. Sliding session 30 min.
- [x] **Roles:** admin, analyst, viewer (`require_role` dependency).
- [x] **Gestión de usuarios** — CRUD + toggle + reset-password.
- [x] **Clientes y asignaciones** — Client/UserClient con FK.
- [x] **Dashboard home** — `/dashboard/stats`.
- [x] **Profile** — editar perfil, cambiar password.

### Performance Testing — análisis
- [x] **Upload JTL** — soporta CSV y XML (`_is_xml_jtl` + `_parse_xml_jtl_to_df`
      con depth=1 para evitar contar samples anidados).
- [x] **Multi-JTL upload** (jtl_filenames JSON).
- [x] **Test types:** load, stress, endurance, scalability, spike, smoke.
- [x] **Redirect separation** — labels 30x identificados y separados.
- [x] **Análisis IA (12 secciones + recomendaciones + conclusiones)** — Gemini
      o OpenAI, con `FallbackAnalyzer` ante 429.
- [x] **Verdict + per-transaction verdicts** (KNX-09) vs acceptance criteria.
- [x] **Capacity analysis** (KNX-17).
- [x] **Edición manual del análisis IA** — `PUT /executions/{id}/analysis`.

### Reportes
- [x] **HTML standalone** con Plotly interactivo (offline-capable).
- [x] **PDF profesional con WeasyPrint + matplotlib** — cover full-bleed
      (`@page :first { margin: 0 }`), branding SQA, Indigo `#4f46e5`.
- [x] **Reporte comparativo** carga vs estrés con IA.
- [x] **Reporte integrado drag-and-drop** — fusiona secciones de múltiples
      reportes en uno. Persistido en `integrated_reports`.
- [x] **Análisis IA consolidado** del reporte integrado.

### Configuración de IA
- [x] **Provider switch** entre Gemini y OpenAI.
- [x] **API key encriptada** con Fernet en `ai_config`.
- [x] **Modelos live** (`/ai-config/models/live`) con cache TTL 5 min y
      fallback hardcoded.
- [x] **Test connection** desde la UI sin guardar primero.
- [x] **Límites diarios/mensuales** con auto-reset y contadores.
- [x] **Diagnóstico** `/gemini-test`.

### AI Script Designer (esta sesión)
- [x] **Generación de JMX desde prompt** (`POST /script-designer/ai/generate`).
- [x] **Refinamiento conversacional** (`POST /refine`) con historial.
- [x] **Upload de archivos** — Postman, OpenAPI/Swagger (JSON/YAML), texto.
- [x] **`POST /generate-from-file`** multipart con detector y parser específicos.
- [x] **Persistencia de archivo de referencia** entre refinamientos.
- [x] **Validación estructural** del JMX + lista de componentes.
- [x] **Descarga .jmx**.
- [x] **System prompt profesional** (10 secciones obligatorias, reglas de
      Postman/Swagger, JMeter 5.6.3).

### Script Designer original
- [x] **Editor visual** de requests con onboarding y drafts.
- [x] **Variable Manager** con scan, autocomplete, inline editor.
- [x] **Data Files** — upload CSV, columnas, mapping a variables.
- [x] **Importers:** HAR, Postman, OpenAPI, WSDL, Chrome push-pull.
- [x] **Smoke Test** + Request Runner + Run Result Panel.
- [x] **Variable Extractor Panel** con sugerencias de IA (`ai-correlate`).
- [x] **AI Debug** sobre resultados de smoke.
- [x] **Ejecución con motor propio** (Stepping Thread Group + virtual users).
- [x] **JTL/JMX persistidos** y descargables.

### Monitoreo
- [x] **Grafana embebido** vía iframe (requiere `GF_SECURITY_ALLOW_EMBEDDING=true`).
- [x] **InfluxDB 2.7** como sink de métricas live del motor propio.
- [x] **WebSocket** `/ws/executions/{id}/metrics` para Live Metrics Chart.
- [x] **MonitoringConfig** persistido con token Fernet-encriptado.

### Attachments + IA visión
- [x] **Subida de imágenes** monitoring + evidence.
- [x] **Análisis IA por imagen** con bifurcación Gemini Vision / OpenAI Vision.
- [x] **Fallback OCR** con `pytesseract` si Vision falla.
- [x] **Análisis batch** `/analyze-all-images`.
- [x] **Edición manual** del análisis por imagen.
- [x] **Análisis correlacionado** de monitoreo + evidence con datos de
      ejecución.

### Hardening de seguridad (post-Phase 5)
- [x] JWT en cookie httpOnly, **no localStorage**.
- [x] CSRF double-submit cookie + middleware.
- [x] CORS estricto en `ENVIRONMENT=production`.
- [x] `withCredentials: true` en axios.
- [x] Credenciales todas en `.env` (sin hardcodes).
- [x] `traceback` removido de respuestas de error.
- [x] Login.tsx sin credenciales visibles.

### Docker / Producción
- [x] `docker-compose.yml` con healthchecks para los 5 servicios.
- [x] `docker-compose.prod.yml` override (workers múltiples, no defaults,
      puertos cerrados, frontend nginx target).
- [x] Volúmenes nombrados, sin bind-mounts en prod.

---

## PENDIENTES

1. **Historial de informe integrado** — UI lista la tabla `integrated_reports`
   pero falta la pantalla de reapertura/edición con drag-and-drop sobre un
   reporte ya persistido.
2. **Ajuste visual de gráficas con muchas transacciones** — high cardinality
   strategy ya está en `services/export/high_cardinality_strategy.py` pero
   falta pulir la presentación final (etiquetas, leyendas, agrupación visual).
3. **HF13** — bug en parser JTL `summary_df` para archivos muy pequeños
   (pocos samples), métricas pueden quedar en `NaN` o `0` cuando la prueba
   dura segundos.
4. **R4 — Design System responsive** para resoluciones 15" y 27" simultáneas
   (Dashboard y reportes se ven apretados en 15", desbalanceados en 27").
5. **JMX export desde Script Designer original** — `POST /scripts/{id}/export-jmx`
   existe en backend pero la integración del UI requiere validación final.
6. **Deploy producción `kinetix.sqasa.co`** — sincronización pendiente del
   cambio de `frontend Dockerfile target: production` y los nuevos endpoints
   AI Script Designer.
7. **Cleanup de 294 archivos `.bak`** — `find backend frontend -name "*.bak*"`
   reporta 294. Necesita política de retención y limpieza.
8. **Rotar API key OpenAI expuesta** — alguna key fue commiteada/log en algún
   momento; rotar y purgar histórico.
9. **Integración Git push desde AI Script Designer** — guardar JMX generado
   directamente en repo del cliente con commit firmado.
10. **Commit y push de todos los cambios locales** — incluye AI Script
    Designer + ajustes de `api.py`/`App.tsx`/`Sidebar.tsx` + estos 2 archivos
    de documentación.

---

## BACKUPS DISPONIBLES

**Total archivos `.bak*`:** **294** (en `backend/` + `frontend/`).

Muestra de los más recientes (top 30):

```
backend/app/api/v1/api.py.bak_20260521_110851
backend/app/api/v1/endpoints/script_ai.py.bak_upload_20260521_112654
backend/app/services/engine/har_importer.py.bak_20260319_185917
backend/app/services/engine/openapi_importer.py.bak_20260319_185917
backend/app/services/engine/postman_importer.py.bak_20260319_142144
backend/app/services/engine/postman_importer.py.bak_20260319_185359
backend/app/services/engine/postman_importer.py.bak_20260319_195613
backend/app/services/engine/smoke_test.py.bak_20260319_232001
backend/app/services/engine/smoke_test.py.bak_20260319_233914
backend/app/services/engine/smoke_test.py.bak_20260326_123628
backend/app/services/engine/smoke_test.py.bak_hf7
backend/app/services/engine/variable_engine.py.bak_20260319_185359
backend/app/services/engine/variable_engine.py.bak_20260326_123628
backend/app/services/engine/variable_engine.py.bak_20260326_175006
backend/app/services/engine/variable_engine.py.bak_20260327_120533
backend/app/services/engine/variable_engine.py.bak_hf7
frontend/src/App.tsx.bak_20260521_111011
frontend/src/components/layout/Sidebar.tsx.bak_20260521_111011
frontend/src/components/layout/Sidebar.tsx.bak_hf3
frontend/src/components/layout/Sidebar.tsx.bak_hf4
frontend/src/pages/AIScriptDesigner.tsx.bak_upload_20260521_112654
frontend/src/pages/IntegratedReportPage.tsx.bak_hf10b_20260408_124943
frontend/src/pages/IntegratedReportPage.tsx.bak_hf9_3
frontend/src/pages/MonitoringPage.tsx.bak_hf10c2_20260408_131739
frontend/src/pages/ScriptDesigner.tsx.bak_20260327_120533
frontend/src/pages/ScriptDesigner.tsx.bak_hf3
frontend/src/pages/ScriptDesigner.tsx.bak_hf8
frontend/src/services/api.ts.bak_sprintB_20260415_131709
frontend/src/services/api.ts.bak_20260327_193933
frontend/src/services/api.ts.bak_hf2
```

Comando para listar todos:

```bash
find backend frontend -name "*.bak*" -type f | sort
```

> Política sugerida: conservar últimos 3 `.bak` por archivo, mover el resto a
> `backups/archive/` o eliminar. Decisión pendiente de Fredy.
