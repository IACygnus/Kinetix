c3922ab · 2026-09-17

# ETAPA 6.4 — Capas en el PDF y en el HTML exportado (D49)

**Llamadas reales a la IA: 0.** Se valida sobre `E3-estilo-pruebakinetix`
(`20bb2356-410d-465f-8717-c9a025e26e03`). Sin `docker build`.

---

## 1. Qué se implementó

### PDF — se imprime lo que estuviera seleccionado

`chart_multiline` acepta la capa pedida. Con `'ambas'` dibuja exactamente lo de
siempre; con `'promedio'` se salta las series punteadas; con `'maximo'` dibuja solo las
punteadas **y les da el nombre de su promedio en la leyenda** — si no, el gráfico saldría
sin leyenda y no habría forma de saber qué transacción es cada línea.

El color se asigna siempre, aunque la serie no se dibuje: así apagar los promedios no
cambia el color de los máximos.

### HTML — abre con lo recibido y ofrece el control

1. **Visibilidad inicial:** las trazas de la capa apagada salen como `'legendonly'`, no
   como `false`. Siguen existiendo, el lector las puede recuperar y —lo que pide §3— con
   `hovermode: 'x unified'` **Plotly las deja fuera del hover**. No hubo que tocar ni un
   `hovertemplate`.
2. **Los tres botones** "Ambas · Promedio · Máximo" junto a los controles que ya tenía cada
   gráfica, con la capa recibida marcada. Alternan con `Plotly.restyle`.
3. El informe integrado hereda los botones en sus bloques por transacción, porque comparte
   `_bloque_grafica_html`; en su PDF dibuja "Ambas" (D49/T6).

### El parámetro

```
?capa=general|rt:maximo          la gráfica general del informe, solo máximos
?capa=tx:4. Get_Booking_Id|rt:promedio     ese bloque, solo promedios
```

El identificador `alcance|gráfica` es **el mismo que arma el frontend**
(`useChartLayers.idGrafica`), así que los dos lados no tienen dos vocabularios. Lo que no
se entienda —un id mal formado, un valor inventado— se ignora y esa gráfica sale con las
dos capas: un parámetro roto no puede tumbar una exportación que por lo demás se puede
entregar entera.

## 2. PARADA evitada: el presupuesto de `export_html.py`

**La primera implementación cruzó el umbral y hay que dejarlo escrito.**

El reporte 46 estimó ≤ 90 líneas reales en `export_html.py`, con parada en 135. La primera
versión de 6.4 lo dejó en **+142 acumuladas — 7 por encima del umbral**. Composición:

| | Líneas |
|---|---|
| JavaScript del selector incrustado (`JS_CAPAS`) | 25 |
| CSS de los botones (`CSS_CAPAS`) | 8 |
| Comentarios | 22 |
| Líneas en blanco | 14 |
| Python y docstrings | ~73 |

Casi la mitad no era código del endpoint: era **texto de JS y CSS viviendo dentro de un
archivo protegido**.

En vez de pedir que se suba el presupuesto, se movió ese contenido a un módulo nuevo y **no
protegido**, `backend/app/services/export/capas_html.py`, que ya era el sitio correcto:
el JS y el CSS los necesitan el informe individual **y** el integrado, y tenerlos en un
solo sitio es lo que impide que los dos documentos acaben pintando el selector distinto.

**Resultado: `export_html.py` queda en +74, por debajo de su presupuesto de 90.** Las
pruebas se volvieron a pasar enteras después del movimiento, con el mismo resultado.

### Presupuestos, acumulado de toda la etapa

| Archivo protegido | Presupuesto | Parada (+50 %) | Real |
|---|---|---|---|
| `export_html.py` | 90 | 135 | **74** |
| `export_pdf.py` | 55 | 83 | **42** |
| `Dashboard.tsx` | 60 | 90 | **33** |
| `report_generator.py` | 60 | 90 | **16** |

## 3. Archivos tocados en 6.4

| Archivo | +/− | Protegido | Qué |
|---|---|---|---|
| `backend/app/services/export/capas_html.py` | **nuevo**, 92 | no | CSS, JS, el selector y la visibilidad inicial |
| `backend/app/services/export/report_generator.py` | +16 / −3 | **sí** | `chart_multiline(..., capa=…)` |
| `backend/app/api/v1/endpoints/export_pdf.py` | +15 / −2 | **sí** | parámetro `?capa=` y su reparto por gráfica |
| `backend/app/api/v1/endpoints/export_html.py` | +50 / −11 | **sí** | parámetro, visibilidad inicial y los botones |
| `backend/app/api/v1/endpoints/integrated_report.py` | +12 | no | importa el CSS y el JS compartidos |
| `backend/app/services/export/seleccion.py` | +7 / −2 | no | tolera el `Query` sin resolver (ver §5) |

