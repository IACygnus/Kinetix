# 042 — Mini-informe de `token` regenerado completo

**Fecha:** 2026-08-19
**Sprint:** cierre de N4.6b. **No hay cambios de código:** este reporte documenta una
ejecución del endpoint ya entregado en `8245bff`.
**Commit del reporte:** ver §7.
**Llamadas de IA:** **8** — las 8 secciones, 90,8 s. Coste en §6.
**Ejecución:** `115346ea-fcf6-4951-bec1-9495e3c035f5` — *24342-Coomeva_SendCode_Performance*, Bancoomeva, `scalability`.
**Transacción:** `token`, 8.600 muestras, máximo 21.060 ms.

---

## 1. Por qué esta corrida

El reporte 041 dejó el mini-informe mixto a propósito: 4 secciones regeneradas con
las correcciones de N4.6b y 4 con el texto del 040, que todavía escribía "8,600
muestras" a la inglesa y repetía el pico en `chart_error_rate`. Esta corrida
elimina esa mezcla: **las 8 secciones salen de los prompts corregidos**.

```
POST /api/v1/executions/115346ea-.../transaction-report?label=token
{"total":8,"generated":8,"failed":0,"elapsed_ms":90769,"label":"token"}
```

**8 de 8, ningún fallo.** Las 8 filas son las mismas de siempre —`UPDATE` sobre el
UNIQUE de N4.5, sin duplicados—, todas con marca de tiempo nueva:

```
       section        | sort_order | is_edited |   gen    | chars
----------------------+------------+-----------+----------+-------
 summary              |          0 | f         | 02:46:42 |  1102
 chart_response_times |          1 | f         | 02:46:53 |   629
 chart_latency        |          2 | f         | 02:47:04 |   762
 chart_error_rate     |          3 | f         | 02:47:13 |   517
 chart_codes          |          4 | f         | 02:47:22 |   621
 chart_tps            |          5 | f         | 02:47:34 |   656
 conclusions          |          6 | f         | 02:47:46 |  1087
 recommendations      |          7 | f         | 02:47:58 |  1280
(8 rows)
```

---

## 2. Verificación de las tres correcciones

```
seccion                 pal  miles_ing   dec_ing   pico  esperado   prohib   md
summary                 183         no        no   True      True       no   no
chart_response_times    114         no        no   True      True       no   no
chart_latency           126         no        no  False     False       no   no
chart_error_rate         73         no        no  False     False       no   no
chart_codes              82         no        no  False     False       no   no
chart_tps               108         no        no  False     False       no   no
conclusions             178         no        no   True      True       no   no
recommendations         201         no        no   True      True       no   no

TODAS LAS COMPROBACIONES: OK
```

### 2.1 Formato español en las 8

Cero miles a la inglesa (`\d,\d{3}`) y cero decimales con punto en unidades
(`%`, `TPS`, `segundos`, `veces`). Las cifras que aparecen en los textos:
**8.600, 8.577, 1.666, 1.332, 1.070, 21.060, 0,27%, 33,33%, 5,16 TPS, 17,00 TPS,
4,78, 47,6 veces, 3,6 veces, 1,1 segundos, 83,5%.**

Comparado con el 040, donde el mismo informe escribía "8,600 muestras",
"0.27%", "5.16 TPS" y "1.1 segundos".

### 2.2 El pico, solo en las 4 obligatorias

| Sección | ¿21.060 ms? | Regla |
|---|---|---|
| `summary` | **sí** | obligatorio |
| `chart_response_times` | **sí** | obligatorio |
| `chart_latency` | no | opcional — cita el máximo de SU serie: 1.332 ms, 3,6 veces su promedio |
| `chart_error_rate` | no | opcional — se queda en 23 de 1.666 intervalos y el pico de 33,33% |
| `chart_codes` | no | opcional — se queda en 8.577 de 8.600 en 200 |
| `chart_tps` | no | opcional — usa 17,00 TPS de máximo |
| `conclusions` | **sí** | obligatorio |
| `recommendations` | **sí** | obligatorio — abre con él |

`chart_error_rate` era la que en el 041 seguía repitiéndolo. Ya no. **GRAF1 se
cumple**: el pico está en el resumen, en la gráfica de tiempos, en las conclusiones
y en las recomendaciones.

### 2.3 La latencia, con la interpretación corregida

> 370 ms de latencia promedio frente a 443 ms de tiempo total indica que 83,5% del
> ciclo ocurre **antes del primer byte**, mientras 73 ms quedan para **descarga del
> cuerpo de respuesta**. Esta proporción apunta a que la espera principal está en
> conexión, envío y procesamiento del servidor, **no en transferencia de contenido**.

Las tres igualdades de N4.6b están bien aplicadas: latencia = hasta el primer byte
(incluye el servidor), elapsed − latencia = descarga, y la lectura causal que sale
de ahí. Además cita el máximo de la serie de latencia (1.332 ms), no el del tiempo
total: no mezcla las dos series.

### 2.4 Lo demás sigue en su sitio

