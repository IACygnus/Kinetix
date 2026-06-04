# Sprint 2.5c.1 — Listeners + Data Files + Smoke configurable

**Fecha:** 2026-06-02
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** ✅ tres correcciones implementadas; tests 91 colectados (90 pass + 1 slow deselected); tsc EXIT=0; round-trip jp@gc OK; columnas DB creadas.

---

## Resumen

Tarea unificada con tres correcciones detectadas en validación:

1. **HF7.B.1** — listeners ampliados de 5 a 11 tipos (incluyendo las 4 gráficas jp@gc que Fredy usa en pruebas reales + 2 variantes "with CSV").
2. **HF2.1** — refactor Data Files ↔ CSV Data Set: al subir un CSV con variables declaradas se autocrea un CSV Data Set en la estructura, con path portable `${Data}/<archivo>` y resolución en runtime para el smoke.
3. **2.5c.1** — smoke test configurable (1-20 usuarios, 1-5 loops) con resolución de `${Data}` al path real del container.

**Backups creados** (timestamp `20260602_101552`, sufijo `.bak_25c1_`): los 8 archivos modificados.

---

## HF7.B.1 — Listeners 5 → 11

### Tipos soportados

| listener_kind | guiclass / tag | schema_kind |
|---|---|---|
| view_results_tree | ViewResultsFullVisualizer / ResultCollector | view_results_tree |
| view_results_tree_with_csv | ViewResultsFullVisualizer (+filename .csv) | view_results_tree |
| summary_report | SummaryReport | summary_report |
| aggregate_report | StatVisualizer ("Informe Agregado") | aggregate_report |
| aggregate_report_with_csv | StatVisualizer (+filename .jtl) | aggregate_report |
| response_time_graph | RespTimeGraphVisualizer | other |
| jpgc_response_times_over_time | ResponseTimesOverTimeGui / CorrectedResultCollector | kg_apc_response_times_over_time |
| jpgc_response_codes_per_second | ResponseCodesPerSecondGui / CorrectedResultCollector | kg_apc_response_codes_per_second |
| jpgc_transactions_per_second | TransactionsPerSecondGui / CorrectedResultCollector | kg_apc_transactions_per_second |
| jpgc_active_threads_over_time | ThreadsStateOverTimeGui / CorrectedResultCollector | kg_apc_active_threads_over_time |
| backend_listener | BackendListenerGui / BackendListener | other |

### Backend
- `refine_operations_applier.py`:
  - `LISTENER_KIND_DEFAULTS` extendido a 11 entradas (cada una conserva `schema_kind`, los jp@gc añaden `interval_grouping`, los `*_with_csv` añaden `with_filename` + `default_filename_pattern`).
  - Nuevo helper `_corrected_result_collector_raw_xml(guiclass, name, interval, filename)` para las gráficas jp@gc (`kg.apc.jmeter.vizualizers.CorrectedResultCollector` con SaveConfig completo + interval_grouping + props de gráfica).
  - `_result_collector_raw_xml` ahora acepta `filename` (antes hardcodeaba vacío).
  - `_build_listener_raw_xml` despacha jp@gc vs ResultCollector estándar y propaga filename.
  - Nuevo `_resolve_listener_filename(op, defaults)` (op.filename → default pattern → vacío).
  - `_apply_add_listener` resuelve filename y lo escribe también en `ListenerModel.filename`.
- `refine_operations.py`: `AddListenerOp.listener_kind` Literal → 11 tipos; nuevo campo opcional `filename`.

### Frontend (`AIScriptEditor.tsx`)
- `AddElementModal`: el `<select>` de listeners se reorganiza en 3 `<optgroup>` (Resultados / Gráficas jp@gc / Otros) con los 11 tipos.
- El builder client-side de `raw_xml` (réplica del applier Python) se extiende: mapa `defaults` con 11 entradas (incluye `interval`/`filenamePattern`), rama nueva para `kg.apc...CorrectedResultCollector` y soporte de filename en los ResultCollector.

