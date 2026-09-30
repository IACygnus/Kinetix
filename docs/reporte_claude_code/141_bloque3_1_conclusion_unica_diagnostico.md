Commit base `93913ca` · 30 de septiembre de 2026 · Bloque 3, paso 3.1 — una sola caja de conclusiones y recomendaciones en el integrado (diagnóstico, solo lectura)

# Una sola conclusión en el informe integrado — diagnóstico

**No se ha cambiado código.** Todo lo de aquí sale de leer el código y de **una consulta de solo
lectura** a la base de Fredy (solo recuentos, sin textos). Lo que no se ha visto en pantalla se dice.

---

## 1. Cómo funciona hoy

### 1.1 Hay dos textos de IA, y Fredy solo ve uno

| | «Unificadas» (prompt 23 del 137) | «Consolidado» (prompt 24) |
|---|---|---|
| Dónde nace | `POST /reports/integrated` al pulsar **«Generar Informe Integrado»** (`integrated_report.py:1664`, prompt en `:1730`) | `POST /reports/integrated/generate-consolidated` al pulsar **«Generar Análisis Consolidado»** (`:2057`, prompt en `:2225`) |
| Cuántos | **Uno** para todo el integrado | **Uno por tipo de prueba**: `load` y `stress`. Con carga y estrés, dos |
| Qué recibe | Las conclusiones **originales** de cada ejecución (`execution.ai_conclusions`: **no ve las ediciones del analista**), el análisis de cada captura (el **original**, sin la edición) y los globales de monitoreo y evidencias | Por ejecución: **cifras clave** (peticiones, error, promedio, caudal, latencia, duración, P90/P95/P99), el veredicto, sus conclusiones y recomendaciones **editadas**, los análisis de sección (los editados completos y marcados «CORREGIDO POR EL USUARIO»; el resto, recortados a 400 caracteres), las transacciones que detalla el documento y las capturas **editadas** con sus globales |
| Respeta el selector de R1 | Solo el de capturas | Sí: transacciones y capturas (R-D7) |
| Se guarda | **No.** Vive en el estado `conclusions` de la página | Sí: `integrated_reports.consolidated_analysis` = `{load: {conclusions, recommendations, generated_at, edited}, stress: {…}}` |
| Se ve en pantalla | **No. No se pinta en ningún sitio** | Sí: `ConsolidatedAnalysisSection.tsx`, **dos cajas por tipo** (Conclusiones consolidadas y Recomendaciones consolidadas). **Con carga y estrés, cuatro cajas** |
| Se edita | No | Sí: `textarea` con autoguardado (F3) y copia local (R1) |

### 1.2 Lo que sale en el PDF y en el HTML

Los dos exportadores pintan **un solo bloque** «Conclusiones y Recomendaciones» al final
(`export-pdf` en `:1900`, `export-html` en `:2004`). Su texto sale de `_resolve_unified_conclusions`
(`:1460`):

1. **si la pantalla manda un texto** (`request.unified_conclusions`), ese;
2. si no, el consolidado de la base aplanado (`_flatten_consolidated`, `:1444`):
   `PRUEBA DE CARGA / Conclusiones / Recomendaciones --- PRUEBA DE ESTRES / …`.

La pantalla manda en `unified_conclusions` el estado `conclusions`, que cambia así
(`IntegratedReportPage.tsx`):

| Momento | Qué queda en `conclusions` |
|---|---|
| Al abrir un integrado guardado (`:431`) | El consolidado aplanado |
| Al pulsar «Generar Informe Integrado» (`:526`) | **El texto unificado, el que no se ve** |
| Al generar el consolidado (`:826`) o guardar una edición (`:286`) | El consolidado aplanado |

Las conclusiones propias de cada ejecución no salen en el integrado: el PDF las quita
(`_strip_pdf_individual_conclusions`), el HTML no las pinta y la pantalla las esconde
(`Dashboard.tsx`, `!embedded`).

### 1.3 Dos defectos que salen de esto (leídos en el código, no vistos en pantalla)

- **D-a. Se puede exportar un texto que Fredy no ha visto.** Tras «Generar Informe Integrado», el PDF y el
  HTML llevan el texto unificado, que no se ve, no se edita y no se guarda, **aunque el integrado ya
  tenga un consolidado editado**. Solo se corrige solo si después se edita o se regenera el consolidado.
  Al recargar la página, vuelve el consolidado.
