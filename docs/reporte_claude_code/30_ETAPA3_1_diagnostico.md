6706591 · 2026-09-16

# ETAPA 3.1 — Diagnóstico de los textos de IA (read-only)

**Llamadas reales a la IA en este sub-paso: 0.** No se tocó ningún archivo del
proyecto: todo el trabajo salió de leer código, leer la base y correr un
prototipo del detector desde el scratchpad.

---

## 1. Inventario de prompts (D27)

Diecinueve prompts distintos, en cinco archivos. La columna «llamadas por
informe» es lo que se consume en una ejecución como `E2-validacion`
(3 transacciones, sin redirecciones, sin monitoreo ni evidencias).

| # | Prompt | Archivo:línea | Sección de telemetría | Llamadas |
|---|---|---|---|---|
| 1 | Tabla resumen | `gemini.py:1346` | `summary_table` | 1 |
| 2 | Errores | `gemini.py:1417` | `errors` | 1 |
| 3 | Gráfica (6 tipos vivos) | `gemini.py:1493` | `chart_*` | 6 |
| 4 | Redirecciones | `gemini.py:1562` | `redirects` | 0-1 |
| 5 | Conclusiones | `gemini.py:1603` | `conclusions` | 1 |
| 6 | Recomendaciones | `gemini.py:1722` | `recommendations` | 1 |
| 7 | Visión (imagen) | `gemini.py:1234` | (no pasa por `_generate`) | por imagen |
| 8 | Visión — respaldo OCR | `gemini.py:1306` | `ocr_fallback_*` | por imagen |
| 9-14 | Las 6 secciones por transacción | `transaction_report.py:144` | `txreport_*` | 6 × transacción |
| 15 | Monitoreo correlacionado | `analysis_ai.py:70` | `monitoring_analysis` | 1 si hay |
| 16 | Evidencias correlacionadas | `analysis_ai.py:177` | `evidence_analysis` | 1 si hay |
| 17 | Comparativo carga vs estrés | `compare.py:102` | `comparison_analysis` | 1 si se pide |
| 18 | Conclusiones unificadas del integrado | `integrated_report.py:1569` | `unified_conclusions` | 1 |
| 19 | Consolidado del integrado (por tipo) | `integrated_report.py:1993` | `consolidated_{tipo}` | 1-2 |

Fuera de alcance por D27, confirmado: `script_ai.py` (genera JMX),
`engine/ai_correlation.py`, `har_chunk_router.py`, `har_flow_analyzer.py`,
`jmx_chunk_assembler.py`.

### 1.1 Cómo se formatean HOY los números que entran en cada prompt

| Origen del bloque de datos | Formato | Ejemplo real que produce |
|---|---|---|
| `build_tier_summary` (`gemini.py:875`) | inglés | `avg=422ms, P95=..., ratio 3.9x` |
| `_build_transactions_table` (`gemini.py:1331`) | inglés | `\| 10,075 \| 28.20% \| 179 \|` |
| `analysis_pipeline.py:190-290` (datos de las gráficas) | inglés | `promedio 108ms, P90 123ms`, `2,841 de 10,075` |
| `generate_conclusions` / `generate_recommendations` | inglés | `Error rate: 28.20%`, `P99: 481.26ms` |
| `analysis_ai.py` (monitoreo y evidencias) | crudo de la BD | `Avg Response Time: 179.73ms` |
| `compare.py` | inglés | `{:,}` y `{:.2f}` |
| `integrated_report.py:1893` (KPIs del consolidado) | crudo de la BD | `Total Requests: 10075, Error Rate: 28.2%` |
| **`transaction_report.py` (`_n()`, línea 88)** | **español** | **`1.677 muestras`, `41,26%`, `4,0 veces`** |

Un solo módulo formatea a la española, y es justo el único cuyos textos salen
limpios. Ese contraste es el resultado más útil de este diagnóstico y está
medido en §5.

---

## 2. Reglas de estilo dispersas y sus contradicciones

Hay **cinco bloques de reglas** repartidos y **ninguno los aplica a todos los
prompts**:

| Bloque | Dónde | A qué prompts llega |
|---|---|---|
| `SYSTEM_PROMPT` (4.939 chars, 19 reglas + 4 ejemplos) | `gemini.py:327` | a todos menos visión |
| `STYLE_REMINDER` (864 chars) | `gemini.py:371` | solo gráficas generales y las 6 por transacción |
| `UX_RULE` — percentiles en personas (611 chars) | `transaction_report.py:47` | **solo** por transacción |
| `FORMATO_NUMERICO` — español (346 chars) | `transaction_report.py:60` | **solo** por transacción |
| `get_metric_unit_instruction` | `gemini.py:411` | los 10 generales |

