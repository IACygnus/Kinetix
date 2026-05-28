# Sprint 2.4e — Cierre del Editor IA

**Fecha:** 2026-05-26
**Estado:** ✅ tsc EXIT=0 — **SPRINT 2.4 COMPLETO**

## Cambios

### Frontend

| Archivo | Tipo | Diff |
|---|---|---|
| `frontend/src/pages/AIScriptEditor.tsx` | MOD | 2492 → 3025 (+533) |
| `frontend/src/pages/AIScriptEditorList.tsx` | NUEVO | 163 |
| `frontend/src/App.tsx` | MOD | 253 → 262 (+9: 1 import + ruta) |
| `frontend/src/components/layout/Sidebar.tsx` | MOD | 376 → 383 (+7: import `Code` + item "Editor IA") |

Backups con sufijo `.bak_sprint2_4e2_20260526_123526` para los 3 archivos modificados.

## Funcionalidades nuevas (este sprint)

### 6 paneles de configuración global

- **`TestPlanEditPanel`**: nombre, comentarios, modo funcional, serialize_threadgroups, tearDown_on_shutdown.
- **`UDVsEditPanel`**: tabla 12-col add/remove/edit de UDVs. Helper UI con sintaxis `${var}` recordatoria.
- **`CSVDataSetEditPanel`**: 2 SectionCards (Archivo+Variables / Formato+Comportamiento). Filename, variable_names join/split por coma, delimiter, encoding, share_mode (3 opciones), 4 checkboxes (ignore_first_line, recycle, stop_thread, quoted_data).
- **`HttpDefaultsEditPanel`**: grid 2x2 (protocol/domain/port/encoding) + path full-width.
- **`CookieManagerEditPanel`**: enabled, clear_each_iteration, policy.
- **`CacheManagerEditPanel`**: enabled, clear_each_iteration, use_expires.

### Wireup (DetailPanel)

6 casos añadidos al switch: `test_plan`, `udvs`, `csv_data_set`, `http_defaults`, `cookie_manager`, `cache_manager`. Cada uno invoca `onUpdateStructure` con el slice correspondiente del root marcado `is_dirty: true`, disparando el auto-save con debounce 800ms.

### Nueva página `AIScriptEditorList.tsx`

Workspace dedicado al editor:
- Lista los diseños AI que tienen `has_jmx===true` (filtro vía `aiScriptDesignsAPI.list({ include_drafts: false })`).
- Filtros: búsqueda por nombre + dropdown de cliente.
- Tabla 4 columnas (Nombre / Cliente / Actualizado / Acción "Editar").
- Click "Editar" → `navigate(/ai-script-designer/editor/${id})`.
- Estados de loading/error/vacío.

### Ruta `/ai-script-editor` en App.tsx

Registrada dentro del `<Route element={<Layout />}>` — hereda Layout/Sidebar automáticamente (no requiere envoltorio manual). Roles: admin, analyst.

### Item "Editor IA" en Sidebar

Añadido bajo "Diseño" → entre "Mis Diseños IA" y "Guardados". Icono `Code`, roles `[admin, analyst]`.

## Resumen del Sprint 2.4 completo (a-e)

| Sub-sprint | Alcance | Líneas finales AIScriptEditor.tsx |
|---|---|---|
| 2.4a | Estructura base + árbol read-only | 942 |
| 2.4b | Infraestructura + auto-save + Thread Group | 1501 (+559) |
| 2.4c | HTTP Sampler | 1829 (+328) |
| 2.4d | Children del Sampler (9 tipos) | 2492 (+663) |
| 2.4e | Config global + sidebar + lista | **3025 (+533)** |
| **TOTAL Editor IA** | — | **3025 líneas** |

Más: `AIScriptEditorList.tsx` (163), modificaciones a `App.tsx`, `Sidebar.tsx`, `api.ts`, tipos TS, y wiring en `AIScriptDesigner.tsx` y `AIDesignerHistory.tsx`.

## Funcionalidades totales del Editor IA (sprints a-e)

### Estructura
- Layout 2 paneles (árbol 30% / detalle 70%) + header full-width.
- Árbol jerárquico con búsqueda, auto-expand, badges de método HTTP, indicadores de enabled/disabled.
- Modal "Ver XML raw" con copia al portapapeles.
- Botones de acceso: chat (AIScriptDesigner header), workspace (AIDesignerHistory row), sidebar (Editor IA).

### Edición end-to-end con auto-save
- **TestPlan**: nombre, comentarios, flags.
- **UDVs**: tabla editable.
- **CSV Data Sets**: archivo, variables, formato, comportamiento.
- **HTTP Defaults / Cookie Manager / Cache Manager**: configuración completa.
- **Thread Group**: Standard (num_threads, ramp, loops, scheduler) o Stepping (9 campos kg.apc) + visualización SVG de curva de carga.
- **HTTP Sampler**: URL/método, body (raw/form/none con switching), opciones avanzadas.
- **Sampler children (9 tipos)**: HeaderManager, ResponseAssertion, Regex/Json/XPath/Boundary Extractors, Constant/Uniform/Gaussian Timers.
- **Auto-save** debounce 800ms → `regenerateJmx` + `upsert` → indicador "Guardando…/Guardado hace Xs/Error" en header.