- **D-b. El consolidado cae al respaldo en silencio y deja las cajas vacías.** Si `_generate` devuelve
  `None`, `raw` queda en `""`, no aparecen los marcadores y el corte «por la mitad» (`:2288`) guarda
  dos textos vacíos, sin aviso y sin registro en `ai_section_origins` (F1 no cubre el integrado).

---

## 2. Lo de R1 y una sola caja

| Pieza de R1 | Dónde vive | Con una sola caja |
|---|---|---|
| **Ediciones de sección** (textos de la ejecución y de las capturas) | `sections[i].overrides` | **No cambian.** Siguen alimentando el prompt como hoy («CORREGIDO POR EL USUARIO», capturas editadas) |
| **Edición de las conclusiones** | `consolidated_analysis[tipo]` con `edited: true` | La caja única es **una clave más** del mismo diccionario (`unico`). El autoguardado, las ediciones pendientes y la copia local ya trabajan por clave (`pendingEditsRef[tt]`, `copiaYaGuardada`): **funcionan sin cambios** |
| **Selector** (qué transacciones y capturas entran) | `sections[i].seleccion` | Se respeta igual que en el consolidado de hoy: lo que no entra en el documento no entra en la conclusión |
| **Historial** | `_resumen_trabajo` → `consolidado_editado` | Sigue funcionando: recorre los valores y mira `edited`. Hay que saltar la clave del legado (§3) |
| **Aviso de regenerar con ediciones** (F5) | `hasManualEdits` en el componente | Sin cambios: si la caja única o el legado tienen `edited`, pide confirmación |

**Nada de R1 se rompe**, porque la caja única se guarda donde ya se guardan las del consolidado.

---

## 3. Los integrados ya guardados

Recuento en la base de Fredy (solo lectura, 30/09/2026):

| | Integrados |
|---|---|
| Total | **32** |
| Con consolidado | 26 |
| Con consolidado **de carga y de estrés** (dos bloques) | **3** |
| Con el consolidado **editado a mano** | **8** |
| Con 2 o más ejecuciones | 7 (3 de ellos, carga y estrés; los otros 4, del mismo tipo, **ya salen con un solo bloque**) |
| Con overrides de las conclusiones de una ejecución | 0 |

**Propuesta para no perder nada, con el criterio de D60 (nada se migra):**

- **Un integrado que no se regenera sigue exactamente igual**: sus cajas por tipo en pantalla, editables,
  y el mismo texto en el PDF y el HTML. No se toca su fila.
- **Al regenerar**, el consolidado viejo **no se borra**: pasa entero a `consolidated_analysis._legado`.
  Las claves que empiezan por `_` ya las saltan los dos aplanadores (el de Python y el de la pantalla).
  Si tenía ediciones, antes sale la confirmación de F5, como hoy.
- **Pendiente de tu decisión (D2):** si el legado se enseña en pantalla, plegado y de solo lectura, o solo
  queda en la base.

---

## 4. Propuesta

### 4.1 Una caja, un prompt

**El texto unificado (prompt 23) desaparece.** El consolidado (prompt 24) pasa a ser **uno para todo el
integrado**, sin agrupar por tipo, con la forma de la guía de estilo (su ejemplo de conclusiones y
recomendaciones de dos ejecuciones): de 4 a 7 viñetas de conclusiones, con el dictamen al final y
explicado, y de 4 a 7 de recomendaciones, un solo análisis para todas las pruebas.

**Qué recibe el prompt único**, en el orden del bloque 2.2 (lo común delante):

1. **Por cada ejecución, su bloque de la ejecución**: el mismo de su informe individual
   (`contexto_prompt.contexto_de_parser`). Trae tipo de prueba, cifras globales, **tabla por
   transacción**, agrupación por tiempo de respuesta, criterios, fases y hechos. Así concluye con las
   cifras de primera mano, no solo con los textos. Cuesta parsear el JTL de cada ejecución (segundos). Sin
   JTL, se usan las cifras de la base, como hoy.
