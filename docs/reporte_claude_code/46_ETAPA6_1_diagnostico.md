0948a7e · 2026-09-17

# ETAPA 6.1 — Diagnóstico de gráficas, exportación y textos (read-only)

**Llamadas reales a la IA: 0.** Ningún archivo tocado. Solo lectura de código y de la
base; ni un `docker build`, ni un endpoint de generación.

Referencia: `docs/ESPECIFICACION-informe.md` v1.2 §3 (control de capas), §6 (selector de
exportación) y §7 (las cuatro salidas).

---

## 1. Qué gráficas tienen serie dual promedio/máximo

La serie de máximos existe en **una sola gráfica**, "Response Times", y existe en los dos
alcances (general y por transacción) de las cuatro salidas. Ninguna otra gráfica del
producto tiene dos capas: Latency, Error Rate, Response Codes, TPS y Active Threads son
de una sola línea (o de una línea por transacción / por código, que es otra cosa).

| Salida | Gráfica | Cómo se dibuja el máximo | Dónde |
|---|---|---|---|
| Pantalla — general | Response Times por Transaccion | una `<Line>` extra por transacción, `dataKey = "<label> (max)"`, `strokeDasharray="2 3"`, `legendType="none"` | `ReportBody.tsx:259-264` |
| Pantalla — transacción | la misma, con 1 sola etiqueta | idéntico; `rtMaxLabels` lo arma `seriesParaReportBody` | `TransactionReportSection.tsx:104-111` |
| PDF — general | `chart_multiline(..., dual_max=True)` | serie `"<label> (max)"` añadida por `_build_series(with_max=True)`; matplotlib la pinta `linewidth=0.8, linestyle='--', label='_nolegend_'` | `export_pdf.py:66-81, 325-336` · `report_generator.py:99-143` |
| PDF — transacción | `_tx_charts['response_times']` | dos series fijas: `Promedio` y `Promedio (max)`, `dual_max=True` | `export_pdf.py:119-125` |
| HTML — general | 2 traces Plotly por transacción | el 2.º trace lleva `dash:'dot'`, `width:1`, `opacity:0.85`, `showlegend:False` | `export_html.py:632-646` |
| HTML — transacción | 2 traces | `Promedio` y `Promedio (max)`, el segundo con `showlegend:False` | `export_html.py:146-157` |
| Integrado (PDF y HTML) | las mismas | reusa `_build_series`/`chart_multiline` y el trace gemelo | `integrated_report.py:83, 134, 920` |

El sufijo es **el mismo literal** en los dos lados: `MAX_SUFFIX = ' (max)'`
(`chartConfig.ts:159`) y `MAX_SERIES_SUFFIX = ' (max)'` (`report_generator.py:79`).

**Consecuencia para D46:** el selector segmentado "Ambas · Promedio · Máximo" aparece en
**una gráfica por informe** en el alcance general y **una por bloque** en el alcance por
transacción. En un informe con 3 transacciones son 4 selectores, no 24.

## 2. Dónde se construyen tooltip y leyenda

### Pantalla (recharts)

- **Tooltip:** `CustomChartTooltip`, `ReportBody.tsx:46-72`. Recibe `payload` de recharts
  y pinta **una fila por entrada**, ordenadas de mayor a menor. Aquí está el duplicado
  que denuncia §3: la serie de máximos es una `<Line>` más, así que entra en el
  `payload` y genera su propia fila "Auth (max) — 1.013 ms" debajo de "Auth — 422 ms".
  `legendType="none"` la saca de la leyenda, **no** del tooltip.
- **Leyenda:** `ScrollableLegend`, `ReportBody.tsx:81-143`. Ya filtra las series de
  máximos (`e.type !== 'none'`, línea 88) porque recharts no honra `legendType="none"`
  cuando la leyenda usa `content` propio. El botón maestro "Ocultar todas / Mostrar
  todas" y el toggle por serie escriben en `hiddenLines*`, que llega por `ctx`.
