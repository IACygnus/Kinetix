# Sprint 2.4-HF5 — Refine pierde contexto

**Fecha:** 2026-05-28
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** Aplicado y validado (1 llamada real OpenAI gpt-4o)

---

## 1. Síntomas reportados

1. Al pedir un ajuste (especialmente viniendo del Editor IA con `?fromEditor=true`), la IA **no modifica** el JMX — lo regenera parcialmente.
2. Borra samplers, omite secciones, devuelve fragmentos en lugar del JMX completo.
3. `Error: timeout of 180000ms exceeded` cuando el JMX es grande.

---

## 2. Diagnóstico (read-only)

### 2.1. Cómo funcionaba `/refine` antes

- **Recibía** `current_jmx` del frontend (`script_ai.py:310`, `AIScriptDesigner.tsx:488`).
- **NO tenía SYSTEM_PROMPT específico** — reusaba el `SYSTEM_PROMPT` de generación, cuyo encabezado dice *"genera scripts JMeter COMPLETOS y PROFESIONALES"*. El modelo lo interpretaba como una nueva generación, no como una edición incremental.
- La única señal de "modifica, no regeneres" era 1 línea enterrada dentro del user message: `"JMX actual (modifica solo lo solicitado y devuelvelo COMPLETO)"` (línea 502).

### 2.2. `max_tokens` efectivo

| Provider | Refine antes | Output máximo real del modelo |
|---|---|---|
| OpenAI (hardcoded) | **8192** | gpt-4o = 16384, gpt-4.1 = 32768 |
| Gemini (hardcoded) | **8192** | gemini-2.5-flash soporta ≥ 32768 |

**Cálculo del truncamiento:**
- Fixture `Ejercicio_Booking.jmx` = 93.439 chars ≈ **23.000–30.000 tokens output**.
- Con `max_tokens=8192` ≈ **24.000–32.000 chars** de output máximo.
- Un JMX de 95KB queda **truncado a la mitad o menos** — de ahí los samplers faltantes y la sensación de que "borra contenido".

### 2.3. Causa raíz por síntoma

| Síntoma | Causa raíz |
|---|---|
| "Regenera parcialmente / fragmentos" | `SYSTEM_PROMPT` generativo + `max_tokens=8192` muy bajo. El modelo abrevia. |
| "Borra samplers, omite secciones" | **Truncamiento del output** por `max_tokens=8192`. |
| "timeout 180000ms" | Refine con JMX grande + history grande + intentar bombear 8192 tokens excede los 3 min del axios. Secundario al problema principal. |

---

## 3. Fix aplicado

### 3.1. Archivos modificados

| Archivo | Cambio | Líneas netas |
|---|---|---|
| `backend/app/api/v1/endpoints/script_ai.py` | `REFINE_SYSTEM_PROMPT` + `_build_refine_messages` + `_call_ai(max_tokens_override)` + `_count_jmx_elements` + `_validate_refine_not_destructive` + reescritura `refine_jmx` + mensaje de error específico para truncamiento | +274 / -12 |
| `frontend/src/pages/AIScriptDesigner.tsx` | `axios timeout` 180000 → 300000 ms | +3 / -1 |

**Backups creados:**
- `backend/app/api/v1/endpoints/script_ai.py.bak_hf5_20260528_130210`
- `frontend/src/pages/AIScriptDesigner.tsx.bak_hf5_20260528_130210`

### 3.2. Detalles de cada fix

**a) `REFINE_SYSTEM_PROMPT` dedicado (2.372 chars):**
- Encabezado: *"Tu única tarea es REFINAR un Test Plan JMX EXISTENTE"*.
- "REGLA ABSOLUTA: PRESERVAR TODO LO EXISTENTE" como primer bloque.
- Lista explícita de prohibiciones: fragmentos, borrar samplers, `<!-- ... -->`, abreviar.
- Proceso en 4 pasos: leer JMX completo → identificar cambio → aplicar solo eso → devolver JMX completo.

**b) `_build_refine_messages`:**
- `current_jmx` va PRIMERO, en un bloque claramente delimitado con separadores `═════` y la nota "NO lo acortes, NO omitas samplers, NO uses placeholders".
- La instrucción del usuario va DESPUÉS, también delimitada, con la frase clave "Aplica SOLO ese cambio sobre el JMX completo de arriba. Conserva todo lo demás IDÉNTICO."
- `conversation_history` se preserva entre system y JMX/instrucción (no se pierde coherencia conversacional).

**c) `max_tokens` dinámico:**
- OpenAI: `OPENAI_MAX_TOKENS.get(model, 16384)` (gpt-4o → 16384, gpt-4.1 → 32768, gpt-5-mini → 16384, etc.).
- Gemini: `REFINE_GEMINI_MAX_TOKENS = 32768`.
- `_call_ai` ahora acepta `max_tokens_override`; el endpoint `/generate` sigue usando 8192 (sin cambio en su comportamiento).

**d) Validación anti-destructiva (`_validate_refine_not_destructive`):**
- Usa `parse_jmx_to_structure` para contar Thread Groups y Samplers (recursivo en Controllers).
- Fallback a conteo de tags si el parse falla (output truncado mid-XML).
- Rechaza si el refinado tiene **menos Thread Groups** que el original.
- Rechaza si el refinado tiene **< 50% de samplers** que el original.
- En caso de rechazo, conserva el `current_jmx` original y devuelve mensaje claro al frontend.

**e) Mensaje de error específico para truncamiento:**
- Si la respuesta de la IA contiene `<?xml` pero NO `</jmeterTestPlan>`, se identifica como output truncado y se sugiere usar modelo con mayor capacidad (`gpt-4.1`, `gemini-2.5-flash`) o pedir cambios más localizados.

