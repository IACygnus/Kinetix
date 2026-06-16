# Sprint 2.7 — Endurecimiento Diseñador IA (COMPLETO end-to-end)

> Reporte consolidado de los 3 sub-sprints (2.7a / 2.7b / 2.7c).
> **Fecha de cierre:** 2026-06-09

---

## Resumen ejecutivo

Sprint de 3 sub-sprints que endurece el Diseñador IA para funcionar con HARs
grandes y complejos de **cualquier cliente** (PeopleSoft, SAP, web tradicional,
APIs REST/SOAP). Origen: el diagnóstico forense del fallo con
`erpoci.colcomercio.com` (HAR PeopleSoft de 3.5 MB → JMX truncado en el Sampler
6 de 10).

---

## Bugs originales (de diagnostico-disenador-ia-har-complejo.md)

1. `max_tokens=8192` fijo en `/generate` y `/generate-from-file` → truncado con
   HARs grandes (gpt-4o soporta 16384).
2. Asimetría: solo `/refine` detectaba truncado; los otros 2 daban un mensaje
   engañoso.
3. Los N samplers parciales ya generados se descartaban al truncarse.
4. `SYSTEM_PROMPT` empujaba verbosidad ilimitada → agravaba el truncado.
5. Auto-save sobrescribía un `current_jmx` válido con vacío tras fallar.

---

## Sub-sprints completados

### 2.7a — max_tokens dinámico + detección de truncado + auto-save guard
- `_detect_truncation`: helper compartido (portado de `/refine`).
- `_call_ai` sin override usa `OPENAI_MAX_TOKENS.get(model, DEFAULT)` (gpt-4o → 16384).
- Frontend (`AIScriptDesigner.tsx`): `performAutoSave` conserva el JMX válido si
  la nueva generación es vacía/truncada; panel de error con `whitespace-pre-line`.
- **9 tests** (`test_script_ai_truncation.py`).
- Resuelve bugs #1, #2, #5.

### 2.7b — Auto-continuación del JMX parcial
- `_extract_partial_xml`, `_build_continuation_messages`,
  `_extract_continuation_xml`, `_assemble_continued_jmx`,
  `_try_continue_truncated_generation`.
- Si se detecta truncado → **1** llamada de continuación → ensamblar + validar
  cierre `</jmeterTestPlan>`. Éxito → flujo normal con `continued=True`.
- **9 tests** (`test_script_ai_continuation.py`).
- Resuelve bug #3.

### 2.7c — SYSTEM_PROMPT adaptativo
- `_detect_large_input` (heurística byte/transacciones) + `_select_system_prompt`.
- `SYSTEM_PROMPT_CONSERVATIVE` instruye economía de tokens para inputs grandes.
- Logging del modo de prompt en cada generación.
- **9 tests** (`test_script_ai_prompt_selection.py`).
- Resuelve bug #4.

---

## Métricas acumuladas Sprint 2.7

| Métrica | Valor |
|---|---|
| Backend tests | **130 → 157 (+27)** |
| Regresiones | 0 |
| Tests nuevos | 27 (9 + 9 + 9) |
| Funciones/símbolos nuevos en `script_ai.py` | ~12 |
| Campos nuevos en `AIResponse` | `truncated`, `partial_samplers`, `continued` |
| Archivos de producto modificados | 2 (`script_ai.py` + `AIScriptDesigner.tsx`) |
| `script_ai.py` | 2684 → 3094 líneas (+410) |
| Rebuilds Docker | 0 |
| `tsc --noEmit` | EXIT=0 |

> Nota: el guion estimaba +26 tests; el total real es **+27** (se añadió 1 test
> de borde por sub-sprint para cubrir casos límite). Sin impacto en alcance.

---

## Flujo esperado tras Sprint 2.7 (HAR grande tipo erpoci / PeopleSoft)

1. Frontend sube HAR → backend lo comprime → `_select_system_prompt` detecta
   "large input" (>20 KB) → usa `SYSTEM_PROMPT_CONSERVATIVE`.
2. El modelo genera un JMX con tokens económicos, además con el techo real de
   `max_tokens` (16384 en gpt-4o, no 8192).
3. Si **aún** se trunca → backend lo detecta (`_detect_truncation`) y **auto-
   continúa 1 vez** (`_try_continue_truncated_generation`).
4. Continuación OK → JMX completo ensamblado y entregado (`continued=True`).
5. Continuación falla → mensaje específico (usar modelo mayor / reducir HAR /
   pedir menos transacciones), sin pisar ningún JMX válido previo.

---

## Archivos del sprint

**Producto:**
- `backend/app/api/v1/endpoints/script_ai.py`
- `frontend/src/pages/AIScriptDesigner.tsx`

**Tests nuevos:**
- `backend/tests/test_script_ai_truncation.py` (9)
- `backend/tests/test_script_ai_continuation.py` (9)
- `backend/tests/test_script_ai_prompt_selection.py` (9)

**Reportes:**
- `docs/reports/diagnostico-disenador-ia-har-complejo.md` (forense origen)
- `docs/reports/sprint-2.7a-max-tokens-truncated-detection.md`
- `docs/reports/sprint-2.7b-auto-continuacion-jmx-parcial.md`
- `docs/reports/sprint-2.7c-system-prompt-adaptativo.md`
- `docs/reports/sprint-2.7-COMPLETO-endurecimiento-disenador-ia.md` (este)

**Backups:** `script_ai.py.bak_27a_*`, `*.bak_27b_*`, `*.bak_27c_*`,
`AIScriptDesigner.tsx.bak_27a_*`.

---

## Fuera de alcance (sprints futuros)

- **Fix #6 — Generación por lotes** para HARs con >15-20 transacciones únicas
  (cambio arquitectónico: samplers en tandas + ensamblado backend).
- Test E2E de `_try_continue_truncated_generation` con `_call_ai` mockeado.

---

## Estado: SPRINT 2.5 + 2.5.1 + 2.6 + HF14a + HF14b + 2.7 CERRADOS

Listo para **validación visual TOTAL** de Fredy con dataset real (incluye HARs
complejos: erpoci/PeopleSoft, SAP, APIs). La validación visual es el único
criterio de éxito — los checks verdes (tests/tsc) no la sustituyen.
