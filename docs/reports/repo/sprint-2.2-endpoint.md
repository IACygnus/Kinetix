# Sprint 2.2 — Endpoint POST /script-designer/ai/parse-jmx

**Fecha:** 2026-05-25
**Estado:** ✅ Endpoint completado (4/5 smoke tests OK) — ⚠ Bug en parser detectado por Test 5 (requiere autorización de Fredy para fix, ver Sección "Hallazgo crítico")

## Objetivo

Exponer el parser del Sprint 2.1 como endpoint REST. Sin persistencia: la `AIScriptStructure` se deriva on-demand del JMX recibido.

## Cambios

### Backend

| Archivo | Diff | Cambio |
|---|---|---|
| `backend/app/api/v1/endpoints/script_ai.py` | +35 líneas (1086 → 1121) | 2 imports + `ParseJmxRequest` schema + `parse_jmx_endpoint` |
| `backend/requirements.txt` | +3 líneas | `pytest>=9.0` persistido (deuda Sprint 2.1) |

Backups creados:
- `backend/requirements.txt.bak_sprint2_2_20260525_103951`
- `backend/app/api/v1/endpoints/script_ai.py.bak_sprint2_2_20260525_103951`

### Imports añadidos a `script_ai.py`

```python
from app.schemas.ai_script_structure import AIScriptStructure
from app.services.engine.jmx_to_structure import parse_jmx_to_structure
```

(insertados en bloque alfabético junto a los otros imports `from app.services.*`)

### Schema request (en el mismo archivo, al final)

```python
class ParseJmxRequest(BaseModel):
    jmx_text: str = Field(..., min_length=10, description="Contenido raw del JMX a parsear")
```

### Endpoint nuevo

| Verbo | Path | Roles | Response model |
|---|---|---|---|
| POST | `/api/v1/script-designer/ai/parse-jmx` | admin, analyst | `AIScriptStructure` |

Manejo de errores:
- **422:** payload Pydantic-inválido (jmx_text vacío o < 10 chars).
- **400:** `ValueError` del parser (JMX XML malformado).
- **500:** cualquier otra excepción + log con `logger.exception()`.

Sigue el patrón EXACTO de los demás endpoints del archivo: `_current_user: User = Depends(require_role(["admin", "analyst"]))` con underscore prefix (el endpoint no consume el user object).

## Smoke tests funcionales

| # | Test | HTTP esperado | HTTP real | Resultado |
|---|---|---|---|---|
| 0 | Sin auth | 401/403 | **403** | ✅ |
| 1 | Login + parse fixture `Ejercicio_Booking.jmx` | 200 | **200** | ✅ |
| 2 | JMX inválido (`<not><valid></xml>`) | 400 | **400** | ✅ |
| 3 | Payload vacío (`""`) | 422 | **422** | ✅ |
| 4 | Payload corto (10 chars) | (cubierto por Test 3) | — | — |
| 5 | JMX generado por AI (extraído de DB) | 200 | **500** | ❌ (ver Hallazgo crítico) |

### Métricas del Test 1 (fixture real)

```
test_plan.name: Test Plan
thread_groups: 3
  - Carga (kind=stepping, enabled=True): 6 samplers, 0 controllers
  - Smoke test (kind=standard, enabled=False): 6 samplers, 0 controllers
  - Grabación original (kind=standard, enabled=False): 0 samplers, 1 controllers
csv_data_sets: 2
user_defined_variables: 4
listeners: 6
unmapped top-level: 1
metadata.referenced: 10 / defined: 10 / undefined: []
```

Idéntico a la cobertura del Sprint 2.1 — el endpoint no introduce diferencias semánticas.

### Detalle del Test 2 (JMX inválido)

```json
{"detail": "JMX invalido: JMX XML mal formado: Opening and ending tag mismatch: valid line 1 and xml, line 1, column 19"}
```

### Detalle del Test 3 (payload vacío)

```json
{"detail": [{"type": "string_too_short", "loc": ["body", "jmx_text"], "msg": "String should have at least 10 characters", "input": "", "ctx": {"min_length": 10}}]}
```

