Commit base `e6b9947` · 30 de septiembre de 2026 · Bloque 2.5 — cifras, rampas y caché

# Bloque 2.5 — la versión 2.5 frente a la 2.4

Este reporte **no copia ningún texto de cliente**. Los textos, uno al lado del otro por sección, están en
**`C:\proyectos\Kinetix_pruebas\r2\comparacion3.html`** (izquierda: la 2.4 de `comparacion2.html`;
derecha: la 2.5). **El juicio de si el texto es mejor es de Fredy.**

**Condiciones de parada: ninguna se cumplió.** Suites en verde, 0 secciones de respaldo, sin tocar
archivos protegidos ni la rama web.

**El punto 5 (los comentarios de Fredy) NO se aplicó**: el mensaje traía el marcador «[pega aquí lo que
anotaste]» sin contenido. Queda pendiente hasta que lleguen.

---

## 1. Qué cambió

| Commit | Qué |
|---|---|
| `17c9f3d` 2.5a | **Cifras:** la guía dice «como máximo 4 cifras por párrafo de sección; escoge las que prueban el hallazgo principal y deja fuera el resto» (un minuto o una hora cuentan). Si los datos propios de una sección traen más de 8 cifras, su instrucción lo recuerda (`estilo.recordatorio_cifras`). **Rampas:** `resumen_serie` marca en el propio dato los mínimos, máximos, picos, tramos y episodios que caen en la subida o la bajada (`[en la subida: rampa]`); la instrucción de fases lo explica, y `fases.NOTA_RAMPAS` se repite al final de **todas** las gráficas, generales y por transacción, con el mismo texto (menos usuarios activos, que tiene que contar la rampa). **CLAUDE.md regla 14** actualizada |
| `e6b9947` 2.5b | **Caché:** la tabla por transacción y la agrupación por tiempo de respuesta pasan al bloque de la ejecución (§3) |

---

## 2. Las cifras

| Medida | 2.4 (Nova · p6 · avianca) | 2.5 (Nova · p6 · avianca) |
|---|---|---|
| Respaldo | 0 · 0 · 0 | **0 · 0 · 0** |
| **Cifras por párrafo de sección** | 15,1 · 14,4 · 15,8 | **4,7 · 4,3 · 5,0** |
| Secciones con 4 cifras o menos | — | **57 de 90**; 22 con 5 o 6; 11 con más de 6 |
| Secciones de un solo párrafo | 90 de 90 | **90 de 90** |
| Palabras por sección (mín–máx) | 127–172 · 139–171 · 128–161 | 124–155 · 135–161 · 134–154 |
| Momentos citados | 82 · 55 · 105 = 242 | **4 · 4 · 17 = 25** |
| **…en una rampa** | 12 · 14 · 9 = **35** | **0 · 0 · 0** |
| Conclusiones: viñetas · cifras | 6 · 0–2 | 6 · 0 |
| Recomendaciones: viñetas · cifras | 6–7 · 0–2 | 6–7 · 0–3 |
| Disculpas | 0 | **0** |

- **Cifras:** de ~15 por párrafo a ~4,7. Dos de cada tres secciones cumplen el tope de 4; el resto se pasa
  por una o dos, y 11 por más. Se cuentan también los minutos y los códigos HTTP.
- **Rampas:** ningún momento citado cae ya en una rampa. **El objetivo se cumple por exceso:** el modelo
  casi ha dejado de citar minutos (de 242 a 25). Si Fredy quiere que se diga *cuándo* pasa algo dentro de
  la carga sostenida, hay que pedirlo aparte; la regla de 4 cifras empuja a quitarlos.

### 2.1 Tokens, caché y tiempo

| Versión | Segundos | Entrada | …en caché | A precio completo | Salida | …razonamiento |
|---|---|---|---|---|---|---|
| 2.4 | 1.184,0 | 375.065 | 129.792 (34,6 %) | 245.273 | 70.770 | 48.193 |
| 2.5 | 1.191,3 | 484.537 | **292.096 (60,3 %)** | **192.441** | 78.071 | 57.215 |
| Diferencia | +0,6 % | +29,2 % | ×2,25 | **−21,5 %** | +10,3 % | +18,7 % |

