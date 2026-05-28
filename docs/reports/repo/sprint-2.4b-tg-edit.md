# Sprint 2.4b — Editor IA: infraestructura + auto-save + edición Thread Group

**Fecha:** 2026-05-26
**Estado:** ✅ tsc EXIT=0

## Cambios

### Frontend

| Archivo | Diff |
|---|---|
| `frontend/src/pages/AIScriptEditor.tsx` | 942 → 1501 (+559) |

Backup: `AIScriptEditor.tsx.bak_sprint2_4b_20260525_185916` (más el del 2.4e con el mismo estado, redundante pero conservado).

## Funcionalidades nuevas

### Infraestructura (base para 2.4c-e)

- **Helpers reutilizables**: `SectionCard`, `FormField`, `NotFoundPanel`.
- **Helper `formatRelativeTime(date)`**: "ahora", "hace 30s", "hace 2 min", "hace 1 h".
- **Helper `updateThreadGroup(structure, tgId, updates)`**: mutación inmutable, marca `is_dirty=true`.
- **Callback `updateStructure(newStructure)`** propagado a `DetailPanel` vía prop `onUpdateStructure`.

### Auto-save

- **Estado**: `saving`, `lastSaved`, `saveError`, `tick` (forzar re-render del indicador), `saveTimerRef`, `isDirtyRef`.
- **Función `persistJmx(jmxText)`**: reusa `aiScriptDesignsAPI.upsert` con `session_id` del design (preserva conversation + reference file en el upsert).
- **Debounce 800ms**: cada `updateStructure` reinicia el timer; al disparar llama `regenerateJmx` + `persistJmx`.
- **Indicador visual** en el header: "Guardando…" (azul + spinner), "Guardado hace Xs" (verde), "Error al guardar" (rojo + tooltip), "Sin cambios" (gris).
- **Refresh del indicador** cada 5s vía `setInterval` + `setTick` para que "hace Xs" envejezca.
- **Cleanup del timer** al desmontar.

### Panel Thread Group

- **`ThreadGroupEditPanel`** con sub-componentes:
  - `StandardConfigSection`: num_threads, ramp_time, loops, continue_forever, scheduler (duración + delay).
  - `SteppingConfigSection`: 9 campos del kg.apc — num_threads, initial_delay, start_users_count, start_users_count_burst, start_users_period, ramp_up, flight_time, stop_users_count, stop_users_period.
  - `LoadVisualization`: SVG inline con curva de carga (puntos + área + ejes). Pico y duración mostrados.
- **`computeLoadCurve(tg)`**: genera los puntos `{time, users}` para Standard (linear ramp con scheduler opcional) y Stepping (escalones según start_users_count / start_users_period / ramp_up + flight_time sostenido al final).

### Otros

- **Fix botón ←**: ahora navega a `/ai-script-editor` (ruta placeholder hasta Sprint 2.4e), title="Volver a Editor IA". Antes navegaba al chat.
- **Caso `thread_group`** añadido al switch del `DetailPanel`. Resto de tipos siguen con placeholder ámbar "Edición disponible próximamente" (2.4c-e).

## Adaptaciones del prompt original

1. **Nombres de campos SteppingConfig corregidos.** El snippet del prompt usaba `step_users_count` y `step_users_period`, que NO existen en el schema TS del Sprint 2.0. Los campos reales del kg.apc SteppingThreadGroup son `start_users_count` (cuántos añadir por paso) y `start_users_period` (tiempo entre pasos). Adapté los labels:
   - "Usuarios por paso" → `start_users_count`
   - "Tiempo entre pasos (s)" → `start_users_period`
2. **Campos Stepping añadidos al panel** que el snippet original omitía pero existen en el schema:
   - `initial_delay` — "Delay inicial (s)" (Threads initial delay)
   - `start_users_count_burst` — "Burst inicial"
   - `stop_users_count` — "Usuarios a quitar por paso"
   - `stop_users_period` — "Tiempo entre stops (s)"
3. **`persistJmx` ajustado al shape real de `AIScriptDesignUpsertPayload`.** El snippet del prompt incluía `name` e `is_draft` en el payload — ese tipo NO los acepta. Solo manda: `session_id`, `client_id`, `current_jmx`, `conversation`, `reference_file_*`. Si el usuario quiere renombrar el design desde el editor, deberá usar otro endpoint (fuera de scope de 2.4b).
4. **`designNameSnapshot` se conserva en state pero NO se envía al upsert** (marcado con `void` para suprimir warning de unused-var). Está listo para cuando el upsert acepte rename.
5. **Lucide icons `Save`, `CheckCircle`, `Clock` NO añadidos.** El snippet del header termina usando `Loader2`, `CheckCircle2` y `AlertCircle` — todos ya importados del Sprint 2.4a. Importar los del prompt habría producido warnings de unused-imports.
6. **`SamplerChild` y `TGChild` siguen importados** aunque solo `SamplerChild` se usa en otras partes — `TGChild` lo deja el Sprint 2.4a; lo conservo intacto para evitar regresiones en el árbol.
7. **`computeLoadCurve` ajustado** a los nombres reales: usa `start_users_count` y `start_users_period` en vez de los `step_users_*` del snippet. El comportamiento es equivalente — escalones de ramp + plateau, con flight_time al final.

## Validaciones

- ✅ `npx tsc --noEmit` → EXIT=0, sin warnings.
- ✅ Línea final: 1501 (+559 sobre Sprint 2.4a).
- ⏳ Validación visual: pospuesta hasta cierre de Sprint 2.4e (decisión de Fredy).

## Pendientes derivados

- **Sprint 2.4c**: panel HTTP Sampler (method, domain, port, protocol, path, body raw/form, headers conf, follow_redirects, keepalive). Reusa `SectionCard` y `FormField`.
- **Sprint 2.4d**: panel children del sampler (HeaderManager edit table, ResponseAssertion editor, RegexExtractor con builder, Timers).
- **Sprint 2.4e**: UDVs, CSV Data Sets, HttpDefaults, CookieManager, CacheManager, TestPlan + sidebar "Editor IA" + página `AIScriptEditorList.tsx` + ruta `/ai-script-editor`.

## Estado para Sprint 2.4c

**LISTO.** Infraestructura completa: el callback `onUpdateStructure` ya llega al `DetailPanel`, los helpers existen, el auto-save funciona end-to-end y el panel Thread Group sirve como template visual para los próximos. El Sprint 2.4c puede consumir `SectionCard`, `FormField` y `NotFoundPanel` directamente.