### Cosas que NO se editan (preservadas via raw_xml)
- Controllers (Generic/Loop/If/While/Throughput) — navegables en el árbol pero sin panel propio.
- Listeners — passthrough total (raw_xml preserva save_config interno).
- Unmapped (ProxyControl, etc.) — passthrough.

## Adaptaciones del prompt original

1. **Ruta SIN `<Layout>` envoltorio.** El patrón real de `App.tsx` envuelve TODAS las rutas protegidas en `<Route element={<Layout />}>` padre. La ruta nueva hereda el layout automáticamente. Si hubiera envuelto manualmente con `<Layout>` habría producido un layout anidado (sidebar duplicado).
2. **Sidebar shape correcto.** Los items usan `path` (no `to`), tipo `SubMenuItem` definido en el archivo. Roles opcional. El item "Editor IA" se añadió como hijo de "Diseño" (no como item top-level), siguiendo la jerarquía existente.
3. **`CSVShareMode` cast obligatorio.** El campo `ds.share_mode` es de tipo `CSVShareMode = 'shareMode.all' | 'shareMode.group' | 'shareMode.thread'` (estricto). El `e.target.value` del `<select>` es `string` — necesario `as CSVShareMode` en el onChange para mantener type-safety.
4. **Tipos importados en bloque** en AIScriptEditor.tsx: 7 nuevos (TestPlanModel, UserDefinedVariable, CSVDataSetModel, CSVShareMode, HttpDefaultsModel, CookieManagerModel, CacheManagerModel). Sin duplicación.
5. **`Code` icon añadido a Sidebar.tsx** (no estaba importado).
6. **Cero helpers duplicados** — `SectionCard`, `FormField`, `NotFoundPanel` reusados del 2.4b.
7. **`AIScriptEditorList` usa tipos del API directamente** (`AIScriptDesignSummary`, `ClientInfo`) en vez de interfaces locales redundantes que el snippet sugería.

## Validaciones

- ✅ `npx tsc --noEmit` → EXIT=0, sin warnings.
- ✅ AIScriptEditor.tsx: 3025 líneas (+533 sobre 2.4d).
- ✅ Nueva ruta `/ai-script-editor` registrada (línea 184 de App.tsx).
- ✅ Item "Editor IA" en sidebar (sin duplicados).
- ⏳ Validación visual completa: pendiente.

## Pendientes derivados (FUTUROS sprints)

- **Sprint 2.5:** ejecución smoke test 1 usuario con datos reales del CSV/UDV.
- **Sprint 2.6:** visualización gráfica avanzada del Stepping (overlay con TPS esperado, etc.).
- **Sprint 2.7:** mejorar SYSTEM_PROMPT IA para generar UDVs/CSVs cuando referencia variables (bug del Sprint 2.1.1).
- **Edición de Controllers** (Generic/Loop/If/While/Throughput) — actualmente solo navegables en el árbol con placeholder.
- **Renombrar el design desde el Editor** (requiere endpoint backend que acepte `name` en upsert o un PATCH dedicado).

## Estado para Validación Visual

**SPRINT 2.4 COMPLETO** y listo para validación visual completa de Fredy.

### Cómo validar visualmente

1. `http://localhost:5173` → login (admin / sqa2024).
2. Sidebar → "Diseño" → **"Editor IA"** → debe aparecer la lista de diseños con JMX (filtros por nombre y cliente funcionando).
3. Click **"Editar"** en cualquier diseño con JMX → abre el editor en `/ai-script-designer/editor/{id}`.
4. Probar edición en cada tipo del árbol:
   - **Resumen**: stats + variables ref/def/undef + unmapped.
   - **Test Plan**: cambiar nombre, comentarios, flags.
   - **Variables (UDV)**: añadir/editar/quitar variables.
   - **HTTP Defaults / Cookie / Cache Manager**: tocar campos.
   - **CSV**: cambiar filename, delimiter, share_mode.
   - **Thread Group** (Carga stepping): editar usuarios totales, ramp_up, flight_time → ver la curva SVG cambiar.
   - **Sampler**: cambiar method, path, switching de body type, headers.
   - **Sampler children**: editar HeaderManager (table), ResponseAssertion (patrones), Regex/JSON Extractor (refname, regex, json_path).
5. Verificar indicador en header: **"Guardando…"** (azul + spinner) → **"Guardado hace Xs"** (verde) tras ~1s.
6. **Recargar la página** → los cambios deben persistir (vienen del JMX guardado por upsert).
7. Botón **"Ver XML raw"** → modal con el JMX actual (debería reflejar las ediciones).
8. Botón **← (ArrowLeft)** → debe volver al Editor IA workspace (no al chat).

Si algo no funciona, lo arreglamos como hotfix antes del Sprint 2.5.
