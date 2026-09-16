976e0b8 · 2026-09-15

# ETAPA 2.1 — Diagnóstico completo (read-only)

**Llamadas reales a la IA en este sub-paso: 0.** Nada modificado.
Termina en la **PARADA PREVISTA**: se requiere autorización de 4 archivos protegidos.

---

## 1. Throughput Over Time (D19)

**Distinción imprescindible:** hay que retirar la **gráfica** y su análisis, **no** la métrica
escalar `throughput` (req/s), que alimenta la tabla resumen, los KPI y el prompt de TPS. Si se
retirase la métrica, se romperían secciones que la especificación conserva.

| Qué | Archivo:línea | Acción |
|---|---|---|
| Llamada de IA | `services/ai/analysis_pipeline.py:214-225` | **retirar** |
| Campo del resultado | `analysis_pipeline.py:47, 92, 327, 351` | dejar de poblar |
| Columna `ai_analysis_throughput` | `db/models/test.py:63` | **conservar** (datos históricos) |
| Columna `throughput` (escalar) | `db/models/test.py:47` | **conservar y seguir usando** |
| Persistencia | `api/v1/endpoints/upload.py:435, 496` | dejar de escribir |
| Serie `throughput_timeline` | `upload.py:1242-1245, 1323` | dejar de enviar |
| Gráfica en pantalla | **`Dashboard.tsx:1113-1127`** 🔒 | **retirar** |
| Estado y edición en pantalla | **`Dashboard.tsx:228, 342, 358, 394`** 🔒 | retirar |
| Config de la gráfica | `frontend/src/config/chartConfig.ts:71-77` | retirar `throughputOverTime` |
| PDF — imagen | **`export_pdf.py:329`** 🔒 · **`report_generator.py:1041`** 🔒 | **retirar** |
| PDF — texto IA | **`export_pdf.py:394`** 🔒 | retirar |
| HTML — traces y bloque | **`export_html.py:573-575, 690, 782, 1185-1188, 1298`** 🔒 | **retirar** |
| Integrado — imagen, texto y bloque | `integrated_report.py:152, 190, 378, 598, 705-708` | retirar |
| Integrado — vista previa | `frontend/src/components/integrated/ExecutionReportSection.tsx:21, 142-146` | retirar |
| Overrides en base | clave `ai_analysis_throughput` | **D23: ignorar, no borrar** |

**Confirmado por `SELECT`:** la clave `ai_analysis_throughput` **existe hoy** en
`integrated_reports.sections[].overrides.analysis` de informes reales. D23 aplica de verdad,
no es una precaución teórica.

**KPI "Throughput" (valor escalar)**: aparece en `report_generator.py:527, 1008`,
`export_html.py:1141`, `ExecutionReportSection.tsx:106`. **No se toca** — es la métrica, no la
gráfica. Se declara explícitamente para que no se retire por error de búsqueda.

**Hallazgo lateral:** `ai_analysis_response_time_over_time` (`analysis_pipeline.py:46`) es un
campo **legado que ya no se genera** (siempre `""`), pero **sí existe como override** en la base.
No forma parte de esta etapa; se anota para no confundirlo con Throughput.

---

## 2. Informe por transacción actual (N3/N4)

| Pieza | Archivo:línea |
|---|---|
| Secciones (8) | `db/models/transaction_chart_analysis.py:39` → `summary` + 5 `chart_*` + `conclusions` + `recommendations` |
| Series (5 gráficas) | `services/jtl/transaction_series.py:29` — `CHART_TYPES` **ya es exactamente la lista de D15** |
| Generación | `services/ai/transaction_report.py:208-251` (bucle por sección) |
| Prompts | `transaction_report.py:140-180` |
| Disparo automático | `upload.py:873` (`asyncio.create_task`) → `upload.py:836` |
| Endpoints | `upload.py:746, 893, 948, 986, 1061` |
| Pantalla | **`TransactionReportSection.tsx`** (433 líneas) · montado en **`Dashboard.tsx:12`** 🔒 |
| PDF | **`export_pdf.py:179` `_build_transaction_reports`** 🔒 → **`report_generator.py:262` `transaction_reports_html`** 🔒 |
| HTML | **`export_html.py:57`** 🔒 (gemela de la anterior) |
| Integrado | `integrated_report.py:232-234` (reutiliza la de `export_pdf`) |

### 2.1 Dos hallazgos que afectan al plan

**(a) El orden actual contradice D17.** Hoy los bloques por transacción van **después** de las
conclusiones generales:

