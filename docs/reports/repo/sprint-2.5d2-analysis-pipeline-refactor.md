# Sprint 2.5d.2 — Refactor pipeline IA + endpoint /analyze-with-ai

> Refactor delicado sobre `/upload` (endpoint critico de uso diario). Objetivo:
> extraer el pipeline IA inline a un modulo publico y reusarlo desde un endpoint
> nuevo, **sin cambiar el comportamiento de `/upload`**.

## Decision de diseño: dos capas (aprobada por el CTO)

La firma propuesta `run_jtl_analysis_pipeline(test_execution, jtl_path, db)` no
podia reproducir el parsing de `/upload` (deteccion de formato `jtl`/`locust`/
`wapt` + multi-archivo `JTLParser.parse_multiple`) sin cambiar su
comportamiento. Solucion en dos capas:

1. **`run_ai_and_verdict(parser, metrics, test_type, acceptance_criteria_dict,
   metric_unit, db)`** — el bloque AI (12 secciones + sintesis) + verdict, movido
   **VERBATIM** desde `upload.py`. `/upload` conserva intactos su parsing y la
   construccion de `TestExecution`; solo delega este bloque. **Delegacion pura.**
2. **`run_jtl_analysis_pipeline(test_execution, jtl_path, db, acceptance_criteria)`**
   — wrapper publico para `/analyze-with-ai`: parsea un unico JTL, popula las
   metricas basicas del `TestExecution` y mapea los 13 campos `ai_*`. Llama a la
   capa 1. NO hace commit.

Ambas capas comparten la logica IA real. El path multi-formato de `/upload`
queda intacto.

## A) Lineas movidas de upload.py al pipeline

- Bloque inline `upload.py:310–632` (`# ===== AI STATUS TRACKING =====` …
  `Verdict computed`) → movido a
  `backend/app/services/ai/analysis_pipeline.py::run_ai_and_verdict`.
- **Verificacion objetiva:** diff normalizado (sin indentacion/blancos) entre el
  bloque original (del `.bak`) y la funcion extraida → **298 lineas logicas
  IDENTICAS**. La logica IA+verdict es byte-equivalente.
- `/upload` ahora delega en ~26 lineas (llamada + desempaquetado de los 13
  `ai_*` + `ai_status`). Diff: `upload.py` −324 / +26.

## B) Funciones de gemini.py usadas (NO se modifico gemini.py)

`get_gemini_analyzer`, `load_ai_config_from_db`, `prepare_insights_for_prompt`,
`FallbackAnalyzer`, `compute_verdict`, `compute_per_transaction_verdicts`, y los
metodos **sincronos** del analyzer: `analyze_summary_table`, `analyze_errors`,
`analyze_chart` (×8 graficos), `analyze_redirects`, `generate_conclusions`,
`generate_recommendations`. Manejo de errores: el bloque AI es non-fatal (try/
except global, igual que antes); cada seccion cae a `FallbackAnalyzer` si la IA
devuelve `None`.

## C) Nuevo modulo `analysis_pipeline.py`

- `AIAnalysisResult` (dataclass) con los 13 `ai_*` + `ai_status`.
- `run_ai_and_verdict(...)` — capa compartida (verbatim).
- `run_jtl_analysis_pipeline(...)` — wrapper publico single-JTL. Popula las
  metricas basicas con el mismo mapeo que `upload.py` (incluido strip de tzinfo).

## D) Nuevo endpoint

`POST /api/v1/performance-executions/{execution_id}/analyze-with-ai`
- Valida ejecucion `completed` + JTL en disco (>100 bytes) + ACL.
- Construye un `TestExecution` (tabla del Dashboard) y corre el pipeline publico.
- **Fix Dashboard:** el endpoint de charts hace un glob NO recursivo
  (`/app/uploads/*{jtl_filename}`); el JTL de una ejecucion FULL vive en
  `/app/uploads/jtl_results/{id}/`. El endpoint copia el JTL a `/app/uploads/`
  con nombre unico `aiexec_{id}_result.jtl` y setea ese `jtl_filename`, para que
  el Dashboard (detalle **y** charts) funcione.
- Devuelve `{test_execution_id, performance_execution_id, dashboard_url, status}`.

## E) Tests: 98 → 100 PASS (+2), 2 slow deselected

`backend/tests/test_analysis_pipeline.py`:
- `test_pipeline_parsea_jtl_y_popula_metricas_basicas` — mockea Gemini (metodos
  sincronos) y `time.sleep`; verifica metricas basicas (3 samples, 1 error).
- `test_pipeline_jtl_inexistente_lanza_error`.

(El proyecto no usa pytest-asyncio → las corrutinas se corren con `asyncio.run`.)

## Verificacion critica — `/upload` sin cambios de comportamiento: SI

1. **Equivalencia logica probada:** 298 lineas logicas identicas (bloque inline
   original == funcion extraida).
2. **Construccion de `TestExecution` intacta** (mismo bloque, mismos campos).
3. **End-to-end real:** upload de un JTL (6 samples, 1 error) → **HTTP 200**
   (54s, pipeline IA completo). Persistido: `total_requests=6`, `total_errors=1`,
   `error_rate=16.67`, `avg=204ms`, `p95=418.75`, `throughput=2.4`, y
   `ai_analysis_summary` / `ai_conclusions` / `ai_recommendations` NO vacios.

## F) Curl al nuevo endpoint

- `POST /performance-executions/9001/analyze-with-ai` (fixture `completed`) →
  **HTTP 200** (~52–55s), `dashboard_url: /dashboard/{test_execution_id}`.
- Sobre el `TestExecution` resultante (sin pasos manuales):
  `GET /executions/{id}` → **200**, `GET /executions/{id}/charts` → **200**
  (Dashboard carga detalle + graficos).

## Endpoints registrados

```
POST /api/v1/performance-executions/{execution_id}/analyze-with-ai
```

## Backups

`upload.py.bak_25d2_20260602_182640`,
`performance_executions.py.bak_25d2_20260602_182640`.

## Artefactos de prueba (dejados para validacion visual)

- `performance_executions` id=9001 (fixture `completed`).
- `test_executions`: la del `/upload` (`RefactorCheck`) y las de `analyze-with-ai`
  (abrir `/dashboard/a66068d9-d52c-438f-a572-f625b0f17198` para validar el
  Dashboard end-to-end). JTLs en `/app/uploads/aiexec_9001_result.jtl` y
  `/app/uploads/jtl_results/9001/`. Se pueden limpiar cuando ya no se necesiten.

## Estado

**LISTO para Sprint 2.5e.1** (UI base del Editor IA: boton Ejecutar, panel live,
historial, y boton "Generar analisis IA" → abre `/dashboard/{id}` en pestaña
nueva).