### Contradicciones encontradas

1. **`analyze_summary_table` pide el veredicto de producción de forma
   explícita**: el punto 3 de su estructura es literalmente
   `«3. VEREDICTO: Listo para produccion? Prioridades de mejora.»`
   (`gemini.py:1405`). Es la causa directa de que el resumen de
   `E2-validacion` diga *«No debería liberarse sin corregir los errores…»*.
   Choca de frente con §4.2 y con D30.
2. **El propio `SYSTEM_PROMPT` enseña la jerga que D29 prohíbe**: su ejemplo
   aprobado dice *«fue la mas rapida con 139ms y tier excelente»*. El modelo
   copia la forma del ejemplo, y la forma incluye «tier».
3. **`build_tier_summary` entrega los datos con la jerga puesta**:
   `=== TIER CRITICO ===`, `=== TIER EXCELENTE ===`,
   `=== ALERTA: ALTA VARIABILIDAD ===`. Lo mismo hacen el `insights_summary`
   de conclusiones y el `action_items` de recomendaciones.
4. **Las instrucciones por gráfica piden la jerga**: `response_times` pide
   *«distribución por tiers»* y *«variabilidad P99/avg»* (`gemini.py:1521`).
5. **`SYSTEM_PROMPT` prohíbe la palabra «hallazgo» y tres prompts la usan**:
   el de evidencias (*«Clasifica los hallazgos por severidad»*), el de
   recomendaciones (encabezado `HALLAZGOS DE LOS ANALISIS:`) y el unificado
   del integrado (*«correlacionen TODOS los hallazgos»*).
6. **Los percentiles se traducen en un sitio y en otro no**: `UX_RULE` solo
   viaja en los prompts por transacción. En el informe general nadie pide la
   traducción, y por eso salen `P99 de 696ms` sueltos.
7. **El formato numérico igual**: `FORMATO_NUMERICO` solo viaja por
   transacción. En el general conviven `3,1 veces` y `3.9x` en el mismo
   informe.
8. **`STYLE_REMINDER` es un subconjunto literal** de las reglas 12, 13, 14,
   15, 16 y 17 del `SYSTEM_PROMPT`. No añade nada; solo repite al final.
9. **`compare.py` escribe su prompt en markdown** (`## Prueba de CARGA`)
   mientras el `SYSTEM_PROMPT` prohíbe el markdown en la salida.
10. **Topes de palabras sin criterio común**: 120 / 150 / 200 / 350 / 400 /
    500 según el prompt.

### 2.1 El `SYSTEM_PROMPT` viaja dos veces por llamada (E1.1 H3, confirmado)

`_generate` (`gemini.py:1097`) manda el `SYSTEM_PROMPT` como mensaje `system`,
y **además** cada prompt empieza por `f"""{SYSTEM_PROMPT}…"""`. Medido sobre la
telemetría de `E2-validacion`:

- 92.379 tokens de prompt en 28 llamadas, de los que **solo el 7,8 % llegó
  cacheado**.
- El `SYSTEM_PROMPT` son 4.939 chars ≈ 1.500 tokens, duplicados en cada
  llamada: **~42.000 tokens desperdiciados por informe**.

Con Gemini el bloque solo viaja dentro del prompt (el modelo se crea sin
`system_instruction`), así que D34 debe mover la responsabilidad a `_generate`
para los dos proveedores, no simplemente borrar la copia.

---

## 3. Dónde se pinta la caja de análisis — y el choque con un archivo protegido

| Vista | Componente | ¿Protegido? |
|---|---|---|
| General — resumen, redirecciones, errores, conclusiones, recomendaciones | `Dashboard.tsx:706, 764, 862, 927, 936` | **SÍ** |
| General — las 6 gráficas | `ReportBody.tsx:266-369`, con `AnalysisBox` **definido en `Dashboard.tsx:388`** | **SÍ (el componente)** |
| Por transacción | `TransactionReportSection.tsx:219` | no |
| Integrado — ejecución | `ExecutionReportSection.tsx:174` | no |
| Integrado — monitoreo/evidencias | `MonitoringReportSection.tsx:77` | no |
| Monitoreo / Evidencias | `MonitoringPage.tsx`, `EvidencePage.tsx`, `ImageAnalysisCard.tsx` | no |

