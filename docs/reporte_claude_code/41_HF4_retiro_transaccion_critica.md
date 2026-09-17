9a92de8 · 2026-09-17

# HF-4 — Se retira el bloque «Análisis por Transacción Crítica»

**Llamadas reales a la IA: 0.** Solo se leyó lo ya guardado y se volvieron a
construir informes con ello.

**Autorización de Fredy:** `export_html.py`, `report_generator.py`,
`export_pdf.py` y `Dashboard.tsx`, **solo** para retirar ese bloque.

---

## 1. Diagnóstico: dónde estaba y qué lo alimentaba

El bloque lo pintaba una única función, `transaction_analyses_html`
(`report_generator.py:202`), desde las filas de **`transaction_analyses`** —una
tabla que desde N3.4 es **legacy de solo lectura**—, y lo llamaban tres sitios:

| Salida | Quién lo pintaba | Quién cargaba los datos |
|---|---|---|
| **PDF individual** | `report_generator.py:1113` (dentro de `build_pdf_html`) | `export_pdf.py:463` |
| **HTML individual** | `export_html.py:1270` | `export_html.py:742` |
| **Integrado (HTML y PDF)** | `integrated_report.py:752` | `_load_transaction_analyses` + dos llamadas (líneas 230 y 914) |
| **Pantalla** | **nadie** | — |

### El hallazgo: en pantalla nunca estuvo

`Dashboard.tsx` **no pinta ese bloque**. Lo único que la pantalla usa de
`GET /executions/{id}/transaction-analyses` es la **lista de etiquetas** con la
que `TransactionReportSection.tsx:289` decide qué transacciones tienen bloque
propio. El texto `ai_analysis` de esa tabla no se lee en el frontend.

**Consecuencia: `Dashboard.tsx` no se tocó.** La autorización estaba, no hizo
falta usarla.

Y se confirma lo que dice D38 sobre por qué molestaba: la caja se pintaba igual
aunque no hubiera texto, con la nota *«Esta transaccion se marco como critica
pero no se genero su analisis individual»*. Desde N3.4 esa fila casi nunca trae
texto, así que lo habitual era ver esa frase.

---

## 2. Qué se cambió

| Archivo | Cambios reales | Qué |
|---|---|---|
| `report_generator.py` *(protegido)* | **23** (19+/4−) | Se retira la llamada; la función queda documentada como retirada y sin usar; el título de la tabla por transacción pasa a ser el del general |
| `export_html.py` *(protegido)* | **19** (5+/14−) | Fuera el import, el cargador de datos, la llamada; título de la tabla igualado |
| `export_pdf.py` *(protegido)* | **15** (4+/11−) | Fuera el cargador de datos |
| `integrated_report.py` | **27** (5+/22−) | Fuera el import, `_load_transaction_analyses`, sus dos llamadas y el punto de pintado |
| `Dashboard.tsx` *(protegido)* | **0** | No pintaba el bloque |

Ninguno pasa de 40 líneas reales: el máximo son las 27 de `integrated_report.py`,
que además no es protegido.

**Las filas de `transaction_analyses` no se tocan.** Siguen ahí, se siguen
creando en cada upload y la pantalla las sigue usando para saber qué
transacciones abrir. Lo único que cambia es que **ya no se leen para exportar**.

### Decisión técnica que tomé y declaro

| # | Decisión | Por qué |
|---|---|---|
| **T16** | `transaction_analyses_html` **se conserva**, sin usar, con un encabezado que dice que HF-4 la retiró | Borrarla entera son 46 líneas en un archivo protegido cuya autorización es «solo para retirar el bloque», y el presupuesto era 40. Dejarla desconectada retira el bloque al 100 % y permite volver atrás con una línea. Queda anotado que, si sigue sin usarse, se puede retirar entera |
| **T17** | El nombre del bloque **no se escribe ni en los comentarios** del HTML | La primera versión del comentario llevaba la frase y el PDF la seguía conteniendo: los comentarios viajan dentro del documento entregado. Es la misma lección que D22 con «mini-informe», y el detector la cazó |

---

## 3. El encabezado y la tabla por transacción, igualados al general

Las cuatro salidas ya usaban **exactamente las mismas 14 columnas**
(Transaccion · Muestras · Errores · % Error · Promedio · Mediana · P90 · P95 ·
P99 · Min · Max · TPS · KB/s Recv · KB/s Sent). Lo único desalineado era el
**título**:

| Salida | Antes | Ahora |
|---|---|---|
| Pantalla | `Reporte Resumen` | *(ya estaba bien)* |
| **PDF** | `Metricas de la Transaccion` | **`Reporte Resumen por Transaccion`** |
| **HTML** | `Metricas de la Transaccion` | **`Reporte Resumen por Transaccion`** |
| Integrado | hereda del HTML | **igualado** |

En pantalla ya coincidían porque `SummaryTable.tsx` tiene un único
`titulo = 'Reporte Resumen'` por defecto y lo usan los dos alcances (D15/D21).

---

## 4. Validación

Nuevo paso **10** en `verificar_etapa2.py`, con su script `hf4_check.py`, sobre
las **cuatro salidas** y **cero llamadas a la IA**:

- que no aparezca `Transaccion Critica` ni `Transacción Crítica`;
- que no aparezca `no se genero su analisis individual` ni su versión con tildes;
- que el título de la tabla del general aparezca **exactamente `1 + n` veces**
  (el general más un bloque por transacción);
- que **esas `1 + n` tablas lleven las mismas 14 columnas**.

Corrido sobre las dos ejecuciones que pedía el plan:

| Ejecución | Resultado |
|---|---|
| `E3-estilo-pruebakinetix` (`20bb2356-…`) | **24 de 24** — «EL BLOQUE NO ESTA EN NINGUNA DE LAS CUATRO SALIDAS» |
| `E2-validacion` (`59e25069-…`) | **24 de 24** — ídem |

```
PASA  | Pantalla: sin 'Transaccion Critica'
PASA  | Pantalla: 4 tablas 'Reporte Resumen' (general + transacciones)
PDF individual: 3.549.668 chars · 3 bloques por transaccion
PASA  | PDF: el titulo 'Reporte Resumen por Transaccion' aparece 4 veces
        (1 del general + 3 por transaccion)
PASA  | PDF: las 4 tablas llevan las mismas columnas
...
HF-4: EL BLOQUE NO ESTA EN NINGUNA DE LAS CUATRO SALIDAS
```

Y `verificar_etapa2.py` completo, ahora con **diez pasos**, sobre
`E3-estilo-pruebakinetix`:

```
ETAPA 2 — LAS CUATRO SALIDAS PASAN
```

---

## 5. Lo que este sub-paso NO hizo

- **No tocó la base.** Ni una fila de `transaction_analyses`.
- **No tocó `Dashboard.tsx`.** No hacía falta.
- **No tocó el panel de selección**: eso es la Etapa 5, que empieza en el
  reporte 42.
