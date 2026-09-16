7c18eb4 · 2026-09-15

# ETAPA 1.4 — Fix H4: liberar el event loop

**Llamadas reales a la IA en este sub-paso: 0** (validación con stubs).
**Ningún archivo protegido tocado** — verificado con `git diff --name-only` contra la lista.
7 archivos, **42 inserciones / 24 eliminaciones** (las 24 son los sitios de llamada reescritos).

---

## 1. Diagnóstico

Hecho con un **analizador AST**, no con `grep`: recorre cada `.py`, localiza las llamadas a
funciones de IA y comprueba si la función que las contiene es `async def` y si la llamada está
bajo `asyncio.to_thread` / `run_in_executor`.

### Resultado inicial: 36 llamadas bloqueantes dentro de `async def`, **0 en archivos protegidos**

| Archivo | Líneas | Llamada | Función async |
|---|---|---|---|
| `services/ai/analysis_pipeline.py` | 147, 172, 195, 210, 223, 236, 253, 268, 279, 295, 309, 332 | `gemini.analyze_*`, `generate_conclusions`, `generate_recommendations` | `run_ai_and_verdict` |
| `services/ai/analysis_pipeline.py` | 154, 178, 201, 220, 233, 245, 261, 276, 287, 301, 330, 353 | `fallback.*` | `run_ai_and_verdict` |
| `api/v1/endpoints/analysis_ai.py` | 107, 211 | `gemini._generate` | `generate_monitoring_analysis`, `generate_evidence_analysis` |
| `api/v1/endpoints/compare.py` | 132 | `gemini._generate` | `generate_comparison` |
| `api/v1/endpoints/integrated_report.py` | 1589, 2041 | `gemini._generate` | `generate_integrated_report`, `generate_consolidated_analysis` |
| `api/v1/endpoints/script_ai.py` | 1885, 2202, 2349, 2599 | `_call_ai` (sync, `script_ai.py:1673`) | `generate_jmx`, `generate_jmx_from_file`, `refine_jmx`, `refine_jmx_surgical` |
| `api/v1/endpoints/ai_config.py` | 399, 433 | `generate_content`, `openai_chat_completion` | `test_ai_connection` |
| `api/v1/endpoints/upload.py` | 117 | `generate_content` | `test_gemini` |

### Decisión declarada: las 12 de `fallback.*` NO se envuelven

`FallbackAnalyzer` es **cómputo local**: formatea texto a partir de métricas ya calculadas, sin
red ni disco. Bloquea microsegundos. Mandarlas a un hilo añadiría coste de cambio de contexto sin
ganancia. **Se envuelven las 24 que son IA real**, que son las que esperan a la red.

### Otros bloqueos síncronos en los mismos caminos (reportados, NO tocados)

El parseo del JTL con pandas también es síncrono y está en caminos `async`:
`upload.py:159, 381, 393, 403`, `upload.py:732` (`_parse_execution_df`),
`analysis_pipeline.py:450`. Para el JTL de 1,4 MB de la línea base tarda poco frente a los ~12 s
por llamada de IA, pero **con un JTL grande sería el siguiente cuello de botella**.
Queda fuera del alcance de H4: `jtl_parser.py` es archivo protegido y aquí solo se tocan los
puntos de llamada, no el parser.

---

## 2. Implementación (D1)

Transformación uniforme, sin cambiar parámetros, textos, orden ni secuencialidad:

```python
# antes
ai_analysis_summary = gemini.analyze_summary_table(
    summary_df, metrics, test_type=test_type, ...
)
# después
ai_analysis_summary = await asyncio.to_thread(
    gemini.analyze_summary_table,
    summary_df, metrics, test_type=test_type, ...
)
```

Y en las de una sola línea:

```python
-        analysis = gemini._generate(full_prompt, section_name="monitoring_analysis") or ""
+        analysis = await asyncio.to_thread(gemini._generate, full_prompt, section_name="monitoring_analysis") or ""
```

El sufijo `or ""` conserva su semántica: `await` liga más fuerte que `or`, así que sigue siendo
`(await …) or ""`.

`import asyncio` añadido en los 4 archivos que no lo tenían (`analysis_ai.py`, `compare.py`,
`integrated_report.py`, `ai_config.py`). `script_ai.py` y `upload.py` ya lo importaban.

### Diff (extracto; los 24 sitios siguen el mismo patrón)

