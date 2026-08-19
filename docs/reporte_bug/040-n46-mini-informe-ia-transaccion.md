# N4.6 — Generación IA del mini-informe por transacción, bajo demanda

**Fecha:** 2026-08-19
**Commit:** `d6ba2f78e99fb37dce9dc1ac1bb844e4854be027` — *N4.6: generacion IA del mini-informe por transaccion bajo demanda*
**Push:** `github` (`72ba7ef..d6ba2f7`, rama `backup-trabajo-local`). **`origin` (Azure) no se tocó.**
**Llamadas de IA:** **8** — una transacción real, autorizada por el CTO. Detalle de coste y tiempo en §7.
**Archivos tocados:** **3** (máx. 4). **Backups:** `.bak_n46_20260819_175630`.
**ALTER TABLE:** ninguno. La tabla es la de N4.5.

---

## 1. Qué se hizo

| Archivo | Cambio |
|---|---|
| `backend/app/services/ai/transaction_report.py` | **Nuevo.** 200 líneas: los 8 prompts, el resumen de series, el upsert idempotente y el bucle tolerante a fallos |
| `backend/app/api/v1/endpoints/upload.py` | **+138 / −27.** Dos endpoints nuevos (POST genera, GET lee y reporta progreso), dos helpers y la extracción del cargador de JTL que N4.4 ya tenía escrito |
| `backend/app/services/ai/transaction_analysis.py` | **+33 / −84.** Le sale la IA: el premarcado del upload solo registra la fila |

### 1.1 El presupuesto se pasó, y por cuánto

Pediste 140-180 líneas. El neto real es **+260** (200 nuevas + 111 netas en
`upload.py` − 51 que se borran del premarcado). El desglose de las 200 del
archivo nuevo:

| Concepto | Líneas |
|---|---|
| Texto de instrucciones a la IA (regla UX, las 8 instrucciones de sección, bloque de métricas, plantilla del prompt) | ~45 |
| Docstrings que justifican las decisiones | 26 |
| Comentarios y líneas en blanco | 38 |
| Código ejecutable (digest de series, upsert, bucle) | ~91 |

El código ejecutable propiamente dicho cabe en el presupuesto; lo que lo rompe
es que **en este sprint el texto de los prompts ES el producto** y ocupa líneas
como cualquier otra cosa. Lo dejo declarado en vez de comprimir los prompts a
una línea ilegible para que el conteo cuadre. Los archivos sí se respetaron: 3
de 4, y ninguno protegido.

---

## 2. El servicio y los dos endpoints

### 2.1 `POST /api/v1/executions/{id}/transaction-report?label=`

Rol `admin | analyst` (gasta IA; el GET solo pide sesión activa). Hace, en orden:
localiza y parsea el JTL, calcula las 5 series de N4.3, toma las métricas de esa
transacción del summary ya calculado, y lanza las 8 secciones **en serie**.
Devuelve contadores:

```json
{"total":8,"generated":8,"failed":0,"elapsed_ms":108763,"label":"token"}
```

Al final sincroniza los contadores de cupo con `update_ai_usage_in_db`, igual
que hace el upload. Sin eso, 8 llamadas por cada mini-informe quedarían fuera
del límite diario y mensual configurado.

### 2.2 `GET /api/v1/executions/{id}/transaction-report?label=`

Devuelve las secciones persistidas y el bloque `progress`, que es el que
consumirá N4.7:

```json
"progress": {"done": 8, "total": 8, "persisted": 8, "pending": []}
```

### 2.3 Mecanismo de progreso: la base, no la memoria

**Decisión: `COMMIT` después de cada sección, y el progreso se lee contando
filas.** No hay registro en memoria, ni WebSocket, ni tabla de jobs.

El motivo es concreto: en producción el backend arranca con `--workers 2`. Un
diccionario en memoria vive en UN proceso, y el sondeo del frontend puede caer
en el otro — mostraría 0 de 8 mientras el trabajo avanza. La base es el único
canal que ven los dos procesos, y ya la estamos escribiendo de todas formas.

