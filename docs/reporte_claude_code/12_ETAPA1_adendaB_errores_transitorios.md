5e8b863 · 2026-09-15

# ADENDA B — Errores transitorios y timeout del cliente

**Llamadas reales a la IA en este sub-paso: 0.**
Archivo: `services/ai/gemini.py`. **58 inserciones / 3 eliminaciones.** Ningún archivo protegido.

**Regresión que corrige:** D5 (1.5) puso `max_retries=0` para hacer visible cada intento, pero
con eso **desactivó también el reintento de los fallos que sí lo merecen**. Esta adenda recupera
ese comportamiento dentro del bucle propio, donde la telemetría lo ve.

---

## 1. Diagnóstico (read-only)

### 1.1 Qué reintentaba el SDK instalado

`openai 2.54.0`, `BaseClient._should_retry`: **408, 409, 429 y todo ≥ 500**, más los errores de
conexión y timeout. Constantes por defecto: `DEFAULT_MAX_RETRIES = 2`,
`DEFAULT_TIMEOUT = Timeout(connect=5.0, read=600, write=600, pool=600)`.

### 1.2 Cómo los clasificaba `_clasificar_error` ANTES de esta adenda

| Excepción | ¿Reintentaba el SDK? | Clasificación antes | Consecuencia |
|---|---|---|---|
| `APIConnectionError` | sí | **`error`** | sin reintento → fallback |
| `APITimeoutError` | sí | **`error`** | sin reintento → fallback |
| `APIStatusError 408` | sí | **`error`** | sin reintento → fallback |
| `APIStatusError 409` | sí | **`error`** | sin reintento → fallback |
| `APIStatusError 500/502/503` | sí | **`error`** | sin reintento → fallback |
| `ServiceUnavailable` (Gemini) | — | **`error`** | sin reintento → fallback |
| `InternalServerError` (Gemini) | — | **`error`** | sin reintento → fallback |
| `DeadlineExceeded` (Gemini) | — | **`error`** | sin reintento → fallback |
| `APIStatusError 400/401/403/404` | no | `error` | **correcto, no cambia** |

**Siete tipos de fallo recuperable se rendían al primer intento.** Un corte de red de un segundo
dejaba la sección sin texto.

### 1.3 Timeout efectivo del cliente de `GeminiAnalyzer`

`OpenAI(api_key=…, max_retries=0)` → `Timeout(connect=5.0, read=600, …)`.
**Diez minutos de lectura.** Con H4 corregida, una llamada colgada retiene un hilo del pool y el
informe entero se queda esperando por ella.

### 1.4 Clientes NO afectados por D5 — confirmado, no se tocan

| Sitio | Construcción | `max_retries` |
|---|---|---|
| `ai_config.py:69` (test de conexión) | `OpenAI(api_key=api_key)` | 2 (defecto del SDK) |
| `ai_config.py:434` (test de conexión) | `OpenAI(api_key=api_key)` | 2 (defecto del SDK) |
| `script_ai.py:1715` (`_call_ai`) | `OpenAI(api_key=api_key)` | 2 (defecto del SDK) |
| `gemini.py` (`GeminiAnalyzer`) | **el único con `max_retries=0`** | 0 |

D5 sólo tocó el cliente de `GeminiAnalyzer`. Los otros tres conservan el reintento del SDK y
**quedan fuera del alcance de esta adenda**.

---

## 2. Evidencia del defecto, medida ANTES de tocar nada

Los 8 escenarios nuevos, ejecutados contra el código de la adenda A:

```
FALLA | APIConnectionError -> OK: 2 intentos, espera 2 s   | r=None tramos=[]
FALLA | APITimeoutError x3 -> 3 intentos (2 s + 4 s)       | tramos=[] abierto=False
FALLA | APIStatusError 502 -> OK: reintenta                | r=None
PASA  | APIStatusError 400 -> error inmediato
PASA  | APIStatusError 401 -> error inmediato
FALLA | ServiceUnavailable (Gemini) -> OK: reintenta       | r=None
PASA  | prueba del circuito que falla por transitorio
FALLA | cliente con timeout=120                            | read=600
=== 3/8 escenarios PASAN ===
```

Los 3 que ya pasaban confirman que **D12 y la adenda A no necesitaban cambios**: los 4xx ya
fallaban en seco sin abrir el circuito, y el `finally` ya liberaba el flag.

---

## 3. Implementación

### Diff (`git diff -w`, el cambio real sin reindentaciones)

