# GRAF1-C — Serie dual avg/max en los exports (cierre de GRAF1)

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado y validado por endpoint. **Pendiente: validación visual de Fredy** (criterio único de éxito).
**Alcance:** 5 archivos, **+67 / −12 líneas** (≈55 netas). Presupuesto: 5-6 archivos / ~50-65 líneas. Dentro.
**Base:** `docs/reporte_bug/graf1-fix-serie-dual.md` §2 (filas 5-8) y §3. Consume el `value_max` de GRAF1-A.

---

## 1. Qué cambió

| # | Archivo | Δ | Cambio |
|---|---|---:|---|
| 1 | `services/export/report_generator.py` 🔒 | +21/−7 | `MAX_SERIES_SUFFIX` + `chart_multiline(..., dual_max=False)` con estilo por serie |
| 2 | `services/export/high_cardinality_strategy.py` | +6/−1 | `value_max=('value_max','max')` en la serie "Resto" (el hueco conocido) |
| 3 | `endpoints/export_pdf.py` | +8/−2 | `_build_series(..., with_max=True)` + `dual_max=True` |
| 4 | `endpoints/export_html.py` | +15 | 2º trace Plotly punteado por transacción |
| 5 | `endpoints/integrated_report.py` | +17/−2 | **5º consumidor** — ramas PDF (`:115-126`) y HTML (`:901-919`) |

### Diff completo de `report_generator.py` (archivo protegido)

```diff
 # Public chart functions
 # ---------------------------------------------------------------------------
 
+# GRAF1-C: sufijo que marca la serie de maximos (misma convencion que el dashboard)
+MAX_SERIES_SUFFIX = ' (max)'
+
 def chart_area(timestamps, values, color, ylabel, fill=True):

-def chart_multiline(series_list, ylabel, use_code_colors=False):
+def chart_multiline(series_list, ylabel, use_code_colors=False, dual_max=False):
     """Multi-series line chart → base64 PNG.
 
     series_list: list of (label, timestamps, values)
+    dual_max: GRAF1-C — las series cuyo nombre termina en MAX_SERIES_SUFFIX se
+        dibujan finas y punteadas, con el color de su serie base y sin entrada
+        en la leyenda. Con dual_max=False el resultado es identico al de siempre.
     """
     all_x: list = []
     all_labels: list = []
-    for idx, (label, timestamps, values) in enumerate(series_list):
+    base_colors: dict = {}
+    for label, timestamps, values in series_list:
         x_secs, x_labels = make_time_labels(timestamps)
         if not x_secs:
             continue
-        if use_code_colors:
-            color = get_code_color(label.replace('HTTP ', ''))
+        is_max = dual_max and label.endswith(MAX_SERIES_SUFFIX)
+        if is_max:
+            color = base_colors.get(label[:-len(MAX_SERIES_SUFFIX)], '#94a3b8')
+        elif use_code_colors:
+            color = base_colors[label] = get_code_color(label.replace('HTTP ', ''))
+        else:
+            color = base_colors[label] = get_color_for_index(len(base_colors))
+        if is_max:
+            ax.plot(x_secs, values, color=color, linewidth=0.8, linestyle='--',
+                    alpha=0.85, label='_nolegend_')
         else:
-            color = get_color_for_index(idx)
-        ax.plot(x_secs, values, color=color, linewidth=1.5, label=label)
+            ax.plot(x_secs, values, color=color, linewidth=1.5, label=label)
         if len(x_secs) > len(all_x):
 
-    ncol = min(4, len(series_list))
+    ncol = min(4, max(1, len(base_colors)))
```

Tres decisiones a señalar:

- **`label='_nolegend_'`** es la convención de matplotlib para excluir una serie de la leyenda — equivalente al `legendType="none"` de Recharts en GRAF1-B y al `showlegend: False` de Plotly. Los tres exports y la pantalla usan el mismo criterio: **3 entradas de leyenda, 6 líneas**.
- **El color se indexa con `len(base_colors)`, no con el índice del bucle.** Sin esto, al intercalar avg/max las series promedio cogerían los colores 0,2,4 y **cambiarían de color respecto a hoy**. Con el diccionario, los promedios conservan exactamente sus colores actuales y cada máximo reusa el de su promedio.
- **`ncol`** ahora cuenta entradas de leyenda, no series dibujadas (si no, con 3 transacciones la leyenda pasaría a 4 columnas).

