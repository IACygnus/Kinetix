# Sprint 2.6b — Frontend routing listeners en vivo

## Objetivo
Durante una ejecución activa (drawer live abierto), al hacer click en un
**listener** del árbol del Editor IA el panel central muestra el renderer del
listener (placeholder por ahora) en vez del editor estructural. Click en
sampler/UDV/CSV/etc. → editor estructural normal. Cierre del drawer → comportamiento
normal restaurado.

## Decisión de arquitectura
El borrador proponía bifurcar el `onClick` de cada listener en el árbol +
estado `activeListenerKind/Name` separado + `handleListenerClick`. El árbol real
usa un **`onSelect` unificado** (`setSelected`) propagado por toda la cadena
`TreeView → ThreadGroupNode → TGChildNode`, con `selected: SelectedNode` como
única fuente de verdad (`{ kind: 'listener', id }`).

En vez de tocar el árbol (invasivo, múltiples niveles de props), se enruta en el
**render del panel central**:
- `activeListener` se **deriva** de `selected` + `structure.listeners`.
- `isViewingLiveListener = isInExecutionMode && activeListener !== null`.
- `listenersState` es **execution-wide** (el endpoint 2.6a devuelve todos los
  listeners), así que cambiar de listener NO requiere re-fetch ni reset.

Resultado: cero cambios al árbol, una sola fuente de verdad, menos estado.

## Componentes nuevos
### `frontend/src/services/api.ts`
- Tipos `SamplerStats`, `TimeBucket`, `ListenersState`.
- `executionAPI.getListenersState(id)` → `GET /performance-executions/{id}/listeners-state`.
- `executionAPI.clearListenersCache(id)` → `DELETE .../listeners-state-cache`.

### `frontend/src/pages/AIScriptEditor.tsx`
- Estados: `listenersState`, `listenersPollLoading`, `listenersPollIntervalRef`.
- Memos: `isInExecutionMode` (drawer abierto + ejecución), `activeListener`
  (derivado de `selected`), `isViewingLiveListener`.
- `useEffect` de polling: fetch inicial + `setInterval(2s)` SOLO si el listener
  está siendo visto y la ejecución está `running`/`starting`; si está terminada,
  un único fetch (datos congelados). Cleanup del interval en unmount/cambio.
- `handleCloseExecutionPanel`: añade `clearListenersCache(...)` (Opción R híbrida)
  + reset de `listenersState` al cerrar el drawer.
- Routing del panel central: `isViewingLiveListener` → `<ListenerLiveViewer>`,
  si no → `<DetailPanel>` (sin cambios al flujo existente).
- Componente `ListenerLiveViewer` (placeholder): header con label por kind,
  badge "Actualizando cada 2s" (running) / "Datos congelados" (completed),
  body con resumen (samples / samplers únicos / buckets) + aviso de renderer
  en construcción. Map `LISTENER_KIND_LABELS` alineado al tipo `ListenerKind`
  real del frontend (incluye `graph_results`, `kg_apc_hits_per_second`).

## UX flujo
1. Click "Ejecutar" → drawer abre → modo ejecución activo.
2. Click en listener del árbol → panel central muestra `ListenerLiveViewer`.
3. Polling cada 2s a `/listeners-state` mientras corre.
4. Click en otro elemento (sampler, UDV, CSV…) → vuelve al editor estructural.
5. Ejecución `completed` → badge "Datos congelados", el polling se detiene
   (un solo fetch final ya sucedió).
6. Cierre del drawer → `DELETE /listeners-state-cache` + reset de estado.

## NO incluido (Sprints 2.6c-g)
- Renderers reales por tipo (tablas Summary/Aggregate, View Results Tree,
  gráficas jp@gc, Response Time Graph).
- Sincronización con `interval_grouping` específico de jp@gc.
- Cambios de backend.

## Validación
- `tsc --noEmit`: **EXIT=0**.
- Imports lucide en 1 sola línea (`Loader2`, `CheckCircle2` ya existían — sin duplicados).
- Hooks nuevos en líneas 958-1010, early return `if (error || !structure)` en
  1083 → todos los hooks antes del early return (regla #16 OK).
- Líneas: `AIScriptEditor.tsx` 5879 → 6084 (+205); `api.ts` 776 → 830 (+54).
- Flujo sin ejecución intacto: `isInExecutionMode=false` → siempre `DetailPanel`.

## Backups
`api.ts.bak_26b_20260603_142847`, `AIScriptEditor.tsx.bak_26b_20260603_142847`.

## Estado: LISTO para Sprint 2.6c (Summary + Aggregate Report).
```