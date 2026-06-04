# Sprint 2.5d.1 — Ejecución FULL (backend) + DB + background tasks

> Scope reducido por decisión del CTO. Este sprint es **solo backend de
> ejecución**. El refactor del pipeline IA (`/analyze-with-ai`) es **Sprint
> 2.5d.2**; la UI del Editor IA es **Sprint 2.5e.1**.

## Decisiones de diseño aplicadas

1. **Identidad de ejecución = `INTEGER` autoincrement** (no UUID). Se reusa el
   PK existente de `performance_executions`. El flujo hace `INSERT` →
   `flush()` para obtener el id → crea el workdir con ese id.
2. **`scenario_id` nullable**: las ejecuciones nacidas del Editor IA no tienen
   un `Scenario` asociado, así que `scenario_id` queda `NULL` y se usa
   `ai_design_id` para vincular al diseño.
3. **Polling, no WebSocket**: el frontend (2.5e.1) leerá
   `/performance-executions/{id}/live-metrics` cada ~2s. El WebSocket existente
   (`ws_metrics.py`) NO se tocó (sigue sirviendo al motor de escenarios).
4. **Backend Listener HABILITADO** en FULL (al revés del smoke) → métricas a
   InfluxDB/Grafana.

## A) ALTER DB ejecutado

```sql
ALTER TABLE performance_executions ALTER COLUMN scenario_id DROP NOT NULL;
ALTER TABLE performance_executions ADD COLUMN IF NOT EXISTS ai_design_id UUID
  REFERENCES ai_script_designs(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_performance_executions_ai_design_id
  ON performance_executions(ai_design_id);
```

Verificado: `scenario_id` ahora nullable, `ai_design_id uuid` presente, índice
y FK creados.

## B) Modelo modificado

`backend/app/db/models/performance_execution.py`:
- `scenario_id`: `nullable=False` → `nullable=True`.
- Nueva columna `ai_design_id = Column(UUID(as_uuid=False),
  ForeignKey("ai_script_designs.id", ondelete="SET NULL"), nullable=True,
  index=True)`.

## C) Código nuevo

### `backend/app/services/engine/jmeter_runner.py` (helpers FULL)
- `prepare_full_run_jmx(jmx, data_dir_resolver, influxdb_resolver)` — NO reduce
  threads/loops; habilita `BackendListener`; `CSVDataSet.stopThread=false`;
  reescribe UDVs (`${Data}`, `${Resultados}`, InfluxDB).
- `run_jmeter_async(...)` — subprocess asíncrono (`asyncio.create_subprocess_exec`)
  con monitor de progreso cada 2s (`progress_callback`) y `pid_callback` para
  registrar el PID. Timeout duro configurable.
- `cancel_jmeter_process(pid)` — `SIGTERM` al subprocess.
- `parse_jtl_summary(jtl_path)` — métricas agregadas leyendo el JTL CSV parcial
  (samples, success/fail, throughput/s, avg ms, error %). Tolerante a archivos
  incompletos.

### `backend/app/services/engine/execution_tracker.py` (nuevo)
- `ExecutionTracker` singleton thread-safe: `register/get/update/unregister/
  all_running`, keyed por `execution_id: int`. Mantiene pid, workdir,
  `latest_metrics`, `elapsed_sec`, `status`.

### `backend/app/api/v1/endpoints/script_ai.py`
- `POST /script-designer/ai/designs/{design_id}/execute` — carga diseño + ACL,
  carga Data Files (usa `df.file_path`), INSERT+flush para id, crea
  `/app/uploads/jtl_results/{id}/`, copia CSVs con su `original_filename`,
  `prepare_full_run_jmx`, escribe JMX, COMMIT, lanza `asyncio.create_task(...)`,
  devuelve `{execution_id: int, ...}`.
- `_run_full_execution_background(...)` — actualiza status `running`→
  `completed/error/cancelled` en DB (usando `AsyncSessionLocal`), publica
  métricas en el tracker, respeta `stopping`→`cancelled`.
- `GET /script-designer/ai/designs/{design_id}/executions` — historial (int id).

### `backend/app/api/v1/endpoints/performance_executions.py`
- `GET /performance-executions/{id}/live-metrics` — tracker first, DB fallback.
- `POST /performance-executions/{id}/stop` — marca `stopping`, mata el proceso
  por PID, persiste `cancelled`.

## D) Tests: 91 → 98 PASS (+7), 2 slow deselected

`pytest tests/ -m "not slow"` → **98 passed, 2 deselected**.

Nuevos en `backend/tests/test_jmeter_runner.py`:
- `test_prepare_full_run_habilita_backend_listener`
- `test_prepare_full_run_no_modifica_num_threads`
- `test_prepare_full_run_jmx_invalido_lanza_error`
- `test_prepare_full_run_reescribe_data_resolver`
- `test_parse_jtl_summary_vacio`
- `test_parse_jtl_summary_calcula_metricas`
- `test_execution_tracker_register_and_get`

(`tsc --noEmit` EXIT=0; sin cambios de frontend este sprint.)

## E) Curl exitoso a `/execute` con design real

Diseño `0d0c7f38…` (booking 1). Flujo login → execute → stop → live-metrics →
history, todo HTTP 200:
- `execute` → `{"execution_id":22,"status":"starting",
  "execution_dir":"/app/uploads/jtl_results/22"}`
- `stop` → `{"status":"cancelled","process_signaled":true}` (el subprocess
  JMeter arrancó y recibió SIGTERM).
- DB: `id=22, scenario_id=NULL, ai_design_id=0d0c7f38…, status=cancelled`,
  rutas JTL/JMX seteadas.
- Workdir `/app/uploads/jtl_results/22/` con `test.jmx`, `result.jtl`,
  `jmeter.log`.

(Se canceló a ~1.5s para minimizar tráfico real a InfluxDB.)

## F) Endpoints nuevos registrados (4)

```
POST  /api/v1/script-designer/ai/designs/{design_id}/execute
GET   /api/v1/script-designer/ai/designs/{design_id}/executions
GET   /api/v1/performance-executions/{execution_id}/live-metrics
POST  /api/v1/performance-executions/{execution_id}/stop
```

## Backups creados

`*.bak_25d1_20260602_175627` de: `jmeter_runner.py`, `script_ai.py`,
`performance_executions.py`, `performance_execution.py` (modelo).

## Estado

**LISTO para Sprint 2.5d.2** (refactor mínimo del pipeline IA en `upload.py` →
función pública + endpoint `POST /performance-executions/{id}/analyze-with-ai`).
Luego **Sprint 2.5e.1** (UI del Editor IA: botón Ejecutar, panel live, historial).

### No tocado (según scope)
- `gemini.py` / `upload.py` (pipeline IA) → 2.5d.2.
- `AIScriptEditor.tsx` / `api.ts` (frontend) → 2.5e.1.
- `ws_metrics.py` (WebSocket existente).