El coste de commitear 8 veces en vez de 1 es despreciable al lado de los ~13 s
que tarda cada llamada de IA, y trae dos regalos: si el proceso muere en la
sección 5, las 4 primeras ya están guardadas; y regenerar solo lo que falta es
posible sin más maquinaria.

### 2.4 Tolerancia por sección

La fila se escribe **siempre**, con texto o sin él. Una excepción en una llamada
se registra (`logger.error`) y el bucle sigue con la siguiente. Validado en §5.1:
con `chart_latency` reventando a propósito, las otras 7 salieron.

Un matiz que hay que saber: el `_circuit_open` de `GeminiAnalyzer` es global. Si
un 429 agota los reintentos, el resto de secciones devuelve `None` de inmediato
en lugar de reintentar. El mini-informe no se cae —quedan filas vacías y
regenerar las rellena— pero un 429 temprano puede dejar 7 secciones sin texto.
Es el comportamiento que ya tiene el resto del sistema; no se cambió aquí.

### 2.5 Idempotencia

El guardado busca por `(execution_id, label, section)` y hace `UPDATE` si la fila
existe. Regenerar reescribe las mismas 8 filas, con los mismos `id` (§5.1, paso 3).
Al regenerar se limpia `is_edited` y `ai_analysis_updated_at`: el texto es nuevo,
la marca de edición manual ya no aplica.

---

## 3. Los 8 prompts

### 3.1 Dónde va la regla de traducir percentiles, y por qué

**Va en los prompts por transacción (constante `UX_RULE` de
`transaction_report.py`), NO en el `SYSTEM_PROMPT`.**

El `SYSTEM_PROMPT` lo comparten los 12 análisis globales que acabamos de validar
en C2 (`ef8636c`) y el análisis de imágenes. Meter ahí una regla nueva obliga a
revalidar todo eso —14 llamadas por upload— por una regla que solo tiene sentido
cuando se habla de UNA transacción y de SUS percentiles. La regla 6 del proyecto
(1 tarea = 1 prompt atómico) apunta en la misma dirección: este sprint cambia el
mini-informe, no el informe global.

Si más adelante quieres la misma traducción en las secciones globales, es mover
la constante al `SYSTEM_PROMPT` y volver a validar los 14 textos. Queda como
decisión abierta, no como deuda escondida.

El texto de la regla:

```
TRADUCCION A EXPERIENCIA DE USUARIO (obligatorio, el publico es gerencial):
- Todo percentil que menciones va con su lectura en personas: P90 = 1 de cada 10
  usuarios, P95 = 1 de cada 20, P99 = 1 de cada 100, mediana = la mitad de los usuarios.
- Forma exacta: "1 de cada 10 usuarios espera mas de 3,5 segundos (P90: 3.515 ms)".
  Primero las personas y el tiempo en segundos, la cifra tecnica despues entre parentesis.
- Por encima de 1.000 ms expresa el tiempo en segundos con un decimal; por debajo
  deja los milisegundos.
- Un percentil suelto, sin decir a cuantos usuarios afecta, no sirve para este informe.
```

### 3.2 Qué lleva cada prompt

Los 8 comparten: `SYSTEM_PROMPT` completo (reglas C2 heredadas) + métricas reales
de la transacción + el resumen de su serie + la instrucción de la sección + el
tope de palabras + `STYLE_REMINDER` (C2) + `UX_RULE` al final, que es la posición
que más pesa.

Las métricas incluyen **el máximo con su ratio calculado en Python**
(`21060 ms (47.6 veces su promedio)`), lección GRAF1: el modelo no estima el
ratio, lo recibe hecho. También mediana, mínimo, P90, P95, P99, errores y caudal.