---

## HF2.1 — Data Files ↔ CSV Data Set

### Arquitectura
- Subir CSV **con variables declaradas** → el backend:
  1. parsea `current_jmx`,
  2. asegura UDV `Data` = `/app/uploads/ai_data_files/{design_id}` (resoluble en runtime),
  3. crea `CSVDataSetModel` con `filename=${Data}/<archivo>` (portable) y `variable_names=<declaradas>`,
  4. regenera el JMX y lo guarda en `design.current_jmx`,
  5. vincula `data_file.linked_csv_dataset_id` al id del nuevo CSV Data Set.
- En **smoke**, `${Data}` se reescribe al path real del container (ver 2.5c.1). En **descarga**, se mantiene `${Data}` portable.

### Columnas nuevas (modelo `ai_design_data_files`)
| Columna | Tipo | Uso |
|---|---|---|
| `linked_csv_dataset_id` | VARCHAR(50) NULL | id del CSV Data Set autocreado (trazabilidad) |
| `variable_names_declared` | JSONB DEFAULT '[]' | variables declaradas por el usuario |

> **NOTA (regla #10 del proyecto):** `Base.metadata.create_all` solo crea tablas nuevas, no altera existentes. La tabla `ai_design_data_files` ya existía, por lo que se ejecutó **ALTER manual** en la DB dev (ver Validaciones §3). En cualquier entorno nuevo donde la tabla aún no exista, las columnas se crean automáticamente.

### Backend (`ai_design_data_files.py`)
- `upload_data_file`: nuevo Form `variable_names`; captura el `design` (antes se descartaba); persiste `variable_names_declared`; si hay variables, llama (best-effort, no aborta el upload) a `_autocreate_csv_dataset_in_structure`.
- Nuevo `_autocreate_csv_dataset_in_structure(...)` con la lógica de los 5 pasos. No persiste por sí mismo (el caller hace commit).

### Frontend
- `api.ts`: `aiDesignDataFilesAPI.upload(...)` acepta un 6º parámetro opcional `variableNames` (se envía como `variable_names`).
- `AIScriptEditor.tsx`:
  - `DataFilesPanel`: nuevo input "Nombres de variables JMeter (separadas por coma)" + estado `variableNames`. Al subir con variables, tras `onReload()` llama `onReloadStructure()` para refrescar el árbol (donde apareció el CSV Data Set).
  - Nuevo callback `reloadStructure()` en el componente principal (re-fetch design + re-parse JMX), propagado por `DetailPanel` → `DataFilesPanel`.

---

## 2.5c.1 — Smoke configurable

### Backend
- `jmeter_runner.py` — `patch_jmx_for_smoke(jmx, num_threads=1, loops=1, data_dir_resolver=None)`:
  - Valida rangos: `num_threads` 1-20, `loops` 1-5 → `ValueError` si fuera de rango.
  - `ThreadGroup.num_threads` y `LoopController.loops` usan los parámetros (antes literales `"1"`); ramp_time sigue en 1, scheduler off.
  - `data_dir_resolver`: reescribe el `Argument.value` de las UDVs indicadas (ej. `{'Data': '/app/uploads/ai_data_files/<id>'}`).
  - Defaults sin args = comportamiento 2.5b (1 user / 1 loop) → compat total.
- `script_ai.py` — endpoint `POST /designs/{id}/smoke-test`:
  - Nuevos Query params `num_threads` (1-20) y `loops` (1-5).
  - Construye `data_dir_resolver = {"Data": "/app/uploads/ai_data_files/{design.id}"}` y lo pasa al patch.
  - Log incluye threads/loops.

### Frontend
- `api.ts`: `smokeTestAPI.run(designId, { numThreads, loops, timeoutSec })` (firma con opciones; envía `num_threads`/`loops`/`timeout_sec`).
- `AIScriptEditor.tsx`:
  - Estado `smokeConfig { numThreads, loops }`.
  - `runSmokeTest(config)` parametrizado.
  - **Eliminado** el `useEffect` de auto-ejecución al abrir el modal.
  - `SmokeTestModal`: panel de configuración (inputs 1-20 / 1-5 + botón "Ejecutar smoke test") visible cuando no hay running/result/error. "Reintentar" reusa `smokeConfig`.

---

## Tests

| Archivo | Antes | Después | Nuevos |
|---|---|---|---|
| `test_refine_operations.py` | — | +5 | jpgc_response_times, jpgc_transactions_per_second, with_csv_filename_custom, with_csv_default_pattern, jpgc_round_trip |
| `test_jmeter_runner.py` | — | +4 | num_threads_configurable, default_sigue_uno, rechaza_fuera_de_rango, data_dir_resolver_reescribe_udv |

**Resultado:** `pytest tests/ -m "not slow"` → **90 passed, 1 deselected** (el test slow de JMeter subprocess real). Colectados: 91 (antes 82). 0 regresiones.

---

## Round-trip jp@gc

`apply_operations` con los 4 listeners jp@gc → `regenerate_jmx_from_structure` → re-parse:
- Los 4 guiclasses presentes en el JMX regenerado (`ResponseTimesOverTimeGui`, `ResponseCodesPerSecondGui`, `TransactionsPerSecondGui`, `ThreadsStateOverTimeGui`).
- `CorrectedResultCollector` presente.
- 10 listeners tras re-parse (6 del fixture + 4 nuevos). **ROUND-TRIP COMPLETO ✅**

---

## Validaciones

1. **Backend:** `docker exec -w /app jmeter_backend python -m pytest tests/ -m "not slow" -q` → 90 passed, 1 deselected.
2. **Frontend:** `tsc --noEmit` → **EXIT=0**.
3. **Columnas DB:** modelo OK + ALTER ejecutado en Postgres dev:
   ```sql
   ALTER TABLE ai_design_data_files ADD COLUMN IF NOT EXISTS linked_csv_dataset_id VARCHAR(50);
   ALTER TABLE ai_design_data_files ADD COLUMN IF NOT EXISTS variable_names_declared JSONB DEFAULT '[]'::jsonb;
   ```
   Verificado con `\d ai_design_data_files`.
4. **Imports endpoints** modificados: OK.
5. **No rebuild Docker.** Backend está volumen-montado (`./backend:/app`); frontend recarga vía Vite.

---

## Archivos modificados (8)

| Archivo | Δ aprox |
|---|---|
| backend/app/services/engine/refine_operations_applier.py | +~120 (defaults 11 + helper jpgc + filename) |
| backend/app/schemas/refine_operations.py | +~25 (Literal 11 + filename) |
| backend/app/db/models/ai_design_data_file.py | +~16 (2 columnas) |
| backend/app/api/v1/endpoints/ai_design_data_files.py | +~80 (variable_names + autocreate) |
| backend/app/services/engine/jmeter_runner.py | +~40 (num_threads/loops/resolver) |
| backend/app/api/v1/endpoints/script_ai.py | +~14 (params + resolver) |
| frontend/src/services/api.ts | +~20 (smoke opts + upload variableNames) |
| frontend/src/pages/AIScriptEditor.tsx | +~140 (smoke config + 11 listeners + data files var) |

---

## No-regresión

- Botón **"Pedir a IA"** (HF4): intacto, sin cambios.
- Smoke test 2.5b sin args: comportamiento idéntico (1 user / 1 loop) — test `default_sigue_siendo_uno` lo cubre.
- Listeners existentes (5 originales): round-trip y nombres preservados (tests HF7.B siguen verdes).
- `_autocreate_csv_dataset_in_structure` es best-effort: si falla no rompe el upload del CSV.

---

## Estado: LISTO para Sprint 2.5d (endpoint /execute full run con metrics_collector + JTL persistido).
