Commit base `9958ca0` · 30 de septiembre de 2026 · R2, la corrida con IA antes y después

# R2 — la corrida con IA, antes y después

Este reporte **no copia ningún texto de cliente**. Los textos, uno al lado del otro, están en
`C:\proyectos\Kinetix_pruebas\r2\comparacion.html`, **fuera del repositorio**. Aquí van las cifras.
**El juicio de si el texto es mejor es de Fredy.**

---

## 1. Qué se corrió

| | |
|---|---|
| Modelo | **openai / gpt-5.5**, comprobado antes de empezar con `/ai-config/estado` → `ok:true`. La configuración de IA no se ha tocado |
| «Antes» | La copia de HEAD `41cf237` en `/tmp/r2_antes/backend`, idéntica al tar de `Kinetix_pruebas\r2\` (misma huella de `gemini.py`, 147 archivos) |
| «Después» | El código actual, con R2 (`243900c`). La suite `r2_series.py` pasa entera antes de correr |
| Ejecuciones | `35ca5b92` «Nova capa media» (carga, 8,28 % de error, 30 min, 4 transacciones con informe) · `42334732` «prueba 6» (41,32 %, 5 min, 3 transacciones) · `1e592533` «prueba avianca» (0,06 %, 3 min, 4 transacciones) |
| Cómo | `backend/pruebas_e2e/corrida_r2.py`, en proceso, **una ejecución tras otra y en serie**: antes → después por cada ejecución |
| Sin escribir en la base | Conexión propia con `default_transaction_read_only=on` y sin autoflush (se comprobó que la base rechaza la escritura), más el colector que sustituye a `_upsert`, el único `commit` del camino. Acaba en `rollback` |

**Resultado del lote:** seis corridas completas entre las 11:08 y las 11:53. **Ni un 429, ni un fallo de
tiempo, ni un transitorio.**

### 1.1 El intento fallido

Hubo un primer intento a las 10:59 que **perdió por un fallo mío** la corrida «antes» de Nova entera:
34 llamadas reales. El script leyó `ex.name` después del `rollback`, SQLAlchemy lanzó
`DetachedInstanceError` y el JSON no llegó a escribirse.

Lo que se cambió antes de volver a correr:

- el nombre se lee al principio;
- ante cualquier excepción se guarda lo que haya (`parcial: true`);
- un modo en seco (`R2_SECO=1`) recorre el camino entero sin IA. Se probaron así las dos versiones
  antes de relanzar.

**Coste del error:** 34 llamadas de más, así que en total se hicieron **226 llamadas**, no 192. Y tiene una consecuencia sobre la caché de Nova, que explica §4.

---

## 2. Respaldo

| Ejecución | Antes | Después |
|---|---|---|
| `35ca5b92` Nova | **0** secciones | **0** |
| `42334732` prueba 6 | **0** | **0** |
| `1e592533` prueba avianca | **0** | **0** |

Ninguna sección salió de `FallbackAnalyzer`. Se comprobó de dos formas: si `_generate` devolvió `None`, y
si el texto lleva alguna de las plantillas del respaldo (`origen.PLANTILLAS`).

**Redirecciones** no se generó en ninguna de las dos versiones de ninguna ejecución, porque ninguna tiene
redirecciones. Figura como *no aplica*, no como respaldo. Se comparan **34 + 28 + 34 = 96 secciones**.

---

## 3. Las cifras

### 3.1 Llamadas, tiempo y tokens

| Ejecución · versión | Llamadas | Segundos | Entrada | …en caché | Salida | …de razonamiento |
|---|---|---|---|---|---|---|
| Nova · antes | 34 | 441,7 | 79.986 | 54.784 | 30.208 | 21.977 |
| Nova · después | 34 | 476,8 | 117.669 | **0** | 35.930 | 26.430 |
| prueba 6 · antes | 28 | 357,9 | 66.888 | 21.504 | 24.302 | 17.398 |
| prueba 6 · después | 28 | 397,0 | 95.960 | 1.792 | 28.179 | 20.407 |
| prueba avianca · antes | 34 | 471,6 | 78.541 | 35.840 | 32.168 | 24.184 |
| prueba avianca · después | 34 | 503,2 | 113.620 | 1.792 | 38.601 | 29.477 |
| **Total antes** | **96** | **1.271,2** | **225.415** | **112.128** | **86.678** | **63.559** |
| **Total después** | **96** | **1.377,0** | **327.249** | **3.584** | **102.710** | **76.314** |
| **Diferencia** | = | **+8,3 %** | **+45,2 %** | **−96,8 %** | **+18,5 %** | +20,1 % |

- **Las llamadas son las mismas** (R-D11 se cumple: 10 generales + 6 por transacción).
- **El tiempo** sube un 8 %: unos 35 s por informe.
- **La entrada** sube un 45 %. Es la serie resumida, que es lo que R2 añade.
- **La salida** sube un 18,5 %. Tres cuartas partes son razonamiento, que no se ve en el texto: los
  textos visibles miden casi lo mismo (90.445 caracteres antes, 91.056 después).

### 3.2 Coste, con la tarifa como fórmula

Con `Pe` = precio de la entrada normal, `Pc` = precio de la entrada en caché y `Ps` = precio de la salida,
todo en dólares por millón de tokens. OpenAI cobra el razonamiento como salida.

```
coste = [ (entrada − caché) × Pe  +  caché × Pc  +  salida × Ps ] / 1.000.000

