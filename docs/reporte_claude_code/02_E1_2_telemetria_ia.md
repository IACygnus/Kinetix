5baee06 · 2026-09-15

# E1.2 — Telemetría por llamada de IA en `_generate`

**Objetivo:** registrar una línea por llamada con latencia y tokens (incluidos los de
razonamiento) para cerrar H1, que E1.1 dejó abierta. **Cero cambio de comportamiento.**

**Llamadas reales a la IA: 0** (verificado por contador del stub en los 6 escenarios).
**Archivo modificado: solo `backend/app/services/ai/gemini.py`.** 49 líneas netas, 0 eliminaciones.

---

## 1. Diagnóstico read-only (Paso 1)

### 1.1 Precondiciones

| Comprobación | Resultado |
|---|---|
| `git branch --show-current` | `backup-trabajo-local` ✓ |
| `git status` | limpio ✓ |
| `git rev-parse --short HEAD` | `5baee06` |
| `docs/ESPECIFICACION-informe.md` línea 3 | `**Versión 1.1 · Aprobada por Fredy Bonilla**` ✓ |

> Nota menor: el enunciado citó el reporte anterior como `01_E1_1_...`; el archivo real es
> `01_E1.1_diagnostico_tiempo_generacion.md` (con puntos). Este reporte sí usa guiones bajos,
> según el nombre pedido.

### 1.2 Líneas de log actuales — ¿identifican la sección?

**Sí.** Todas usan `section_name`, parámetro de `_generate` (línea 871), disponible sin tocar
a los llamadores. **No hace falta E1.2b.**

| Línea | Código |
|---|---|
| `gemini.py:877` | `logger.info(f"AI CIRCUIT OPEN: skipping {section_name} (using fallback)")` |
| `gemini.py:881` | `logger.info(f"AI CALL: provider={self.provider}, model={self.model_name}, section={section_name}, prompt_len={len(prompt)}")` |
| `gemini.py:907` | `logger.error(f"AI EMPTY for {section_name}: {motivo}")` |
| `gemini.py:916` | `logger.info(f"AI OK: section={section_name}, response_len={len(result)}, preview={result[:80]}")` |
| `gemini.py:923` | `logger.warning(f"AI RATE LIMITED (attempt {attempt+1}/{max_retries}) for {section_name}...")` |
| `gemini.py:927` | `logger.error(f"AI ERROR for {section_name}: {error_str}")` |
| `gemini.py:933` | `logger.warning(f"AI UNAVAILABLE: {section_name} - max retries exceeded...")` |

Datos ya disponibles: **nombre de sección** (`section_name`), **prompt_len** (`AI CALL`),
**response_len** (`AI OK`), **número de intento** (`AI RATE LIMITED`).
Lo que **no** existía: latencia por llamada, y **ningún token**.

### 1.3 Llamadores

**`openai_chat_completion`** — 4 llamadores:

| Archivo:línea | Qué consume del retorno |
|---|---|
| `api/v1/endpoints/ai_config.py:433` | `response.choices[0].message.content` |
| `api/v1/endpoints/script_ai.py:1727` | `completion.choices` y `completion.choices[0].finish_reason` |
| `services/ai/gemini.py:890` (`_generate`) | `response.choices[0].message.content`, `finish_reason` |
| `services/ai/gemini.py:970` (`analyze_image`) | `response.choices[0].message.content` |

**`_generate`** — 11 llamadores, todos pasan `section_name`:
`analysis_ai.py:107, 211` · `compare.py:132` · `integrated_report.py:1589, 2041` ·
`gemini.py:1027, 1121, 1197, 1266, 1307, 1430, 1535`.
Todos consumen **solo el `str` devuelto** (con `or ""` en la mayoría).

### 1.4 ¿Qué devuelve `openai_chat_completion`?

**El objeto de respuesta completo** — `return client.chat.completions.create(...)`
(`gemini.py:157, 168, 175`). `finish_reason` se lee en `gemini.py:904` y en `script_ai.py:1736`.