⚠️ **Único matiz de comportamiento:** una serie vacía ya no consume un índice de color (antes `enumerate` sí lo consumía). En la práctica no ocurre: `_build_series` descarta los sub-DataFrames vacíos antes de llegar aquí.

---

## 2. Evidencia — export individual

### HTML (Plotly)

```
$ grep -o '"name": "[^"]* (max)"' new.html | sort | uniq -c
      1 "name": "Adapter SendCode (max)"
      1 "name": "Adapter VerifMethod (max)"
      1 "name": "token (max)"
"dash": "dot"      → 3
"showlegend": false → 3
```

Valores reales dentro de los traces del HTML generado:

| Trace | puntos | max |
|---|---:|---:|
| `token` | 1.666 | 7.243 ms |
| **`token (max)`** | 1.666 | **21.060 ms** |
| `Adapter VerifMethod` | 1.650 | 12.110 ms |
| **`Adapter VerifMethod (max)`** | 1.650 | **21.058 ms** |

### PDF (WeasyPrint + matplotlib)

Instrumenté el `Axes` real que dibuja `chart_multiline` (espía sobre `plt.subplots`, sólo lectura):

```
series al chart : 6
lineas dibujadas: 6
entradas leyenda: 3  ['token', 'Adapter VerifMethod', 'Adapter SendCode']
ylim            : -930 -> 22107   ← cubre los 21.060
   token                  lw=1.5 ls=-   color=#3b82f6
   _nolegend_             lw=0.8 ls=--  color=#3b82f6   ← mismo color que su promedio
   Adapter VerifMethod    lw=1.5 ls=-   color=#ef4444
   _nolegend_             lw=0.8 ls=--  color=#ef4444
   Adapter SendCode       lw=1.5 ls=-   color=#10b981
   _nolegend_             lw=0.8 ls=--  color=#10b981
PNG dual != PNG solo-promedio: True (285.812 vs 167.544 bytes)
```

### Tamaño y páginas

| Export | Antes (GRAF1-A) | Después (GRAF1-C) | Δ |
|---|---:|---:|---:|
| HTML individual | 465.993 B | 617.766 B | **+32,6 %** |
| PDF individual | 868.949 B | 951.027 B | **+9,4 %** |
| **Páginas PDF** | **14** | **14** | **estable** |

Tiempos: HTML 1,40 s · PDF 4,26 s. Ambos HTTP 200.

---

## 3. Evidencia — informe integrado (5º consumidor)

Exportado el informe guardado `2c5ba18e…` (3 secciones: Coomeva + Coomeva_2 + monitoreo), pasando su `report_id` para leer los overrides reales. **Los endpoints de export no escriben en DB** (verificado: sólo `_load_section_overrides`, que es lectura) — no se creó ningún informe nuevo.

| Rama | HTTP | Tamaño | Tiempo | Evidencia |
|---|---:|---:|---:|---|
| **HTML** | 200 | 4.091.383 B | 2,61 s | **6** traces `(max)` (2 ejecuciones × 3 labels), 6 × `"dash": "dot"`, 6 × `"showlegend": false` |
| **PDF** | 200 | 3.549.565 B | 9,04 s | `%PDF-1.7`, **27 páginas**; el `Axes` de su rama: 6 series, 6 líneas, **3 entradas de leyenda**, ylim hasta 22.107 |

No tengo línea base de páginas del integrado previa al cambio (no se capturó antes de editar); el conteo del **PDF individual sí está verificado estable en 14/14**.

---

## 4. Evidencia — tolerancia y alta cardinalidad

### Datos sin `value_max` (informes viejos / cacheados)

Simulado eliminando la columna de los DataFrames reales:

```
series con with_max=True sobre datos viejos: 3  ['token','Adapter VerifMethod','Adapter SendCode']
PNG identico al de hoy (byte a byte): True
trace plotly extra? value_max in columns -> False
top_n sin value_max: OK, 3 series
```

**El PNG sale byte a byte idéntico** al que produce la ruta de siempre. Ni línea extra, ni entrada de leyenda, ni error. Las tres guardas (`with_max and 'value_max' in sub_df.columns`, `'value_max' in sub_df.columns` en Plotly, y `dual_max` en el chart) son independientes: basta una para que el export degrade a promedio.

