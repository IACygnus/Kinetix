# Sprint 2.5e.1 — UI base de ejecución

> Frontend-only. UI para lanzar y monitorear ejecuciones FULL desde el Editor IA,
> consumiendo los endpoints del Sprint 2.5d.1.

## Componentes nuevos

- **`executionAPI`** en `frontend/src/services/api.ts` (+ tipos
  `ExecutionStartResponse`, `ExecutionLiveMetrics`):
  - `start(designId, timeoutSec=3600)` → `POST /script-designer/ai/designs/{id}/execute`
  - `getLiveMetrics(executionId)` → `GET /performance-executions/{id}/live-metrics`
  - `stop(executionId)` → `POST /performance-executions/{id}/stop`
- **Botón "Ejecutar"** (morado, icono `Zap`) en el header del Editor IA, a la
  izquierda de "Probar (Smoke)". Deshabilitado sin `designId`, mientras inicia,
  o si ya hay una ejecución `running`.
- **Modal de confirmación pre-ejecución**: advertencia de que NO es smoke, que
  respeta el Thread Group, que envía métricas a InfluxDB/Grafana, y duración
  estimada. Botones Cancelar / Ejecutar ahora.
- **Drawer lateral derecho de ejecución live**: estado + tiempo transcurrido +
  métricas (samples, éxitos, errores, throughput, response time avg, tasa de
  error), link a Grafana, y botón "Detener ejecución".
- **Polling cada 2s** a `/live-metrics`; se detiene solo al alcanzar un estado
  terminal (`completed` / `cancelled` / `error`). Cleanup del intervalo al
  desmontar el componente.

## UX flujo

1. Click en **Ejecutar** → abre el modal de confirmación.
2. Click en **Ejecutar ahora** → `executionAPI.start(designId)`; se cierra el
   modal, se abre el drawer con estado `starting` y arranca el polling.
3. El drawer se actualiza cada 2s con el estado real y las métricas agregadas
   del JTL en curso.
4. Mientras está `running`, el footer muestra **Detener ejecución** →
   `executionAPI.stop()`; el polling reflejará el cambio a `cancelled`.
5. Al llegar a un estado terminal, el polling se detiene; el usuario cierra el
   drawer (la `X`), lo que limpia el estado para una próxima ejecución.

## Estados manejados (badge de color)

- `starting` (azul), `running` (morado + spinner/pulse), `completed` (verde +
  check), `error` (rojo + XCircle), `cancelled` (gris + X), `stopping` (gris).
- El botón "Detener" solo aparece en `running`.
- Banner placeholder al `completed` anticipando el botón "Generar análisis IA"
  (Sprint 2.5e.2).

## NO incluido (Sprint 2.5e.2)

- Botón "Generar análisis IA" (`/analyze-with-ai` → abrir `/dashboard/{id}` en
  pestaña nueva).
- Historial de ejecuciones del diseño.

## Validación

- `tsc --noEmit` → **EXIT=0**.
- `AIScriptEditor.tsx`: **5307 → 5588 líneas** (+281).
- `api.ts`: 655 → 702 líneas (+47).
- Imports lucide-react confirmados: `Zap`, `X`, `Loader2`, `AlertTriangle`,
  `CheckCircle2`, `XCircle` (todos presentes).

## Backups

`AIScriptEditor.tsx.bak_25e1_20260603_090205`,
`api.ts.bak_25e1_20260603_090205`.

## Estado

**LISTO para Sprint 2.5e.2** (botón "Generar análisis IA" + historial de
ejecuciones del diseño). Pendiente validación visual de Fredy.
