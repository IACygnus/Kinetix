# Sprint 2.6c — Summary Report + Aggregate Report viewers

## Objetivo
Renderers tabulares para los listeners Summary Report y Aggregate Report,
integrados en el `ListenerLiveViewer` (placeholder del 2.6b). Los datos vienen de
`listenersState.per_sampler_stats` del endpoint `/listeners-state` (2.6a).

## Componentes nuevos (`frontend/src/pages/AIScriptEditor.tsx`)

### `SummaryReportViewer` (estilo JMeter Summary Report)
- Tabla de 8 columnas: Sampler · # · Avg · Min · Max · Err % · Throughput · KB/sec.
- Fila **TOTAL** con agregados globales: avg ponderado por count, min/max globales,
  suma de throughput y KB/s, error % global.
- Footer con total de samples y samplers únicos.
- Estado vacío: "Esperando samples del JTL…".

### `AggregateReportViewer` (métricas completas)
- Tabla de 14 columnas: Sampler · # · Avg · Median · 90% · 95% · 99% · Min · Max ·
  Std Dev · Err % · TPS · KB recv/s · KB sent/s.
- p95 resaltado (font-semibold); Err % en rojo cuando > 0.
- Footer con total de samples y samplers únicos.

## Integración
El body de `ListenerLiveViewer` ahora despacha por `listenerKind`:
- `summary_report` → `SummaryReportViewer`.
- `aggregate_report` → `AggregateReportViewer`.
- Resto de kinds → placeholder existente "Renderer en construcción" (2.6d-g).

El header del viewer (badges "Actualizando cada 2s" / "Datos congelados") y los
estados de loading/sin-datos se conservan del 2.6b.

## Notas de implementación
- **Variantes "with CSV" no existen en el frontend**: el tipo `ListenerKind`
  del frontend (`aiScriptStructure.ts`) solo define `summary_report` y
  `aggregate_report` (sin sufijos `_with_csv`). Por eso las condiciones son
  igualdad simple, no `includes([...,'..._with_csv'])`. Si en el futuro el parser
  introduce esas variantes, basta extender las condiciones.
- **Fix sobre el borrador**: `tsconfig` tiene `noUnusedLocals` y
  `noUnusedParameters` en `true`. El `SummaryReportViewer` del borrador
  destructuraba `totalSamples` sin usarlo → habría roto `tsc`. Se resolvió
  añadiéndole un footer que consume `totalSamples` (consistente con el de
  Aggregate), en vez de eliminar la prop.
- Las funciones se declaran tras `ListenerLiveViewer`; por hoisting de
  `function`, están disponibles para el dispatch sin problema de orden.
- Import de `SamplerStats` añadido al bloque de tipos desde `../services/api`.

## Validación
- `tsc --noEmit`: **EXIT=0**.
- `SummaryReportViewer`/`AggregateReportViewer` definidos (líneas 2694 / 2806) y
  usados en el dispatch (líneas 2625 / 2633).
- Líneas: `AIScriptEditor.tsx` 6084 → 6293 (+209).

## Backup
`AIScriptEditor.tsx.bak_26c_20260603_151043`.

## NO incluido (próximos sub-sprints)
- View Results Tree (2.6d), gráficas jp@gc (2.6e-f), Backend Listener (2.6g).

## Estado: LISTO para Sprint 2.6d (View Results Tree).
```