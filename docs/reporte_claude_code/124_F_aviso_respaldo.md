Commit base `eb59c46` · 29 de septiembre de 2026

# F1 + F2 — el aviso de respaldo

**Que Kinetix diga con todas las letras cuándo un texto del informe no lo escribió la IA, y por qué.** Nace del 26 al 28 de septiembre: la clave de OpenAI dejó de valer y se generaron informes con el `FallbackAnalyzer` durante dos días sin que nadie lo supiera.

**Cero llamadas de generación a la IA. Cero escrituras en la base de Fredy.** Todo se probó contra el backend de pruebas (8002, `jmeter_analyzer_test`, sin clave de IA), y contra OpenAI solo con `models.retrieve` y una clave inventada `ZZTEST-`, que no genera ni cuesta. Fredy tenía la aplicación cerrada durante F2 (regla 31).

---

## 0. Lo que había y por qué no se veía

| Pieza | Antes |
|---|---|
| Aviso al terminar de subir | Un toast que **se cerraba solo a los 5 s** |
| `ai_status.success` | Verdad si la **primera** sección salía de la IA, aunque las otras nueve cayeran al respaldo |
| ¿Se guardaba? | **No.** Viajaba en `sessionStorage` y se borraba al leerlo |
| Informes por transacción | Una sección fallida quedaba **vacía sin ningún aviso** |
| Motivo | `GeminiAnalyzer._last_error`, un atributo **de clase** compartido entre hilos: una subida y la generación en segundo plano podían pisarse el motivo |

---

## 1. F1 — backend

| Pieza | Dónde |
|---|---|
| Tabla **`ai_section_origins`**: una fila por (ejecución, transacción, sección) con el origen (`ia` · `respaldo` · `sin_texto` · `fijo`), el proveedor y el modelo, el tipo de motivo, **el error literal**, la fecha y si se corrigió a mano después | `db/models/ai_origen.py` (**nuevo**) |
| La única definición de qué es respaldo, cómo se cuenta, cómo se reconoce un informe viejo y qué dice la marca | `services/ai/origen.py` (**nuevo**) |
| Un **buzón de fallo por llamada** (`ContextVar`): `_generate` anota el tipo y el literal en el dict de quien llamó; `asyncio.to_thread` lo lleva al hilo. **Dos generaciones en paralelo no se pisan** (probado) | `gemini.py` |
| Cada sección del informe general registra su origen; `success` pasa a ser verdad **solo si todas** salieron de la IA; `ai_status` lleva el recuento y el motivo | `analysis_pipeline.py` |
| Cada sección del informe por transacción registra su origen, en el **mismo commit** que el texto | `transaction_report.py` |
| `GET /executions/{id}/origen-ia` · `ai_origen` en la lista del historial · `origen` en cada sección de `GET /transaction-report` · editar a mano marca la sección como corregida (solo si el texto **cambia**: el autoguardado reenvía todo) | `upload.py`, `schemas/test.py` |
| Lo mismo para las ejecuciones del motor propio | `performance_executions.py` |
| **`GET /ai-config/estado`**: ¿sirve la IA ahora? **Sin generar nada** (OpenAI: `models.retrieve`; Gemini: `get_model`, `transport="rest"`). Caché de 60 s, que se vacía al guardar la configuración. Para cualquier usuario activo | `services/ai/estado_ia.py` (**nuevo**), `ai_config.py` |
| La **marca invisible** en los dos exportados del integrado (HTML y metadatos del PDF: «Asunto» y «Palabras clave») | `integrated_report.py`, `origen.py::metas_para` |
| La misma marca para los exportados **individuales**: el módulo está hecho y probado, **falta enchufarlo** (ver §5) | `services/export/origen_marca.py` (**nuevo**) |

**Los motivos**, tal como los lee una persona: clave rechazada · cupo agotado · límite del proveedor · proveedor sin respuesta · respuesta vacía · modelo inexistente · IA ya caída en este informe · límite de Kinetix · sin IA configurada · error del proveedor.

**La marca**, tal como sale (decisión de Fredy: **cuántas, cuándo y por qué**):

> `Kinetix · origen del texto: 10 de 10 secciones NO las escribió la IA, 10 con texto de respaldo · generado el 2026-09-26 17:22 UTC · motivo: la clave de la IA no sirve (el proveedor la rechaza) (gpt-5.5: Error code: 401 - token_invalidated)`