## Hallazgo crítico — Bug en el parser (NO en el endpoint)

**Test 5 reveló un bug del parser del Sprint 2.1** que el fixture estándar no cubría.

### Root cause

El JMX generado por la IA (extraído de `ai_script_designs.current_jmx`, 23 351 chars) contiene un comentario XML:

```xml
<!-- Samplers para las operaciones de reserva -->
```

En `lxml`, los Comments se comportan distinto a los Elements:
- `comment.tag` es una `cyfunction` (`<cyfunction Comment at 0x...>`), no un string.
- `comment.get('testclass', '')` retorna `None`, **ignorando el default `""`**.

El parser usa `_testclass_attr(elem)` y luego hace `"HTTPSampler" in testclass` — lo que lanza `TypeError: argument of type 'NoneType' is not iterable` cuando `testclass=None`.

### Stack trace (reproducido)

```
File "/app/app/services/engine/jmx_to_structure.py", line 569, in _parse_tg_children
    if "HTTPSampler" in testclass or "HttpTestSampleGui" in guiclass:
       ^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: argument of type 'NoneType' is not iterable
```

### Fix propuesto (NO aplicado — fuera de scope)

Patch defensivo en `_walk_hashtree_children` o en los helpers `_*_attr`:

```python
# Opción A: filtrar Comments en el walker
def _walk_hashtree_children(hash_tree_elem):
    ...
    for ...:
        if not isinstance(elem.tag, str):  # Comment, PI, etc.
            continue
        ...

# Opción B: defensa en los helpers
def _testclass_attr(elem) -> str:
    return elem.get("testclass", "") or ""  # convierte None → ""
```

La opción A es la correcta (semánticamente preserva los comentarios solo si se quiere, y el resto del parser asume elementos reales).

### Impacto

- **Endpoint funciona en sí mismo:** el `try/except` captura el `TypeError` y devuelve HTTP 500 (no crashea el server).
- **JMX sin comentarios XML:** funciona perfectamente (Test 1).
- **JMX con comentarios XML (típico de IA generators):** falla con HTTP 500.

### Decisión

**NO toqué el parser** porque el prompt del Sprint 2.2 indica explícitamente "NO tocar el parser (Sprint 2.1 cerrado). Solo importarlo." El fix requiere autorización explícita de Fredy.

**Sugerencia:** Sprint 2.1.1 (1 prompt atómico, ≤5 líneas de cambio, test adicional al `test_jmx_parser.py`).

## Decisiones técnicas

- `ValueError` del parser → 400 Bad Request (parser ya lo lanza para XML malformado).
- Excepciones inesperadas → 500 con `logger.exception()` para traceback en logs.
- Sin persistencia: el frontend mantiene `jmx_text` + `structure` en estado local.
- `_current_user` con underscore (sin uso del user object) sigue el patrón del archivo.
- `pytest>=9.0` persistido en `requirements.txt` para no perder la instalación al próximo `docker compose build`.

## Pendientes derivados

- **🔴 Sprint 2.1.1 (URGENTE, bloqueador funcional):** fix de comentarios XML en parser. ≤5 líneas en `_walk_hashtree_children` + 1 test.
- **Sprint 2.3:** regenerador `AIScriptStructure → JMX` + round-trip test.
- **Sprint 2.4:** validar contra segundo JMX (Timers + JSR223).
- **Frontend (Sprint 2.5+):** consumir este endpoint al abrir el Editor IA.
- **Rebuild de Docker (en algún momento):** persistir pytest del Sprint 2.1 efímero. Sin urgencia; el container actual sigue con pytest instalado.

## Estado para Sprint 2.3

**LISTO con caveat documentado.** El endpoint cumple su contrato (4/5 smoke tests passing) y el flujo "AI genera JMX → usuario edita" funcionará desde el frontend para JMX sin comentarios. Para no romper el caso de uso principal (JMX de la propia AI Designer), el Sprint 2.1.1 debe ejecutarse ANTES de que el frontend del Sprint 2.5 consuma este endpoint en producción.
