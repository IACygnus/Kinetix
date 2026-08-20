# 045 — N4.8: mini-informe por transaccion en el PDF individual

**Fecha:** 2026-08-19
**Branch:** `backup-trabajo-local`
**Commit:** `f6f1a97` — "N4.8: mini-informe por transaccion en el PDF"
**Archivos de codigo tocados:** 2 (ambos autorizados por Fredy para este bloque)
- `backend/app/services/export/report_generator.py` (protegido)
- `backend/app/api/v1/endpoints/export_pdf.py`

**Backups:** `.bak_n48_20260819_223133` de los dos archivos
**Llamadas de IA:** 0 — se usaron los 8 textos ya guardados de `token` en la ejecucion de Coomeva
**Ciclo Docker:** `py_compile` + `docker restart jmeter_backend`, sin build

---

## 1. Lo que se construyo

Despues de las conclusiones y recomendaciones generales, el PDF individual ahora
lleva un bloque por cada transaccion que tenga mini-informe generado, con la
estructura del diagrama del sprint N4:

1. Encabezado de la transaccion (nombre + criticidad), abriendo pagina nueva
2. Su tabla de metricas — las 14 columnas del resumen general, solo esa fila
3. Su analisis de resumen
4. Sus 5 graficas, cada una con su texto al lado (layout denso de N2.1)
5. Sus conclusiones y sus recomendaciones

---

## 2. Decisiones de diseño

### 2.1 De donde salen las transacciones

**De `transaction_chart_analyses`, no de `transaction_analyses`.**

La ejecucion de Coomeva tiene los 8 textos de `token` en
`transaction_chart_analyses` y **cero filas** en `transaction_analyses`:

```
SELECT label, is_critical, marked_by FROM transaction_analyses
 WHERE execution_id='115346ea-...';
(0 rows)
```

El registro de criticidad (N3.4) es posterior a esa ejecucion. Tomar
`transaction_analyses` como origen habria dejado el bloque sin pintar justo en el
unico caso que habia que validar. Es el mismo criterio que ya aplica N4.7 en
pantalla (`upload.py:672` — `report_labels` union las criticas).

Se toman solo las etiquetas que tienen **al menos un texto no nulo**: una fila
creada y vacia no dispara un bloque entero.

### 2.2 La criticidad del encabezado

Como para Coomeva no hay fila de criticidad, la linea se compone de forma
determinista y sin IA, con los **mismos disparadores del premarcado de N3.2**
(`upload.py:136-143`): pico relativo >= 10x el promedio y pico absoluto >= 10 s.
Si ademas existe la fila de `transaction_analyses`, se antepone quien la marco.

Para `token` sale exactamente el caso que documenta N3.2:

```
pico de 21,060 ms, 48x el promedio · pico absoluto de 21,060 ms (>=10 s, posible timeout)
```

### 2.3 Las series, en proceso y no por HTTP

`_build_transaction_reports` llama a `build_transaction_series` (N4.3)
directamente con el DataFrame que el endpoint del PDF **ya tiene parseado**. Ir
por HTTP a `/transaction-charts` habria vuelto a leer y parsear el JTL entero una
vez por transaccion.

Se pasa `parser.df_main` cuando existe (mismo criterio que `_parse_execution_df`
en `upload.py:723`), no el `df` que devuelve `parse()` — ese incluye las
redirecciones.

### 2.4 Las graficas

Con `chart_multiline` / `chart_area`, las mismas del resto del PDF:

| Grafica | Funcion | Nota |
|---|---|---|
| Tiempos de Respuesta | `chart_multiline(..., dual_max=True)` | GRAF1: promedio y maximo en series separadas para que el pico de 21 s no se promedie |
| Latencia | `chart_area` violeta | |
| Tasa de Error | `chart_area` rojo | |
| Codigos de Respuesta | `chart_multiline(use_code_colors=True)` | Los puntos vienen aplanados por `(bucket, codigo)`; se agrupan por codigo igual que `_build_codes_series` |
| Transacciones por Segundo | `chart_area` verde | |

