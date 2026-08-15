# N3.1 — Diagnóstico read-only: chat/panel de transacciones críticas

**Fecha:** 2026-08-15
**Tipo:** DIAGNÓSTICO. **Cero líneas de código modificadas** (verificado con
`git status`: sin cambios en `backend/` ni `frontend/`).
**Alcance:** qué existe hoy, dónde encaja lo nuevo, y plan de sub-sprints.

---

## 1. La pantalla actual (Nuevo Reporte / UploadJTL)

### 1.1 Cómo detecta las transacciones

| Paso | Dónde |
|---|---|
| Al soltar el archivo se llama a `extractLabelsFromFile()` | `frontend/src/components/dashboard/UploadJTL.tsx:93-104` |
| Que llama al endpoint `/extract-jtl-labels` | `backend/app/api/v1/endpoints/upload.py:112-148` |
| Y pinta el panel «Criterios por Transaccion» | `UploadJTL.tsx:515-552` |

**El endpoint devuelve SOLO labels, ninguna métrica:**

```python
sorted_labels = sorted(list(labels))
return {"labels": sorted_labels, "count": len(sorted_labels)}   # upload.py:147-148
```

### 1.2 Tres limitaciones del endpoint actual (verificadas, no supuestas)

1. **Solo lee las primeras 10.000 líneas** (`upload.py:124`:
   `lines = text.split('\n')[:10000]`). En el JTL de 27.805 muestras que usé
   para medir, cualquier transacción que aparezca por primera vez después de la
   fila 10.000 **no se detecta**.
2. **Solo entiende JTL en CSV.** Usa `csv.reader` y busca una columna de
   cabecera llamada `label` (`upload.py:127-139`). Probado en vivo contra el
   backend:

   ```
   JTL CSV -> {'labels': ['Home', 'Login'], 'count': 2}
   JTL XML -> {'labels': [], 'error': "No se encontro columna 'label' en el archivo"}
   ```

   Es decir: **hoy, con un JTL en XML, el panel de criterios por transacción no
   aparece nunca.** Y hay JTL XML reales en el sistema (el de 181 MB con 8.206
   muestras que medí es uno).
3. **Re-parsea el archivo por su cuenta**, en vez de usar `JTLParser`, que sí
   soporta ambos formatos y ya está escrito y probado.

Las tres se arreglan **gratis** si el endpoint nuevo se apoya en `JTLParser`.

### 1.3 Dónde se guardan los criterios individuales

Se construyen en el cliente y viajan como un JSON dentro del payload de upload:

```typescript
// UploadJTL.tsx:228-247
const perTransaction = {};
Object.entries(transactionCriteria).forEach(([label, vals]) => { ... });
const acceptanceCriteria = JSON.stringify({
  concurrency, response_time, availability,
  ...(Object.keys(perTransaction).length > 0 ? { per_transaction: perTransaction } : {}),
});
```

Se persisten en **`test_executions.acceptance_criteria_json`**
(`backend/app/db/models/test.py:28`, columna `JSON`), escrito en
`upload.py:352` y actualizado en `analysis_pipeline.py:495`.

**Dato clave:** esa columna **ya no contiene solo criterios de entrada**. El
pipeline le escribe resultados encima:

```python
# analysis_pipeline.py:376-383
acceptance_criteria_dict['verdict'] = verdict
per_txn_result = compute_per_transaction_verdicts(summary_df, acceptance_criteria_dict)
if per_txn_result:
    acceptance_criteria_dict['verdicts_per_transaction'] = per_txn_result.get('verdicts_per_transaction', {})
```

---

## 2. Métricas por transacción sin pasar por la IA

**Sí, y ya están calculadas.** `JTLParser.get_summary_table_data()`
(`backend/app/services/jtl/jtl_parser.py:336-380`) devuelve, por cada label:

`muestras · promedio · mediana · p90 · p95 · p99 · min · max · errores ·
tasa_error · kb_received · kb_sent · rendimiento`

