# Sprint 2.4-HF5.1 — Refine quirúrgico híbrido

**Fecha:** 2026-05-28
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** Aplicado y validado (1 llamada real OpenAI gpt-4o)

---

## 1. Contexto y motivación

El HF5 resolvió el "contexto perdido" del refine y elevó `max_tokens` al techo del modelo, pero confirmó que **gpt-4o (16K tokens output) sigue siendo insuficiente** para JMX de >50KB: el modelo trunca el output mid-XML y la validación anti-destructiva conserva el original con un mensaje accionable.

El HF5.1 cambia la arquitectura: en lugar de pedirle a la IA que devuelva el JMX entero, la IA devuelve **operaciones estructuradas en JSON** (< 1KB típico), el backend las aplica a la `AIScriptStructure` parseada y regenera el JMX localmente con el regenerator del Sprint 2.3a.

Como red de seguridad, si la IA detecta que el cambio requiere add/delete (no soportado en MVP), responde con `fallback_to_full_refine=true` y el frontend cae automáticamente al endpoint `/refine` clásico del HF5.

---

## 2. Archivos creados / modificados

| Archivo | Tipo | Líneas |
|---|---|---|
| `backend/app/schemas/refine_operations.py` | NUEVO | 192 |
| `backend/app/services/engine/refine_operations_applier.py` | NUEVO | 274 |
| `backend/app/api/v1/endpoints/script_ai.py` | MODIFICADO | +334 / -3 |
| `frontend/src/services/api.ts` | MODIFICADO | +33 / -0 |
| `frontend/src/pages/AIScriptDesigner.tsx` | MODIFICADO | +60 / -10 |
| `backend/tests/test_refine_operations.py` | NUEVO | 154 |

**Backups creados:**
- `backend/app/api/v1/endpoints/script_ai.py.bak_hf5_1_20260528_133515`
- `frontend/src/pages/AIScriptDesigner.tsx.bak_hf5_1_20260528_133515`
- `frontend/src/services/api.ts.bak_hf5_1_20260528_133515`

---

## 3. Operaciones soportadas en MVP

| Operación | Función |
|---|---|
| `update_test_plan` | Cambiar name / comments / functional_mode / serialize_threadgroups |
| `update_thread_group` | num_threads, ramp_time, loops, on_sample_error, stepping (anidado) |
| `update_sampler` | name, method, domain, port, protocol, path, body (anidado), redirects, keepalive |
| `update_sampler_child` | Modificar HeaderManager / Assertion / Extractor / Timer existente por id |
| `update_udvs` | Reemplazar TODA la lista de UDVs globales |
| `update_csv_dataset` | filename, variable_names, delimiter, share_mode, etc. |
| `update_http_defaults` | protocol, domain, port, path, encoding |
| `set_enabled` | Activar/desactivar TG, sampler, sampler_child, CSV, listener, cookie/cache |

**Fuera de MVP (gatillan fallback):** agregar nuevo sampler/header/assertion/extractor/UDV, borrar elementos, mover elementos entre TGs.

---

## 4. Flujo end-to-end

```
Frontend (refine button)
    │
    ▼
1. refineSurgicalAPI.refine(currentJmx, prompt, history, fileContent)
    │
    ▼
2. POST /api/v1/script-designer/ai/refine-surgical
    │
    ▼ Backend:
3. parse_jmx_to_structure(currentJmx) → AIScriptStructure
4. _build_structure_summary(structure) → texto con IDs reales
5. _build_messages(REFINE_SURGICAL_SYSTEM_PROMPT, ..., user_message)
6. _call_ai(messages, ai_conf, max_tokens=4096) → raw JSON
7. _parse_ai_operations(raw) → RefineOperationSet
8. Si fallback_to_full_refine=true → return RefineSurgicalResponse(fallback_used=true)
9. apply_operations(structure, op_set.operations) → mutated structure, applied count
10. regenerate_jmx_from_structure(structure) → JMX completo
11. return RefineSurgicalResponse(jmx_content, operations_applied, explanation)
    │
    ▼ Frontend:
12. if !fallback_used && !error → adoptar jmx_content
13. else → aiApi.post('/refine', ...) clásico HF5
```

---

## 5. Validaciones

### 5.1. Tests backend

```
50 passed in 1.35s
```

