# Sprint 2.6e — jp@gc Response Times Over Time + Response Codes per Second

## Objetivo
Renderers de gráficas jp@gc usando Recharts, consumiendo `state.time_buckets`
del endpoint `/listeners-state` (2.6a). Integrados en `ListenerLiveViewer`.

## Imports nuevos (Recharts)
La línea de import existente (`LineChart, Line, XAxis, YAxis, Tooltip,
ResponsiveContainer`) se expandió a un bloque con `AreaChart`, `Area`, `Legend`,
`CartesianGrid` añadidos. Sigue siendo un único `from 'recharts'`.
Además se importó el tipo `TimeBucket` desde `../services/api`.

## Helpers compartidos para gráficas
- `bucketsToResponseTimeSeries(buckets)` → `[{ time, [sampler]: avg_ms, ... }]`.
- `bucketsToCodesPerSecondSeries(buckets)` → `[{ time, "200": count, ... }]`.
- `uniqueSamplersFromBuckets` / `uniqueCodesFromBuckets` (códigos ordenados
  2xx → 3xx → 4xx → 5xx por primer dígito).
- `CHART_COLORS` paleta cíclica (10 colores).
- `colorForCode` (emerald 2xx / blue 3xx / amber 4xx / red 5xx / gray otros).

## Componentes nuevos (`frontend/src/pages/AIScriptEditor.tsx`)

### `ResponseTimesOverTimeViewer` (LineChart)
- Una línea `monotone` por sampler (color de `CHART_COLORS` cíclico), eje X
  numérico = tiempo (s, `bucket_start_sec`), eje Y = response time avg (ms).
- `CartesianGrid`, `Legend`, `Tooltip` con `labelFormatter` (`t = Ns`) y formato
  de valor en ms. `dot={false}`, `isAnimationActive={false}` (live, sin animación).
- Footer con conteo de buckets y samplers.

### `ResponseCodesPerSecondViewer` (AreaChart apilado)
- Un `Area` por código HTTP, `stackId="1"` (apilado), color por familia
  (`colorForCode`), `fillOpacity 0.6`. Eje Y = samples/intervalo.
- `Tooltip` con `Código {n}`. Footer lista los códigos detectados.

Ambos: estado vacío "Esperando datos para graficar…" cuando no hay buckets.
Datos provienen de `b.per_sampler[label].avg_response_ms` y `b.totals.codes`
respectivamente (shape `TimeBucket` confirmado en diagnóstico).

## Integración
`ListenerLiveViewer` despacha:
- `kg_apc_response_times_over_time` → `ResponseTimesOverTimeViewer`.
- `kg_apc_response_codes_per_second` → `ResponseCodesPerSecondViewer`.
Exclusión del placeholder extendida a los 5 kinds ya cubiertos.

## Notas
- Props verificadas contra `noUnusedLocals`/`noUnusedParameters`: `timeBuckets`
  se usa en ambos componentes; todos los helpers se referencian.
- Recharts ya estaba instalado y usado (HF13 mini-chart) — sin cambios de deps.

## Validación
- `tsc --noEmit`: **EXIT=0**.
- `from 'recharts'` en un único bloque de import (línea 39).
- Componentes definidos (líneas 3322 / 3394) y usados en el dispatch (2653 / 2658).
- Líneas: `AIScriptEditor.tsx` 6643 → 6879 (+236).

## Backup
`AIScriptEditor.tsx.bak_26e_20260603_153151`.

## NO incluido (próximos sub-sprints)
- jp@gc TPS + Active Threads Over Time + Response Time Graph nativo (2.6f).
- Backend Listener (2.6g).

## Estado: LISTO para Sprint 2.6f (jp@gc TPS + Active Threads + Response Time Graph).
```