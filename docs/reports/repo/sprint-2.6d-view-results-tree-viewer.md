# Sprint 2.6d — View Results Tree Viewer

## Objetivo
Renderer del listener View Results Tree: lista cronológica de samples (del campo
`samples_tail` del endpoint `/listeners-state`, últimos 100) con panel de detalle
por sample. Integrado en `ListenerLiveViewer` cuando `kind === 'view_results_tree'`.

## Componentes nuevos (`frontend/src/pages/AIScriptEditor.tsx`)

### `ViewResultsTreeViewer`
- Layout 2 paneles: lista (420px) a la izquierda + detalle a la derecha.
- **Lista**: por sample muestra icono OK/FAIL (`CheckCircle2`/`XCircle`), label,
  badge de código HTTP coloreado (2xx verde, 3xx azul, 4xx ámbar, 5xx/otros rojo),
  tiempo (`elapsed` ms) y hora local del `timeStamp` (formato `es-CO` con ms).
  Orden cronológico inverso (más reciente primero).
- **Filtros**: checkbox "Solo errores" (`success != true`), dropdown por sampler
  (labels únicos), búsqueda libre (label / responseMessage / URL / responseCode).
  Cualquier cambio de filtro resetea la selección.
- **Contador**: `N / M mostrados (cap 100)` + indicación de `total` cuando
  `total_samples_parsed > samples_tail.length`.

### `SampleDetailView` (tabs)
- **Resultado**: Estado SUCCESS/FAIL, código HTTP, mensaje, response time,
  latency, connect time, bytes recibidos/enviados. Si hay `failureMessage`,
  caja roja con el mensaje.
- **Request**: URL (`URL || url`), thread, timestamp, group/all threads, dataType,
  IdleTime.
- **Response Data**: aviso de que JMeter no guarda el body en el JTL por defecto,
  con instrucción para habilitar `saveResponseData` y la alternativa de abrir el
  JMX en JMeter desktop.

## Claves de sample consumidas (case-sensitive, del header JTL real 2.6a)
`timeStamp`, `elapsed`, `label`, `responseCode`, `responseMessage`, `threadName`,
`dataType`, `success`, `failureMessage`, `bytes`, `sentBytes`, `grpThreads`,
`allThreads`, `URL`, `Latency`, `Connect`, `IdleTime`. Todas presentes en el JTL
que genera el motor. `URL` es mayúscula en JMeter → se usa `URL || url` como fallback.

## Integración
`ListenerLiveViewer` despacha `view_results_tree` → `ViewResultsTreeViewer`. La
variante "with CSV" no existe como kind separado en el frontend y se renderizaría
con el mismo viewer. Exclusión del placeholder extendida a los 3 kinds ya cubiertos.

## Notas de implementación
- `fractionalSecondDigits` se castea con `as Intl.DateTimeFormatOptions` (puede no
  estar en los type defs base de la lib TS) — `tsc` OK.
- Props verificadas contra `noUnusedLocals`/`noUnusedParameters`: `samplesTail` y
  `totalSamplesParsed` se usan en `ViewResultsTreeViewer`; `sample` en `SampleDetailView`.
- `CheckCircle2`/`XCircle` ya estaban importados de lucide-react (sin imports nuevos).
- Funciones declaradas tras `AggregateReportViewer`; disponibles para el dispatch
  por hoisting de `function`.

## Validación
- `tsc --noEmit`: **EXIT=0**.
- `ViewResultsTreeViewer` (línea 2890) y `SampleDetailView` (3086) definidos y
  usados en el dispatch (2641) y en el detalle (3068).
- Líneas: `AIScriptEditor.tsx` 6293 → 6643 (+350).

## Backup
`AIScriptEditor.tsx.bak_26d_20260603_152351`.

## NO incluido (próximos sub-sprints)
- Gráficas jp@gc (2.6e-f), Backend Listener (2.6g).

## Estado: LISTO para Sprint 2.6e (gráficas jp@gc Response Times + Codes).
```