Los textos del informe general llegan a pantalla por `GET /executions/{id}`
(`testAPI.getExecution`, `Dashboard.tsx:191`). Las 11 cajas del general viven
dentro de `Dashboard.tsx`, incluido el `AnalysisBox` que `ReportBody` recibe
como prop.

### PARADA declarada (D36 en el informe general)

**D36 en el informe general exige tocar `Dashboard.tsx`.** No hay forma de
evitarlo sin duplicar el detector en TypeScript, que sería una segunda fuente
de verdad y contradice D35. El diff mínimo son **tres puntos**:

1. Guardar lo que devuelva el endpoint: `const [avisos, setAvisos] = useState<Record<string,string[]>>({})`
   y una línea en `loadData` (`setAvisos(execData.style_warnings || {})`). **~2 líneas.**
2. `AnalysisBox` acepta un prop `avisos?: string[]` y, si llega no vacío,
   pinta encima una franja ámbar. **~4 líneas.**
3. Pasar `avisos` en las 11 cajas (5 directas + las 6 que van por `ReportBody`,
   que solo necesita reenviar el prop). **~11 líneas en `Dashboard.tsx` + ~6 en
   `ReportBody.tsx`.**

Total estimado en el protegido: **~17 líneas añadidas, 0 eliminadas, 0
movidas**. Ninguna toca gráficas, cálculo ni guardado.

**Esto queda pendiente de la autorización de Fredy.** El resto de la Etapa 3
no depende de ello: 3.2, 3.3 y 3.5 no tocan frontend, y 3.4 puede entregar el
aviso en transacciones, integrado, monitoreo y evidencias — todos fuera de la
lista de protegidos — más el endpoint del general devolviendo ya sus
`style_warnings`. Se continúa con eso y el aviso del general queda enchufable
con las 17 líneas de arriba en cuanto haya luz verde.

---

## 4. Auditoría anti-texto-fijo y trazabilidad (D37, primera pasada)

### 4.1 ¿Hay textos «cuadrados» en el código?

Se buscaron en `backend/` y `frontend/src/` las cifras literales y las frases
distintivas de los textos persistidos de `E2-validacion`:

`10075` · `10.075` · `10,075` · `2841` · `2.841` · `2,841` · `28[.,]20` ·
`41[.,]26` · `56[.,]77` · `71[.,]42` · `179[.,]73` · `33[.,]59` · `161[.,]70` ·
`259[.,]85` · `13[.,]33` · `481[.,]26` · `426[.,]00` · `406[.,]00` ·
`Get_Booking_Id` · `Put_Update_Booking` · `Delete_Booking_Id` ·
`Post Create_Booking` · `no cargan` · `eliminaciones que fallan`

**Resultado: 0 coincidencias en las 24 búsquedas.** Ninguna cifra ni frase de
esos informes está escrita en el código.

**La única fábrica de texto fijo del producto es `FallbackAnalyzer`**
(`gemini.py:506-800`), y lo es por diseño. Sus firmas reconocibles son
*«La prueba proceso N solicitudes con una tasa de error del…»*, *«Se evaluaron
N transacciones:»* y *«indica una disparidad significativa en el rendimiento»*.
Si alguna vez aparecen en un informe, ese informe no lo escribió el modelo.

### 4.2 ¿Salió algo de `FallbackAnalyzer` en `E2-validacion`?

No. `Kinetix_pruebas/e2_validacion.json` tiene **28 líneas de telemetría, las
28 con `outcome=ok`**, una por cada sección persistida con texto:

| | Secciones con texto en BD | Líneas `AI_TELEMETRY` |
|---|---|---|
| Informe general | 10 (redirecciones vacía, sin redirecciones en el JTL) | 10 |
| Por transacción (3 × 6) | 18 | 18 |
| **Total** | **28** | **28** |

Cero `fallback`, cero `empty`, cero `circuit_open`, cero `error`.

### 4.3 Un aviso sobre la referencia §4.3

**El ejemplo aprobado de la especificación es exactamente el dataset de
`ff186cc7`**: 10.075 transacciones, 28,20 % de error, 2.841 errores, y los
41,26 % / 56,77 % / 71,42 % de `Get_Booking_Id`, `Put_Update_Booking` y
`Delete_Booking_Id`. Es el mismo JTL con el que corrió `E2-validacion` y con
el que correrá `E3-estilo-pruebakinetix`.

Consecuencia práctica: **sobre ese JTL es imposible distinguir «el modelo usó
los datos» de «el modelo copió el ejemplo»**. Por eso la prueba de D31 solo
vale en `E3-estilo-avianca` (3.5b), que es un dataset distinto. Queda como
está en el plan; se deja anotado para que nadie lea el resultado de
`pruebakinetix` como prueba de que no copia.