`build_transaction_series` entrega el timestamp en ISO (su consumidor original
era JSON) y `make_time_labels` resta timestamps: `_tx_points` los convierte a
`pd.Timestamp`.

### 2.5 Reglas 11 y 17

El bloque **no define CSS nuevo**: reutiliza las clases que `build_pdf_html` ya
tiene (`.section`, `.chart-unit`, `.chart-cell`, `.chart-ai-cell`, `.ai-box`,
`.label-cell`, `.num`). Verificado sobre el HTML generado (punto 4.4): cero
`flex`, cero `grid`, cero `rem`, todo en `mm`/`pt`, y las graficas van en
`<table>`.

---

## 3. Diff

292 lineas, **todas insertadas** — ni una linea existente modificada o borrada en
ninguno de los dos archivos.

```
 backend/app/api/v1/endpoints/export_pdf.py      | 166 ++++++++++++++++++++++++
 backend/app/services/export/report_generator.py | 126 ++++++++++++++++++
 2 files changed, 292 insertions(+)
```

### 3.1 Diff completo de `report_generator.py` (archivo protegido)

```diff
diff --git a/backend/app/services/export/report_generator.py b/backend/app/services/export/report_generator.py
index 0454f53..4764bd6 100644
--- a/backend/app/services/export/report_generator.py
+++ b/backend/app/services/export/report_generator.py
@@ -243,6 +243,129 @@ def transaction_analyses_html(rows: Optional[List[Dict[str, Any]]], for_pdf: boo
     return titulo + ''.join(cajas)
 
 
+# N4.8: titulos de las 5 graficas del mini-informe y el color de su barra, en el
+# orden aprobado. Las claves son las de CHART_TYPES (N4.3) y las de las secciones
+# 'chart_*' de transaction_chart_analyses (N4.5): una sola lista evita que el
+# orden de las graficas y el de los textos se desalineen.
+TRANSACTION_CHARTS = (
+    ('response_times', 'Tiempos de Respuesta', '#8884d8'),
+    ('latency', 'Latencia', '#9c27b0'),
+    ('error_rate', 'Tasa de Error', '#f44336'),
+    ('codes', 'Codigos de Respuesta', '#4CAF50'),
+    ('tps', 'Transacciones por Segundo', '#2196F3'),
+)
+
+_SIN_TEXTO = ('<em style="color:#94a3b8">Esta grafica forma parte del mini-informe pero su '
+              'texto no se genero (fallo o quedo pendiente).</em>')
+
+
+def transaction_reports_html(reports: Optional[List[Dict[str, Any]]]) -> str:
+    """N4.8: el mini-informe por transaccion dentro del PDF individual.
+
+    Un bloque por transaccion con mini-informe generado, cada uno abriendo pagina
+    nueva: encabezado (nombre + criticidad), su tabla de metricas con las mismas
+    columnas del resumen general, su analisis de resumen, sus 5 graficas con el
+    texto al lado (layout denso de N2.1) y sus conclusiones y recomendaciones.
+
+    Sin `reports` devuelve cadena vacia: el PDF sale EXACTAMENTE como antes,
+    mismo conteo de paginas y sin titulo huerfano. Mismo criterio que el logo de
+    N1.6 y que el bloque de N3.5.
+
+    Una grafica cuyo texto fallo o quedo pendiente se pinta igual, con una nota
+    (criterio de N3.5): omitirla en silencio le haria creer a quien lee el
+    reporte que esa grafica no se analizo porque no hacia falta.
+
+    Reutiliza las clases que ya define el CSS de `build_pdf_html`
+    (.section / .chart-unit / .chart-cell / .chart-ai-cell / .ai-box): solo table
+    layouts y unidades mm/pt, sin flex ni grid (reglas 11 y 17).
+    """
+    if not reports:
+        return ''
+
+    def _caja(titulo, texto, permitir_corte=False):
+        """Caja de analisis con el mismo aspecto que `ai_box` del cuerpo general."""
+        cuerpo = markdown_to_html(texto) if texto else _SIN_TEXTO
+        corte = 'break-inside:auto;' if permitir_corte else ''
+        return (f'<div class="ai-box" style="border-left-color:#4f46e5;{corte}">'
+                f'<div class="ai-title">{titulo}</div>'
+                f'<div class="ai-text">{cuerpo}</div></div>')
+
+    def _unidad(titulo, color, img_b64, texto):
+        """N2.1: grafica y su texto lado a lado, como unidad indivisible."""
+        if not img_b64:
+            return ''
+        head = f'<div class="chart-title" style="border-left-color:{color}">{titulo}</div>'
+        img = f'<img class="chart-img" src="data:image/png;base64,{img_b64}" />'
+        lado = _caja(f'Analisis - {titulo}', texto)
+        return (f'<table class="chart-unit"><tr>'
+                f'<td class="chart-cell">{head}{img}</td>'
+                f'<td class="chart-ai-cell">{lado}</td>'
+                f'</tr></table>')
+
+    bloques = []
+    for r in reports:
+        etiqueta = r.get('label', '')
+        criticidad = r.get('criticality') or ''
+        sec = r.get('sections') or {}
+        graf = r.get('charts') or {}
+        m = r.get('metrics') or {}
+
+        # --- encabezado de la transaccion, abriendo pagina
+        sub = (f'<div style="font-size:9pt;color:#cbd5e1;margin-top:1.5mm">{criticidad}</div>'
+               if criticidad else '')
+        cabecera = (
+            '<div style="break-before:page;page-break-before:always;'
+            'background:#0a1628;color:white;padding:5mm 6mm;border-radius:2mm;margin-bottom:4mm">'
+            '<div style="font-size:8pt;letter-spacing:0.4pt;text-transform:uppercase;'
+            'color:#f5a623;font-weight:700">Mini-informe por transaccion</div>'
+            f'<div style="font-size:19pt;font-weight:700;margin-top:1.5mm">{etiqueta}</div>'
+            f'{sub}</div>'
+        )
+
+        # --- tabla de metricas: mismas columnas que el resumen general
+        if m:
+            err = ' style="color:#ef4444;font-weight:600"' if float(m.get('errorPct', 0)) > 0 else ''
+            fila = (
+                f'<tr><td class="label-cell">{etiqueta}</td>'
+                f'<td class="num">{int(m.get("samples", 0)):,}</td>'
+                f'<td class="num"{err}>{int(m.get("errors", 0)):,}</td>'
+                f'<td class="num"{err}>{float(m.get("errorPct", 0)):.2f}%</td>'
+                f'<td class="num">{float(m.get("avg", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("median", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("p90", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("p95", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("p99", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("min", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("max", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("tps", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("kbRecv", 0)):.2f}</td>'
+                f'<td class="num">{float(m.get("kbSent", 0)):.2f}</td></tr>'
+            )
+            tabla = (
+                '<div class="section"><div class="section-header">Metricas de la Transaccion</div>'
+                '<table><thead><tr>'
+                '<th style="text-align:left">Transaccion</th><th>Muestras</th><th>Errores</th><th>% Error</th>'
+                '<th>Promedio</th><th>Mediana</th><th>P90</th><th>P95</th><th>P99</th>'
+                '<th>Min</th><th>Max</th><th>TPS</th><th>KB/s Recv</th><th>KB/s Sent</th>'
+                f'</tr></thead><tbody>{fila}</tbody></table></div>'
+            )
+        else:
+            # La transaccion tiene textos pero ya no figura en el resumen de esta
+            # ejecucion. Se dice, no se calla.
+            tabla = ('<div class="ai-box" style="border-left-color:#f5a623"><div class="ai-text">'
+                     '<em>No se encontraron las metricas de esta transaccion en el resumen de '
+                     'esta ejecucion.</em></div></div>')
+
+        partes = [cabecera, tabla, _caja('Analisis de la Transaccion', sec.get('summary'))]
+        for clave, titulo, color in TRANSACTION_CHARTS:
+            partes.append(_unidad(titulo, color, graf.get(clave), sec.get('chart_' + clave)))
+        partes.append(_caja('Conclusiones de la Transaccion', sec.get('conclusions'), permitir_corte=True))
+        partes.append(_caja('Recomendaciones de la Transaccion', sec.get('recommendations'), permitir_corte=True))
+        bloques.append(''.join(partes))
+
+    return ''.join(bloques)
+
+
 def cover_meta_parts(meta: Dict[str, Any]) -> Dict[str, str]:
     """N2.3: piezas de la fila de metadatos de la portada (PDF y HTML).
 
@@ -930,6 +1053,9 @@ tbody tr:nth-child(even) {{
 {ai_box('conclusions', 'Conclusiones', '#4f46e5', allow_break=True)}
 {ai_box('recommendations', 'Recomendaciones', '#4f46e5', allow_break=True)}
 
+<!-- ===== N4.8: MINI-INFORME POR TRANSACCION (despues de las conclusiones generales) ===== -->
+{transaction_reports_html(meta.get('transaction_reports'))}
+
 <!-- ===== FOOTER ===== -->
 <div class="report-footer">
     <strong>sqa &mdash; Software Quality Assurance</strong><br>
```

