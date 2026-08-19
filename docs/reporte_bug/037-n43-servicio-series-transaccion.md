# N4.3 — Servicio de series temporales por transacción

**Fecha:** 2026-08-18
**Commit:** `5168a48` — *N4.3: servicio de series temporales por transaccion*
**Push:** `github/backup-trabajo-local` (`d96c398..5168a48`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO Y VALIDADO — 27 verificaciones medidas, todas en OK.**
**Llamadas de IA:** **0.** El plan no las pedía para este paso y no se hizo
ninguna.

**Presupuesto del plan (reporte 036 §6):** 1 archivo nuevo, ~90 líneas →
**1 archivo nuevo, 157 líneas.** Me pasé 67. El desglose y la justificación
están en §5; no hubo ampliación de alcance, el exceso es documentación y
degradación por columnas ausentes.

**Backups:** ninguno necesario. N4.3 **crea** un archivo y no modifica ninguno
(`git status` lo confirma: una sola entrada, `??`). Nada que respaldar.

---

## 1. Qué se creó

`backend/app/services/jtl/transaction_series.py` — módulo nuevo, junto al parser
pero **fuera** de él.

```
available_labels(df) -> List[str]
build_transaction_series(df, label, interval_seconds=1) -> Dict
CHART_TYPES = ('response_times', 'latency', 'error_rate', 'codes', 'tps')
DEFAULT_INTERVAL_SECONDS = 1
```

`build_transaction_series` devuelve las **5 gráficas aprobadas** de UNA
transacción, como listas de puntos ya serializables:

| Clave | Forma de cada punto | Origen |
|---|---|---|
| `response_times` | `{timestamp, value, value_max}` | ya existía por label en el parser |
| `latency` | `{timestamp, value}` | **nueva** |
| `error_rate` | `{timestamp, value}` (%) | **nueva** |
| `codes` | `{timestamp, value, code}` | **nueva** |
| `tps` | `{timestamp, value}` | ya existía por label en el parser |

Más `label`, `interval_seconds`, `sample_count` y `warnings`.

### 1.1 Las tres decisiones de diseño que importan

**a) `jtl_parser.py` no se tocó — ni una línea.** El módulo recibe el DataFrame
ya parseado (`parser.df_main`, o `parser.df` si no hay redirecciones separadas:
el mismo criterio de `get_all_charts_data()`). El archivo protegido se leyó para
replicar el cálculo, nunca se modificó.

**b) Bucket de 1 s por defecto, parametrizable.** GRAF1 manda: con buckets más
grandes el pico de 21.060 ms se promedia y desaparece del gráfico del que va a
hablar el análisis. El parámetro existe porque N4.4 puede necesitar bajar
resolución, pero el default protege la lección.

**c) Errores como excepción, no como diccionario vacío.** Label inexistente,
DataFrame vacío o sin columnas base lanzan `ValueError` con mensaje en español.
El endpoint de N4.4 lo traducirá a 400/404. Devolver series vacías en silencio
haría que el mini-informe saliera en blanco sin que nadie supiera por qué.

### 1.2 Degradación cuando falta una columna

`Latency`, `success` y `responseCode` están al 100 % en los JTL de JMeter
(medido en 036 §2), pero los parsers de WAPT y Locust no siempre las producen.
Si falta una, **esa serie sale vacía, las otras cuatro se calculan igual** y el
motivo viaja en `warnings` para que la UI lo pueda decir. Además `success` se
normaliza: si llega como texto, `'false'` se lee como falso — con un
`astype(bool)` directo habría dado `True` y la tasa de error habría salido en
cero.

---

## 2. Validación medida

Ejecutada dentro del contenedor contra el JTL real de Coomeva
(`resultados_general_carga  31-jul.-2026-134550.jtl`, 25.773 muestras, 3
transacciones, 1.800 s). **27 verificaciones, 27 en OK.**

### 2.1 Equivalencia con el parser — la prueba que de verdad decide

La serie `response_times` que produce el módulo nuevo se comparó punto por punto
contra la que produce `get_all_charts_data()['response_times_by_label']`:

| Transacción | Puntos | Timestamps | avg | max (GRAF1) |
|---|---|---|---|---|
| `token` | 1.666 = 1.666 ✅ | idénticos ✅ | **delta 0.0** ✅ | **delta 0.0** ✅ |
| `Adapter VerifMethod` | 1.650 = 1.650 ✅ | idénticos ✅ | **delta 0.0** ✅ | **delta 0.0** ✅ |
| `Adapter SendCode` | 1.661 = 1.661 ✅ | idénticos ✅ | **delta 0.0** ✅ | **delta 0.0** ✅ |