**Consecuencia decisiva:** `response.usage` **ya es accesible dentro de `_generate`** sin tocar
la firma ni el retorno de `openai_chat_completion`. **No se activó ninguna condición de parada:**
no hizo falta ni un parámetro aditivo. `openai_chat_completion` queda **sin modificar**.

### 1.5 Montaje y recarga

```
bind  C:\proyectos\Kinetix\backend -> /app  (rw=true)
Cmd:  uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --timeout-keep-alive 300
```

El código está montado por volumen y uvicorn corre con **`--reload`**: el contenedor ve el
cambio sin rebuild ni restart. (La prueba con stubs, además, se ejecutó en un proceso
`python3` aparte, así que no dependía de la recarga.)

---

## 2. Diff completo

Backup: `backend/app/services/ai/gemini.py.bak_E1.2_20260915_131843`
(cubierto por `.gitignore:163` → `*.bak_*`, no se commitea).

```diff
--- a/backend/app/services/ai/gemini.py
+++ b/backend/app/services/ai/gemini.py
@@ -9,6 +9,8 @@
 import os
 import time
+import json                                      # E1.2: telemetria por llamada
+from datetime import datetime, timezone          # E1.2: marcas de tiempo ISO 8601
 import google.generativeai as genai
 from typing import Dict, List, Optional, Tuple
 import logging
@@ -175,6 +177,35 @@
             **_openai_token_param(model_name, limit), **kwargs)
 
 
+# ===================== E1.2: telemetria por llamada de IA =====================
+# Una linea `AI_TELEMETRY {json}` por INTENTO de `_generate`. Es solo un log:
+# no toca parametros enviados, ni el valor devuelto, ni el control de flujo.
+# Todo va dentro de try/except — un fallo de telemetria jamas interrumpe la
+# generacion. `usage` solo existe en OpenAI; con Gemini los tokens quedan null.
+def _emit_ai_telemetry(section, provider, model, t0, attempt, limit, prompt_chars,
+                       outcome, response=None, finish_reason=None) -> None:
+    """E1.1 dejo abierta H1 por no capturar `usage`; esto es lo que la cierra."""
+    try:
+        fin = datetime.now(timezone.utc)
+        u = getattr(response, "usage", None)
+        ctd = getattr(u, "completion_tokens_details", None)
+        ptd = getattr(u, "prompt_tokens_details", None)
+        logger.info("AI_TELEMETRY %s", json.dumps({
+            "section": section, "provider": provider, "model": model,
+            "ts_start": t0.isoformat(), "ts_end": fin.isoformat(),
+            "latency_ms": round((fin - t0).total_seconds() * 1000),
+            "attempt": attempt, "max_completion_tokens": limit,
+            "prompt_chars": prompt_chars,
+            "prompt_tokens": getattr(u, "prompt_tokens", None),
+            "completion_tokens": getattr(u, "completion_tokens", None),
+            "reasoning_tokens": getattr(ctd, "reasoning_tokens", None),
+            "cached_tokens": getattr(ptd, "cached_tokens", None),
+            "finish_reason": finish_reason, "outcome": outcome,
+        }, default=str, ensure_ascii=False))
+    except Exception:
+        pass   # la telemetria nunca puede tumbar una generacion
+
+
 # Performance tier thresholds (ms)
@@ -841,16 +872,28 @@
         Circuit breaker: if AI was rate-limited once, skip all subsequent calls immediately."""
 
+        # E1.2: `_t0` se reinicia en cada intento; `_tel` solo evita repetir 8 argumentos.
+        _t0 = datetime.now(timezone.utc)
+
+        def _tel(outcome, attempt, response=None, finish_reason=None):
+            _emit_ai_telemetry(
+                section_name, self.provider, self.model_name, _t0, attempt,
+                _openai_max_tokens_for(self.model_name) if self.provider == "openai" else None,
+                len(prompt), outcome, response, finish_reason)
+
         # Circuit breaker — skip immediately if API already proven unavailable
         if GeminiAnalyzer._circuit_open:
             logger.info(f"AI CIRCUIT OPEN: skipping {section_name} (using fallback)")
             GeminiAnalyzer._total_errors += 1
+            _tel("circuit_open", 0)
             return None
 
         logger.info(f"AI CALL: provider={self.provider}, ...")
         GeminiAnalyzer._total_requests += 1
 
         for attempt in range(max_retries):
+            _t0 = datetime.now(timezone.utc)   # E1.2: latencia POR intento
+            response = None
             try:
                 if self.provider == "gemini":
@@ -876,13 +919,20 @@
                         logger.error(f"AI EMPTY for {section_name}: {motivo}")
                         GeminiAnalyzer._last_error = motivo
                         GeminiAnalyzer._total_errors += 1
+                        # E1.2: el caso B6.3 (tope agotado por razonamiento) queda
+                        # visible con sus tokens, que es justo lo que faltaba ver.
+                        _tel("empty", attempt + 1, response, fin)
                         return None
                 else:
                     GeminiAnalyzer._total_errors += 1
+                    _tel("error", attempt + 1)
                     return None
 
                 result = sanitize_ai_text(result)
                 logger.info(f"AI OK: section={section_name}, ...")
+                _tel("ok", attempt + 1, response,
+                     getattr(response.choices[0], "finish_reason", None)
+                     if getattr(response, "choices", None) else None)
                 return result
 
             except Exception as e:
@@ -890,18 +940,21 @@
                     logger.warning(f"AI RATE LIMITED ...")
+                    _tel("rate_limited", attempt + 1)   # E1.2: antes de dormir
                     time.sleep(wait_time)
                     continue
                 else:
                     logger.error(f"AI ERROR for {section_name}: {error_str}")
                     GeminiAnalyzer._last_error = f"{self.model_name}: {error_str[:180]}"
                     GeminiAnalyzer._total_errors += 1
+                    _tel("error", attempt + 1)
                     return None
 
         logger.warning(f"AI UNAVAILABLE: {section_name} - max retries exceeded...")
         GeminiAnalyzer._circuit_open = True
         GeminiAnalyzer._total_errors += 1
+        _tel("fallback", max_retries)
         return None
```