- **Ocultar una transacción** ya apaga sus dos capas a la vez: la línea de máximos usa
  `hide={hiddenLinesResponseTimes.has(label)}` — la clave del promedio, no la suya
  (`ReportBody.tsx:263`).

Los tres `Set` de series ocultas viven **fuera** de ReportBody: en `Dashboard.tsx` para el
general y en `BloqueGraficasTx` para cada transacción
(`TransactionReportSection.tsx:128-130`).

### HTML exportado (Plotly)

- **Tooltip:** `hovermode: 'x unified'` en los dos layouts —
  `plotly_layout_base` (`export_html.py:990-1004`) y `window.n49Layout`
  (`export_html.py:386-395`) — más un `hovertemplate` por trace. Plotly **ya excluye del
  hover las trazas ocultas** (`visible: 'legendonly'`), así que con el control de capas
  implementado como cambio de `visible`, el requisito de §3 "el tooltip muestra solo la
  capa activa" sale sin tocar el `hovertemplate`.
- **Leyenda:** la nativa de Plotly. Los traces de máximos llevan `showlegend:False`, de
  modo que **hoy no hay ninguna forma de apagarlos desde el HTML**.
- **Controles existentes:** `_ctrl_basic(chart_id)` (`export_html.py:255-264`) pinta
  "Mostrar todas / Ocultar todas" y `_ctrl_y_axis` pinta el control de eje Y. Los helpers
  JS (`hf10hShowAll`, `hf10hHideAll`, …) se definen una sola vez, de forma idempotente,
  en `export_html.py:1273-1311`. **Es el sitio natural para el toggle de capas.**

### PDF (matplotlib)

`chart_multiline` decide el estilo por el sufijo del nombre de la serie
(`report_generator.py:120-131`). No hay tooltip ni interacción: la "selección" solo puede
llegar como parámetro y traducirse en qué series se pasan o se dibujan.

## 3. Cómo llegan hoy los exportados desde los botones

```
Dashboard.tsx:995  <button onClick={handleExportHTML}>   Exportar HTML
Dashboard.tsx:999  <button onClick={handleExportPDF}>    Exportar PDF
        v
Dashboard.tsx:281 / 298   handleExportHTML / handleExportPDF
        v
services/api.ts:255 / 262  testAPI.exportHTML(id) / exportPDF(id)   <- GET, sin parámetros
        v
GET /api/v1/executions/{id}/export/html     export_html.py:483
GET /api/v1/executions/{id}/export/pdf      export_pdf.py:278
        v  (dentro del endpoint, siempre, sin condición)
export_pdf.py:463    meta['transaction_reports'] = await _build_transaction_reports(...)
export_html.py:741   _tx_reports = await build_transaction_reports_plotly(...)
```

Las dos funciones que construyen los bloques por transacción tienen la **misma forma**:
leen `transaction_chart_analyses`, filtran por `SECTIONS_GENERADAS`, ordenan por el orden
del resumen y devuelven una lista de `{label, criticality, metrics, sections, traces|charts}`
(`export_pdf.py:179-261`, `export_html.py:53-127`). Si la lista sale vacía devuelven `[]` y
el documento queda exactamente como el de hoy.

**Consecuencia para D50/D51:** el filtro cabe en un solo punto por salida —justo después
de calcular `etiquetas`— y el valor por defecto (sin parámetro) es "todas", que es el
comportamiento actual. La lista de transacciones que el diálogo debe ofrecer ya la sirve
un endpoint existente: `GET /executions/{id}/transaction-analyses`, campo `report_labels`
(`upload.py:720`), que es el mismo que usa `TransactionReportSection` para saber qué
bloques pintar (`TransactionReportSection.tsx:284-291`). **No hace falta endpoint nuevo.**

El integrado entra por otra puerta (`integrated_report.py:218-220` y `:988-994`) y no pasa
por los endpoints individuales: queda intacto sin esfuerzo, como pide §6.

## 4. Inventario de textos sin tilde

Solo cadenas **visibles**. Los comentarios del código, los identificadores, las claves de
sección (`chart_response_times`) y los nombres de gráfica que la especificación fija en
inglés ("Response Times", "Latency Over Time", "Transactions per Second"…) **no se tocan**.