### El hueco de `high_cardinality_strategy.py` (15+ labels)

Simulado con 20 transacciones sintéticas a partir de los datos reales:

```
entrada: 20 -> salida: 11 | suffix: 'Top 10 de 20 transacciones'
serie agregada : 'Resto (10 transacciones)'
columnas       : ['timestamp', 'value', 'value_max', 'label']   ← antes se perdia value_max
max(value)     : 2.986 ms
max(value_max) : 21.060 ms
```

Antes de este cambio la serie "Resto" llegaba **sin** `value_max`: en una prueba de 15+ transacciones los máximos del grupo agregado habrían desaparecido del PDF y del HTML. Ahora se conservan, y si la columna no existe el `agg` simplemente no la incluye.

---

## 5. ⚠️ Punto (5) NO implementado — sigue sin confirmación

Igual que en GRAF1-B, el prompt condicionaba el cambio de umbral en `gemini.py` a que *"el mensaje que acompaña este prompt confirme el umbral de 10000ms"*. **No llegó esa confirmación**, así que no lo apliqué. `gemini.py` sigue como en GRAF1-A: `P99/avg > 3x` **o** `max/avg > 10x`.

El caso que lo motiva sigue vivo: **`Adapter VerifMethod` tiene max = 21.058 ms pero ratio 7,2x**, así que no dispara la alerta de variabilidad (su máximo sí es visible en su línea de tier). La línea exacta, cuando Fredy confirme:

```python
if tx['avg'] > 0 and (tx['p99'] / tx['avg'] > 3 or tx['max'] / tx['avg'] > 10 or tx['max'] >= 10000):
```

---

## 6. Historial GRAF1 (hashes)

```
$ git log --oneline -5
1c0d0d0  GRAF1-C: serie dual avg/max en exports PDF/HTML/integrado (cierre GRAF1)
0aa43b6  GRAF1-B: linea de maximos en Response Times del dashboard
337b018  GRAF1-A: serie dual avg/max 1s + maximos al encuadre de la IA
b0eb62f  GRAF1: diagnostico de alcance (fix detenido por tope de archivos) + salvaguarda 4b4e5977
c3e3bb4  DPERF-1: quitar sleeps del pipeline + precarga SDK + DEBUG off (fixes B/C/D)
```

| Fase | Hash | Entrega |
|---|---|---|
| A | `337b018` | `value_max` en el dato + máximos en el encuadre de la IA |
| B | `0aa43b6` | 2ª línea en el dashboard |
| C | (este) | 2ª línea en PDF, HTML e informe integrado + serie "Resto" |

---

## 7. Validación visual para Fredy (criterio único de éxito)

Ejecución **115346ea** (Coomeva 31-jul). Exportar **PDF** y **HTML**, y comparar las tres vistas:

1. **Pantalla · PDF · HTML deben contar la misma historia:** 3 líneas sólidas (promedios) + 3 punteadas finas del mismo color, eje Y llegando a ~21.000 ms, leyenda de 3 entradas en las tres.
2. **Contra JMeter** (su gráfica a 500 ms): las espigas de `token` y `Adapter VerifMethod` deben coincidir en posición temporal y altura (~21 s).
3. **Legibilidad con 3 transacciones** — el juicio pendiente. En el PDF son 6 líneas en 180 mm; si satura, los ajustes de un carácter son `alpha` (0.85) o `linewidth` (0.8) en `chart_multiline`, y `width`/`dash` en los traces Plotly.
4. **Informe integrado:** el de Coomeva con 2 ejecuciones — verificar que ambas secciones muestran su dual y que la leyenda no se duplicó.
5. Abrir un **informe antiguo** ya exportado y confirmar que sale como siempre (sin punteados, sin huecos).

---

## 8. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- Backups `.bak_graf1c_20260814_102950` de los 5 archivos.
- `py_compile` OK en los 5 · `docker restart jmeter_backend` sin build · `Application startup complete`.
- **Ningún análisis IA ejecutado** — cuota intacta. Los exports no invocan al modelo.
- Los exports de validación no crearon registros en `integrated_reports` (se reusó el `report_id` existente y los endpoints de export son de sólo lectura).

**Con esto cierra GRAF1:** los picos de ~21 s existen en el dato, llegan a la IA, se ven en pantalla y salen en los tres exports.
