# N4.6b — Latencia mal interpretada, formato numérico y repetición del pico

**Fecha:** 2026-08-19
**Commit:** `8245bff1b0af6e3a89a76d70f6696d458a9e2193` — *N4.6b: corregir interpretacion de latencia, formato numerico y repeticion del pico*
**Push:** `github` (`04e61cd..8245bff`, rama `backup-trabajo-local`). **`origin` (Azure) no se tocó.**
**Llamadas de IA:** **5** — 1 sonda del techo de `gpt-5.5` (16 tokens de salida) + 4 secciones regeneradas. Detalle en §6.
**Archivos tocados:** **3** (máximo permitido). **Backups:** `.bak_n46b_20260819_183244`.
**Esto NO es la pantalla.** N4.7 sigue sin empezar.

---

## 1. Los cuatro defectos y qué se hizo con cada uno

| # | Defecto del CTO sobre el reporte 040 §6 | Corrección |
|---|---|---|
| 1 | `chart_latency` invirtió la definición: atribuyó la descarga del cuerpo al procesamiento del servidor | Bloque `DEFINICION_LATENCIA` en el prompt de esa sección, con las tres igualdades y dos prohibiciones explícitas |
| 2 | "8.600" escrito como "8,600"; mezcla de "1.070 ms" con "1070 ms" | Los datos se entregan **ya formateados** por `_n()` en Python + regla `FORMATO_NUMERICO` como respaldo |
| 3 | El pico de 21.060 ms aparecía en las 8 secciones | `PICO_OBLIGATORIO` de 4 secciones; en las otras 4 se menciona solo si aporta |
| 4 | `gpt-5.5` caía al default de 4096 con warning | Entrada `"gpt-5.5": 16384` en `OPENAI_MAX_TOKENS`, verificada contra la API |

| Archivo | Diff |
|---|---|
| `backend/app/services/ai/transaction_report.py` | +72 / −21 |
| `backend/app/api/v1/endpoints/upload.py` | +9 / −1 (parámetro `sections` para regenerar solo lo afectado) |
| `backend/app/services/ai/gemini.py` | +5 / 0 (la entrada del modelo y su justificación) |

---

## 2. Defecto 1 — la latencia

### 2.1 Lo que se metió en el prompt de `chart_latency`

```
COMO SE LEE LA LATENCIA EN JMETER (definicion obligatoria, no la inviertas):
- Latency es el tiempo hasta el PRIMER BYTE de la respuesta: incluye la conexion,
  el envio de la peticion Y el procesamiento del servidor.
- Elapsed menos Latency es el tiempo de DESCARGA del cuerpo de la respuesta.
- Por tanto: una latencia alta apunta a servidor lento o red lenta de ida; una
  diferencia elapsed-latency alta apunta a respuestas pesadas o ancho de banda limitado.
- PROHIBIDO atribuir el tiempo de descarga al procesamiento del servidor.
- PROHIBIDO explicar la latencia como si fuera solo red: el procesamiento del
  servidor esta dentro de ella.
```

Va **solo** en esa sección: es la única que interpreta la resta. Verificado en §5.1
que las otras siete no la llevan.

### 2.2 El antes y el después, sobre la misma transacción

**ANTES** (reporte 040, generado 23:03:34):

> 443 ms de tiempo promedio en token contrastan con 370 ms de latencia promedio, por lo que 83,5% del tiempo apunta a red o espera previa y 73 ms, equivalentes a 16,5%, sugieren procesamiento efectivo del servidor. La mediana de 333 ms indica que la mitad de los usuarios queda por debajo de ese tiempo, mientras 1 de cada 10 usuarios espera mas de 529 ms (P90: 529 ms), 1 de cada 20 usuarios espera mas de 657 ms (P95: 657 ms) y 1 de cada 100 usuarios espera mas de 1,1 segundos (P99: 1070 ms). El maximo de 21060 ms, 47.6 veces sobre su promedio, apunta a esperas intermitentes fuera del procesamiento normal. En produccion, algunos clientes sentiran respuestas agiles, pero otros viviran demoras aisladas que deterioran la confianza en el ingreso.