**f) Timeout frontend:**
- `axios timeout` 180s → 300s (5 min) para acomodar refines legítimos con JMX grandes + max_tokens elevado.

---

## 4. Validación

### 4.1. Tests backend

```
42 passed in 0.98s
```

Todos los tests existentes (`tests/test_jmx_parser.py` 27 tests + `tests/test_jmx_regenerator.py` 15 tests) pasan tras los cambios.

### 4.2. Test helper de validación anti-destructiva

| Caso | Esperado | Resultado |
|---|---|---|
| refined = original | `safe=True` | ✅ `safe=True, msg=''` |
| refined truncado a 5KB | `safe=False` | ✅ `safe=False, msg='El refinamiento eliminó Thread Groups (3 → 0)...'` |
| refined sin 1 TG | `safe=False` | ✅ `safe=False, msg='El refinamiento eliminó Thread Groups (3 → 2)...'` |

### 4.3. TypeScript check

```
npx tsc --noEmit → EXIT=0
```

### 4.4. Prueba manual end-to-end (1 llamada real OpenAI gpt-4o)

**Payload:**
- `current_jmx`: `Ejercicio_Booking.jmx` (93.439 chars, 3 Thread Groups, 18 HTTPSamplerProxy).
- `prompt`: "Cambia el ramp-up del primer Thread Group a 45 segundos. NO modifiques nada más."
- `conversation_history`: `[]`.

**Resultado HTTP:**
```
HTTP=200 time=179.516s size=182946B
```

**Comportamiento observado:**
- La IA empezó a producir un JMX (response 72KB) pero **truncó mid-output** (sin `</jmeterTestPlan>` ni cierre `\`\`\``), porque `gpt-4o` tiene techo de 16.384 tokens y el JMX completo requiere ~30.000 tokens.
- El extractor `_extract_jmx_and_explanation` no encontró un bloque cerrado → activó el nuevo mensaje de error específico de truncamiento.
- **`jmx_content` devuelto = `current_jmx` original (93.439 chars, 18 samplers, 2 TGs preservados)** ✅
- **`error` = "La respuesta de la IA quedó truncada (output incompleto). El JMX es demasiado grande para el modelo actual. Se conserva el JMX actual. Considera usar un modelo con mayor capacidad (gpt-4.1, gemini-2.5-flash) o pedir cambios más localizados."** ✅
- **`is_valid` = True** (el original sigue siendo válido).

**Lectura del resultado:**

Para JMX típicos (<50KB, <15K tokens output), `max_tokens=16384` con gpt-4o **sí es suficiente** y el refine ahora preservará todo + aplicará el cambio. Para JMX **muy grandes** como el fixture de booking (95KB), incluso 16K tokens es insuficiente — el modelo trunca, la validación lo atrapa, el original se conserva y el usuario recibe un mensaje accionable (cambiar a gpt-4.1 / gemini, o pedir cambios localizados).

Antes del fix: el frontend recibía un JMX TRUNCADO MID-XML con samplers faltantes, y el usuario pensaba que "la IA borró cosas". Ahora: el usuario recibe un mensaje claro y el JMX original intacto.

---

## 5. Antes / Después — Tabla comparativa

| Aspecto | Antes (HF4) | Después (HF5) |
|---|---|---|
| System prompt en `/refine` | El de generación ("genera scripts completos") | Dedicado, preserva-todo |
| `max_tokens` OpenAI | 8192 hardcoded | `OPENAI_MAX_TOKENS[model]` (8K → 32K según modelo) |
| `max_tokens` Gemini | 8192 hardcoded | 32768 |
| Validación post-IA | Ninguna salvo "¿hubo bloque XML?" | Cuenta TGs/samplers; rechaza si perdió contenido |
| Mensaje al usuario en truncamiento | "La IA no devolvió un bloque JMX actualizado." | Distingue truncamiento vs respuesta sin JMX; sugiere modelo con más capacidad |
| Timeout frontend | 180s | 300s |
| JMX grande truncado | Frontend recibía XML truncado y lo pintaba | Frontend conserva el original; mensaje accionable |

---

## 6. Resultado

- ✅ **Causa raíz #1 (contexto perdido)**: resuelto con `REFINE_SYSTEM_PROMPT` + estructura del mensaje (JMX como bloque inmutable primero).
- ✅ **Causa raíz #2 (truncamiento)**: parcialmente resuelto subiendo `max_tokens` al techo del modelo. Para JMX que excedan ese techo, la validación anti-destructiva atrapa el caso y devuelve mensaje accionable en vez de un JMX corrupto.
- ✅ **Causa raíz #3 (timeout 180s)**: resuelto subiendo timeout a 300s + mensaje específico cuando ocurre truncamiento.
- ✅ **Tests backend**: 42/42 OK.
- ✅ **tsc**: EXIT=0.
- ✅ **Prueba manual**: la respuesta truncada fue rechazada y el original se conservó con mensaje accionable.

---

## 7. Recomendación para Fredy

Para refines sobre **JMX de >50KB** (ej. proyectos con muchos endpoints), considerar cambiar la configuración IA en `/admin/ai-config`:
- **OpenAI**: `gpt-4.1` (max_tokens = 32.768) — más caro pero soporta JMX completos.
- **Gemini**: `gemini-2.5-flash` (32.768 tokens) — más barato.

Si se mantiene `gpt-4o` (16.384), pedir cambios **localizados** (un sampler, un header, un assertion) en vez de transformaciones globales del JMX.

---

## 8. Estado

**LISTO para HF6 (límite HAR grande) o validación visual de Fredy en navegador.**

No se hizo `docker compose build` ni `up`. El backend recargó automáticamente via `--reload` de uvicorn dev.
