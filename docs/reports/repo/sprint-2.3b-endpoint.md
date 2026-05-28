# Sprint 2.3b — Endpoint POST /script-designer/ai/regenerate-jmx

**Fecha:** 2026-05-25
**Estado:** ✅ Completado — 5/5 smoke tests OK, round-trip vía API verificado

## Objetivo

Exponer el regenerador del Sprint 2.3a como endpoint REST. Sin persistencia: recibe `AIScriptStructure` (con flags `is_dirty` marcando ediciones) y devuelve el JMX regenerado.

## Cambios

### Backend

| Archivo | Diff |
|---|---|
| `backend/app/api/v1/endpoints/script_ai.py` | 1121 → 1164 (+43: 1 import + `RegenerateJmxResponse` schema + `regenerate_jmx_endpoint`) |

Backup: `backend/app/api/v1/endpoints/script_ai.py.bak_sprint2_3b_20260525_173431`.

### Import añadido

```python
from app.services.engine.structure_to_jmx import regenerate_jmx_from_structure
```

### Endpoint nuevo

| Verbo | Path | Roles | Request | Response |
|---|---|---|---|---|
| POST | `/api/v1/script-designer/ai/regenerate-jmx` | admin, analyst | `AIScriptStructure` (JSON) | `{jmx_text: str, size_chars: int}` |

Manejo de errores:
- **422:** payload Pydantic-inválido (estructura mal formada).
- **400:** `ValueError` del regenerador (estructura semánticamente inválida — ej. ConfigElement sin raw_xml).
- **500:** cualquier otra excepción + `logger.exception()`.

Sigue el patrón EXACTO de `parse_jmx_endpoint` del Sprint 2.2: `_current_user: User = Depends(require_role(["admin", "analyst"]))` con underscore prefix.

## Smoke tests funcionales (5/5)

| # | Test | HTTP esperado | HTTP real | Resultado |
|---|---|---|---|---|
| 0 | Sin auth | 401/403 | **403** | ✅ |
| 1 | Parse fixture → regenerate (round-trip vía API) | 200 + 89 023 chars + aliases stepping preservados | **200** + 89 023 chars + 5/5 checks OK | ✅ |
| 2 | Edit (`is_dirty=true` en sampler) + regenerate refleja cambio (`/EDITED-FROM-API` aparece) | 200 + edit visible | **200** + edit visible | ✅ |
| 3 | Estructura inválida (`test_plan: "no es un objeto"`) | 422 con `model_attributes_type` | **422** + detail Pydantic | ✅ |
| 4 | Estructura vacía (`{}`) → JMX mínimo | 200 + JMX > 0 | **200** + 846 chars | ✅ |
| 5 | **Round-trip completo vía API** (parse → regen → parse) — conteos idénticos | 200 + 8 métricas iguales | **200** + 8/8 OK | ✅ |

### Detalle Test 1 (regenerate fixture)

```
Parse → HTTP 200, payload: 93 439 chars
Regenerate → HTTP 200, output: 89 023 chars

Aliases en XML regenerado:
  Start users count: YES
  rampUp: YES
  flighttime: YES
  SteppingThreadGroup: YES
  jmeterTestPlan: YES
```

### Detalle Test 2 (edit + regenerate)

```python
# Edición programática del payload antes del POST
ch['sampler']['path'] = '/EDITED-FROM-API'
ch['sampler']['is_dirty'] = True
```

Resultado: HTTP 200, el string `/EDITED-FROM-API` aparece en el JMX regenerado → el flag `is_dirty=true` invalidó el reuse de raw_xml y forzó reconstrucción del sampler.

### Detalle Test 3 (estructura inválida)

```json
{
  "detail": [{
    "type": "model_attributes_type",
    "loc": ["body", "test_plan"],
    "msg": "Input should be a valid dictionary or object to extract fields from",
    "input": "no es un objeto",
    "url": "https://errors.pydantic.dev/2.5/v/model_attributes_type"
  }]
}
```

### Detalle Test 4 (estructura vacía)

`{}` → JMX mínimo válido de 846 chars (solo `<jmeterTestPlan>` + `<TestPlan>` con UDV vacíos). Confirma que el regenerador no rompe ante estructura vacía y que `AIScriptStructure()` tiene defaults sensatos.

### Detalle Test 5 (round-trip completo vía API)

`Ejercicio_Booking.jmx` → parse-jmx → regenerate-jmx → parse-jmx (re-parse del JMX regenerado):

| Métrica | Original (post-parse) | Re-parsed (post-regen) | OK? |
|---|---|---|---|
| Thread Groups | 3 | 3 | ✅ |
| Samplers (recursivo) | 18 | 18 | ✅ |
| CSV Data Sets | 2 | 2 | ✅ |
| UDVs | 4 | 4 | ✅ |
| Listeners | 6 | 6 | ✅ |
| Unmapped | 1 | 1 | ✅ |
| Variables referenced | 10 | 10 | ✅ |
| Variables undefined | 0 | 0 | ✅ |

**8/8 conteos coinciden** — el ciclo completo es idempotente sobre los conteos editables.

## Adaptaciones del prompt original

Cero adaptaciones funcionales. El snippet del prompt se aplicó tal cual. Detalles menores:

- **`logger.exception()`** ya estaba en el patrón del `parse_jmx_endpoint` (Sprint 2.2) — reusado para consistencia.
- **Sin caracteres no-ASCII en docstrings** (`tamano`, `invalido`) — el archivo usa convención sin tildes en docstrings nuevos, consistente con `parse_jmx_endpoint`.

## Decisiones técnicas

- **Response schema con `size_chars`** además del `jmx_text` — facilita al frontend mostrar el tamaño sin tener que recalcular `len()`. Cero costo en backend.
- **AIScriptStructure como body directo** — FastAPI valida automáticamente con Pydantic v2. No hace falta wrapper request.
- **`ValueError → 400`, `Exception → 500`** — mismo contrato que `parse-jmx` para que el frontend pueda manejar errores con un solo bloque catch.

## Endpoints totales del módulo AI Script (Sprint 2.x)

| Verbo | Path | Sprint | Función |
|---|---|---|---|
| POST | `/script-designer/ai/parse-jmx` | 2.2 | JMX → AIScriptStructure |
| POST | `/script-designer/ai/regenerate-jmx` | **2.3b** | AIScriptStructure → JMX |

## Pendientes derivados

- **Sprint 2.4:** frontend Editor IA que consume ambos endpoints. Debe setear `is_dirty=true` en cada campo editado.
- **Sprint 2.5+:** ejecución smoke test con el JMX regenerado.
- **Backlog:** SYSTEM_PROMPT de la IA debe generar UDVs/CSVs cuando referencia variables (bug detectado en Sprint 2.1.1).

## Estado para Sprint 2.4

**LISTO.** El backend del Editor IA está completo: parse + regenerate funcionales, round-trip API verificado byte-conceptual, edit-preserving operativo. El frontend del Sprint 2.4 puede consumir ambos endpoints directamente sin cambios adicionales en backend.