**AHORA** (generado 23:36:11):

> 370 ms de latencia promedio frente a 443 ms de tiempo total deja 73 ms para descarga del cuerpo, por lo que el 83,5% del tiempo ocurre antes del primer byte y el 16,5% después. Esto apunta a que la espera principal está en conexión, envío de la petición y procesamiento del servidor, no en transferencia de respuesta; el máximo temporal de 1,3 segundos (1.332 ms), 3,6 veces sobre su promedio, sugiere episodios puntuales de espera previa. La mitad de los usuarios recibe respuesta en 333 ms o menos, 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms) y 1 de cada 100 espera más de 1,1 segundos (P99: 1.070 ms). En producción, la mayoría percibirá autenticación ágil, con demoras ocasionales que pueden sentirse como una pausa antes de ingresar.

### 2.3 Por qué el nuevo es correcto

| | Texto viejo | Texto nuevo |
|---|---|---|
| Los 370 ms de latencia | "apunta a red o espera previa" | "ocurre antes del primer byte… conexión, envío de la petición y procesamiento del servidor" |
| Los 73 ms de diferencia | "sugieren procesamiento efectivo del servidor" ❌ | "deja 73 ms para descarga del cuerpo" ✅ |
| Conclusión | El servidor solo trabaja 73 ms | "la espera principal está en conexión, envío de la petición y procesamiento del servidor, no en transferencia de respuesta" |

El viejo decía que el servidor procesaba en 73 ms y que 370 ms eran red. Es
exactamente al revés: los 370 ms **contienen** el procesamiento, y los 73 ms son
descarga. Con 8.600 muestras de un token que devuelve un JSON pequeño, el texto
nuevo es además coherente con lo que se espera de esa transacción.

Un detalle que confirma que la sección entendió su propio dato: el máximo que cita
ahora es **1.332 ms, el máximo de la serie de latencia**, no los 21.060 ms del
tiempo total. El viejo mezclaba las dos series.

---

## 3. Defecto 2 — formato numérico español

### 3.1 La decisión: formatear en Python, no pedírselo al modelo

Pediste evaluarlo y **sí es viable**, así que se hizo ahí. Función `_n()`:

```python
def _n(valor, dec: int = 0) -> str:
    """Numero a la espanola: miles con punto, decimales con coma."""
    txt = f"{float(valor or 0):,.{dec}f}"
    return txt.replace(",", "\x01").replace(".", ",").replace("\x01", ".")
```

Todas las cifras del bloque de métricas y del resumen de series pasan por ella.
El modelo ya no reformatea nada: **copia**. La regla `FORMATO_NUMERICO` del prompt
queda como cinturón de seguridad para las cifras que el modelo derive por su
cuenta (porcentajes calculados, ratios propios).

El origen del defecto era mecánico: el código anterior usaba `{valor:,}`, que en
Python es el formato inglés. Le estábamos entregando "8,600" y pidiéndole en el
mismo prompt que escribiera a la española.

### 3.2 El bloque que ahora recibe la IA

```
METRICAS REALES DE LA TRANSACCION "token" (prueba de scalability):
- Muestras ejecutadas: 8.600
- Tiempo promedio: 443 ms | Mediana: 333 ms | Minimo: 311 ms
- Percentil 90: 529 ms | Percentil 95: 657 ms | Percentil 99: 1.070 ms
- Tiempo maximo observado: 21.060 ms (47,6 veces su promedio)
- Errores: 23 (0,27% de sus muestras)
- Caudal de la transaccion: 4,78 por segundo
```

Comprobación de `_n()`:

```
    8600 -> 8.600        0.27 -> 0,27
   21060 -> 21.060        1.1 -> 1,1
    1070 -> 1.070        47.6 -> 47,6
    1666 -> 1.666        4.78 -> 4,78
```

### 3.3 Resultado en los textos regenerados

