# HF18a — Guardián de truncación extendido (finish_reason=stop mentiroso)

## Bug crítico resuelto

El Sprint 2.7b detectaba truncación **solo** por `finish_reason="length"`.
gpt-4o presenta un failure mode conocido: con prompts densos y HARs grandes,
el modelo devuelve `finish_reason="stop"` (afirma que terminó) pero corta el
JMX **antes** de `</jmeterTestPlan>`.

Evidencia real: `qa_pideky_com5.har` post-HF17 devolvió:
- `finish_reason=stop`
- 313 líneas de XML
- Sin cierre `</jmeterTestPlan>`
- Auto-continuación **NO** se activó (2.7b solo miraba `length`)
- Frontend intentó parsear XML incompleto → "XML inválido: line 313 col 90"
- UX rota: badge "JMX Inválido" en rojo + botón "Descargar" en verde

Este bug **no es específico de Pideky**: cualquier HAR grande puede disparar el
mismo comportamiento.

## Fix aplicado

### 1. `_detect_truncation` extendido (backend/app/api/v1/endpoints/script_ai.py)

Nueva firma (backward-compatible):

```python
def _detect_truncation(
    raw_text: str,
    finish_reason: str | None = None,
) -> tuple[bool, int, str]:
```

Reconoce 5 casos, devolviendo un `truncation_type` machine-readable como 3er
valor:

| finish_reason | XML | truncation_type | ¿activa continuación? |
|---|---|---|---|
| `length` | sin cierre | `length` (Sprint 2.7a) | Sí |
| `stop` | sin cierre | `stop_mentiroso` (**HF18a**) | Sí |
| `None`/otro | sin cierre | `unknown_no_close` (defensivo) | Sí |
| cualquiera | con cierre | `no_truncation` | No |
| — | sin `<?xml` | `no_xml` | No |

Los tipos `length`, `stop_mentiroso` y `unknown_no_close` disparan
`_try_continue_truncated_generation` del Sprint 2.7b **sin cambios**.

### 2. Cambio de contrato del 3er valor de retorno

**Importante:** en Sprint 2.7a el 3er valor de `_detect_truncation` era el
**mensaje al usuario**. HF18a lo repurposó a `truncation_type` (requerido para
distinguir los casos en logs y tests). El mensaje al usuario se extrajo a un
helper nuevo:

```python
def _truncation_hint_message(partial_samplers: int) -> str:
    # mismo texto que Sprint 2.7a; reconstruido en el failure path de cada endpoint
```

Ambos endpoints (`/generate`, `/generate-from-file`) reconstruyen `trunc_msg`
vía este helper, así que el mensaje que ve el usuario cuando la
auto-continuación falla es **idéntico** al de antes.

### 3. `_call_ai` ahora devuelve `(raw_text, finish_reason)`

Antes retornaba solo `str`. HF18a lo cambió a `tuple[str, str]`:
- **OpenAI:** `completion.choices[0].finish_reason` directo (`"unknown"` si null).
- **Gemini:** su enum `candidates[0].finish_reason` se mapea al vocabulario
  OpenAI — `MAX_TOKENS → "length"`, `STOP → "stop"`, resto → nombre en
  minúsculas. Best-effort (`try/except`, default `"stop"`).

Las 5 llamadas a `_call_ai` se actualizaron:
- `/generate` y `/generate-from-file` → capturan `finish_reason` y lo pasan a
  `_detect_truncation`.
- `_try_continue_truncated_generation`, `/refine` y refine-quirúrgico →
  `raw, _ = _call_ai(...)` (no necesitan finish_reason).

### 4. Logging mejorado

Distingue el tipo de truncación en logs para debug futuro:

```
AI Script Designer /generate: JMX truncado (tipo=stop_mentiroso), intentando auto-continuacion (samplers=3)
```

Permite verificar en producción que el fix se activó ante un "stop mentiroso".

## Compat backward

- La firma antigua sigue funcionando: `_detect_truncation(raw)` (finish_reason
  = None por defecto → un JMX sin cerrar se trata como `unknown_no_close` y
  activa la continuación, igual que Sprint 2.7a).
- El mensaje al usuario es idéntico (vía `_truncation_hint_message`).

## Tests

- **Nuevos:** 7 en `backend/tests/test_hf18a_truncation_detection.py`
  (length, stop_mentiroso, completo+stop, completo+length, sin-xml,
  finish_reason desconocido, compat sin finish_reason).
- **Actualizados:** 3 en `backend/tests/test_script_ai_truncation.py` — el
  cambio de contrato (3er valor: message → type) obligó a reapuntar esas
  aserciones al nuevo tipo y a `_truncation_hint_message`. No cambia el conteo
  de tests (se editaron, no se agregaron/quitaron).
- **Suite completa:** `196 passed, 2 deselected` (los 2 slow). 0 fallos, nada
  roto en Sprint 2.7a/b ni en el resto.
- `tsc --noEmit` EXIT=0 (frontend no tocado).

## Estado

HF18a aplicado. Listo para revalidar con `qa_pideky_com5.har`.

Meta de validación con Fredy:
- Regenerar con mismo HAR y mismo prompt.
- Verificar en logs: `tipo=stop_mentiroso` seguido de `auto-continuacion OK`.
- El JMX resultante **debe** cerrar con `</jmeterTestPlan>`.
- El frontend debe mostrar "JMX Válido".

## Archivos tocados

- `backend/app/api/v1/endpoints/script_ai.py` — `_detect_truncation` extendido,
  `_truncation_hint_message` nuevo, `_call_ai` retorna tupla, 5 call sites +
  2 puntos de detección + logging.
- `backend/tests/test_hf18a_truncation_detection.py` — nuevo (7 tests).
- `backend/tests/test_script_ai_truncation.py` — 3 tests reapuntados al nuevo
  contrato.
- Backup: `script_ai.py.bak_hf18a_20260707_194403`.