### Por qué no cambia el comportamiento

1. **`git diff` da 49 inserciones y 0 eliminaciones.** Ninguna línea preexistente fue modificada.
2. **Ningún parámetro enviado al modelo cambia.** La llamada
   `openai_chat_completion(client, model, messages, _openai_max_tokens_for(...), temperature=...)`
   está intacta; `openai_chat_completion` no se tocó.
3. **Ningún `return` cambia.** Cada `_tel(...)` va *inmediatamente antes* de un `return` que ya
   existía, y `_tel` no devuelve nada usado.
4. **Ninguna rama de control cambia.** No se añadió ni un `if`, ni un `continue`, ni un `raise`.
5. **`response = None` al inicio del bucle** es puramente defensivo: la variable solo se lee
   dentro de la iteración que la asigna, y tras el bucle no se usa.
6. **Toda la telemetría vive en try/except** (escenario `f` lo demuestra en ejecución).

---

## 3. Resultados de los escenarios (0 llamadas reales)

El script temporal sustituyó `openai.OpenAI`, `get_gemini_analyzer` y `openai_chat_completion`
por dobles que **cuentan invocaciones y lanzan excepción** ante cualquier intento real. El
analizador se construyó con `object.__new__` para no ejecutar el constructor con una key real.
Los scripts se borraron del contenedor al terminar.

| # | Escenario | `outcome` | Tokens capturados | Retorno | ¿Igual que antes? |
|---|---|---|---|---|---|
| a | `finish_reason="stop"`, `usage` completo | `ok` | prompt 1500 · completion 320 · **reasoning 1216** · cached 1024 | `'Texto de prueba.'` | ✓ texto saneado |
| b | `finish_reason="length"`, contenido vacío | `empty` | prompt 1500 · completion 16384 · **reasoning 16384** · cached 0 | `None` | ✓ |
| c | excepción reconocida como 429 | `rate_limited` ×3 + `fallback` | null | `None` | ✓ |
| d | excepción real no-429 | `error` | null | `None` | ✓ |
| e | circuit breaker ya abierto | `circuit_open` | null | `None` | ✓ |
| f | **telemetría rota** (`usage` lanza) | *(ninguna línea)* | — | `'texto ok'` | ✓ **la generación no se ve afectada** |

