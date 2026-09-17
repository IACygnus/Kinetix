3ba8fee · 2026-09-17

# ETAPA 6 — Cierre: gráficas, exportación y fin del plan de corrección

**Llamadas reales a la IA en toda la etapa: 0.** El presupuesto era ≤ 10. Todo se validó
sobre informes **ya generados** (`E3-estilo-pruebakinetix`, 3 transacciones; `E5-panel`,
2 transacciones), leyendo lo guardado y volviendo a exportarlo. Ni un `docker compose
build`.

Referencia: `docs/ESPECIFICACION-informe.md` v1.2 §3, §6 y §7.

---

## 1. Qué pedía la etapa y qué quedó

| Decisión | Qué pedía | Estado |
|---|---|---|
| **D46** | Selector "Ambas · Promedio · Máximo" por gráfica con serie dual, en el general y en cada bloque por transacción | Hecho. 1 + N selectores; ninguna gráfica de una sola capa lo lleva |
| **D47** | Tooltip con una línea por transacción, formato `Auth: 422 ms (máx. 1.013 ms)`, sin duplicados | Hecho. El máximo se pliega en la fila de su promedio |
| **D48** | Estado en memoria de sesión, no persistido; se envía al exportar | Hecho. `useChartLayers`, colgado de Dashboard |
| **D49** | PDF con la selección recibida; HTML abre con ella y ofrece el mismo control | Hecho en las dos salidas |
| **D50** | Diálogo al exportar: "Solo informe general" o "General y transacciones" | Hecho. Solo en los individuales |
| **D51** | Parámetro explícito, validado; sin parámetro, comportamiento actual | Hecho. `?tx=`, label desconocido → 400 |
| **D52** | Títulos y textos visibles con tilde en las cuatro salidas | Hecho. 80 cadenas |
| **D53** | Retirar `transaction_analyses_html` | Hecho. 62 líneas |

## 2. Los seis sub-pasos

| Sub-paso | Reporte | Commit |
|---|---|---|
| 6.1 Diagnóstico (read-only) | 46 | `f68d6a6` |
| 6.2 Capas y tooltip en pantalla | 47 | `904724e` |
| 6.3 Selector de exportación | 48 | `c3922ab` |
| 6.4 Capas en PDF y HTML | 49 | `07fcdda` |
| 6.5 Tildes y limpieza | 50 | `3ba8fee` |
| 6.6 Cierre | 51 (este), 52, 53 | — |

## 3. Archivos nuevos y archivos tocados

### Nuevos, ninguno protegido

| Archivo | Qué |
|---|---|
| `frontend/src/hooks/useChartLayers.ts` | el estado de capas, el id de gráfica y el serializador para el export |
| `frontend/src/components/dashboard/ExportScopeDialog.tsx` | el diálogo de alcance; pide su propia lista y decide solo |
| `backend/app/services/export/seleccion.py` | lee `?tx=` y `?capa=`, filtra y valida — una definición para las dos salidas |
| `backend/app/services/export/capas_html.py` | CSS, JS, selector y visibilidad inicial del HTML exportado |

### Protegidos: presupuesto contra realidad

El reporte 46 fijó una estimación por archivo y una parada en +50 %.

| Archivo | Presupuesto | Parada | Real | |
|---|---|---|---|---|
| `export_html.py` | 90 | 135 | **99** | 9 por encima de la estimación, 36 por debajo de la parada |
| `Dashboard.tsx` | 60 | 90 | **54** | |
| `export_pdf.py` | 55 | 83 | **43** | |
| `report_generator.py` | 60 | 90 | **33** añadidas, **75** retiradas | el saldo es negativo: sale más código del que entra |

**El umbral se cruzó una vez**, en 6.4: `export_html.py` llegó a +142 porque llevaba
dentro 25 líneas de JavaScript y 8 de CSS. En vez de pedir más presupuesto se sacaron a
`capas_html.py` —que además es donde tenían que estar, porque el informe integrado usa el
mismo— y el archivo bajó a +74. Queda escrito en el reporte 49.

## 4. Verificación

