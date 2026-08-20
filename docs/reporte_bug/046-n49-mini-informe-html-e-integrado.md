# 046 — N4.9: mini-informe por transaccion en el HTML individual y en el informe integrado

**Fecha:** 2026-08-19
**Branch:** `backup-trabajo-local`
**Commit:** `a499653` — "N4.9: mini-informe por transaccion en HTML e informe integrado"
**Sigue a:** N4.8 (`f6f1a97`, reporte 045), que dejo el bloque en el PDF individual

**Archivos de codigo tocados:** 2 (ambos autorizados por Fredy para este bloque)
- `backend/app/api/v1/endpoints/export_html.py`
- `backend/app/api/v1/endpoints/integrated_report.py`

**Backups:** `.bak_n49_20260819_224814` de los dos archivos
**Llamadas de IA:** 0 — se usaron los 8 textos ya guardados de `token` en la ejecucion de Coomeva
**Ciclo Docker:** `py_compile` + `docker restart jmeter_backend`, sin build

---

## 1. El hallazgo del punto (2): el integrado NO heredaba N4.8 — lo BORRABA

El prompt pedia verificar si el informe integrado hereda solo lo que hizo N4.8,
como paso con N2.1. **No lo heredaba. Lo eliminaba entero.**

El integrado compone el body del individual llamando a `build_pdf_html` desde
`_generate_full_execution_pdf_html`, y despues le pasa
`_strip_pdf_individual_conclusions` para quitar las conclusiones por ejecucion
(las consolidadas van al final del informe). Ese strip barre **todo lo que hay
entre dos comentarios**:

`integrated_report.py:1305` (antes del cambio)

```python
html = _re.sub(
    r'<!--\s*=+\s*CONCLUSIONES Y RECOMENDACIONES.*?(?=<!--\s*=+\s*FOOTER)',
    '', html, flags=_re.DOTALL | _re.IGNORECASE,
)
```

Y `build_pdf_html` emite el bloque de N4.8 justo **entre** esos dos marcadores:

```
<!-- ===== CONCLUSIONES Y RECOMENDACIONES ===== -->
   conclusiones + recomendaciones
<!-- ===== N4.8: MINI-INFORME POR TRANSACCION ===== -->
   el bloque entero
<!-- ===== FOOTER ===== -->
```

Comprobado sobre el patron real antes de tocar nada:

```
sobrevive el bloque N4.8: False
```

Y sobre el PDF integrado generado con el codigo previo:

```
antes_integrado.pdf   paginas=12  bloques "MINI-INFORME"=0
```

**Correccion** (`integrated_report.py`, 2 lineas): el corte para tambien en el
marcador de N4.8.

```diff
-    # Primary strategy: comment-boundary strip
+    # Primary strategy: comment-boundary strip.
+    # N4.9: el corte para en el marcador de N4.8 ademas de en el de FOOTER.
+    # build_pdf_html emite el mini-informe por transaccion ENTRE las conclusiones
+    # y el pie, asi que el patron original (que barria hasta FOOTER) se lo
+    # llevaba por delante y en el integrado el bloque desaparecia entero. Las
+    # conclusiones individuales se siguen quitando igual — son las consolidadas
+    # las que van al final del informe.
     html = _re.sub(
-        r'<!--\s*=+\s*CONCLUSIONES Y RECOMENDACIONES.*?(?=<!--\s*=+\s*FOOTER)',
+        r'<!--\s*=+\s*CONCLUSIONES Y RECOMENDACIONES.*?(?=<!--\s*=+\s*(?:N4\.8|FOOTER))',
         '', html, flags=_re.DOTALL | _re.IGNORECASE,
     )
```

El orden regla 18 (`_strip_pdf_individual_conclusions` antes de
`_strip_individual_report_extras`, lineas 1691 y 1693) no se toca.

Aparte del strip, la rama PDF del integrado tampoco tenia los **datos**: solo
poblaba `meta['transaction_analyses']` (N3.5). Se le añadio
`meta['transaction_reports']` **reusando** `_build_transaction_reports` de N4.8
en vez de copiarlo.

---

## 2. Lo que se construyo

### 2.1 HTML individual (`export_html.py`)