Es decir, **todo lo que Fredy quiere pre-llenado** (tiempo de respuesta,
errores, muestras ejecutadas) y bastante más.

### 2.1 Medición del costo (lo que pediste)

Contra un JTL real de la instalación, dentro del contenedor, mediana de 3
corridas:

| JTL | Formato | Muestras | Transac. | `parse()` | `get_summary_table_data()` |
|---|---|---|---|---|---|
| 5,0 MB | CSV | **27.805** | 3 | **0,07 s** | **0,018 s** |
| 181,4 MB | XML | 8.206 | 6 | 2,48 s | 0,024 s |

Salida real del JTL de 27.805 muestras:

```
              label  muestras    promedio    p95   max  errores  tasa_error
              token      9279  447.066925  691.1 21059       26    0.280203
Adapter VerifMethod      9277 2668.804355 3363.4 21058       56    0.603643
   Adapter SendCode      9249  149.937615  172.0   514       25    0.270299
```

**Conclusión:** un endpoint de previsualización sobre un JTL de 25-30 K muestras
cuesta **menos de 100 ms** de cómputo. El tiempo que percibirá Fredy es el de
subir el archivo, no el del cálculo. Para JTL en XML el parseo domina
(2,5 s en 181 MB), pero sigue siendo aceptable para una previsualización.

> `jtl_parser.py` está en la lista de **archivos protegidos**. No hace falta
> tocarlo: el endpoint nuevo lo llama en modo lectura.

---

## 3. Dónde persistir el análisis por transacción

Regla 10: `Base.metadata.create_all` **crea tablas nuevas solas**, pero una
columna nueva en una tabla existente exige `ALTER TABLE` manual.

| Opción | Migración | Veredicto |
|---|---|---|
| Columna `Text` nueva en `test_executions` (como las 11 de `test.py:59-71`) | **ALTER manual** | ✗ descartada por la regla 10 |
| `capacity_analysis_json` (`test.py:74`) | ninguna | ✗ ocupada por KNX-17 |
| Clave nueva dentro de `acceptance_criteria_json` | ninguna | ~ funciona, pero mezcla criterios de entrada con análisis de salida en el mismo JSON que Fredy edita a mano |
| **Tabla nueva `transaction_analyses`** | **ninguna: se crea sola** | ✔ **recomendada** |

### 3.1 Schema propuesto (sin ALTER TABLE)

```python
# backend/app/db/models/transaction_analysis.py  (archivo nuevo)
class TransactionAnalysis(Base):
    __tablename__ = "transaction_analyses"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True),
                          ForeignKey("test_executions.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    label = Column(String(500), nullable=False)     # nombre de la transaccion
    is_critical = Column(Boolean, default=False)    # marcada por IA o por Fredy
    marked_by = Column(String(20), default="ai")    # 'ai' | 'user'
    metrics_json = Column(JSON, nullable=True)      # foto de muestras/avg/p95/errores
    ai_analysis = Column(Text, nullable=True)       # el analisis individual
    ai_analysis_updated_at = Column(DateTime, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
```

Ventajas sobre meterlo en el JSON: una fila por transacción (no infla la fila de
la ejecución), se puede reanalizar una sola transacción, y el borrado en cascada
ya lo resuelve el FK — el mismo patrón que `execution_attachments`
(`backend/app/db/models/attachment.py`).

---

## 4. El pipeline de IA

### 4.1 Está fijo, no es dinámico

`run_ai_and_verdict()` (`analysis_pipeline.py:58`) son **12 pasos escritos a
mano**, cada uno en su variable, con logs `[1/12]`, `[2/12]`… y un retorno de
dataclass con campos fijos:

```python
# analysis_pipeline.py:386-401
return AIAnalysisResult(
    ai_analysis_summary=..., ai_analysis_errors=..., ai_analysis_response_times=...,
    ...
    ai_conclusions=..., ai_recommendations=..., ai_status=ai_status,
)
```

