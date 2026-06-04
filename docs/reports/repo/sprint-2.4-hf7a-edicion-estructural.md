# Sprint 2.4-HF7.A — Edición estructural en el árbol del Editor IA

**Fecha:** 2026-05-30
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** Aplicado y validado (sin gasto de cuota IA)

---

## 1. Alcance

| Letra | Capacidad | Estado |
|---|---|---|
| A | Agregar HTTPSampler nuevo a un Thread Group existente | ✅ |
| A.1 | Agregar children al sampler: HeaderManager, ResponseAssertion, RegexExtractor, JsonExtractor, ConstantTimer | ✅ |
| A.2 | Agregar UDV nueva a la lista global + CSV Data Set nuevo | ✅ |
| B | Eliminar cualquier elemento del árbol (con confirmación) | ✅ |
| C | Toggle enable/disable visual (checkbox al lado del nombre) | ✅ |

**Fuera de alcance (otros sprints):**
- Agregar/eliminar Listeners → HF7.B (se pide por el chat IA).
- Agregar Thread Groups nuevos → fuera del HF7 (se pide por chat).
- Smoke test → Sprint 2.5.

---

## 2. Archivos creados / modificados

| Archivo | Tipo | Líneas |
|---|---|---|
| `backend/app/schemas/refine_operations.py` | MOD | +112 / -1 |
| `backend/app/services/engine/refine_operations_applier.py` | MOD | +293 / -2 |
| `backend/app/api/v1/endpoints/script_ai.py` | MOD | +51 / -15 (REFINE_SURGICAL_SYSTEM_PROMPT) |
| `frontend/src/pages/AIScriptEditor.tsx` | MOD | +668 / -28 |
| `backend/tests/test_refine_operations.py` | MOD | +130 / -1 |

**Backups creados:**
- `backend/app/services/engine/refine_operations_applier.py.bak_hf7a_20260530_005957`
- `backend/app/schemas/refine_operations.py.bak_hf7a_20260530_005957`
- `backend/app/api/v1/endpoints/script_ai.py.bak_hf7a_20260530_005957`
- `frontend/src/pages/AIScriptEditor.tsx.bak_hf7a_20260530_005957`

---

## 3. Operaciones nuevas en el refine quirúrgico

| Op | Schema | Función |
|---|---|---|
| `add_sampler` | `AddSamplerOp(thread_group_id, sampler, position)` | Crea HTTPSampler en el TG indicado. Body anidado opcional. |
| `add_sampler_child` | `AddSamplerChildOp(sampler_id, child_kind, data)` | Crea Header/Assertion/Extractor/Timer en el sampler. `child_kind` ∈ {header_manager, response_assertion, regex_extractor, json_extractor, constant_timer}. |
| `add_udv` | `AddUdvOp(name, value, metadata)` | Añade UDV global. Rechaza si ya existe el nombre. |
| `add_csv_dataset` | `AddCsvDatasetOp(data)` | Crea CSV Data Set con defaults razonables. |
| `delete_element` | `DeleteElementOp(target_kind, id, sampler_id?, udv_name?)` | Elimina TG, sampler, sampler_child, csv_data_set, listener o UDV. |

**System prompt:** se actualizó `REFINE_SURGICAL_SYSTEM_PROMPT` documentando las 5 ops nuevas con ejemplos y se eliminó la sección antigua de "FALLBACK para add/delete" (ahora soportadas). El fallback queda solo para casos verdaderamente complejos (convertir kind del TG, mover entre TGs, cambios masivos).

---

## 4. Diseño frontend — TreeView interactivo

- **Tipos nuevos:** `AddElementType`, `DeletableKind`, `ToggleableKind`, `TreeActions`.
- **Estado del modal en `AIScriptEditor`:** `addModalOpen`, `addModalType`, `addModalContext`.
- **Handlers:** `openAddModal`, `handleAddElement`, `handleDeleteElement`, `handleToggleEnabled` — todos `useCallback` para evitar re-renders.
- **`treeActions`** se pasa por props desde `TreeView` a `ThreadGroupNode → TGChildNode → SamplerChildNode`.
- **UI:**
  - `TreeItem` extendido con props opcionales `enabled`, `onToggleEnabled`, `onAdd`, `addTitle`, `onDelete`, `deleteTitle`. Renderiza checkbox a la izquierda y botones `Plus` / `Trash2` que aparecen on-hover (group-hover).
  - `ThreadGroupNode`: checkbox + botón "Agregar HTTP Sampler" + botón "Eliminar TG".
  - `TGChildNode` (sampler): checkbox + botón "Agregar componente" + botón "Eliminar sampler".
  - `SamplerChildNode`: checkbox + botón "Eliminar child" (sin Add — los children son hojas).
  - **`AddElementModal`**: nuevo componente con 4 ramas (sampler / sampler_child / udv / csv_dataset), validación de campos requeridos, autofocus en el primer input.