### 3.2 `export_pdf.py` — resumen del añadido (166 lineas)

| Añadido | Que hace |
|---|---|
| `TRANSACTION_CHARTS` al import | las 5 claves y sus titulos, desde `report_generator` |
| `_tx_points()` | puntos de N4.3 -> `(timestamps, valores)`, con `pd.Timestamp` |
| `_tx_charts()` | las 5 graficas de una transaccion con `chart_multiline` / `chart_area` |
| `_criticidad()` | la linea del encabezado, determinista, con los umbrales de N3.2 |
| `_build_transaction_reports()` | consulta, ordena, calcula series y arma la lista |
| 2 lineas en el flujo | `meta['transaction_reports'] = await _build_transaction_reports(...)` antes de `build_pdf_html` |

El orden de aparicion de los bloques es el de la tabla resumen (lo que el lector
acaba de ver). Un fallo en una transaccion la deja sin graficas y sigue con las
demas: un mini-informe no puede tumbar la generacion del PDF entero.

---

## 4. Validacion

Metodo: se generaron los PDF **antes** (restaurando los `.bak_n48` en el
container y reiniciando) y **despues**, y se comparo por extraccion de texto con
PyMuPDF. Ninguna llamada de IA en todo el proceso.

### 4.1 Tolerancia — ejecucion SIN mini-informes ("caso 1")

