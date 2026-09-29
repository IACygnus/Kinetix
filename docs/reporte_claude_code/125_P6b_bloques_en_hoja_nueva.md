Commit base `eb59c46` · 29 de septiembre de 2026

# P6b — los bloques de capturas empiezan en hoja nueva

**Solo la rama PDF.** Son seis líneas de CSS, con su comentario, en el `<style>` del PDF del integrado (`integrated_report.py`), junto a las de `.conclusions-block`. **`_build_att_html` no cambia** y el HTML exportado tampoco: lleva las mismas clases, pero este `<style>` no viaja con él (regla de la rama web, 29/09/2026). Cero IA y cero escrituras. El PDF se genera en proceso y acaba en `rollback`.

```css
.monitoreo-block, .evidencias-block {{ page-break-before: always; break-before: page; }}
.monitoreo-title, .evidencias-title {{ page-break-after: avoid; break-after: avoid; }}
```

Las clases `monitoreo-block` y `evidencias-block` ya las ponía `_build_att_html` en el envoltorio de cada bloque (B3/B4.2), pero **no tenían ninguna regla** en ningún sitio.

## Medido: integrado `42505814`, rasterizado con `p6_espacio_pdf.py`

| Pág. | Antes | Después |
|---|---|---|
| 6 | «Métricas de Monitoreo» + CPU (ya empezaba hoja, por casualidad) | Igual, ahora **garantizado** |
| 11 | LATENCIA - CLOUDWATCH | Igual |
| 12 | ERROR - CLOUDWATCH + **«Evidencias y Hallazgos» con su captura al pie** (el contenido llega a 187 de 195 mm) | ERROR - CLOUDWATCH y su análisis |
| 13 | Solo el análisis de la evidencia, separado de su captura | **«Evidencias y Hallazgos», su título, la captura y su análisis, juntos** |

- **Hojas: 20 antes, 20 después. El documento no gana ni pierde ninguna.** El bloque de evidencias pasa a la hoja 13, que antes ya existía solo para su análisis.
- **Ninguna captura partida:** cada una de las 8 aparece en una sola página y ningún contenido baja del margen inferior (máximo 186 mm de 195). El par título + imagen lleva `break-inside: avoid` desde P6, y el primer elemento de cada bloque pasa por el mismo camino que los demás.

**Sobre «la captura queda cortada».** En el PDF de antes, la imagen de la evidencia (1543 × 157 px) estaba **entera** en la página 12: una sola vez, 259 × 26,4 mm. Parecía cortada porque **el archivo subido ya viene recortado por abajo**: la captura de JMeter se tomó así. Comprobado abriendo el original de `/app/media/attachments/35ca5b92…/79c57cb9….png`. Al pie de la hoja la impresión era de corte; arriba de su propia hoja se lee como lo que es.

**Capturas** (`C:\proyectos\Kinetix_pruebas\p6\`): `p6b_antes_p11.png`, `p6b_antes_p12.png`, `p6b_antes_p13.png` frente a `p6b_despues_p11.png`, `p6b_despues_p12.png`, `p6b_despues_p13.png`.

**Nota de nombre.** En el PDF el bloque de monitoreo se sigue titulando «**Métricas de Monitoreo**». En la pantalla se llama «Capturas de infraestructura» desde O-D42. No lo he cambiado porque no se pidió; si se quiere igualar, es una cadena en `integrated_report.py`.

## Regresión

`cierre_r1.sh` (R1.1 a R1.4, C2 integrado, C2 individual), `r1_pdf_texto.py` ×2 y `p6_captura_alta.py`: **TODO PASA**.