Las 5 secciones de gráfica reciben el resumen de SU serie (pico y su hora,
promedio, intervalos con error, reparto de códigos, TPS medio y máximo).
Resumen, conclusiones y recomendaciones reciben las cinco. Los ~500 KB de puntos
que devuelve N4.3 no caben en un prompt: lo que se manda es su forma.

### 3.3 Topes

| Sección | Tope |
|---|---|
| `summary` | 200 palabras |
| las 5 `chart_*` | 120 palabras — el mismo de las gráficas globales (regla 8 del SYSTEM_PROMPT) |
| `conclusions`, `recommendations` | 200 palabras |

`sanitize_ai_text` se aplica dos veces: dentro de `_generate` y otra vez en el
servicio antes de persistir (regla 14).

---

## 4. El análisis por transacción sale del upload

Aplicado tal cual lo dejó documentado el reporte 039 §3:

| Antes de N4.6 | Después |
|---|---|
| El upload llamaba a la IA una vez por transacción marcada (hasta 10) | El upload no llama a la IA por transacción: **0 llamadas** |
| El texto se guardaba en `transaction_analyses.ai_analysis` | La fila se crea con `ai_analysis = NULL` |
| Contadores `{requested, analyzed, failed, skipped}` | Contadores `{requested, registered, skipped}` |

`transaction_analyses.ai_analysis` queda **legacy de solo lectura**: nadie vuelve
a escribirla, las ejecuciones ya analizadas conservan su texto y el bloque N3.5 de
los reportes viejos lo sigue mostrando (verificado en §5.4). No se borró ninguna
columna — habría sido un `ALTER TABLE`, prohibido por la regla 10.

El módulo `transaction_analysis.py` ya no importa nada de `gemini.py`. Su
`build_transaction_prompt` se eliminó: ese prompt vive ahora como la sección
`summary` del archivo nuevo, con la regla UX añadida.

Los parámetros `test_type` y `analyzer` de `analyze_critical_transactions` quedan
sin uso; se conservan en la firma para no tocar la llamada del upload. Está
marcado con un comentario en el código.

---

## 5. Validación

### 5.1 Con stub, sin gastar IA

Ejecución sintética `2222…2222`, analizador de mentira, una sección programada
para reventar con un 429 simulado.

```
--- PASO 1: generacion con una seccion rota (chart_latency) ---
N4.6: fallo la seccion 'chart_latency' de 'token': 429 simulado: quota exceeded
contadores: {'total': 8, 'generated': 7, 'failed': 1}
llamadas al analizador: 8
  0 summary                [v1] texto de summary para token               edited=False
  1 chart_response_times   [v1] texto de chart_response_times para to     edited=False
  2 chart_latency          (VACIA)                                        edited=False
  3 chart_error_rate       [v1] texto de chart_error_rate para token      edited=False
  4 chart_codes            [v1] texto de chart_codes para token           edited=False
  5 chart_tps              [v1] texto de chart_tps para token             edited=False
  6 conclusions            [v1] texto de conclusions para token           edited=False
  7 recommendations        [v1] texto de recommendations para token       edited=False
filas totales: 8
```

**La sección rota no arrastró a las otras siete**, y aun así dejó su fila.

Regeneración (paso 3), después de editar `chart_tps` a mano:

```
contadores: {'total': 8, 'generated': 8, 'failed': 0}
filas antes: 8 | filas despues: 8 | mismos ids: True
  summary                [v2] texto de summary para token               edited=False
  …las 8 con marca [v2], incluida la que estaba vacía…
```

**8 filas antes, 8 después, los mismos `id`: fue UPDATE, no INSERT.** La sección
editada a mano volvió a `is_edited=False` porque su texto se reemplazó.

Y los 8 prompts, medidos:

```
  summary                  7467 chars | max: True | ratio: True | UX: True
  chart_response_times     7118 chars | max: True | ratio: True | UX: True
  chart_latency            7076 chars | max: True | ratio: True | UX: True
  chart_error_rate         7102 chars | max: True | ratio: True | UX: True
  chart_codes              7089 chars | max: True | ratio: True | UX: True
  chart_tps                7075 chars | max: True | ratio: True | UX: True
  conclusions              7462 chars | max: True | ratio: True | UX: True
  recommendations          7440 chars | max: True | ratio: True | UX: True
```