**Caso crítico (b) resuelto:** el patrón B6.3 — tope agotado por razonamiento y fallback
silencioso — ahora queda visible con `reasoning_tokens=16384` y `finish_reason="length"`.

### Observación sobre el escenario c (no es un cambio, es un hallazgo)

El fixture decía `"fallo simulado no-429"` y entró por la rama de rate-limit **porque el texto
contiene la subcadena `429`**. La condición de `gemini.py:921` busca subcadenas
(`"429"`, `"quota"`, `"rate"`, `"resource"`) en el mensaje de error, así que cualquier excepción
que las contenga por casualidad se trata como rate-limit y **duerme 5+10+15 s**.
Es comportamiento **preexistente** y **no se ha tocado**. Se deja anotado por si E1.3 ve esperas
inesperadas. El escenario `d` cubre el error genuino no-429.

---

## 4. Ejemplo real de línea `AI_TELEMETRY`

```
AI_TELEMETRY {"section": "txreport_conclusions", "provider": "openai", "model": "gpt-5.5",
"ts_start": "2026-09-15T18:20:38.729780+00:00", "ts_end": "2026-09-15T18:20:38.730080+00:00",
"latency_ms": 0, "attempt": 1, "max_completion_tokens": 16384, "prompt_chars": 170,
"prompt_tokens": 1500, "completion_tokens": 320, "reasoning_tokens": 1216,
"cached_tokens": 1024, "finish_reason": "stop", "outcome": "ok"}
```

*(línea del escenario `a`, con `section` reescrita a un nombre real; `latency_ms` es 0 porque el
cliente era un doble en memoria — con la API real llevará el valor de verdad).*

**Nada sensible:** no se registra ni el prompt, ni la respuesta, ni la API key, ni datos del
cliente. Solo `prompt_chars` como tamaño.

---

## 5. Cómo extraer la telemetría (para Fredy y para E1.3)

Volcado crudo:

```bash
docker logs jmeter_backend --timestamps --tail 5000 | grep "AI_TELEMETRY"
```

Solo el JSON, listo para procesar:

```bash
docker logs jmeter_backend --tail 5000 2>&1 | grep -o 'AI_TELEMETRY {.*}' | sed 's/^AI_TELEMETRY //'
```

Resumen por sección (latencia y tokens de razonamiento), sin dependencias externas:

```bash
docker logs jmeter_backend --tail 5000 2>&1 | grep -o 'AI_TELEMETRY {.*}' | sed 's/^AI_TELEMETRY //' \
| docker exec -i jmeter_backend python3 -c "
import sys, json
filas = [json.loads(l) for l in sys.stdin if l.strip()]
print(f'{len(filas)} llamadas')
tot_lat = tot_rz = 0
for f in filas:
    rz = f.get('reasoning_tokens') or 0
    tot_lat += f.get('latency_ms') or 0; tot_rz += rz
    print(f\"{f['section']:30s} {f['outcome']:12s} {f.get('latency_ms'):7} ms  razonamiento={rz}\")
print(f'TOTAL latencia={tot_lat/1000:.1f}s  tokens de razonamiento={tot_rz}')
"
```

Para responder H1 basta comparar, por llamada, `reasoning_tokens` contra `completion_tokens`:
si el razonamiento domina la salida, H1 queda confirmada.

---

## 6. Estado

**Implementado, pendiente validación de Fredy.**

- **El backend en ejecución YA CARGA el cambio**: el código está montado por bind mount y
  uvicorn corre con `--reload`, así que recargó solo al guardar el archivo.
  **No hace falta restart ni rebuild.** Si Fredy prefiere un arranque limpio, la decisión es suya.
- La telemetría **no produce ninguna línea hasta que se ejecute una generación real**, porque
  solo se emite dentro de `_generate`.
- **No se ejecutó E1.3** ni se generó ningún informe.
