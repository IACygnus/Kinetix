# Sprint 2.6f — jp@gc TPS + Active Threads + Response Time Graph

## Objetivo
3 renderers de gráficas adicionales, consumiendo `state.time_buckets` y reusando
helpers del 2.6e. Integrados en `ListenerLiveViewer`.

## Helpers nuevos (junto a los de 2.6e, reusan el tipo `TimeBucket`)
- `bucketsToTpsSeries(buckets)` → `[{ time, [sampler]: throughput, __total__: throughput }]`.
- `bucketsToActiveThreadsSeries(buckets)` → `[{ time, activeThreads }]` (de
  `totals.active_threads_max`).

Reusados sin duplicar: `uniqueSamplersFromBuckets`, `CHART_COLORS`.

## Componentes nuevos (`frontend/src/pages/AIScriptEditor.tsx`)

### `TransactionsPerSecondViewer` (LineChart)
- Línea **total** destacada (negra, grosor 3, clave `__total__`) + una línea
  punteada por sampler (color `CHART_COLORS` cíclico). `Legend`/`Tooltip`
  traducen `__total__` → "Total". Valores en tps con 2 decimales.

### `ActiveThreadsOverTimeViewer` (AreaChart `stepAfter`)
- Área de usuarios virtuales activos (`totals.active_threads_max`), interpolación
  `stepAfter` para reflejar los saltos discretos del ramp-up. Eje Y sin decimales.
- Footer con el pico máximo de concurrencia.

### `ResponseTimeGraphViewer` (LineChart)
- Response time promedio **total** (`totals.avg_response_ms`) vs tiempo. Una sola
  línea (sin desglose por sampler). Representa el listener nativo de JMeter.

Las 3: estado vacío "Esperando datos…", `isAnimationActive={false}` (live polling).

## Integración + corrección de kind
`ListenerLiveViewer` despacha:
- `kg_apc_transactions_per_second` → `TransactionsPerSecondViewer`.
- `kg_apc_active_threads_over_time` → `ActiveThreadsOverTimeViewer`.
- **`graph_results`** → `ResponseTimeGraphViewer`.

⚠️ **Desviación del borrador (necesaria)**: el prompt asumía el kind
`response_time_graph`, que **no existe** en el tipo `ListenerKind` del frontend
(`frontend/src/types/aiScriptStructure.ts`). Los kinds reales de gráfica nativa
son `graph_results` y `kg_apc_hits_per_second`. Además, en el catálogo interno
del editor el "Response Time Graph" nativo (RespTimeGraphVisualizer) mapea a
`schemaKind: 'other'`, que está reservado para Backend Listener (2.6g). Por eso
`ResponseTimeGraphViewer` se dispatcha sobre **`graph_results`** (el único kind de
gráfica temporal nativa aún sin renderer); usar el literal `response_time_graph`
habría sido código muerto que nunca haría match.

Exclusión del placeholder extendida a 8 kinds.

## Notas
- **No se añadieron `BarChart`/`Bar`** a los imports de Recharts: los 3
  componentes usan `LineChart`/`AreaChart`. Un import sin usar habría roto
  `noUnusedLocals`. El import sigue en un único bloque.
- Props verificadas contra `noUnusedLocals`/`noUnusedParameters`: `timeBuckets`
  usado en los 3; helpers nuevos referenciados.

## Estado de renderers del Sprint 2.6
8 / 9 kinds con renderer:
- `summary_report`, `aggregate_report` (2.6c)
- `view_results_tree` (2.6d)
- `kg_apc_response_times_over_time`, `kg_apc_response_codes_per_second` (2.6e)
- `kg_apc_transactions_per_second`, `kg_apc_active_threads_over_time`, `graph_results` (2.6f)

Pendiente: `other` (Backend Listener / InfluxDB) y `kg_apc_hits_per_second` → 2.6g.

## Validación
- `tsc --noEmit`: **EXIT=0**.
- `from 'recharts'` en un único bloque (sin `BarChart`/`Bar`).
- Componentes definidos (3509 / 3597 / 3669) y usados en el dispatch (2663 / 2668 / 2673).
- Líneas: `AIScriptEditor.tsx` 6879 → 7153 (+274).

## Backup
`AIScriptEditor.tsx.bak_26f_20260603_162227`.

## Estado: LISTO para Sprint 2.6g (Backend Listener + cierre Sprint 2.6).
```