```diff
+# ADENDA B (D9): fallos de red o del servidor que SI merecen reintento. Son los que
+# el SDK reintentaba por su cuenta hasta que D5 le puso max_retries=0; sin esto, una
+# desconexion puntual tumbaba la seccion al primer intento.
+try:
+    from openai import APIConnectionError as _OpenAIAPIConnectionError
+    from openai import APITimeoutError as _OpenAIAPITimeoutError
+except ImportError:
+    _OpenAIAPIConnectionError = _OpenAIAPITimeoutError = None
+try:
+    from google.api_core.exceptions import (
+        ServiceUnavailable as _GoogleServiceUnavailable,
+        InternalServerError as _GoogleInternalServerError,
+        DeadlineExceeded as _GoogleDeadlineExceeded,
+    )
+except ImportError:
+    _GoogleServiceUnavailable = _GoogleInternalServerError = _GoogleDeadlineExceeded = None

+# ADENDA B (D11): el defecto del SDK era read=600 s. Una seccion colgada retenia un hilo
+# diez minutos y el informe entero se quedaba esperando. 120 s sobra: la llamada mas lenta
+# medida en las dos corridas de linea base fue de 15,9 s.
+CLIENTE_TIMEOUT_S = 120.0
+ESPERA_TRANSITORIA_S = 2              # D9: esperas de 2 s y 4 s entre intentos transitorios

-    """'quota_exhausted' | 'rate_limit' | 'error'. Sin heuristicas de texto."""
+    """'quota_exhausted' | 'rate_limit' | 'transient' | 'error'. Sin heuristicas de texto."""

+    # RateLimitError va ANTES que APIStatusError: es subclase suya.
     if _OpenAIRateLimitError is not None and isinstance(err, _OpenAIRateLimitError):
         return "rate_limit"
     if _OpenAIAPIStatusError is not None and isinstance(err, _OpenAIAPIStatusError):
-        return "rate_limit" if getattr(err, "status_code", None) == 429 else "error"
+        estado = getattr(err, "status_code", None)
+        if estado == 429:
+            return "rate_limit"
+        # ADENDA B (D9): los mismos codigos que el SDK reintentaba.
+        if estado in (408, 409) or (isinstance(estado, int) and estado >= 500):
+            return "transient"
+        # D12: el resto de 4xx (400, 401, 403, 404...) es culpa de la peticion.
+        # Reintentar no cambia nada: error seco, sin espera y sin abrir el circuito.
+        return "error"
+    # APITimeoutError es subclase de APIConnectionError; basta comprobar la base.
+    if _OpenAIAPIConnectionError is not None and isinstance(err, _OpenAIAPIConnectionError):
+        return "transient"
     if _GoogleResourceExhausted is not None and isinstance(err, _GoogleResourceExhausted):
         return "rate_limit"
+    transitorias_gemini = tuple(
+        c for c in (_GoogleServiceUnavailable, _GoogleInternalServerError, _GoogleDeadlineExceeded)
+        if c is not None
+    )
+    if transitorias_gemini and isinstance(err, transitorias_gemini):
+        return "transient"
     return "error"

-            self._openai_client = OpenAI(api_key=self._api_key, max_retries=0)
+            self._openai_client = OpenAI(
+                api_key=self._api_key, max_retries=0, timeout=CLIENTE_TIMEOUT_S)

+                    if tipo == "transient":
+                        # ADENDA B (D9): red caida, timeout o 5xx. Son los casos que el SDK
+                        # reintentaba antes de D5; sin este reintento, un corte de un segundo
+                        # dejaba la seccion sin texto. Esperas cortas: 2 s y 4 s.
+                        wait_time = ESPERA_TRANSITORIA_S * (attempt + 1)
+                        logger.warning(f"AI TRANSIENT (attempt {attempt+1}/{max_retries}) ...")
+                        GeminiAnalyzer._last_error = f"{self.model_name}: {error_str[:180]}"
+                        _tel("transient_error", attempt + 1)
+                        # Sin dormir tras el ultimo intento: no queda nada que esperar.
+                        # Con max_retries=3 las esperas son 2 s y 4 s, no 2/4/6.
+                        if attempt + 1 < max_retries:
+                            time.sleep(wait_time)
+                        continue
```

### Decisiones de detalle declaradas

- **`APITimeoutError` no se comprueba por separado**: en el SDK es subclase de
  `APIConnectionError`, así que basta la clase base. El import se mantiene por claridad y por si
  el SDK cambia la jerarquía.
- **Sin espera tras el último intento transitorio.** La rama de `rate_limit` heredada duerme
  también en el tercer intento (5+10+15 = 30 s, comportamiento preexistente que no se toca), pero
  para los transitorios se pidió «2 s y 4 s» y dormir 6 s más antes de rendirse no aporta nada.
- **D10 no necesitó código nuevo**: agotados los 3 intentos, el flujo cae en el bloque de cierre
  del bucle, que ya llama a `_abrir_circuito(motivo)` con enfriamiento y prueba. Es el mismo
  camino que ya usaba `rate_limit`.
- **`_last_error` se actualiza en cada intento transitorio**, para que el motivo quede visible si
  se agotan (patrón B6.3).

---

## 4. Validación — 0 llamadas reales

| Escenario | Resultado |
|---|---|
| `APIConnectionError`, luego OK | **PASA** — 2 intentos, `tramos=[2]`, devuelve texto, circuito cerrado |
| `APITimeoutError` ×3 | **PASA** — `tramos=[2, 4]`, circuito abierto |
| `APIStatusError 502`, luego OK | **PASA** — reintenta y devuelve texto |
| `APIStatusError 400` | **PASA** — error inmediato, 0 s, circuito cerrado, motivo visible |
| `APIStatusError 401` | **PASA** — error inmediato, circuito cerrado |
| `ServiceUnavailable` (Gemini), luego OK | **PASA** — reintenta y devuelve texto |
| Prueba del circuito que falla por transitorio ×3 | **PASA** — reabre con marca nueva, flag liberado |
| Cliente construido | **PASA** — `timeout=120.0`, `max_retries=0` |

**8/8** (eran 3/8 antes del cambio).

### Regresión obligatoria

- **1.5 (HF-2): 12/12 siguen pasando.**
- **Adenda A: 8/8 siguen pasando.**

`py_compile` OK. Uvicorn recargó (`Application startup complete`). `GET /health` → **200**.

---

## 5. Telemetría

Nuevo outcome **`transient_error`**, uno por cada intento transitorio fallido. El resto
(`ok`, `empty`, `error`, `rate_limited`, `quota_exhausted`, `circuit_open`, `fallback`) queda
intacto, así que las corridas de 1.3 y 1.6 siguen siendo comparables con las futuras.

---

## Estado

**Etapa 1 implementada, pendiente validación de Fredy.**
