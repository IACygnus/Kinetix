Commit `a9e9294` · 26 de septiembre de 2026

# ETAPA R1 — cierre: el guardado del integrado y el selector de secciones

Diagnóstico previo: reporte 120 §1 y §2. Decisiones R-D1 a R-D8 del encargo, más las tres respuestas de Fredy (opción (a) en las dos primeras preguntas; en la tercera, que el prompt del consolidado diga qué transacciones detalla el documento).

**Estado: implementado y probado en la base de pruebas. Pendiente de la validación visual de Fredy (regla 9).**

---

## 0. Marco y garantías

| Qué | Cómo |
|---|---|
| Copia antes de empezar (R5) | `C:\proyectos\Kinetix_pruebas\backup_20260926_1310_preR1.sql` (7 MB, 31 tablas) |
| Pruebas | Todas contra **`jmeter_analyzer_test`** y el backend del **8002** (regla 34), con datos `ZZTEST-` (R2) |
| Presupuesto de IA | **0 llamadas.** El backend de pruebas se reinició **sin clave de IA** (`GEMINI_API_KEY` vacía, comprobado en `/proc/<pid>/environ`). «Generar informe integrado» cae en «API key no configurada» sin salir a la red, y el log del 8002 tiene **0** líneas `AI CALL`. El prompt del consolidado se captura en proceso con un sustituto de la IA |
| Login | Ni un intento. Los tokens se generan en proceso con el `SECRET_KEY` del backend |
| Base de Fredy | **Intacta.** Huella al terminar idéntica a la del principio: `integrated_reports` 31 filas, última modificación el 25/09 18:16 UTC; `test_executions` 71, última el 26/09 17:22 UTC (12:22 en Bogotá, antes de la copia de las 13:10); `transaction_chart_analyses` 294; `execution_attachments` 39; `clients` 15 |
| Escrituras al 8001 | Tres `PATCH` con **401**, de las primeras corridas de R1.1 (§2.3). Rechazados sin escribir: token de la base de pruebas e id de un informe que no existe en la de Fredy |
| Regla 31 | Fredy cerró la aplicación antes de tocar `frontend/` |

---

## 1. R1.1 — el guardado

### 1.1 Qué fallaba (reporte 120 §1)

El guardado se programaba 1,8 s después y **se cancelaba al salir por el menú**. F5 y cerrar la pestaña mandaban **solo el consolidado**. La pantalla decía «Guardado» sin haber guardado. Los tres integrados de Fredy del 25/09 no tienen ni una edición de sección.

### 1.2 Qué se cambió

| R-D | Cambio | Dónde |
|---|---|---|
| R-D1 | La barra tiene cinco estados: **Cambios sin guardar** · Guardando… · **Guardado HH:MM** (solo con el 200 del servidor) · **No se guardó** · Sin cambios pendientes. Dentro del integrado, la caja por transacción ya no dice «Guardado» por su cuenta: dice «Se guarda con el informe integrado» | `IntegratedReportPage.tsx`, `TransactionReportSection.tsx` |
| R-D2 | `enviarAlSalir()`, una sola función para las tres salidas: al desmontar (menú), en `beforeunload` (F5, cerrar). Envía **secciones y consolidado**, con `keepalive` | `IntegratedReportPage.tsx` |
| R-D2 | Antes de armar el envío, se quita el foco de la caja activa: su `onBlur` vuelca el texto por el camino de siempre. Sin esto, escribir y pulsar F5 perdía esa caja. **No toca `Dashboard.tsx`** | ídem |
| R-D2 | El desmontaje usa `useLayoutEffect`: su limpieza corre **antes** de que React quite el DOM, así que la caja con el foco todavía existe | ídem |
| R-D3 | Un fallo sale como **mensaje rojo fijo**, no solo como color | ídem |
| R-D4 | «Guardar cambios» se resalta en ámbar en cuanto hay algo pendiente | ídem |
| — | `generate-consolidated` relee el informe antes de escribir (`db.refresh`): ya no pisa lo guardado mientras la IA redactaba (reporte 120 §1, punto 4) | `integrated_report.py` |
| — | Al regenerar el consolidado, las ediciones de **sección** pendientes se guardan, en vez de darlas por guardadas como antes | `IntegratedReportPage.tsx` |