No hay registro de secciones ni bucle. **Añadir N secciones dinámicas no cabe
dentro de esta función**: lo correcto es una función aparte
(`analyze_critical_transactions()`) que se invoque después, y que escriba en la
tabla nueva. Así el pipeline de 12 pasos no se toca y no hay riesgo de regresión.

### 4.2 Costo por llamada

| Concepto | Medido / estimado |
|---|---|
| `SYSTEM_PROMPT` | **1.611 caracteres ≈ 400 tokens** (medido) |
| Métricas de una transacción en el prompt | ~150-250 tokens |
| Salida (el prompt limita a 200 palabras por análisis, `gemini.py:155`) | ~270 tokens |
| **Total por transacción** | **≈ 1.000 tokens** |

10 transacciones críticas ≈ **10 K tokens**, comparable a una sola de las 12
secciones actuales. El costo real no es el dinero sino el **tiempo**: las
llamadas van en serie con reintentos de 5/10/15 s (`gemini.py`), así que 10
transacciones pueden añadir un par de minutos al upload. Recomiendo un tope
configurable (ver decisión D4).

### 4.3 Regalo: el pre-marcado puede salir gratis

`compute_per_transaction_verdicts()` (`gemini.py:240-284`) **ya clasifica cada
transacción** como `APTO` / `APTO CON RESERVAS` / `NO APTO` comparando su p90 y
su tasa de error contra los criterios:

```python
rt_fail = p90 > rt_threshold
er_fail = error_rate > er_threshold
rt_warning = p90 > (rt_threshold * 0.8) and not rt_fail
```

Eso es exactamente «la IA premarca las críticas», pero **determinista, gratis e
instantáneo**. Propongo premarcar con esta lógica (todo lo que sea `NO APTO` o
`APTO CON RESERVAS`) y dejar la IA solo para el análisis de las marcadas. Si
Fredy prefiere que sea la IA quien decida cuáles son críticas, es una llamada
extra (~1 K tokens) — decisión D3.

---

## 5. Los exports

### 5.1 Cómo se arma hoy una sección

Cada endpoint construye un diccionario plano `ia` con **13 claves fijas**
(`export_pdf.py:229-243`) y la plantilla pinta una caja por clave:

```python
{ai_box('summary', 'Analisis del Reporte Resumen')}      # report_generator.py:871
...
{ai_box('conclusions', 'Conclusiones', ...)}             # report_generator.py:886
{ai_box('recommendations', 'Recomendaciones', ...)}      # report_generator.py:887
```

### 5.2 Punto de inserción del bloque nuevo

«Después de las secciones generales y antes de conclusiones» cae en:

| Salida | Archivo:línea | ¿Protegido? |
|---|---|---|
| PDF individual **e integrado** | `report_generator.py:886` (justo antes de `ai_box('conclusions')`) | **SÍ — PROTEGIDO** |
| HTML standalone (`build_standalone_html`) | `report_generator.py:1190` | **SÍ — PROTEGIDO** (y hoy es código muerto, ver reportes 022/023) |
| HTML individual | `export_html.py` (bloque equivalente) | no, pero en la lista de «no tocar sin mención» |
| HTML integrado | `integrated_report.py:647-690` | no |

### 5.3 La maquinaria NO sirve tal cual

`ai_box(key, ...)` pinta **una** sección desde **una** clave. Un bloque por
transacción son N cajas variables, así que hace falta un helper nuevo
(`ai_boxes_transacciones(lista)`, ~15-20 líneas) en `report_generator.py`. Es
poco código, pero **toca un archivo protegido y requiere tu autorización
explícita** (decisión D5).

---

## 6. El chat: mi recomendación es que NO sea un chat

`AIScriptDesigner.tsx` mide hoy **1.352 líneas** (el CLAUDE.md dice 532: está
desactualizado). Es una máquina conversacional completa — historial de mensajes,
adjuntar archivo, ciclo de refinamiento, preview de JMX, validación.