Delta exactamente **cero**, no "aproximadamente cero": el mini-informe pintará
la misma curva que el dashboard, no una parecida.

### 2.2 Las tres series nuevas, contra el DataFrame

| Verificación | `token` | `Adapter VerifMethod` | `Adapter SendCode` |
|---|---|---|---|
| TPS × intervalo == muestras | 8.600 = 8.600 ✅ | 8.599 = 8.599 ✅ | 8.574 = 8.574 ✅ |
| Códigos × intervalo == muestras | 8.600 ✅ | 8.599 ✅ | 8.574 ✅ |
| Set de códigos == los del JTL | `200`, `Non HTTP response code…` ✅ | `200`, `401`, `Non HTTP…` ✅ | `200`, `401` ✅ |
| Latencia ponderada == media real | 386,2813 = 386,2813 ✅ | 2864,7835 = 2864,7835 ✅ | 139,0637 = 139,0637 ✅ |
| Error ponderado == tabla resumen | 0,2674 % ✅ | 0,6280 % ✅ | 0,2683 % ✅ |

La latencia y la tasa de error se validaron **ponderando cada bucket por su
número de muestras** y comparando contra la media global del DataFrame y contra
`tasa_error` de `get_summary_table_data()`. Es la comprobación que detecta un
bucket mal construido, cosa que un simple "no está vacío" no vería.

### 2.3 Casos borde

| Caso | Resultado |
|---|---|
| Label inexistente | `ValueError: La transaccion 'NO_EXISTE' no existe en este JTL` ✅ |
| DataFrame vacío | `ValueError: El DataFrame no tiene muestras` ✅ |
| Sin columna `Latency` | serie vacía + warning, **las otras 4 se calculan** ✅ |
| `success` como texto `'true'/'false'` | misma tasa de error que con booleanos ✅ |
| `interval_seconds=3` | 600 puntos en vez de 1.666 ✅ |
| `interval_seconds=0` | cae al default de 1 s ✅ |

### 2.4 Coste medido (mejor de 5 corridas, bucket 1 s)

| Transacción | Tiempo | Muestras | Puntos | JSON |
|---|---|---|---|---|
| `token` | **341,9 ms** | 8.600 | 8.353 | 503,5 KB |
| `Adapter VerifMethod` | **315,3 ms** | 8.599 | 8.303 | 505,2 KB |
| `Adapter SendCode` | **337,4 ms** | 8.574 | 8.328 | 500,9 KB |

**Corrijo hacia arriba una cifra de mi propio diagnóstico.** En 036 §3.4 dije
"~0,3 s por petición" contando 76 ms de agrupación + 0,2 s de parseo. Medido de
punta a punta, **la construcción sola son ~340 ms**: la agrupación de pandas
sigue costando decenas de milisegundos, pero armar 8.300 diccionarios de Python
con `iterrows()` cuesta el resto. Con el re-parseo del JTL, N4.4 servirá una
transacción en **~0,55 s**, no en 0,3 s.

Sigue siendo la decisión correcta frente a +1,26 MB en **cada** apertura del
dashboard, y el tamaño sí quedó donde predije (500 KB medidos contra ~570 KB
estimados). Si esos 340 ms molestan en N4.4, la vía es cambiar `iterrows()` por
`zip()` sobre arrays de numpy; no hace falta ahora.

### 2.5 Arranque limpio

```
docker restart jmeter_backend        -> Up (healthy), sin build
import del modulo dentro del contenedor -> OK
import de app.main                   -> OK (sin romper el arranque)
GET /health                          -> HTTP 200
python -m py_compile                 -> OK
```

Sin frontend en este sub-sprint: no aplica `tsc`.

### 2.6 Datos de prueba limpiados

El script de validación se copió a `/tmp` del contenedor, se ejecutó y **se
borró**. No escribió en la base: `transaction_analyses` sigue con las **10
filas** de antes, la más reciente de las 20:18:09 del 18/08 — de tu upload,
anterior a este sub-sprint. Cero llamadas de IA, cero filas nuevas, cero
archivos de prueba en el repo.

---

## 3. Lo que NO hace N4.3 (y es correcto que no lo haga)

- **No expone endpoint.** Eso es N4.4. Hoy el módulo no lo importa nadie: es
  código nuevo, aislado y sin efecto sobre lo que ya funciona.