| Archivo | Visibles | Ejemplos |
|---|---|---|
| `ReportBody.tsx` | 1 | "Response Times por Transaccion" (:245) |
| `Dashboard.tsx` | 18 | "Analisis" (:397, :401, :711, :769, :783, :869, :872), "Veredicto por Transaccion" (:658), "Transaccion" (:664, :847), "Duracion" (:564), "Distribucion de Codigos de Error" (:800), "Detalle de Errores por Transaccion" (:842), "Codigo" (:848), "Sesion expirada … inicie sesion" (:235), "Analisis de Redirecciones" (:770), "Analisis generado …" (:503-504) |
| `SummaryTable.tsx` | 1 | "Transaccion" (:47) |
| `TransactionReportSection.tsx` | 0 | ya llegó con tildes en la Etapa 3 ("Análisis", "Resumen de la transacción") |
| `report_generator.py` | 14 | "Codigos de Respuesta" (:266), "Transacciones por Segundo" (:267), "Reporte Resumen por Transaccion" (:349, :1107), "Transaccion" en cabeceras (:351, :1110), "Analisis - Response Times por Transaccion" (:435), "Distribucion de Response Codes" (:453), "Analisis de Errores" (:453), "Analisis de Redirecciones" (:675), "Analisis del Reporte Resumen" (:1119) |
| `export_html.py` | ~20 | "Reporte Resumen por Transaccion" (:325), "Transaccion" (:327), los "Analisis - …" de `HTML_BODY_CHARTS` (:222-236) y de `_TX_GRAFICAS`, "Duracion", "Aceptacion", "Ejecucion" en portada y metadatos |
| `export_pdf.py` | 3 | "Ejecucion" y dos "Analisis" en el armado de `meta` |

**Total ≈ 57 cadenas**, concentradas en 4 familias de palabra: *Transacción, Análisis,
Códigos, Duración/Ejecución/Descripción*. "Resumen", "Promedio", "Latencia", "Errores" y
"Muestras" no llevan tilde y no entran.

Dos textos ya retirados no se tocan porque su bloque salió del producto en HF-4:
"Analisis por Transaccion Critica" (`report_generator.py:229, 237`) — ver §5.

## 5. `transaction_analyses_html` — confirmado código muerto (D53)

```
$ grep -rn "transaction_analyses_html" --include=*.py --include=*.ts --include=*.tsx .
./backend/app/services/export/report_generator.py:202:def transaction_analyses_html(...)
```

Una sola aparición: su propia definición. Ningún llamador en las cuatro salidas. La propia
docstring, escrita en HF-4, dice *"si al leer esto sigue sin usarse, se puede retirar
entera"*. Son **62 líneas** (`:202-256` más el bloque de cajas hasta `:256`) y arrastra dos
cadenas sin tilde. Se retira en 6.5.

## 6. Estimación de cambios reales por archivo protegido

Cuenta solo **líneas realmente modificadas o añadidas** (condición C3: no se cuentan
líneas movidas, y no hay ninguna extracción prevista — nada obliga a mover código, así que
la condición C1 no llega a activarse en esta etapa).

| Archivo protegido | Líneas hoy | Qué se toca | Estimación |
|---|---|---|---|
| `Dashboard.tsx` | 1.018 | estado de capas del general (D48) y su paso por `ctx`; abrir el diálogo desde los dos botones y pasar la selección a `testAPI`; 18 tildes | **≤ 60** |
| `export_pdf.py` | 538 | parámetro de transacciones + validación 400 + filtro (D51); parámetro de capas y su reparto a `chart_multiline` (D49); 3 tildes | **≤ 55** |
| `export_html.py` | 1.358 | lo mismo que el PDF; botones de capas en `_ctrl_basic` y su helper JS; selección inicial aplicada a `visible`; ~20 tildes | **≤ 90** |
| `report_generator.py` | 1.145 | `chart_multiline` acepta la capa pedida; 14 tildes; retirar `transaction_analyses_html` | **≤ 60 modificadas + 62 borradas** |

