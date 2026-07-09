# HF20 — Fix consolidado de listeners (parser anidado + persistencia manual)

## Contexto
Referencia: `docs/reports/diagnostico-regresiones-pre-sprint-3.0.md` (Regresiones 2 y 3).
Estado inicial: **202 tests PASS** (suite completa) / 200 no-slow. Branch
`backup-trabajo-local`, HF18b aplicado, tag `pre-sprint-3.0-20260708_190944`.

> Nota: el prompt citaba "211 PASS" como baseline; el conteo real del repo en el
> momento del fix era **202** (suite completa, incluye 2 slow) / 200 no-slow. Se
> reporta el número real medido, no el estimado.

## Bugs resueltos

### HF20a — Parser no reconoce ResultCollector anidado en Thread Group
- **Síntoma:** View Results Tree y Summary Report aparecían con el placeholder
  "Edición disponible próximamente. Tipo: unmapped." cuando la IA los generaba
  dentro del `hashTree` del Thread Group (patrón habitual de la IA).
- **Causa:** `_parse_tg_children` (`jmx_to_structure.py`) tenía un dispatch sin
  rama para `ResultCollector` → caía en el `else` → `UnsupportedElement` →
  renderizaba como hijo `unsupported` del TG en el árbol. El mapeo
  `ResultCollector → listeners[]` solo existía en el dispatch **top-level**.
- **Fix (2 partes, mismo shape que top-level):**
  1. Rama nueva en `_parse_tg_children`: al ver `ResultCollector` (por
     `testclass`) lo **omite** como `TGChild` para que NO renderice como
     "unmapped" en el árbol.
  2. Helper nuevo `_extract_nested_listeners(hash_tree)`: recolecta los
     `ResultCollector` anidados (recorriendo también controllers) y los mapea a
     `ListenerModel` vía el mismo `_parse_listener` / `_LISTENER_KIND_MAP` del
     top-level. El orquestador `parse_jmx_to_structure` hace bubble-up de esos
     listeners a `structure.listeners[]` en la rama de Thread Groups.

### HF20b — Listeners agregados manualmente desaparecen tras reload
- **Síntoma:** el usuario agregaba un listener, el sidebar mostraba
  "Listeners (2)"; cualquier reload (subir CSV, remontar componente) → "Listeners (0)".
- **Causa:** `handleAddElement` / `handleDeleteElement` / `handleToggleEnabled`
  usaban `setStructure(next)` directo → NO marcaban `isDirtyRef` → NO disparaban
  el auto-save → la DB (`current_jmx`) nunca recibía la estructura actualizada.
  Al recargar, `reloadStructure` volvía a parsear el JMX de DB (sin los
  listeners) → Listeners (0).
- **Fix:** los 3 handlers ahora usan `updateStructure(next)` (misma función
  cableada al panel de samplers), que marca `isDirtyRef.current = true` y agenda
  el debounce de persistencia (`regenerateJmx` → `persistJmx` → upsert a DB).
  Se agregó `updateStructure` a las deps de los 3 `useCallback`.

## Cambios en archivos

### `backend/app/services/engine/jmx_to_structure.py` (+35 líneas, 902 → 937)
- `_parse_tg_children`: rama `elif "ResultCollector" in testclass: pass` antes
  del `else` (líneas ~686-692).
- Helper nuevo `_extract_nested_listeners(hash_tree) -> List[ListenerModel]`
  (después de `_parse_listener`, líneas ~730-753).
- `parse_jmx_to_structure`: `structure_data["listeners"].extend(
  _extract_nested_listeners(child_ht))` en la rama de Thread Groups (línea ~885).

### `frontend/src/pages/AIScriptEditor.tsx` (3 replaces, +6/-6 líneas)
- `handleAddElement` (línea 714): `setStructure(next)` → `updateStructure(next)`
  + `updateStructure` a deps.
- `handleDeleteElement` (línea 770): `setStructure(next)` → `updateStructure(next)`
  + `updateStructure` a deps.
- `handleToggleEnabled` (línea 837): `setStructure(next)` → `updateStructure(next)`
  + `updateStructure` a deps.
- Los `setStructure` de carga inicial / `reloadStructure` (líneas 255, 304) y el
  interno de `updateStructure` (371) se dejan intactos (no deben disparar auto-save).

## Tests

### Backend (HF20a) — `backend/tests/test_jmx_parser_listener_anidado.py` (nuevo, 6 tests)
1. `test_listener_anidado_en_tg_se_mapea_correctamente` — 2 listeners en
   `listeners[]`, ninguno en `unmapped[]`.
2. `test_listener_anidado_no_deja_unsupported_en_children` — el TG no queda con
   hijos `unsupported` (valida el fix de render del árbol).
3. `test_listener_toplevel_sigue_funcionando` — backward compat top-level.
4. `test_listener_anidado_mantiene_atributo_enabled` — preserva `enabled`.
5. `test_listener_anidado_tiene_kind_mapeado` — `view_results_tree` /
   `summary_report` vía `_LISTENER_KIND_MAP`.
6. `test_no_regresion_estructura_completa_con_listener_anidado` — TG y sampler
   intactos.

> Adaptación: la API real es `parse_jmx_to_structure(jmx_text) -> AIScriptStructure`
> (modelo Pydantic, acceso por atributos), no `jmx_to_structure` con `dict.get()`
> como sugería el prompt. Tests reescritos contra la firma real.

### Frontend (HF20b) — validación visual
No hay test runner de frontend configurado (sin Vitest/Jest en `package.json`;
scripts: `dev`/`build`/`preview`). Se documenta como **validación visual** por Fredy:
- Agregar listener → sidebar dice "Listeners (N)".
- Recargar página / subir CSV → sidebar sigue diciendo "Listeners (N)".
- Verificable en DB: `SELECT current_jmx FROM script_designs WHERE id = ...`
  debe contener el `<ResultCollector>` agregado.

### Resultado
- **202 → 208 PASS** (+6) suite completa. 0 fallos, 0 regresiones.
- Subset `-k "listener or parser"`: 58 passed.
- `tsc --noEmit`: **EXIT=0**.

## Acoplamiento resuelto
- **HF20a** permite que los listeners parseados (del TG anidado o top-level)
  rendericen correctamente en el árbol en vez de como "unmapped".
- **HF20b** permite que los listeners agregados manualmente se persistan y
  sobrevivan a reloads.
- Juntos: el flujo end-to-end del listener funciona en ambos casos
  (IA-generado anidado + agregado manual).

## Pendiente (fuera de scope HF20)
- **HF20c** (CSV auto-generation post-IA) — requiere decisión de negocio sobre
  generar CSV con datos dummy/reales vs pedir al usuario. Sprint separado.

## Estado
HF20 aplicado. Backups: `*.bak_hf20_20260708_230441` (ambos archivos).
Listo para validación visual por Fredy con el caso restful-booker (regenerar el
diseño y verificar que los listeners ya NO aparecen como "unmapped" y que los
agregados manualmente persisten tras reload).
