Commit base `20b9ec5` · 30 de septiembre de 2026 · Bloque 2.4 — la corrida con IA de la estructura (2.2) y la guía de estilo (2.3)

# Bloque 2.4 — la versión nueva frente al «después» del 136

Este reporte **no copia ningún texto de cliente**. Los textos, uno al lado del otro por sección, están en
**`C:\proyectos\Kinetix_pruebas\r2\comparacion2.html`**, fuera del repositorio. Aquí van las cifras.
**El juicio de si el texto es mejor es de Fredy.**

---

## 1. Qué se corrió

| | |
|---|---|
| Modelo | **openai / gpt-5.5**, `reasoning_effort` **medium** (sin tocar). Comprobado antes con `estado_ia.comprobar` → `ok` |
| Izquierda | El «después» del 136 (R2, commit `243900c`), ya guardado: `corrida_despues_<id>.json` |
| Derecha | El código de ahora: 2.1 (fases), 2.2a/2.2b (estructura e incoherencias) y 2.3 (guía de estilo) |
| Ejecuciones | `35ca5b92` Nova · `42334732` prueba 6 · `1e592533` prueba avianca: las mismas del 136 |
| Cómo | `corrida_r2.py` en proceso, en serie, base en **solo lectura** y acabando en `rollback`. Antes, una pasada en seco (`R2_SECO=1`) |
| Solo la versión nueva | 96 llamadas; el lote terminó a las 15:32 |

**Condiciones de parada: ninguna se cumplió.** Todas las suites en verde, **ninguna sección cayó al
respaldo**, no se tocó ningún archivo protegido ni la rama web del HTML.

---

## 2. Respaldo

| Ejecución | Después del 136 | Versión nueva |
|---|---|---|
| Nova | 0 | **0** |
| prueba 6 | 0 | **0** |
| prueba avianca | 0 | **0** |

---

## 3. Tokens, caché y tiempo

| Ejecución · versión | Llamadas | Segundos | Entrada | …en caché | Salida | …razonamiento |
|---|---|---|---|---|---|---|
| Nova · 136 | 34 | 476,8 | 117.669 | 0 | 35.930 | 26.430 |
| Nova · nueva | 34 | **431,2** | 134.022 | **48.896 (36,5 %)** | **26.540** | 18.286 |
| prueba 6 · 136 | 28 | 397,0 | 95.960 | 1.792 | 28.179 | 20.407 |
| prueba 6 · nueva | 28 | **345,7** | 112.476 | **34.816 (31,0 %)** | **20.228** | 13.670 |
| prueba avianca · 136 | 34 | 503,2 | 113.620 | 1.792 | 38.601 | 29.477 |
| prueba avianca · nueva | 34 | **407,1** | 128.567 | **46.080 (35,8 %)** | **24.002** | 16.237 |
| **Total 136** | 96 | 1.377,0 | 327.249 | 3.584 (1,1 %) | 102.710 | 76.314 |
| **Total nueva** | 96 | **1.184,0** | 375.065 | **129.792 (34,6 %)** | **70.770** | **48.193** |
| **Diferencia** | = | **−14,0 %** | +14,6 % | ×36 | **−31,1 %** | **−36,8 %** |

- **La entrada sube un 14,6 %**: el bloque de la ejecución viaja en las 16 llamadas y el sistema lleva
  ahora la guía y los dos ejemplos.
- **La entrada que se paga a precio completo baja un 24,2 %** (de 323.665 a 245.273), porque un tercio
  sale de la caché.
- **La salida baja un 31 %** y el razonamiento un 37 %: textos más cortos y más claros de pedir.
- Con la fórmula del 136 §3.2, el coste por tres informes pasa de
  `(323.665·Pe + 3.584·Pc + 102.710·Ps)/10^6` a `(245.273·Pe + 129.792·Pc + 70.770·Ps)/10^6`: **baja en las
  tres partidas que se pagan caras**.

### 3.1 Qué llamadas usan la caché

**45 de las 96**, siempre con 2.816 o 3.840 tokens. El patrón es el mismo en las tres ejecuciones:

| Llamadas | Caché |
|---|---|
| Las 9 primeras del informe general (resumen, errores, 6 gráficas, conclusiones) | **ninguna** |
| Recomendaciones | **sí**, 3.840: comparte con conclusiones casi todo el mensaje |
| Por transacción: resumen y la primera gráfica | ninguna |
| Por transacción: las otras cuatro | **sí**, 2.816 |