Los 8 llevan el máximo (21060), su ratio y la regla de traducción.

### 5.2 Una transacción REAL

- **Ejecución:** `115346ea-fcf6-4951-bec1-9495e3c035f5` — *24342-Coomeva_SendCode_Performance*, cliente Bancoomeva, tipo `scalability`.
- **Transacción:** `token`, 8.600 muestras, **máximo 21.060 ms** (el pico de GRAF1), promedio 443 ms, P90 529 ms, P95 657 ms, P99 1.070 ms, 23 errores (0,27%).
- **Resultado:** `{"total":8,"generated":8,"failed":0,"elapsed_ms":108763}` — **8 de 8, ningún fallo.**

Antes de gastar, el endpoint gratuito de N4.4 confirmó el pico: `pico max serie 21060.0`.

Verificación automática sobre los 8 textos:

```
seccion                palabras  prohibidas  markdown  21060  ratio47  1 de cada
summary                     204     ninguna        no   True     True       True
chart_response_times        124     ninguna        no   True     True       True
chart_latency               133     ninguna        no   True     True       True
chart_error_rate             92     ninguna        no   True     True      False
chart_codes                 102     ninguna        no   True     True       True
chart_tps                   115     ninguna        no   True     True       True
conclusions                 208     ninguna        no   True     True       True
recommendations             192     ninguna        no   True     True       True
```

- **Palabras prohibidas: ninguna** en las 8 (se buscaron las 6 vetadas más "se observa que").
- **Markdown: ninguno** — sin `**`, sin `#`, sin viñetas, sin backticks.
- **El pico de 21.060 ms aparece en las 8 secciones**, siempre con su ratio de 47,6 veces.
- **La traducción a usuarios aparece en 7 de 8.** La que falta es `chart_error_rate`, y es correcto: esa sección habla de tasa de error y no cita ningún percentil, así que no hay nada que traducir.
- **Topes:** las de gráfica se pasaron entre 0 y 13 palabras del tope de 120 (124, 133, 115, 102, 92); summary y conclusions se pasaron 4 y 8 palabras de 200. Es la desviación normal de un modelo contando palabras; ninguna sección se dispara.

### 5.3 El upload ya no genera el análisis por transacción

Verificado por código y por ejecución, sin gastar un solo upload con IA:

```
contadores del premarcado: {'requested': 2, 'registered': 2, 'skipped': 0}
llamadas de IA registradas por GeminiAnalyzer: antes=0 despues=0 -> delta=0
  token                  critica=True por=user ai_analysis_NULL=True max=21060.0
  Adapter VerifMethod    critica=True por=user ai_analysis_NULL=True max=9000.0
filas en transaction_chart_analyses (no deberia crear ninguna): 0
```

Dos transacciones marcadas, dos filas creadas con sus métricas, **`ai_analysis` en
NULL y cero llamadas de IA**. Y por código, los imports que quedan en el módulo:

```
19:import logging
20:from typing import Dict, List, Optional
22:from app.db.models.transaction_analysis import TransactionAnalysis
```

**No queda ni una importación de `gemini.py`**: aunque alguien quisiera, ese
módulo ya no puede llamar a la IA.

### 5.4 Un informe VIEJO sigue mostrando su bloque N3.5

Ejecución `5381abec…` (*caso 1*, del 18 de agosto), que tiene texto legacy en
`transaction_analyses`. Export HTML: **200, 535.851 bytes**. Dentro:

```
Analisis por Transaccion                      presente=True pos=23483
token promedió 443 ms                         presente=True pos=23977
Adapter VerifMethod procesó 8.599             presente=True pos=25609
```

Y el bloque, tal como se renderiza:

