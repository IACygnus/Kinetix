1046fd9 · 2026-09-17

# ETAPA 5.1 — Diagnóstico del panel de selección (read-only)

**Llamadas reales a la IA: 0.** Ningún archivo tocado.

**No hay parada:** D42 no exige ninguna decisión de producto que no esté ya
cubierta. El detalle está en §5.

---

## 1. Qué hay hoy en «Nuevo Reporte»

Todo vive en `frontend/src/components/dashboard/UploadJTL.tsx` (829 líneas, **no
protegido**). Son **dos bloques distintos** que hablan de lo mismo y no se hablan
entre sí:

| Bloque | Líneas | Qué muestra | De dónde salen sus datos |
|---|---|---|---|
| **«Transacciones del JTL»** (N3.3) | 574-642 | Tabla con checkbox, nombre, marca «critica», motivo y métricas | `POST /extract-jtl-transactions` |
| **«Criterios por Transaccion»** (HF2) | 645-700 | Un `<details>` plegado con tres campos por transacción y un «aplicar a todas» | `detectedLabels`, estado local `transactionCriteria` |

El segundo es el que **D43 hace desaparecer**: sus tres campos se mudan dentro de
la fila desplegable del primero (D40).

### 1.1 Las columnas de hoy contra las que pide §2.1 (D39)

| Hoy | v1.2 §2.1 |
|---|---|
| Transaccion | Transacción |
| Muestras | Muestras |
| Promedio | Promedio |
| **p90** | *(fuera)* |
| **Max** | *(fuera)* |
| — | **TPS** *(falta)* |
| Errores (cantidad y %) | Errores (cantidad y %) |

Sobran `p90` y `Max`; **falta TPS**.

**TPS ya está calculado y no hace falta inventarlo.** `get_summary_table_data`
(`jtl_parser.py:379`) hace `rendimiento = muestras / duración`, donde la duración
es la de **toda la prueba** (`timestamp.max - timestamp.min`, línea 342) — que es
exactamente la definición de D39. El endpoint tiene esa columna en el
`summary_df` y **simplemente no la devuelve**: añadirla es una línea.

### 1.2 El premarcado y la selección

- `is_critical_suggested` lo decide el **backend**.
- `manualSel` guarda **solo lo que Fredy toca**; la selección efectiva es
  `manualSel[label] ?? is_critical_suggested` (línea 168). Ese diseño se conserva
  tal cual: D40 dice que «el checkbox de selección sigue igual».
- Tres botones: «Marcar todas», «Solo criticas» (vuelve a la sugerencia) y
  «Ninguna».

---

## 2. Dónde está la regla de criticidad — y en qué lenguaje

**Solo existe en Python.** No hay una línea de esa lógica en TypeScript.

`POST /extract-jtl-transactions` (`upload.py:129-215`) marca una transacción con
**tres señales**, y basta una:

| Señal | Regla | ¿Depende de los criterios? |
|---|---|---|
| **(a) Veredicto** | `compute_per_transaction_verdicts` devuelve `NO APTO` o `APTO CON RESERVAS` | **Sí** |
| **(b) Pico relativo** | `max >= 10 × promedio` | No |
| **(c) Pico absoluto** | `max >= 10000 ms` | No |

Y el veredicto (KNX-09, `gemini.py:441-485`) es:

```python
rt_threshold = per_transaction[label].response_time  o  global response_time
er_threshold = 100 - (per_transaction[label].availability  o  global availability)

rt_fail    = p90 > rt_threshold
er_fail    = tasa_error > er_threshold
rt_warning = p90 > rt_threshold * 0.8  y  no rt_fail

NO APTO            si rt_fail o er_fail
APTO CON RESERVAS  si rt_warning
APTO               en el resto
```

**Dos métricas y solo dos: `p90` y `tasa_error`.** La **concurrencia no
interviene** en el veredicto por transacción, aunque el formulario la pida y se
guarde.

### 2.1 Cómo se recalcula hoy

Cambiar los criterios **globales** dispara un `useEffect` con 800 ms de debounce
(`UploadJTL.tsx:158-168`) que **vuelve a subir el JTL entero** al endpoint para
que el backend recalcule. El comentario lo justifica: «así el umbral de
criticidad tiene una sola fuente de verdad».

Eso **no sirve para D42**: con criterios por fila, cada tecla obligaría a
resubir el archivo. De ahí que D42 mande portar la regla a TS con pruebas de
paridad — y es el caso «solo existe en el backend».

