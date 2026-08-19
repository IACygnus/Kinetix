# N4.4 — Endpoint de series por transacción bajo demanda

**Fecha:** 2026-08-18
**Commit:** `c7f389f` — *N4.4: endpoint de series por transaccion bajo demanda*
**Push:** `github/backup-trabajo-local` (`9da769f..c7f389f`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO Y VALIDADO POR CURL CONTRA DATOS REALES.** Las 5
validaciones pedidas pasan.
**Llamadas de IA:** **0.**

**Presupuesto:** ~70-90 líneas, máx 2 archivos → **77 insertadas, 0 borradas,
1 archivo** (`backend/app/api/v1/endpoints/upload.py`).
**Backup:** `upload.py.bak_n44_20260818_200334`.

---

## 1. El endpoint

```
GET /api/v1/executions/{execution_id}/transaction-charts?label=<nombre>
                                                        [&interval_seconds=1..60]
```

Devuelve las 5 series de UNA transacción, tal cual las produce el servicio de
N4.3, más los metadatos:

```json
{
  "label": "token",
  "interval_seconds": 1,
  "sample_count": 8600,
  "response_times": [{"timestamp": "...", "value": 360.0, "value_max": 360.0}, ...],
  "latency":        [{"timestamp": "...", "value": 360.0}, ...],
  "error_rate":     [{"timestamp": "...", "value": 0.0}, ...],
  "codes":          [{"timestamp": "...", "value": 1.0, "code": "200"}, ...],
  "tps":            [{"timestamp": "...", "value": 1.0}, ...],
  "warnings": [],
  "elapsed_ms": 1470
}
```

`warnings` viaja siempre, también vacío: es donde llegan los avisos de columna
ausente (WAPT/Locust sin `Latency`) para que la UI pueda decir por qué falta una
gráfica en vez de pintarla en blanco. `elapsed_ms` es el tiempo de servidor
—parseo + cálculo— y sirve para el indicador de progreso de N4.7.

### 1.1 Mapa de errores a HTTP

| Situación | Código | Mensaje |
|---|---|---|
| ID que no es UUID | **400** | `ID de ejecucion invalido: 'no-es-uuid'` |
| Ejecución inexistente | **404** | `Ejecucion no encontrada` |
| Sin acceso al cliente (no admin) | **403** | `_check_execution_access`, mismo patrón que `GET /executions/{id}` |
| JTL ausente del disco | **404** | `No se encuentra el JTL de esta ejecucion (…). Las series por transaccion se calculan desde el archivo original.` |
| JTL ilegible / corrupto | **400** | `No se pudo parsear el JTL de esta ejecucion: …` |
| JTL sin muestras utilizables | **400** | `El JTL de esta ejecucion no tiene muestras utilizables` |
| Label inexistente | **404** | `La transaccion 'X' no existe en este JTL. Transacciones disponibles: …` |
| Falta el parámetro `label` | **422** | validación de FastAPI |
| `interval_seconds` fuera de 1-60 | **422** | validación de FastAPI |
| Sin autenticación | **401** | cookie httpOnly, igual que el resto |

**Ninguna ruta devuelve series vacías en silencio.** El 404 de label
inexistente además **lista las transacciones disponibles**: quien se equivoque
de nombre ve inmediatamente los válidos.

### 1.2 `/charts` no se tocó

Confirmado por dos vías, no por declaración:

- El diff son 77 líneas **insertadas y cero borradas**: el import del servicio
  N4.3 y el bloque del endpoint nuevo, colocado antes de `/charts`.
- El código de la función `/charts` es **byte-idéntico** al del backup:
  `sha256 = bf3f7104aed7bfdf…`, 8.742 caracteres en ambos archivos.

Esto obligó a repetir ~12 líneas de búsqueda del JTL en disco en vez de extraer
un helper compartido. Es deliberado: refactorizar esa parte habría significado
tocar `/charts`, que era exactamente lo prohibido.

---

## 2. Validación por curl con datos reales

Ejecución `115346ea` — *24342-Coomeva_SendCode_Performance*, 25.773 muestras.
Autenticación real: `POST /auth/login` con cookie httpOnly.

### 2.1 Las 5 series de `token` → 200

```
HTTP 200 | total 3,54 s | 475.543 bytes
label=token | interval=1s | muestras=8600 | warnings=[] | elapsed_ms=3048
  response_times   1666 puntos
  latency          1666 puntos
  error_rate       1666 puntos
  codes            1689 puntos
  tps              1666 puntos
```

**`max(response_times.value_max) = 21060.0`** — exactamente el máximo crudo del
JTL para `token`, el mismo valor que guarda `max_response_time` en la base y el
mismo que devuelve `/charts`. **GRAF1 sobrevive de punta a punta:** el pico llega
al endpoint nuevo sin suavizarse.

### 2.2 Errores

```
label=NoExiste  -> 404 {"detail":"La transaccion 'NoExiste' no existe en este JTL.
                         Transacciones disponibles: token, Adapter VerifMethod, Adapter SendCode"}
sin label       -> 422
id no-uuid      -> 400 {"detail":"ID de ejecucion invalido: 'no-es-uuid'"}
sin cookie      -> 401
ejecucion inexistente -> 404 {"detail":"Ejecucion no encontrada"}
JTL ausente     -> 404 {"detail":"No se encuentra el JTL de esta ejecucion
                         (archivo_que_no_existe_n44.jtl). Las series por transaccion
                         se calculan desde el archivo original."}
```

**Ningún traceback en ninguna de las seis rutas.**

Para el caso del JTL ausente no había ninguna ejecución real sin archivo —se
verificaron las 50 filas de `test_executions` y todas tienen el suyo—, así que
se insertó una fila de prueba apuntando a un archivo inexistente, se llamó al
endpoint y **se borró** (`DELETE 1`, verificado con `count = 0`). La tabla
volvió a sus 50 filas.

### 2.3 `interval_seconds`

```
interval_seconds=3  -> 200 | 600 puntos (contra 1.666 a 1 s) | 188.549 bytes | max sigue en 21060
interval_seconds=0  -> 422 (fuera del rango 1-60)
```

El máximo se conserva al bajar resolución porque la agregación es `max`, no
`mean`; lo que se pierde es la ubicación exacta del pico en el tiempo.

### 2.4 `/charts` sigue igual

```
GET /executions/115346ea/charts -> HTTP 200 | 2,96 s | 1.095.692 bytes
  response_times_by_label  4977 elementos
  tps_by_label             1795 elementos
  codes_per_second          676 elementos
  timeline                  600 elementos
  MAX value_max = 21060.0
```

Los cuatro conteos coinciden **exactamente** con los que medí en el diagnóstico
036 §3.1 antes de existir N4.3 y N4.4 (4.977 / 1.795 / 676 / 600). Sin
regresión, y el código además es byte-idéntico (§1.2).

### 2.5 Arranque limpio

```
python -m py_compile backend/app/api/v1/endpoints/upload.py -> OK
docker restart jmeter_backend                               -> Up (healthy), sin build
GET /health                                                 -> 200
```

---

## 3. La medición que no salió como yo dije

**Mi estimación en el reporte 037 fue ~0,55 s por petición. La realidad medida
es 1,74-3,54 s.** Lo declaro antes de justificarlo.

Medidas de esta sesión, mismo endpoint, misma transacción:

| Llamada | Total punta a punta | `elapsed_ms` de servidor |
|---|---|---|
| 1ª (fría) | 3,54 s | 3.048 ms |
| 2ª | 1,78 s | 1.470 ms |
| 3ª | 1,74 s | 1.462 ms |
| 4ª | 2,36 s | 2.149 ms |

### 3.1 Dónde se va el tiempo

| Etapa | Tiempo |
|---|---|
| `glob` sobre `/app/uploads` (186 entradas) | **1 ms** |
| `JTLParser.parse()` | **362 ms** |
| `build_transaction_series()` | **1.070-1.800 ms** |
| serialización JSON | **31 ms** |

Y dentro de `build_transaction_series`, perfilado aparte:

| Operación | Tiempo |
|---|---|
| Los 5 `groupby` de pandas, juntos | **76 ms** |
| Armar **una** serie con `iterrows()` (1.666 puntos) | **151 ms** |
| Armar **la misma** serie con `zip()` sobre columnas | **11 ms** — **14× más rápido**, salida verificada idéntica |

**El cuello de botella no es pandas ni el disco: es `iterrows()`.** Cinco series
× ~150 ms ≈ 750 ms solo en construir diccionarios, y el resto es varianza de
carga del host (la misma llamada repetida da 1.114 / 1.607 / 2.676 ms, con
Docker Desktop compartiendo CPU). El 341 ms que medí en N4.3 fue con la máquina
descargada; el número honesto es el rango, no el mejor caso.

### 3.2 Qué hacer con esto

Cambiar `iterrows()` por `zip()` sobre arrays en `transaction_series.py` bajaría
la construcción de ~800-1.400 ms a **~130 ms**, y la respuesta del endpoint a
**~0,5 s** — que es justo lo que había estimado. Son ~5 líneas por serie, con
salida byte-idéntica (verificado: `a == b` en el perfilado).

**No lo hice en N4.4** porque la tarea era el endpoint y la regla del sprint es
un sub-sprint por prompt: optimizar el módulo de N4.3 dentro de N4.4 sería
ampliar alcance por mi cuenta. **Queda propuesto como N4.4b** (~20 líneas, 1
archivo, sin IA) — tú decides si entra antes de N4.5, si se pliega a N4.7 cuando
la UI cargue 5 gráficas de golpe, o si 1,7 s es tolerable y se deja.

Contexto para decidir: el mini-informe carga **una** transacción por vez y ya
gasta ~72 s de IA por transacción (036 §5.2). 1,7 s de datos frente a 72 s de
análisis no es lo que se va a notar. Donde sí molestaría es al cambiar de
transacción con el informe ya generado.

---

## 4. Estado del plan N4 al cierre

| # | Sub-sprint | Estado | Nota |
|---|---|---|---|
| N4.1 | Aprobación de la estructura | ✅ hecho | decisiones del CTO |
| N4.2 | Diagnóstico read-only | ✅ hecho | reporte 036 |
| N4.3 | Servicio `transaction_series.py` | ✅ hecho | reporte 037 · `5168a48` |
| **N4.4** | **Endpoint `GET …/transaction-charts?label=`** | ✅ **hecho** | **este reporte · `c7f389f`** |
| N4.4b | *(propuesto)* `zip()` en vez de `iterrows()` | ⬜ opcional | ~20 líneas · sin IA · §3.2 |
| N4.5 | Tabla + modelo `transaction_chart_analyses` | ⬜ pendiente | ~55 líneas · sin ALTER TABLE |
| N4.6 | Generación IA bajo demanda (8 llamadas) **+ sacar N3.4 del upload** | ⬜ pendiente | ~140 líneas · **8 llamadas de IA** · aquí entra la regla de estilo de percentiles |
| N4.7 | Pantalla: botón por transacción, "generar todas" en cola, indicador de progreso | ⬜ pendiente | ~160 líneas · ⚠️ autorización si toca `Dashboard.tsx` |
| N4.8 | Export PDF | ⬜ pendiente | 🔴 `report_generator.py` protegido + `export_pdf.py` |
| N4.9 | Export HTML + informe integrado | ⬜ pendiente | 🔴 `export_html.py` + `integrated_report.py` |

**Lo que N4.4 deja listo para N4.7:** el frontend ya puede pedir las 5 series de
una transacción con una sola llamada, distinguir un fallo real de un dato
ausente por los códigos HTTP, y mostrar el motivo cuando falte una gráfica
gracias a `warnings`.

---

## 5. Datos de prueba limpiados

- Fila de prueba en `test_executions`: **insertada y borrada**, verificado con
  `count = 0`. La tabla quedó en sus **50** filas.
- Scripts de medición: copiados a `/tmp` del contenedor, ejecutados y
  **borrados**.
- `transaction_analyses` no se tocó: sigue con sus 10 filas previas.
- En el repo solo entran el endpoint y este reporte.

---

## 6. Criterio de éxito

El endpoint responde, los errores son entendibles y el pico de 21.060 ms llega
intacto, pero **esto sigue sin verse en pantalla**: hasta N4.7 la evidencia es
la de §2. Y queda tu decisión pendiente sobre §3.2.

**Parado aquí. N4.5 no se ha empezado.**
