# Sprint 2.7a — Endurecimiento Diseñador IA (Parte 1/3)

> Parte 1 de 3 del endurecimiento del Diseñador IA tras el diagnóstico forense
> `docs/reports/diagnostico-disenador-ia-har-complejo.md` (fallo con el HAR
> PeopleSoft de erpoci.colcomercio.com).
> **Fecha:** 2026-06-08

---

## Bugs resueltos (de diagnostico-disenador-ia-har-complejo.md)

1. **`max_tokens=8192` fijo en `/generate` y `/generate-from-file`** → la
   generación se cortaba a media XML con HARs grandes (gpt-4o soporta 16384).
   Ahora es **dinámico por modelo**.
2. **Asimetría de detección:** solo `/refine` distinguía un JMX truncado; los
   otros dos endpoints devolvían un mensaje engañoso ("Reformula tu prompt o
   revisa el archivo"). Ahora **detectan truncación** con mensaje accionable.
3. **Auto-save destructivo:** `performAutoSave` podía sobrescribir un
   `current_jmx` válido con vacío tras una generación fallida. Ahora **conserva
   el JMX válido previo**.

---

## Cambios backend — `backend/app/api/v1/endpoints/script_ai.py` (+42 líneas)

### Fix A — max_tokens dinámico (`_call_ai`)
El branch sin `max_tokens_override` (paths de generación) pasó de un cap fijo
`8192` a:
```python
effective_max_tokens = OPENAI_MAX_TOKENS.get(model, OPENAI_DEFAULT_MAX_TOKENS)
```
Idéntico al lookup que ya usaba el branch con override (`model_ceiling`). Para
`gpt-4o` resuelve a **16384**; para modelos cuyo techo real es 4096
(gpt-4-turbo, gpt-3.5-turbo) resuelve a su máximo real (antes 8192 los excedía).
El `logger.info("OpenAI call ... max_tokens=%d ... finish_reason=%s")` existente
ya refleja el nuevo valor.

### Fix B — detección de truncado (helper compartido)
Nuevo helper `_detect_truncation(raw_text) -> (is_truncated, partial_samplers, message)`
que porta la lógica de `/refine`:
```python
is_truncated = "<?xml" in raw_text and "</jmeterTestPlan>" not in raw_text
partial_samplers = raw_text.count("<HTTPSamplerProxy")
```
Aplicado en el branch `if not jmx:` de **`/generate`** y **`/generate-from-file`**:
- Si truncado → mensaje específico (cuenta de samplers parciales + 3 soluciones:
  modelo mayor, reducir HAR, pedir menos transacciones) + flags
  `truncated=True` / `partial_samplers=N`.
- Si no → mensaje genérico original (sin cambios).

Schema `AIResponse` extendido con `truncated: Optional[bool]` y
`partial_samplers: Optional[int]` (heredados por `FileGenerateResponse`).

> `/refine` quedó **intacto** (su semántica conserva el JMX actual y su mensaje
> difiere). El helper centraliza solo los dos paths de generación.

---

## Cambios frontend — `frontend/src/pages/AIScriptDesigner.tsx` (+15 líneas)

### Fix C — guard de auto-save
En `performAutoSave`, antes del upsert:
```ts
const isClosedJmx = (s) => !!s && s.includes('</jmeterTestPlan>');
const incomingJmx = overrides?.current_jmx ?? (currentJmx || null);
const jmxToSave = isClosedJmx(incomingJmx)
  ? incomingJmx
  : isClosedJmx(currentJmx) ? currentJmx : incomingJmx;
```
Si la generación entrante no produjo un JMX cerrado pero ya hay uno válido en
estado, **se conserva el válido** en lugar de pisarlo con vacío.

### Part 6 — mensaje de error
- Interface `AIResponse` extendida con `truncated?` y `partial_samplers?`.
- Panel de error con `whitespace-pre-line` para que el mensaje multilínea de
  truncado (cuenta de samplers + soluciones) se lea correctamente. El mensaje
  accionable lo emite el backend; el frontend solo lo muestra.

---

## Tests — `backend/tests/test_script_ai_truncation.py` (nuevo, 113 líneas, 9 tests)

Ejercitan el código real portado (no mocks de endpoint):
- `_detect_truncation`: flagea truncado / ignora completo / ignora texto sin XML
  / cuenta samplers parciales (4 tests).
- `_extract_jmx_and_explanation`: retorna `""` en truncado, JMX en completo (2).
- `OPENAI_MAX_TOKENS`: gpt-4o=16384, default=4096, modelo desconocido→default,
  gpt-4o > 8192 legacy (3).

**Suite: 130 → 139 PASS** (+9), 2 deselected (slow). `tsc --noEmit` EXIT=0.

---

## Validaciones

| Check | Resultado |
|---|---|
| `pytest -m "not slow"` | **139 passed**, 2 deselected |
| Tests nuevos | 9 PASS |
| `npx tsc --noEmit` | **EXIT=0** |
| Backend reload | `Application startup complete` (sin errores de import) |
| Docker rebuild | **NO** (solo reload de código montado) |
| Backups | `*.bak_27a_20260608_165501` (backend + frontend) |

> El log en vivo `max_tokens=16384` aparecerá en la próxima generación real
> contra OpenAI (gpt-4o). La resolución del valor está cubierta por
> `test_openai_max_tokens_for_gpt_4o`. No se disparó una llamada facturada.

---

## Estado: LISTO para 2.7b

Pendiente en las siguientes partes (NO incluido aquí):
- **2.7b** — recuperación / auto-continuación del JMX parcial (los N samplers ya
  generados se reportan pero aún se descartan).
- **2.7c** — SYSTEM_PROMPT adaptativo para HARs grandes / PeopleSoft.
