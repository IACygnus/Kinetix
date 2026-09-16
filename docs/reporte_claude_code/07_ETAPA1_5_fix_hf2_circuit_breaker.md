b3cd3d1 · 2026-09-15

# ETAPA 1.5 — Fix HF-2: clasificación de errores y circuit breaker

**Llamadas reales a la IA en este sub-paso: 0** (12 escenarios con stubs y reloj simulado).
2 archivos: `services/ai/gemini.py` y `api/v1/endpoints/ai_config.py`.
**143 inserciones / 12 eliminaciones.** Ningún archivo protegido.

---

## 1. Diagnóstico

### 1.1 El circuito no se cierra nunca — defecto grave

`_circuit_open` aparece en **4 sitios y sólo uno lo pone a `False`**:

| Línea | Uso |
|---|---|
| `gemini.py:838` | declaración `= False` |
| `gemini.py:847` | **único reset**, dentro de `__init__` |
| `gemini.py:885` | lectura (bloquea la llamada) |
| `gemini.py:955` | apertura `= True` |

`__init__` sólo corre cuando `get_gemini_analyzer` **crea una instancia nueva**, y el analizador
es un **singleton de módulo** (`_analyzer_instance`) que sólo se recrea si cambia la clave
`provider:model:key[:8]` (`gemini.py:1610`).

> **Declarado como defecto grave:** con la configuración estable, un único pico de rate-limit
> deja la IA apagada **hasta reiniciar el proceso**. Todo informe posterior sale con texto de
> fallback, y el usuario no tiene forma de recuperarla desde la interfaz.

### 1.2 Falsos positivos de la detección por subcadenas

`gemini.py:921` clasificaba como rate-limit cualquier mensaje que contuviera `"429"`, `"quota"`,
`"rate"` o `"resource"`. Ejemplos reales que caían mal y pagaban **5+10+15 = 30 s** de espera
antes de rendirse:

| Mensaje | Por qué caía | Debería ser |
|---|---|---|
| `Failed to generate response` | contiene `rate` (gene**rate**) | error |
| `resource not found` | contiene `resource` | error |
| `Corporate proxy error` | contiene `rate` (corpo**rate**) | error |
| `fallo simulado no-429` | contiene `429` | error |

El último no es hipotético: **lo produjo mi propio fixture en E1.2** y por eso quedó documentado.

### 1.3 Intentos reales ante un 429

Cliente construido como `OpenAI(api_key=…)` → `max_retries` por defecto del SDK = **2 reintentos**
(3 envíos). Multiplicado por el bucle propio de 3 intentos: **hasta 9 peticiones HTTP** por
sección, de las cuales la telemetría de E1.2 sólo veía 3.

### 1.4 Caminos que comparten el breaker

El estado es **de clase**, así que un solo circuito gobierna: pipeline general, mini-informes por
transacción, consolidado, comparativo, monitoreo, evidencia y visión — todos pasan por
`GeminiAnalyzer._generate`. `script_ai.py` usa su propio `_call_ai` y **no** está sujeto al
breaker. Esto **no cambia el plan**: es el comportamiento deseado (un proveedor caído lo está
para todos) y con D2 ya no es una condena permanente.

---

## 2. Implementación

### D3 — clasificación por tipo/código

```python
def _clasificar_error(err) -> str:
    """'quota_exhausted' | 'rate_limit' | 'error'. Sin heuristicas de texto."""
    ...  # body["code"] == "insufficient_quota"  -> quota_exhausted
    if isinstance(err, _OpenAIRateLimitError):   return "rate_limit"
    if isinstance(err, _OpenAIAPIStatusError):
        return "rate_limit" if err.status_code == 429 else "error"
    if isinstance(err, _GoogleResourceExhausted): return "rate_limit"
    return "error"
```

Clases verificadas contra los SDK **instalados** (`openai 2.54.0`: `RateLimitError`,
`APIStatusError`; `google.api_core.exceptions.ResourceExhausted` presente), importadas con
`try/except` como el resto del módulo.

### D4 — cuota agotada