2. Su veredicto y **las transacciones que detalla el documento** (selector de R1).
3. Sus textos: conclusiones y recomendaciones y análisis de sección, **con las ediciones del analista
   primero** (como hoy).
4. Las capturas de monitoreo y de evidencias **editadas**, con sus globales, **atadas a su ejecución por
   nombre**. Hoy se atan al tipo de prueba.
5. Al final, la instrucción y el permiso de dictamen.

### 4.2 Edición y exportación

- **Pantalla:** una caja de Conclusiones y otra de Recomendaciones, a lo ancho y una debajo de la otra,
  con el mismo autoguardado. Sin el rótulo «Prueba de carga» o «Prueba de estrés».
- **PDF y HTML: la maquetación no cambia.** Solo cambia el texto que reciben: el aplanador devuelve
  `Conclusiones:` + viñetas y `Recomendaciones:` + viñetas, sin la etiqueta por tipo. La caja ya usa
  `white-space: pre-wrap` en las dos salidas (comprobado en el 139 §5.1), así que las viñetas salen una
  por línea. **La rama web no se toca.**
- **La exportación lee siempre lo guardado** (arregla D-a): con `report_id`, `_resolve_unified_conclusions`
  lee la base y no el texto que manda la pantalla.

### 4.3 Pasos atómicos

| Paso | Qué | Archivos | Líneas (estimadas) | Marca |
|---|---|---|---|---|
| 3.2 | **Prompt único** en un módulo nuevo, `services/ai/conclusion_unica.py`: arma el prompt de §4.1, lo parte por marcadores y, si la IA no responde, **devuelve el fallo en vez de dos cajas vacías** (arregla D-b). Suite sin IA que compruebe el prompt contra el integrado ZZTEST-R1 de la base de pruebas | nuevo (~160) + `pruebas_e2e/` | ~160 + suite | — |
| 3.3 | **El endpoint usa el módulo**: `generate-consolidated` guarda `consolidated_analysis.unico` y mueve lo anterior a `_legado`. `_flatten_consolidated` entiende `unico`. `_resumen_trabajo` y los avisos de estilo saltan `_legado` | `integrated_report.py` `:2057-2344`, `:1444`, `:2383`, `:2453` | −150 / +50 | — |
| 3.4 | **Fuera el unificado**: `/integrated` deja de llamar a la IA (una llamada menos por generación) y los exportadores leen lo guardado | `integrated_report.py` `:1715-1755`, `:1460` | −40 / +10 | — |
| 3.5 | **Pantalla**: la caja única, el legado según D2, el aplanador de la página, y dejar de usar `data.unified_conclusions` | `ConsolidatedAnalysisSection.tsx` (~40), `IntegratedReportPage.tsx` `:88`, `:431`, `:526`, `:826` (~20) | ~60 | **Pantalla: regla 31** (avisar y esperar tu confirmación) |
| 3.6 | **Corrida con IA sin escribir** sobre uno de los 3 integrados de carga y estrés: el consolidado de hoy (dos bloques) frente al único, lado a lado. Y regresión: `cierre_r1.sh`, `cableado_c2_integrado.py` | `pruebas_e2e/` | — | — |

**Protegidos: ninguno.** `integrated_report.py` no lo es, y ni `Dashboard.tsx`, ni `export_html.py`, ni
`export_pdf.py`, ni `report_generator.py` hacen falta. **La rama web del HTML no se toca.** Son más de 3
archivos y más de 50 líneas: por eso va en pasos (regla 4).

---

## 5. Decisiones que te tocan

1. **D1.** ¿Desaparece el texto unificado (prompt 23) y queda solo el consolidado único? Mi propuesta: sí.
2. **D2.** El consolidado viejo de un integrado regenerado: ¿plegado y de solo lectura en pantalla, o solo
   en la base?
3. **D3.** Los integrados que no se regeneran: ¿siguen con sus cajas por tipo en pantalla y en las
   exportaciones? Mi propuesta: sí, sin tocarlos.
4. **D4.** ¿Le damos al prompt el bloque de cada ejecución desde su JTL (§4.1.1), o basta con las cifras de
   la base que ya recibe?
5. **D5.** ¿Arreglamos D-a (exportar lo guardado) ya, aparte, o dentro de 3.4?
