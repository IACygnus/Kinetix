Commit base `41cf237` · 28 de septiembre de 2026

# Punto 6 del diagnóstico 120 — el espacio de las capturas en el PDF del integrado

**Cero llamadas a la IA. Cero escrituras en la base de Fredy.** El PDF se genera en proceso (`export_integrated_pdf` no hace commit y la sesión acaba en `rollback`), se rasteriza y se mide. R2 sigue en pausa, esperando la key; sus archivos no se tocan aquí.

| Qué | Dónde |
|---|---|
| El cambio | `backend/app/api/v1/endpoints/integrated_report.py`, **solo la rama `for_pdf`** de `_build_att_html` y el `<style>` del PDF del integrado. No es protegido. **+55 −9** |
| La medida, versionada | `backend/pruebas_e2e/p6_espacio_pdf.py <etiqueta> [report_id]` |
| Los PDF y las páginas rasterizadas | `C:\proyectos\Kinetix_pruebas\p6\` (`antes_p*.png`, `despues_a_p*.png`, `despues_b_p9.png`) |
| Integrado medido | `42505814…`, el mismo del diagnóstico 120 |

Sin frontend: la regla 31 no aplica.

> **Este reporte tiene dos vueltas.** Los §1 a §7 son la primera: tope de 90 mm y ancho completo solo para las capturas anchas. **El estado final está en §8**: todas las capturas al ancho del documento, por decisión de Fredy.

---

## 1. Antes y después, página a página

Una **captura** es una imagen del PDF cuyo tamaño en píxeles coincide con el de un adjunto del integrado; las gráficas del cuerpo no cuentan. «Blanco» son los milímetros entre el final del contenido y el margen inferior de 15 mm.

| Pág. antes | Captura | Antes: impresa a | ppp | Blanco | → | Pág. después | Después: impresa a | ppp | Blanco |
|---|---|---|---|---|---|---|---|---|---|
| 6 | CPU (1290×555) | 139,5 × 60,0 mm | 235 | 64 | | 6 | **209,2 × 90,0 mm** | **157** | 34 |
| 7 | MEMORIA (1653×557) | 178,1 × 60,0 | 236 | 72 | | 7 | **259,0 × 87,3** | **162** | 45 |
| 8 | CPU QUOTA (1755×368) | 259,0 × 54,3 | 172 | 78 | | 8 | 259,0 × 54,3 | 172 | 78 |
| 9 | LOG ANALYTICS (1892×460) | 246,8 × 60,0 | 195 | 72 | | 9 | **259,0 × 63,0** | 186 | 69 |
| 10 | LLAMADAS API (1904×533) | 214,3 × 60,0 | 226 | 72 | | 10 | **259,0 × 72,5** | 187 | 60 |
| 11 | LATENCIA (1905×561) | 203,7 × 60,0 | 237 | 72 | | 11 | **259,0 × 76,3** | 187 | 56 |
| 12 | ERROR CLOUDWATCH (1900×539) | 211,5 × 60,0 | 228 | 77 | | 12 | **259,0 × 73,5** | 186 | **8** |
| 13 | evidencia «Internal server error» (1543×157) | 259,0 × 26,4 | 151 | 98 | | 12 | 259,0 × 26,4 | 151 | (misma hoja) |
| 19 | — (título de conclusiones solo) | — | — | **169** | | — | *desaparece* | — | — |

| Resumen | Antes | Después |
|---|---|---|
| Páginas del PDF | 21 | **20** |
| Páginas con capturas | 8 | 7 |
| **Capturas por página** | **1,00** | **1,14** |
| **Blanco medio en esas páginas** | **75,7 mm** | **50,0 mm** |
| Tamaño del PDF | 2.855.497 B | 2.855.123 B |

**Menos ppp es mejor aquí.** La imagen es la misma; cuantos menos puntos por pulgada, más grande se imprime y más grande sale la letra de dentro. La captura de CPU pasa de 235 a 157 ppp: **la letra es un 50 % más grande**. Todas las anchas van ya a 259 mm, el ancho útil entero.

### Las capturas para comparar (misma página, antes y después)

- **Página 6 (CPU - DYNATRACE):** `antes_p6.png` ↔ `despues_a_p6.png`. Es la que más cambia: la captura pasa de 139 a 209 mm de ancho y los números del panel se leen sin ampliar.
- **Página 12:** `antes_p12.png` ↔ `despues_a_p12.png`. Es la hoja que ahora lleva **dos capturas**: el 5XX de CloudWatch y la evidencia del 500. El análisis de la segunda sigue en la hoja 13.
- **Conclusiones:** `antes_p19.png` (el título solo en la hoja, 169 mm en blanco) ↔ `despues_a_p19.png` (el título pegado a su caja).

---

## 2. Qué se cambió

Todo en `_build_att_html`, rama `for_pdf`. La rama web se queda como estaba: solo gana un `<div>` sin estilo alrededor del título y la imagen.

| # | Antes | Después |
|---|---|---|
| 1 | `page-break-inside:avoid` en la **tarjeta entera** (título + imagen + análisis) | Solo en la **pareja título + imagen** (`pair_style`). La tarjeta se puede partir |
| 2 | `avoid` también en la **caja del análisis** | Fuera. El texto lleva `orphans:3; widows:3` para que no quede una línea suelta, y el rótulo «Análisis» lleva `break-after:avoid` para no quedarse solo al pie |
| 3 | `max-height:60mm` en toda imagen | **`max-height:90mm`** |
| 4 | — | Si la proporción es **mayor de 2,5:1**, `width:100%` y alto automático. La proporción se lee de la cabecera del archivo con PIL; si no se puede leer, se queda el estilo general |
| 5 | `.conclusions-block` sin CSS; el comentario prometía un salto de página | `.conclusions-block { break-before: page }`, su `.ai-box` con `break-inside: auto` y el título con `break-after: avoid` |

### Lo de `.conclusions-block`

El comentario de la línea 1829 decía «forced new page via .conclusions-block, boxes don't split». **Ninguna regla hacía ninguna de las dos cosas**: esa clase no tenía CSS en ningún sitio.

Lo que pasaba de verdad es que la caja heredaba `break-inside: avoid` de `.ai-box`, desde el estilo extraído del protegido. Como la caja mide **más de una hoja**, WeasyPrint la empujaba entera a la página siguiente, dejaba el título solo en una hoja con **169 mm en blanco** y después la partía igualmente, porque no cabe en ninguna.

Ahora el bloque empieza página con su título y la caja se parte donde toque. El comentario se corrigió para decir lo que hace.

---

## 3. La alternativa de dos columnas: medida y descartada

Para las capturas estrechas probé el trato de N2.1: imagen al 62 % y análisis al 38 %, en tabla, porque WeasyPrint no maqueta bien con flex. Fue un cambio **temporal**: se midió con `P6_VARIANTE=B` y se retiró. El código final no lo lleva, comprobado con `grep`.

| | Variante A (la que queda) | Variante B (dos columnas) |
|---|---|---|
| Capturas por página | **1,14** | 1,00 |
| Blanco medio | **50,0 mm** | 87,5 mm |
| Ancho de las anchas | **259 mm** | 160,6 mm |
| ppp de la captura de 1904 px | **187** | 301 (letra un 38 % más pequeña) |

**B empeora las tres cosas.** Con la columna de texto al 38 %, el análisis de la página 9 ocupa 14 líneas y la tarjeta mide unos 95 mm. Siguen sin caber dos en 180 mm, y encima las capturas anchas se encogen. Captura en `despues_b_p9.png`.

---

## 4. Por qué no son dos capturas por página en todas

**Lo digo claro: el objetivo de «dos por hoja» no se cumple en este integrado.** Se pasa de 1,00 a 1,14. Lo que sí se cumple es que la letra sale más grande y que el blanco baja un tercio.

El motivo es aritmético. La hoja útil mide 180 mm de alto (210 menos 2 × 15). Con la letra más grande, una tarjeta de este integrado mide:

| Pieza | mm |
|---|---|
| Título | ~8 |
| Imagen a todo el ancho | 26-90 (la mayoría 63-87) |
| Caja del análisis (5-6 líneas a 267 mm) | ~30-35 |
| Márgenes | ~8 |
| **Tarjeta** | **~95-135** |

Dos tarjetas son 190-270 mm, y no caben en 180. **«Dos por hoja» y «letra más grande» chocan con capturas anchas y análisis de este largo.** Donde una tarjeta es corta, como la evidencia de 26 mm de la página 12, sí entran dos.

Si quisieras dos por hoja de todos modos, las palancas que quedan son estas. **No he tocado ninguna:**
1. **Bajar el tope a ~55 mm para las anchas.** Vuelve la letra de antes; es deshacer la mitad de esta etapa.
2. **Análisis más cortos** (~60 palabras). La caja baja a ~20 mm. Es un cambio de prompt en `analyze_image`.
3. **Aceptar el resultado.** Una captura grande por hoja con su texto, sin huecos de 70-100 mm.

Mi recomendación es la **3**. El problema del reporte 120 §5 era que la letra de dentro no se leía, y eso ya se arregla.

---

## 5. Regresión

| Suite | Resultado |
|---|---|
| `r2_series.py` (R2 sigue igual) | **TODO PASA** |
| `cierre_r1.sh` → R1.1 guardado | Falla **de forma intermitente** con `Server disconnected without sending a response` en `export-pdf`. **Es anterior a P6**: ver §8.4 |
| R1.2 selector · R1.3 historial · R1.4 punta a punta | **TODO PASA** |
| C2 integrado · C2 individual | **CABLEADO CORRECTO** |
| `r1_pdf_texto.py` sobre `r1_integrado.pdf` y `r1_seleccion.pdf` | **TODO PASA** los dos (ver abajo) |

**`r1_pdf_texto.py` necesitaba PyMuPDF, que ya no está en ningún Python de esta máquina.** No he instalado nada en el equipo. Le añadí un respaldo con `pypdfium2`, que sí está en el contenedor, así que la comprobación corre ahora ahí.

Ese respaldo dio al principio **un falso fallo**, `ZZR1CIERRESLRH-img`. pdfium devuelve el guion de un corte de línea como `U+FFFE`, y en el PDF ponía `ZZR1CIERRESLRH\ufffeimg`. Se normaliza a `-`, que es lo que ya hacía PyMuPDF. **No era una regresión**: la marca estaba en la página 14.

El backend de pruebas (8002) se levantó con `preparar_base_de_pruebas.sh`, sin claves de IA. Su paso 4, el juego de datos `ZZTEST-`, lanzó un `JSONDecodeError` al primer intento, pero **las suites crean sus propios datos** (`r1_datos.py`) y no lo necesitaban.

---

## 6. Huella en la base de Fredy

Se comparó contra el `pg_dump` de esta mañana (`backup_20260928_1621_preR2.sql`):

| Tabla | Respaldo | Ahora |
|---|---|---|
| `integrated_reports` | 31 | 31 (último cambio: 25/09) |
| `transaction_chart_analyses` | 294 | 294 |
| `execution_attachments` | 39 | 39 |
| `test_executions` | 71 | **72** |
| `ai_config` | 1 | 1 (`updated_at` 28/09 21:45:07) |

**La ejecución nueva no es mía, y se comprobó antes de escribirlo (regla 33):**
- Es `afc2af7d…`, «asasascasc», cliente «prueba avianca», con el JTL de Nova.
- La creó un `POST /upload` a las **21:45:04 UTC** desde **`172.18.0.1`**, que es el navegador y no los scripts (`127.0.0.1`).
- Lo precede un login de `admin` a las 21:43:45.
- El `updated_at` de `ai_config` es la sincronización del contador de uso de ese mismo upload.

**No se toca.**

**Un dato de ese upload para lo de la key** (lo añado a lo que te informé): OpenAI respondió `'Your API key has been invalidated.'`, **`code: token_invalidated`**. Es un tercer código:

| Hora (UTC) | Endpoint | Código |
|---|---|---|
| 21:22 | chat, mi corrida | `expired_secret_key` («has expired») |
| 21:44 | `GET /v1/models`, el diagnóstico | `invalid_api_key` |
| 21:45 | chat, tu upload | **`token_invalidated`** («has been invalidated») |

«Invalidated» apunta más a una key **revocada o rotada** que a una caducidad por fecha. Sigue siendo hipótesis; el panel de OpenAI lo dirá.

Ese upload corrió, además, con el código de R2, que está en el árbol sin commit y el backend de desarrollo recarga en caliente. Salió entero con texto de respaldo, por la key.

---

## 7. Qué queda

- ~~Validación visual de Fredy~~ **Validado por Fredy el 28/09** (estado final de §8). Abrir las parejas de capturas de §1, o generar el PDF del integrado desde la pantalla.
- **Decidir §4:** dejarlo como está (recomendado) o tirar de una de las dos palancas.
- **Sin commit.** Los archivos de este punto (`integrated_report.py`, `p6_espacio_pdf.py`, `r1_pdf_texto.py` y este reporte) no se cruzan con los de R2, así que pueden ir en su propio commit cuando lo digas.

---

## 8. Segunda vuelta: todas las capturas al ancho del documento

Fredy lo aclaró: **una captura por hoja está bien.** Lo que hace legible la letra es el **ancho**, y la primera vuelta todavía dejaba la de CPU en 209 de 259 mm.

### 8.1 El cambio

| Antes (primera vuelta) | Ahora |
|---|---|
| `max-height:90mm`, y `width:100%` solo si la proporción pasaba de 2,5:1 | **Toda captura a `width:100%`, alto automático, sin tope** |
| — | **Una sola excepción:** si a todo el ancho mediría más de **155 mm**, se limita a 155 mm de alto y pierde ancho. Deja una línea en el log |

Los dos números son constantes con nombre al lado de `_build_att_html`:
- `_ANCHO_UTIL_MM = 259`: 267 mm útiles menos el relleno de la tarjeta.
- `_ALTO_MAX_CAPTURA_MM = 155`: 180 mm útiles menos ~25 de título y márgenes.

### 8.2 Las capturas, con su ancho impreso

Rasterizado de `42505814…` (`despues_c`). Las siete de monitoreo, más la evidencia:

| Pág. | Captura | Píxeles | Antes (HEAD) | **Ahora** | ppp antes → ahora |
|---|---|---|---|---|---|
| 6 | CPU - DYNATRACE | 1290 × 555 | 139,5 × 60,0 mm | **259,0 × 111,4 mm** | 235 → **127** |
| 7 | MEMORIA - DYNATRACE | 1653 × 557 | 178,1 × 60,0 | **259,0 × 87,3** | 236 → 162 |
| 8 | CPU QUOTA - DYNATRACE | 1755 × 368 | 259,0 × 54,3 | **259,0 × 54,3** | 172 → 172 |
| 9 | LOG ANALYTICS - DYNATRACE | 1892 × 460 | 246,8 × 60,0 | **259,0 × 63,0** | 195 → 186 |
| 10 | LLAMADAS API - CLOUDWATCH | 1904 × 533 | 214,3 × 60,0 | **259,0 × 72,5** | 226 → 187 |
| 11 | LATENCIA - CLOUDWATCH | 1905 × 561 | 203,7 × 60,0 | **259,0 × 76,3** | 237 → 187 |
| 12 | ERROR - CLOUDWATCH | 1900 × 539 | 211,5 × 60,0 | **259,0 × 73,5** | 228 → 186 |
| 12 | *(evidencia)* Internal server error | 1543 × 157 | 259,0 × 26,4 | **259,0 × 26,4** | 151 → 151 |

**Ninguna por debajo de 259 mm.** La de CPU es la que más cambia: su letra se imprime **1,85 veces más grande** que en HEAD (235 → 127 ppp).

**La pareja de la página 6:** `C:\proyectos\Kinetix_pruebas\p6\antes_p6.png` ↔ `despues_c_p6.png`. La captura ocupa ahora el ancho entero de la hoja y el análisis cabe debajo, en la misma página (el contenido llega a 182 mm).

Resto del documento: 20 páginas, las mismas que en la primera vuelta. El blanco medio de las páginas de capturas baja a 46,9 mm.

### 8.3 La captura muy alta: el único caso donde el ancho completo no sirve

Una imagen no se puede partir entre dos hojas. Si a 259 mm de ancho mide más que la hoja, o se reduce o se sale de la página.

**En la base de Fredy no hay ninguna.** Medí los 42 archivos de `/app/media` a 259 mm de ancho:

| La más alta a todo el ancho | Mide |
|---|---|
| 1600 × 715 (JPG, dos copias) | 115,7 mm |
| 1290 × 555 (la de CPU) | 111,4 mm |
| 607 × 241 (tres copias) | 102,8 mm |
| un PNG de **1 × 1 px** | (no es una captura) |

**Lo que hace el código si llega una**, comprobado con imágenes sintéticas (`backend/pruebas_e2e/p6_captura_alta.py`, **TODO PASA**; sin base y sin IA):

| Caso | Resultado |
|---|---|
| Ancha, 1290 × 555 | 259,0 × 111,4 mm |
| En el límite, 1000 × 598 | **259,0 × 154,9 mm, en una hoja con su título** |
| Vertical, 800 × 1200 (388 mm a todo el ancho) | **103,3 × 155,0 mm**, en una hoja con su título, y avisada en el log |

**Mi propuesta para ese caso**, si llega a darse:
- dejarlo como está: la hoja entera para ella, con el ancho que permita el alto;
- y decírselo al analista **al subirla**: «esta captura es vertical; en el PDF saldrá a X mm de ancho».

Lo mejor es recortarla o capturarla en horizontal. Avisar sería un cambio de pantalla (`AttachmentSection.tsx`), así que **no lo he hecho**: es frontend y lo decides tú.

**Decisión de Fredy (28/09):** el aviso **no se hace ahora**. Es frontend y no hay ninguna captura que lo necesite; queda anotado por si aparece una.

**Un efecto que conviene saber.** Las capturas de 607 px de ancho (tres en la base) se estirarán hasta 259 mm, a **60 ppp**. Se verán más grandes pero blandas: la imagen no tiene más detalle que ese. Lo que las arregla es capturarlas con más resolución (reporte 120 §5), no el PDF.

### 8.4 La regresión, y una corrección a §5

En la primera vuelta escribí que el fallo de R1.1 fue «con el backend de pruebas recién levantado». **Era una suposición, y la comprobación la desmiente.**

| Qué se probó | Resultado |
|---|---|
| Secuencia de `cierre_r1.sh` (datos → sesión → R1.1) con **el `integrated_report.py` de HEAD** | **1 de 2** pasadas correctas |
| La misma secuencia con **el código de P6** | **1 de 2** pasadas correctas |
| `export-html` + `export-pdf` llamados directamente, 3 veces | **3 de 3** correctas (PDF en 7,3-7,6 s) |
| Lo mismo **justo después de forzar una recarga** del backend de pruebas | **3 de 3** correctas |

- **El fallo es anterior a P6**: sale igual con el código de HEAD.
- **No es la recarga**: justo después de una, las llamadas directas salen bien.
- El backend no se cae: mismo proceso, sin traza en su log. La petición del PDF entra, empieza a generarse (se ve el subsetting de fuentes) y la conexión se corta sin respuesta.
- **Causa no encontrada.** Solo pasa dentro de la secuencia de R1.1, con la parte de navegador delante. Queda como deuda de la suite de R1, no de este punto.

El resto de la regresión, sobre el código final: R1.2, R1.3, R1.4, C2 integrado y C2 individual, **TODO PASA / CABLEADO CORRECTO**. `r1_pdf_texto.py` sobre los dos PDF, **TODO PASA**. `p6_captura_alta.py`, **TODO PASA**.

### 8.5 Diff final de `integrated_report.py`

Solo la rama `for_pdf` de `_build_att_html`, las dos constantes y el `<style>` del PDF del integrado (`.conclusions-block`). La rama web no cambia de aspecto.