- **Palabras prohibidas: ninguna** en las 8.
- **Markdown: ninguno.**
- **Percentiles traducidos a usuarios** en las 7 que citan percentiles;
  `chart_codes` no cita ninguno, así que no traduce nada.
- **Topes:** `recommendations` 201 palabras (tope 200) y `chart_latency` 126
  (tope 120) son los únicos desbordes, de 1 y 6 palabras. Las demás entran.

---

## 3. Los 8 textos finales

Generados el 2026-08-20 entre las 02:46:42 y las 02:47:58 (UTC), OpenAI `gpt-5.5`.
Copiados de la base sin retocar.


### 1. `summary` — pico obligatorio

*183 palabras (tope 200) · 1102 caracteres · generado 02:46:42*

> 8.600 muestras de token cerraron con 443 ms promedio, 333 ms de mediana y mínimo de 311 ms, lo que sugiere una respuesta base ágil para la mitad de los usuarios. 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms), 1 de cada 20 usuarios espera más de 657 ms (P95: 657 ms) y 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1.070 ms), comportamiento que apunta a degradación puntual en la cola alta, no a lentitud constante.
>
> El máximo de 21.060 ms, 47,6 veces sobre su promedio, rompe el patrón sano de la transacción y es coherente con esperas intermitentes o intentos fallidos de conexión. Los 23 errores, equivalentes al 0,27% de las muestras, terminaron como org.apache.http.conn.HttpHostConnectException, con pico de 33,33% en un intervalo, lo que sugiere indisponibilidad breve del destino más que errores funcionales de la operación.
>
> Con 4,78 transacciones por segundo y máximo temporal de 17,00 TPS, token soporta carga, pero no entrega consistencia plena. En producción, algunos usuarios iniciarán rápido y otros percibirán demoras largas o intentos fallidos al validar su acceso.

### 2. `chart_response_times` — pico obligatorio

*114 palabras (tope 120) · 629 caracteres · generado 02:46:53*

> 443 ms de promedio y 333 ms de mediana dejan a la mitad de los usuarios por debajo de 333 ms, coherente con un nivel base ágil durante la mayor parte de los 1.666 puntos de la serie. 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms) y 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1.070 ms), lo que sugiere variabilidad acotada salvo eventos aislados. El pico de 21.060 ms a las 19:11:21, 47,6 veces sobre su promedio, apunta a una espera intermitente o timeout puntual bajo carga. En producción, algunos clientes podrían iniciar sesión rápido y otros quedarían esperando lo suficiente para abandonar el proceso.

### 3. `chart_latency` — pico opcional

*126 palabras (tope 120) · 762 caracteres · generado 02:47:04*

> 370 ms de latencia promedio frente a 443 ms de tiempo total indica que 83,5% del ciclo ocurre antes del primer byte, mientras 73 ms quedan para descarga del cuerpo de respuesta. Esta proporción apunta a que la espera principal está en conexión, envío y procesamiento del servidor, no en transferencia de contenido; el máximo de latencia de 1.332 ms, 3,6 veces su promedio, sugiere episodios puntuales de espera previa sin patrón dominante de respuesta pesada. La mitad de los usuarios espera más de 333 ms y 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1.070 ms), coherente con una experiencia usualmente rápida pero con demoras aisladas. En producción, algunos clientes percibirán el ingreso ágil y otros sentirán pausas ocasionales antes de avanzar.

### 4. `chart_error_rate` — pico opcional

*73 palabras (tope 120) · 517 caracteres · generado 02:47:13*

> 23 errores sobre 8.600 muestras dejaron una tasa de 0,27%, distribuida en 23 de 1.666 intervalos, lo que sugiere fallos aislados y no un deterioro constante de token. La mayor tasa fue 33,33% en un intervalo, comportamiento coherente con episodios breves de indisponibilidad o rechazos intermitentes bajo carga, sin continuidad suficiente para indicar una degradación sostenida. En producción, el usuario percibirá ingresos mayoritariamente exitosos, pero con casos puntuales donde deberá reintentar la autenticación.

### 5. `chart_codes` — pico opcional

*82 palabras (tope 120) · 621 caracteres · generado 02:47:22*

> 8.577 respuestas 200 sobre 8.600 muestras sugieren que token mantiene una disponibilidad funcional alta, con 23 fallas Non HTTP response code: org.apache.http.conn.HttpHostConnectException equivalentes al 0,27% de sus ejecuciones. Ese reparto apunta a un servicio mayoritariamente sano, pero con interrupciones puntuales de conexión que son coherentes con rechazos temporales, indisponibilidad breve del destino o agotamiento intermitente de capacidad de atención. En producción, la mayoría de usuarios ingresará sin novedad, aunque un grupo pequeño podría encontrar intentos fallidos que obliguen a repetir la operación.

### 6. `chart_tps` — pico opcional

*108 palabras (tope 120) · 656 caracteres · generado 02:47:34*