Medido sobre los prompts: las gráficas generales comparten con la anterior ~3.740 caracteres del mensaje
del usuario (bloque + lectura base) y **no** reutilizan nada; las de una transacción comparten ~4.870
(bloque + cabecera + lectura base) y **sí**. **La reutilización aparece solo cuando el tramo común es
bastante más largo que el sistema y el bloque.** No está comprobado dónde está ese umbral ni por qué el
sistema solo (idéntico en las 96) no se reutiliza. Dos vías, sin probar: alargar lo común de las
generales (la tabla de transacciones delante, por ejemplo) o el parámetro `prompt_cache_key` de OpenAI.

---

## 4. Los textos

Secciones = las 8 generales que no son síntesis más las 6 de cada transacción (90 por versión).
Párrafo = línea no vacía. Cifra = número, sin contar los de los nombres de transacción.

| Medida | 136 (Nova · p6 · avianca) | Nueva (Nova · p6 · avianca) |
|---|---|---|
| Secciones de **un solo párrafo** | 7 · 4 · 4 de 32/26/32 (**17 %**) | 32 · 26 · 32 (**100 %**) |
| Párrafos por sección (media) | 2,12 · 2,12 · 2,16 | **1,00 · 1,00 · 1,00** |
| Palabras por sección (mín–máx) | 108–236 · 110–230 · 99–237 | **127–172 · 139–171 · 128–161** |
| **Cifras por sección** | 28,7 · 30,3 · 28,6 | **15,1 · 14,4 · 15,8** |
| Cifras por párrafo | 13,5 · 14,3 · 13,3 | 15,1 · 14,4 · 15,8 |
| Disculpas (detector actual) | 0 · 0 · 0 | **0 · 0 · 0** |

- **Las cifras por sección bajan a la mitad; por párrafo, no**: había dos párrafos por sección y ahora
  uno. **Siguen siendo unas 15 cifras en 150 palabras.** El ejemplo de Fredy lleva **4**. Es lo que más
  lejos queda de la guía; la lectura de `comparacion2.html` dirá si pesa.
- Los minutos cuentan como cifra (`min 3:14` es una).

### 4.1 Conclusiones y recomendaciones

| | 136 | Nueva |
|---|---|---|
| Conclusiones: forma | 6 párrafos numerados | **6 viñetas «•»** en las tres |
| Conclusiones: palabras · cifras | 424–488 · **52–78** | **218–246 · 0–2** |
| Recomendaciones: forma | párrafos por prioridad (CRÍTICAS/ALTAS/MEDIAS), 0 viñetas | **6–7 viñetas «•»** |
| Recomendaciones: palabras · cifras | 419–455 · **43–56** | **233–261 · 0–2** |

### 4.2 Momentos citados y rampas

Se cuentan en **todas** las secciones (en el 136 solo se miraban las conclusiones), con las fases de
`services/ai/fases.py`: `min M:SS`, `M:SS` de fin de intervalo y horas del reloj de la prueba.

| | 136 | Nueva |
|---|---|---|
| Momentos citados (Nova · p6 · avianca) | 198 · 200 · 227 = **625** | 82 · 55 · 105 = **242** |
| …en una rampa | 70 · 126 · 50 = **246 (39 %)** | 12 · 14 · 9 = **35 (14 %)** |
| …en las conclusiones | 23, 5 en rampa | **0** |

Los 35 que quedan en rampa son casi todos de subida (30). **Salen sobre todo de las gráficas por
transacción**: tiempos de respuesta (12) y caudal (10); las generales de caudal (4) y de usuarios
activos (3), que sí tienen que contar el arranque; y 2 en cada una de latencia, códigos y tasa de error
por transacción. Es donde mirar si hay que apretar más.

**Ojo con la izquierda:** en el 136, los minutos de una transacción se contaban desde su primera muestra;
ahora, desde el inicio de la prueba (2.2a). La diferencia es de segundos, pero en un borde de fase puede
cambiar la fase de un momento.

### 4.3 La captura (137 §5.4)

Una llamada real con la primera captura de monitoreo de Nova, sin guardar el texto
(`captura_finish.py`): **`finish_reason = stop`**, tope 16.384, `reasoning_effort = medium`, 2.652 tokens
de entrada, **753 de salida de los que 512 son razonamiento**. Con el tope viejo de 1.024 quedaban 512
para el texto: no llegaba a cortarse en esta, pero iba justo. Un párrafo de 150 palabras.

