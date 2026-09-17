904724e · 2026-09-17

# ETAPA 6.3 — Selector de exportación (D50, D51)

**Llamadas reales a la IA: 0.** Se valida sobre `E3-estilo-pruebakinetix`
(`20bb2356-410d-465f-8717-c9a025e26e03`), 3 transacciones con análisis. Exportar solo lee
lo que ya está guardado. Sin `docker build`.

---

## 1. Qué se implementó

### D50 — el diálogo

Pulsar **Exportar PDF** o **Exportar HTML** ya no exporta: abre un diálogo que pregunta
qué incluir (v1.2 §6).

- **"Solo informe general"** — portada, tabla resumen, gráficas generales y conclusiones.
- **"General y transacciones"** — con la lista de las transacciones que tienen análisis,
  **todas marcadas por defecto**. Es la opción preseleccionada, de modo que confirmar sin
  tocar nada da el documento de siempre.
- **Cancelar no exporta.**

La lista sale de `GET /executions/{id}/transaction-analyses`, campo `report_labels`: el
mismo origen que usa la pantalla para decidir qué bloques pinta, así que el diálogo no
puede ofrecer una transacción que el PDF no sepa dibujar. Si la ejecución no tiene
ninguna, no hay nada que preguntar y se exporta directamente.

Solo aplica a los exports **individuales**. El informe integrado no pasa por estos
endpoints (`integrated_report.py` construye los bloques por su cuenta) y queda exactamente
como estaba, como pide §6.

### D51 — el parámetro, y qué pasa si no viene

```
GET /executions/{id}/export/pdf              todas las transacciones   (lo de siempre)
GET /executions/{id}/export/pdf?tx=          solo el informe general
GET /executions/{id}/export/pdf?tx=Auth      el general y esa
GET …?tx=Auth&tx=Login                       el general y esas dos
GET …?tx=NoExiste                            400
```

La diferencia entre "el parámetro no vino" (`None`) y "vino vacío" (`[]`) es lo que
distingue *todas* de *solo el general*, sin inventar un segundo parámetro booleano que
pudiera contradecir a la lista. **Cualquier cliente que no mande nada recibe el documento
de hoy**, byte a byte.

Un label que no existe en la ejecución es un **400**, no un silencio: entregar un PDF sin
el bloque que se pidió, y sin decirlo, es peor que fallar — quien lo abre no tiene forma
de notar lo que falta.

## 2. Archivos tocados

| Archivo | +/− | Protegido | Qué |
|---|---|---|---|
| `backend/app/services/export/seleccion.py` | **nuevo**, 103 | no | lee `?tx=` y `?capa=`, filtra y valida. Una sola definición para las dos salidas |
| `frontend/src/components/dashboard/ExportScopeDialog.tsx` | **nuevo**, 196 | no | el diálogo: pide su lista, decide solo, devuelve la selección |
| `frontend/src/services/api.ts` | +33 / −4 | no | `ExportOpciones` y el armado de la query |
| `backend/app/api/v1/endpoints/export_pdf.py` | **+27 / −5** | **sí** | parámetro, filtro y validación |
| `backend/app/api/v1/endpoints/export_html.py` | **+24 / −5** | **sí** | lo mismo, con el mismo helper |
| `frontend/src/components/dashboard/Dashboard.tsx` | **+26 / −7** acumulado con 6.2 | **sí** | un estado, dos `onClick` y el montaje del diálogo |

**Presupuestos del reporte 46 frente a lo real (acumulado 6.2 + 6.3):**

| Archivo | Presupuesto | Parada (+50 %) | Real |
|---|---|---|---|
| `Dashboard.tsx` | 60 | 90 | **26** |
| `export_pdf.py` | 55 | 83 | **27** |
| `export_html.py` | 90 | 135 | **24** |
| `report_generator.py` | 60 | 90 | 0 (sin tocar todavía) |

Condición C3 cumplida: todo son cambios reales. C1 no aplica — no se movió código.

Copias de seguridad: `export_pdf.py.bak_etapa6_6.3_20260917`,
`export_html.py.bak_etapa6_6.3_20260917`, `api.ts.bak_etapa6_6.3_20260917`.

## 3. Por qué el helper aparte

`filtrar_transacciones` y `seleccion_de_query` viven en
`backend/app/services/export/seleccion.py`, no dentro de los dos endpoints. Dos razones:

1. Los dos archivos están protegidos y así el cambio en ellos se queda en 4 líneas de
   lógica cada uno.
