# N4.2 — Diagnóstico read-only: qué dato existe hoy para el mini-informe por transacción

**Fecha:** 2026-08-18
**Estado:** **DIAGNÓSTICO. NO SE ESCRIBIÓ CÓDIGO.** `git status` cierra sin una
sola modificación de código (§9).
**Llamadas de IA:** **0.** Todas las mediciones son de parseo, agrupación y
serialización local.
**Datos de la medición:** `resultados_general_carga  31-jul.-2026-134550.jtl`
— Coomeva, **25.773 muestras**, 3 transacciones, 1.800 s de duración.

---

## 1. Series que existen HOY en `get_all_charts_data()`

`jtl_parser.py:451-515` (**PROTEGIDO — solo lectura**). El método produce ocho
datasets. Solo **dos** están agrupados por transacción:

| Dataset | Agrupación | Bucket | Agregación |
|---|---|---|---|
| `response_times_by_label` | **por label** | **1 s fijo** (GRAF1-A) | `mean` + `max` (dual) |
| `tps_by_label` | **por label** | adaptativo (**3 s** en este JTL) | `count / intervalo` |
| `timeline` | global | adaptativo | avg_rt, avg_latency, throughput |
| `throughput_timeline` | global | adaptativo | derivada de `timeline` |
| `latency_timeline` | global | adaptativo | derivada de `timeline` |
| `error_rate_timeline` | global | adaptativo | derivada de `timeline` |
| `active_threads_timeline` | global | adaptativo | derivada de `timeline` |
| `codes_per_second` | **por código HTTP**, no por label | adaptativo | `count / intervalo` |

**Respuesta directa a la pregunta:** **latencia, tasa de error y códigos de
respuesta NO existen por transacción.** Las tres se calculan una sola vez sobre
el DataFrame completo (`get_timeline_data()`, `jtl_parser.py:388-423`) y
`codes_per_second` agrupa por `responseCode`, nunca por `label`. No hay forma de
derivar la serie de una transacción a partir de lo que hoy devuelve el endpoint:
el dato ya viene sumado sobre todas.

### 1.1 Tabla: existentes vs por calcular (las 5 gráficas del mini-informe)

| Gráfica del mini-informe | ¿Existe por transacción? | De dónde sale |
|---|---|---|
| Tiempos de respuesta (avg + max) | ✅ **Sí** | `response_times_by_label`, 1 s, ya con `value_max` |
| Transacciones por segundo | ✅ **Sí** | `tps_by_label`, bucket adaptativo |
| **Latencia** | ❌ **No** | hay que agrupar `Latency` por `label` + bucket |
| **Tasa de error** | ❌ **No** | hay que agrupar `success` por `label` + bucket |
| **Códigos de respuesta** | ❌ **No** | hay que agrupar `responseCode` por `label` + bucket |

**Balance: 2 existen, 3 hay que calcular.**

---

## 2. ¿El DataFrame tiene con qué calcularlas? Sí, y es barato

Columnas del JTL de Coomeva ya parseado, **cobertura del 100 % en las tres
necesarias**:

| Columna | dtype | No nulos |
|---|---|---|
| `Latency` | `int64` | 25.773 / 25.773 (100 %) |
| `success` | `bool` | 25.773 / 25.773 (100 %) |
| `responseCode` | `object` | 25.773 / 25.773 (100 %) |
| `label`, `timestamp`, `elapsed` | — | 100 % |

No hace falta tocar el parser ni volver a leer el JTL con otro esquema: las tres
columnas ya viajan en `self.df` y en `self.df_main`.

### 2.1 Coste medido de agrupar (mejor de 5 corridas, bucket 1 s, 3 transacciones)

| Serie | Tiempo | Puntos | JSON |
|---|---|---|---|
| `response_times_by_label` *(ya existe, como referencia)* | 31,7 ms | 4.977 | 510,5 KB |
| `latency_by_label` **(nueva)** | **21,6 ms** | 4.977 | 411,5 KB |
| `error_rate_by_label` **(nueva)** | **19,2 ms** | 4.977 | 381,7 KB |
| `codes_by_label` **(nueva)** | **35,5 ms** | 5.076 | 466,7 KB |