---

## 5. Lo que cambió en el código (2.2 y 2.3)

| Commit | Qué |
|---|---|
| `b27ab3b` 2.2a | `contexto_prompt.py` (nuevo): el bloque de la ejecución, **idéntico** en las 10 generales y las 6 de cada transacción, detrás de un **único** sistema. Orden: bloque → [cabecera de la transacción] → lectura base → lo propio. El permiso de dictamen sale del sistema y va al final del mensaje |
| `76de13f` 2.2b | Los globales de monitoreo y evidencias con permiso de dictamen; el de monitoreo con línea de tiempo y fases; OCR sin disculpa; la captura con el sistema, el razonamiento de la configuración y el tope del modelo, y su `finish_reason` en la telemetría; límite de 600 palabras en las unificadas; fuera las instrucciones muertas |
| `20b9ec5` 2.3 | La guía de estilo de Fredy sustituye a las reglas de apertura con dato, cifras exactas en todo, percentiles en lista, párrafos de 2 a 4 oraciones y cierre con impacto, y al ejemplo de tono. Secciones: un párrafo de 120 a 160 palabras. Conclusiones y recomendaciones: 4 a 7 viñetas. Comparativa, unificadas y consolidado: un solo análisis para todas las ejecuciones |

**Tres cosas a saber:**

- **El porcentaje del ejemplo de Fredy va pegado** (`32,89%`, no `32,89 %`): es lo que pide el formato
  español del producto (D32) y el modelo copia los ejemplos.
- **`sanitize_ai_text` ya no borra las viñetas**: convierte `- ` y `* ` en `• `. Sin esto, unas
  conclusiones en viñetas de markdown llegaban como líneas sueltas. **CLAUDE.md regla 14** sigue diciendo
  que las borra: hay que actualizarla.
- **El detector de estilo no exigía párrafos ni apertura con dato**: no hubo que cambiarlo.
  `estructura_prompts.py` comprueba que el ejemplo de Fredy y sus viñetas dan **cero avisos**.

### 5.1 Las viñetas en las salidas

`vinetas_export.py` (base de pruebas, 8002, datos ZZTEST, textos originales devueltos al final): en el
**HTML** exportado cada viñeta abre su propia línea (`<br>• …`) y en el **PDF** salen 4 + 4 líneas que
empiezan por «•». La página del PDF se miró renderizada: se leen bien. **Sin tocar los exportadores
(protegidos) ni la rama web.** El integrado pinta el consolidado con `white-space: pre-wrap` en las dos
salidas, y la pantalla, en un `textarea`: las dos conservan los saltos.

---

## 6. Suites

| Suite | Resultado |
|---|---|
| `estructura_prompts.py` (nueva) | **TODO PASA** — sistema único, bloque idéntico en 22 llamadas, permiso solo en conclusiones y recomendaciones y al final, incoherencias del 137 §5, guía de estilo |
| `r2_series.py` | **TODO PASA** (actualizada: el bloque viaja en `contexto`) |
| `criterios_5b2.py` | **TODO PASA** |
| `f1_respaldo.py` (8002) | **TODO PASA** |
| `vinetas_export.py` (nueva, 8002) | **TODO PASA** |
| `cierre_r1.sh` (8002, reporte 138) | **TODO PASA** |

---

## 7. Lo que no se comprobó

- **Si el texto es mejor.** Es de Fredy: `comparacion2.html`.
- **La variabilidad del modelo.** Una corrida por versión.
- **Por qué el sistema solo no se reutiliza de caché** (§3.1).
- **Los prompts de pantalla** (globales de capturas, comparativa, integrado) solo se comprobaron sin IA;
  de la captura se hizo una llamada.
- **Gemini.** Todo es con gpt-5.5.

## 8. Archivos

| Dónde | Qué |
|---|---|
| `backend/pruebas_e2e/comparar_b22.py` | Nuevo: `comparacion2.html` y `resumen2.json`. Sin IA; el JTL, en solo lectura |
| `backend/pruebas_e2e/captura_finish.py` | Nuevo: una llamada a la captura, sin guardar el texto |
| `backend/pruebas_e2e/corrida_r2.py` | Pasa el bloque a las transacciones (2.2a) |
| `C:\proyectos\Kinetix_pruebas\r2\` (fuera del repositorio) | `comparacion2.html`, `resumen2.json`, los tres `corrida_b22_*.json` y `b22_lote.log` |