### 1.3 Dos decisiones mías (Fredy pidió que quedaran declaradas)

1. **Contador de ediciones en vez de un sí/no.** Cada edición suma uno; un guardado solo da por guardado lo que llevaba al salir. Corrige la carrera del reporte 120 §1, punto 5: una edición hecha mientras un PATCH viaja ya no queda marcada como guardada.
2. **Copia local de lo que se envía al salir.** Antes de enviar, lo pendiente se guarda en el navegador; se borra cuando el servidor confirma. Al volver a abrir el informe:
   - si la copia sigue ahí y **la base ya tiene esos textos**, se descarta en silencio;
   - si no los tiene, la página dice **«Hay cambios de su última visita que no llegaron a guardarse»**, con «Recuperar y guardar» y «Descartar».

   Es la red de seguridad para lo único que un navegador no deja comprobar: si el envío hecho al cerrar la pestaña llegó.

**Límite declarado.** `keepalive` admite hasta 64 KB. Por encima se envía sin él: al navegar por el menú sale igual, y al cerrar la pestaña queda la copia local.

### 1.4 Validación — `r1_integrado.py` (TODO PASA)

En cada salida se editan **tres cajas** —una general, una por transacción y una de captura— y el foco **se queda dentro de la última**, sin blur.

| Camino | Resultado |
|---|---|
| Salir por el **menú** de inmediato | Las tres en la base |
| **F5** con el cursor dentro | Las tres en la base |
| **Descargar** la página (`beforeunload` + `unload`, lo que hace el navegador al cerrar) | Las tres en la base |
| **Cerrar la pestaña** de verdad | Las tres en la base. Al volver **no** se ofrece recuperar nada: la copia se descartó sola |
| Indicador | «Cambios sin guardar» o «Guardando…» antes del 200; «Guardado HH:MM» después. Nunca «Guardado» antes |
| Servidor que falla (500 simulado) | Aviso rojo visible y «No se guardó»; al salir **no** llega a la base (control). Al volver: «Recuperar y guardar» → queda en la base y el aviso desaparece |
| **HTML** exportado | Las 14 marcas |
| **PDF** exportado | Las 14 marcas, leídas del PDF real **fuera del contenedor** (`r1_pdf_texto.py`, PyMuPDF) |

Regresión de la regla 24: `cableado_c2_integrado.py` y `cableado_c2.py`, **CABLEADO CORRECTO**, contra la base de pruebas.

---

## 2. Lo que la prueba enseñó

### 2.1 `page.route()` no sirve para probar «guardar al salir»

Con el desvío 8001→8002 por interceptación de Playwright, F5 pasaba, pero **descargar y cerrar perdían el envío**. La interceptación muere con el documento, y la prueba no distinguía un fallo del producto de uno suyo.

- **Solución:** Chromium con `--host-resolver-rules=MAP localhost:8001 127.0.0.1:8002`, que desvía **en la resolución** y no intercepta nada.
- **Comprobado con una sonda:** una ruta inventada llegó 2 veces al log del 8002 y 0 al del 8001.
- **La interceptación queda solo** para simular el 500, y solo mientras dura ese caso.
- **Las dos suites C2 lo usan** si se les pasa `KX_API_PUERTO`. Antes apuntaban por defecto a la base de Fredy y hacían login por la pantalla.

### 2.2 El guardado lento — DEUDA, no es de R1

**Síntoma:** en un integrado con transacciones, un guardado hecho mientras la página aún carga tarda varios segundos en responder. En C2 se vieron **más de 6 s**; con la página ya cargada, **1,3 s**.

**Lo medido, y que corrige la hipótesis de partida** (el parseo repetido del JTL):

| Medida | Valor |
|---|---|
| Parseo del JTL de estrés de «Nova capa media» (36.895 peticiones, 8 MB) | **0,1 s** |
| `GET /charts` de una ejecución `ZZTEST-` (4.811 peticiones) | 0,29 s |
| `GET /transaction-charts` de una transacción | 0,03 s |
| **Peticiones que lanza al abrirse un integrado de dos ejecuciones** | **57** |
| … de ellas, `/charts` | **8**, cuatro por ejecución |
| … de ellas, `/transaction-analyses` | **12**, seis por ejecución |

