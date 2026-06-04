# Sprint 2.6 — Listeners en vivo (COMPLETO end-to-end)

## Resumen ejecutivo

Sprint de 7 sub-sprints (a–g) que entrega monitoreo de ejecuciones JMeter en
tiempo real desde el Editor IA. Durante una ejecución FULL, el usuario hace click
en cualquier listener del árbol y ve su vista propia, actualizándose cada 2s,
de forma análoga a JMeter desktop. Backend de parse incremental + 10 renderers
de frontend, uno por cada `ListenerKind`.

## Sub-sprints completados

### 2.6a — Backend listeners-state
- `backend/app/services/engine/listeners_state_service.py`: cache thread-safe
  por `execution_id` + parse incremental del JTL (offset byte-exacto).
- 2 endpoints: `GET /performance-executions/{id}/listeners-state`,
  `DELETE .../listeners-state-cache`.
- 10 tests nuevos.
- **2 bugs detectados y corregidos en el borrador**:
  1. `f.tell()` tras iterar `csv.reader` lanza `OSError` → el offset no avanzaba
     → se duplicaban samples en cada poll. Reescrito con lectura binaria + corte
     por último `\n`.
  2. Ejecución terminada nunca poleada en vivo → cache vacío → 0 samples al primer
     poll. Añadido `freshly_initialized` (parse completo una vez si el cache
     arranca con status terminal).

### 2.6b — Frontend routing
- **Decisión de arquitectura**: NO se tocó el árbol; el listener activo se
  **deriva** de `selected` (única fuente de verdad). Routing solo en el panel
  central. `listenersState` execution-wide → cambiar de listener no re-fetch-ea.
- Polling 2s al endpoint; cleanup del cache backend al cerrar drawer (Opción R
  híbrida); `ListenerLiveViewer` con dispatch por `listenerKind` (placeholder).
- `api.ts`: tipos `SamplerStats`/`TimeBucket`/`ListenersState` +
  `getListenersState`/`clearListenersCache`.

### 2.6c — Summary + Aggregate Report (tablas)
- `SummaryReportViewer`: 8 columnas + fila TOTAL (avg ponderado, min/max globales).
- `AggregateReportViewer`: 14 columnas (median/90/95/99, std dev, KB recv/sent).
- Fix: `noUnusedParameters` habría roto tsc por `totalSamples` sin usar → footer
  que lo consume.

### 2.6d — View Results Tree
- `ViewResultsTreeViewer`: lista 420px + `SampleDetailView` con 3 tabs
  (Resultado / Request / Response Data).
- Filtros: solo errores, por sampler, búsqueda libre. Cap 100 más recientes con
  indicación de total. Aviso de Response Data no disponible (config JMeter).

### 2.6e — Response Times Over Time + Response Codes per Second
- `ResponseTimesOverTimeViewer` (LineChart, línea por sampler).
- `ResponseCodesPerSecondViewer` (AreaChart apilado por familia de código HTTP).
- Helpers compartidos (`bucketsToResponseTimeSeries`, `uniqueSamplersFromBuckets`,
  `CHART_COLORS`, `colorForCode`, …). Recharts ampliado (Area/Legend/CartesianGrid).

### 2.6f — TPS + Active Threads + Response Time Graph
- `TransactionsPerSecondViewer` (total destacado + líneas punteadas por sampler).
- `ActiveThreadsOverTimeViewer` (AreaChart `stepAfter`, pico de concurrencia).
- `ResponseTimeGraphViewer` (línea simple del avg total).
- **Corrección de kind**: el borrador asumía `response_time_graph`, inexistente
  en `ListenerKind`. Dispatch real sobre **`graph_results`**.

### 2.6g — Backend Listener + Hits per Second + cierre
- `HitsPerSecondViewer` (hits/sec = `totals.count / bucket_size_sec`).
- `BackendListenerViewer` (caso especial sin datos de JTL: estado + config
  InfluxDB + guía Grafana + alternativas jp@gc).

## Renderers activos: 10 / 10 kinds

| Kind | Componente | Sub-sprint |
|---|---|---|
| `summary_report` | `SummaryReportViewer` | 2.6c |
| `aggregate_report` | `AggregateReportViewer` | 2.6c |
| `view_results_tree` | `ViewResultsTreeViewer` | 2.6d |
| `kg_apc_response_times_over_time` | `ResponseTimesOverTimeViewer` | 2.6e |
| `kg_apc_response_codes_per_second` | `ResponseCodesPerSecondViewer` | 2.6e |
| `kg_apc_transactions_per_second` | `TransactionsPerSecondViewer` | 2.6f |
| `kg_apc_active_threads_over_time` | `ActiveThreadsOverTimeViewer` | 2.6f |
| `graph_results` | `ResponseTimeGraphViewer` | 2.6f |
| `kg_apc_hits_per_second` | `HitsPerSecondViewer` | 2.6g |
| `other` | `BackendListenerViewer` | 2.6g |

## Métricas acumuladas (medidas)

- Backend tests: **100 → 110** (+10, todos del 2.6a).
- `AIScriptEditor.tsx`: **5,879 → 7,353** (+1,474 acumulado):
  - 2.6b +205 · 2.6c +209 · 2.6d +350 · 2.6e +236 · 2.6f +274 · 2.6g +200.
- `api.ts`: 776 → 830 (+54).
- Módulos backend nuevos: 1 (`listeners_state_service.py`).
- Endpoints nuevos: 2.
- Viewers nuevos: 10 + `SampleDetailView` + helpers de transformación.
- Bugs detectados/corregidos en desarrollo: 2 (ambos en 2.6a).

## UX flow completo

1. Editor IA → "Ejecutar" → modal → ejecutar.
2. Drawer derecho abre con métricas básicas (mini-chart HF13).
3. Click en un listener del árbol → panel central muestra su renderer.
4. Renderer se actualiza cada 2s mientras `status=running`.
5. Click en otro listener → cambia sin loading (state compartido).
6. Click en sampler/UDV/CSV → vuelve al editor estructural.
7. Ejecución completa → renderers congelados con últimos datos (badge "Datos congelados").
8. "Generar análisis IA del JTL" → dashboard completo en pestaña nueva.
9. Cierre del drawer → `DELETE /listeners-state-cache` (Opción R).

## Desviaciones del borrador documentadas
- **2.6f**: kind real `graph_results` (no `response_time_graph`).
- **2.6g**: `BackendListenerViewer` muestra config con defaults del stack, NO
  parsea `ListenerModel.raw_xml` (mejora candidata futura).

## Pendiente de validación
Criterio de éxito (regla #9): **validación visual de Fredy** de los 10 renderers
en una ejecución real. Recomendado: una ejecución con algún error (para apilado
multicolor en Response Codes) y con ramp-up (para los escalones de Active Threads).

## Estado: SPRINT 2.6 COMPLETO END-TO-END.
```