# Sprint 2.4c — Editor IA: edición HTTP Sampler

**Fecha:** 2026-05-26
**Estado:** ✅ tsc EXIT=0

## Cambios

### Frontend

| Archivo | Diff |
|---|---|
| `frontend/src/pages/AIScriptEditor.tsx` | 1501 → 1829 (+328) |

Backup: `AIScriptEditor.tsx.bak_sprint2_4c_20260526_093824`.

## Funcionalidades nuevas

### Helpers

- **`updateSampler(structure, tgId, samplerId, updates)`**: mutación inmutable del sampler dentro del TG correspondiente. Marca `is_dirty=true` automáticamente.

### Panel `HTTPSamplerEditPanel`

Cuatro secciones reusando `SectionCard` + `FormField` del Sprint 2.4b:

1. **General**: Nombre, checkbox "Habilitado".
2. **URL y método**: grid de 12 columnas con Método (dropdown 7 opciones), Protocolo (http/https/default), Dominio, Puerto, y Path (full-width abajo).
3. **Cuerpo de la petición**: dropdown de modo (`none`/`raw`/`form`) que:
   - Al cambiar a `none`: limpia `raw_text` y `form_args`.
   - Al cambiar a `raw`: preserva `raw_text` previo si existe; limpia `form_args`.
   - Al cambiar a `form`: limpia `raw_text`; preserva `form_args` previo.
   - Muestra textarea (raw) / `FormParamsEditor` (form) / mensaje informativo (none).
4. **Opciones avanzadas**: checkboxes `follow_redirects`, `auto_redirects`, `use_keepalive` + input de `content_encoding`.

### Componente `FormParamsEditor`

- Tabla 12-col con columnas: Nombre, Valor, URL encode (checkbox), botón eliminar.
- Botón "+ Añadir parámetro" que inserta `{name:'', value:'', metadata:'=', always_encode:false, use_equals:true}` (todos los campos requeridos por el tipo `FormArgument`).
- Mensaje informativo cuando no hay parámetros.

### Wireup

- Caso `selected.kind === 'sampler'` añadido al switch del `DetailPanel`.
- Busca el TG por `tg_id` y el sampler dentro de `tg.children` por `sampler_id`.
- Pasa `onUpdate` que invoca `updateSampler` y propaga al `onUpdateStructure` del Sprint 2.4b → dispara auto-save con debounce 800ms.

## Adaptaciones del prompt original

1. **`HTTPSamplerModel.comments` NO existe en el schema TS** → eliminé el `FormField` de comentarios que el snippet incluía en la sección "General". Adaptación obligatoria para que `tsc` pase. Si en el futuro se añade `comments` al modelo, se puede restaurar.
2. **`useState` en `FormParamsEditor`**: NO se necesita — los params vienen del prop y se devuelven vía `onChange`. El snippet original ya lo planteaba así (controlled component); confirmado correcto.
3. **`raw_text` reset a `null`** (no `undefined`) — el schema permite `string | null | undefined` (campo `?`), pero el parser del backend usa `null` cuando no hay body raw. Mantengo consistencia con `null`.
4. **`metadata: '=', use_equals: true`** al crear `FormArgument` nuevo — son campos `string` y `boolean` requeridos (no opcionales) del schema. Los defaults reflejan el comportamiento JMeter estándar de form args.
5. **Cero helpers nuevos** — `SectionCard`, `FormField`, `NotFoundPanel`, `methodColor` ya existen del 2.4b/2.4a. No se duplicaron.

## Validaciones

- ✅ `npx tsc --noEmit` → EXIT=0, sin warnings.
- ✅ Línea final: 1829 (+328 sobre Sprint 2.4b).
- ⏳ Validación visual: pospuesta hasta cierre de Sprint 2.4e.

## Pendientes derivados

- **Sprint 2.4d**: panel children del sampler — `HeaderManager` (editor de tabla), `ResponseAssertion` (test_strings array + test_type bitmask), `RegexExtractor` / `JsonExtractor` / `XPathExtractor` / `BoundaryExtractor`, Timers (constant/uniform/gaussian). Reusa los mismos helpers.
- **Sprint 2.4e**: UDVs, CSV, HttpDefaults, CookieManager, CacheManager, TestPlan + sidebar "Editor IA" + página `AIScriptEditorList.tsx` + ruta `/ai-script-editor`.

## Estado para Sprint 2.4d

**LISTO.** Panel sampler operativo, infraestructura completa, callback `onUpdateStructure` propagado. El Sprint 2.4d puede acceder a un sampler seleccionado vía `selected.kind === 'sampler_child'` y reusar `updateSampler` para mutar `sampler.children` con la misma estrategia inmutable.