```
seccion                regenerada  cambio palabras  miles_ing  dec_ing pico21060
summary                      True    True      189         no       no      True
chart_response_times        False   False      124         no       no      True
chart_latency                True    True      134         no       no     False
chart_error_rate            False   False       92  ['8,600']['0.27%', '33.33%']      True
chart_codes                  True    True       86         no       no     False
chart_tps                    True    True      114         no       no     False
conclusions                 False   False      208  ['8,600']['0.27%', '33.33%']      True
recommendations             False   False      192  ['8,600']['0.27%', '5.16 TPS', '17.00 TPS', '1.1 segundos']      True
```

**Las 4 regeneradas: cero miles a la inglesa, cero decimales con punto.** Escriben
8.600, 8.577, 0,27%, 99,73%, 5,16 TPS, 17,00 TPS, 1.070 ms, 1,1 segundos.

**Las 4 no regeneradas conservan el defecto**, porque su texto es el del 040 y no
se volvió a pagar por él. La base tiene ahora un informe mixto; §7 explica qué
hacer con eso.

Único resto de formato inglés en los prompts: el contraejemplo dentro de la propia
regla ("PROHIBIDO el formato ingles (8,600 muestras, 1.1 segundos)"), que es el
patrón "ASI NO" que ya usa el `SYSTEM_PROMPT` desde C2. La zona de datos está
limpia en las 8 secciones.

---

## 4. Defecto 3 — repetición del pico

`PICO_OBLIGATORIO = ("summary", "chart_response_times", "conclusions", "recommendations")`.

- En esas 4 el prompt dice: *"El maximo de 21.060 ms y su ratio (47,6 veces su promedio) son OBLIGATORIOS en esta seccion."*
- En las otras 4: *"El maximo de 21.060 ms se menciona SOLO si aporta a esta grafica en concreto; si no aporta, no lo repitas: otras secciones del informe ya lo tratan."*

**GRAF1 sigue intacta:** el pico es obligatorio en el resumen, en la gráfica de
tiempos de respuesta, en las conclusiones y en las recomendaciones. Es imposible
que desaparezca del mini-informe.

Resultado real, en las 3 secciones opcionales regeneradas:

| Sección | ¿Cita 21.060 ms? | Qué hizo en su lugar |
|---|---|---|
| `chart_latency` | **No** | Cita el máximo de SU serie: 1,3 segundos (1.332 ms), 3,6 veces sobre su promedio |
| `chart_codes` | **No** | Se queda en el reparto: 8.577 de 8.600 en 200, 23 rechazos de conexión, 99,73% de éxito |
| `chart_tps` | **No** | Usa el ratio propio de su gráfica: 17,00 TPS máximo, 3,3 veces sobre su promedio |
| `summary` (obligatoria) | **Sí** | "el máximo de 21.060 ms, 47,6 veces su promedio" |

Las tres opcionales no solo dejaron de repetir: **cada una encontró el ratio que
sí le pertenece**. Eso es lo que la repetición estaba tapando.

---

## 5. Defecto 4 — `gpt-5.5` en `OPENAI_MAX_TOKENS`

### 5.1 El doble uso, verificado antes de tocar nada

`OPENAI_MAX_TOKENS` la importa también `script_ai.py` (líneas 55-56) y la usa en
tres sitios. Efecto de añadir la entrada:

| Consumidor | Antes | Después |
|---|---|---|
| `gemini.py::_openai_max_tokens_for` (los 12 análisis globales + las 8 del mini-informe) | 4096 + warning | 16384 |
| `script_ai.py:1726` (generación de JMX) | 4096 + warning | 16384 — **corrige la misma trampa HF18b en el Script Designer** |
| `script_ai.py:1719` (refine, `min(override, ceiling)`) | 4096 | 16384 |
| `script_ai.py:2336` (`get(model, REFINE_OPENAI_FALLBACK_MAX_TOKENS)`) | 16384 por fallback | 16384 por entrada — **sin cambio** |

**No se modificó ninguna entrada existente.** El dict pasa de 16 a 17 claves.

