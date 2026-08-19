# N4.5 — Tabla y modelo `transaction_chart_analyses`

**Fecha:** 2026-08-19
**Commit:** `18794018a5da3f980e254e0518c5bb3a67efec68` — *N4.5: tabla transaction_chart_analyses*
**Push:** `github` (`28b43fe..1879401`, rama `backup-trabajo-local`). **`origin` (Azure) no se tocó.**
**Llamadas de IA:** **0.**
**Archivos tocados:** **2** — 1 nuevo (81 líneas) + 1 línea en `main.py`.
**ALTER TABLE:** **ninguno.** La tabla la creó `Base.metadata.create_all` sola al reiniciar.

---

## 1. Qué se hizo

| Archivo | Cambio |
|---|---|
| `backend/app/db/models/transaction_chart_analysis.py` | **Nuevo.** 81 líneas: modelo `TransactionChartAnalysis` + tupla `SECTIONS` |
| `backend/app/main.py` | **+1 línea**: import del modelo junto al de N3.4 (línea 28), antes de `create_tables()` |

```diff
 from app.db.models.transaction_analysis import TransactionAnalysis   # N3.4
+from app.db.models.transaction_chart_analysis import TransactionChartAnalysis   # N4.5
```

`backend/app/db/models/__init__.py` **no se tocó**, igual que en N3.4: ese
`__init__` tampoco exporta `TransactionAnalysis`. El registro en el metadata lo
da el import de `main.py`.

**Backup previo:** `backend/app/main.py.bak_n45_20260819_*` (queda fuera de git
por `.gitignore`).

---

## 2. Estructura de la tabla

```
transaction_chart_analyses
  id                     UUID   PK
  execution_id           UUID   NOT NULL  FK -> test_executions(id) ON DELETE CASCADE, index
  label                  VARCHAR(500) NOT NULL
  section                VARCHAR(40)  NOT NULL     -- discriminador, 8 valores
  ai_analysis            TEXT
  generated_at           TIMESTAMP                 -- cuando lo produjo la IA
  is_edited              BOOLEAN NOT NULL          -- patron 'edited' del consolidado
  ai_analysis_updated_at TIMESTAMP                 -- cuando lo toco el usuario
  sort_order             INTEGER
  created_at             TIMESTAMP

  UNIQUE  (execution_id, label, section)   uq_txchart_execution_label_section
  INDEX   (execution_id, label)            ix_txchart_execution_label
  INDEX   (execution_id)                   ix_transaction_chart_analyses_execution_id
```

### 2.1 El discriminador `section` — las 8 secciones

No es una lista escrita a mano. Las 5 del medio se **derivan** de `CHART_TYPES`
de `transaction_series.py` (N4.3), para que el discriminador no pueda
desalinearse de las series que el servicio realmente calcula:

```python
SECTIONS = ("summary",) + tuple(f"chart_{c}" for c in CHART_TYPES) + ("conclusions", "recommendations")
```

Verificado contra el contenedor:

```
$ docker exec jmeter_backend python -c "from app.db.models.transaction_chart_analysis import SECTIONS; print(len(SECTIONS)); print(SECTIONS)"
8
('summary', 'chart_response_times', 'chart_latency', 'chart_error_rate',
 'chart_codes', 'chart_tps', 'conclusions', 'recommendations')
```

Dos desvíos deliberados respecto al borrador del reporte 036 §4.2, ambos a favor
de la legibilidad que pediste:

1. **Prefijo `chart_`** en las 5 gráficas. El borrador proponía `latency` a
   secas; `chart_latency` deja claro que es el texto *de una gráfica* y coincide
   con los nombres que ya usa el análisis global (`chart_latency`,
   `chart_error_rate`…). Un `summary` y un `latency` sueltos, uno al lado del
   otro en la misma columna, no dicen a qué nivel viven.
2. **`VARCHAR(40)` con la lista cerrada en Python, no un `ENUM` de Postgres.** Un
   ENUM se ve más estricto, pero añadir una sección novena exigiría `ALTER TYPE`
   — la regla 10 lo prohíbe igual que un `ALTER TABLE`. La tupla `SECTIONS` da la
   lista cerrada sin hipotecar el esquema.

### 2.2 Por qué UNIQUE `(execution_id, label, section)`

Un texto por (ejecución, transacción, sección). Hace el guardado idempotente
—regenerar el mini-informe es un `UPDATE`, no una fila nueva— y bloquea el
duplicado si dos peticiones se cruzan. El índice `(execution_id, label)` cubre la
lectura real: *dame las 8 secciones de esta transacción*.

---

## 3. Decisión documentada: relación con `transaction_analyses` (N3.4)

**La nueva tabla COMPLEMENTA a `transaction_analyses`. No la reemplaza.**
El reparto queda así:

| Tabla | Qué guarda | Quién la escribe |
|---|---|---|
| `transaction_analyses` (N3.4) | **Qué transacciones se marcaron**: `is_critical`, `marked_by` ('ai'/'user'), `sort_order`, y la foto de métricas con la que se marcaron (`metrics_json`) | El premarcado determinista |
| `transaction_chart_analyses` (N4.5) | **Los textos** del mini-informe de esas transacciones: 8 filas por transacción | La generación IA bajo demanda (N4.6) |

