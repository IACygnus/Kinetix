# UI-2 — Veredicto fuera de exports + bloque del logo estructurado + retiro de "Response Time Over Time"

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado y validado por endpoint. **Pendiente: validación visual de Fredy** (criterio único de éxito).
**Alcance:** 6 archivos, **+58 / −205 líneas** (saldo **−147**: es un cambio mayoritariamente de borrado).

| Archivo | + | − |
|---|---:|---:|
| `services/export/report_generator.py` 🔒 | 24 | 80 |
| `endpoints/integrated_report.py` | 12 | 45 |
| `endpoints/export_html.py` | 10 | 43 |
| `services/ai/analysis_pipeline.py` | 6 | 18 |
| `components/dashboard/Dashboard.tsx` 🔒 | 5 | 18 |
| `endpoints/export_pdf.py` | 1 | 1 |

`py_compile` OK (5 backend) · `tsc --noEmit` **exit 0** · backend reiniciado sin build · backups `.bak_ui2_20260814_105750`.

---

## 1. Punto (1) — Veredicto fuera de los exports

El badge APTO/NO APTO se retiró de **cuatro** puntos de emisión. **En pantalla se conserva intacto** (no se tocó ningún render de la app).

| Salida | Dónde vivía | Acción |
|---|---|---|
| PDF individual + integrado | `report_generator.py:265-276` (cálculo), `:752` (span en la portada), `:511-537` (CSS `.cover-verdict`) | Eliminados |
| HTML individual | `export_html.py:518-531` + `:827` (cabecera) | Eliminados |
| HTML integrado | `integrated_report.py:367-378` + `:612` (cabecera) | Eliminados |
| PDF integrado — ficha por sección | `integrated_report.py:1142-1151` (badge centrado bajo el `<h2>`) | Eliminado |

**Lo que SÍ se conserva:** el resumen del criterio en el pie de la portada (`Criterio: <2000ms, >99% disponibilidad`). Solo desaparece el juicio APTO/NO APTO, no los criterios.

### Evidencia — prueba forzada

Llamé a `build_pdf_html` con `acceptanceCriteria={'verdict': 'NO APTO'}` — es decir, con el veredicto presente en los datos, que es el caso en que antes se pintaba:

```
ocurrencias APTO/NO APTO : 0
clase cover-verdict      : 0
Criterio en el pie       : True (se conserva)
```

En los HTML realmente generados: **0 badges** en el individual y **0** en el integrado.

> ⚠️ **Nota de método:** los PDF de WeasyPrint usan fuentes subset, así que **el texto no es greppable dentro del `.pdf`** (un grep sobre el binario da 0 para *cualquier* cadena, incluso las que sí están). Por eso la evidencia del PDF es sobre el **HTML que WeasyPrint renderiza**, que es la fuente real, y no un grep del binario —que habría sido un falso positivo.

**Lo que NO se tocó, a propósito:** `integrated_report.py:1752-1842` pasa el veredicto como **dato de entrada al prompt** de las conclusiones consolidadas. No es un badge ni se pinta: es contexto para la IA. Retirarlo cambiaría el análisis, que no es lo que se pidió. Dilo si lo quieres fuera también.

---

## 2. Punto (2) — Bloque del logo como columna

Corrige N1.8: el logo quedaba huérfano en la celda derecha y el cliente se repetía a la izquierda.

**Ahora, con logo:** la celda derecha es una columna `CLIENTE → logo → nombre del cliente`, y la izquierda deja de repetir el cliente (se queda con el tipo de prueba). **Sin logo: layout clásico, sin hueco.**

### Evidencia — portada PDF, las dos ramas

```
=== CON logo ===
   celda 1: TIPO DE PRUEBA > Carga
   celda 2: NOMBRE DEL PROYECTO > Proy-X
   celda 3: DURACION > 0m 10s
   celda 4: CLIENTE > [LOGO] > Coomeva      ← columna completa

=== SIN logo ===
   celda 1: CLIENTE > Coomeva               ← layout de siempre
   celda 2: NOMBRE DEL PROYECTO > Proy-X
   celda 3: DURACION > 0m 10s
   celda 4: TIPO DE PRUEBA > Carga
```

En los HTML generados (individual e integrado), la estructura `Cliente → <img logo> → nombre` se detecta **OK en ambos**.

Restricciones respetadas: la portada PDF sigue en `table` (regla 11) con medidas en `mm`/`pt` (regla 17); el logo mantiene `max-height:26mm` y el nombre va bajo él con `text-align:right` heredado de la celda.

---

## 3. Punto (3) — Retiro de "Response Time Over Time"

⚠️ Verificado dos veces: se retira **"Response Time Over Time"** (promedio agregado). Se conservan **"Response Times por Transaccion"** (la fuente de verdad, con la serie dual de GRAF1) y todas las demás "… Over Time" (Throughput, Latency, Error Rate, Active Threads).

| Salida | Qué se quitó |
|---|---|
| **Pantalla** | Bloque completo de la gráfica + su `AnalysisBox`; contador "(8 graficas)" → "(7 graficas)"; `timelineData` (quedaba sin uso — `noUnusedLocals` lo habría rechazado) |
| **PDF individual** | Bloque en la plantilla + `ai_box` + el `chart_area` que lo generaba (`export_pdf.py:168`) |
| **HTML individual** | Bloque, `rt_over_time_traces`, parámetro de la firma, `_compute_trace_stats`, `Plotly.newPlot` |
| **PDF integrado** | `chart_area` de `rt_time` (`integrated_report.py:130`) |
| **HTML integrado** | Bloque, traces, `id_rt_time`, stats, `Plotly.newPlot`, entrada del dict |
| **Pipeline IA** | La llamada `analyze_chart('response_time_over_time', …)` **y** el `get_all_charts_data()` que solo servía para contar puntos de esa serie |