antes   = ( 113.287 × Pe  +  112.128 × Pc  +   86.678 × Ps ) / 10^6
después = ( 323.665 × Pe  +    3.584 × Pc  +  102.710 × Ps ) / 10^6
```

Son las tres ejecuciones juntas. Por informe, dividir entre tres.

**La entrada que se paga a precio completo casi se triplica: ×2,86.** De esa subida:

- **~101.800 tokens son la serie**: la entrada total sube de 225.415 a 327.249.
- **~108.500 tokens son la caché perdida**: el «antes» pagó a `Pc` 112.128 tokens que el «después» paga
  a `Pe`.

Si el «después» se cacheara en la misma proporción que el «antes» (49,7 %), pagaría a `Pc` unos 162.700
tokens y a `Pe` unos 164.600. **La diferencia entre cachear y no cachear es de ~159.100 × (Pe − Pc) / 10^6
por cada tres informes.** Es la parte del sobrecoste que se puede recuperar sin tocar lo que dice el
prompt.

---

## 4. La caché: por qué el «después» pasó de 54,8 k a 0

**La hipótesis de partida era que la serie va al principio y rompe el prefijo fijo. Los datos no la
sostienen.**

| Qué se miró | Antes | Después |
|---|---|---|
| Primeros caracteres del prompt | `UNIDAD DE MEDIDA: …` | **los mismos** |
| Mensaje de sistema | constante | constante. R2 solo le añadió la regla 15, «sin disculpas» |
| Prefijo común de una sección de transacción con las anteriores | 1.160–1.310 caracteres | **1.370–2.470**: más largo |
| Prefijo común en tokens, estimado (regresión de los tokens reportados sobre los caracteres; `tiktoken` no está en el contenedor y no se ha instalado) | mínimo ~1.720, mediana ~2.030 | mínimo ~1.720, mediana ~2.170 |
| Secciones de transacción con caché | **56 de 66** (siempre 1.792 tokens) | **0 de 66** |
| Secciones generales con caché | 6 de 30, y las 6 son de Nova | 2 de 30 |

**Por separado:**

- **La caché del «antes» de Nova es en parte herencia del intento fallido.** Su primera llamada ya salió
  con 2.816 tokens en caché, y solo Nova tiene caché en las secciones generales (6 de 10; las otras dos
  ejecuciones, 0 de 10). Son los mismos prompts que había mandado 9 minutos antes el intento de §1.1.
- **La caché de las secciones de transacción del «antes» es propia.** «prueba 6» y «prueba avianca» no se
  habían corrido nunca y se cachean igual (12/18 y 20/24). Es el prefijo de 1.792 tokens que comparten
  el mensaje de sistema y la cabecera de datos de la transacción.
- **En el «después», ese prefijo común existe y es más largo, y aun así no se cachea.** Supera con creces
  el mínimo de 1.024 tokens de OpenAI.

### 4.1 La prueba controlada (4 llamadas, con tu visto bueno)

`backend/pruebas_e2e/prueba_cache_r2.py`, después de terminar el lote:

- **Qué se mandó:** el mensaje de sistema de cada versión con el prompt de la llamada 13 de Nova
  (latencia de la primera transacción), **dos veces seguidas**, a 2 s de distancia.
- **Cómo:** mismo modelo y mismos parámetros que `_generate`, con la salida limitada a 64 tokens.
- **Sin tocar nada:** no pasa por `_generate`, así que no toca contadores, circuito ni buzón. La clave
  se lee en una sesión de solo lectura.

| Versión | Llamada | Tokens de entrada | En caché |
|---|---|---|---|
| antes | 1.ª | 2.331 | 1.792 |
| antes | 2.ª (el mismo texto) | 2.331 | 1.792 |
| después | 1.ª | 3.383 | **2.816** |
| después | 2.ª (el mismo texto) | 3.383 | **2.816** |

### 4.2 Qué demuestra, y la causa

1. **El prompt del «después» sí se cachea, y más que el del «antes».** Repetido tal cual, reutiliza
   2.816 tokens, el 83 %. **No hay nada en su contenido que lo impida.** La hipótesis de que la serie
   rompe el prefijo queda descartada dos veces: por el prefijo común (tabla de arriba) y por esta
   prueba.
2. **La caché del «después» se escribió durante el lote.** La 1.ª llamada de cada par ya salió con
   caché: es el mismo texto que el lote había mandado unos 45 minutos antes, y seguía guardado.
3. **La caché se reutiliza por bloques, no hasta el último token.** Ni repitiendo el mismo texto se
   reaprovecha entero: 1.792 de 2.331 en el «antes» y 2.816 de 3.383 en el «después».

**La causa, hasta donde llega lo medido:** en el lote, cada sección del «después» **guardó** su prefijo,
pero **ninguna sección distinta encontró un bloque guardado que coincidiera con el suyo**, aunque
comparten con las anteriores más de 1.024 tokens. En el «antes», el bloque de 1.792 tokens sí era común
a todas las secciones de transacción y se reutilizaba de una a otra. **Es una cuestión de dónde caen los
cortes de los bloques respecto al punto en que dos secciones empiezan a diferenciarse, no de que el
texto no se pueda cachear.**

**Lo que no está comprobado:** el tamaño exacto en tokens del mensaje de sistema y del prefijo común.
La regresión de §4 da ~1.720 en las dos versiones y no distingue bien, porque las cifras se tokenizan
más densas que el texto. Para cerrarlo haría falta contar los tokens de verdad: `tiktoken`, que no está
en el contenedor, o una llamada con solo el mensaje de sistema.

**No se arregla aquí: va al bloque de prompts.** La vía que sugiere la prueba es la estructura del
prompt:

- lo común a todas las secciones (sistema y cabecera de la transacción) lo bastante largo como para
  cubrir un bloque entero, y todo delante;
- lo propio de cada sección (instrucción, lectura base y serie), detrás.

---

## 5. Las disculpas (R-D14)

Medidas con el detector **actual** (`estilo.detectar_estilo`, tipo `disculpa`) en las dos versiones:
la misma vara para las dos.

| Ejecución | Antes | Después |
|---|---|---|
| Nova | 1 | **0** |
| prueba 6 | 1 | **0** |
| prueba avianca | 0 | **0** |
| **Total** | **2** | **0** |

Las dos del «antes» están resaltadas en ámbar en `comparacion.html`.

---

## 6. ¿Las conclusiones dicen cuándo, cuánto y en qué transacción?

Es lo que faltaba en el diagnóstico 120. Se mide **frase a frase** en las conclusiones:

- **cuándo**: `min M:SS`, o una hora `hh:mm(:ss)`;
- **cuánto**: una cifra con su unidad;
- **en qué transacción**: el nombre de una de las transacciones con informe, con o sin su número.

| Ejecución · versión | Frases | Con cuándo | Con cuánto | Con transacción | **Las tres a la vez** |
|---|---|---|---|---|---|
| Nova · antes | 24 | **0** | 8 | 6 | 0 |
| Nova · después | 24 | **2** | 11 | 5 | 0 |
| prueba 6 · antes | 34 | **0** | 14 | 6 | 0 |
| prueba 6 · después | 33 | **3** | 14 | 7 | 0 |
| prueba avianca · antes | 24 | **0** | 11 | 7 | 0 |
| prueba avianca · después | 24 | **5** | 10 | 6 | **1** |

- **Antes, ninguna conclusión decía cuándo pasó nada. Después lo dicen 10 frases de 81.**
- Pero **solo una frase de las tres ejecuciones reúne las tres cosas**. La mejora del «cuándo» está en
  las conclusiones; la frase que lo ata todo, casi nunca.
- Las frases con «cuándo» de las dos versiones están en `comparacion.html`, en un bloque al principio de
  cada ejecución, con el momento resaltado en verde. En el texto completo de las conclusiones, también.

**Es un recuento por patrones, no una lectura.** Una frase como «al final de la prueba» no cuenta como
cuándo, y un nombre de transacción abreviado a mano no cuenta como transacción.

### 6.1 ¿En qué fase de la prueba cae cada momento citado? (para el bloque de prompts, sin corregir)

`backend/pruebas_e2e/fases_r2.py` saca las fases de cada JTL con los hilos activos (`allThreads`), por
segundo:

- **rampa de subida:** hasta alcanzar el 95 % del máximo de hilos;
- **meseta:** mientras se está en el 95 % o más;
- **rampa de bajada:** desde la última vez en el 95 % hasta el final.

Después clasifica cada momento que citan las conclusiones del «después»:

- `min M:SS`, y el `M:SS` suelto que cierra un intervalo («entre min A y B»), como minuto de la prueba;
- `hh:mm:ss`, como hora del reloj, convertida con el inicio de la línea de tiempo.

| Ejecución | Fases |
|---|---|
| Nova (30:00, máx. 4 hilos) | subida 0:00–3:14 · meseta 3:14–30:00 · **sin rampa de bajada**: termina a plena carga |
| prueba 6 (5:01, máx. 5 hilos) | subida 0:00–2:19 · meseta 2:19–4:24 · bajada 4:24–5:01 |
| prueba avianca (3:00, máx. 50 hilos) | subida 0:00–0:27 · meseta 0:27–2:59 · bajada de un segundo |

| Ejecución | Momento citado | Fase |
|---|---|---|
| Nova | min 0:05 | **rampa de subida** |
| Nova | min 10:18 · 10:19 (intervalo) | meseta |
| Nova | min 29:59 | meseta, pero es **el último segundo de la prueba** |
| prueba 6 | min 0:01 (dos veces) | **rampa de subida** |
| prueba 6 | min 2:30 · 3:21 (intervalo) · min 3:45 · min 4:11 | meseta |
| prueba 6 | min 5:01 (dos veces, una como fin de intervalo) | **rampa de bajada** (el último segundo) |
| prueba avianca | min 0:29 · min 0:30 · 20:49:00 (= 0:29) | meseta, a **2-3 s del final de la subida** |
| prueba avianca | min 2:00 · 2:01 (×2) · 2:02 · 2:07 (×2) · 20:50:32 · 20:50:38 | meseta |

**En total, 23 momentos citados:**

- **5 caen en una rampa**: 3 en la de subida y 2 en la de bajada.
- **18 caen en la meseta**, pero **4 de ellos están en un borde**: 3 a 2-3 s de acabar la subida y el
  último segundo de Nova.
- Solo **14 caen de lleno en la carga sostenida**, que es donde un momento dice algo del sistema bajo
  carga.

**Lo que asoma, y no se corrige aquí:**

- Varios de los momentos de rampa son **el primer y el último fallo** («de min 0:01 hasta min 5:01»,
  «min 0:05 … min 29:59»). La serie da el primer y el último fallo, y el modelo los cita tal cual: dicen
  *que* hubo fallos durante toda la prueba, no *cuándo* se concentraron.
- **El prompt no le dice al modelo dónde están las rampas.** Si la serie marcara las fases, el modelo
  podría separar lo que pasa al subir la carga de lo que pasa con la carga sostenida.

Va al bloque de prompts.

---

## 7. Lo que no se pudo comprobar

- **Si el texto es mejor.** Es tuyo: `comparacion.html`.
- **El tamaño exacto en tokens del prefijo común** (§4.2). La prueba controlada descartó el contenido
  como causa, pero la última pieza necesita contar tokens de verdad.
- **Las fases se sacan con un umbral del 95 % de los hilos.** Con otro umbral, los momentos de los bordes
  cambiarían de fase.
- **El coste en dólares.** Sin tarifa; queda la fórmula de §3.2.
- **La variabilidad del modelo.** Hay una corrida por versión y ejecución. Una diferencia pequeña, como
  el +8 % de tiempo o el ±1 en disculpas, puede ser ruido. No se repitió para no gastar más llamadas.
- **Gemini.** Todo es con gpt-5.5.

---

## 8. Archivos

| Dónde | Qué |
|---|---|
| `backend/pruebas_e2e/corrida_r2.py` | Recibe la ejecución como argumento, cuenta tokens por intento, detecta el respaldo, para en el primer 429 o transitorio, conexión de solo lectura, modo en seco, guarda lo parcial |
| `backend/pruebas_e2e/comparar_r2.py` | Nuevo: `comparacion.html` y `resumen.json` desde los seis JSON. No llama a la IA ni abre la base |
| `backend/pruebas_e2e/prueba_cache_r2.py` | Nuevo: la prueba controlada de la caché (§4.1). 2 llamadas por ejecución del script |
| `backend/pruebas_e2e/fases_r2.py` | Nuevo: fases de la prueba por hilos activos y la fase de cada momento citado (§6.1). Sin IA; lee el JTL en solo lectura |
| `C:\proyectos\Kinetix_pruebas\r2\` (fuera del repositorio) | `comparacion.html`, `resumen.json`, los seis `corrida_*.json` (con prompts y respuestas) y los dos logs del lote |

## 9. Pendiente de tu decisión

1. **Tu lectura de `comparacion.html`**: si R2 queda validada o hay que ajustar algo.
2. **`docs/reports/repo/`**: los reportes que alguien movió allí, con el 132 y el token maestro en claro.
   Sigue en el árbol y sin versionar.
