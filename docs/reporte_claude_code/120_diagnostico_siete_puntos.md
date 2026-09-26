Commit `a9e9294` · 26 de septiembre de 2026

# Diagnóstico — los siete puntos del veredicto de Fredy

**Solo lectura.** No se tocó código, ni la base, ni la configuración de los contenedores. **Cero llamadas a la IA.**

Lo que sí se ejecutó, y por qué no escribe:

| Qué | Cómo se garantizó que no escribe |
|---|---|
| `SELECT` sobre `integrated_reports`, `execution_attachments`, `transaction_chart_analyses`, `test_executions` | Solo `SELECT` |
| Los dos PDF (individual e integrado) generados **en proceso**, llamando a las funciones de los endpoints con una sesión propia | `export_pdf` y `export_integrated_pdf` no hacen `commit`; la sesión termina con `rollback` |
| Reproducción del punto 1 con Chromium (Playwright del contenedor) contra la pantalla real | **Toda petición que no fuera GET se interceptó**: se registró su cuerpo y se respondió un 200 falso. Ningún PATCH llegó al backend. El token se generó en proceso, así que **no se gastó cupo de `/auth/login`** |
| Lectura del log de `jmeter_backend` | `docker logs` |

Los scripts, el PDF del integrado y las capturas están en **`C:\proyectos\Kinetix_pruebas\diag120\`** (fuera del repositorio, porque este diagnóstico no cambia nada del repo). Copias de borrador en el `/tmp` del contenedor: `diag120_*`.

> **Nota de inventario.** Dos protegidos ya no tienen las líneas que dice CLAUDE.md §11: `Dashboard.tsx` tiene **1053** (no 1045) y `export_pdf.py` tiene **573** (no 547). No es de este diagnóstico: solo se anota.

---

## 1. El integrado no guarda las ediciones — LO MÁS URGENTE

### Qué pasa

La edición **sí se manda cuando la página tiene tiempo de mandarla**, y **se pierde cuando no lo tiene**. Es el caso (1) de los cuatro: *la petición no se manda*. El mecanismo de la Etapa 7 (`sections[].overrides.analysis` + `_aplicar_overrides_tx`) **sigue vivo y nadie lo pisó**. Lo que falla es **cuándo** se dispara el guardado.

Reproducido en navegador contra el integrado de Fredy del 25/09 12:35 (`42505814…`), editando el análisis del resumen de la prueba de carga:

| Qué hizo el usuario tras escribir | PATCH que salió | ¿Llevaba la edición? |
|---|---|---|
| Clic fuera y **esperar 6 s** | 1, a los 2,1 s, con `sections` y `overrides.analysis = [ai_analysis_summary]` | **Sí** |
| Clic en **«Guardar cambios»** y salir | 1, con `sections` | **Sí** |
| Clic en **otro enlace del menú** (navegación dentro de la app) | **Ninguno** | **Se pierde** |
| **F5** o cerrar la pestaña | 1, **solo con `consolidated_analysis`** | **Se pierde** |

### Por qué

`frontend/src/pages/IntegratedReportPage.tsx`:

1. **Salir cancela el guardado en vez de hacerlo.** La edición se guarda en una referencia y se programa un PATCH a **1,8 s** (`SAVE_DEBOUNCE_MS`, línea 33; `scheduleSave`, 196-203). Al desmontar la página, la limpieza solo hace `clearTimeout` (241-244). Si se sale por el menú dentro de esos 1,8 s, **nada se manda**. Y el gesto natural —escribir y hacer clic en el menú— cae siempre dentro de la ventana, porque **ese mismo clic es el que confirma la edición** (el `onBlur` de `EditableTextArea`, `Dashboard.tsx:69-71`).
2. **F5 o cerrar manda solo el consolidado.** El `beforeunload` (232-238) envía `{ consolidated_analysis }` y **nunca `sections`**, que es donde viven las ediciones de sección.
3. **La pantalla dice «Guardado» cuando no lo está.** `scheduleSave` no marca la página como pendiente, así que la barra sigue mostrando el «Guardado HH:MM» del último guardado del consolidado (683-687). En las cajas por transacción, `TextoEditable` pone «Guardado» en cuanto la edición entra en memoria (`TransactionReportSection.tsx:239, 260`). **El usuario ve «Guardado» y se va.**

Dos defectos más, **leídos en el código y no reproducidos**:

4. **Regenerar el consolidado puede pisar ediciones de sección.** `generate_consolidated_analysis` lee el informe al empezar (`_load_section_overrides`, `integrated_report.py:1924`) y al terminar lo vuelve a pedir con `db.get` (2130), que devuelve **el mismo objeto de la sesión**, sin releer (`expire_on_commit=False`). Escribe entonces las `sections` de **antes** de la llamada a la IA (2133-2137): lo que se guardó mientras la IA generaba, se pierde.
5. **Carrera con la marca de «pendiente».** `persistEdit` pone `dirtyRef = false` **después** del `await` (168): una edición hecha mientras un PATCH está en vuelo queda marcada como guardada y no se manda.

### Lo que dice la base

- Los **tres** integrados del 25/09 (12:11, 12:35 y 13:14) **no tienen `overrides` en ninguna sección**, aunque el log registra **19 y 12 PATCH con 200** en las sesiones de 12:35 y 13:14. Sí guardaron el consolidado (`edited: true`).
- El de agosto (`fa724249…`) **sí tiene overrides**: el mecanismo funciona cuando el guardado llega a salir.
- **No hay ninguna clave `tx|`** en ningún integrado guardado.

> **Una duda que declaro (regla 33).** Como cada PATCH arma `sections` a partir de **todas** las ediciones acumuladas en la sesión, que los 19 PATCH salieran sin overrides significa que, en el momento de cada uno, **no había ninguna edición de sección en memoria**. Esto encaja si Fredy editó las secciones **después** del último guardado del consolidado y salió por el menú (caso 1). **No puedo saber desde el log qué cajas tocó ni en qué orden.** El log sí muestra 23 `PUT /executions/53a086cb…/analysis` justo antes: esas son ediciones del **informe individual** de la prueba de estrés, que sí se guardan.

### ¿Afecta a los exportados?

**Sí, en el mismo sentido.** Los dos exportadores leen los overrides **de la base**, no de la pantalla (`_load_section_overrides`, 1711 y 1813). Antes de exportar, la pantalla vacía el guardado pendiente (`flushPending`, 394 y 418), así que **exportar sin salir de la página sí lleva la edición**. Lo que se perdió al salir no sale en ningún exportado.

- Los overrides generales (`ai_analysis_*`) se aplican en PDF y HTML con `_apply_ia_overrides`.
- `_aplicar_overrides_tx` sigue llamándose (PDF 223-225, HTML 1004-1006).
- **Hueco aparte:** un override de transacción **solo se aplica si esa transacción ya tiene texto** en `transaction_chart_analyses`. `_aplicar_overrides_tx` solo actualiza bloques que ya existen (1162-1168). Si se edita en pantalla una transacción sin texto guardado, la edición no llega al exportado.

**El historial** (`GET /integrated-reports`) **no muestra ediciones por diseño**: devuelve nombre, fechas, `has_consolidated` y el número de secciones (2176-2185). Lo único que cambia al guardar es `updated_at`.

### Archivos y tamaño

| Archivo | ¿Protegido? | Cambio |
|---|---|---|
| `frontend/src/pages/IntegratedReportPage.tsx` (707) | No | Al desmontar, **mandar** el guardado pendiente con `keepalive`, en vez de cancelarlo; `beforeunload` con `sections`; estado «pendiente» desde la primera edición; `dirtyRef` limpio solo si no llegó otra edición en vuelo. **~30-40 líneas** |
| `frontend/src/components/dashboard/TransactionReportSection.tsx` (673) | No | Que no diga «Guardado» antes de tiempo, y vaciar su temporizador al desmontar. **~10 líneas** |
| `backend/app/api/v1/endpoints/integrated_report.py` (2293) | No | `db.refresh(report)` antes de escribir en `generate-consolidated`. **~3 líneas** |

**Total: ~45-55 líneas en 3 archivos, ninguno protegido.** Se valida con `cableado_c2_integrado.py` (regla 24) más los cuatro escenarios de la tabla de arriba. `repro_integrado.py` ya los reproduce sin escribir en la base.

---

## 2. El integrado no deja elegir qué incluye

### Qué hay hoy

Solo se elige **la sección entera**. Por cada ejecución se puede añadir «Reporte», «Monitor (n)» o «Evidencia (n)» (`IntegratedReportPage.tsx:542-557`), quitar una sección y reordenarlas. **No se puede elegir** qué captura de infraestructura entra, qué evidencia, qué transacción ni qué capa de gráfica.

**El historial no guarda ninguna selección.** Cada sección se guarda como `{order, type, source_id, source_name, overrides?}` y nada más. `SectionInput` (1032-1036) no tiene dónde ponerla.

**Hay además una discrepancia pantalla/exportado:**
- **En pantalla**, una sección «Reporte» muestra dentro su monitoreo y sus evidencias si no se añadieron como secciones aparte (457-470).
- **Los exportados** solo los incluyen si se añadieron como secciones aparte (1743-1751, 1835-1842).
- Resultado: **lo que se ve no es lo que se exporta.**

### Cuánto se reutiliza

- **Casi todo el backend de transacciones y capas.** `_build_transaction_reports(…, seleccion=None, capas=None)` (`export_pdf.py:185`) y `build_transaction_reports_plotly(…, seleccion=None, capas=None)` (`export_html.py:64`) **ya aceptan la selección**. El integrado los llama sin ella (224, 1005). **No hay que tocar ningún protegido**: basta con pasársela desde `integrated_report.py`.
- De `seleccion.py`, las funciones se usan tal cual, con un matiz: `filtrar_transacciones` devuelve **400** si un label no existe (62-67). En el integrado, una selección guardada que se quedó vieja **rompería el exportado entero**, así que hay que tolerarla.
- `ExportScopeDialog.tsx` está atado a una sola ejecución y a un formato. Su lista de casillas se puede reutilizar por sección, pero el diálogo tal cual no.

### Qué hay que escribir

| Qué | Dónde | Protegido |
|---|---|---|
| Campos `tx`, `adjuntos` y `capas` en `SectionInput`; pasarlos a `_generate_full_execution_pdf_html` / `_plotly_html` | `integrated_report.py` | No |
| Filtro por id en `_get_attachments` (1236-1242) | ídem | No |
| Que la selección sobreviva a regenerar: `_merge_overrides` solo conserva `overrides`, y el frontend manda secciones «desnudas» en 359, 400 y 424 | ídem + `IntegratedReportPage.tsx` + `ConsolidatedAnalysisSection.tsx:66` | No |
| Opciones por sección en la pantalla | `IntegratedReportPage.tsx` | No |
| Filtrar capturas y evidencias en pantalla | `MonitoringReportSection.tsx` | No |
| **Ocultar transacciones en pantalla** | `TransactionReportSection` lo monta `Dashboard.tsx` (938-945) | **Sí: `Dashboard.tsx`** |

**Tamaño: ~200-300 líneas en 5-6 archivos.** Las capturas, las evidencias y los exportados **no tocan ningún protegido**. Que la **pantalla** oculte transacciones sí toca `Dashboard.tsx`: un cambio de pocas líneas (pasar una prop), pero hace falta tu autorización. Si no se autoriza, la selección de transacciones solo afectaría al exportado.

**Queda una decisión tuya:** ¿la selección alimenta también al consolidado (lo que no se incluye, la IA no lo lee) o solo al documento?

---

## 3. Lo que recibe la IA — el punto que más importa

### Qué pasa

**La mayoría de las secciones del informe general no reciben ninguna serie de tiempo.** Solo reciben agregados. Y el bloque de estilo les prohíbe inventar cifras que no estén en los datos (`estilo.py:166-169`). Ante una pregunta sobre el tiempo y sin datos del tiempo, el modelo hace lo correcto: **dice que no puede**. Las dos frases que encontraste salen exactamente de ahí.

### Cada llamada y lo que recibe — informe general

Secuenciales, en `run_ai_and_verdict` (`services/ai/analysis_pipeline.py:62-442`). Todas llevan el mismo bloque fijo de sistema (~1.800 tokens).

| # | Sección | Lo que recibe | ¿Serie? |
|---|---|---|---|
| 1 | Tabla resumen | Tabla por transacción (muestras, errores, promedio, P95, P99, mín., máx., caudal), grupos por tiempo, totales, criterios | No |
| 2 | Errores | Conteo por `label × código`. **`'message': ''` siempre** (ap:177), aunque el JTL trae `responseMessage` y `failureMessage` | No |
| 3 | Response Times | Por label: promedio, mín., máx., etiqueta `[PICO]` si máx/prom ≥ 10, P90/P95/P99 | No |
| 4 | Latency | Una línea: latencia media, tiempo medio, KB/s | No |
| 5 | **Error Rate** | Solo: *«Tasa de error: X (N de M peticiones). Duración: S segundos.»* (ap:253-258). **Y el prompt le pide decir si los fallos son «constantes, intermitentes o van a más»** (`gemini.py:1565`) | **No** |
| 6 | Response Codes | Totales acumulados por código. El prompt pregunta «si los fallos se concentran en algún tramo» (1567) | No |
| 7 | TPS | Caudal total y por label | No |
| 8 | **Active Threads** | Solo *«Concurrencia durante N segundos. Tiempo promedio…»* (ap:304-308): **ni un número de hilos**. El prompt pide subida, meseta, bajada y cuántos a la vez (1571) | **No** |
| 9 | Redirecciones *(solo si hay)* | Tabla y conteos | No |
| 10 | Conclusiones | Cifras globales, criterios y veredicto, **y los textos de 1-9** | No |
| 11 | Recomendaciones | Cifras y los textos de 1, 2, 3, 4, 7 y 8. **No recibe Error Rate ni Codes** | No |

**10 llamadas** en el caso normal (9 sin errores, 11 con redirecciones).

- *«Con la información agregada no es posible atribuir los errores a una falla constante, intermitente o creciente minuto a minuto»* → **llamada 5**.
- *«…no hay máximos ni saltos puntuales»* → cuadra con la **4** o la **7**, que tampoco tienen serie.

### Informe por transacción

Seis llamadas (resumen + 5 gráficas), `services/ai/transaction_report.py`. Aquí la serie **sí llega**, pero `_serie_digest` (87-123) la reduce a una línea:

| Gráfica | Qué queda de la serie |
|---|---|
| Response Times | Promedio, pico **y la hora del pico** — la única con «cuándo» |
| Latency | Promedio y máximo. Sin hora |
| Error Rate | Cuántos intervalos tuvieron fallo y el pico. **Sin hora, sin tramos, sin tendencia** |
| Codes | **Totales acumulados**: la dimensión tiempo se tira |
| TPS | Promedio y máximo. Sin mínimo ni hora |

**Total de «las 17»:** 10 (±1) del general + 6 por transacción crítica. Con una transacción son 16, o 17 si hay redirecciones.

### ¿Están las series donde se arman los prompts?

**Sí, y sin tocar el protegido.**

- **General.** El `parser` ya parseado está en el ámbito de `run_ai_and_verdict`. `parser.get_timeline_data(interval)` (`jtl_parser.py:388-423`) ya calcula por intervalo promedio, latencia, conteo, `error_rate` y **`active_threads`**. Se **llama**; `jtl_parser.py` no se toca. Un comentario en ap:223-224 dice que `get_all_charts_data()` se quitó de aquí a propósito, cuando se retiraron las gráficas de «Over Time».
- **Por transacción.** El diccionario `series` completo ya llega a `generate_transaction_report`. Solo lo resume `_serie_digest`.
- **Para recalcular a posteriori**, el JTL está en disco (`/app/uploads`) y se re-parsea bajo demanda. La tabla `test_results` existe, pero **nadie escribe en ella**.

### Coste de darle a cada sección su serie resumida

| Cambio | Archivo | Líneas |
|---|---|---|
| Un resumidor único: máx., mín. y promedio con **la hora** de cada uno; 3-5 tramos (subida / meseta / bajada) con su promedio y máximo; rachas de intervalos con error; tendencia. Todo formateado con `estilo.py` (regla 22) | **nuevo** `services/ai/resumen_serie.py` | 120-180 |
| General: una llamada a `get_timeline_data` y el resumen de **su** serie en las secciones 4, 5, 6, 7 y 8 (y la 8 recibe por fin los hilos) | `analysis_pipeline.py` | 40-70 |
| Por transacción: rehacer `_serie_digest` con el resumidor, incluidos los códigos **en el tiempo** (primer 5xx, tramos) | `transaction_report.py` | 40-60 |
| Ajustar el texto de lo que cubre cada gráfica, si hace falta | `gemini.py` | 0-15 |

- **~200-320 líneas.** **Ningún protegido**: `jtl_parser.py` solo se llama.
- **Coste en tokens:** +150-400 de entrada por sección. Son ~+10 % de entrada por informe, y la salida no cambia. **Ninguna llamada nueva.**

**De paso, y es barato:** que la sección de errores reciba los `responseMessage` y `failureMessage` más frecuentes por código. Hoy van vacíos a propósito o por olvido, y es lo que permite distinguir un 500 de otro 500.

### ¿Las llamadas comparten algo?

**No.** Las secciones 1 a 9 son **independientes**: cada prompt se arma solo con sus datos. La de códigos **no sabe** lo que dijo la de errores, y la de Error Rate tampoco. Solo Conclusiones y Recomendaciones reciben los textos anteriores, y Recomendaciones deja fuera Error Rate y Codes.

**Una «lectura base» que las demás respeten:**

- **Qué es.** Una llamada nueva, **la primera**, que recibe los resúmenes de serie y devuelve 8-12 hechos numerados. Por ejemplo: «los errores empiezan a las 10:14 y son intermitentes», «el código dominante de fallo es 500». Esos hechos entran en todas las demás como «HECHOS FIJADOS, no los contradigas».
- **Dónde.** `gemini.py` (~90-140 líneas, entre la llamada nueva y un parámetro opcional en cada `analyze_*`), `analysis_pipeline.py` (~20) y `transaction_report.py` (~30).
- **Coste.** +1 llamada por informe y +1 por transacción, +200-400 tokens de entrada en cada llamada posterior, y **~10-20 s más** con `gpt-5.5`. Opcionalmente, guardarla en una columna nueva de `test_executions`, lo que obliga a un `ALTER` (regla 10).

**Orden recomendado dentro de este punto:** primero las series (sin llamadas nuevas). Después, **con un informe regenerado delante**, decidir si hace falta la lectura base. Con datos de tiempo, parte de la incoherencia entre secciones puede desaparecer sola, porque todas leerían los mismos hechos.

---

## 4. El canal de contexto del analista

### ¿Hay hoy algún campo que llegue a los prompts?

**Ninguno.**

- `description` se rellena sola con «Cliente: X» (`UploadJTL.tsx:318`) y **no hay campo en el formulario** para escribirla.
- `description`, `name`, `client` y `project` solo se guardan en base: `run_ai_and_verdict` no los recibe (`upload.py:443-450`).
- Si los criterios no son JSON válido se guardan como `{"raw_text": …}`, y **todos los prompts ignoran `raw_text`** (`criterios.py:28-34`).
- Lo único libre que llega a un prompt es la **descripción de una captura**, en el análisis de imágenes.

### La conversación previa — dimensionada, no implementada

| Etapa | Qué | Archivos |
|---|---|---|
| **C1** | Guardar y usar un **contexto libre**, sin preguntas: un campo de texto en la carga que viaja a todos los prompts como «CONTEXTO DEL ANALISTA (hechos declarados, no cifras)». **Resuelve ya lo de «el servicio se apagó a mitad de prueba».** | `UploadJTL.tsx`, `api.ts`, `upload.py`, `analysis_pipeline.py`, `gemini.py`, `transaction_report.py`; una columna en `test_executions` → **`ALTER` manual** (regla 10). ~120-180 líneas |
| **C2** | **Las preguntas**: un endpoint que, con el JTL ya parseado, pide a la IA 3-6 preguntas a partir de los resúmenes de serie de §3 (+1 llamada) | endpoint nuevo en `upload.py` o módulo aparte; `gemini.py`. ~100-150 líneas |
| **C3** | **Las respuestas** en la pantalla de carga: un paso nuevo antes de «Analizar» | componente nuevo + `UploadJTL.tsx` + `api.ts`. ~150-250 líneas |
| **C4** *(opcional)* | **Mostrar** el contexto en el informe | Toca `Dashboard.tsx`, `export_html.py` y `export_pdf.py`: **los tres protegidos**. Se puede no hacer: el contexto informa el análisis sin aparecer en el documento |

**Total C1-C3: ~400-600 líneas en 6-8 archivos, +1 llamada por carga, ningún protegido.**

- **C1 da el 80 % del valor con el 30 % del trabajo**, y no depende de nada.
- **C2 depende de §3**: sin series, la IA no tiene de qué preguntar.
- **Tabla o columna.** Si las preguntas tienen que existir **antes** de que exista la ejecución, o se quiere su historial, es una tabla nueva (la crea `create_all`). Si no, basta una columna.

### Por qué no se puede arrastrar el JTL

**No lo he podido determinar leyendo el código, y lo declaro (regla 33).** Los manejadores de `UploadJTL.tsx` están bien escritos: `onDragOver` con `preventDefault` y `onDrop` que llama a `addFiles` (95-103, 196-206, 436-446). Diferencias concretas con los dos diseñadores, cualquiera de las cuales encaja con «no funciona»:

1. **La extensión se compara distinguiendo mayúsculas** (`f.name.endsWith('.jtl')`, línea 130). Un `resultados.JTL` o `.CSV` se rechaza con «Solo se permiten archivos .jtl, .csv o .xml». El diseñador IA pasa el nombre a minúsculas (`AIScriptDesigner.tsx:535-537`).
2. **La zona de suelta es solo el recuadro punteado**, debajo de los campos del formulario, y **no hay ningún manejador a nivel de página**. Soltar fuera del recuadro hace que el navegador **abra o descargue el archivo**, que parece «no deja arrastrar».
3. **El resaltado parpadea**: `dragleave` lo apaga al pasar sobre cualquier hijo (el icono, el botón, el texto). El diseñador IA lo evita comprobando `relatedTarget` (518-524). Da la impresión de que la zona rechaza el archivo, aunque la suelta funcionaría.

**Para cerrarlo hace falta una prueba tuya de 30 segundos:** soltar un `.jtl` en minúsculas **justo dentro** del recuadro, y decirme si sale el error rojo, si el navegador abre el archivo o si no pasa nada.

- **Tamaño:** ~15-25 líneas en `UploadJTL.tsx` (no protegido).
- **R4:** `UploadJTL.tsx` es código de pantalla, así que antes de tocarlo aviso en el chat y espero tu confirmación.

---

## 5. Las imágenes pixeladas

### Medido

| Etapa | Resolución | Evidencia |
|---|---|---|
| Archivo subido → guardado | **Idéntico, byte a byte.** Ni el frontend redimensiona antes de subir (`AttachmentSection.tsx:81-94`) ni el backend (`attachments.py:58-59` escribe los bytes tal cual; no importa PIL) | 39 archivos en `/app/media/attachments`: de 607×241 a **1911×599 px**, PNG; media 171 KB (monitoreo) y 40 KB (evidencias) |
| → HTML del integrado | **Original.** Base64 del archivo sin tocar (`integrated_report.py:1494-1500`), `max-height:800px` | — |
| → PDF del integrado | **Original.** Mismo base64. WeasyPrint lo recodifica sin pérdida | Medido en el PDF de `42505814…`: las 8 capturas entran con **todos sus píxeles** |
| → PDF / HTML individuales | **No llevan capturas** desde hace tiempo (`export_html.py:41`, `export_pdf.py:26`) | — |
| → IA (Vision) | Original, sin reducir, y **no se reescribe el archivo** | — |

**Tampoco hay límite de tamaño que recorte:** el límite es 10 MB por archivo (`attachments.py:24`) y se rechaza, no se reduce.

### Entonces, ¿por qué se ven mal?

**Porque el texto dentro de la captura queda diminuto en el papel, no porque se pierdan píxeles.**

- Una captura de Dynatrace a 1.904 px de ancho se imprime a **214 mm**, es decir a unos 226 ppp. Una letra de 12 px de la pantalla original sale a **~3,8 pt** en el PDF, la mitad del mínimo de 8 pt de la regla 17.
- Al ampliar en el visor para leerla, se ven los píxeles: es la resolución **de la pantalla donde se tomó la captura** (96 ppp, `dpi=(96,96)` en el propio PNG).
- Recorte del original a 1:1 en `diag120/orig_crop.png`: **ya es así de blando en el archivo subido**.

| Página del PDF | Captura (px) | Tamaño impreso | ppp efectivos |
|---|---|---|---|
| 6 | 1290 × 555 | 139,5 × 60,0 mm | 235 |
| 8 | 1755 × 368 | 259,0 × 54,3 mm | 172 |
| 10 | 1904 × 533 | 214,3 × 60,0 mm | 226 |
| 13 (evidencia) | 1543 × 157 | 259,0 × 26,4 mm | 151 |

### Qué se puede subir

**La mejora está en la captura, no en el código.** Capturar con el navegador al **200 %** (o con la escala de Windows al 200 %) da ~3.800 px de ancho y el doble de nitidez. Estimación, **no medida**:

| Opción | Peso por captura | Integrado con 10 capturas |
|---|---|---|
| Hoy (1×, PNG) | 130-700 KB | ~2,9 MB *(medido: 8 capturas)* |
| **2×, PNG** | ~0,6-2 MB | **~8-18 MB**: grande para correo |
| 2×, recodificado a JPEG calidad 90 **al exportar** | ~250-500 KB | ~4-7 MB |

La tercera fila sería un cambio de **~15 líneas** en `_build_att_html` (`integrated_report.py`, no protegido). El archivo original no se toca y el PDF no se dispara. **Pero un JPEG mete ruido alrededor del texto fino**: la decisión es tuya, y conviene verlo en una captura real antes de decidir.

---

## 6. El espacio del PDF

### Rasterizado

Páginas del integrado `42505814…` en `C:\proyectos\Kinetix_pruebas\diag120\`: `pdf_integrado_p06.png`, `p09`, `p13` (capturas) y `p03` (gráficas, para comparar).

**Medido en las 8 páginas de capturas:**

- Cada página lleva **una sola** captura con su análisis.
- El contenido acaba entre los **93 y los 127 mm** de una hoja de 210 mm con 15 mm de margen inferior.
- Quedan **~70-100 mm en blanco por página**, un 40 % de la hoja.
- Las capturas estrechas no llegan a la mitad del ancho: la de la página 6 ocupa **139 de 267 mm**.

### Qué CSS lo provoca

Todo está en **`_build_att_html`, rama `for_pdf`** (`integrated_report.py:1447-1468`). **No es `report_generator.py`**: el protegido no maqueta capturas.

1. **`max-height:60mm`** en la imagen (1465-1468). Una captura ancha queda limitada por el alto: la página 6 se queda en 139 mm de ancho con ~64 mm en blanco a cada lado.
2. **`page-break-inside:avoid`** en la tarjeta entera, que lleva título, imagen y análisis (1455-1458). Una tarjeta mide ~90-110 mm y **no caben dos en 180 mm**: la segunda salta a la página siguiente y deja el hueco. **Es la causa principal de los huecos.**
3. **`page-break-inside:avoid`** también en la caja del análisis (1448-1452). Lo agrava.
4. **Imagen y texto apilados.** Las gráficas del cuerpo ya se arreglaron en N2.1 con dos columnas (gráfica 46 % · análisis 54 %, `report_generator.py:932-939`); **las capturas nunca recibieron ese trato**.

Y un detalle: el comentario de la línea 1756 promete que `.conclusions-block` fuerza una página nueva, pero **esa clase no tiene CSS en ningún sitio**. La caja final hereda `break-inside: avoid` de `.ai-box` (del estilo extraído del protegido) y salta entera de página.

### El arreglo

- **Solo `integrated_report.py`, no protegido: ~20-30 líneas.**
- Quitar `avoid` de la tarjeta y dejarlo en la pareja título + imagen, para que el análisis pueda pasar a la hoja siguiente.
- Subir el tope de alto (a ~85-95 mm) o, para las capturas anchas (proporción > 2,5:1), fijar el ancho al 100 %.
- **Opcional:** las dos columnas de N2.1 para las capturas estrechas.
- Resultado esperable: **~2 capturas por página** en lugar de una, con la letra de dentro más grande (esto ayuda también a §5).
- **Se valida rasterizando**, como aquí, antes y después.

---

## 7. Las dos cajas de conclusiones

### Dónde y por qué son dos

**Es diseño, no un fallo.** `POST /reports/integrated/generate-consolidated` (`integrated_report.py:1900-2154`) agrupa las ejecuciones por tipo (`executions_by_type = {"load": […], "stress": […]}`, 1927-1943) y hace **una llamada a la IA por tipo** (2035). Guarda `consolidated_analysis = {load: {conclusions, recommendations}, stress: {…}}`. La pantalla incluso lo anuncia: «Se generarán análisis separados para Carga y Estrés» (`ConsolidatedAnalysisSection.tsx:92-94`).

- **En pantalla:** dos pares de cajas, uno por tipo (150-195).
- **En los exportados:** una sola caja, pero con el texto aplanado en dos bloques («PRUEBA DE CARGA… — PRUEBA DE ESTRÉS…», `_flatten_consolidated`, 1374-1387). Se sigue leyendo como dos.
- **Las conclusiones individuales NO se cuelan.** Se retiran en el PDF (`_strip_pdf_individual_conclusions`), el HTML no las pinta y la pantalla las oculta (`Dashboard.tsx:947-948`).

**Por qué la infraestructura va por separado:**

- **El análisis global de monitoreo nunca se pinta.** Todas las llamadas pasan `ai_analysis=""` (1585, 1746, 1838), así que la caja «Análisis Global» sale siempre vacía.
- **Al consolidado sí entra, pero solo en uno de los dos bloques.** El de la prueba cuyo `test_type` coincide con la ejecución que tiene las capturas (1983-1999). Con las capturas colgadas de la prueba de carga, **el bloque de estrés no sabe nada de la infraestructura**. Lo mismo pasa con las evidencias.

### Coste de una sola caja de conclusiones y una de recomendaciones

| Qué | Dónde | Líneas |
|---|---|---|
| Un solo prompt que compare carga frente a estrés **y los cruce con la infraestructura y las evidencias**; una sola clave (`all`); ~600 palabras por bloque en vez de 400 | `generate_consolidated_analysis` | 40-60 |
| `_flatten_consolidated` con la etiqueta nueva (hoy `all` saldría como «PRUEBA DE ESTRÉS»); exportados con **dos cajas reales** (conclusiones y recomendaciones) y sin el salto de página forzado | `integrated_report.py` | 20-30 |
| Rótulos y el texto de «análisis separados»; **las tres copias** de la lógica de aplanado en la página (36-43, 280-285, 641-648), que conviene dejar en una | `ConsolidatedAnalysisSection.tsx`, `IntegratedReportPage.tsx` | 15-25 |

- **~80-115 líneas, ningún protegido.**
- **Pasa de 2 llamadas a 1**, con un prompt más largo.
- **Compatibilidad:** los integrados ya guardados tienen `load` y `stress`. Se leen tal cual (el bucle de pantalla ya es genérico) y se unifican al regenerar. **Nada se migra**, igual que D60.
- **De paso:** `POST /integrated` hace **otra llamada** con un prompt unificado antiguo (1605-1639), cuyo texto se usa en los exportados hasta que existe el consolidado. Hay dos fuentes de conclusiones, y retirarla ahorra una llamada por «Generar Informe Integrado».

---

## 8. Resumen y orden propuesto

| # | Punto | Causa en una línea | Archivos | Protegido | Tamaño |
|---|---|---|---|---|---|
| 1 | Ediciones del integrado | El guardado se cancela al salir y F5 no manda `sections`; la pantalla dice «Guardado» antes de tiempo | `IntegratedReportPage.tsx`, `TransactionReportSection.tsx`, `integrated_report.py` | No | ~45-55 líneas |
| 2 | Elegir qué incluye | No existe: solo secciones enteras; los constructores ya aceptan selección | `integrated_report.py`, `IntegratedReportPage.tsx`, `MonitoringReportSection.tsx`, `ConsolidatedAnalysisSection.tsx` | Solo si la **pantalla** oculta transacciones: `Dashboard.tsx` | ~200-300 líneas |
| 3 | Lo que recibe la IA | 5 de las 8 secciones de gráfica no reciben serie; Active Threads ni siquiera los hilos; las secciones no comparten nada | nuevo `resumen_serie.py`, `analysis_pipeline.py`, `transaction_report.py`, `gemini.py` | No | ~200-320 (+90-190 la lectura base) |
| 4 | Contexto del analista | Ningún campo libre llega a los prompts | C1: 6 archivos + `ALTER` | No (salvo mostrarlo: C4) | C1 ~120-180; C1-C3 ~400-600 |
| 4b | Arrastrar el JTL | Sin determinar; tres candidatos | `UploadJTL.tsx` | No | ~15-25 |
| 5 | Imágenes pixeladas | No se pierde resolución: el texto de la captura queda a ~4 pt en papel | Ninguno obligatorio; opcional `integrated_report.py` | No | 0 (~15 opcional) |
| 6 | Espacio del PDF | `avoid` en la tarjeta entera + `max-height:60mm` | `integrated_report.py` | No | ~20-30 |
| 7 | Dos cajas | Un consolidado por tipo de prueba, por diseño; la infraestructura solo entra en uno | `integrated_report.py`, `ConsolidatedAnalysisSection.tsx`, `IntegratedReportPage.tsx` | No | ~80-115 |

**Orden que propongo, y por qué:**

1. **§1 — las ediciones del integrado.** Es **pérdida de trabajo** y cada día que siga así se pierden más ediciones. Es el más pequeño y no toca ningún protegido. Una etapa sola, validada con los cuatro escenarios de §1.
2. **§6 — el espacio del PDF**, con la guía de §5 (capturar al 200 %). Veinte líneas en un archivo no protegido, se valida rasterizando y **no gasta IA**. Y mejora a la vez lo que pedías en §5.
3. **§3 — las series a los prompts**, sin la lectura base. Es **lo que hace que el informe concluya**, y tras el paso 1 del orden es lo que más valor tiene. No añade llamadas. **Cuesta IA real validarlo** (regenerar informes: regla 25), por eso va después de lo que se valida gratis.
4. **§4 C1 — el campo de contexto libre.** Va aquí porque **usa las mismas tuberías que §3** (`analysis_pipeline.py`, `gemini.py`, `transaction_report.py`): hacerlo justo después evita abrir dos veces los mismos prompts. Resuelve lo de «el servicio se apagó».
5. **§7 — una caja de conclusiones y una de recomendaciones.** Es otro prompt, y conviene diseñarlo **con §3 ya hecho**: el consolidado heredará textos con cifras de tiempo y la comparación carga/estrés tendrá con qué cruzarse.
6. **§3b — la lectura base**, solo si con §3 y §7 hechos siguen saliendo secciones que se contradicen. Puede que no haga falta.
7. **§2 — la selección en el integrado.** Es la más grande de las de pantalla y tiene una decisión tuya pendiente: si la selección alimenta al consolidado, y si autorizas tocar `Dashboard.tsx`.
8. **§4 C2-C3 — la conversación previa.** Es la más grande y **depende de §3**: sin series, la IA no sabe qué preguntar.
9. **§4b — arrastrar el JTL:** en cuanto me digas qué pasa al soltar el archivo. Es pequeño y se puede meter en cualquier hueco, **avisando antes por R4**.

**Ningún cambio de código en este diagnóstico.**