**El cálculo no es el problema: las tres series nuevas cuestan 76 ms sobre
25.773 muestras.** Para contexto, `parse()` completo tarda 0,2 s y
`get_all_charts_data()` entero tarda 468 ms. **El problema es el tamaño de lo
que sale.**

---

## 3. Tamaño del payload — aquí está el riesgo real

### 3.1 Lo que pesa hoy `/executions/{id}/charts` (3 transacciones)

| Bloque | Puntos | JSON |
|---|---|---|
| `response_times_by_label` | 4.977 | 510,5 KB |
| `tps_by_label` | 1.795 | 154,2 KB |
| `codes_per_second` | 676 | 54,3 KB |
| `throughput_timeline` | 600 | 31,0 KB |
| `latency_timeline` | 600 | 37,9 KB |
| `error_rate_timeline` | 600 | 31,4 KB |
| `active_threads_timeline` | 600 | 30,9 KB |
| **TOTAL series temporales** | **9.848** | **850,2 KB** |

**Sin compresión.** `main.py` solo monta `CORSMiddleware`: **no hay
`GZipMiddleware`**, así que estos bytes viajan tal cual por la red.

### 3.2 Lo que añadirían las 3 series nuevas por label, a 1 s (GRAF1)

| Transacciones | Tiempo de cálculo | Puntos nuevos | JSON nuevo | Sobre el payload actual |
|---|---|---|---|---|
| 1 | 25 ms | 5.321 | **412,7 KB** | +49 % |
| **3** | 44 ms | 15.030 | **1.259,9 KB** | **+148 %** |
| 10 | 97 ms | 39.613 | **2.957,3 KB** | +348 % |
| **20** | 158 ms | 57.831 | **4.291,5 KB** | +505 % |

*(Escalado con las mismas 25.773 muestras repartidas en N etiquetas sintéticas:
el escenario real de "el mismo test, con más transacciones". El número de puntos
lo manda la duración, no el volumen: 1.800 s → ~1.700 buckets por serie y por
transacción.)*

**Y hay un efecto que se suele olvidar:** con 20 transacciones no solo crece lo
nuevo, también crece lo que ya existe. `response_times_by_label` pesa 170 KB por
transacción y `tps_by_label` 51 KB; con 20 etiquetas el endpoint general
llegaría a **~4,5 MB antes de añadir nada**, y a **~8,8 MB después**.

### 3.3 Bajar el bucket a adaptativo NO es la solución

Con el intervalo adaptativo (3 s en este JTL) y 3 transacciones, las tres series
nuevas bajan de 1.259,9 KB a **469,5 KB**. Tienta, pero **contradice GRAF1**: el
bucket de 1 s existe precisamente para que el pico de 21.060 ms no se promedie y
desaparezca. Si el mini-informe va a hablar de picos, sus gráficas tienen que
verlos.

### 3.4 Recomendación: **endpoint aparte, bajo demanda**

**Recomiendo NO meter las series por transacción en `/charts`.** Razones, en
orden de peso:

1. **Se pagan siempre y se usan casi nunca.** `/charts` lo pide el Dashboard
   entero en cada apertura. Las series por transacción solo hacen falta para las
   marcadas como críticas — 2 de 3 en la ejecución real de Coomeva, y el tope de
   N3.4 es 10.
2. **El coste de calcularlas bajo demanda es despreciable:** 0,2 s de re-parseo
   + 76 ms de agrupación ≈ **0,3 s por petición**, contra +1,26 MB en cada carga
   del dashboard.
3. **Ya existe el precedente arquitectónico.** `/executions/{id}/transaction-analyses`
   (N3.4, `upload.py:636-675`) es exactamente eso: un endpoint pequeño y
   separado para lo que solo consumen algunas vistas.
4. **`/charts` no se toca**, y con él no se toca su contrato ni `Dashboard.tsx`
   (protegido).

**Forma sugerida:** `GET /executions/{id}/transaction-charts?label=<label>` →
las 5 series de **una** transacción (~570 KB a 1 s, medido). Filtrar por label
en el servidor es lo que mantiene la respuesta pequeña; devolver todas las
marcadas de golpe reproduce el problema del §3.2.

