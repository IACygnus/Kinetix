# Sprint 2.4-HF5.2 — Refine quirúrgico kind-aware

**Fecha:** 2026-05-28
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** Aplicado y validado (1 llamada real OpenAI gpt-4o)

---

## 1. Problema resuelto

En el HF5.1 quedó un bug silencioso: cuando la IA pedía `update_thread_group` con `ramp_time` sobre un TG de tipo **stepping** (kg.apc), el applier seteaba `tg.ramp_time` en el modelo Pydantic — pero el regenerator `_build_stepping_thread_group` **no escribe `ThreadGroup.ramp_time`** en el XML de los TGs stepping (sólo escribe los aliases del `SteppingConfig`: `rampUp`, `flighttime`, `Start users count`, etc.).

Resultado para el usuario: `operations_applied=1`, `explanation` decía "ramp-up cambiado a 45s" — pero el XML descargado seguía teniendo `rampUp=5`. **No había feedback de que el cambio no se reflejó**.

---

## 2. Cambios

### 2.1. Applier (`backend/app/services/engine/refine_operations_applier.py`)

- **Nuevas constantes:**
  - `STANDARD_TO_STEPPING_FIELD_MAP = {"ramp_time": "ramp_up"}` — redirección automática.
  - `STANDARD_ONLY_FIELDS = {"continue_forever"}` — se ignora con warning sobre stepping.
  - `STEPPING_ONLY_FIELDS = {"initial_delay", "start_users_count", "start_users_count_burst", "start_users_period", "ramp_up", "flight_time", "stop_users_count", "stop_users_period"}` — error explícito si se intentan aplicar sobre standard.
- **Nueva función `_normalize_thread_group_fields(tg, fields)`** → retorna `(top_level_fields, stepping_fields, warnings)`:
  - Si la IA envía `{"stepping": {...}}` anidado, se usa tal cual.
  - Si la IA envía `ramp_time` sobre stepping → se redirige a `stepping.ramp_up` con warning.
  - Si la IA envía `start_users_count` sobre standard → `OperationError` explícito (porque convertir el TG entre kinds requiere fallback).
- **Handler `UpdateThreadGroupOp`** reescrito para:
  - Llamar a `_normalize_thread_group_fields`.
  - Aplicar `top_level_fields` al root del TG y `stepping_fields` al `tg.stepping`.
  - Soportar campos por **nombre python** (ej. `ramp_up`) y por **alias XML** (ej. `rampUp`).
  - Loggear warnings vía `logger.info("[refine-applier] ...")` (firma de `apply_operations` se mantiene en 2-tupla para no romper tests existentes).

### 2.2. SYSTEM_PROMPT y resumen de estructura (`backend/app/api/v1/endpoints/script_ai.py`)

- **`_build_structure_summary`** ahora etiqueta cada TG explícitamente como `STANDARD` o `STEPPING` y lista los campos relevantes según el kind:
  - `STANDARD` → `num_threads, ramp_time, loops, on_sample_error`.
  - `STEPPING` → `num_threads, initial_delay, start_users_count, start_users_period, ramp_up, flight_time, stop_users_count, stop_users_period`.
- **`REFINE_SURGICAL_SYSTEM_PROMPT`** amplía la sección de `update_thread_group` con instrucciones explícitas sobre cómo distinguir standard vs stepping y dónde van los campos en cada caso. Ejemplos completos para ambos.

---

## 3. Tests añadidos

5 nuevos en `backend/tests/test_refine_operations.py`:

| Test | Verifica |
|---|---|
| `test_update_ramp_time_en_stepping_se_redirige` | `ramp_time` sobre stepping → `stepping.ramp_up` |
| `test_update_loops_sobre_stepping_no_lanza` | `loops` sobre stepping se acepta (el regenerator lo escribe) |
| `test_update_stepping_field_sobre_standard_lanza_error` | `start_users_count` sobre standard → `OperationError` |
| `test_update_stepping_objeto_anidado_funciona` | `{"stepping": {"ramp_up": 88, "flight_time": 240}}` formato preferido |
| `test_update_num_threads_funciona_en_ambos_kinds` | `num_threads` va al root en ambos kinds |