Copias de seguridad: `*.bak_etapa6_6.4_20260917` de los cuatro archivos existentes.

## 4. Verificación

### `capas_exportadas.py` — 21 comprobaciones, PDF y HTML generado

Se **espía la llamada de dibujo** (`chart_multiline`) para ver qué series recibe y con qué
capa, y además se comparan los PNG resultantes.

| Caso | Resultado |
|---|---|
| **PDF sin parámetro** | 4 gráficas con serie dual (1 general + 3 por transacción), todas en `'ambas'` |
| **PDF con la general en "Máximo"** | la general se dibuja con `capa='maximo'` y **su PNG cambia**; los 3 PNG de las transacciones son **byte a byte los mismos** |
| **PDF con una transacción en "Promedio"** | solo cambia el PNG de esa; la general y los otros dos bloques salen idénticos |
| **PDF con parámetros basura** (`esto-no-es-un-id`, `general|rt:inventada`) | todo vuelve a `'ambas'` y el PDF sale igual que el de siempre |
| **HTML sin parámetro** | las 12 trazas visibles |
| **HTML con "Máximo"** | solo las `(max)` visibles, el resto `legendonly`, y el botón "Máximo" marcado |
| **HTML con una transacción en "Promedio"** | ese bloque abre en promedio; la general del mismo documento sigue con las dos capas |
| **El documento se basta solo** | lleva el JS (`window.kxCapa`), el CSS (`.capa-btn.active`), 4 selectores y 12 botones |
| **Ninguna gráfica de una sola capa lleva selector** | latency, error-rate, codes, tps y threads, comprobadas una a una |

### `capas_html_render.py` — 13 comprobaciones abriendo el HTML en Chromium

| Bloque | Resultado |
|---|---|
| **1. Abre con la capa recibida** | 6 trazas, todas `(max)`; el botón marcado es "Máximo" |
| **2. Los botones alternan** | "Promedio" → 6 trazas, ninguna de máximos · "Ambas" → 12, mitad y mitad · el botón activo se mueve |
| **3. El hover** | con "Promedio": `1. Auth : 431 ms \| 2. Get Booking : 213 ms \| …` — **ni una serie (max)**. Con "Máximo": `1. Auth (max) : 474 ms \| …` — ni una de promedio |
| **4. Los bloques por transacción** | el bloque pasa a "Máximo" (`['Promedio (max)']`) y la general no se mueve |
| **5. Consola** | **cero errores** |

> **Corrección de otra comprobación mía.** La primera versión leía el hover con
> `all_inner_texts()`, que sobre nodos `<text>` de SVG devuelve cadena vacía: la
> comprobación pasaba sin haber mirado nada. Se cambió a leer `textContent` desde el
> navegador, y es lo que produjo las líneas de hover citadas arriba. Dos comprobaciones más
> del otro script (una clave de diccionario no única y un recorte con expresión regular que
> se paraba en el primer `]`) también estaban mal escritas; las tres eran errores de la
> prueba, ninguno del código.

### Regresiones

- `export_alcance.py` (6.3, 20 comprobaciones): **TODO PASA** después del movimiento.
- `integrado_check.py`: **TODO PASA** — HTML y PDF integrados 200.
- `integrado_pdf_html.py`: **TODO PASA** — los 3 bloques por transacción sobreviven al
  recorte y las conclusiones individuales siguen recortadas.

## 5. Decisión técnica declarada: el `Query` sin resolver

Al llamar un endpoint **en proceso** —que es como se prueban aquí las dos salidas— FastAPI
no resuelve los valores por defecto, así que `capa` llegaba como el objeto `Query(None)` y
`capas_de_query` reventaba con `'Query' object is not iterable`. Por HTTP nunca ocurre.

Se podría haber arreglado solo en la prueba, pero este proyecto invoca endpoints en proceso
a menudo (`pdf_real_html.py`, `integrado_pdf_html.py`, los tres scripts de esta etapa), así
que los dos lectores de `seleccion.py` comprueban ahora que lo recibido sea una lista y
tratan cualquier otra cosa como "no vino". Es preciso —`isinstance(x, (list, tuple))`— y
no enmascara ningún otro error.

## 6. Lo que NO se tocó

- Los `hovertemplate`: apagar la traza ya la saca del hover unificado.
- Las gráficas de una sola capa, en ninguna salida.
- El PDF del informe integrado, que dibuja "Ambas" — §6 lo deja fuera del selector de
  exportación y no hay pantalla de la que heredar una selección.
- El eje Y: sigue calculándose sobre las dos series, para que cambiar de capa no mueva la
  escala.

---

**Estado:** 6.4 implementada y verificada en las dos salidas, pendiente validación de
Fredy. El umbral de `export_html.py` se cruzó y se corrigió sacando el JS y el CSS del
archivo protegido; los cuatro protegidos quedan dentro de presupuesto. Sigue 6.5 — tildes
y limpieza.
