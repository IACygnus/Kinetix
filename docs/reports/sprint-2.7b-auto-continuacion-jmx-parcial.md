# Sprint 2.7b — Auto-continuación del JMX parcial (Parte 2/3)

> Parte 2 de 3 del endurecimiento del Diseñador IA. Continúa
> `docs/reports/sprint-2.7a-max-tokens-truncated-detection.md` y resuelve el
> Fix #3 del diagnóstico forense.
> **Fecha:** 2026-06-08

---

## Bug resuelto (de diagnostico-disenador-ia-har-complejo.md, Fix #3)

- Cuando el modelo se cortaba por límite de tokens, los **N samplers ya
  generados se descartaban** (en erpoci: 6 de 10). 2.7a sólo lo reportaba.
- El usuario perdía varios minutos de trabajo del modelo y debía reintentar.

---

## Estrategia

Si `/generate` o `/generate-from-file` detectan truncado (vía `_detect_truncation`
de 2.7a), **antes de devolver el error** intentan **UNA** continuación automática:

1. Extraer el XML parcial del `raw_text` (`_extract_partial_xml`).
2. Construir mensajes de continuación con system prompt minimalista que sólo
   pide el fragmento faltante (`_build_continuation_messages`). Se envía sólo el
   **tail** (≤2000 chars) del parcial + la intención original; **no** se
   reinyecta el archivo de referencia (ya agotó el presupuesto de la 1ª llamada).
3. Llamar al modelo **una vez** (`_call_ai`, mismo provider/modelo/key).
4. Extraer el XML de la continuación (`_extract_continuation_xml`).
5. Ensamblar parcial + continuación (`_assemble_continued_jmx`).
6. Validar que el resultado contenga `</jmeterTestPlan>`.
   - **OK** → cae al flujo de éxito normal (`_parse_jmx` + persistencia), con
     `continued=True` y una `explanation` que avisa "JMX generado en 2 pasos".
   - **Falla** → devuelve el mensaje de truncado de 2.7a + el motivo concreto
     del fallo de continuación.

Máximo **1 continuación por generación** (sin multi-iteración — eso queda fuera
de alcance).

---

## Funciones nuevas — `backend/app/api/v1/endpoints/script_ai.py` (+252 líneas)

| Función | Rol |
|---|---|
| `_extract_partial_xml(raw_text)` | Extrae el XML desde `<?xml` aunque esté truncado; descarta fence de apertura. |
| `_build_continuation_messages(...)` | Prepara `[system, user]` para pedir SOLO el fragmento faltante; envía sólo el tail (≤`_CONTINUATION_CONTEXT_TAIL_CHARS=2000`). |
| `_extract_continuation_xml(raw)` | Saca el XML de la respuesta de continuación (fenced o crudo). |
| `_assemble_continued_jmx(partial, cont)` | Une parcial + continuación en un único documento. |
| `_try_continue_truncated_generation(...)` | Orquesta el flujo; retorna `(jmx, ok, error)`. |

Schema `AIResponse` (+ `FileGenerateResponse` por herencia): nuevo campo
`continued: Optional[bool]`.

### Adaptaciones vs. el guion del sprint

- **`_call_ai` es síncrono y devuelve `str`** (no `async`, no tupla
  `(text, finish_reason)`). `_try_continue_truncated_generation` se implementó
  **síncrona** y llama `_call_ai(...)` directo, igual que ya hacen los endpoints.
- Los endpoints **devuelven modelos Pydantic** (`AIResponse`/`FileGenerateResponse`),
  no `JSONResponse`. La integración respeta ese patrón, conservando los campos
  `file_kind`/`file_content`/`file_name`/`compression_stats` en el path de archivo.

---

## Frontend

**Sin cambios** (Part 6 era opcional). La `explanation` "JMX generado en 2 pasos…"
ya se muestra naturalmente como mensaje del assistant en el chat
(`AIScriptDesigner.tsx`), por lo que el usuario ve la nota informativa sin
necesidad de un panel nuevo. `tsc --noEmit` sigue en EXIT=0.

---

## Tests — `backend/tests/test_script_ai_continuation.py` (nuevo, 130 líneas, 9 tests)

- `_extract_partial_xml`: con fence / sin XML / descarta fence de apertura (3).
- `_extract_continuation_xml`: con fence / sin fence (2).
- `_assemble_continued_jmx`: produce JMX cerrado con una sola apertura (1).
- `_build_continuation_messages`: estructura system/user + límite de tail +
  menciona el archivo sin reinyectar su contenido (3).

> La orquestación `_try_continue_truncated_generation` depende de `_call_ai`
> (OpenAI/Gemini real); su happy-path se valida indirectamente vía los helpers
> que ensambla. Un test E2E con mock de provider puede venir en sprint posterior.

---

## Validaciones

| Check | Resultado |
|---|---|
| `pytest -m "not slow"` | **148 passed**, 2 deselected |
| Tests nuevos | 9 PASS |
| `npx tsc --noEmit` | **EXIT=0** |
| Backend reload | `Application startup complete` (sin errores de import) |
| Docker rebuild | **NO** |
| Backup | `script_ai.py.bak_27b_20260608_204022` |

---

## Costo extra

Hasta **+1 llamada** a OpenAI/Gemini por generación truncada. Sólo se dispara
cuando hay truncación real (`finish_reason=length` → JMX sin cierre). Trade-off
justificado: el usuario recibe un JMX completo en vez de perder los samplers ya
generados.

---

## Estado: LISTO para 2.7c

Pendiente: **2.7c** — SYSTEM_PROMPT adaptativo para HARs grandes / PeopleSoft
(reducir verbosidad / priorizar transacciones críticas) + cierre del Sprint 2.7.