**Aviso operativo:** aunque se resuelva por endpoint aparte, si algún día se
sirven 4-8 MB en una sola respuesta, en producción hay un nginx delante cuyo
`client_max_body_size` / timeouts **viven fuera del repo**. Añadir
`GZipMiddleware` sería una mejora transversal barata (estos JSON comprimen muy
bien), pero es sprint aparte y no es requisito de N4.

---

## 4. Render y persistencia

### 4.1 `chart_multiline` y `chart_area` sirven tal cual — no hace falta helper nuevo de matplotlib

| Gráfica de la transacción | Helper | Cómo |
|---|---|---|
| Tiempos de respuesta avg + max | `chart_multiline(..., dual_max=True)` | dos tuplas: `(label, ts, avg)` y `(label + MAX_SERIES_SUFFIX, ts, max)`. Es **el patrón exacto** de `export_pdf.py:78` |
| Latencia | `chart_area(ts, valores, color, ylabel)` | serie única |
| Tasa de error | `chart_area(...)` | serie única |
| TPS | `chart_area(...)` o `chart_multiline` con una serie | serie única |
| Códigos de respuesta | `chart_multiline(..., use_code_colors=True)` | una serie por código, colores ya estandarizados |

Lo que **sí** falta es un armador de tuplas por transacción, equivalente al
`_series_by_label()` de `export_pdf.py:66` pero filtrando por un label. Son
~15 líneas y **no** obligan a tocar `report_generator.py` (protegido) salvo que
se quiera compartirlo entre PDF y HTML.

### 4.2 Persistencia sin `ALTER TABLE`

`transaction_analyses` (N3.4) tiene **una** columna de texto, `ai_analysis`, y un
`metrics_json`. El mini-informe necesita **8 textos por transacción** (resumen +
5 gráficas + conclusiones + recomendaciones). Tres caminos:

| Opción | ¿ALTER TABLE? | Veredicto |
|---|---|---|
| A. Columnas nuevas en `transaction_analyses` | **Sí** | ❌ prohibido por la regla 10 |
| B. Meter los 8 textos dentro de `metrics_json` | No | ⚠️ funciona, pero mezcla métricas con análisis y hace imposible editar un texto sin reescribir el JSON entero (F5 edita análisis sueltos) |
| C. **Tabla nueva `transaction_chart_analyses`** | **No** | ✅ **recomendada** |

**Diseño recomendado (opción C)** — una fila por texto:

```
transaction_chart_analyses
  id                 UUID PK
  execution_id       UUID FK -> test_executions(id) ON DELETE CASCADE, index
  label              VARCHAR(500)
  section            VARCHAR(40)   -- 'summary' | 'response_times' | 'latency' |
                                   -- 'error_rate' | 'codes' | 'tps' |
                                   -- 'conclusions' | 'recommendations'
  ai_analysis        TEXT
  ai_analysis_updated_at DATETIME
  sort_order         INTEGER
  created_at         DATETIME
```

Por qué encaja sin fricción:

- **Regla 10 respetada literal:** `Base.metadata.create_all` **crea tablas
  nuevas solas**; el ALTER solo hace falta para columnas en tablas existentes.
  Es el mismo argumento con el que se creó `transaction_analyses` en N3.4
  (docstring de `transaction_analysis.py`).
- **Registro del modelo:** basta con importarlo en `main.py` junto al de N3.4
  (`main.py:27`), antes de `create_tables()` (`main.py:89-92`).
- **Una fila por texto** = editar un análisis suelto es un `UPDATE` de una fila,
  igual que hoy hace F5 con los análisis de sección.
- `transaction_analyses` **no se modifica**: sigue siendo la tabla del análisis
  global de la transacción y la fuente del bloque N3.5.

---

## 5. Costo de IA con la estructura aprobada

**8 llamadas por transacción**, confirmado: 1 (resumen) + 5 (una por gráfica) +
1 (conclusiones) + 1 (recomendaciones).

### 5.1 Tiempos reales medidos (no estimados)

Del log del contenedor, ejecución completa del 18/08 a las 20:15:46–20:18:09,
provider `openai`, modelo `gpt-5.5`:

