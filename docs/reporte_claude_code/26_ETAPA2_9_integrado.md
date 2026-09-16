c957047 · 2026-09-16

# ETAPA 2.9 — El informe integrado

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.

Reporte del sub-paso 2.9, que quedó sin escribir cuando se encadenaron 2.10 y 2.11.
Commits: **`73ceee3`** (el integrado) y **`e1a5bc6`** (cierre de D19 en el frontend).
Ningún archivo protegido salvo las 6 líneas de `Dashboard.tsx` de `e1a5bc6`.

---

## 1. Qué hereda y qué había que hacer

El integrado **no tiene render propio de los bloques por transacción**: reutiliza
`_build_transaction_reports` de `export_pdf.py` (2.7b) y `transaction_reports_plotly_html`
de `export_html.py` (2.8b). Por eso **D21, D20, D16, D22 y D17 llegaron hechos**, sin tocar
una línea aquí.

Lo que sí era suyo:

| Decisión | Qué se hizo | Dónde |
|---|---|---|
| **D19** | Fuera la gráfica Throughput en las **dos** salidas del integrado: no se genera la imagen de matplotlib, no se calculan las *traces* de Plotly, no viaja `ai_analysis_throughput` y se retira el bloque de la plantilla | `integrated_report.py` |
| **D19** (vista previa) | Fuera la gráfica y la sección editable «Throughput» del panel de secciones | `ExecutionReportSection.tsx` |
| **D23** | `"ai_analysis_throughput"` sale de `_IA_KEY_BY_COLUMN` | `integrated_report.py` |
| — | `_strip_pdf_individual_conclusions`: el comentario describía un orden que D17 dejó obsoleto | `integrated_report.py` |

El escalar `throughput` (req/s) del KPI y de la tabla resumen **no se toca** en ninguna de
las dos salidas.

---

## 2. D23 al renderizar — lo que de verdad lo apaga

En 2.5 se sacó `ai_analysis_throughput` del **prompt del consolidado** (`_SECCION_LABEL`).
Eso impide que alimente a la IA, pero **no** impide que se pinte: el render usa otro mapa,
`_IA_KEY_BY_COLUMN`, que traduce columna de `test_executions` a clave del dict `ia` que
consumen las plantillas. Mientras la clave estuviera ahí, un override editado a mano seguía
apareciendo en el documento.

Sacarla del mapa es lo que apaga la sección. **Ninguna fila se borra**: en la base hay
informes reales con ese override escrito a mano, y se conservan por si la decisión cambia.
Ignorar, no borrar.

---

## 3. El recorte de conclusiones — el riesgo de la regla 18

El integrado toma el HTML del PDF individual y le quita las conclusiones de cada ejecución,
porque las consolidadas van una sola vez al final. El recorte va **de un comentario a otro**:

```
<!-- ===== CONCLUSIONES Y RECOMENDACIONES ... -->   ← desde aquí
...
<!-- ===== N4.8 | FOOTER ... -->                    ← hasta aquí
```

Antes de la etapa, el informe por transacción se emitía **entre** las conclusiones y el pie,
y por eso el patrón tenía que parar también en el marcador `N4.8`: sin eso, el recorte se
llevaba por delante los bloques por transacción. **Con D17 el informe por transacción va
antes de las conclusiones**, así que el corte de CONCLUSIONES a FOOTER vuelve a ser el
correcto. Se conserva la alternativa `N4.8` por si se procesa el HTML de un informe generado
antes del cambio.

El orden de los dos `_strip` (regla 18) **no se tocó**.

### Prueba

`e2e/integrado_pdf_html.py` espía el HTML que WeasyPrint va a renderizar, en los dos casos
que importan:

| Entrada | Resultado |
|---|---|
| Una sección con `ff186cc7` (3 informes por transacción) | **los 3 bloques sobreviven** al recorte · 0 bloques de conclusiones individuales |
| El informe guardado `fa724249` | **1** bloque de conclusiones, el consolidado · 0 bloques por transacción, porque sus dos ejecuciones no tienen informe por transacción en la base — es el dato, no una regresión |

Las dos salidas por HTTP: `export-html` **200**, 1.508.480 bytes, 1,7 s · `export-pdf`
**200**, 1.518.807 bytes, 5,0 s.

---

## 4. `e1a5bc6` — cierre de D19 en el frontend

Lo que quedaba de la gráfica retirada, ahora que ya no la pinta nadie:

- `Dashboard.tsx` (protegido, **6 líneas**): deja de preparar `throughput_timeline` y de
  pasar `throughputData` y `analysisThroughput` en el `ctx`.
- `ReportBody.tsx` y `TransactionReportSection.tsx`: fuera los campos del `ctx` que ya nadie
  usaba. `chartConfig.ts`: fuera `throughputOverTime`.

**El estado `ai_analysis_throughput` se sigue cargando y guardando**, igual que se hizo con
`response_time_over_time` en UI-2: el texto histórico no se pierde, solo deja de pintarse.

### Equivalencia

Comparación contra la pantalla anterior al cambio: **DOM normalizado idéntico, 0,000 % de
píxeles, mismas llamadas de datos, 26 gráficas.**

> Apunte de método: la primera comparación la hice contra una captura **anterior a D17** y
> dio diferencia —misma longitud de DOM, distinto orden—, que era exactamente el reordenado
> de `adeebcc`. Repetida contra la base correcta (misma revisión, solo sin `e1a5bc6`), pasa.
> La captura de referencia hay que renovarla después de cada cambio de estructura.
