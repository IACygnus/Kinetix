# HF16 — Body UDV con valor real + Parser dual UDV

## Bugs resueltos (de la validación de Fredy con HAR real)

### Bug 2A: BODY_SAMPLER en UDV con valor vacío → JMeter timeout 60s
- La IA generaba `BODY_SAMPLER_1/2` en UDV pero con `Argument.value` vacío.
- El sampler referenciaba `${BODY_SAMPLER_N}` pero JMeter no podía resolver el
  body → arrancaba, configuraba SSL y quedaba esperando indefinidamente sin
  ejecutar samplers (timeout 60s con 0/0 samplers).
- **Fix:** prompts reforzados (base + conservador) que prohíben UDV vacía y
  exigen el body real completo (o inline si es corto).

### Bug 2B: Parser "5 variables sin definir" cuando SÍ están definidas
- El parser detectaba UDV solo en el bloque `<Arguments testname="User Defined
  Variables">` hermano del TestPlan (**Patrón A**).
- La IA está generando el **Patrón B**: `<elementProp
  name="TestPlan.user_defined_variables" elementType="Arguments">` **embebido**
  dentro del TestPlan, que quedaba sin detectar → `undefined_variables` en falso.
- **Fix:** extractor dual que detecta ambos patrones y los fusiona sin duplicar.

## Diagnóstico: el fix va en BACKEND (Caso A)

El backend parsea el JMX en `backend/app/services/engine/jmx_to_structure.py`
(`parse_jmx_to_structure`) y devuelve `AIScriptStructure`. El frontend
(`AIScriptEditor.tsx`) solo **consume** `structure.metadata.undefined_variables`
y `structure.user_defined_variables` (no re-parsea XML). Por tanto el fix del
parser es 100% backend.

> ⚠️ Nota de archivo protegido: `jmx_to_structure.py` está bajo
> `backend/app/services/engine/` (carpeta protegida, CLAUDE.md §11). HF16
> autoriza explícitamente este fix; el cambio es **quirúrgico y aditivo**
> (+35 líneas, 0 deleciones), no un refactor.

## Cambios

### `backend/app/api/v1/endpoints/script_ai.py` (Bug 2A)
- **SYSTEM_PROMPT_CONSERVATIVE** — el punto "Bodies grandes" (Sprint 2.7c) se
  reemplazó por una **REGLA ABSOLUTA**:
  - Body ≤300 chars → inline en el sampler (no UDV).
  - Body >300 chars → UDV `BODY_SAMPLER_N` **con el body real completo**.
  - **PROHIBIDO** `Argument.value=""`, `"..."`, `"PLACEHOLDER"` o cualquier stub.
  - Si excede 2000 chars y no cabe por tokens → preferir inline (truncado) antes
    que UDV vacía.
  - Sampler con `${BODY_X}` y `BODY_X=""` = **INEJECUTABLE** (timeout con 0 samples).
- **SYSTEM_PROMPT** (base) — nueva sección condensada **"REGLAS DE BODIES
  REALES"**: bodies POST/PUT/PATCH reales y completos, nunca vacíos/placeholders;
  UDV `BODY_SAMPLER_N` vacía deja el script inejecutable.

### `backend/app/services/engine/jmx_to_structure.py` (Bug 2B)
- Nuevo helper `_parse_embedded_test_plan_udv(test_plan_elem)` — extrae UDV del
  slot inline `TestPlan.user_defined_variables` (Patrón B).
- `parse_jmx_to_structure` extrae el Patrón B tras parsear el TestPlan y lo
  **fusiona** con el Patrón A recolectado en el loop, **sin duplicar por nombre**
  (Patrón A gana en colisión, por ser el bloque canónico).

## Tests

`backend/tests/test_udv_extraction.py` (nuevo, **7 tests**):
1. `test_extract_udv_patron_a_arguments_sibling` — Patrón A sigue funcionando (regresión).
2. `test_extract_udv_patron_b_embedded_en_testplan` — Patrón B detectado (HF16 fix).
3. `test_patron_b_no_reporta_falsos_undefined` — vars embebidas referenciadas NO caen en `undefined_variables`.
4. `test_extract_udv_detecta_valor_vacio` — UDV con `Argument.value` vacío → `value == ""`.
5. `test_helper_embedded_udv_directo` — helper directo (con y sin slot embebido).
6. `test_prompt_conservative_prohibe_udv_vacia` — prompt conservador prohíbe UDV vacía.
7. `test_prompt_base_menciona_bodies_reales` — prompt base exige bodies reales.

**Resultado suite:** `179 passed, 2 deselected (slow)` — antes 172 → ahora 179 (+7).
Se corrigió `test_prompt_conservative_menciona_economia` (existente): mi edit
renombró el punto; se restauró la cadena literal "Bodies grandes" en el
encabezado sin tocar el test.

## Validaciones
- Backend: `pytest -m "not slow"` → **179 passed** (172 + 7 nuevos), 2 slow deselected.
- Frontend: `npx tsc --noEmit` → **EXIT=0**.
- `grep -c "vac|placeholder|inejecutable"` en `script_ai.py` → **17** (>2 esperado).
- Correlación (Sprint 2.8) intacta: 74 matches (>5 esperado).
- Sin rebuild Docker (tests corren en el contenedor ya activo).

## Pendiente diferido a HF17 (Parte 5, opcional en HF16)
- **Aviso amarillo (warning UX)** en el frontend cuando una variable ESTÉ
  definida en UDV pero con `value` vacío Y sea referenciada en un sampler.
  Se difiere: es una feature de UI separable del fix del parser (Caso A cierra
  el falso "sin definir"; el aviso de "definida pero sin valor" es un flujo
  nuevo en `AIScriptEditor.tsx`). El refuerzo de prompts (Bug 2A) ya ataca la
  causa raíz del BODY vacío.

## Ground truth de referencia
- `Pideky_Final.jmx` queda documentado como referencia para futuros sprints de calidad.
- Meta actual: 60-70% cobertura vs ground truth.
- Meta futura: comparador automatizado (sprint futuro, fuera de HF16).

## Backups
- `backend/app/api/v1/endpoints/script_ai.py.bak_hf16_20260707_162213`
- `backend/app/services/engine/jmx_to_structure.py.bak_hf16_20260707_162213`

## Estado
HF16 aplicado. **LISTO para validación visual con HAR real (`qa_pideky_com5.har`).**