| Sección | Duración |
|---|---|
| `summary_table` | 12,50 s |
| `errors` | 8,59 s |
| `chart_response_times` | 8,81 s |
| `chart_throughput` | 8,07 s |
| `chart_latency` | 11,79 s |
| `chart_error_rate` | 7,06 s |
| `chart_codes_per_second` | 8,38 s |
| `chart_transactions_per_second` | 6,18 s |
| `chart_active_threads` | 9,31 s |
| `conclusions` (350 palabras) | 19,81 s |
| `recommendations` (350 palabras) | 21,33 s |
| `transaction_0` (N3.4, 200 palabras) | 10,92 s |
| `transaction_1` (N3.4, 200 palabras) | 9,07 s |
| **TOTAL del upload actual (13 llamadas)** | **141,8 s ≈ 2 min 22 s** |

Promedios que sirven para proyectar: **análisis de gráfica 8,5 s**, **análisis
de transacción 10,0 s**, **conclusiones/recomendaciones 20,6 s**.

### 5.2 Proyección del mini-informe

| Concepto | Llamadas | Tiempo |
|---|---|---|
| Resumen de la transacción | 1 | 10,0 s |
| 5 gráficas × 8,5 s | 5 | 42,6 s |
| Conclusiones + recomendaciones **a 350 palabras** | 2 | 41,1 s |
| **Por transacción (conservador)** | **8** | **≈ 93,7 s (1 min 34 s)** |
| *Si se acotan a 200 palabras, como N3.4* | 8 | ≈ 72,6 s (1 min 13 s) |

| Escenario | Llamadas | Tiempo solo del mini-informe | Total del upload |
|---|---|---|---|
| 3 transacciones | 24 | 4 min 41 s | **7 min 3 s** |
| 5 transacciones | 40 | 7 min 49 s | 10 min 11 s |
| 10 transacciones (tope `MAX_TRANSACTIONS`) | 80 | 15 min 37 s | **17 min 59 s** |

**Consecuencia de diseño, no opinable:** el timeout global de axios es
**600 s** (`frontend/src/services/api.ts:14`). Con 3 transacciones el upload
síncrono queda a **7 min sobre un techo de 10** — sin margen; con 10
transacciones **revienta el timeout**. En producción hay además un nginx cuyo
`proxy_read_timeout` no está versionado.

**Por eso el mini-informe debe generarse BAJO DEMANDA, fuera de `/upload`**, con
su propio endpoint y su propio botón. Ese diseño además hace gratis el reintento
de una sola transacción cuando la IA falle, en vez de repetir el upload entero.

---

## 6. Plan de sub-sprints atómicos

| # | Sub-sprint | Archivos | Estimación | Protegido |
|---|---|---|---|---|
| **N4.3** | Servicio `transaction_series.py`: las 3 series nuevas por label + las 2 que ya existen, filtrando por un label. **No toca `jtl_parser.py`** — recibe el DataFrame ya parseado | 1 nuevo | ~90 líneas | **No** |
| **N4.4** | Endpoint `GET /executions/{id}/transaction-charts?label=` bajo demanda | `upload.py` (o endpoint nuevo) | ~70 líneas | No |
| **N4.5** | Modelo + tabla `transaction_chart_analyses` + import en `main.py` (sin ALTER) | 1 nuevo + `main.py` | ~55 líneas | No |
| **N4.6** | Generación IA bajo demanda: 8 prompts por transacción, `sanitize_ai_text`, persistencia, contadores. Reusa `transaction_analysis.py` | `transaction_analysis.py` + endpoint | ~140 líneas | No |
| **N4.7** | Pantalla: componente nuevo `TransactionReportSection.tsx` + botón "Generar mini-informe" | componente nuevo + ~6 líneas de montaje | ~160 líneas | ⚠️ **`Dashboard.tsx` si el montaje va ahí — pedir autorización, o montarlo desde el panel de N3.3 (`UploadJTL.tsx`) para evitarlo** |
| **N4.8** | Export PDF: 5 gráficas + textos por transacción | `report_generator.py`, `export_pdf.py` | ~120 líneas | 🔴 **`report_generator.py` PROTEGIDO** (autorización tipo D5) y **`export_pdf.py` bajo la regla de no tocarlo sin mención explícita** |
| **N4.9** | Export HTML standalone (Plotly aislado por transacción) e informe integrado | `export_html.py`, `integrated_report.py` | ~120 líneas | 🔴 **`export_html.py` bajo la misma regla** |