```diff
--- a/backend/app/services/ai/analysis_pipeline.py
+import asyncio            # ETAPA 1.4 (H4): las llamadas de IA son sincronas
-        ai_analysis_summary = gemini.analyze_summary_table(
+        ai_analysis_summary = await asyncio.to_thread(
+            gemini.analyze_summary_table,
             summary_df, metrics, test_type=test_type,
             acceptance_criteria=acceptance_criteria_dict, insights=insights,
             test_date=test_date, metric_unit=metric_unit,
         )
   (… 11 llamadas más, idéntico patrón: analyze_errors, 7× analyze_chart,
      analyze_redirects, generate_conclusions, generate_recommendations)

--- a/backend/app/api/v1/endpoints/analysis_ai.py
-        analysis = gemini._generate(full_prompt, section_name="monitoring_analysis") or ""
+        analysis = await asyncio.to_thread(gemini._generate, full_prompt, section_name="monitoring_analysis") or ""
-        analysis = gemini._generate(full_prompt, section_name="evidence_analysis") or ""
+        analysis = await asyncio.to_thread(gemini._generate, full_prompt, section_name="evidence_analysis") or ""

--- a/backend/app/api/v1/endpoints/compare.py
-        ai_analysis = gemini._generate(prompt, section_name="comparison_analysis") or ""
+        ai_analysis = await asyncio.to_thread(gemini._generate, prompt, section_name="comparison_analysis") or ""

--- a/backend/app/api/v1/endpoints/integrated_report.py
-            unified = gemini._generate(prompt, section_name="unified_conclusions") or ""
+            unified = await asyncio.to_thread(gemini._generate, prompt, section_name="unified_conclusions") or ""
-            raw = gemini._generate(prompt, section_name=f"consolidated_{test_type}") or ""
+            raw = await asyncio.to_thread(gemini._generate, prompt, section_name=f"consolidated_{test_type}") or ""

--- a/backend/app/api/v1/endpoints/script_ai.py
-        raw_text, finish_reason = _call_ai(messages, ai_conf)
+        raw_text, finish_reason = await asyncio.to_thread(_call_ai, messages, ai_conf)
   (… y las otras 3 de _call_ai)

--- a/backend/app/api/v1/endpoints/ai_config.py
-            response = m.generate_content("Responde solo: OK")
+            response = await asyncio.to_thread(m.generate_content, "Responde solo: OK")
-            response = openai_chat_completion(
+            response = await asyncio.to_thread(
+                openai_chat_completion,
                 client, model, [{"role": "user", "content": "Responde solo: OK"}], _limit,
             )

--- a/backend/app/api/v1/endpoints/upload.py
-        response = model.generate_content("Responde solo: OK FUNCIONANDO")
+        response = await asyncio.to_thread(model.generate_content, "Responde solo: OK FUNCIONANDO")
```

### D6 (lock en el estado de clase) — decisión declarada

**Se aplica en 1.5, no aquí.** El estado a proteger (`_circuit_open`, contadores, marca de
apertura) se reescribe entero en 1.5 al implementar D2/D3/D4. Meter el lock ahora obligaría a
tocar las mismas líneas dos veces y a revisar el diff dos veces. Va donde vive la máquina de
estados.

---

## 3. Validación (0 llamadas reales)

### py_compile — los 7 archivos

```
OK  services/ai/analysis_pipeline.py      OK  api/v1/endpoints/integrated_report.py
OK  api/v1/endpoints/analysis_ai.py       OK  api/v1/endpoints/script_ai.py
OK  api/v1/endpoints/compare.py           OK  api/v1/endpoints/ai_config.py
                                          OK  api/v1/endpoints/upload.py
```

### Re-escaneo AST tras el cambio

**24 → 0 llamadas de IA bloqueantes.** Las 12 que siguen apareciendo son las de `fallback.*`,
comprobadas una a una: todas son `fallback.…`, ninguna `gemini.…`.

### Prueba del event loop

Analizador falso que bloquea **2 s síncronos** por llamada (3 llamadas = 6 s) y una corrutina
que debe latir cada 100 ms:

```
--- ANTES del fix (llamada sincrona directa) ---
sin to_thread: duracion=6.0s  ticks=0/59   hueco_max=6000 ms  *** LOOP BLOQUEADO ***
--- DESPUES del fix (envuelta en to_thread) ---
con to_thread: duracion=6.0s  ticks=60/59  hueco_max=101 ms   OK (loop libre)

latidos:      0/59  ->  60/59
hueco maximo: 6000 ms  ->  101 ms
=== LLAMADAS REALES A LA IA: 0 ===
```

Antes el reloj **no latió ni una vez** en 6 segundos: inanición total, no un hueco grande.
Después late 60 veces con un hueco máximo de 101 ms, que es el periodo nominal.

> Nota de método: la primera versión de esta prueba calculaba el hueco como `max(marcas)` y con
> la lista vacía daba `0 ms`, etiquetando el caso bloqueado como "OK". Se corrigió para que
> **cero latidos cuente como bloqueo de toda la duración**, que es lo que realmente ocurre.

### Recarga y salud del backend

```
WARNING: WatchFiles detected changes in 'analysis_ai.py', 'ai_config.py', 'compare.py',
         'integrated_report.py'. Reloading...
INFO:    Started server process [22763]
INFO:    Application startup complete.
```

`GET /health` → **200** en 3,4 ms · `GET /auth/me` → **401** en 49 ms (correcto sin cookie).

---

## Estado

Sub-paso 1.4 completado. El efecto sobre la sonda `/auth/me` se medirá en la corrida de 1.6:
la referencia a batir es el **máximo de 54,9 s** registrado en 1.3.

Se continúa con 1.5 (clasificación de errores y circuit breaker).