Lo que describes no es una conversación, es un formulario con datos:
«lista de transacciones con sus números, marco las que quiero, ajusto umbrales».
Un chat obliga a inventar turnos («¿cuáles marco?» → «marca la 3 y la 5») para
hacer lo que un check hace en un clic, y arrastra estado de mensajes que hay que
mantener.

| Opción | Esfuerzo | Riesgo |
|---|---|---|
| **Panel** (extender el `<details>` que ya existe en `UploadJTL.tsx:515-552` con una columna de métricas y un check) | **~80-110 líneas, 1 archivo no protegido** | bajo |
| Chat estilo AIScriptDesigner | ~300-400 líneas + endpoint conversacional + estado | alto |

**Recomendación: panel.** Si más adelante quieres preguntarle cosas a la IA
sobre las transacciones, se le añade un botón «preguntar a la IA» que reusa el
endpoint de análisis — sin construir un chat completo ahora. Decisión D2.

---

## 7. Plan de sub-sprints atómicos

| Sprint | Qué | Archivos | Líneas | Protegidos |
|---|---|---|---|---|
| **N3.2** | Endpoint `POST /extract-jtl-transactions`: labels + métricas reales + criticidad sugerida. Usa `JTLParser` (arregla XML y el tope de 10.000 líneas de paso) | `upload.py` + schema | ~60-80 | no |
| **N3.3** | Panel en Nuevo Reporte: tabla de transacciones con datos pre-llenados, checks, «marcar todas», criterios individuales como hoy | `UploadJTL.tsx` (706 líneas, no protegido) | ~80-110 | no |
| **N3.4** | Persistencia + análisis IA individual: modelo nuevo, servicio `analyze_critical_transactions()`, enganche tras el pipeline | modelo nuevo, servicio nuevo, `upload.py`, `analysis_pipeline.py` | ~120-150 | no |
| **N3.5** | Bloque «Análisis por transacción crítica» en las 4 salidas | `report_generator.py` **(PROTEGIDO)**, `export_html.py`, `integrated_report.py` | ~80-100 | **SÍ** |
| **N3.6** *(opcional)* | Re-analizar una transacción desde el Dashboard sin re-subir el JTL | `upload.py`, `Dashboard.tsx` **(PROTEGIDO)** | ~40-60 | **SÍ** |

Orden recomendado: N3.2 → N3.3 (ya se ve y se valida la pantalla) → N3.4 →
N3.5. Cada uno es validable por separado; N3.2+N3.3 ya te dan la pantalla
funcionando aunque el análisis todavía no exista.

---

## 8. Decisiones que necesito de ti

| # | Decisión | Mi recomendación |
|---|---|---|
| **D1** | ¿Tabla nueva `transaction_analyses` o clave dentro de `acceptance_criteria_json`? | **Tabla nueva** — se crea sola (regla 10), no mezcla entrada con salida |
| **D2** | ¿Panel o chat? | **Panel** — 1/4 del código, mismo resultado |
| **D3** | ¿Premarcado determinista (gratis, ya existe) o que decida la IA? | **Determinista**, con la lógica de `compute_per_transaction_verdicts` |
| **D4** | ¿Tope de transacciones críticas analizadas? | **Máx. 10 por informe**, configurable; si no, el upload se alarga varios minutos |
| **D5** | ¿Autorizas tocar `report_generator.py` (protegido) en N3.5? | Necesario: sin eso el bloque no sale en PDF |
| **D6** | ¿`/extract-jtl-transactions` sustituye a `/extract-jtl-labels` o convive? | **Convive** ahora, se deprecia después |
| **D7** | ¿Qué hago con los JTL en XML, donde hoy el panel no aparece? | El endpoint nuevo lo arregla sin coste extra |

---

## 9. Cierre

**No se modificó ni un archivo de código.** `git status` sobre `backend/` y
`frontend/` sale limpio (salvo los `.bak_*` de sprints anteriores, que no son
código). Todo lo medido se hizo en modo lectura: parseo de JTL existentes,
llamadas a endpoints ya desplegados y lectura de fuentes.

Dime D1-D7 y arranco con N3.2.