2. **Las dos salidas no pueden divergir** en qué significa `?tx=`. Si el filtro estuviera
   escrito dos veces, el PDF y el HTML podrían empezar a responder distinto al mismo
   parámetro, que es exactamente el tipo de deriva que la Etapa 2 vino a corregir.

El módulo ya trae también el lector de `?capa=` (`capas_de_query`, `capa_de`,
`id_grafica`), que usará 6.4. Se escribió ahora porque es el mismo archivo nuevo y porque
`Dashboard` ya manda el parámetro: el backend lo ignora hasta 6.4, sin efecto.

## 4. Verificación

### Backend — `export_alcance.py`, 20 comprobaciones sobre el informe real

Ejecuta los dos endpoints **en proceso**, espiando el HTML que se le entrega a WeasyPrint
y leyendo el cuerpo del `HTMLResponse`.

| Caso | PDF | HTML |
|---|---|---|
| **Sin parámetro** | 3 bloques, los 3 esperados | 3 bloques |
| **`?tx=` vacío** | 0 bloques · **8 páginas frente a 17** del completo | 0 bloques |
| …y conserva el resto | conclusiones y gráficas generales intactas | ídem |
| **`?tx=5. Put_Update_Booking`** | solo ese bloque | solo ese bloque |
| **Todas marcadas** | 3 bloques y **el mismo peso** que sin parámetro | 3 bloques |
| **Pedidas al revés** | salen en el orden de la tabla resumen | — |
| **Label inexistente** | 400 · *"Transaccion sin analisis en esta ejecucion: …"* | 400 |
| **Una válida + una inválida** | 400 (no se exporta a medias) | — |
| **Longitud de la URL con todas** | 136 caracteres | — |

Las 8 páginas frente a 17 son la comprobación de verdad: se renderiza el PDF con
WeasyPrint y se cuentan las páginas del documento, no cadenas del HTML intermedio.

> **Corrección de una comprobación mía.** La primera versión de la prueba buscaba que la
> cadena `INFORME DE CADA TRANSACCION` desapareciera del PDF solo-general y marcaba FALLA.
> Esa cadena es un **comentario HTML de la plantilla** (`report_generator.py:1131`),
> invisible en el documento: la comprobación estaba mal, no el código. Se sustituyó por el
> conteo de páginas, que sí mide el documento entregado.

### Riesgo 1 del reporte 46, resuelto

La URL con las 3 transacciones mide **136 caracteres**. El límite práctico de 2.000 queda
lejísimos: harían falta decenas de transacciones con nombres largos para acercarse. **Se
mantiene `GET`**; no hace falta cambiar a `POST`.

### Pantalla — `dialogo_export.py`, 13 comprobaciones con Playwright

| Bloque | Resultado |
|---|---|
| **1. El botón abre el diálogo** — 3 transacciones listadas, las 3 marcadas, "General y transacciones" preseleccionado, **ninguna exportación disparada** | PASA (4) |
| **2. Cancelar** — el diálogo se cierra y no se dispara ninguna exportación | PASA (2) |
| **3. "Solo informe general"** — la lista se deshabilita, viaja `?tx=` vacío, **respuesta 200** | PASA (4) |
| **4. Desmarcar una** — se desmarca `4. Get_Booking_Id` y viajan exactamente `['5. Put_Update_Booking', '6. Delete_Booking_Id']` | PASA (3) |
| **5. El integrado** — ninguna petición del integrado lleva `tx` | PASA |

### Regresiones

- `integrado_check.py`: **TODO PASA** — HTML 200 (1,5 MB, 1,4 s) y PDF 200 (1,5 MB, 4,2 s),
  sin Throughput, sin palabra prohibida, sin conclusiones por transacción.
- `npx tsc --noEmit`: sin errores.

## 5. Lo que NO se tocó

- El informe integrado: ni su endpoint, ni su diálogo (no tiene), ni sus bloques.
- El orden de las transacciones: lo fija la tabla resumen y la selección no lo altera —
  pedirlas al revés las devuelve en el orden del resumen.
- El `Content-Disposition` y el nombre del archivo descargado.
- El verbo: sigue siendo `GET` con `responseType: 'blob'`.

---

**Estado:** 6.3 implementada y verificada en las dos salidas y en pantalla, pendiente
validación de Fredy. Ninguna condición de parada activada. Sigue 6.4 — capas en PDF y HTML.