| | Antes | Despues |
|---|---|---|
| Paginas | **7** | **7** |
| Bytes | 811.842 | 811.844 |
| Imagenes unicas | 8 | 8 |

```
texto identico pagina a pagina (con pie incluido): True
menciona "MINI-INFORME": False
```

**Las 7 paginas salen con el texto identico, caracter por caracter, pie de pagina
incluido.** Los 2 bytes de diferencia son metadatos de creacion del propio
WeasyPrint. Sin titulo huerfano.

### 4.2 Coomeva — conteo de paginas y de graficas

| | Antes | Despues | Delta |
|---|---|---|---|
| Paginas | **8** | **12** | +4 |
| Bytes | 852.912 | 1.315.821 | +462.909 |
| Imagenes unicas | **9** | **14** | **+5** |

Las +5 imagenes son exactamente las 5 graficas de `token`. (El conteo es de
xrefs deduplicados: WeasyPrint comparte el diccionario de recursos entre paginas,
asi que `get_images()` por pagina devuelve el catalogo completo y engaña.)

```
paginas 1..8 con contenido intacto: 7/8  (solo cambia el "de N" del pie)
```

La unica diferencia en las 8 paginas previas es el pie `Pagina X de 8` -> `de 12`,
que es lo que tiene que pasar al crecer el documento. La portada no lleva pie y
por eso sale identica tambien con el pie incluido.

### 4.3 Coomeva — el bloque, pagina a pagina