Adicionalmente, 2 tests existentes (`test_update_thread_group_ramp_time` y `test_multiple_operaciones_orden`) se ajustaron para escoger explícitamente un TG **standard** del fixture en lugar de `thread_groups[0]` (que es "Carga" stepping). Antes pasaban por accidente confiando en el bug; ahora son explícitos sobre qué kind verifican.

---

## 4. Validaciones

### 4.1. Tests backend

```
pytest tests/ -q
55 passed in 1.59s
```

- 27 `test_jmx_parser.py`.
- 15 `test_jmx_regenerator.py`.
- **13 `test_refine_operations.py`** (8 HF5.1 + 5 nuevos HF5.2).

### 4.2. TypeScript check

```
npx tsc --noEmit → EXIT=0
```

Sin cambios en frontend.

### 4.3. Prueba manual end-to-end (1 llamada real OpenAI gpt-4o)

**Payload:** mismo que en HF5.1 — el caso que fallaba silenciosamente.
- `current_jmx`: `Ejercicio_Booking.jmx` (93.439 chars, 3 TGs: 1 stepping + 2 standard, 18 samplers).
- `prompt`: "Cambia el ramp-up del primer Thread Group a 45 segundos".

**Resultado HTTP:**
```
HTTP=200 time=2.706s size=93673B
```

**Response:**
```json
{
  "is_valid": true,
  "fallback_used": false,
  "operations_applied": 1,
  "explanation": "Ramp-up del primer Thread Group cambiado a 45 segundos",
  "error": null,
  "jmx_content": "...<jmeterTestPlan>...</jmeterTestPlan>"   // 89.043 chars
}
```

**Verificación estructural del JMX devuelto:**

| Elemento | Esperado | Real |
|---|---|---|
| 3 Thread Groups | ✅ | "Carga" (stepping), "Smoke test", "Grabación original" |
| 18 HTTPSamplerProxy | ✅ | 18 |
| `rampUp` del SteppingThreadGroup "Carga" | **45** | **45 ✅** |
| `ramp_time` del TG standard "Smoke test" | 1 (sin cambio) | 1 ✅ |
| `ramp_time` del TG standard "Grabación original" | 1 (sin cambio) | 1 ✅ |

**El bug silencioso del HF5.1 quedó arreglado**: la IA, gracias al prompt enriquecido, emitió la operación directamente con `{"stepping": {"ramp_up": 45}}` (no necesitó la redirección automática del applier). El applier sigue siendo la red de seguridad por si una IA distinta envía el formato viejo (`ramp_time`).

---

## 5. Antes / Después

| Aspecto | HF5.1 | HF5.2 |
|---|---|---|
| `ramp_time` sobre stepping TG | Se setea en `tg.ramp_time` (modelo), regenerator lo ignora, bug silencioso | Se redirige a `stepping.ramp_up`, regenerator lo escribe como `<stringProp name="rampUp">` |
| `start_users_count` sobre standard TG | Se aplica al modelo aunque no aplica semánticamente | `OperationError` explícito sugiriendo `fallback_to_full_refine` |
| Visibilidad para la IA del kind del TG | Solo `kind=stepping`/`kind=standard` como texto plano | Marcador `STANDARD`/`STEPPING` explícito + listado de campos válidos por kind |
| Resultado XML para "ramp-up=45" sobre stepping | `rampUp=5` (sin cambio) | **`rampUp=45`** ✅ |
| Tests cubriendo el caso | 0 | 5 nuevos + 2 ajustados explícitos |

---

## 6. Estado

**LISTO para HF6 (límite HAR grande) o validación visual de Fredy en navegador.**

No se hizo `docker compose build` ni `up`. Backend recargó vía `--reload` de uvicorn dev.

### Backups creados

- `backend/app/services/engine/refine_operations_applier.py.bak_hf5_2_20260528_165151`
- `backend/app/api/v1/endpoints/script_ai.py.bak_hf5_2_20260528_165151`
- `backend/tests/test_refine_operations.py.bak_hf5_2_20260528_165151`