- **Mutación local:** deep-clone con `JSON.parse(JSON.stringify(structure))`, mutación, `setStructure(next)`. El auto-save existente (`regenerate-jmx`) sincroniza con backend automáticamente.

---

## 5. Validaciones

### 5.1. Tests backend

```
pytest tests/ -q
71 passed in 1.57s
```

- 63 tests pre-HF7.A (sin cambios).
- **8 nuevos en `test_refine_operations.py`** (Sprint 2.4-HF7.A):
  - `test_add_sampler_a_tg_existente` ✅
  - `test_add_sampler_child_header_manager` ✅
  - `test_add_udv` ✅
  - `test_add_udv_duplicado_lanza_error` ✅
  - `test_add_csv_dataset` ✅
  - `test_delete_sampler` ✅
  - `test_delete_udv` ✅
  - `test_delete_inexistente_lanza_error` ✅

### 5.2. TypeScript check

```
npx tsc --noEmit → EXIT=0
```

### 5.3. Round-trip end-to-end (parse → add → regenerate → re-parse)

Sobre el fixture `Ejercicio_Booking.jmx` (93 439 chars, 3 TGs, 18 samplers, 3 UDVs, 2 CSVs):

| Operación | Verificado en el XML regenerado | Verificado tras re-parse |
|---|---|---|
| `AddSamplerOp("Test E2E", "GET /health")` sobre TG standard | `"Test E2E"` y `/health` presentes | sampler con `method=GET`, `path=/health` |
| `AddUdvOp("env", "prod")` | `"env"` presente | UDV `env` re-parseada |
| `AddCsvDatasetOp("CSV Test", "data.csv", ["a","b"])` | `"CSV Test"` presente | CSV `CSV Test` re-parseado |
| `AddSamplerChildOp(sampler_id, "response_assertion", ["200"])` | _(verificado vía re-parse)_ | `children[0].type == "response_assertion"` |

Salida del script de prueba:
```
JMX original:  93 439 chars
aplicadas:     3 (la 4ª op se aplica en una segunda llamada tras descubrir el id del sampler nuevo)
JMX regenerado: 91 403 chars
ROUND-TRIP OK: parse → add(4 ops) → regenerate → re-parse mantiene todos los nuevos elementos
```

---

## 6. Cómo validar visualmente

1. Abrir un diseño existente en el Editor IA (`/ai-script-designer/editor/{designId}`).
2. **Toggle:** click en cada checkbox al lado de TG / sampler / sampler_child / CSV / cookie / cache / listener — el elemento se atenúa visualmente y queda registrado en `is_dirty`.
3. **Agregar:**
   - Hover sobre un Thread Group → aparece botón `+` → click → modal "Nuevo HTTP Sampler" con nombre/método/path/domain → "Crear".
   - Hover sobre un sampler → aparece botón `+` → click → modal "Agregar componente al Sampler" → escoger tipo → "Crear".
   - En "Configuración global", el TreeItem "Variables (N)" trae un botón `+` → modal "Nueva variable (UDV)".
   - En "Configuración global", el TreeItem "CSV Data Sets" trae un botón `+` → modal "Nuevo CSV Data Set".
4. **Eliminar:** hover sobre cualquier elemento eliminable → aparece botón `🗑` → confirm → desaparece del árbol.
5. El indicador de auto-save (top derecha) debe mostrar "Guardando..." → "Guardado".
6. Al recargar la página, los cambios persisten.

---

## 7. Garantías de no-regresión

- 63/63 tests pre-HF7.A siguen verdes (no se rompió ninguno).
- `tsc --noEmit` → EXIT=0.
- `treeActions` es **opcional** en todas las interfaces nuevas (`TreeViewProps`, `ThreadGroupNodeProps`, `TGChildNodeProps`, `SamplerChildNodeProps`, `TreeItemProps`) — el árbol funciona sin él en cualquier otro call site.
- El refine clásico `/refine` (HF5) y el quirúrgico `/refine-surgical` siguen funcionando intactos. Las 5 ops nuevas son aditivas en el `RefineOp` Union.
- El regenerator del Sprint 2.3a maneja correctamente la rama `is_dirty=True` o `raw_xml=""` que es el camino que toman los elementos creados from-scratch — verificado por el round-trip.

---

## 8. Estado

**LISTO para HF7.B (listeners) o validación visual de Fredy en navegador.**

No se hizo `docker compose build` ni `up`. Backend recargó vía `--reload` de uvicorn dev.

### Notas para HF7.B

- Las operaciones de agregar/eliminar listener ya están parcialmente soportadas:
  - `DeleteElementOp(target_kind="listener", id=...)` ya funciona.
  - El toggle visual de listener ya funciona.
- Falta para HF7.B: `add_listener` (no en el alcance de HF7.A) y la UI para escoger el tipo de listener (View Results Tree, Summary Report, etc.).