> 5,16 TPS fue el promedio temporal de token, con máximo de 17,00 TPS y caudal consolidado de 4,78 por segundo sobre 8.600 muestras, lo que sugiere una demanda procesada sin caída sostenida. La mediana de 333 ms indica que la mitad de los usuarios recibe respuesta en 333 ms, mientras 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1.070 ms), comportamiento coherente con variaciones puntuales de latencia cuando sube el volumen. Los 23 errores, equivalentes al 0,27%, apuntan a afectación baja, no a degradación general del servicio. En producción, el usuario percibirá ingreso ágil en la mayoría de intentos, con demoras aisladas para una minoría.

### 7. `conclusions` — pico obligatorio

*178 palabras (tope 200) · 1087 caracteres · generado 02:47:46*

> 8.600 muestras de token dejaron un promedio de 443 ms, mediana de 333 ms y 0,27% de errores, lo que sugiere un servicio ágil en operación normal pero con inestabilidad puntual. La mitad de los usuarios completa en 333 ms o menos (mediana: 333 ms), 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms), 1 de cada 20 usuarios espera más de 657 ms (P95: 657 ms) y 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1.070 ms), comportamiento coherente con una experiencia aceptable para la mayoría.
>
> El máximo de 21.060 ms, 47,6 veces sobre su promedio, apunta a esperas intermitentes asociadas a conexión, lectura consistente con 23 respuestas org.apache.http.conn.HttpHostConnectException y picos de error de 33,33% en un intervalo. Aunque 8.577 respuestas fueron 200 y el caudal llegó a 17,00 TPS, token no queda listo para producción hasta estabilizar esos episodios, porque combinan errores reales con demoras superiores a 10 segundos. En producción, el usuario percibirá accesos rápidos la mayor parte del tiempo, pero algunos intentos fallarán o quedarán esperando demasiado.

### 8. `recommendations` — pico obligatorio

*201 palabras (tope 200) · 1280 caracteres · generado 02:47:58*

> 21.060 ms fue el máximo de token, 47,6 veces sobre su promedio de 443 ms, y apunta a esperas intermitentes de conexión o indisponibilidad temporal del destino.
>
> 1. Priorizar la validación de conectividad hacia el servicio que atiende token, porque los 23 errores, equivalentes al 0,27% de 8.600 muestras, terminaron como org.apache.http.conn.HttpHostConnectException. Ese patrón sugiere rechazos o fallas de conexión antes de recibir respuesta HTTP, por lo que debe revisarse disponibilidad del endpoint, reglas de red, balanceador y límites de conexión.
>
> 2. Ajustar timeouts y reintentos controlados para contener el impacto del pico de 21.060 ms, 47,6 veces sobre su promedio. La mitad de los usuarios espera más de 333 ms (mediana: 333 ms), pero 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1.070 ms), lo que sugiere degradación concentrada en una cola pequeña de solicitudes.
>
> 3. Correlacionar los intervalos con fallos y carga, ya que hubo 23 intervalos con al menos un fallo, un pico de error de 33,33% en un intervalo y máximo de 17,00 TPS. Esta combinación es coherente con sensibilidad de token ante ráfagas puntuales.
>
> En producción, el usuario percibirá ingresos normalmente rápidos, pero con fallas puntuales y esperas largas que pueden impedirle continuar.


---

## 4. Antes y después del mismo informe

| | Reporte 040 (primera corrida) | Reporte 041 (parcial) | Este (completo) |
|---|---|---|---|
| Secciones con formato español | 0 de 8 | 4 de 8 | **8 de 8** |
| Secciones que repiten el pico | 8 de 8 | 5 de 8 | **4 de 8, las obligatorias** |
| Latencia bien interpretada | no | sí | **sí** |
| Llamadas de IA | 8 | 4 | 8 |

---

## 5. Estado de la base

```
transaction_chart_analyses de esta ejecución: 8 filas, 8 secciones distintas,
8 con texto, 0 editadas a mano, todas regeneradas en esta corrida.
progress: {"done": 8, "total": 8, "persisted": 8, "pending": []}
```

Sin filas de prueba, sin duplicados, sin secciones vacías. El mini-informe de
`token` queda listo para que N4.7 lo pinte.

---

## 6. Coste

| Métrica | Valor |
|---|---|
| Llamadas de IA | **8** |
| Modelo | OpenAI `gpt-5.5` |
| Tiempo del bucle | **90,8 s** (`elapsed_ms: 90769`) |
| Tiempo total del POST | 92,0 s (incluye parsear el JTL) |
| Por sección | 9-12 s |
| Contador mensual | **125 → 133, +8 exactos** |

Más rápido que la corrida del 040 (108,8 s) con el mismo trabajo: variación normal
del proveedor, no un cambio nuestro.

El contador diario pasó de 12 a 8 porque se reinició al cambiar el día; los 8 que
muestra son los de esta corrida.

**Coste acumulado del mini-informe de `token`:** 21 llamadas — 8 en N4.6, 5 en
N4.6b (1 sonda + 4 secciones) y 8 en esta.

---

## 7. Cierre

Sin cambios de código: el endpoint y los prompts son los de `8245bff` (N4.6b).
Este reporte solo documenta su ejecución completa y el resultado.

**N4.7 sigue sin empezar.**
