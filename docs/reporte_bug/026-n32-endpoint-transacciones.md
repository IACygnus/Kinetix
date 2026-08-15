# N3.2 — Endpoint de transacciones con métricas y criticidad sugerida

**Fecha:** 2026-08-15
**Commit:** `671aa23` — *N3.2: endpoint de transacciones con metricas y
criticidad sugerida*
**Push:** `github/backup-trabajo-local` (`748c262..671aa23`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO Y VALIDADO CONTRA JTL REALES DEL SISTEMA.**

**Presupuesto:** ~60-90 líneas, máx 2 archivos → **94 insertadas / 2 borradas,
1 archivo** (`upload.py`). No hizo falta schema nuevo: la respuesta es un dict
plano y el endpoint no persiste nada.

Decisiones aplicadas: **D3** (premarcado determinista + señal de timeout) ·
**D6** (`/extract-jtl-labels` intacto, conviven) · **D7** (XML arreglado).

---

## 1. Qué se añadió

`POST /api/v1/extract-jtl-transactions` — `backend/app/api/v1/endpoints/upload.py:112-198`.

**Entrada:** `files` (multipart, igual que el endpoint viejo) y, opcionales,
`response_time` y `availability` como campos de formulario.

**Salida:**

```json
{
  "transactions": [
    {"label": "token", "muestras": 8600, "promedio": 442.6, "p90": 529.1,
     "p95": 561.0, "max": 21060.0, "errores": 23, "tasa_error": 0.2674,
     "verdict": "APTO", "is_critical_suggested": true,
     "motivo": "pico de 21060ms, 48x el promedio · pico absoluto de 21060ms (>=10s, posible timeout)"}
  ],
  "count": 3, "critical_count": 2, "criteria_applied": true
}
```

Las transacciones vienen **ordenadas con las críticas primero** y, dentro de
cada grupo, por `max` descendente: lo que Fredy tiene que mirar queda arriba.

### 1.1 Las tres señales de criticidad

| Señal | Regla | Requiere criterios |
|---|---|---|
| **(a)** veredicto KNX-09 | `NO APTO` o `APTO CON RESERVAS` (p90 vs tiempo, tasa de error vs disponibilidad) | sí — sin criterios se omite |
| **(b)** pico relativo | `max >= 10 × promedio` | no |
| **(c)** pico absoluto | `max >= 10000 ms` | no |

Cualquiera de las tres marca, y el `motivo` dice cuál disparó (se acumulan los
motivos si coinciden varias).

La lógica de (a) **se importa, no se copia**:

```python
from app.services.ai.gemini import (..., compute_per_transaction_verdicts)   # N3.2
...
verdicts = compute_per_transaction_verdicts(summary_df, criteria).get(
    'verdicts_per_transaction', {}) if criteria else {}
```

`gemini.py` y `jtl_parser.py` **no se tocaron**. El parser se usa en lectura:
`JTLParser(path).parse()` + `get_summary_table_data()`.

---

## 2. Validación con JTL reales del sistema

### 2.1 Caso 1 — CSV de Coomeva (25.773 muestras) CON criterios (2500 ms / 99 %)

```
HTTP 200 | tiempo total 0.271s
count= 3 | critical_count= 2 | criteria_applied= True

  CRITICA | token                  n= 8600 avg=   442.6 p90=  529.1 max= 21060.0 err= 23 (0.267%) verdict=APTO
          motivo: pico de 21060ms, 48x el promedio · pico absoluto de 21060ms (>=10s, posible timeout)
  CRITICA | Adapter VerifMethod    n= 8599 avg=  2940.7 p90= 3515.2 max= 21058.0 err= 54 (0.628%) verdict=NO APTO
          motivo: no apto por criterios (p90 3515ms, 0.63% error) · pico absoluto de 21058ms (>=10s, posible timeout)
     ok   | Adapter SendCode       n= 8574 avg=   139.1 p90=  149.0 max=   388.0 err= 23 (0.268%) verdict=APTO
```

**El caso que pediste verificar explícitamente:** `token` tiene
**`verdict = APTO`** — pasa el criterio de p90 (529 ms contra 2500) y el de
error (0,267 % contra 1 %). Con la señal (a) sola **se habría escapado**. Sale
marcada como crítica por las señales (b) y (c), con el motivo diciendo
exactamente por qué: *pico de 21060ms, 48x el promedio*. Es la lección de GRAF1
funcionando.

### 2.2 Las métricas cuadran con lo que ya está guardado

Contraste contra `test_executions` de esa misma ejecución (`115346ea`):

| Dato | Endpoint nuevo | Guardado en la ejecución | |
|---|---|---|---|
| Suma de muestras | 8600 + 8599 + 8574 = **25.773** | `total_requests` = **25.773** | ✔ |
| Promedio ponderado | **1.175,11 ms** | `avg_response_time` = **1.175,07 ms** | ✔ |
| Máximo | **21.060 ms** (token) | `max_response_time` = **21.060 ms** | ✔ |

(La diferencia de 0,04 ms en el promedio es el redondeo a 2 decimales que
aplica el endpoint antes de sumar.)

### 2.3 Caso 2 — JTL en XML: antes y después

Mismo archivo real de 73 MB, los dos endpoints, uno detrás del otro:

```
== endpoint VIEJO /extract-jtl-labels ==
{"labels":[],"error":"No se encontro columna 'label' en el archivo"}
HTTP 200 | 1.078s

== endpoint NUEVO /extract-jtl-transactions ==
HTTP 200 | 1.500s
count= 6 | critical_count= 6
  CRITICA | 1. Url                  n=  558 avg= 1243.7 max= 15476.0 err=   0 verdict=NO APTO
  CRITICA | 2. Login                n=  555 avg= 3532.7 max= 11535.0 err=   0 verdict=NO APTO
  CRITICA | 3. My_Info              n=  547 avg= 1735.7 max=  5760.0 err=   0 verdict=NO APTO
  CRITICA | 6. Salir                n=  545 avg= 1360.6 max=  4780.0 err=   0 verdict=NO APTO
  CRITICA | 5. My_Info_Dashboard    n=  546 avg=  875.4 max=  3167.0 err=   0 verdict=NO APTO
  CRITICA | 4. My_Info_Save         n=  546 avg=  776.1 max=  2574.0 err=   0 verdict=APTO CON RESERVAS
```

Donde antes salía una lista vacía, ahora salen las 6 transacciones con sus
métricas. **Un JTL XML de 73 MB se procesa en 1,5 s.**

> Observación para N3.3: esta ejecución es una prueba de estrés donde **las 6
> transacciones** disparan la señal (a). Es justo el escenario en el que el tope
> blando de 10 con aviso (D4) tiene sentido; aquí no se supera, pero con 20-30
> transacciones sí se superaría y el panel debe avisar en vez de mandar 30
> análisis a la IA.

### 2.4 Caso 3 — Sin criterios

```
HTTP 200
count= 3 | critical_count= 2 | criteria_applied= False

  CRITICA | token                max= 21060.0 verdict=None | pico de 21060ms, 48x el promedio · pico absoluto de 21060ms (>=10s, posible timeout)
  CRITICA | Adapter VerifMethod   max= 21058.0 verdict=None | pico absoluto de 21058ms (>=10s, posible timeout)
     ok   | Adapter SendCode      max=   388.0 verdict=None | -
```

Responde 200, `verdict` viene `None` (la señal (a) se omite, como se
especificó) y marca solo por las señales de pico. Nótese que
`Adapter VerifMethod`, que con criterios salía crítica también por (a), aquí
solo conserva el motivo del pico absoluto: el motivo refleja lo que realmente
se evaluó, no se inventa.

### 2.5 Caso 4 — Tiempo de respuesta

CSV de 25.773 muestras (4,6 MB), 5 corridas incluyendo la subida del archivo:

```
  corrida 1: 0.353s
  corrida 2: 0.363s
  corrida 3: 0.230s
  corrida 4: 0.476s
  corrida 5: 0.297s
```

**Mediana 0,35 s**, muy por debajo del <1 s previsto en N3.1. El XML de 73 MB
tarda 1,5 s, dominado por el parseo, no por el cálculo.

---

## 3. Archivo tocado

| Archivo | Qué | Backup |
|---|---|---|
| `backend/app/api/v1/endpoints/upload.py` | endpoint nuevo + 2 líneas de import (`Form`, `compute_per_transaction_verdicts`) | `.bak_n32_20260815_132410` |

`py_compile` limpio · backend reiniciado **sin build** · `/extract-jtl-labels`
sin un solo cambio (verificado en el diff: solo se le añadió código **encima**).

---

## 4. Nota para N3.3

El endpoint ya entrega `is_critical_suggested`, `motivo`, `verdict` y el orden
de presentación resuelto, así que el panel puede pintarse casi directamente:
una fila por transacción, el check premarcado con `is_critical_suggested` y el
`motivo` como texto de apoyo bajo el nombre. El tope blando de 10 (D4) se
aplica en el panel, no aquí: el endpoint informa `critical_count` para que la
UI pueda avisar.

**Criterio de éxito: tu validación.** Lo de arriba es verificación funcional
contra datos reales.