```html
<div style="…">token</div>
<div style="…">8,600 muestras · promedio 443 ms · p90 529 ms · max 21060 ms · 23 errores (0.27%)</div>
<div style="…"><p>token promedió 443 ms en 8.600 muestras, con percentil 90 en 529 ms…</p></div>
```

**El texto legacy sigue llegando al reporte.** Nada de lo que hizo N4.6 lo tocó.

### 5.5 Limpieza y contadores

Las dos ejecuciones sintéticas (`2222…`, `3333…`) se borraron; el `ON DELETE
CASCADE` de N4.5 se llevó sus filas hijas. Estado final de la base:

```
                tabla                 | filas | ejecuciones | labels | con_texto
--------------------------------------+-------+-------------+--------+-----------
 transaction_chart_analyses           |     8 |           1 |      1 |         8
 de ejecuciones de prueba (2222/3333) |     0 |           0 |      0 |         0
 transaction_analyses (N3.4 legacy)   |    10 |           5 |      0 |         4
 test_executions de prueba            |     0 |           0 |      0 |         0
```

**Cero filas sintéticas, cero ejecuciones de prueba.** Las 8 filas que quedan son
las reales de `token` en la ejecución de Bancoomeva: **no las borré a propósito**,
para que N4.7 tenga contra qué pintar la pantalla sin volver a gastar IA. Si las
quieres fuera:

```sql
DELETE FROM transaction_chart_analyses
 WHERE execution_id='115346ea-fcf6-4951-bec1-9495e3c035f5' AND label='token';
```

Los dos scripts de prueba (`_n46_stub_test.py`, `_n46_upload_test.py`) se
borraron del repositorio; no entraron en el commit.

---

## 6. Los 8 textos reales, completos

Generados el 2026-08-19 entre las 23:03:13 y las 23:04:47 (UTC), proveedor
**OpenAI `gpt-5.5`**, sobre `token` de la ejecución de Bancoomeva. Van tal cual
salieron de la base, sin retocar.


### 1. `summary`

*204 palabras (tope 200) · 1194 caracteres · prompt de 7,549 caracteres · generado 23:03:13*

> 443 ms de promedio en token luce operativo frente a una mediana de 333 ms, donde la mitad de los usuarios queda en 333 ms o menos, pero el máximo de 21060 ms, 47,6 veces sobre su promedio, rompe el patrón sano y apunta a bloqueos intermitentes o intentos de conexión que no responden. El mínimo de 311 ms contra el máximo de 21060 ms marca una brecha de 67,7 veces, coherente con un servicio que normalmente responde rápido pero presenta episodios severos de espera.
>
> 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms), 1 de cada 20 usuarios espera más de 657 ms (P95: 657 ms) y 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1070 ms), lo que sugiere degradación perceptible en la cola superior aunque el promedio siga en 443 ms. Los 23 errores sobre 8,600 muestras, equivalentes a 0.27%, asociados a org.apache.http.conn.HttpHostConnectException, apuntan a fallas puntuales de conectividad; el pico de error de 33.33% en un intervalo refuerza un comportamiento intermitente, no uniforme.
>
> En producción, el usuario percibirá respuestas ágiles la mayor parte del tiempo, pero con casos aislados de espera excesiva y fallas que pueden interrumpir el inicio o renovación de sesión.

### 2. `chart_response_times`

*124 palabras (tope 120) · 689 caracteres · prompt de 7,119 caracteres · generado 23:03:24*

> 443 ms de promedio en token, con mediana de 333 ms y mínimo de 311 ms, apunta a un nivel base ágil durante la mayor parte de los 1666 puntos de la serie. 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms), 1 de cada 20 supera 657 ms (P95: 657 ms) y 1 de cada 100 espera más de 1,1 segundos (P99: 1070 ms), lo que sugiere degradación aislada más que lentitud sostenida. El pico de 21060 ms a las 19:11:21, 47,6 veces sobre su promedio, es coherente con esperas o timeouts intermitentes, reforzado por 23 errores equivalentes al 0,27%. En producción, algunos clientes sentirán una autenticación rápida, pero otros enfrentarán demoras puntuales que pueden hacerles abandonar el ingreso.