**Los informes de antes del registro** se reconocen por el texto: el respaldo escribe con plantillas fijas que la IA no produce. Leído en la base de Fredy con solo `SELECT`: **13 de sus 72 ejecuciones** llevan texto de respaldo, entre ellas «asasascasc» del 28/09, que sale como «10 de 10 — informe anterior al registro del origen: se reconoce por el texto de plantilla».

### 1.1 Un fallo que ya existía, arreglado de paso

La suite lo destapó. **Si la IA no llegaba a empezar** (límite de Kinetix alcanzado, sin clave) **y la subida llevaba criterios de aceptación, el veredicto reventaba con `UnboundLocalError: summary_df`: la subida acababa en 500.** Ya pasaba en `HEAD`: la tabla se calculaba dentro del `try` de la IA (línea 132) y el veredicto la usaba fuera (468). El veredicto no depende de la IA; ahora se calcula igual.

---

## 2. F2 — pantalla

**`Dashboard.tsx` (protegido) no se ha tocado.**

| Qué | Dónde | Cómo |
|---|---|---|
| **Antes de generar** | `UploadJTL.tsx` | Se comprueba la IA **al abrir** la pantalla y **otra vez al pulsar, sin caché**. Si no sirve, el botón de siempre desaparece y queda un panel rojo: el motivo, el error literal, el botón principal «**No generar todavía · volver a comprobar la IA**» y, debajo, «Generar sin IA: el informe saldrá con texto de plantilla», **bloqueado hasta marcar** «Entiendo que el análisis no lo escribirá la IA…». La comprobación va dentro de `uploadFiles`, por donde pasan todas las subidas, también la de varios archivos |
| **Al terminar** | `UploadJTL.tsx` | Si alguna sección no la escribió la IA, un aviso que **no se cierra solo**: el informe se abre al pulsar «Entendido, ver el informe» |
| **En el informe** | `SummaryTable.tsx` | Una franja de texto encima de la tabla resumen: «Este análisis no lo escribió la IA», el motivo, la fecha, **las secciones por su nombre**, las transacciones afectadas, cuántas se corrigieron a mano y el error del proveedor desplegable. Sale también **dentro del integrado**. Solo en el informe general: el de transacción no pasa `total` a la tabla |
| **En cada sección de una transacción** | `TransactionReportSection.tsx` | Un rótulo: «Sin texto: la IA no lo generó. <motivo>». La etiqueta «IA hh:mm» ya no sale en una sección que la IA no escribió |
| **En el historial** | `History.tsx` | La columna «Origen del texto» junto a «Proyecto» («IA» · «Sin IA: 7 de 10 · clave rechazada» · «sin registro»), con la frase completa al pasar el ratón, y el filtro «**Con secciones sin IA (N)**» |
| **Al exportar** | `ExportScopeDialog.tsx` | El aviso y el botón «**Exportar PDF igualmente**». El atajo que exportaba sin abrir el diálogo (informe sin transacciones) ya no se toma si hay algo que avisar |
| **Al exportar el integrado** | `IntegratedReportPage.tsx` | Una confirmación que nombra cada ejecución afectada, con «Exportar PDF/HTML igualmente». Sale de `ai_origen` de la lista que la página ya carga: ninguna petición más |
| Las piezas | `components/common/AvisoRespaldo.tsx` (**nuevo**) | Todas dicen el motivo **con texto**; el color acompaña |

Ninguno de estos avisos sale en el PDF ni en el HTML exportados (decisión de Fredy): allí va la marca invisible.

### Las capturas