```
report_generator.py:1052   <!-- ===== CONCLUSIONES Y RECOMENDACIONES ===== -->
report_generator.py:1053   {ai_box('conclusions', ...)}
report_generator.py:1057   {transaction_reports_html(meta.get('transaction_reports'))}
```

Lo mismo en el integrado (`integrated_report.py`: «mini-informe por transaccion **ENTRE** las
conclusiones») y en pantalla (`Dashboard.tsx`: «**despues de** las secciones»).
D17 exige: general → transacciones → conclusiones al final. **Hay que reordenar las 4 salidas.**

**(b) `transaction_reports_html` es una plantilla propia, no el render del general.** Su
docstring lo dice: «layout denso de N2.1», con su propia caja de métricas, sus gráficas y sus
conclusiones por transacción (`report_generator.py:362`). Es exactamente lo que D21 prohíbe.
Unificarlo es el cambio estructural mayor de la etapa y vive en un archivo protegido.

### 2.2 Textos visibles con "mini-informe" (D22)

Separando **visible** de **comentario/identificador**:

| Visible (hay que cambiar) | Archivo:línea |
|---|---|
| `Mini-informe por Transaccion</h2>` | `TransactionReportSection.tsx` |
| mensaje de progreso `…mini-informes...` | `TransactionReportSection.tsx` |
| texto de botón/vacío `…mini-informe o escribelo a mano.` | `TransactionReportSection.tsx` |
| `Mini-informe por transaccion</div>` | `export_html.py` 🔒 |
| `_SIN_TEXTO`: «esta grafica forma parte del **mini-informe**…» | `report_generator.py:259` 🔒 |
| «se marco como critica pero no se genero su analisis individual» | `report_generator.py:240` 🔒 |

**Solo comentarios de código (NO se tocan, D22):** `upload.py`, `export_pdf.py`,
`integrated_report.py`, cabeceras de `export_html.py` y de `TransactionReportSection.tsx`.
Los identificadores `txreport_*`, `transaction_chart_analyses` y `TransactionChartAnalysis`
**se conservan**.

---

## 3. Render del informe general por salida

| Salida | Quién pinta | ¿Admite filtrar por label? |
|---|---|---|
| Pantalla | **`Dashboard.tsx:1080-1210`** 🔒 — 8 bloques **en línea**, no componentizados; cada uno con su `ResponsiveContainer` y su `AnalysisBox` | **No.** Alcance cableado |
| PDF | **`report_generator.py:build_pdf_html`** 🔒 vía `chart_unit(...)` | **No** |
| HTML | **`export_html.py:1150-1300`** 🔒 — bloques literales con `Plotly.newPlot` | **No** |
| Integrado | `integrated_report.py:598-710` — **ya parametriza por `prefix`** para aislar IDs | Parcial: aísla IDs, no filtra datos |

**Datos por transacción ya disponibles** (no hay que crearlos):
`build_transaction_series(df, label)` (5 series), `get_summary_table_data()` filtrable por label,
y los 6 análisis en `transaction_chart_analyses`. El endpoint bajo demanda es `upload.py:948`.

---

## 4. Overrides del integrado (D23)

Indexados como `sections[].overrides.{analysis|images}`. Claves de `analysis` presentes hoy:

```
ai_analysis_active_threads · ai_analysis_codes_per_second · ai_analysis_error_rate
ai_analysis_errors · ai_analysis_latency · ai_analysis_response_time_over_time
ai_analysis_response_times · ai_analysis_summary · ai_analysis_throughput
ai_analysis_transactions_per_second
```

- **`ai_analysis_throughput` existe** → se ignora al renderizar (D23).
- **No existe hoy ninguna clave de conclusiones/recomendaciones por transacción**: el segundo
  caso de D23 no tiene datos que proteger, pero la regla se implementa igual por si aparecen.

---

## 5. Configuración de IA (D13)

| Pieza | Archivo:línea | Qué falta |
|---|---|---|
| Modelo | `db/models/ai_config.py:22` | **añadir `reasoning_effort`** (D13b) |
| Schemas | `schemas/ai_config.py:17, 21, 37, 40` | añadir el campo |
| Endpoints | `api/v1/endpoints/ai_config.py` (GET/POST/test) | leer, guardar y usar en el test (D13d) |
| Pantalla | `components/admin/AIConfigPage.tsx` | selector junto al modelo |
| **Clave del singleton** | `gemini.py:get_gemini_analyzer` → `f"{provider}:{model_name}:{api_key[:8]}"` | **no incluye el effort** → D13c obliga a añadirlo |
| kwargs de la llamada | `gemini.py:_generate` → `openai_chat_completion(..., temperature=…)` | añadir el kwarg cuando aplique |
| Telemetría | `gemini.py:_emit_ai_telemetry` | añadir el campo (D13e) |