**Por qué así y no fusionarlas.** Las dos tablas tienen ciclos de vida
distintos: la marca existe desde el upload y no cuesta nada; los textos cuestan
~94 s de IA por transacción (036 §5.2) y puede que nunca se generen. Meterlos en
la misma fila obliga a que una tabla de registro barato cargue con columnas que
casi siempre estarán vacías, y a que regenerar un texto toque la fila del
marcado.

**Cómo deja el camino de N4.6 (sacar el análisis de N3.4 del upload).** Limpio,
sin migración:

- El premarcado sigue creando la fila en `transaction_analyses` durante el
  upload, con `ai_analysis` en `NULL`. La tabla conserva su función: es el
  registro de qué transacciones son críticas, que es lo que la UI necesita para
  ofrecer el botón "generar mini-informe".
- El texto que hoy vive en `transaction_analyses.ai_analysis` pasa a ser la
  sección **`summary`** de la tabla nueva, generada bajo demanda.
- `transaction_analyses.ai_analysis` queda como columna **legacy** de las
  ejecuciones ya analizadas: se sigue leyendo para no romper el bloque N3.5 de
  los reportes viejos, y deja de escribirse. **No hay que borrar ni migrar
  nada** — y borrarla sería un `ALTER TABLE`, prohibido.

Es decir: N4.6 solo tiene que *dejar de escribir* en un sitio y *empezar a
escribir* en otro. No hay estado intermedio inconsistente.

---

## 4. Validación

### 4.1 `py_compile` y arranque

```
$ python -m py_compile app/db/models/transaction_chart_analysis.py app/main.py
PY_COMPILE OK
$ docker restart jmeter_backend        # restart, SIN build
INFO:app.main:Tablas de base de datos verificadas/creadas
INFO:app.main:Aplicacion lista
INFO:     Application startup complete.
```

Cero errores y cero trazas en el arranque.

### 4.2 `\d` de la tabla creada

```
                       Table "public.transaction_chart_analyses"
         Column         |            Type             | Nullable
------------------------+-----------------------------+----------
 id                     | uuid                        | not null
 execution_id           | uuid                        | not null
 label                  | character varying(500)      | not null
 section                | character varying(40)       | not null
 ai_analysis            | text                        |
 generated_at           | timestamp without time zone |
 is_edited              | boolean                     | not null
 ai_analysis_updated_at | timestamp without time zone |
 sort_order             | integer                     |
 created_at             | timestamp without time zone |
Indexes:
    "transaction_chart_analyses_pkey" PRIMARY KEY, btree (id)
    "ix_transaction_chart_analyses_execution_id" btree (execution_id)
    "ix_txchart_execution_label" btree (execution_id, label)
    "uq_txchart_execution_label_section" UNIQUE CONSTRAINT, btree (execution_id, label, section)
Foreign-key constraints:
    "transaction_chart_analyses_execution_id_fkey" FOREIGN KEY (execution_id)
        REFERENCES test_executions(id) ON DELETE CASCADE
```

Los cuatro requisitos están: **unique**, **index compuesto**, **index de FK**,
**FK con CASCADE**.

### 4.3 INSERT de varias secciones para la misma transacción

Ejecución de prueba `1111…1111` + 2 transacciones × 8 secciones:

```
INSERT 0 1     <- test_executions
INSERT 0 16    <- transaction_chart_analyses

        paso         | total | transacciones | secciones
---------------------+-------+---------------+-----------
 1) filas insertadas |    16 |             2 |         8
```

### 4.4 Recuperar las 8 secciones de UNA transacción, por separado

```
       section        | sort_order |              texto               | is_edited
----------------------+------------+----------------------------------+-----------
 summary              |          0 | texto IA de summary / Login      | f
 chart_response_times |          1 | texto IA de chart_response_times | f
 chart_latency        |          2 | texto IA de chart_latency / Logi | f
 chart_error_rate     |          3 | texto IA de chart_error_rate / L | f
 chart_codes          |          4 | texto IA de chart_codes / Login  | f
 chart_tps            |          5 | texto IA de chart_tps / Login    | f
 conclusions          |          6 | texto IA de conclusions / Login  | f
 recommendations      |          7 | texto IA de recommendations / Lo | f
(8 rows)
```

### 4.5 Editar UNA sección sin tocar las otras 15

```sql
UPDATE transaction_chart_analyses
   SET ai_analysis='TEXTO EDITADO POR EL USUARIO', is_edited=true, ai_analysis_updated_at=now()
 WHERE execution_id='1111…' AND label='Login' AND section='chart_latency';
-- UPDATE 1
```

Estado después — **una sola fila cambió**:

```
     label      |    section     |            texto             | is_edited | tiene_fecha_edicion
----------------+----------------+------------------------------+-----------+---------------------
 Login          | chart_latency  | TEXTO EDITADO POR EL USUARIO | t         | t
 …las otras 15  | …              | texto IA de …                | f         | f

 editadas | intactas | total
----------+----------+-------
        1 |       15 |    16
```