**La causa probable no es el parseo, es el volumen.**
- La misma información se pide varias veces por ejecución: la piden `Dashboard` embebido, `TransactionReportSection`, el selector y la tarjeta, y en desarrollo `React.StrictMode` duplica los efectos.
- Todo va a **un solo proceso** de backend, que resuelve el trabajo de CPU dentro de manejadores asíncronos y deja la cola parada mientras tanto.
- Un PATCH que sale en medio espera detrás de todas.
- **No está demostrado cuál de las dos pesa más**, y lo declaro (regla 33).

**Tamaño estimado:**

| Pieza | Líneas | Protegido |
|---|---|---|
| Diagnóstico: medir con y sin `StrictMode`, y con dos procesos de backend | 0 (solo medición) | — |
| Caché del DataFrame por ejecución en `upload.py` (clave: rutas + fecha del JTL) | ~40-60 | No |
| Quitar peticiones duplicadas en la pantalla del integrado | ~30-60 | **Sí, si alguna vive en `Dashboard.tsx`** |

Mientras tanto, la barra dice «Guardando…» hasta que el servidor responde: el usuario ya no se va creyendo que está guardado.

### 2.3 Un despiste mío

En la primera integración de la regresión C2 lancé `r1_integrado.py` en segundo plano por error y lo corté al segundo. No llegó a hacer nada. Y un script de limpieza de procesos se terminó a sí mismo, porque su propia línea de órdenes contenía «8002»: el 8001 (proceso 1 y su trabajador) no se tocó.

---

## 3. R1.2 — el selector

### 3.1 Qué hace

Cada tarjeta de «Secciones del Informe» lleva un desplegable **«Incluye: …»** con casillas, «Todas» y «Ninguna».

- **Carga o estrés:** qué transacciones llevan su informe propio. «Ninguna» = solo el informe general.
- **Monitoreo o evidencias:** qué capturas entran.
- Se elige **antes de generar** y vale para la pantalla, el PDF, el HTML y el consolidado.
- **Se guarda con el informe**, por el mismo camino y con el mismo indicador que una edición.

**Convenio, el mismo del individual (`seleccion.py`):**
- `null`, ausente o `{}` = **todo**. Es lo que tiene cualquier integrado anterior a R1, que se ve igual que siempre: nada se migra.
- Una lista = solo esas.
- `[]` = ninguna.
- Marcar todas vuelve a «todo», así que lo que se añada después a la ejecución entra solo.

### 3.2 ⚠ El cambio visible de la opción (a) — lo que Fredy veía antes

**Hasta R1, en pantalla, una sección de carga o de estrés mostraba dentro sus capturas de infraestructura y sus evidencias cuando no se habían añadido como sección aparte. Desde R1 ya no las muestra: las capturas y las evidencias entran en el informe integrado SOLO como sección propia (botones «Monitor (n)» y «Evidencia (n)»).**

Es lo que el PDF y el HTML hacían siempre: nunca las incluyeron dentro de la sección de carga. La pantalla y el documento decían cosas distintas, y se alinea la pantalla al documento.

**Consecuencia para un informe ya guardado:** si se armó sin secciones de monitoreo o evidencias, al abrirlo **dejarán de verse sus capturas**. Para recuperarlas en pantalla y en el documento hay que añadir esas secciones.

### 3.3 Qué se reutilizó y qué no

| Del individual | ¿Se reutiliza? |
|---|---|
| El parámetro `seleccion` de `_build_transaction_reports` y `build_transaction_reports_plotly` | **Sí**: se les pasa desde `integrated_report.py`. **Los dos archivos protegidos no se tocan** |
| El convenio `null` / `[]` | Sí |
| El origen de la lista de transacciones (`/transaction-analyses`) | Sí, el mismo que usa la pantalla |
| `filtrar_transacciones` y su 400 | **No, a propósito.** En el individual la selección se pide en el momento; en el integrado está **guardada** y puede quedarse vieja. Un 400 tumbaría el documento entero; aquí se descarta la que ya no existe y se anota en el log |
| `ExportScopeDialog.tsx` | **No**: está atado a una sola ejecución y a un formato. Se escribió `SelectorContenidoSeccion.tsx` (101 líneas) |

### 3.4 El consolidado (R-D7 y la respuesta 3)