**Orden recomendado:** N4.3 → N4.4 → N4.5 → N4.6 (backend completo y
verificable sin frontend) → N4.7 (ya con dato real que pintar) → N4.8/N4.9.

**Coste de IA por sub-sprint:** N4.3, N4.4, N4.5, N4.7 → **0 llamadas**
(stubbeables, patrón F5/N3.4). N4.6 → **8 llamadas** (una transacción real, de
punta a punta). N4.8/N4.9 → **0**, consumen lo ya persistido.

### 6.1 Decisiones que hay que confirmar antes de N4.3

1. **¿Cuáles son las 5 gráficas?** El diagnóstico asume: tiempos de respuesta
   (avg+max), latencia, tasa de error, códigos de respuesta y TPS. Si alguna
   sobra o falta, cambia el §1.1 y el conteo de llamadas.
2. **¿Conclusiones y recomendaciones por transacción a 350 o a 200 palabras?**
   Son 20 s de diferencia por transacción (§5.2).
3. **¿El mini-informe se dispara con un botón por transacción o uno para todas
   las marcadas?** Por transacción permite reintentar una sola cuando la IA
   falle.

---

## 7. Riesgos detectados

1. **`codes_per_second` global no es filtrable por transacción** — hoy agrupa por
   código. La serie por transacción es dato **nuevo**, no un subconjunto.
2. **El bucket de 1 s es innegociable por GRAF1** pero es el que dispara el
   payload (§3.3). El endpoint aparte es lo que hace compatible una cosa con la
   otra.
3. **Sin `GZipMiddleware`**, cada KB medido es un KB transmitido.
4. **N4.8/N4.9 tocan tres archivos con restricción explícita** (uno protegido,
   dos bajo regla de memoria). Ese es el punto del sprint donde hace falta tu
   autorización por escrito.
5. **El tope `MAX_TRANSACTIONS = 10`** de N3.4 se hereda: 10 transacciones son
   80 llamadas de IA. Conviene un tope propio para el mini-informe, más bajo.

---

## 8. Lo que este diagnóstico NO cubre

- **No se midió el coste en tokens/dinero**, solo en tiempo y llamadas: la
  factura depende del modelo activo y no se consultó ninguna API.
- **No se probó con un JTL de 20 transacciones reales.** El escalado del §3.2 se
  hizo repartiendo las 25.773 muestras de Coomeva en etiquetas sintéticas, que
  es el escenario correcto para el tamaño del payload (lo manda la duración),
  pero un test real con 20 transacciones distintas podría tener labels que no
  cubren toda la ventana y pesar algo menos.
- **No se evaluó el impacto en el informe integrado** de N + 8 secciones nuevas
  por ejecución al construir el consolidado (F5.2): con 3 transacciones son 24
  textos más que podrían entrar al prompt del consolidado. Es un diagnóstico
  aparte antes de N4.9.

---

## 9. Cierre sin modificaciones

```
git status --short
 D docs/reports/sprint-hf18b-max-tokens-unificado.md      <- previo a esta sesion
?? docs/reporte-para-fredy-3.0.c.1.md                     <- previo a esta sesion
?? docs/reporte-para-fredy-3.0.c.2.md                     <- previo a esta sesion
?? docs/reporte_bug/n1.6-logo-pdf.md                      <- previo a esta sesion
?? docs/reporte_bug/n1.7-logo-html-individual.md          <- previo a esta sesion
?? docs/reporte_bug/n1.8-cabecera-exports.md              <- previo a esta sesion
?? docs/reports/repo/sprint-hf18b-max-tokens-unificado.md <- previo a esta sesion
```

**Ni un archivo de código modificado.** `jtl_parser.py` (protegido) se leyó, no
se tocó. Los dos scripts de medición se copiaron a `/tmp` del contenedor, se
ejecutaron y se borraron; **no se añadió nada al repo salvo este reporte**. Cero
llamadas a la IA y cero escrituras en base de datos.