Misma estructura que N4.8, despues de las conclusiones generales: encabezado de
la transaccion con su criticidad → tabla de metricas (14 columnas del resumen) →
analisis de resumen → las 5 graficas con su texto → conclusiones y
recomendaciones de la transaccion. Las graficas van en **Plotly**, como el resto
del HTML.

Tres piezas nuevas:

| Pieza | Que hace |
|---|---|
| `build_transaction_reports_plotly()` | gemela de `_build_transaction_reports` (N4.8): mismo origen de datos, misma criticidad, series en proceso |
| `_tx_traces()` | las 5 series de una transaccion como traces de Plotly |
| `transaction_reports_plotly_html()` | el markup + el JavaScript del bloque |

`_build_plotly_html` recibe dos parametros nuevos (`tx_body`, `tx_js`) **con
default `''`**, asi que cualquier llamada que no los pase produce exactamente el
mismo documento que antes.

### 2.2 Informe integrado, rama HTML

`_generate_full_execution_plotly_html` calcula los mini-informes de SU ejecucion
y los mete en `execution_data`; `_build_plotly_html_isolated` los pinta con el
`prefix` que ya usaba para el resto de graficas (`sec0_`, `sec1_`, …), de modo
que dos ejecuciones del mismo informe no colisionan ni se mezclan.

### 2.3 Mismo origen de datos que N4.8 (punto 3 del prompt)

- **Que transacciones:** las que tienen texto en `transaction_chart_analyses`.
- **Criticidad:** `_criticidad` de N4.8 se **importa**, no se copia — los
  umbrales de N3.2 (pico >= 10x el promedio, pico absoluto >= 10 s) siguen
  teniendo una sola fuente.
- **Series:** `build_transaction_series` (N4.3) llamado **en proceso** con el
  DataFrame ya parseado (`parser.df_main`), nunca por HTTP.

### 2.4 La serie dual de tiempos

Promedio en linea solida y maximo en punteada del mismo color, con
`showlegend: False` en el maximo — el criterio verificado en el reporte 044: el
maximo es la misma transaccion, no otra, y no debe aportar entrada de leyenda
propia. Medido sobre el HTML generado:

```
traces: 2
   name=Promedio            showlegend=True   dash=None
   name=Promedio (max)      showlegend=False  dash=dot
ENTRADAS DE LEYENDA: 1
```

### 2.5 Un solo markup, dos hojas de estilo

El HTML individual define `.section` / `.ai-box` / `.chart-title`; el integrado
define las mismas con prefijo `plotly-`. En vez de duplicar el markup,
`transaction_reports_plotly_html` recibe el juego de clases
(`TX_CLASES_INDIVIDUAL` / `TX_CLASES_INTEGRADO`) y el conversor de markdown del
documento anfitrion.

---

## 3. Diff

```
 backend/app/api/v1/endpoints/export_html.py       | 303 +++++++++++++++++++++-
 backend/app/api/v1/endpoints/integrated_report.py |  37 ++-
 2 files changed, 335 insertions(+), 5 deletions(-)
```

Las **unicas 2 lineas sustituidas** son las del strip (punto 1); las otras 3 son
lineas de firma/docstring ampliadas. Todo lo demas son inserciones.

`integrated_report.py` — los 6 cambios:

| # | Donde | Que |
|---|---|---|
| 1 | `_generate_full_execution_pdf_html` | `meta['transaction_reports']` reusando `_build_transaction_reports` de N4.8 |
| 2 | `_strip_pdf_individual_conclusions` | el corte para en el marcador de N4.8 |
| 3 | `_generate_full_execution_plotly_html` | `execution_data['transaction_reports']` con traces |
| 4 | `_build_plotly_html_isolated` | llama al constructor con `prefix` y clases del integrado |
| 5 | fragmento HTML | `{tx_body}` dentro de la seccion de la ejecucion |
| 6 | script del fragmento | `{tx_js}` dentro del mismo IIFE que el resto de graficas |

---

## 4. Validacion

Metodo: se generaron las 4 salidas **antes** (restaurando los `.bak_n49` en el
container y reiniciando) y **despues**. Cero llamadas de IA.

El informe integrado de prueba lleva **dos ejecuciones**: Coomeva
(`24342-Coomeva_SendCode_Performance`, con mini-informe de `token`) y "caso 1"
(sin mini-informes).