Esto es exactamente lo que `metrics_json` habría impedido: ahí, editar un texto
obliga a reescribir el JSON entero con los otros siete dentro.

### 4.6 El UNIQUE rechaza el duplicado

```
ERROR:  duplicate key value violates unique constraint "uq_txchart_execution_label_section"
DETAIL:  Key (execution_id, label, section)=(1111…, Login, chart_latency) already exists.
```

### 4.7 Borrado en cascada + limpieza con contadores

```
=== antes del borrado ===
 ejecuciones_prueba | filas_txchart
--------------------+---------------
                  1 |            16

=== DELETE FROM test_executions WHERE id='1111…'  → DELETE 1 ===
   (no se tocó la tabla hija)

=== después ===
 ejecuciones_prueba | filas_txchart
--------------------+---------------
                  0 |             0
```

**16 → 0 sin borrar nada a mano.** La base queda como estaba: cero filas de
prueba, cero ejecuciones de prueba.

### 4.8 Las tablas existentes NO cambiaron

Snapshot de `information_schema.columns` antes y después del restart:

```
columnas antes: 235 | después: 245
--- diff ---
220a221,230
> transaction_chart_analyses|id|uuid
> transaction_chart_analyses|execution_id|uuid
> transaction_chart_analyses|label|character varying
> transaction_chart_analyses|section|character varying
> transaction_chart_analyses|ai_analysis|text
> transaction_chart_analyses|generated_at|timestamp without time zone
> transaction_chart_analyses|is_edited|boolean
> transaction_chart_analyses|ai_analysis_updated_at|timestamp without time zone
> transaction_chart_analyses|sort_order|integer
> transaction_chart_analyses|created_at|timestamp without time zone
```

**El diff es puramente aditivo: 10 líneas, todas de la tabla nueva.** Ni una
columna alterada, movida ni eliminada en las 17 tablas anteriores. Tablas:
**17 → 18**.

`transaction_analyses` verificada intacta: mismas 10 columnas, mismos 2 índices,
misma FK.

---

## 5. Estado del plan N4 (036 §6)

| # | Sub-sprint | Estado |
|---|---|---|
| N4.2 | Diagnóstico read-only del dato | ✅ cerrado — reporte 036, commit `d96c398` |
| N4.3 | Servicio `transaction_series.py` (5 series por label) | ✅ cerrado — reporte 037, commit `5168a48` |
| N4.4 | Endpoint `GET /executions/{id}/transaction-charts?label=` | ✅ cerrado — reporte 038, commit `c7f389f` |
| **N4.5** | **Modelo + tabla `transaction_chart_analyses`** | ✅ **cerrado — este reporte, commit `1879401`** |
| N4.4b | Servir varias transacciones de una / cache | ⏸️ **aprobado, plegado a N4.7** por decisión del CTO |
| N4.6 | Generación IA bajo demanda: 8 prompts/transacción, `sanitize_ai_text`, persistencia en esta tabla, contadores. Saca el análisis de N3.4 del upload | ⏭️ **siguiente** |
| N4.7 | Pantalla `TransactionReportSection.tsx` + botón. Absorbe N4.4b | ⏳ pendiente — ⚠️ el montaje puede tocar `Dashboard.tsx` (protegido) |
| N4.8 | Export PDF con las 5 gráficas y los textos | ⏳ pendiente — 🔴 `report_generator.py` protegido, `export_pdf.py` bajo regla de memoria |
| N4.9 | Export HTML standalone e informe integrado | ⏳ pendiente — 🔴 `export_html.py` bajo la misma regla |

**Backend del mini-informe: 3 de 4 piezas listas** (series → endpoint → tabla).
Falta N4.6 para que haya texto que guardar.

---

## 6. Lo que este sprint NO hizo

- **No se escribió ni un endpoint.** La tabla existe y está probada por SQL, pero
  todavía no hay ninguna ruta que inserte ni lea de ella. Eso es N4.6.
- **No se tocó `transaction_analyses`** — ni el modelo, ni la tabla, ni el código
  que la escribe hoy en el upload. La decisión del §3 describe lo que hará N4.6,
  no algo ya aplicado.
- **No se validó con datos reales de IA.** Los 16 textos de la prueba eran
  cadenas sintéticas; cero llamadas al proveedor.
- **No hay validación de `section` en la base.** La lista cerrada vive en la
  tupla `SECTIONS` de Python (§2.1): la columna aceptaría cualquier string de 40
  caracteres si alguien inserta por SQL directo. Es el precio consciente de no
  usar un ENUM que después exigiría `ALTER TYPE`.

---

## 7. Cierre

```
$ git log -1 --format='%H %s'
18794018a5da3f980e254e0518c5bb3a67efec68 N4.5: tabla transaction_chart_analyses

$ git push github HEAD
   28b43fe..1879401  HEAD -> backup-trabajo-local
```

**Parado aquí. N4.6 no se encadenó.**