- **Capturas y evidencias:** lo quitado **no llega al prompt**.
- **Transacciones:** el consolidado nunca leyó sus textos (D61), y sigue sin leerlos. Lo nuevo es que el prompt lleva **qué transacciones detalla el documento**, con la orden de no remitir a un informe por transacción que no esté en la lista. Por ejemplo, «- ZZTEST-R1 carga: ninguna (solo el informe general)».
- **Defecto encontrado en R1.4 y corregido:** el consolidado se redactaba con el texto **editado** de las cajas generales (F5), pero con el texto **original** de las capturas. El PDF y el HTML ya usaban el editado, así que el consolidado podía contradecir al documento en el que va. Ahora usa el editado.
- **Sigue sin tocar, y queda anotado:** la llamada antigua de `POST /integrated` (conclusiones unificadas, reporte 120 §7) no lee ninguna edición. Su texto solo se usa hasta que existe el consolidado.

### 3.5 Decisiones mías

1. **Una sección de monitoreo o evidencias sin ninguna captura elegida no sale** en el documento, en vez de salir con el título vacío. El selector lo avisa al dejarla vacía.
2. **El selector de transacciones ofrece las mismas que pinta la pantalla**: las marcadas como críticas y las que tienen informe. Las que no tienen texto no salen en el exportado, igual que antes de R1. Por eso el prompt de estrés dice «ninguna (solo el informe general)» aunque la pantalla muestre tres bloques sin texto.

### 3.6 Archivos

| Archivo | Líneas | Protegido |
|---|---|---|
| `SelectorContenidoSeccion.tsx` | nuevo, 101 | No |
| `IntegratedReportPage.tsx` | 707 → 894 (R1.1 + R1.2) | No |
| `TransactionReportSection.tsx` | 673 → 689 | No |
| `MonitoringReportSection.tsx`, `DashboardEmbed.tsx`, `ConsolidatedAnalysisSection.tsx` | +6 a +9 cada uno | No |
| **`Dashboard.tsx`** | **1053 → 1055: 3 líneas añadidas y 1 cambiada** (declarar la prop, recibirla, pasarla). Nada más (R-D8) | **Sí** |
| `integrated_report.py` | 2293 → 2439 | No |

**`IntegratedReportPage.tsx` superó la estimación.** El plan decía unas 70 líneas para R1.1 y fueron unas 150: el exceso es la copia local con su recuperación, y los comentarios.

### 3.7 Validación — `r1_seleccion.py` (TODO PASA)

- Opción (a): una sección de carga sola no pinta ni capturas ni evidencias.
- En pantalla, con una transacción de tres, una captura de dos y ninguna evidencia: se ve solo eso.
- En la base: cada sección guarda su `seleccion`, y la de estrés, sin tocar, guarda `{}`.
- Al reabrir: «1 de 3 transacciones», «1 de 2 capturas», «ninguna captura», y la pantalla sigue igual.
- HTML y PDF: el informe de la transacción elegida sí; los de las otras dos, no. La captura 1 sí, la 2 no; la evidencia, no. El PDF se leyó fuera del contenedor.
- Consolidado: la captura elegida llega; la quitada y la evidencia quitada, no; el prompt dice qué transacción detalla el documento.
- Fusión: una petición **sin** `seleccion` (una pestaña con la versión anterior) conserva la guardada; una con `{}` es una decisión explícita, «todo».

---

## 4. R1.3 — el historial

La lista de informes integrados tiene dos columnas nuevas, calculadas del propio registro, sin ninguna consulta más por informe:

- **Trabajo guardado** (y se puede ordenar por ella): «N textos editados» y «consolidado corregido», o «Sin ediciones». Los textos se cuentan **una vez** por ejecución y campo, aunque viajen en varias secciones de la misma ejecución.
- **Contenido**: «Todo», o una línea por sección elegida («ZZTEST-R1 carga: 1 transacción», «Evidencias: …: ninguna captura»). Sin totales: darlos costaría consultar cada ejecución por cada fila.
- **Filtro nuevo «Con ediciones guardadas»**, junto a los de estado.

Validación, `r1_historial.py` (TODO PASA): la cuenta de la API coincide con la calculada por SQL (4), y la pantalla, los rótulos y el filtro también.