### 3. `chart_latency`

*133 palabras (tope 120) · 748 caracteres · prompt de 7,078 caracteres · generado 23:03:34*

> 443 ms de tiempo promedio en token contrastan con 370 ms de latencia promedio, por lo que 83,5% del tiempo apunta a red o espera previa y 73 ms, equivalentes a 16,5%, sugieren procesamiento efectivo del servidor. La mediana de 333 ms indica que la mitad de los usuarios queda por debajo de ese tiempo, mientras 1 de cada 10 usuarios espera mas de 529 ms (P90: 529 ms), 1 de cada 20 usuarios espera mas de 657 ms (P95: 657 ms) y 1 de cada 100 usuarios espera mas de 1,1 segundos (P99: 1070 ms). El maximo de 21060 ms, 47.6 veces sobre su promedio, apunta a esperas intermitentes fuera del procesamiento normal. En produccion, algunos clientes sentiran respuestas agiles, pero otros viviran demoras aisladas que deterioran la confianza en el ingreso.

### 4. `chart_error_rate`

*92 palabras (tope 120) · 588 caracteres · prompt de 7,105 caracteres · generado 23:03:45*

> 23 errores sobre 8,600 muestras dejan la tasa de token en 0.27%, con fallos presentes en 23 de 1666 intervalos, lo que sugiere eventos aislados y no una degradación constante. El pico de 33.33% en un intervalo apunta a una afectación puntual, coherente con interrupciones breves o esperas intermitentes; el máximo de 21060 ms, 47.6 veces su promedio de 443 ms, refuerza la hipótesis de episodios excepcionales más que lentitud sostenida. En producción, el usuario final percibirá ingresos normalmente ágiles, pero con casos aislados de espera prolongada o intento fallido al autenticarse.

### 5. `chart_codes`

*102 palabras (tope 120) · 686 caracteres · prompt de 7,158 caracteres · generado 23:03:55*

> 8,577 respuestas fueron 200 y 23 terminaron en Non HTTP response code: org.apache.http.conn.HttpHostConnectException, con 0.27% de error sobre 8,600 muestras. Ese reparto sugiere un servicio mayoritariamente sano, pero con fallas puntuales de conexión que apuntan a indisponibilidad intermitente o rechazo temporal del destino. El máximo de 21060 ms, 47.6 veces sobre su promedio de 443 ms, apunta a esperas excepcionales asociadas a esos episodios, aunque 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1070 ms). En producción, la mayoría de clientes avanzaría sin fricción, pero algunos encontrarían demoras largas o intentos fallidos que afectan la confianza en el servicio.

### 6. `chart_tps`

*115 palabras (tope 120) · 690 caracteres · prompt de 7,074 caracteres · generado 23:04:13*

> 5.16 TPS de promedio, 17.00 TPS de máximo y 4.78 operaciones por segundo procesadas por token sugieren un caudal activo pero no plano, con ráfagas que no se sostienen durante toda la prueba. La mediana de 333 ms y el promedio de 443 ms son coherentes con respuestas ágiles en la mayoría de ejecuciones; 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1070 ms), mientras el máximo de 21060 ms, 47.6 veces su promedio, apunta a pausas intermitentes que pueden comprimir temporalmente el caudal. Los 23 errores, 0.27% de 8,600 muestras, sugieren afectación baja pero real. En producción, el usuario percibirá accesos normalmente rápidos, con casos aislados de espera larga o reintento.

### 7. `conclusions`

*208 palabras (tope 200) · 1262 caracteres · prompt de 7,544 caracteres · generado 23:04:26*