---

## 5. Línea base del detector D35

Prototipo del detector corrido sobre los textos **ya guardados**, sin
regenerar nada. Cuatro tipos: `jerga` (D29), `percentil_sin_traducir` (D29),
`veredicto_fuera_de_conclusiones` (D30) y `formato_ingles` (D32).

| Tipo | `E2-validacion` | `E1.3-baseline-2` |
|---|---|---|
| `formato_ingles` | **105** | 108 |
| `jerga` | **9** | 18 |
| `percentil_sin_traducir` | **9** | 8 |
| `veredicto_fuera_de_conclusiones` | **1** | 1 |
| **Total** | **124** | **135** |

### 5.1 Repartido por bloque — el dato que decide la Etapa 3

| Bloque | Secciones | Avisos | Por sección |
|---|---|---|---|
| Informe general (`E2-validacion`) | 11 | **121** | 11,0 |
| Por transacción (`E2-validacion`, 3 × 6) | 18 | **3** | 0,17 |

**Los textos por transacción ya salen casi limpios.** Sus tres avisos son la
palabra «variabilidad» — ni una sola cifra en formato inglés, ni un solo
percentil suelto. Los del informe general acumulan 121. La diferencia entre
un bloque y otro es exactamente `_n()` + `UX_RULE` + `FORMATO_NUMERICO`.

Un ejemplo de cada lado, del mismo informe y la misma prueba:

> **Por transacción**: «1 de cada 10 usuarios espera más de 123 ms (P90:
> 123 ms) […] El pico máximo fue 438 ms a las 20:04:05, 4,0 veces su
> promedio».

> **General**: «Auth concentra la mayor variabilidad con P99 de 696ms y máximo
> de 1013ms» · «6 transacciones quedaron en tier excelente, con promedio
> global de 179.73ms».

La Etapa 3 no tiene que inventar el estilo: tiene que **llevar a los otros
diecisiete prompts lo que ya funciona en `transaction_report.py`**, y añadir el
detector para que se vea cuándo falla.

### 5.2 Los 14 términos que más se repiten en `E2-validacion`

`108ms` (7) · `P99` (6) · `33.59` (5) · `3.9` (4) · `41.26` (4) · `56.77` (4) ·
`71.42` (4) · `422ms` (4) · `3.9x` (4) · `28.20` (4) · `10,075` (4) · `99.5`
(4) · `tier` (3) · `179.73` (3).

---

## 6. Decisiones técnicas tomadas en el diagnóstico

Las declaro aquí porque afectan a lo que el detector marca:

| # | Decisión | Por qué |
|---|---|---|
| T1 | **El cierre con impacto al usuario NO es veredicto.** «En producción, el usuario percibirá reservas que no cargan» se conserva y no se marca | Lo exige la regla 16 del `SYSTEM_PROMPT`, lo conserva D28 y lo usa la referencia §4.3. D30 prohíbe el *dictamen* («listo/apto/no apto para producción», «no debería liberarse», «antes de producción»), no la frase de percepción |
| T2 | Un punto seguido de **tres** dígitos es separador de miles a la española (`3.515 ms`) y no se marca; con uno o dos dígitos es decimal inglés (`179.73`) y sí | Determinista y sin falsos positivos en los 29 textos de la línea base |
| T3 | `variabilidad` se marca entera, no solo «alta variabilidad» | D29 la nombra y el guion de 3.6 pide que no aparezca. «Variación» no se marca |
| T4 | El `%` va pegado al número (`0,27%`) y la unidad separada (`125 ms`) | D32 lo fija así |
| T5 | Las secciones con veredicto permitido son `conclusions`, `recommendations`, el consolidado y las conclusiones unificadas del integrado | §4.2 y D30 |

---

## 7. Resultado del sub-paso

- Inventario cerrado: **19 prompts**, 5 archivos.
- **10 contradicciones** documentadas, con su archivo y su línea.
- **0 textos fijos** en código; **28/28** secciones de `E2-validacion`
  verificadas como salida real del modelo.
- Línea base del detector: **124 avisos** en `E2-validacion`, de los que
  **121 están en el informe general** y **3 en los bloques por transacción**.
- **Una parada declarada**: el aviso ámbar del informe general necesita
  ~17 líneas en `Dashboard.tsx`. Todo lo demás de la etapa sigue adelante.

Siguiente: 3.2, los helpers deterministas con sus pruebas unitarias.