Los prefijos para decidir si aplica ya existen: `_OPENAI_NEWGEN_PREFIXES = ("gpt-5","o1","o3","o4")`
(`gemini.py:103`), el mismo criterio de `max_completion_tokens` que pide D13.

---

## 6. Propuesta de diseño para D21

Un único render por salida, parametrizado por alcance:

```
alcance = "general" | f"transaccion:{label}"
```

| Salida | Firma propuesta |
|---|---|
| Pantalla | `<ReportBody scope={{kind:'general'}} … />` y `<ReportBody scope={{kind:'transaction', label}} … />`, extrayendo los bloques de `Dashboard.tsx` a un componente nuevo `ReportBody.tsx` (**archivo nuevo, no protegido**); `Dashboard.tsx` queda como orquestador |
| PDF | `report_body_html(meta, charts, scope)` en `report_generator.py`; `transaction_reports_html` pasa a ser un bucle que llama a `report_body_html` con cada label |
| HTML | `_report_body(meta, traces, scope, prefix)` en `export_html.py`, reutilizando el `prefix` que el integrado ya usa para aislar IDs |
| Integrado | reutiliza las dos anteriores; **no necesita render propio** |

La estrategia que **minimiza el diff en protegidos**: mover el cuerpo a funciones/componentes
nuevos y dejar en el archivo protegido la llamada. Aun así, el corte inicial obliga a tocarlos.

---

## 7. LISTA CERRADA de archivos protegidos

### Se necesitan — 4

| Archivo | Qué cambia | Por qué no se puede evitar | Diff estimado |
|---|---|---|---|
| **`Dashboard.tsx`** (1.317) | Quitar bloque Throughput (~18 l.) y sus 4 estados; reordenar para que las transacciones vayan antes de conclusiones; extraer los bloques de gráficas a `ReportBody.tsx` y llamarlo con alcance | Es **el único** sitio donde se pinta el informe en pantalla. D19, D17 y D21 son inevitables aquí | **~120-160** (mayoría, líneas movidas a un archivo nuevo) |
| **`report_generator.py`** (1.066) | Quitar `chart_unit('Throughput Over Time', …)`; mover las conclusiones **después** de los bloques por transacción; convertir `transaction_reports_html` en un bucle sobre el render general; quitar conclusiones/recomendaciones por transacción; `page-break-before` (D24); textos "mini-informe" | Contiene `build_pdf_html` **y** la plantilla paralela que D21 obliga a unificar | **~150-200** |
| **`export_pdf.py`** (534) | `_build_transaction_reports`: dejar de pedir `conclusions`/`recommendations`; quitar la imagen y el texto de throughput | Es el ensamblador de datos del PDF | **~30-40** |
| **`export_html.py`** (1.339) | Quitar traces y bloque de throughput; unificar el cuerpo por alcance; reordenar; texto visible "Mini-informe" | Es el único render del HTML individual | **~120-160** |

### NO se necesitan — declarado

| Archivo | Por qué no |
|---|---|
| `jtl_parser.py` | Las series por transacción ya existen (`transaction_series.py`, no protegido). Cero cambios |
| `virtual_user.py` | Motor de ejecución, sin relación con el informe |
| `services/engine/` | Ídem |
| `ScriptDesigner.tsx` | Sin relación |

**Archivos NO protegidos que también cambian:** `analysis_pipeline.py`, `transaction_report.py`,
`transaction_chart_analysis.py`, `upload.py`, `integrated_report.py`, `ai_config.py` (modelo,
schema, endpoint), `gemini.py`, `chartConfig.ts`, `TransactionReportSection.tsx`,
`ExecutionReportSection.tsx`, `AIConfigPage.tsx`, más `ReportBody.tsx` (nuevo).

---

## 8. Contradicciones con D13-D26

Ninguna decisión resulta inviable. Dos precisiones:

1. **D19 y la métrica escalar.** «Se retira de todo» debe entenderse como la **gráfica Throughput
   Over Time y su análisis**. El valor `throughput` (req/s) sigue en la tabla resumen, los KPI y
   el prompt de TPS. Se implementa así salvo indicación contraria.
2. **D17 obliga a reordenar, no solo a añadir.** Hoy las transacciones van *después* de las
   conclusiones en las 4 salidas. No estaba dicho en el enunciado y es trabajo real.

---

## Estado

**PARADA PREVISTA.** Pendiente de autorización de los 4 archivos protegidos de §7.