- **No persiste nada.** La tabla `transaction_chart_analyses` es N4.5.
- **No llama a la IA.** Eso es N4.6.
- **No toca `/upload`.** La salida del análisis N3.4 del upload está planificada
  en §4.1, para N4.6.

---

## 4. Estado del plan N4 al cierre

| # | Sub-sprint | Estado | Nota |
|---|---|---|---|
| N4.1 | Aprobación de la estructura | ✅ hecho | decisiones del CTO |
| N4.2 | Diagnóstico read-only | ✅ hecho | reporte 036 |
| **N4.3** | **Servicio `transaction_series.py`** | ✅ **hecho** | **este reporte — commit `5168a48`** |
| N4.4 | Endpoint `GET /executions/{id}/transaction-charts?label=` | ⬜ pendiente | ~70 líneas · sin archivos protegidos |
| N4.5 | Tabla + modelo `transaction_chart_analyses` | ⬜ pendiente | ~55 líneas · sin ALTER TABLE |
| N4.6 | Generación IA bajo demanda (8 llamadas) **+ sacar N3.4 del upload** | ⬜ pendiente | ~140 líneas + la mudanza · **8 llamadas de IA** |
| N4.7 | Pantalla: botón por transacción, "generar todas" en cola, **indicador de progreso** | ⬜ pendiente | ~160 líneas · ⚠️ pedir autorización si el montaje toca `Dashboard.tsx` |
| N4.8 | Export PDF | ⬜ pendiente | 🔴 `report_generator.py` protegido + `export_pdf.py` |
| N4.9 | Export HTML + informe integrado | ⬜ pendiente | 🔴 `export_html.py` + `integrated_report.py` |

### 4.1 Decisiones del CTO ya incorporadas al plan

| Decisión | Dónde aterriza |
|---|---|
| Las 5 gráficas son las asumidas | ✅ **ya implementado**: `CHART_TYPES` en este módulo |
| Conclusiones y recomendaciones a **200 palabras** | N4.6 — baja la proyección de 93,7 s a **~72,6 s por transacción** (036 §5.2) |
| Botón por transacción + "generar todas" en cola secuencial | N4.7 (UI) y N4.6 (el endpoint recibe **una** transacción por llamada, que es lo que permite reintentar la que falle) |
| Generación bajo demanda, fuera de `/upload` | N4.4/N4.6 |
| Endpoint aparte para las series | N4.4 |
| Tabla nueva sin ALTER | N4.5 |
| **Sacar el análisis N3.4 del upload** | **N4.6**, en el mismo paso que lo sustituye. Hacerlo antes dejaría el bloque N3.5 de los exports sin datos entre un sub-sprint y otro |
| Indicador de progreso en el mismo paso que el botón | N4.7 — requiere que el endpoint de N4.6 reporte por gráfica |
| Estilo C2 + traducir percentiles a experiencia de usuario | N4.6, en los 8 prompts |

**Sobre la regla de estilo nueva** ("1 de cada 10 usuarios espera más de 3,5
segundos (P90: 3.515 ms)"): no entra en N4.3 porque aquí no se redacta nada.
Anotada para N4.6, donde se añadirá como regla 20 del `SYSTEM_PROMPT` o como
línea del prompt por transacción — la decisión de dónde ponerla es parte de ese
sub-sprint.

---

## 5. Exceso de presupuesto: 157 líneas contra 90 estimadas

Lo declaro porque la regla del sprint obliga a hacerlo. El desglose:

| Bloque | Líneas |
|---|---|
| Docstring del módulo (por qué vive fuera del parser, GRAF1) | 22 |
| Docstring de `build_transaction_series` + comentarios | 27 |
| Código efectivo | ~100 |
| Líneas en blanco | ~8 |

**Sobre las ~90 estimadas, el código efectivo se pasó en ~10 líneas**; el resto
del exceso es documentación y los tres bloques de degradación por columna
ausente (§1.2), que no estaban en la estimación original. No hubo ampliación de
alcance: sigue siendo un archivo, sin tocar nada protegido, sin endpoint, sin
base y sin IA. Si prefieres el módulo con menos comentario, se recorta en un
prompt aparte.

---

## 6. Criterio de éxito

Las 27 verificaciones pasan y la equivalencia con el parser es exacta, pero
**esto todavía no se ve en pantalla**: N4.3 es infraestructura. La validación
visual llegará en N4.7, cuando haya gráficas que mirar. Hasta entonces, la
evidencia es la medida de §2.

**Parado aquí, como marca la regla del sprint.** N4.4 no se ha empezado.
