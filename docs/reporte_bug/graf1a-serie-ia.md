# GRAF1-A — Serie dual avg/max a 1s + máximos al encuadre de la IA

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado y validado por endpoint. **Pendiente: validación visual de Fredy** (criterio único de éxito).
**Alcance:** 5 archivos, **+26 / −12 líneas** (≈19 netas). Presupuesto: 5 archivos / ~25 líneas. Dentro.
**Base:** `docs/reporte_bug/graf1-fix-serie-dual.md` §3 (diseño) y §4 (hallazgo del encuadre).

---

## 1. Qué cambió

| # | Archivo | Δ | Cambio |
|---|---|---:|---|
| 1 | `services/jtl/jtl_parser.py` 🔒 | +7/−3 | `RT_INTERVAL_SECONDS = 1` **local a la serie** + `.agg(['mean','max'])` → columnas `timestamp, value, value_max` |
| 2 | `schemas/test.py` | +1 | `value_max: Optional[float] = None` en `TimeSeriesPoint` |
| 3 | `endpoints/upload.py` | +2 | Propaga `value_max` en el endpoint de charts (guard `'value_max' in label_df.columns`) |
| 4 | `services/ai/analysis_pipeline.py` | +5/−1 | Marca `[PICO: max Nx el promedio]` en `rt_lines` cuando `max/avg ≥ 10` |
| 5 | `services/ai/gemini.py` | +11/−7 | `max=` en las 4 líneas de tier (`build_tier_summary`), variabilidad también por `max/avg > 10x`, e instrucción de considerar avg **Y** max en el prompt de la sección |

**No se tocó** la asignación de tier por `avg` (decisión de producto aparte, §4 del reporte de alcance). El máximo ahora es **visible y mencionable**, no decisorio.

**El intervalo adaptativo del resto de series NO cambió** — `RT_INTERVAL_SECONDS` sólo se usa en el bucle de `response_times_by_label`; timeline, throughput, latencia, error rate, códigos/s y TPS por label siguen con `_calculate_adaptive_interval()`.

Backups: `*.bak_graf1a_20260814_085319` en los 5 archivos. `py_compile` OK en los 5. Backend reiniciado sin build (`Application startup complete`).

---

## 2. Evidencia — validación 1: el máximo real llega al dato

`GET /executions/115346ea-…/charts` → **HTTP 200**, 1.07 MB, **0,96 s**, 4.977 puntos (exactamente los previstos en §5 del reporte de alcance).

Muestra del primer punto:

```json
{"timestamp": "2026-07-31T18:45:50", "value": 360.0, "value_max": 360.0, "label": "token"}
```

**Granularidad:** deltas entre buckets = 1 s en 1.698 de 1.745 saltos; los de 2-3 s son segundos sin muestras (no hay bucket vacío). **Confirmado 1 s.**

### Serie vs JTL crudo

| Transacción | buckets | `max(value)` (avg 1s) | **`max(value_max)`** | **max crudo JTL** | ¿coincide? |
|---|---:|---:|---:|---:|:---:|
| `token` | 1.666 | 7.243 ms | **21.060 ms** | **21.060 ms** | ✅ |
| `Adapter VerifMethod` | 1.650 | 12.110 ms | **21.058 ms** | **21.058 ms** | ✅ |
| `Adapter SendCode` | 1.661 | 353 ms | **388 ms** | **388 ms** | ✅ |

Max crudo calculado sobre el JTL del volumen (`25.773 muestras`, 3 labels) con `max(elapsed)` por label. **Coincidencia exacta en las tres.**

Contra los **2.914 / 6.148 ms** que la serie mostraba antes (3 s avg): los ~21 s existen ahora en el dato. `value_max` está presente en el **100 %** de los puntos de las tres transacciones.

---

## 3. Evidencia — validación 4: el máximo llega al texto de la IA

Renderizado con el pipeline real (`prepare_insights_for_prompt` + `build_tier_summary`) sobre el JTL de Coomeva. **Sin llamar a la IA — cuota intacta.**

```
TOTAL DE TRANSACCIONES ANALIZADAS: 3

=== TIER DEGRADADO (2000-5000ms) - 1 transacciones ===
  Adapter VerifMethod: avg=2941ms, P95=3749ms, P99=4281ms, max=21058ms, errores=54, TPS=4.78

=== TIER EXCELENTE (<500ms) - 2 transacciones ===
  token: avg=443ms, P95=657ms, P99=1070ms, max=21060ms, errores=23, TPS=4.78
  Adapter SendCode: avg=139ms, P95=156ms, P99=179ms, max=388ms, errores=23, TPS=4.76

=== ALERTA: ALTA VARIABILIDAD (P99/avg > 3x o max/avg > 10x) - 1 transacciones ===
  token: avg=443ms vs P99=1070ms (ratio 2.4x), max=21060ms (ratio 47.6x sobre el promedio)

MEJOR TRANSACCION: Adapter SendCode (avg=139ms)
PEOR TRANSACCION: Adapter VerifMethod (avg=2941ms)
```

`rt_lines` (lo que va al prompt de la sección):