### 4.1 Tolerancia — HTML individual sin mini-informes

```
bytes antes  : 535851
bytes despues: 535851
sha256 antes  : b12ac085f43018eaa75f4b2b3c172352b23e1413d36fbf3c13c38bcb2f654cee
sha256 despues: b12ac085f43018eaa75f4b2b3c172352b23e1413d36fbf3c13c38bcb2f654cee
IDENTICOS BYTE A BYTE: True
```

Byte a byte, mismo hash. Sin titulo huerfano, sin hueco, sin `chart-tx`.

> Nota: la primera version dejaba +177 bytes porque los comentarios
> `<!-- N4.9 -->` vivian en la plantilla. Se movieron dentro de la cadena que
> devuelve la funcion: vacia es vacia.

### 4.2 HTML individual de Coomeva

| | Antes | Despues |
|---|---|---|
| Bytes | 591.580 | **909.003** (+53,7%) |
| Bloque presente | no | si |

```
--- encabezado ---
   nombre     : token
   criticidad : pico de 21,060 ms, 48x el promedio · pico absoluto de 21,060 ms (>=10 s, posible timeout)

--- las 5 graficas: div + su Plotly.newPlot ---
   response-times   div=True  newPlot=True
   latency          div=True  newPlot=True
   error-rate       div=True  newPlot=True
   codes            div=True  newPlot=True
   tps              div=True  newPlot=True
   total divs chart-tx: 5   total newPlot chart-tx: 5

--- las 8 secciones (texto real de la BD dentro del HTML) ---
   summary SI | chart_response_times SI | chart_latency SI | chart_error_rate SI
   chart_codes SI | chart_tps SI | conclusions SI | recommendations SI
   TOTAL: 8/8
   cajas "Analisis - ": 5
   notas "su texto no se genero": 0
```

Los 8 textos no se comprobaron por titulo sino contrastando los **primeros 55
caracteres de cada registro de `transaction_chart_analyses`** contra el texto del
HTML.

### 4.3 Informe integrado — HTML

| | Antes | Despues |
|---|---|---|
| Bytes | 1.110.741 | **1.428.467** |

```
bloques de mini-informe: 1   (correcto: solo Coomeva tiene)
ids de grafica del bloque: 5
      sec0_chart-tx0-codes
      sec0_chart-tx0-error-rate
      sec0_chart-tx0-latency
      sec0_chart-tx0-response-times
      sec0_chart-tx0-tps
newPlot del bloque: 5 | coinciden con los div: True
secciones del informe: 2
secciones CON bloque de mini-informe: ['sec0_']
clases del integrado (plotly-ai-box) en el bloque: True
textos de la BD dentro del integrado: 8/8
```

**Sin mezclar:** las 5 graficas cuelgan todas de `sec0_` (Coomeva). La seccion
`sec1_` ("caso 1") no tiene ni un `chart-tx`.

### 4.4 Informe integrado — PDF

| | Antes | Despues | Delta |
|---|---|---|---|
| Paginas | **12** | **15** | +3 |
| Imagenes unicas | 9 | 14 | +5 |
| Bloques "MINI-INFORME" | **0** | **1** | +1 |
| Bytes | 866.733 | 1.328.637 | +461.904 |

Las +5 imagenes son las 5 graficas de `token`. Los 8 textos de la BD estan
presentes. Y el bloque queda **dentro de la seccion de su ejecucion**:

```
pag  1- 6 : Coomeva — portada, resumen y sus graficas
pag  7- 9 : MINI-INFORME POR TRANSACCION | token | pico de 21,060 ms, 48x el promedio ...
pag 10    : caso 1 — su propia portada
pag 11-14 : caso 1 — resumen y graficas
pag 15    : caso 1 — su bloque N3.5 (Adapter VerifMethod)
```

No se arrastra al final ni se mezcla con la siguiente ejecucion. Ademas:

```
conclusiones individuales retiradas (queda la consolidada): True
```

El strip sigue haciendo su trabajo con las conclusiones; lo que ya no se lleva
por delante es el mini-informe.

### 4.5 Tolerancias, ejercitando la funcion real en el container