**Lo que dirá el historial de Fredy** (leído en su base, sin escribir):
- **10 de sus 31 informes** tienen trabajo guardado.
- Los del 25/09 que tienen consolidado, el de las **12:35** y el de las **13:14**, saldrán como «consolidado corregido» y **sin textos de sección**, que es exactamente lo que se perdió. El de las 12:11 no guardó ninguna edición y saldrá como «Sin ediciones».
- El del 12/08 10:43 lleva 10 textos editados.

---

## 5. R1.4 — punta a punta, `r1_punta_a_punta.py` (TODO PASA)

1. Se crea el integrado **desde la pantalla**: carga, monitoreo (2), evidencia (1) y estrés.
2. **Antes de generar**: la carga sin transacciones y el monitoreo sin la captura 2.
3. Se genera y se editan tres cajas: la general de carga, la general de estrés y una captura. Después se **sale a lo bruto por el menú**, con el foco dentro.
4. Base: las tres ediciones y la selección están guardadas.
5. Al volver: las tres ediciones se ven, la selección se ve en las tarjetas y no hay nada que recuperar.
6. HTML y PDF: llevan las tres ediciones y **ningún** informe por transacción de la carga, ni la captura 2. El PDF se leyó fuera del contenedor.
7. Consolidado: **ningún** texto por transacción de la carga, dice «ninguna (solo el informe general)», lleva la captura 1 y no la 2, y **se redacta sobre las ediciones**. Aquí apareció el defecto de §3.4.
8. **0 llamadas a la IA**: el log del 8002 da 0 `AI CALL` antes y después.

---

## 6. R1.5 — regresión en serie

```
docker exec -e GEMINI_API_KEY= -e OPENAI_API_KEY= jmeter_backend sh /tmp/preparar_base_de_pruebas.sh
docker exec jmeter_backend sh /app/pruebas_e2e/cierre_r1.sh
```

```
=== R1.1 guardado        TODO PASA
=== R1.2 selector        TODO PASA
=== R1.3 historial       TODO PASA
=== R1.4 punta a punta   TODO PASA
=== C2 integrado         CABLEADO CORRECTO
=== C2 individual        CABLEADO CORRECTO
CIERRE R1: TODO PASA
```

`tsc --noEmit` del frontend: sin errores. No se corrieron las suites de las etapas anteriores que apuntan por defecto a ejecuciones de la base de Fredy (`export_alcance.py`, `integrado_pdf_html.py`…). R1 no toca `seleccion.py`, `export_pdf.py`, `export_html.py` ni `report_generator.py`.

**Pruebas versionadas (regla 36)**, todas en `backend/pruebas_e2e/`: `r1_datos.py`, `r1_integrado.py`, `r1_seleccion.py`, `r1_historial.py`, `r1_punta_a_punta.py`, `r1_prompt_consolidado.py`, `r1_pdf_texto.py` (se corre fuera del contenedor), `r1_sesion_test.py` y `cierre_r1.sh`.

**Datos que quedan en `jmeter_analyzer_test`**, todos `ZZTEST-`:
- el cliente `ZZTEST-R1`;
- dos ejecuciones con sus JTL copiados en `/app/uploads/ZZTEST-R1_*.jtl` y sus imágenes copiadas en `/app/media/attachments/<id de la ejecución de pruebas>/`, de modo que ningún registro de pruebas apunta a un archivo de Fredy;
- los integrados de las suites. Los que crea R1.4 se renombran a `ZZTEST-R1 punta a punta <marca>`.

---

## 7. Despliegue

- **Sin SQL.** La selección vive dentro de `integrated_reports.sections` (JSONB), que ya existía.
- **Sin variables nuevas** y **sin dependencias nuevas**.
- Cambian backend **y** frontend: en el servidor hace falta `up -d --build` (ver `59_handoff_despliegue_analisis.md`).
- En desarrollo basta Ctrl + Shift + R.

## 8. Pendiente

- **Validación visual de Fredy** (reporte 122).
- La deuda de §2.2.
- CLAUDE.md §11 sigue diciendo 1045 líneas para `Dashboard.tsx` (ya eran 1053 antes de R1; ahora 1055) y 547 para `export_pdf.py` (573). No lo he editado: es un documento que no se toca a la ligera.