```
- token: promedio 443ms, P90 529ms, P95 657ms, P99 1070ms, min 311ms, max 21060ms [PICO: max 48x el promedio]
- Adapter VerifMethod: promedio 2941ms, ... max 21058ms
- Adapter SendCode: promedio 139ms, ... max 388ms
```

### Antes vs después — el hallazgo del §4, corregido

`token` era el caso exacto del reporte de alcance: **tier excelente, y lo peor que la IA veía era P99=1070 ms**.

- **Antes** (`gemini.py.bak_graf1a_…:618`): la línea de tier era `avg=…, P95=…, P99=…, errores=…, TPS=…` — **sin `max`**.
- **Antes** (`:575`): `if tx['avg'] > 0 and tx['p99'] / tx['avg'] > 3` → para `token`, 1070/443 = **2,4x < 3** ⇒ **no entraba en la alerta de variabilidad**.
- **Ahora:** su `max=21060ms` aparece en la línea de tier **y** dispara la alerta con ratio **47,6x**, más el marcador `[PICO: max 48x]` en `rt_lines`.

⚠️ **Límite honesto del umbral:** `Adapter VerifMethod` tiene `max/avg = 7,2x` (< 10), así que **no** dispara la alerta ni el marcador `[PICO]` — pero su `max=21058ms` **sí** es visible en su línea de tier, y la instrucción del prompt pide considerar avg Y max en todas. Si Fredy quiere que también dispare alerta, el umbral 10x es un parámetro de una línea.

---

## 4. Evidencia — validaciones 2 y 3: compatibilidad

**Endpoint / pantalla:** `charts` responde 200 con el esquema válido. `Dashboard.tsx:409` lee `item.value` **exclusivamente** (`timeMap.get(item.timestamp)[key] = item.value`) — ignora el campo nuevo. Ningún consumidor del frontend lee `value_max`.

**Exports (consumidores no migrados):**

| Export | HTTP | Tamaño | Tiempo |
|---|---:|---:|---:|
| HTML (Plotly) | 200 | 466 KB | 0,68 s |
| PDF (WeasyPrint) | 200 | 869 KB | 3,46 s |

PDF válido (`%PDF-1.7`), HTML con sus 16 referencias Plotly. `chart_multiline()` y `apply_top_n_aggregation()` operan por nombre de columna (`'value'`), así que la columna extra pasa sin efecto.

### ⚠️ Corrección a "nada visual cambia"

El prompt asumía que GRAF1-A no cambia nada visual. **No es exacto, y conviene que Fredy lo sepa antes de mirar la pantalla:**

`value` sigue siendo el promedio (semántica intacta, ningún consumidor roto), **pero su intervalo pasó de 3 s a 1 s** — que es lo que exige el diseño §3 aprobado. Al suavizar sobre 1 s en vez de 3 s, el promedio dibujado sube: **el pico visible de `token` pasa de 2.914 a 7.243 ms** y el de `Adapter VerifMethod` de 6.148 a 12.110 ms. La línea será más dentada y con más puntos (1.795 → 4.977).

No es una regresión —es más fiel al crudo— pero **la gráfica del dashboard y de los exports se verá distinta hoy**, sin haber tocado ningún archivo de render. Lo que sigue faltando es la **segunda línea** (los 21 s), que llega en GRAF1-B/C.

**Coste:** payload de la respuesta 3,5x (previsto en §5: 141 → 491 KB para esa serie; total del endpoint 1,07 MB). Endpoint en 0,96 s, exports sin degradación apreciable.

---

## 5. Nota para Fredy — validación real pendiente y cierre de DPERF-1

Lo verificado aquí es que **el número correcto llega al texto que recibe la IA**. Lo que **no** está verificado es que la IA lo *use* — eso sólo se demuestra con un análisis real, y no lo ejecuté para no gastar cuota.

**La validación real es tu próximo análisis de un JTL con timeouts.** Concretamente, el informe debe **mencionar los picos de ~21 s** que hoy omite (hoy diría "tier excelente, picos de hasta 1070 ms" sobre una transacción con 23 timeouts de 21 s). Si el texto sigue sin mencionarlos teniendo `max=21060ms` y la alerta 47,6x delante, el problema ya no es el encuadre sino la redacción del prompt de la sección — y eso sería un GRAF1-A.2 acotado.

**De paso, cronometra ese análisis** (de "Subir" a informe en pantalla): es la medición que falta para **cerrar DPERF-1** con el "después" contra la línea base.

Pendiente en el backlog GRAF1: **B** (2ª línea en el dashboard) y **C** (dual en PDF, HTML e integrado, incluido el 5º consumidor `integrated_report.py` y el `value_max` que `apply_top_n_aggregation` descarta en la serie "Resto" con ≥15 labels).

---

## 6. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- **Ningún análisis IA ejecutado** — cuota intacta. El texto de §3 se generó con los helpers deterministas, sin llamada al modelo.
- Sin `docker compose build`; sólo `docker restart jmeter_backend`.
- Backups `.bak_graf1a_20260814_085319` de los 5 archivos, en su carpeta original.
