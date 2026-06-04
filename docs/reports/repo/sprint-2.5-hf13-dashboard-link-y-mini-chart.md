# HF13 — Cierre Sprint 2.5 (dashboard link + mini-chart + quitar Grafana)

3 correcciones detectadas en validación visual del Sprint 2.5.

## Fix 1 (CRÍTICO): dashboard_url del /analyze-with-ai

- **Síntoma:** el botón "Abrir Dashboard completo" abría `/dashboard` (la lista)
  en vez del reporte específico.
- **Root cause:** bug de URL en el **backend**, NO de routing en App.tsx. El
  endpoint construía `dashboard_url = f"/dashboard/{test_execution.id}"`, pero en
  `frontend/src/App.tsx` la ruta `/dashboard` mapea a `DashboardHome` (lista) y
  **no existe** `/dashboard/:id`. Por tanto `/dashboard/{uuid}` caía al catch-all
  `path="*"` → `<Navigate to="/dashboard" replace />` (la lista).
- **Ruta correcta ya existente:** `path="/performance/report/:executionId"` →
  `ReportWrapper` → `<Dashboard executionId=... />` (reporte completo: gráficas +
  análisis IA + verdict + recomendaciones).
- **Fix:** una línea en `performance_executions.py`:
  `dashboard_url = f"/performance/report/{test_execution.id}"`.
  **No se tocó App.tsx** (archivo crítico de routing) — la ruta correcta ya existía.

## Fix 2: Quitado el link "Abrir Grafana"

- **Razón:** no hay un dashboard de Grafana pre-configurado/provisionado para
  Kinetix todavía; el link apuntaba genéricamente a `localhost:3000`.
- Se eliminó el bloque `<a href="http://localhost:3000">…</a>` del drawer.
- **Pendiente:** sprint futuro de provisionamiento Grafana.

## Fix 3: Mini-chart de response time (placeholder hasta Sprint 2.6)

- Línea única (response time avg vs tiempo) con **recharts** (`^2.15.4`, ya
  instalado), color indigo `#4f46e5`, `isAnimationActive={false}` (sin
  temblor en cada update de 2s).
- Nuevo estado `metricsHistory`; se acumula un punto en cada tick del polling
  (`{ time: elapsed_sec, avg_response_ms }`), máximo **60 puntos** (~2 min).
- **Reset** al iniciar cada ejecución (`setMetricsHistory([])`).
- Ubicado en el drawer, debajo de los counters / tasa de error (donde estaba el
  link de Grafana). Solo se muestra con `metricsHistory.length > 1`.
- Nota visible: "Vista simplificada — listeners en vivo vendrán en Sprint 2.6".

## Archivos modificados

- `backend/app/api/v1/endpoints/performance_executions.py` (+3 / −1: comentario + 1 línea).
- `frontend/src/pages/AIScriptEditor.tsx` (~5805 → 5845, +40): import recharts,
  estado `metricsHistory`, reset + acumulación en polling, bloque Grafana
  reemplazado por el mini-chart.

## Validación

- `tsc --noEmit` → **EXIT=0**.
- Import `recharts`: **1 sola línea** (sin duplicados).
- Link Grafana: **removido** (grep sin coincidencias).
- Backend tests: **100 passed**, 2 slow deselected (sin regresiones).
- **Curl `/analyze-with-ai`** (exec real id=23) → HTTP 200, `dashboard_url`:
  `"/performance/report/53ed2005-04e2-493b-9fc7-40dac39846da"`.
- Endpoints de datos del reporte para ese id: `GET /executions/{id}` → **200**,
  `GET /executions/{id}/charts` → **200** (el reporte carga completo).

## Backups

`performance_executions.py.bak_hf13_20260603_110725`,
`AIScriptEditor.tsx.bak_hf13_20260603_110725`.

## Estado

**SPRINT 2.5 CERRADO AL 100%.** Listo para Sprint 2.6 (listeners en vivo, que
reemplazarán el mini-chart placeholder).