`C:\proyectos\Kinetix_pruebas\f2\`:
1. `1_subir_panel.png`: el panel de antes de generar, con «Generar sin IA» bloqueado.
2. `2_tras_generar.png`: el aviso de después, que no se cierra solo.
3. `3_informe_arriba.png` y `3_informe_franja.png`: el informe (ver §5.2) y la franja.
4. `4_transaccion_rotulo.png`: el rótulo por sección.
5. `5_exportar.png`: el diálogo con «Exportar PDF igualmente».
6. `6_historial.png`: la columna y el filtro.
7. `7_integrado_exportar.png`: la confirmación del integrado.

---

## 3. Pruebas

| Suite | Qué | Resultado |
|---|---|---|
| **`f1_respaldo.py`** (nueva) | Buzón (401 → clave, `insufficient_quota` → cupo, dos en paralelo); el pipeline entero con la clave rechazada, con la IA respondiendo y con el límite de Kinetix; las 10 plantillas reconocidas y un texto de IA no; la marca; `/estado` sin configuración, con límite y con una clave inventada contra OpenAI, y su caché. Contra el 8002: una subida `ZZTEST-F1`, `/origen-ia`, el historial, la edición a mano, una transacción y la marca en el HTML y en los metadatos del PDF del integrado | **TODO PASA** |
| **`f2_pantallas.py`** (nueva, Chromium contra el 8002) | Los 7 recorridos de §2, más un informe **sin** respaldo cuyo diálogo de exportar sale **exactamente como antes** | **TODO PASA** (26 comprobaciones) |
| `r2_series.py` · `cierre_r1.sh` (R1.1-R1.4, C2 integrado, C2 individual) · `r1_pdf_texto.py` ×2 | Regresión | **TODO PASA** |

Las dos suites nuevas limpian **solo lo `ZZTEST-F1` / `ZZTEST-F2`, por la API** (reglas 29 y 30).

`dialogo_export.py` (Etapa 6) **no se corrió**: apunta al 8001, que es la base de Fredy, y entra con contraseña, gastando cupo de login (regla 26). Su caso, que el diálogo de un informe normal no cambie, lo cubre §4b de `f2_pantallas.py`.

**Huella en la base de Fredy:** `test_executions` 72, `integrated_reports` 31, `transaction_chart_analyses` 294, **igual que antes**. La tabla `ai_section_origins` existe (la creó `create_all` al recargar) y **está vacía**.

---

## 4. De paso: la rama web de P6

Fredy fijó que el informe HTML está bien y que los ajustes de maquetación son solo del PDF. `f652cf1` había metido un `<div>` sin estilo alrededor del título y la imagen **también en la rama web**. Ahora va solo en `for_pdf`: rama web **idéntica byte a byte a `41cf237`** (antes de P6) y rama PDF idéntica a `f652cf1` (lo validado). Commit aparte: **`eb59c46`**.

---

## 5. Las dos decisiones de Fredy (29/09), aplicadas

**1. La marca en los exportados individuales. Autorizada y aplicada: 4 líneas en protegidos**, un import y una llamada por archivo:
- `export_pdf.py`: de 573 a **575** líneas.
- `export_html.py`: de 1416 a **1418** líneas.

```diff
+from app.services.export.origen_marca import con_marca   # F1
+        html_content = await con_marca(db, execution, html_content)   # F1: marca invisible
```

Comprobado:
- `f1_respaldo.py` lleva tres comprobaciones nuevas: el HTML individual lleva la meta sin pintarla, y el PDF individual la lleva en sus metadatos.
- `export_alcance.py` (6.3) y `capas_exportadas.py` (6.4) pasan sobre la ejecución de Nova de Fredy. Solo leen.

**2. La franja, arriba del todo. Autorizada y aplicada: 2 líneas en `Dashboard.tsx`** (protegido), que pasa de 1055 a **1057**, bajo la cabecera y antes de los KPIs:

```diff
+import { FranjaRespaldo } from '../common/AvisoRespaldo';   // F2
+        <FranjaRespaldo executionId={executionId} />{/* F2: arriba, bajo la cabecera */}
```

A la vez, `SummaryTable.tsx` vuelve a ser **idéntico a `HEAD`**, para que no haya dos franjas. `f2_pantallas.py` comprueba ahora:
- que la franja está **antes de los KPIs**;
- que se ve **sin bajar**: empieza en y=452 de una ventana de 1.100;
- que hay **una sola**.

`f2_pantallas.py` pasa entera, y también el cierre de R1 con los dos C2. En esa pasada **R1.1 volvió a cortarse** con `Server disconnected` al exportar el PDF: es el corte intermitente del reporte 123 §8.4, que también sale con el código de HEAD. **Repetida sola, TODO PASA.** Sigue como deuda de la suite de R1. Captura: `3_informe_arriba.png`.

## 6. Lo que queda

1. **Validación visual de Fredy** (regla 9) y **commit**.
2. **`CLAUDE.md`, al cerrar**: la regla de que el HTML está bien y los ajustes de maquetación son solo del PDF, junto a las de WeasyPrint. También la tabla nueva, los endpoints nuevos y las líneas de los protegidos.
3. **Despliegue**: la tabla nueva la crea el arranque. **Ningún SQL a mano**, ninguna variable de entorno nueva y ninguna dependencia nueva.