### 5.2 El valor no se adivinó: se probó contra la API

```
modelo: gpt-5.5 | parametro de tokens: {'max_completion_tokens': 16384}
limite 16384: ACEPTADO -> respuesta='OK' finish=stop
   usage: 11 in / 16 out
```

La API acepta 16.384 y responde `finish_reason=stop`. 16384 es además el valor
conservador que B6.2 ya fijó para el resto de la familia `gpt-5`; su techo real
documentado es mayor y subirlo es seguro si algún análisis sale corto.

### 5.3 El warning desapareció

```
  gpt-5.5            -> 16384
  gpt-5              -> 16384
  gpt-4o             -> 16384
  modelo-inventado   -> 4096   <- WARNING: sin entrada en OPENAI_MAX_TOKENS...
  entradas en el dict: 17
```

`gpt-5.5` resuelve su techo en silencio; el aviso solo salta con un modelo que de
verdad falta, que es para lo que se escribió en B6.

---

## 6. Coste de IA de este sprint

| Concepto | Llamadas | Detalle |
|---|---|---|
| Sonda del techo de `gpt-5.5` | 1 | prompt de 11 tokens, 16 de salida. Fuera del contador de la app: fue directa al SDK |
| Regeneración de 4 secciones | 4 | `summary`, `chart_latency`, `chart_codes`, `chart_tps` |
| **Total** | **5** | dentro del límite de 4 regeneraciones + la sonda declarada |

```
POST …/transaction-report?label=token&sections=summary,chart_latency,chart_codes,chart_tps
{"total":4,"generated":4,"failed":0,"elapsed_ms":45230,"label":"token"}
```

**45,2 s las cuatro** (~11 s por sección, igual que en N4.6). Contadores de cupo:
mensual **121 → 125, exactamente +4**; la sonda no pasa por ellos porque no usa
`GeminiAnalyzer`.

Para poder pagar solo lo afectado se añadió el parámetro `sections=` al POST
(coma-separado, validado contra `SECTIONS`, 400 si llega un nombre inventado).
Sin él, corregir una sección costaba las ocho. N4.7 lo hereda gratis: el botón
"rehacer esta sección" ya tiene endpoint.

Idempotencia del camino parcial, verificada: la tabla sigue con **8 filas y 8
secciones distintas**, 4 con marca de tiempo nueva (23:35-23:36) y 4 con la
original (23:03-23:04). Regenerar un subconjunto es UPDATE de ese subconjunto.

---

## 7. Estado actual del mini-informe de `token`

| Sección | Texto | Formato español | Pico |
|---|---|---|---|
| `summary` | **nuevo** | ✅ | obligatorio, presente |
| `chart_response_times` | del 040 | ❌ | obligatorio, presente |
| `chart_latency` | **nuevo** | ✅ | opcional, ausente (correcto) |
| `chart_error_rate` | del 040 | ❌ | opcional, presente (sobra) |
| `chart_codes` | **nuevo** | ✅ | opcional, ausente (correcto) |
| `chart_tps` | **nuevo** | ✅ | opcional, ausente (correcto) |
| `conclusions` | del 040 | ❌ | obligatorio, presente |
| `recommendations` | del 040 | ❌ | obligatorio, presente |

Las 8 siguen sin palabras prohibidas y sin markdown.

Dejar las otras cuatro con el texto viejo fue decisión de presupuesto, no
descuido: el encargo topaba en 4 llamadas y las 4 elegidas son las que demuestran
las tres correcciones (la latencia invertida, el formato, y el pico
desapareciendo donde no aporta pero quedándose donde es obligatorio).

Cuando quieras el informe entero coherente, es una llamada de 8 secciones (~110 s,
8 peticiones):

```
POST /api/v1/executions/115346ea-fcf6-4951-bec1-9495e3c035f5/transaction-report?label=token
```

---

## 8. Los otros dos textos regenerados

### `summary` — nuevo (la sección con pico obligatorio)