### Ahorro en el pipeline de IA

**Una llamada al modelo menos por análisis** (de 12 secciones a 11; el log pasa de `[3-10/12] 8 graficos` a `[3-9/12] 7 graficos`). Se elimina además una re-agregación completa del JTL (`get_all_charts_data`) que se hacía solo para el `len(timeline_df)` del prompt — relevante para DPERF-1.

**Los análisis ya guardados no se borran.** La columna `ai_analysis_response_time_over_time` sigue en DB, se sigue cargando y guardando desde el dashboard; simplemente ninguna plantilla la pinta. Para ejecuciones nuevas quedará vacía.

### Evidencia

```
HTML individual:  'Response Time Over Time'=0 | chart-rt-time=0
                  'Throughput Over Time'=3 (se conserva) | 'por Transaccion'=5 (se conserva)
HTML integrado:   'Response Time Over Time'=0 | chart-rt-time=0
                  'Throughput Over Time'=4 (se conserva) | 'por Transaccion'=8 (se conserva)
```

Prueba adicional en la plantilla PDF: inyecté `ia={'responseTimeOverTime': 'TEXTO-VIEJO-NO-DEBE-PINTARSE'}` → **0 ocurrencias** en el HTML renderizado. El texto guardado ya no se pinta aunque exista.

> Los comentarios `<!-- UI-2: … -->` que quedan en las plantillas se reformularon para **no contener la cadena literal**, de modo que un grep de verificación no dé falsos positivos. En la primera pasada el único "resto" detectado era exactamente eso: mi propio comentario.

---

## 4. Páginas del PDF y peso

| Export | Antes (GRAF1-C) | Después (UI-2) |
|---|---:|---:|
| PDF individual | 14 páginas · 951.027 B | **12 páginas** · 854.931 B |
| PDF integrado | 27 páginas · 3.549.565 B | **23 páginas** · 3.359.257 B |
| HTML individual | 617.766 B | 590.892 B |
| HTML integrado | 4.091.383 B | 4.037.347 B |

La bajada de páginas es **el efecto buscado**: cada sección pierde una gráfica y su caja de análisis (el integrado tiene 2 ejecuciones → −4). Lo que importaba mantener estable es **la portada**, que no se parte: sigue ocupando exactamente una página y el bloque de metadatos entra completo en la fila de la tabla.

Los 4 exports responden **HTTP 200**. Dashboard: frontend `200`, endpoint de charts `200`, HMR de Vite sin errores.

---

## 5. Punto (4) — ya aplicado en la sesión anterior

El umbral absoluto `tx['max'] >= 10000` **ya está en `gemini.py`** desde el commit `f069527`, aplicado tras tu confirmación al cierre de GRAF1-C. No se volvió a tocar en UI-2. Efecto vigente: la alerta de alta variabilidad recoge 2 transacciones (`token` y `Adapter VerifMethod`) en vez de 1.

---

## 6. Historial

```
$ git log --oneline -1
UI-2: veredicto fuera de exports + bloque logo estructurado + retiro Response Time Over Time
```

Anteriores: `f069527` (GRAF1-C.2 umbral) · `fad4f01` (GRAF1-C) · `0aa43b6` (GRAF1-B) · `337b018` (GRAF1-A).

---

## 7. Validación visual para Fredy — 4 salidas + pantalla

Ejecución **115346ea** (Coomeva) y el informe integrado de Coomeva:

1. **PDF individual** — portada: sin badge APTO/NO APTO; a la derecha `CLIENTE` → logo grande → `Coomeva`; a la izquierda tipo de prueba, proyecto y duración sin huecos. La portada no se parte.
2. **HTML individual** — misma cabecera; sin badge; la gráfica agregada ya no aparece y "Response Times por Transaccion" queda como primera gráfica.
3. **PDF integrado** — las 2 secciones sin badge (ni en cabecera ni bajo el título de cada sección) y con el bloque del cliente estructurado.
4. **HTML integrado** — ídem, y verificar que no quedó hueco donde estaba la gráfica retirada.
5. **Pantalla** — el panel dice "(7 graficas)", tras "Response Times por Transaccion" viene directamente "Throughput Over Time", y **todo lo demás sigue igual** (incluido el veredicto, que en la app se conserva).
6. **Un cliente sin logo** — exportar y confirmar el layout clásico (CLIENTE + nombre a la izquierda, tipo de prueba a la derecha).

---

## 8. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- **Ningún análisis IA ejecutado** — cuota intacta. Los exports no invocan al modelo.
- Sin `docker compose build`; solo `docker restart jmeter_backend` y HMR en el frontend.
- Los exports de validación no crearon registros: se reusó el `report_id` del informe guardado y esos endpoints son de solo lectura.
- `build_standalone_html` (`report_generator.py:877`) **no tiene ningún llamador** en el repo —es código muerto—, pero se limpió igual (veredicto y gráfica) para que no quede una plantilla contradictoria si algún día se conecta.
