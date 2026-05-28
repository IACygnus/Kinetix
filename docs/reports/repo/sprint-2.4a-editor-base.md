# Sprint 2.4a — Frontend Editor IA: estructura base + árbol read-only

**Fecha:** 2026-05-25
**Estado:** ✅ Completado (compilación TS OK) — ⏳ Pendiente validación visual de Fredy

## Objetivo

Frontend Editor IA: layout de 2 paneles (árbol izquierdo + detalle derecho), vista resumen al entrar sin selección, modal XML raw read-only, botones de acceso desde chat y workspace. Sin edición de campos (eso es 2.4b-d). Sin auto-save (eso es 2.4b).

## Cambios

### Frontend

| Archivo | Tipo | Diff |
|---|---|---|
| `frontend/src/services/api.ts` | MOD | 468 → 492 (+24, wrapper `aiScriptStructureAPI` con `parseJmx` y `regenerateJmx`) |
| `frontend/src/pages/AIScriptEditor.tsx` | NUEVO | 942 líneas |
| `frontend/src/App.tsx` | MOD | 245 → 253 (+8, 1 import + ruta `/ai-script-designer/editor/:designId`) |
| `frontend/src/pages/AIScriptDesigner.tsx` | MOD | 1120 → 1134 (+14, `useNavigate`, icono `Code`, botón "Abrir en Editor IA") |
| `frontend/src/pages/AIDesignerHistory.tsx` | MOD | 418 → 427 (+9, icono `Code`, botón "Abrir en Editor IA" por fila) |
| `frontend/src/components/layout/Sidebar.tsx` | SIN CAMBIOS | acceso solo contextual (decisión de Fredy) |

Backups creados con sufijo `.bak_sprint2_4a_20260525_175710` para los 5 archivos modificados.

## Funcionalidades

- **Layout 2 paneles (B):** árbol izquierdo 30%, detalle derecho 70%, header full-width propio.
- **Árbol jerárquico read-only:** Resumen → TestPlan → Configuración global (UDVs, HTTP Defaults, Cookie/Cache, CSVs) → Thread Groups (con Stepping vs Standard) → Samplers (con badge método HTTP) → SamplerChildren (HeaderManager, Assertions, Extractors, Timers) → Listeners → No editables.
- **Búsqueda de árbol** por nombre (filtra recursivamente).
- **Auto-expand** del primer nivel y de cada Thread Group al cargar.
- **Vista resumen al entrar (A):** 8 stat cards + panel de variables indefinidas (rojo crítico) + panel de variables definidas (verde) + lista de unmapped + warnings del parser.
- **Modal "Ver XML raw" (A)** read-only con botón Copiar al portapapeles.
- **Botones de acceso contextual:**
  - Chat (`/ai-script-designer?designId=X`): botón "Abrir en Editor IA" en el header, deshabilitado si no hay `designId` o no hay `currentJmx`.
  - Workspace (`/ai-script-designer/history`): icono `Code` morado por fila, deshabilitado si `!d.has_jmx`.
- **Placeholder de edición:** al seleccionar cualquier nodo distinto de "Resumen", muestra un panel ámbar "Edición disponible desde Sprint 2.4b" con el `selected.kind` actual.

## Decisiones técnicas

- `JSON.stringify(selected) === JSON.stringify(node)` para comparar selección (objetos discriminados por `kind`).
- `TreeFolder` colapsable con `expanded[key] !== false` (default abierto).
- Conteo recursivo de samplers que descende por controllers anidados (incluye los 6 nietos del Recorder en el fixture).
- Editor NO usa `<Layout>` — tiene header full-width propio + h-screen.
- `aiScriptStructureAPI` añadido al final de `services/api.ts` como un grupo nuevo (sigue el patrón de `aiScriptDesignsAPI`).
- Sin auto-save todavía (eso es 2.4b). El editor NO llama a `regenerateJmx` en este sprint.

## Adaptaciones del prompt original

1. **`useNavigate` añadido al import de `react-router-dom` en `AIScriptDesigner.tsx`** — el archivo solo importaba `useSearchParams`. El nuevo botón necesita navegar al editor.
2. **`Code` añadido a los imports de `lucide-react`** en ambos `AIScriptDesigner.tsx` y `AIDesignerHistory.tsx` — no estaba presente.
3. **`ParseJmxResponse extends AIScriptStructure {}` eliminado** del snippet — Pydantic devuelve el objeto plano directamente; el alias era redundante y rompía build de TS por interface vacía. Reemplazado por `Promise<AIScriptStructure>` directo en la firma.
4. **`StatCard "No editables"` simplificado** — el snippet original tenía `structure.unmapped.length + structure.metadata.unmapped_count - structure.unmapped.length` (que se cancela). Cambiado a `structure.metadata.unmapped_count` directamente (suma top-level + dentro de samplers, calculada por el parser).
5. **`ResponseAssertion` icono usado de `lucide-react` con `CheckCircle2`** — `Search as SearchIcon` y `Filter` del snippet original tampoco se usaban (solo `Search as SearchIcon`); `Filter`, `HTTPSamplerModel`, `UnsupportedElement` también estaban no-usados. Eliminados para tener `tsc --noEmit` con EXIT=0 sin `noUnusedLocals` triggers.

## Validaciones

- ✅ `npx tsc --noEmit` → EXIT=0
- ✅ Ruta `/ai-script-designer/editor/:designId` registrada en `App.tsx` línea 176
- ✅ `AIScriptEditor` importado en `App.tsx` línea 24
- ✅ Sidebar SIN entradas duplicadas (grep confirma: cero matches)
- ⏳ Validación visual de Fredy pendiente

## Pendientes derivados

- **Sprint 2.4b:** panel edición Thread Group (kind, num_threads, ramp, on_sample_error) + sub-panel Stepping config + visualización gráfica (curva de carga) + auto-save (debounce 800ms, llama `regenerateJmx` y `aiScriptDesignsAPI.upsert`).
- **Sprint 2.4c:** panel edición HTTP Sampler (method, domain, port, protocol, path, body raw/form, follow_redirects, keepalive).
- **Sprint 2.4d:** panel edición children del sampler (HeaderManager, Assertion, Extractor, Timer) con sub-formularios por tipo.
- **Sprint 2.4e:** panel edición UDVs/CSVs/Cookie/Cache/HTTP Defaults + warnings panel detallado para variables indefinidas.

## Estado para Sprint 2.4b

**LISTO** para validación visual de Fredy.
- Vite HMR ya tomó los cambios (sin rebuild).
- Cómo probar: abrir `http://localhost:5173`, ir a `Workspace` (`/ai-script-designer/history`), elegir un diseño con JMX guardado (icono `<>` morado en la columna acciones), clic → se abre el Editor IA. Alternativamente: desde un diseño abierto en el chat con JMX generado, botón "Abrir en Editor IA" en el header.

Si la página carga visualmente y el árbol se ve correctamente con el JMX de Ejercicio_Booking (3 TGs / 18 samplers / 2 CSVs / 4 UDVs / 6 listeners / 1 unmapped), el sprint está cerrado y pasamos a 2.4b. Si hay regresión visual, anotarla aquí.
