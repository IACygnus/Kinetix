# Sprint 2.5b — Endpoint smoke-test

**Fecha:** 2026-05-30
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** ✅ Endpoint funcional, validado con diseño real (6/6 samplers OK)

---

## 1. Resumen

Endpoint `POST /api/v1/script-designer/ai/designs/{design_id}/smoke-test` que:
1. Toma el `current_jmx` persistido del diseño.
2. Patchea en memoria a `num_threads=1`, `loops=1`, `scheduler=false`, deshabilita Backend Listener, hace `stopThread=false` en CSVDataSets.
3. Ejecuta `jmeter -n -t patched.jmx -l result.jtl -j jmeter.log` (Sprint 2.5a) en un workdir temporal con timeout configurable (10-300 s).
4. Parsea el JTL CSV con `csv.DictReader`.
5. Devuelve un `SmokeTestResult` con status (`success` | `partial` | `failed` | `error`), métricas agregadas, lista de samplers individuales y los últimos ~3 KB del jmeter.log.
6. Limpia el workdir tras leer el JTL.

---

## 2. Archivos creados / modificados

| Archivo | Tipo | Líneas |
|---|---|---|
| `backend/app/services/engine/jmeter_runner.py` | NUEVO | 222 |
| `backend/app/schemas/smoke.py` | NUEVO | 41 |
| `backend/app/api/v1/endpoints/script_ai.py` | MOD | +175 / -2 (imports + 4 helpers + endpoint) |
| `backend/tests/test_jmeter_runner.py` | NUEVO | 120 |
| `backend/pytest.ini` | NUEVO | 3 (marker `slow`) |

**Backup creado:**
- `backend/app/api/v1/endpoints/script_ai.py.bak_25b_20260530_180122`

---

## 3. Patch de smoke (`patch_jmx_for_smoke`)

Cambios aplicados sobre el JMX en memoria antes de mandarlo a JMeter:

| Elemento | Propiedad | Valor de smoke |
|---|---|---|
| `<ThreadGroup>` | `num_threads`, `ramp_time` | `1` |
| `<ThreadGroup>` | `scheduler` | `false` |
| `<ThreadGroup>` | `duration`, `delay` | vacíos |
| `<ThreadGroup>` LoopController | `loops` | `1` |
| `<ThreadGroup>` LoopController | `continue_forever` | `false` |
| `<kg.apc...SteppingThreadGroup>` | `Start users count`, `rampUp`, `flighttime`, `Start users period`, `Stop users count`, `Stop users period`, `Threads initial delay`, `Start users count burst` | `1` |
| `<BackendListener>` | atributo `enabled` | `"false"` (no enviar smoke a InfluxDB) |
| `<CSVDataSet>` | `stopThread` | `false` (no abortar si falta el CSV) |

---

## 4. Endpoint registrado

```
POST /api/v1/script-designer/ai/designs/{design_id}/smoke-test
  Query param: timeout_sec (10-300, default 60)
  Response model: SmokeTestResult
  Auth: admin | analyst (analyst solo sus propios diseños)
```

### Response schema (`SmokeTestResult`)

```jsonc
{
  "status": "success" | "partial" | "failed" | "error",
  "duration_sec": 5.24,
  "total_samples": 6,
  "successful_samples": 6,
  "failed_samples": 0,
  "samplers": [
    {
      "label": "1. Autenticación - Crear Token",
      "success": true,
      "response_code": "200",
      "response_message": "OK",
      "elapsed_ms": 699,
      "failure_message": null
    }
  ],
  "jmeter_log_tail": "2026-05-30 23:05:33,685 INFO o.a.j.JMeter: Running test ...",
  "error_message": null
}
```

### Mapeo de status

| Caso | status |
|---|---|
| JMeter no arrancó (timeout, FileNotFoundError, etc.) | `error` |
| JMeter corrió pero no produjo samples (JMX sin samplers habilitados) | `failed` |
| Todos los samplers `success=true` | `success` |
| Algunos pasaron, algunos fallaron | `partial` |
| Ningún sampler pasó | `failed` |

---

## 5. Validaciones

### 5.1. Tests backend

```
pytest tests/ -q
82 passed in 5.56s
```

Desglose:
- 76 tests pre-2.5b (sin cambios).
- **5 unit tests nuevos** de `patch_jmx_for_smoke` (rápidos, milisegundos):
  - `test_patch_jmx_for_smoke_reduce_num_threads` ✅
  - `test_patch_jmx_for_smoke_loops_uno` ✅
  - `test_patch_jmx_for_smoke_scheduler_false` ✅
  - `test_patch_jmx_invalido_lanza_error` ✅
  - `test_patch_jmx_deshabilita_backend_listener` ✅
- **1 test slow** marcado `@pytest.mark.slow` que corre `jmeter` real:
  - `test_run_jmeter_smoke_jmx_trivial` ✅ (~5 s)

`pytest.ini` declara el marker `slow` para que `pytest -m "not slow"` lo pueda excluir si se necesita una corrida rápida.

### 5.2. Endpoint registrado

```
POST /api/v1/script-designer/ai/designs/{design_id}/smoke-test
```

### 5.3. Prueba manual end-to-end

Sobre un diseño real con JMX de `restful-booker.herokuapp.com` (6 samplers de CRUD de reservas):

```
HTTP=200 time=5.272s size=3699B
```

Response:
```
status: success
duration: 5.24s
total: 6  ok: 6  fail: 0
error: None
--- samplers ---
[OK] 200 '1. Autenticación - Crear Token'  699ms
[OK] 200 '2. Obtener IDs de Reservas'      514ms
[OK] 200 '3. Crear Reserva'                290ms
[OK] 200 '4. Obtener Reserva por ID'       302ms
[OK] 200 '5. Actualizar Reserva'           252ms
[OK] 201 '6. Eliminar Reserva'              84ms
```

Confirmaciones:
- Subprocess JMeter arrancó OK desde Python.
- El JMX patched ejecutó con 1 usuario / 1 loop (no la carga original del diseño).
- El JTL CSV se generó y se parseó correctamente.
- El log tail llegó al frontend para diagnóstico.
- El workdir temporal se limpió tras leer.

---

## 6. Garantías de no-regresión

- 76/76 tests pre-2.5b siguen verdes.
- No se tocó el binario JMeter ni el Dockerfile (sigue siendo el del Sprint 2.5a).
- El endpoint solo lee de la DB (no escribe) — no modifica el `current_jmx` original.
- El workdir temporal se borra tras leer el JTL, independientemente del éxito/fallo.

---

## 7. Estado

**✅ LISTO para Sprint 2.5c (UI botón "Smoke" en Editor IA).**

### Próximas iteraciones del Sprint 2.5

| Sprint | Capacidad | Estado |
|---|---|---|
| 2.5a | Instalar JMeter + Java + plugins en container | ✅ |
| **2.5b** | Endpoint `smoke-test` que ejecuta el JMX con N=1 | ✅ ESTE SPRINT |
| 2.5c | UI: botón Smoke en Editor IA + panel resultado | ⏳ siguiente |
| 2.5d | Endpoint `/execute` (full run con metrics_collector + JTL persistido) | ⏳ |
| 2.5e | UI: panel de ejecución con progreso live (WebSocket) | ⏳ |

No se hizo `docker compose build`. Backend recargó vía `--reload` de uvicorn dev.