**Umbral de PARADA:** +50 % sobre cada estimación, es decir 90 · 83 · 135 · 90. Si un
archivo lo supera, se para y se avisa antes de seguir.

Archivos **no protegidos** que absorben el grueso del trabajo: `ReportBody.tsx` (selector
y tooltip, D46/D47), `TransactionReportSection.tsx` (estado de capas por bloque),
`services/api.ts` (dos firmas), y un componente nuevo para el diálogo de exportación.

## 7. Decisiones técnicas que tomo (dentro de lo ya autorizado)

| # | Decisión | Por qué |
|---|---|---|
| T1 | El diálogo de exportación vive en un **componente nuevo** `ExportScopeDialog.tsx`, no dentro de `Dashboard.tsx` | mantiene el cambio en el protegido en ~15 líneas: importar, dos estados, dos `onClick` |
| T2 | El estado de capas se guarda como `Record<idGrafica, 'ambas' / 'promedio' / 'maximo'>` en un módulo nuevo `useChartLayers.ts`; `Dashboard` y `BloqueGraficasTx` lo instancian y lo pasan por `ctx` | D48 pide memoria de sesión de pantalla y que el export pueda leerla; un hook aparte evita repetir el mismo bloque en dos sitios |
| T3 | El tooltip de pantalla (D47) **filtra por sufijo**: agrupa `X` con `X (max)` en una sola fila y respeta `hiddenLines` y la capa activa | es el mismo criterio que ya usa `ScrollableLegend:88`, así el filtro no se inventa una segunda convención |
| T4 | En el HTML exportado, el control de capas se implementa como `Plotly.restyle(div, {visible: […]})` sobre los índices de traza, calculados por el sufijo `' (max)'` del `name` | con `hovermode:'x unified'`, ocultar la traza ya la saca del hover: §3 se cumple sin tocar `hovertemplate` |
| T5 | El parámetro de transacciones viaja como **query repetido** `?tx=<label>&tx=<label>` y el de capas como `?capa=<idGrafica>:<valor>`; sin ninguno de los dos, la respuesta es byte a byte la de hoy | D51 pide compatibilidad; el `GET` actual de `api.ts` no cambia de verbo y el `Content-Disposition` sigue igual |
| T6 | El integrado no recibe ninguno de los dos parámetros; en HTML hereda los botones de capas porque comparte `_bloque_grafica_html`, y en PDF dibuja "Ambas" | §6 excluye el integrado del selector de exportación, no del control de capas de §7 |

## 8. Riesgos anotados

1. **`api.ts` usa `GET` con `responseType:'blob'`.** Una lista larga de transacciones con
   nombres largos puede acercarse al límite práctico de URL. Con los informes reales (2-3
   transacciones) no hay problema; si alguna ejecución pasara de ~40 etiquetas habría que
   cambiar a `POST`. Se mide en 6.3 antes de decidir.
2. **Los scripts de verificación viven en `/tmp/e2e` dentro del contenedor**, no en el
   repositorio. Sobreviven mientras el contenedor no se recree. Entra en el checklist de
   despliegue de 6.6.
3. **`hiddenLines` y las capas son ejes independientes.** Ocultar "Auth" en la leyenda y
   elegir "Máximo" deben componerse: la línea de máximos de Auth sigue oculta. Se prueba
   explícitamente en 6.2.

## 9. Datos para las corridas siguientes

| Ejecución | id | Transacciones con informe |
|---|---|---|
| `E3-estilo-pruebakinetix` | `20bb2356-410d-465f-8717-c9a025e26e03` | 3 |
| `E5-panel` | `c33488cb-5f1c-499b-86b3-4b58642c31cb` | 2 |

Ninguna necesita regenerarse: 6.2 a 6.5 se validan sobre informes **ya generados**, sin
tocar la IA.

---

**Estado:** 6.1 cerrado. Ningún hallazgo cambia el plan; ninguna condición de parada
activada. Sigue 6.2 — capas y tooltip en pantalla.
