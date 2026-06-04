# Sprint 2.5e.2 — UI análisis IA + historial (CIERRE Sprint 2.5)

> Frontend-only. Último sub-sprint del Sprint 2.5. Cierra el flujo end-to-end:
> ejecutar → monitorear → analizar con IA → abrir el Dashboard completo.

## Componentes nuevos

- **`executionAPI.history(designId, limit)`** → `GET /script-designer/ai/designs/{id}/executions`
  (+ tipo `DesignExecutionHistoryItem`).
- **`executionAPI.analyzeWithAI(executionId)`** → `POST /performance-executions/{id}/analyze-with-ai`
  con `timeout: 120000` (el pipeline IA tarda ~50-60s) (+ tipo `AnalyzeWithAIResponse`).
- **Botón "Historial"** (icono `History`) en el header, después de "Pedir a IA".
- **Drawer del historial** (`z-40`, 480px): lista de ejecuciones con id, badge de
  estado, fecha, métricas (samples / errores+% / throughput) y mensaje de error.
  Estados: loading (spinner), vacío (call-to-action), y lista.
- **Botón "Generar análisis IA"** en el drawer live cuando `status === 'completed'`
  (reemplaza el placeholder del 2.5e.1). Spinner "~1 min" mientras corre; muestra
  error inline si falla.
- **Bloque de resultado + botón "Abrir Dashboard completo"** → `window.open(dashboard_url,
  '_blank', 'noopener,noreferrer')` (pestaña nueva; el Editor IA queda intacto).

## UX flujo completo (Sprint 2.5 end-to-end)

1. Editor IA → click **Ejecutar** → modal de confirmación → **Ejecutar ahora**.
2. Drawer live se abre; polling cada 2s; métricas actualizándose.
3. Al completarse → aparece **Generar análisis IA del JTL**.
4. Click → spinner ~1 min (llamada a `/analyze-with-ai`) → aparece **Abrir
   Dashboard completo**.
5. Click → abre `/dashboard/{test_execution_id}` en pestaña nueva.
6. El Editor IA permanece intacto en la pestaña original.
7. **Historial** (header) → drawer con todas las ejecuciones del diseño.

## Estados manejados

- Análisis IA: `analyzingAI` (spinner), `analysisResult` (bloque verde + botón
  dashboard), `analysisError` (banner rojo inline). Se resetean al cerrar el
  drawer de ejecución (extensión de `handleCloseExecutionPanel`).
- Historial: `historyLoading`, lista vacía vs poblada, badges por estado
  (completed/running/error/cancelled/otros).

## Cierre Sprint 2.5

### Sub-sprints completados (4/4)
- **2.5d.1** — Backend ejecución FULL (modelo + ALTER `ai_design_id`/`scenario_id`
  nullable, `prepare_full_run_jmx`/`run_jmeter_async`/`parse_jtl_summary`,
  `execution_tracker`, endpoints `execute` / `live-metrics` / `stop` / `executions`).
- **2.5d.2** — Pipeline IA refactorizado (`analysis_pipeline.py`:
  `run_ai_and_verdict` verbatim + `run_jtl_analysis_pipeline`) + endpoint
  `/analyze-with-ai`. `/upload` delega sin cambiar comportamiento.
- **2.5e.1** — UI base: botón "Ejecutar", modal pre-ejecución, drawer live con
  polling.
- **2.5e.2** — UI análisis IA + historial (este sprint).

### Endpoints nuevos del Sprint 2.5 (5)
```
POST /api/v1/script-designer/ai/designs/{design_id}/execute
GET  /api/v1/script-designer/ai/designs/{design_id}/executions
GET  /api/v1/performance-executions/{execution_id}/live-metrics
POST /api/v1/performance-executions/{execution_id}/stop
POST /api/v1/performance-executions/{execution_id}/analyze-with-ai
```

### Métricas acumuladas
- **Backend tests:** 91 → **100** (+9: 7 en 2.5d.1, 2 en 2.5d.2), 2 slow.
- **Frontend `AIScriptEditor.tsx`:** ~5307 → **5805** líneas (2.5e.1 +281, 2.5e.2 +217).
- **Frontend `api.ts`:** 655 → **741** líneas.
- **Módulos backend nuevos:** `execution_tracker.py`, `analysis_pipeline.py`.

## Validación

- `tsc --noEmit` → **EXIT=0**.
- `AIScriptEditor.tsx`: **5588 → 5805** (+217). `api.ts`: 702 → 741 (+39).
- Imports lucide confirmados: `History`, `Sparkles`, `ExternalLink` (+ Zap,
  XCircle, Loader2, X, AlertTriangle, CheckCircle2 de sprints previos).

## Backups

`AIScriptEditor.tsx.bak_25e2_20260603_092316`,
`api.ts.bak_25e2_20260603_092316`.

## Estado

**SPRINT 2.5 COMPLETO END-TO-END.** Listo para validación visual completa de
Fredy (ejecutar un diseño real, ver métricas live, detener, generar análisis IA
y abrir el Dashboard en pestaña nueva).