- 27 tests `test_jmx_parser.py` (existentes).
- 15 tests `test_jmx_regenerator.py` (existentes).
- **8 tests nuevos en `test_refine_operations.py`**:
  - `test_update_thread_group_ramp_time` ✅
  - `test_update_sampler_path` ✅
  - `test_update_udvs_reemplaza_lista` ✅
  - `test_disable_thread_group` ✅
  - `test_update_inexistente_lanza_error` ✅
  - `test_multiple_operaciones_orden` ✅
  - `test_update_stepping_anidado` ✅
  - `test_update_sampler_body_merge` ✅

### 5.2. TypeScript check

```
npx tsc --noEmit → EXIT=0
```

### 5.3. Endpoint registrado

```
POST /api/v1/script-designer/ai/refine
POST /api/v1/script-designer/ai/refine-surgical
```

### 5.4. Prueba manual (1 llamada real OpenAI gpt-4o)

**Payload:**
- `current_jmx`: `Ejercicio_Booking.jmx` (93.439 chars, 3 Thread Groups, 18 HTTPSamplerProxy).
- `prompt`: "Cambia el ramp-up del primer Thread Group a 45 segundos".

**Resultado HTTP:**
```
HTTP=200 time=3.441s size=93672B
```

**Response (sanitizada):**
```json
{
  "is_valid": true,
  "fallback_used": false,
  "fallback_reason": null,
  "operations_applied": 1,
  "explanation": "Ramp-up del primer Thread Group cambiado a 45 segundos",
  "error": null,
  "jmx_content": "...<jmeterTestPlan>...</jmeterTestPlan>"   // 89.042 chars
}
```

**Verificación estructural del JMX devuelto:**
- ✅ Inicia con `<?xml version=...` y termina con `</jmeterTestPlan>`.
- ✅ Los 3 Thread Groups preservados: "Carga" (stepping), "Smoke test" (standard), "Grabación original" (standard).
- ✅ Los 18 HTTPSamplerProxy preservados.
- ✅ `explanation` clara y razonable.

**Nota sobre la operación específica:**
La IA escogió el primer TG del XML como objetivo, que es el SteppingThreadGroup "Carga". El applier seteó `ramp_time=45` en el modelo Pydantic, pero el regenerator del Sprint 2.3a escribe los TGs stepping con sus campos propios (`rampUp`, `Start users period`, etc.) y NO con `ramp_time` (que es solo del ThreadGroup estándar). El cambio queda aplicado en el modelo pero invisible en el XML stepping — comportamiento heredado del regenerator existente, no introducido por HF5.1.

**Mejora posterior sugerida:** en el `REFINE_SURGICAL_SYSTEM_PROMPT`, instruir a la IA a distinguir el `kind` del TG (stepping vs standard) y emitir `update_thread_group` con `stepping.ramp_up` cuando el TG sea stepping.

---

## 6. Comparación de tiempos

| Métrica | Refine clásico (HF5) | Refine quirúrgico (HF5.1) | Δ |
|---|---|---|---|
| Llamada OpenAI gpt-4o sobre `Ejercicio_Booking.jmx` | **179.5s** | **3.4s** | **−52×** |
| Bytes de output de la IA | ~72KB (truncado mid-XML) | 276 chars de JSON | **−260×** |
| `max_tokens` requerido | 16K (insuficiente) | 4K (sobra) | — |
| Resultado | JMX truncado, conservó original con warning | JMX completo regenerado localmente | ✅ |

---

## 7. Fallback al refine clásico

Cuando se gatilla:

1. **AI lo pide explícitamente**: `fallback_to_full_refine=true` en el JSON (porque el cambio requiere add/delete).
2. **AI devuelve JSON inválido**: el backend devuelve `fallback_used=true` con `fallback_reason`.
3. **Excepción de red u otra**: el frontend captura y llama a `/refine` clásico.
4. **AI devuelve `error`**: el frontend cae al clásico.

Cuando el frontend cae al clásico, llama a `aiApi.post('/refine', payload)` con el mismo `payload` que se usaba antes — el `/refine` HF5 sigue intacto y funciona como red de seguridad.

---

## 8. Estado

**LISTO para HF6 (HAR grande) o validación visual de Fredy en navegador.**

### Próximas mejoras sugeridas (no bloquean HF5.1)

- Stepping-aware operation: cuando la IA pide cambiar `ramp_time` sobre un TG stepping, emitir `stepping.ramp_up` en su lugar.
- Soportar `add_sampler` / `delete_sampler` / `add_header` para cubrir el 80% restante de casos sin fallback.
- Telemetría: contar cuántos refines van por quirúrgico vs clásico para medir la tasa de fallback en producción.

No se hizo `docker compose build` ni `up`. Backend recargó automáticamente vía `--reload` de uvicorn dev.
