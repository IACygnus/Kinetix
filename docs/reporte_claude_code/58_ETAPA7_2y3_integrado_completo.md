27c2745 · 2026-09-17

# ETAPA 7.2 y 7.3 — El informe integrado, completo (D57–D61)

**Llamadas reales a la IA: 0.** Todo se validó sobre informes ya generados, volviéndolos a
exportar. La prueba de punta a punta **deja el texto como estaba**: restaura el original al
terminar.

---

## 1. Qué se implementó

### D57 — la pantalla muestra lo mismo que el informe individual

Una línea de guarda era todo:

```tsx
-  {!embedded && (<TransactionReportSection … />)}
+  <TransactionReportSection … onAnalysisEdit={embedded ? onAnalysisEdit : undefined} … />
```

Las otras tres guardas `!embedded` de `Dashboard.tsx` **se quedan**, y el comentario lo deja
escrito: las conclusiones y recomendaciones de cada ejecución las consolida el integrado
(v1.2 §0), y los botones de exportación y el indicador de autoguardado son de la pantalla
individual.

Medido sobre `8713aad1` (dos ejecuciones: una con 3 transacciones, otra con 0):

| | Antes | Después |
|---|---|---|
| Gráficas recharts | 21 | **36** |
| Títulos "Response Times por Transacción" | 2 | **5** |
| Tablas "Reporte Resumen" | 4 | **7** |

Las 15 gráficas nuevas son exactamente 3 transacciones × 5 gráficas, y los 3 títulos nuevos,
sus 3 bloques. El mismo número que el informe individual de esa ejecución.

### D58 — editar dentro del integrado no toca la ejecución

`TransactionReportSection` recibe dos props opcionales. Con `onAnalysisEdit` —que es el canal
que el integrado **ya tenía** para las cajas del informe general (F4)— la edición emite un
override en vez de escribir:

```ts
if (onAnalysisEdit) onAnalysisEdit(executionId, claveOverrideTx(label, section), texto);
else                await api.put(`/executions/${id}/transaction-report/${section}?label=…`, …);
```

La clave es `tx|<label>|<section>` — estable, legible, sin depender de ningún orden ni id
generado. Se guarda en el mismo `sections[i].overrides.analysis` que las demás.

**Sin la prop, el informe individual se comporta exactamente como antes de esta etapa.**

### D59 — los exportados aplican los overrides

El reporte 57 encontró que los dos exportadores del integrado ya traían los bloques por
transacción, pero leyendo directo de `transaction_chart_analyses`, sin overrides. Se añadió
`_aplicar_overrides_tx`, que los pisa **después** de construirlos:

```python
meta['transaction_reports'] = _aplicar_overrides_tx(
    await _build_transaction_reports(db, execution, _df_tx, statistics), overrides)
```

**Vive en `integrated_report.py`, que no es protegido.** Era la decisión importante: meter
el parámetro dentro de `_build_transaction_reports` / `build_transaction_reports_plotly`
habría tocado `export_pdf.py` y `export_html.py`, los dos protegidos y **fuera de lo que
autoriza D62**. Los constructores siguen devolviendo lo que hay en base y el integrado
decide encima; el informe individual no se entera.

### D60 — los integrados existentes no se migran

Un integrado sin overrides no tiene claves `tx|`, así que `_overrides_por_transaccion`
devuelve `{}` y todo sale con los textos originales. Hay precedente del mismo criterio:
`ai_analysis_throughput` salió del mapa en la Etapa 2 y sus overrides siguen en la base, sin
pintarse y sin borrarse.

### D61 — el consolidado no cambia

`_section_analyses_for_prompt` itera sobre `_SECCION_LABEL`, que son nombres de columna, así
que las claves `tx|` nunca entran en su prompt. **Verificado leyendo el código; sin cambios.**

## 2. Archivos tocados

| Archivo | +/− | Protegido |
|---|---|---|
| `frontend/src/components/dashboard/TransactionReportSection.tsx` | +52 / −4 | no |
| `backend/app/api/v1/endpoints/integrated_report.py` | +59 / −2 | no |
| `frontend/src/components/dashboard/Dashboard.tsx` | **+16 / −8** | **sí** |

`DashboardEmbed.tsx` e `IntegratedReportPage.tsx` **no se tocaron**: el canal
`onAnalysisEdit` y el diccionario `analysisOverrides` ya bajaban hasta `Dashboard`, y desde
ahí solo había que reenviarlos.

**Presupuesto D62: 40 líneas reales en `Dashboard.tsx`. Reales: 16, de las cuales 8 son el
comentario que explica por qué esa guarda sale y las otras tres se quedan.** Ningún otro
archivo protegido. Copias de seguridad `*.bak_etapa7_7.2_20260917`.

## 3. Verificación — 16 comprobaciones, 0 llamadas a la IA

`integrado_completo_73.py`, sobre `8713aad1` y la transacción `4. Get_Booking_Id`,
sección `chart_tps`.

| Bloque | Resultado |
|---|---|
| **1. La pantalla** — individual 26 gráficas / 4 títulos; integrado 36 / 5. Los bloques por transacción **coinciden: 3 y 3** | PASA (3) |
| **2. Editar** — se localiza la caja de esa sección en la pantalla del integrado y se escribe | PASA |
| **3. Dónde quedó** — el override `tx\|4. Get_Booking_Id\|chart_tps` está en `integrated_reports.sections`; **`transaction_chart_analyses` NO cambió**; al recargar el integrado el texto sigue; Historial Reporte de esa ejecución **no** lo muestra y conserva el suyo | PASA (5) |
| **4. Exportados** — `export-html` 200 con los **3 bloques** y **el texto editado**; `export-pdf` 200, 3.084.778 bytes, PDF válido | PASA (4) |
| **5. El HTML en el navegador** — **cero errores de consola** | PASA |
| **6. Restaurar** — el PATCH quita el override, no queda ninguna clave `tx\|` y la ejecución sigue con su texto original | PASA (3) |

La prueba es reversible por diseño: al terminar, la base queda como estaba.

### Regresiones

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` (diez pasos, cuatro salidas) | **LAS CUATRO SALIDAS PASAN** |
| `criterios_5b2.py` (Etapa 5b, prompts) | TODO PASA |
| `panel_boton_criterios.py` (Etapa 5b, pantalla) | TODO PASA |
| `capas_tooltip.py` (Etapa 6.2) | TODO PASA |
| `export_alcance.py` (Etapa 6.3) | TODO PASA |
| `capas_exportadas.py` (Etapa 6.4) | TODO PASA |
| `pytest` | 492 pasan, 1 falla — la anterior al plan |
| `npx tsc --noEmit` · `py_compile` | limpios |

## 4. Lo que queda señalado

- **`ExecutionReportSection.tsx` (195 líneas) sigue sin que nadie lo importe.** Es la
  plantilla paralela que quedó huérfana cuando el integrado pasó a `DashboardEmbed`. No se
  retira en esta etapa porque no está en las decisiones; queda anotado como en su día quedó
  `transaction_analyses_html`, que sí se retiró en la Etapa 6 una vez confirmado.
- El integrado sigue **sin selector de transacciones** al exportar, por v1.2 §6 (D59).

---

**Estado:** 7.2 y 7.3 implementadas y verificadas, pendiente validación de Fredy. Ninguna
condición de parada. Sigue 7.4 — preparación del despliegue de análisis (solo documento).
