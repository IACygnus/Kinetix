b7930d3 · 2026-09-16

# ETAPA 2.3 — Retiro de Throughput Over Time en backend e IA (D19)

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.
**Ningún archivo protegido tocado** (pantalla y salidas van en 2.6-2.9).
2 archivos: `services/ai/analysis_pipeline.py`, `api/v1/endpoints/upload.py`.

---

## 1. Qué se retira y qué NO

Como se precisó en el reporte 13 y confirmó la autorización:

| Elemento | Acción |
|---|---|
| Llamada de IA `analyze_chart('throughput', …)` | **retirada** |
| Serie `throughput_timeline` | **deja de calcularse**, viaja vacía |
| Campo `ai_analysis_throughput` del resultado | queda `""` para ejecuciones nuevas |
| Columna `ai_analysis_throughput` en `test_executions` | **intacta**, datos históricos conservados |
| **Escalar `throughput` (req/s)** | **INTACTO** — tabla resumen, KPI y prompt de TPS |

---

## 2. Implementación

### 2.1 La llamada de IA — mismo patrón que UI-2

Justo encima del bloque retirado había el precedente: UI-2 hizo exactamente esto con
«Response Time Over Time». Se sigue la misma forma, sustituyendo el bloque por el comentario que
explica por qué ya no está:

```python
# ETAPA 2 (D19): la grafica "Throughput Over Time" se retira del producto
# entero (especificacion v1.2 §1.2), asi que su seccion de IA ya no se
# genera: una llamada menos por analisis. Mismo patron que UI-2 justo
# arriba. El campo queda vacio para ejecuciones nuevas y lo ya guardado en
# DB NO se toca.
#
# OJO: se retira la GRAFICA y su analisis, no la metrica. El escalar
# `metrics['throughput']` (req/s) sigue vivo y lo usan la tabla resumen,
# los KPI y el prompt de TPS de aqui abajo.
```

**No hizo falta tocar la persistencia.** `AIAnalysisResult.ai_analysis_throughput` tiene `""` por
defecto y ya no se asigna, así que `upload.py` guarda cadena vacía por sí solo — igual que lleva
haciendo con `ai_analysis_response_time_over_time` desde UI-2. Menos diff y menos riesgo.

### 2.2 La serie

```python
# ETAPA 2 (D19): "Throughput Over Time" se retira del producto (v1.2 §1.2).
# La serie deja de calcularse y viaja VACIA. El campo se conserva en el
# schema a proposito: la regla de la etapa es ocultar, no borrar, y asi un
# cliente que aun lo lea recibe una lista vacia en vez de un KeyError.
# El escalar `throughput` (req/s) de la tabla resumen NO se toca.
throughput_timeline: List[TimeSeriesPoint] = []
```

**Decisión declarada:** se conserva el campo `throughput_timeline` en el schema `ChartData` en vez
de eliminarlo. La prohibición 0.1 dice «lo que se retira se OCULTA (se deja de generar y de
pintar)»; aplicado al contrato de la API, eso es dejar de poblarlo, no romperlo. Además evita que
un cliente que aún lo lea reviente durante la transición. El coste es un campo permanentemente
vacío, que se puede retirar en una limpieza posterior sin prisa.

### 2.3 Etiquetas de log y docstring

Decían `[1/12]`, `[3-9/12] Analizando 7 graficos`, `[11/12]`, `[11-12/12]` y «Bloque AI (12
secciones…)». Con 10 llamadas eso pasaba a ser información falsa en cada generación, así que se
actualizan: `[1/10]`, `[2/10]`, `[3-8/10] Analizando 6 graficos`, `[+1 opcional]` para
redirecciones (que es condicional y no cabe en una numeración fija) y `[9-10/10]`.

---

## 3. Validación — 15/15, 0 llamadas reales

Analizador espía que registra cada sección pedida, sin tocar la red:

| Comprobación | Resultado |
|---|---|
| **Sin redirecciones → 10 llamadas** | **PASA** |
| **Con redirecciones → 11 llamadas** | **PASA** |
| No se pide `throughput` | PASA |
| No se pide `response_time_over_time` (UI-2) | PASA |
| Siguen pidiéndose las 10: `summary_table`, `errors`, `response_times`, `latency`, `error_rate`, `codes_per_second`, `transactions_per_second`, `active_threads`, `conclusions`, `recommendations` | PASA (10/10) |
| `redirects` aparece **solo** con redirecciones | PASA |

Secuencia observada sin redirecciones:

```
summary_table, errors, chart_response_times, chart_latency, chart_error_rate,
chart_codes_per_second, chart_transactions_per_second, chart_active_threads,
conclusions, recommendations
```

`chart_throughput` ya no aparece entre `response_times` y `latency`, que es donde estaba.

`py_compile` OK en los 2 archivos.

> Nota de método: el fixture necesitó dos correcciones (faltaba
> `get_response_code_distribution` y devolvía un `dict` donde el pipeline espera un DataFrame).
> Ambas eran del doble de prueba, no del código. Se anota porque durante esos intentos el test
> mostraba «5 llamadas», que podría confundirse con un retiro de más.

---

## 4. Lo que queda pendiente de Throughput

Este sub-paso cubre backend e IA. La gráfica **sigue pintándose** hasta sus sub-pasos:

| Dónde | Sub-paso |
|---|---|
| `Dashboard.tsx`, `chartConfig.ts` | 2.6 |
| `export_pdf.py`, `report_generator.py` | 2.7 |
| `export_html.py` | 2.8 |
| `integrated_report.py`, `ExecutionReportSection.tsx` | 2.9 |

Mientras tanto, las ejecuciones nuevas mostrarán la gráfica **vacía** y su caja de análisis
también: la serie va vacía y el texto es `""`. Es transitorio y se cierra en 2.6-2.9.

---

## Estado

Sub-paso 2.3 completado. Se continúa con 2.4 (IA por transacción: 8 → 6).