```
1. Sin mini-informes:  None -> ('', '')    [] -> ('', '')
2. Dos secciones sin texto:
   div de grafica: 5 | Plotly.newPlot: 5 | notas "no se genero": 2   -> OK
3. Seccion con texto pero SIN serie: el texto no se pierde           -> True
4. Sin metricas: se avisa, no se calla                               -> True
5. Namespacing sec0_ vs sec1_: solapamiento de ids = 0
6. individual usa .ai-box / integrado usa .plotly-ai-box, sin mezclar
7. Serie dual: 2 traces, 1 entrada de leyenda
```

El caso 3 es una tolerancia que no tenia N4.8: si una seccion tiene texto pero
la serie no se pudo calcular, el texto se pinta igual sin su grafica, en vez de
perderse con ella.

### 4.6 Regresion de N4.8

El PDF individual de Coomeva se regenero despues de todos los cambios:
**1.315.821 bytes, identico al que produjo N4.8**. La rama individual no se
movio.

---

## 5. Un tropiezo que conviene dejar escrito

Un parche intermedio recorto `export_html.py` desde
`transaction_reports_plotly_html` hasta el `@router.get` del endpoint para
reemplazar esa funcion. En ese tramo vivian **6 helpers del modulo**
(`_check_execution_access`, `_markdown_to_html`, `_ts_iso_list`, `_float_list`,
`_int_list`, `_compute_redirect_totals`) y se borraron.

`py_compile` paso igual — Python no resuelve nombres al compilar — y el sintoma
fue un `500 Internal Server Error` sin traza en el log. Se detecto comparando la
lista de `def` de nivel superior contra el backup:

```
defs perdidos respecto al backup: ninguno      <- despues de rehacerlo bien
lineas: backup=1042  actual=1342
lineas eliminadas: 1                            <- solo el docstring reemplazado
```

**Leccion:** `py_compile` verde no dice nada sobre nombres que faltan. Al
sustituir una funcion por corte de texto, acotar el corte al siguiente `def` de
nivel superior, y contrastar la lista de definiciones contra el backup antes de
dar nada por bueno.

---

## 6. Comprobaciones

| Check | Resultado |
|---|---|
| `py_compile` de los dos archivos | OK |
| Lista de `def` contra el backup | sin perdidas |
| Ciclo Docker | `docker restart jmeter_backend`, sin build |
| Archivos de codigo tocados | 2 — bajo el limite de 3 |
| Backups | `.bak_n49_20260819_224814` de ambos |
| Llamadas de IA | 0 |
| WeasyPrint rama PDF del integrado | sin cambios de layout: el bloque es el de N4.8, ya en table/mm/pt |
| Regla 18 (orden de los strip) | intacta (lineas 1691 y 1693) |
| `report_generator.py` / `export_pdf.py` | **no modificados** |
| `origin` (Azure DevOps) | **no tocado** |
| Push | remoto `github` |

---

## 7. Archivos para revisar

En `C:\Users\FredyGabrielBonillaB\Documents\N21_PDFs_comparacion\`:

| Archivo | Que es |
|---|---|
| `individual_N49.html` | **HTML individual de Coomeva con el bloque** — 909 KB, las 5 graficas Plotly interactivas |
| `individual_N49_ANTES.html` | El mismo, antes del cambio — 592 KB |
| `integrado_N49.pdf` | **Integrado con 2 ejecuciones** — 15 paginas, el mini-informe de `token` en las 7-9 |
| `integrado_N49_ANTES.pdf` | El mismo, antes — 12 paginas, sin bloque |
| `integrado_N49.html` | **Integrado en HTML** — el bloque bajo `sec0_`, la seccion de caso 1 sin nada |

---

## 8. Estado

Pendiente de **validacion visual de Fredy**:

- `individual_N49.html` — el bloque de `token` tras las conclusiones generales,
  con sus 5 graficas Plotly funcionando (hover, zoom) y la de tiempos mostrando
  el pico en la punteada con UNA sola entrada de leyenda.
- `integrado_N49.pdf` — el mini-informe en las paginas 7-9, dentro de la seccion
  de Coomeva, y la seccion de caso 1 sin bloque.
- `integrado_N49.html` — lo mismo en la version interactiva.