**89 comprobaciones propias de la etapa**, todas sobre datos reales, más la suite completa
de la Etapa 2 sobre dos ejecuciones.

| Prueba | Qué mira | Resultado |
|---|---|---|
| `capas_tooltip.py` | 22 — pantalla: selectores, trazos del SVG, tooltip, leyenda, por gráfica, sin persistencia | TODO PASA |
| `export_alcance.py` | 20 — PDF y HTML: sin parámetro, solo general, una, todas, orden, 400, longitud de URL | TODO PASA |
| `dialogo_export.py` | 13 — pantalla: abre, cancela sin exportar, qué viaja en la petición | TODO PASA |
| `capas_exportadas.py` | 21 — PDF: qué series recibe cada dibujo y comparación de PNG. HTML: visibilidad inicial | TODO PASA |
| `capas_html_render.py` | 13 — el HTML abierto en Chromium: capas, botones, hover y consola | TODO PASA |
| `cableado_c2.py` | 10 — la edición y el autoguardado siguen en su canal | TODO PASA |
| `verificar_etapa2.py` | 10 pasos, las cuatro salidas, sobre `E3` **y** `E5` | LAS CUATRO SALIDAS PASAN |
| `integrado_check.py` · `integrado_pdf_html.py` | el informe integrado, intacto | TODO PASA |
| `npx tsc --noEmit` | compilación del frontend | sin errores |

Las pruebas cuentan **los trazos reales del SVG** y los **bytes de los PNG**, no las clases
de un botón: recharts no pinta una `<Line hide>` y matplotlib produce un PNG distinto si
dibuja otra cosa, así que contar eso es contar lo que se ve.

### Tres comprobaciones mías que estaban mal escritas

Quedan anotadas porque son el tipo de error que hace pasar una prueba sin haber mirado
nada:

1. Buscar `INFORME DE CADA TRANSACCION` en el PDF: es un **comentario HTML** de la
   plantilla, invisible en el documento. Sustituida por el conteo de páginas con
   WeasyPrint (8 frente a 17).
2. Leer el hover de Plotly con `all_inner_texts()`: sobre nodos `<text>` de SVG devuelve
   cadena vacía, así que "el hover no menciona máximos" pasaba sin datos. Sustituida por
   `textContent` leído desde el navegador.
3. Indexar los PNG por `nombres[0]`: todos los bloques por transacción llaman a su serie
   `Promedio`, así que el diccionario se colapsaba a una entrada. Sustituida por posición.

Las tres eran errores de la prueba; ninguna del producto.

## 5. Lo que cambió de método y conviene conservar

- **El presupuesto por archivo protegido funciona.** Cruzarlo obligó a mirar *qué* estaba
  engordando el archivo, y la respuesta —JS y CSS incrustados— era un problema de diseño,
  no de presupuesto.
- **`perl -CSD` no sirve para acentuar archivos UTF-8** desde la línea de órdenes: trata
  los bytes del argumento como Latin-1 y los vuelve a codificar. Modo bytes, y
  `grep -c "Ã"` después de cada tanda.
- **Los scripts de prueba también tienen dependencias del producto.** `hf4_check.py`
  comparaba el título de la tabla sin tilde y había que actualizarlo en el mismo cambio.

## 6. Estado del plan de corrección

| Etapa | Qué | Estado |
|---|---|---|
| 1 | Diagnóstico y preparación | validada |
| 2 | Estructura del informe según v1.2 §1 | **validada por Fredy** |
| 3 | Estilo de los textos de IA (§4) | **validada por Fredy** |
| 5 | Panel de selección (§2) | **validada por Fredy** |
| 6 | Gráficas, exportación y cierre (§3, §6, §7) | implementada, pendiente validación |

No queda ninguna decisión del plan sin implementar.

---

**Estado: Etapa 6 implementada, pendiente validación de Fredy. Plan de corrección
completo.**

Acompañan a este reporte:
- `52_ETAPA6_para_fredy_cierre.md` — dos páginas y un guion para validar.
- `53_checklist_despliegue.md` — la deuda operativa acumulada de las seis etapas.