> 8,600 muestras de token dejaron un promedio de 443 ms, mediana de 333 ms y mínimo de 311 ms, lo que sugiere un comportamiento ágil para la mayoría de solicitudes exitosas. La mitad de los usuarios espera 333 ms o menos (mediana: 333 ms), 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms), 1 de cada 20 usuarios espera más de 657 ms (P95: 657 ms) y 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1070 ms), lectura coherente con una experiencia normalmente rápida pero con degradación perceptible en la cola alta.
>
> El máximo de 21060 ms, 47.6 veces sobre su promedio, apunta a interrupciones intermitentes de conectividad o esperas anómalas, reforzado por 23 errores, equivalentes al 0.27% de las muestras, todos asociados a org.apache.http.conn.HttpHostConnectException. La latencia promedio de 370 ms frente a un máximo de 1332 ms sugiere variabilidad en la comunicación, mientras el pico de error de 33.33% en un intervalo confirma episodios puntuales de indisponibilidad.
>
> Con estos datos, token no queda listo para producción sin estabilizar los episodios de conexión y el pico de 21060 ms. En producción, el usuario percibirá un servicio normalmente rápido, pero con casos aislados donde la operación falla o queda esperando demasiado tiempo.

### 8. `recommendations`

*192 palabras (tope 200) · 1239 caracteres · prompt de 7,522 caracteres · generado 23:04:47*

> 21060 ms fue el máximo de token, 47.6 veces su promedio de 443 ms, y apunta a esperas bloqueantes o cortes intermitentes contra el servicio destino.
>
> 1. Priorizar la estabilización de conectividad hacia token, porque 23 errores, equivalentes al 0.27% de 8,600 muestras, terminaron como Non HTTP response code: org.apache.http.conn.HttpHostConnectException. Este patrón sugiere rechazos o indisponibilidad transitoria del host, por lo que debe validarse ruta, balanceo, disponibilidad del destino, timeouts y reintentos controlados.
>
> 2. Correlacionar el pico de 21060 ms a las 19:11:21 con logs de aplicación, red y balanceador, porque 47.6 veces sobre su promedio no es coherente con la mediana de 333 ms, donde la mitad de los usuarios espera 333ms. Ese contraste apunta a degradaciones puntuales que quedan ocultas si solo se mira el promedio.
>
> 3. Asegurar que token soporte la variación de demanda entre 5.16 TPS promedio y 17.00 TPS máximo, porque 1 de cada 100 usuarios espera más de 1.1 segundos (P99: 1.070 ms). Esa cola de respuesta sugiere sensibilidad ante ráfagas de tráfico.
>
> En producción, el usuario percibirá ingresos normalmente rápidos, pero con episodios aislados de espera larga y fallos que obligan a intentar de nuevo.


---

## 7. Coste y tiempo de la corrida real

| Métrica | Valor |
|---|---|
| Llamadas de IA | **8** (una por sección) |
| Proveedor / modelo | OpenAI `gpt-5.5` |
| Tiempo del bucle de IA | **108,8 s** (`elapsed_ms: 108763`) |
| Tiempo total del POST | **109,3 s** (incluye parsear un JTL de 25.773 muestras, ~0,8 s) |
| Tiempo por sección | entre 10 y 21 s; la más lenta, `recommendations` |
| Caracteres enviados | 58.149 (prompts de 7.074 a 7.549 caracteres) |
| Caracteres recibidos | 7.096 |
| Tokens estimados | ~15.000 de entrada, ~1.800 de salida visible |

El tiempo real quedó **por encima de los ~94 s que estimó el diagnóstico 036**:
109 s medidos. Sirve como número firme para N4.7: el indicador de progreso tiene
que aguantar cerca de dos minutos, y por eso el sondeo lee las filas ya
guardadas en vez de esperar a que termine todo.

Sobre los tokens: la aplicación **no captura el uso real que reporta la API**,
solo cuenta peticiones. La estimación sale de dividir caracteres entre cuatro y
no incluye los tokens de razonamiento de `gpt-5.5`, que son invisibles para
nosotros y se cobran. Tomar la cifra como orden de magnitud, no como factura.