> 8.600 muestras de token cerraron con promedio de 443 ms, mediana de 333 ms y mínimo de 311 ms, lo que sugiere una respuesta base ágil para la mayoría de solicitudes. La mitad de los usuarios queda en 333 ms (mediana: 333 ms), 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms) y 1 de cada 20 usuarios espera más de 657 ms (P95: 657 ms), comportamiento coherente con un servicio mayormente estable bajo carga ordinaria.
>
> 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1.070 ms), y el máximo de 21.060 ms, 47,6 veces su promedio, apunta a bloqueos intermitentes o intentos fallidos de conexión. Los 23 errores, equivalentes al 0,27% de sus muestras, y las 23 respuestas org.apache.http.conn.HttpHostConnectException sugieren indisponibilidad puntual del destino o saturación transitoria en la conexión. El caudal de 4,78 por segundo, con serie promedio de 5,16 TPS y máximo de 17,00 TPS, no explica por sí solo el salto, lo que refuerza una afectación episódica. En producción, algunos clientes obtendrán el token rápido, pero otros enfrentarán demoras largas o intentos fallidos que frenan el ingreso al servicio.

### `chart_codes` — nuevo (pico opcional, no lo cita)

> 8.577 de 8.600 respuestas de token terminaron en 200, mientras 23 quedaron como Non HTTP response code: org.apache.http.conn.HttpHostConnectException, equivalentes al 0,27% de sus muestras. Ese reparto sugiere una salud funcional mayoritariamente estable, porque el servicio responde correctamente en el 99,73% de los casos, pero los 23 rechazos de conexión apuntan a cortes puntuales de disponibilidad, resolución de destino o aceptación de conexiones bajo carga. En producción, el usuario final percibirá la mayoría de accesos exitosos, pero una fracción pequeña verá intentos fallidos que interrumpen su continuidad.

### `chart_tps` — nuevo (pico opcional, usa el ratio de su propia gráfica)

> 5,16 TPS promedio y máximo de 17,00 TPS, 3,3 veces sobre su promedio, sugieren una carga con ráfagas y no un caudal completamente plano. El tiempo promedio de 443 ms y la mediana de 333 ms son coherentes con una transacción que responde bien mientras opera en su nivel base; 1 de cada 10 usuarios espera más de 529 ms (P90: 529 ms) y 1 de cada 20 usuarios espera más de 657 ms (P95: 657 ms), lo que apunta a degradación moderada en los momentos de mayor presión. 1 de cada 100 usuarios espera más de 1,1 segundos (P99: 1.070 ms), y en producción algunos clientes percibirán demoras puntuales al solicitar el acceso.

---

## 9. Lo que este sprint NO hizo

- **No regeneró las 4 secciones restantes** (§7). El informe está mixto a propósito.
- **No tocó el `SYSTEM_PROMPT`.** Las tres reglas nuevas viven en
  `transaction_report.py`, igual que la regla UX de N4.6: los 12 análisis globales
  siguen exactamente como los validaste en C2.
- **No verificó las reglas nuevas con Gemini**, solo con OpenAI `gpt-5.5`.
- **No añadió endpoint de edición manual** de una sección; sigue pendiente desde N4.6.
- **No revisó si el resto del sistema escribe números a la inglesa.** El defecto se
  corrigió en el mini-informe por transacción; los 12 análisis globales usan sus
  propios prompts y no se auditaron. Candidato a sprint aparte.
- **No es la pantalla.** N4.7 sigue sin empezar.

---

## 10. Cierre

```
$ git log -1 --format='%H %s'
8245bff1b0af6e3a89a76d70f6696d458a9e2193 N4.6b: corregir interpretacion de latencia, formato numerico y repeticion del pico

$ git push github HEAD
   04e61cd..8245bff  HEAD -> backup-trabajo-local
```

`py_compile` limpio en los 3 archivos, `docker restart jmeter_backend` sin build,
arranque sin trazas. Los dos scripts de comprobación se borraron del repositorio.

**Parado aquí.**