`insufficient_quota` se mira **antes** que el rate-limit (también es un 429): sin reintentos,
abre el circuito y deja el motivo visible en `_last_error`
(`"gpt-5.5: cuota agotada (insufficient_quota)"`), siguiendo el patrón B6.3.

### D2 + D6 — circuito con enfriamiento y lock

```python
_circuit_opened_at: Optional[float] = None
_probe_in_flight: bool = False
_lock = threading.Lock()          # D6: tras H4 hay varios hilos tocando este estado
```

- `_abrir_circuito(motivo)` — marca el instante (`time.monotonic()`, inmune a cambios de hora).
- `_circuito_bloquea()` — `True` mientras no pasen 60 s; después deja pasar **una sola** llamada
  de prueba (`_probe_in_flight` evita que varios hilos prueben a la vez).
- `_cerrar_circuito()` — lo llama **todo camino exitoso**, así que el circuito se cierra al
  primer acierto.
- `reset_circuit_breaker()` — helper público que `POST /ai-config` invoca al guardar.

### D5 — reintentos sólo propios, respetando `Retry-After`

```python
self._openai_client = OpenAI(api_key=self._api_key, max_retries=0)
...
wait_time = _espera_sugerida(e) or min((attempt + 1) * 5, 15)
```

De hasta 9 peticiones ocultas a **3 intentos, todos visibles en la telemetría**.

### D3 (2ª parte) — errores no-rate-limit

Ya no abren el circuito ni esperan: un fallo puntual de una sección no puede dejar sin IA al
resto del informe.

### D8 — telemetría

Intacta, más el outcome **`quota_exhausted`**. Los demás (`ok`, `empty`, `error`,
`rate_limited`, `circuit_open`, `fallback`) mantienen su significado, así que las corridas 1 y 2
siguen siendo comparables.

---

## 3. Validación — 12/12 escenarios, 0 llamadas reales

`time.sleep` sustituido por un acumulador (reloj simulado): los escenarios de espera se verifican
sin gastar el tiempo real.

| # | Escenario | Resultado |
|---|---|---|
| 1 | `Exception("Failed to generate response")` | **PASA** — `error`, 0 s de espera, circuito cerrado |
| 2 | `Exception("resource not found")` | **PASA** — `error`, 0 s de espera, circuito cerrado |
| 3 | `RateLimitError` transitorio ×3 | **PASA** — 3 intentos, 30 s (5+10+15), circuito abierto |
| 4 | `RateLimitError` con `Retry-After: 7` | **PASA** — respeta 7+7+7 = 21 s en vez de 5/10/15 |
| 5 | `insufficient_quota` | **PASA** — inmediato (0 s), circuito abierto, `_last_error` = `"gpt-5.5: cuota agotada (insufficient_quota)"` |
| 6 | `ResourceExhausted` (Gemini) | **PASA** — clasificado `rate_limit` |
| 7 | Circuito abierto, t < 60 s | **PASA** — `circuit_open` sin llamar al proveedor |
| 8 | Circuito abierto, t ≥ 60 s, prueba OK | **PASA** — llama, devuelve texto y **cierra** |
| 9 | Circuito abierto, t ≥ 60 s, prueba falla | **PASA** — reabre con marca nueva |
| 10 | Guardar config con circuito abierto | **PASA** — `reset_circuit_breaker()` lo cierra y limpia `_last_error` |
| 11 | 2 hilos concurrentes fallando a la vez | **PASA** — 0 excepciones, estado consistente |
| 12 | Camino exitoso | **PASA** — devuelve `'Texto con markdown.'`, saneado igual que antes |

Los escenarios 1, 2 y 4 son exactamente los que **fallaban antes** del cambio: los dos primeros
dormían 30 s para nada; el cuarto ignoraba lo que pedía el proveedor.

`py_compile` OK en los 2 archivos. Recarga de uvicorn confirmada, `GET /health` → 200.

---

## Estado

Sub-paso 1.5 completado. Se continúa con 1.6 (corrida 2, ~35 llamadas reales).

**HF-2 no se puede provocar desde la interfaz** — hace falta que el proveedor devuelva un 429 o
agote la cuota. Su evidencia es esta tabla de 12 escenarios, no una prueba manual.