```
pag  6 : Conclusiones (general)
pag  7 : Recomendaciones (general)
pag  8 : (fin del texto general)
pag  9 : MINI-INFORME POR TRANSACCION | token | pico de 21,060 ms, 48x el promedio ·
         pico absoluto de 21,060 ms (>=10 s, posible timeout) | Metricas de la Transaccion
pag 10 : Tiempos de Respuesta | Analisis - Tiempos de Respuesta | ...
pag 11 : Codigos de Respuesta | Analisis - Codigos de Respuesta | ...
pag 12 : Recomendaciones de la Transaccion | ...
```

El bloque arranca en la pagina 9, la primera pagina nueva: **va despues de las
conclusiones generales y abre pagina**.

**Tabla de metricas:** cabecera "Metricas de la Transaccion" presente y
**14/14 columnas** del resumen general (Transaccion, Muestras, Errores, % Error,
Promedio, Mediana, P90, P95, P99, Min, Max, TPS, KB/s Recv, KB/s Sent).

**Las 5 graficas con su texto al lado:**

```
Tiempos de Respuesta        titulo=True  caja "Analisis - Tiempos de Respuesta"=True
Latencia                    titulo=True  caja "Analisis - Latencia"=True
Tasa de Error               titulo=True  caja "Analisis - Tasa de Error"=True
Codigos de Respuesta        titulo=True  caja "Analisis - Codigos de Respuesta"=True
Transacciones por Segundo   titulo=True  caja "Analisis - Transacciones por Segundo"=True
```

**Las 8 secciones: 8/8 presentes.** Ademas se contrasto contra la base: los
primeros 60 caracteres de cada uno de los 8 registros de
`transaction_chart_analyses` aparecen en el texto extraido del PDF.

```
summary                SI     chart_codes            SI
chart_response_times   SI     chart_tps              SI
chart_latency          SI     conclusions            SI
chart_error_rate       SI     recommendations        SI
```

### 4.4 Tolerancias, ejercitando la funcion real en el container

```
1. Sin mini-informes: None -> ''   [] -> ''            (el bloque no se pinta)

2. Dos secciones sin texto (una fallo, otra ni existe como fila):
   unidades grafica+texto : 5
   imagenes de grafica    : 5
   notas "su texto no se genero" : 2
   -> las 5 graficas siguen ahi y 2 llevan nota: True   (criterio N3.5)

3. Transaccion sin metricas en el resumen:
   aviso presente: True                                (se dice, no se calla)

4. Reglas 11 y 17 sobre el HTML del bloque:
   display:flex False | display:grid False
   unidades rem : ninguna
   unidades mm/pt: 10 ocurrencias

5. Dos transacciones -> page-break-before:always: 2     (una pagina nueva cada una)
```

---

## 5. Comprobaciones

| Check | Resultado |
|---|---|
| `py_compile` de los dos archivos | OK |
| Ciclo Docker | `docker restart jmeter_backend`, sin build |
| Archivos de codigo tocados | 2 — bajo el limite de 4 |
| Diff de `report_generator.py` | completo, punto 3.1 |
| Lineas borradas o modificadas | 0 — 292 insertadas |
| Backups | `.bak_n48_20260819_223133` de ambos |
| Llamadas de IA | 0 |
| Reglas 11 y 17 (table layouts, mm/pt) | verificadas sobre el HTML generado |
| `export_html.py` | **no modificado** — N4.8 es solo PDF |
| `origin` (Azure DevOps) | **no tocado** |
| Push | remoto `github` |

---

## 6. PDFs para revisar

En `C:\Users\FredyGabrielBonillaB\Documents\N21_PDFs_comparacion\`:

| Archivo | Que es |
|---|---|
| `individual_N48.pdf` | **Coomeva con el bloque** — 12 paginas, el mini-informe de `token` arranca en la 9 |
| `individual_N48_ANTES.pdf` | El mismo reporte antes del cambio — 8 paginas, para comparar |
| `individual_N48_sin_miniinforme.pdf` | Ejecucion sin mini-informes — 7 paginas, identica a la de antes |

---

## 7. Estado

Pendiente de **validacion visual de Fredy** sobre `individual_N48.pdf`:
encabezado de `token` en pagina 9, su tabla de metricas, el analisis de resumen,
las 5 graficas con el texto al lado y las conclusiones y recomendaciones de la
transaccion al cierre.
