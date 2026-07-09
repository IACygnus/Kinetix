# Sprint 2.7c — SYSTEM_PROMPT adaptativo (Parte 3/3, CIERRE)

> Parte 3 de 3 del endurecimiento del Diseñador IA. Cierra el Fix #4 del
> diagnóstico forense `docs/reports/diagnostico-disenador-ia-har-complejo.md`.
> **Fecha:** 2026-06-09

---

## Bug resuelto (Fix #4 del diagnóstico)

El `SYSTEM_PROMPT` estándar empuja **verbosidad ilimitada** (Header Manager +
Response Assertion + Regex Extractor en CADA sampler, comentarios XML, body
inline completo). Con HARs grandes (PeopleSoft, SAP, muchas transacciones) el
output objetivo supera el techo de tokens del modelo y se trunca — la causa
agravante del fallo erpoci.

---

## Estrategia

Selector adaptativo según tamaño/complejidad del input:

| Condición del input | Prompt usado |
|---|---|
| Sin archivo, o archivo ≤20 KB y ≤8 transacciones | `SYSTEM_PROMPT` (estándar, sin cambios) |
| Archivo >20 KB **o** >8 transacciones (`"request"`) | `SYSTEM_PROMPT_CONSERVATIVE` |

`SYSTEM_PROMPT_CONSERVATIVE` instruye **economía de tokens**:
1. Bodies grandes (>500 chars) → envolver en UDV (`${BODY_SAMPLER_N}`), no inline.
2. Headers comunes → UN Header Manager global a nivel Thread Group; locales solo
   para headers extra.
3. Extractors solo si el siguiente sampler usa el valor (no "por si acaso").
4. UNA Response Assertion simple (2xx) por sampler.
5. Cero comentarios XML.
6. Omitir atributos opcionales.
7. Agrupar samplers al mismo endpoint con CSV Data Set en vez de duplicar.

Mantiene la estructura obligatoria y **enfatiza cerrar con `</jmeterTestPlan>`**.

---

## Funciones nuevas — `backend/app/api/v1/endpoints/script_ai.py` (+116 líneas)

| Símbolo | Rol |
|---|---|
| `_LARGE_INPUT_BYTE_THRESHOLD = 20_000` | Umbral de bytes. |
| `_MANY_TRANSACTIONS_THRESHOLD = 8` | Umbral de transacciones (`>` estricto). |
| `SYSTEM_PROMPT_CONSERVATIVE` | Prompt económico para inputs grandes. |
| `_detect_large_input(prompt, file_content)` | Heurística byte + transacciones → `(is_large, reason)`. |
| `_select_system_prompt(prompt, file_content)` | Retorna `(prompt, metadata)`. |

### Integración

Ambos endpoints de generación seleccionan el prompt antes de construir los
mensajes y **loguean el modo elegido** (vía el parámetro `system_prompt` que
`_build_messages` ya aceptaba):

- `/generate` → `_select_system_prompt(body.prompt, None)`.
- `/generate-from-file` → `_select_system_prompt(effective_prompt, raw_text)`
  (`raw_text` = HAR ya comprimido / texto del archivo).

```
logger.info("AI Script Designer /generate-from-file: prompt_mode=%s (%s)", ...)
```

> **Nota sobre la heurística de transacciones:** `.count('"request"')` aplica
> mejor sobre HAR crudo. En `/generate-from-file` el HAR ya viene comprimido,
> donde el disparador principal es el umbral de **bytes** (erpoci: 44 479 B >
> 20 KB → conservador). El umbral de transacciones cubre archivos de referencia
> crudos pequeños en bytes pero con muchas entries.

---

## Tests — `backend/tests/test_script_ai_prompt_selection.py` (nuevo, 74 líneas, 9 tests)

- `_detect_large_input`: sin archivo / pequeño / por bytes / por transacciones /
  borde exacto en el umbral no dispara (5).
- `_select_system_prompt`: estándar para pequeño / conservador para grande (2).
- `SYSTEM_PROMPT_CONSERVATIVE`: menciona economía de tokens / pide JMX cerrado (2).

---

## Validaciones

| Check | Resultado |
|---|---|
| `pytest -m "not slow"` | **157 passed**, 2 deselected |
| Tests nuevos | 9 PASS |
| `npx tsc --noEmit` | **EXIT=0** (sin cambios de frontend) |
| Backend reload | `Application startup complete` |
| Docker rebuild | **NO** |
| Backup | `script_ai.py.bak_27c_20260609_084247` |

---

## Estado: Sprint 2.7 COMPLETO end-to-end

Ver reporte consolidado:
`docs/reports/sprint-2.7-COMPLETO-endurecimiento-disenador-ia.md`.