Contadores de cupo, antes y después:

```
antes:   openai | gpt-5.5 | daily_requests_used=26 | monthly_requests_used=113
despues:                    daily_requests_used=8  | monthly_requests_used=121
log:     AI usage synced: +8 requests (daily=8, monthly=121)
```

Mensual: **113 → 121, exactamente +8**. El diario bajó de 26 a 8 porque el
contador diario se reinició al cambiar el día; los 8 que muestra son justo los
de este sprint.

---

## 8. Lo que este sprint NO hizo

- **No hay pantalla.** El mini-informe existe en la API y en la base; nadie lo ve
  todavía. Eso es N4.7.
- **No se probó con Gemini**, solo con OpenAI `gpt-5.5`, que es el proveedor
  configurado. El dispatcher es el mismo `_generate` que usan las 12 secciones
  globales, así que el riesgo es bajo, pero no está verificado.
- **No se generó más de una transacción.** El endpoint atiende una por llamada;
  hacer las 2 o 3 críticas de un informe son 2 o 3 llamadas del frontend, en
  serie o en paralelo — decisión de N4.7.
- **No se tocó el orden ni el contenido de las secciones globales.** El
  `SYSTEM_PROMPT` está intacto (§3.1).
- **No hay endpoint para editar una sección a mano.** La tabla lo soporta
  (`is_edited`, `ai_analysis_updated_at`) y el patrón F5 ya existe en el
  consolidado, pero la ruta `PUT` no se escribió: no estaba en el encargo.
- **`gpt-5.5` no está en `OPENAI_MAX_TOKENS`** y cae al default de 4096 con un
  warning en el log. No afectó a estas 8 secciones —la más larga ocupó 1.262
  caracteres— pero es la misma trampa de la lección HF18b y conviene añadirlo en
  algún sprint de mantenimiento.

---

## 9. Estado del plan N4

| # | Sub-sprint | Estado |
|---|---|---|
| N4.2 | Diagnóstico read-only del dato | ✅ cerrado — 036, `d96c398` |
| N4.3 | Servicio `transaction_series.py` | ✅ cerrado — 037, `5168a48` |
| N4.4 | Endpoint de series por transacción | ✅ cerrado — 038, `c7f389f` |
| N4.5 | Modelo + tabla `transaction_chart_analyses` | ✅ cerrado — 039, `1879401` |
| **N4.6** | **Generación IA bajo demanda + salida del upload** | ✅ **cerrado — este reporte, `d6ba2f7`** |
| N4.7 | Pantalla `TransactionReportSection.tsx` + botón + indicador de progreso. Absorbe N4.4b | ⏭️ **siguiente** — ⚠️ el montaje puede tocar `Dashboard.tsx` (protegido) |
| N4.8 | Export PDF con las 5 gráficas y los textos | ⏳ pendiente — 🔴 `report_generator.py` protegido |
| N4.9 | Export HTML standalone e informe integrado | ⏳ pendiente — 🔴 `export_html.py` bajo regla de memoria |

**El backend del mini-informe está completo:** series → endpoint → tabla → textos.
Lo que falta es enseñarlo.

Para N4.7, tres datos que ya no hay que averiguar: el progreso se sondea con
`GET …/transaction-report?label=`, el trabajo tarda ~110 s por transacción, y
hay 8 textos reales guardados en la ejecución de Bancoomeva para pintar la
pantalla sin gastar IA.

---

## 10. Cierre

```
$ git log -1 --format='%H %s'
d6ba2f78e99fb37dce9dc1ac1bb844e4854be027 N4.6: generacion IA del mini-informe por transaccion bajo demanda

$ git push github HEAD
   72ba7ef..d6ba2f7  HEAD -> backup-trabajo-local
```

`py_compile` limpio en los 3 archivos, `docker restart jmeter_backend` sin build,
arranque sin trazas, las 4 rutas de transacción registradas en el OpenAPI.

**Parado aquí. N4.7 no se encadenó.**
