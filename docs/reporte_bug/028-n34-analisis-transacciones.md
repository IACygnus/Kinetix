# N3.4 — Análisis IA individual de transacciones críticas + persistencia

**Fecha:** 2026-08-15
**Commit:** `f07bce4` — *N3.4: analisis IA individual de transacciones criticas
+ persistencia*
**Push:** `github/backup-trabajo-local` (`269603e..f07bce4`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO Y VALIDADO SIN GASTAR CUOTA DE IA** (analizador
sustituido por un stub, patrón F5).

**Presupuesto:** ~120-160 líneas, máx 4 archivos → **58 insertadas en 2
archivos existentes + 2 archivos nuevos** (modelo 44 líneas, servicio 137
líneas). Total ~239 líneas, de las cuales 137 son el servicio nuevo.

---

## 1. Lo que se añadió

| Archivo | Qué | Nuevo/tocado |
|---|---|---|
| `backend/app/db/models/transaction_analysis.py` | modelo `TransactionAnalysis` | **nuevo** |
| `backend/app/services/ai/transaction_analysis.py` | `analyze_critical_transactions()` + `build_transaction_prompt()` | **nuevo** |
| `backend/app/main.py` | 1 línea: import del modelo para que `create_all` lo cree | tocado |
| `backend/app/api/v1/endpoints/upload.py` | enganche (14 líneas) + `GET .../transaction-analyses` (37 líneas) + 2 imports | tocado |

`analysis_pipeline.py` y `gemini.py` **no se tocaron**. Del segundo solo se
importa lo que ya existía: `SYSTEM_PROMPT`, `get_gemini_analyzer`,
`load_ai_config_from_db` y `sanitize_ai_text`.

### 1.1 Por qué el servicio va aparte

`run_ai_and_verdict` son 12 pasos escritos a mano que devuelven un dataclass de
campos fijos (§4.1 del diagnóstico 025). Añadir ahí N secciones dinámicas obliga
a reescribir la función que produce **todo** el análisis que hoy funciona. El
servicio nuevo se invoca **después**, escribe en su propia tabla y no comparte
estado con el pipeline: si falla, el informe de 12 secciones sale igual.

---

## 2. Validación

### 2.1 La tabla se creó sola, sin ALTER TABLE

`\d transaction_analyses` justo después del restart:

```
         Column         |            Type             | Nullable
------------------------+-----------------------------+----------
 id                     | uuid                        | not null
 execution_id           | uuid                        | not null
 label                  | character varying(500)      | not null
 is_critical            | boolean                     |
 marked_by              | character varying(20)       |
 metrics_json           | json                        |
 ai_analysis            | text                        |
 ai_analysis_updated_at | timestamp without time zone |
 sort_order             | integer                     |
 created_at             | timestamp without time zone |
Indexes:
    "transaction_analyses_pkey" PRIMARY KEY, btree (id)
    "ix_transaction_analyses_execution_id" btree (execution_id)
Foreign-key constraints:
    "transaction_analyses_execution_id_fkey" FOREIGN KEY (execution_id)
        REFERENCES test_executions(id) ON DELETE CASCADE
```

Índice por `execution_id` ✔ · FK con `ON DELETE CASCADE` ✔ · cero migraciones
manuales ✔.

### 2.2 Caso 2 — dos transacciones marcadas, con stub

```
contadores: {'requested': 2, 'analyzed': 2, 'failed': 0, 'skipped': 0}
(a) prompts armados: 2  -> OK
(b) cada prompt lleva las metricas reales de SU transaccion (incluido el max):
    [transaction_0] token                max_en_prompt=True  faltantes=ninguno  -> OK
    [transaction_1] Adapter VerifMethod  max_en_prompt=True  faltantes=ninguno  -> OK
(c) filas persistidas: 2 -> OK
    token                critica=True orden=0 analisis=si max_guardado=21060.0
    Adapter VerifMethod  critica=True orden=1 analisis=si max_guardado=21058.0
```

El bloque de métricas que llega al modelo, extraído del prompt real de `token`:

```
- Muestras ejecutadas: 8,600
- Tiempo promedio: 443 ms
- Percentil 90: 529 ms
- Percentil 95: 561 ms
- Tiempo maximo observado: 21060 ms (48x el promedio)
- Errores: 23 (0.27% de sus muestras)
```

**El max va siempre, y con su relación contra el promedio ya calculada.** Es
literalmente la lección de GRAF1 metida en el prompt: `token` promedia 443 ms y
el modelo no puede ignorar que llegó a 21 s. La instrucción se refuerza abajo:

> *«si el maximo se dispara respecto al promedio, explica esos picos y su causa
> probable (timeouts, contencion, esperas de recursos) aunque el promedio se vea
> sano»*

La verificación no fue visual: se comprobó por búsqueda de cada valor esperado
dentro del prompt (`faltantes=ninguno` significa que los 6 valores de esa
transacción, y solo los suyos, están en su prompt).

### 2.3 Caso 3 — una falla, la otra se guarda igual

```
N3.4: fallo el analisis de 'token': 429 simulado: cuota agotada
contadores: {'requested': 2, 'analyzed': 1, 'failed': 1, 'skipped': 0}   (no lanzo excepcion)
filas persistidas: 2
    token                analisis=NO (fila igualmente guardada)
    Adapter VerifMethod  analisis=si
-> OK
```

La fila de la que falló **se guarda con sus métricas y sin análisis**, así que
el informe puede mostrar la transacción aunque la IA no respondiera, y se sabe
cuál quedó pendiente. El proceso continúa y no lanza.

### 2.4 Caso 4 — sin transacciones marcadas

```
contadores: {'requested': 0, 'analyzed': 0, 'failed': 0, 'skipped': 0}
llamadas a la IA: 0 | filas: 0  -> OK
```

Coste cero: sale antes de pedir el analizador. El upload se comporta
exactamente como antes de N3.4.

### 2.5 Caso 5 — el endpoint de lectura

```
GET /executions/115346ea.../transaction-analyses   HTTP 200
count = 2
  token                critica=True marked_by=user orden=0
      metrics: muestras=8600 promedio=442.6 max=21060.0
  Adapter VerifMethod  critica=True marked_by=user orden=1
      metrics: muestras=8599 promedio=2940.7 max=21058.0

GET (ejecucion sin marcadas) -> {"transaction_analyses":[],"count":0}
```

### 2.6 Datos de prueba limpiados

```
SELECT count(*) FROM transaction_analyses;   ->  2      (antes)
DELETE FROM transaction_analyses WHERE execution_id = '115346ea-...';   ->  DELETE 2
SELECT count(*) FROM transaction_analyses;   ->  0      (despues)
```

**No quedó ni una fila de prueba en tu base.** Y no se gastó una sola llamada de
IA: el stub registró los prompts y devolvió texto fijo.

---

## 3. Detalles que conviene que sepas

1. **`marked_by` sale siempre `'user'`.** El panel de N3.3 manda una lista plana
   de labels, sin decir cuáles venían premarcadas y cuáles añadiste tú. Como la
   lista final es la que confirmas al pulsar Generar Reporte, la registro como
   tuya. Si quieres distinguir «premarcada por el sistema» de «añadida a mano»,
   son ~5 líneas en N3.3 (mandar la lista con su origen) — dime y lo hago.
2. **Tope blando (D4):** el servicio analiza las primeras 10 y **registra el
   resto sin análisis** (cuenta en `skipped`), en vez de descartarlas. No
   bloquea nada; solo protege el tiempo del upload, que hace las llamadas en
   serie.
3. **Se usa `analyzer._generate(...)`**, el mismo método interno que usan las 12
   secciones actuales: trae reintentos, circuit breaker y `sanitize_ai_text`.
   Aun así, el servicio vuelve a aplicar `sanitize_ai_text` sobre el resultado
   para cumplir la regla 14 de forma explícita (es idempotente).
4. **El enganche va después de guardar la ejecución** porque necesita su id, y
   está envuelto en `try`: si algo falla ahí, tu informe ya está guardado.

---

## 4. Lo que falta para cerrar N3

**N3.5 (exports)** ya tiene todo lo que necesita: el endpoint
`GET /executions/{id}/transaction-analyses` devuelve label, métricas y análisis
ordenados por `sort_order`, listo para pintar el bloque «Análisis por
transacción crítica» antes de las conclusiones en las 4 salidas. Recuerda que
toca `report_generator.py`, protegido, con tu autorización D5 ya dada.

**Validación funcional pendiente (tuya):** subir un JTL con transacciones
marcadas y comprobar que se generan los análisis reales. Eso sí consume cuota,
por eso no lo hice yo.
