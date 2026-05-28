# Sprint 2.4d — Editor IA: edición children del Sampler

**Fecha:** 2026-05-26
**Estado:** ✅ tsc EXIT=0

## Cambios

### Frontend

| Archivo | Diff |
|---|---|
| `frontend/src/pages/AIScriptEditor.tsx` | 1829 → 2492 (+663) |

Backup: `AIScriptEditor.tsx.bak_sprint2_4d_20260526_120358`.

## Funcionalidades nuevas

### Helper

- **`updateSamplerChild(structure, tgId, samplerId, childId, updates)`**: mutación inmutable que marca dirty AL CHILD y AL SAMPLER PADRE (defensa redundante — el backend del Sprint 2.3a invalida cache via `_has_dirty_descendant`, pero ambas marcas garantizan re-generación).

### Componente discriminador

- **`SamplerChildEditPanel`**: switch sobre `child.type` que ruta al editor específico. Fallback ámbar para tipos no editables (ej. `unsupported`).

### 9 paneles de edición específicos

1. **`HeaderManagerEdit`** — tabla 12-col (Nombre + Valor + ❌). Add/remove/edit headers.
2. **`ResponseAssertionEdit`** — 7 opciones de `test_field`, 6 opciones de `test_type` (bitmask JMeter), patrones uno por línea, custom_message, checkbox assume_success.
3. **`RegexExtractorEdit`** — refname, regex, template, match_number, default, dropdown `use_headers` con las 5 opciones del tipo `RegexUseHeaders`.
4. **`JsonExtractorEdit`** — refname, json_path, match_number, default.
5. **`XPathExtractorEdit`** — refname, xpath, default.
6. **`BoundaryExtractorEdit`** — refname, left/right boundary, match_number, default.
7. **`ConstantTimerEdit`** — delay_ms.
8. **`UniformRandomTimerEdit`** — constant_delay_ms + random_delay_ms (rango uniforme).
9. **`GaussianRandomTimerEdit`** — constant_delay_ms + deviation_ms (campana).

### Wireup

- Caso `selected.kind === 'sampler_child'` añadido al `DetailPanel`.
- Busca TG → sampler → child por id encadenado. Si cualquiera falta → `NotFoundPanel`.
- `onUpdate` invoca `updateSamplerChild` → `onUpdateStructure` → auto-save con debounce 800ms (cadena del Sprint 2.4b).

## Adaptaciones del prompt original

1. **`RegexExtractorModel.use_headers` solo 5 valores válidos.** El snippet incluía `'unescaped'`, `'as_document'`, `'request_headers'` que NO existen en el tipo `RegexUseHeaders = 'false' | 'true' | 'URL' | 'code' | 'message'`. Eliminé esas 3 opciones del dropdown — solo se ofrecen las 5 reales. Cast explícito `as RegexExtractorModel['use_headers']` en el `onChange` para mantener type-safety.
2. **`XPathExtractorModel.xpath` (no `xpath_query`).** El snippet usaba `data.xpath_query` y `onUpdate({ xpath_query: ... })` — el campo real del schema TS es `xpath`. Adaptación obligatoria.
3. **`Clock` añadido a `lucide-react` imports.** No estaba presente del 2.4a/b/c — el snippet anticipaba su uso para los 3 timers.
4. **`HeaderModel` solo tiene `name` y `value`.** El snippet ya lo asumía correctamente; no había `enabled` ni metadatos que preservar al crear.
5. **`ResponseAssertionModel.test_field` es `AssertionTestField | string`.** Como acepta `string` libre, las 3 opciones extras del dropdown (`request_data`, `request_headers`, `sample_label`) son válidas como strings aunque no estén en el union literal — útil porque JMeter sí las soporta en runtime.
6. **`onUpdate: (updates: any) => void` en `SamplerChildEditPanel`.** El discriminador rutea a 9 paneles distintos, cada uno con su `Partial<T>` específico. Usar `any` aquí evita un union complejo que TS no podría discriminar sin extra runtime checks. La type-safety se preserva DENTRO de cada panel via `ChildEditorProps<T>`.
7. **`SectionCard`, `FormField`, `NotFoundPanel` reusados** — cero duplicación de helpers del 2.4b.

## Validaciones

- ✅ `npx tsc --noEmit` → EXIT=0, sin warnings.
- ✅ Línea final: 2492 (+663 sobre Sprint 2.4c).
- ⏳ Validación visual: pospuesta hasta cierre de Sprint 2.4e.

## Pendientes derivados

- **Sprint 2.4e** (cierre):
  - Paneles UDVs, CSV Data Sets, HTTP Defaults, Cookie Manager, Cache Manager, TestPlan.
  - Sidebar item "Editor IA".
  - Página nueva `AIScriptEditorList.tsx` (workspace dedicado al editor).
  - Ruta `/ai-script-editor` (placeholder del botón ← del Sprint 2.4b).

## Estado para Sprint 2.4e

**LISTO.** Edición completa de TG (2.4b) + Sampler (2.4c) + Children (2.4d). El callback `onUpdateStructure` + auto-save funcional end-to-end. Solo falta cerrar la configuración global y el wireup de navegación en 2.4e.