- **Llamadas con caché: 93 de 96** (antes 45). Solo fallan la primera de cada ejecución y dos sueltas.
- La entrada crece un 29 % porque la tabla y la agrupación van ahora en las 96 llamadas, pero **se paga a
  precio completo un 21,5 % menos**.
- **La salida sube un 10 %** (el razonamiento, un 19 %): el modelo razona más para escoger 4 cifras. Con
  la fórmula del 136 §3.2, la 2.5 paga menos entrada completa y algo más de salida; el saldo depende de
  `Pe` frente a `Ps`.

---

## 3. Por qué las 9 primeras llamadas del general no usaban la caché

**Explicado en parte, en menos de una hora y con 11 llamadas de prueba.**

1. **Hipótesis descartada** (`prueba_cache_25.py`, texto sintético, 4 llamadas): «cada petición guarda
   un solo punto de caché». Una petición que comparte ~5.400 tokens con otra de 6.906 reutilizó 4.864.
   **Se reutilizan todos los cortes de 1.024·k − 256 tokens** (1.792, 2.816, 3.840, 4.864…): son
   exactamente los valores vistos en el 136 y el 139.
2. **Con el prompt real** (`prueba_cache_25b.py`, la gráfica de latencia de Nova, 4 llamadas):

   | Lo que se manda detrás del mismo sistema | En caché |
   |---|---|
   | El prompt tal cual, por segunda vez | 2.816 |
   | Cortado en 3.744 caracteres (lo que comparte con la gráfica siguiente) + un final distinto | **0** |
   | Cortado en 4.400 caracteres + final distinto | 2.816 |
   | Cortado en 5.000 caracteres + final distinto | 2.816 |

   **El tramo común de las secciones generales (sistema + bloque + lectura base) se quedaba unos 200
   tokens por debajo del corte de 2.816.** Las de transacción comparten además su cabecera y lo pasaban:
   por eso ellas sí usaban la caché desde la tercera.
3. **Lo que no está explicado:** por qué **no aparece nunca el corte de 1.792**, que ese tramo común supera
   de largo (el sistema solo ya son ~1.690 tokens). En el experimento sintético sí aparecían los cortes
   bajos. Anotado; no se siguió.
4. **La medida (2.5b):** alargar lo común con lo que ya es igual en todas las llamadas —la tabla por
   transacción y su agrupación— lleva el bloque de ~2.500 a ~5.550 caracteres. **Resultado medido en la
   corrida: 93 de 96 llamadas con caché, 60,3 % de la entrada.**

Coste de la investigación: 2 + 4 + 4 llamadas cortas (salida de 32 o 64 tokens) y 2 más en seco que no
sirvieron (su lectura base era de relleno).

---

## 4. Suites

`estructura_prompts.py`, `r2_series.py` y `criterios_5b2.py`: **TODO PASA** tras cada paso. Una pasada en
seco comprobó que las marcas `[rampa]`, `NOTA_RAMPAS` y el recordatorio de cifras llegan a las 28
llamadas de «prueba 6».

## 5. Lo que no se comprobó

- **Si el texto es mejor**, ni si se echan de menos los minutos (§2). Es de Fredy: `comparacion3.html`.
- **Los comentarios de Fredy** (punto 5): no llegaron.
- **Por qué no aparece el corte de 1.792** (§3.3).
- **La variabilidad del modelo:** una corrida por versión.

## 6. Archivos

| Dónde | Qué |
|---|---|
| `backend/pruebas_e2e/prueba_cache_25.py` · `prueba_cache_25b.py` | Nuevos: las dos pruebas de caché |
| `backend/pruebas_e2e/comparar_b22.py` | Versiones y salida por entorno; cuenta si un momento en rampa se dice como rampa y de qué sección sale |
| `C:\proyectos\Kinetix_pruebas\r2\` (fuera del repositorio) | `comparacion3.html`, `resumen3.json`, los tres `corrida_b25_*.json` y `b25_lote.log` |