---

## 3. Qué se envía y quién lo consume

El payload no cambia (D44). `uploadFiles` (`UploadJTL.tsx:265-296`) arma:

```json
{
  "concurrency": 100, "response_time": 2000, "availability": 99.5,
  "per_transaction": {
    "<label>": { "concurrency": 100, "response_time": 2000,
                 "availability": 99.5, "error_rate": 0.5 }
  },
  "critical_transactions": ["<label>", ...]
}
```

Recorrido completo de `per_transaction`:

| Paso | Dónde |
|---|---|
| Se arma en el navegador | `UploadJTL.tsx:271-284` |
| Viaja como `acceptance_criteria` (JSON en un campo de texto) | `uploadJTL` |
| Se guarda en `test_executions.acceptance_criteria_json` | `/upload` |
| Lo lee el veredicto por transacción | `gemini.py:453` |
| Se recalcula y se guarda con el informe | `analysis_pipeline.py:412-415` |
| **Se pinta en la tabla KNX-09 del informe** | `Dashboard.tsx:654-674` |

Esa tabla del informe lee `verdicts_per_transaction` y, para mostrar el umbral,
`per_transaction[txn].response_time` con el global de reserva. **Es la tabla
contra la que 5.3 comparará lo que calculó el panel**, y no hay que tocarla.

Dos detalles del payload actual que conviene saber:

- `error_rate: 0.5` se escribe **fijo** y **nadie lo lee**: el veredicto deriva
  el umbral de error de `100 - availability`. Se conserva por compatibilidad
  (D44), no porque sirva.
- Una fila solo entra en `per_transaction` si tiene **algún** campo con valor; y
  al entrar, los tres campos se rellenan con el global. Es justo el
  comportamiento que D41 pide describir en la interfaz: *sin criterios propios,
  se evalúan los globales*.

---

## 4. El texto bajo el nombre (D45)

Lo construye el backend (`upload.py:179-186`) y hoy sale así:

```
no apto por criterios (p90 175ms, 64.79% error) · pico de 21060ms, 47x el promedio
```

Tiene los cuatro problemas que la Etapa 3 ya arregló en los textos de IA: jerga
(`p90` suelto), formato inglés (`175ms`, `64.79%`, `47x`), sin tildes y con el
veredicto crudo. D45 lo reescribe; los helpers de `estilo.py` (`ms`, `pct`,
`veces`, `percentil_frase`) ya existen y hacen exactamente eso.

---

## 5. Por qué no hay parada

D42 dice «una sola métrica por criterio: la que usa hoy el backend (no se cambia
la regla)». Comprobado contra el código:

| Criterio | Métrica que usa el backend | ¿Cambia algo? |
|---|---|---|
| Tiempo de respuesta | `p90` | No |
| Disponibilidad | `tasa_error` contra `100 - availability` | No |
| **Concurrencia** | **ninguna** | No. Se sigue pidiendo y guardando (D40, D44), y sigue sin afectar la criticidad |

Que la concurrencia sea editable pero no mueva la marca «crítica» podría
parecer una decisión de producto pendiente. **No lo es**: D42 prohíbe cambiar la
regla y D40 manda mostrar los tres campos. Se implementa así y se dice en la
interfaz, para que nadie espere que al tocar la concurrencia cambie algo.

---

## 6. Plan de 5.2, con lo que cuesta

| Archivo | Qué | Protegido |
|---|---|---|
| `backend/app/api/v1/endpoints/upload.py` | Devolver `tps`; reescribir el `motivo` con los helpers de `estilo.py` (D45) | No |
| `frontend/src/utils/criticidad.ts` *(nuevo)* | El puerto en TS de la regla, puro y sin React (D42) | — |
| `frontend/src/services/api.ts` | `tps` en `TransactionMetrics` | No |
| `frontend/src/components/dashboard/UploadJTL.tsx` | Columnas D39, fila desplegable D40/D41, fuera el bloque D43, tildes D45 | No |
| `backend/tests/test_criticidad_paridad.py` *(nuevo)* | Los casos, en Python | — |
| `frontend/src/utils/criticidad.paridad.ts` *(nuevo)* | Los mismos casos, en TS | — |

**Ningún archivo protegido.** `Dashboard.tsx` no entra: la tabla KNX-09 del
informe ya lee lo que el panel enviará.

Siguiente: 5.2, la implementación.
