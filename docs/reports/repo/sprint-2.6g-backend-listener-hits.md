# Sprint 2.6g — Backend Listener + Hits per Second (cierre 2.6)

## Componentes nuevos (`frontend/src/pages/AIScriptEditor.tsx`)

### `HitsPerSecondViewer` (LineChart)
- hits/sec = `totals.count / bucket_size_sec` por bucket (usa `state.bucket_size_sec`).
- Línea verde simple del total de hits por segundo vs tiempo.
- Estado vacío "Esperando datos…"; `isAnimationActive={false}` (live).

### `BackendListenerViewer` (caso especial — NO usa datos del JTL)
El Backend Listener publica métricas a InfluxDB, no al JTL; por eso no hay
`samples_tail`/`per_sampler_stats` que renderizar. El viewer muestra:
- **Estado**: "Enviando métricas a InfluxDB" (running) / "Sesión finalizada".
- **Configuración**: URL InfluxDB, bucket (`jmeter`), implementación
  (`InfluxdbBackendListenerClient`), percentiles (90/95/99).
- **Cómo ver gráficas**: guía a Grafana (`http://localhost:3000`), con nota de
  que el provisionamiento automático del dashboard queda para sprints futuros.
- **Alternativas dentro de Kinetix**: lista de listeners jp@gc que sí grafican
  en vivo en el editor.

Recibe `listenerName` y `executionStatus` (ya disponibles en `ListenerLiveViewer`).
Usa `Zap`/`Loader2`/`CheckCircle2` (ya importados). El `&` en la URL se escapó
como `&amp;` en el JSX para no romper el parser.

## Integración
Dispatch de `ListenerLiveViewer` completado a **10/10 kinds**:
- `kg_apc_hits_per_second` → `HitsPerSecondViewer`.
- `other` → `BackendListenerViewer`.
Placeholder convertido en defensa para kinds desconocidos futuros (ya no se
muestra para ningún kind real).

## Validación
- `tsc --noEmit`: **EXIT=0**.
- Backend `pytest -m "not slow"`: **110 passed**, 2 deselected (sin regresión).
- Dispatch: 10 condiciones `listenerKind === '...'` (uno por kind).
- Componentes definidos: `HitsPerSecondViewer` (3759), `BackendListenerViewer` (3830).
- Líneas: `AIScriptEditor.tsx` 7153 → 7353 (+200).

## Backup
`AIScriptEditor.tsx.bak_26g_20260603_164437`.

## Nota sobre datos hardcodeados (BackendListenerViewer)
La URL/bucket/percentiles que muestra el viewer son los defaults del stack de
Kinetix (no se parsean de los Arguments reales del listener en el `raw_xml`).
Parsear la config real del `ListenerModel.raw_xml` quedó fuera de alcance de
2.6g; es una mejora candidata si Fredy quiere reflejar configuraciones no estándar.

## Estado: SPRINT 2.6 COMPLETO.
```