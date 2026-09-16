fc7168e · 2026-09-15

# ETAPA 1.7 — Análisis de la línea base

**Llamadas reales a la IA en este sub-paso: 0.** Análisis sobre `baseline1.json` y
`baseline2.json` (70 llamadas válidas, todas `outcome="ok"`).

---

## 1. Telemetría por llamada

Ambas corridas completas están en los JSON. Resumen por sección (las 24 de transacción son
8 secciones × 3 labels; se muestra una de cada tipo):

| Sección | Alcance | rz/ct C1 | rz/ct C2 |
|---|---|---|---|
| summary_table | general | 66 % | 68 % |
| errors | general | 63 % | 69 % |
| chart_response_times | general | 83 % | 71 % |
| chart_throughput | general | 76 % | 77 % |
| chart_latency | general | 77 % | 76 % |
| chart_error_rate | general | 76 % | 76 % |
| chart_codes_per_second | general | 74 % | 71 % |
| chart_transactions_per_second | general | 70 % | 74 % |
| chart_active_threads | general | 75 % | 77 % |
| **conclusions** | general | **41 %** | **40 %** |
| **recommendations** | general | **41 %** | **40 %** |
| summary | transacción | 59 % | 62 % |
| chart_* | transacción | 72–86 % | 72–84 % |
| conclusions / recommendations | transacción | 62 % | 61–78 % |

---

## 2. H1 — **CONFIRMADA**

| | Corrida 1 | Corrida 2 |
|---|---|---|
| Tokens de salida | 27.782 | 28.461 |
| De ellos, razonamiento | 19.085 | 19.924 |
| **Proporción** | **68,7 %** | **70,0 %** |

**Cerca del 70 % de todo lo que el modelo genera es razonamiento que nunca llega al informe**, y
la cifra se repite casi exacta en dos corridas independientes: es una propiedad estable de esta
configuración, no ruido.

El patrón por sección es coherente y explicativo: las secciones de gráfica, con tope de 120
palabras, llegan al 71-86 %; `conclusions` y `recommendations` generales, con tope de 200
palabras y más texto real que producir, bajan al 40-41 %. Cuanto menos texto se pide, mayor
proporción del trabajo se va en pensar.

### Matiz importante que aporta la regresión

H1 se formuló como «los tokens de razonamiento **dominan la latencia**». Lo correcto, a la vista
de los coeficientes, es: **dominan por volumen, no por ser más caros por token.** Un token de
razonamiento cuesta prácticamente lo mismo que uno visible (b ≈ c, §3). Lo que los hace dominar
es que son el 70 % de los tokens generados.

---

## 3. Latencia — regresión lineal (adenda B)

Modelo ajustado sobre las **70 llamadas válidas** de ambas corridas:

```
latencia_s ≈ a + b·(reasoning_tokens/1000) + c·((completion_tokens − reasoning_tokens)/1000)
```

| Coeficiente | Valor | Lectura |
|---|---|---|
| **a** (intercepto) | **+2,397 s** | coste fijo por llamada: red, cola del proveedor, procesado del prompt |
| **b** (por 1.000 tokens de razonamiento) | **+9,948 s** | |
| **c** (por 1.000 tokens visibles) | **+8,862 s** | |
| **R²** | **0,833** (ajustado 0,829) | n = 70 |

**b ≈ c.** Generar un token cuesta lo mismo se muestre o no. No hay penalización oculta por
razonar: hay volumen.

### Granularidad de `reasoning_tokens` y su efecto en la precisión

Los valores observados en las 70 llamadas:

```
512 → 52 veces     1024 → 7 veces
321, 368, 410, 418, 421, 423, 438, 450, 498, 661, 809 → 1 vez cada uno
```

**59 de 70 (84 %) son múltiplos exactos de 512, y 512 solo acumula 52 de 70 (74 %).** El
proveedor reporta el razonamiento en escalones gruesos, no de forma continua.

Consecuencia directa sobre la fiabilidad de **b**: el regresor apenas tiene tres niveles
poblados (≈512, ≈1024 y una cola dispersa), con desviación típica de solo 165 tokens sobre un
rango de 321-1024. **b está estimado sobre muy poca variación real**, así que su valor puntual
(9,95 s/1.000 tok) debe leerse como orden de magnitud, no como constante precisa. El R² de 0,833
es bueno, pero se apoya en gran medida en `c`, cuyo regresor sí varía de forma continua
(133-766 tokens).

### Techo de ganancia al bajar `reasoning_effort` — estimado con **b**

Razonamiento medio por llamada: **557 tokens** → **b · 0,557 = 5,5 s** de los **10,1 s** de
latencia media. **El razonamiento explica el 55 % del tiempo de una llamada.**

| Si el razonamiento baja… | Ahorro por llamada | Ahorro en 35 llamadas |
|---|---|---|
| 50 % | −2,8 s | **−97 s** (−1,6 min) |
| 75 % | −4,2 s | −146 s (−2,4 min) |
| 100 % (imposible) | −5,5 s | −194 s (−3,2 min) |

**Techo realista:** sobre los 357 s de latencia total, reducir el razonamiento a la mitad
recortaría en torno a **1,6 minutos (≈27 %)**. Es la ganancia más grande disponible sin tocar
el número de llamadas ni la secuencialidad — pero **no convierte 6 minutos en 40 segundos**. Para
eso haría falta atacar el número de llamadas o la secuencialidad, que es otra etapa.

---

## 4. Aprovechamiento de caché

| | Corrida 1 | Corrida 2 |
|---|---|---|
| cached / prompt | 8.960 / 115.810 = **7,7 %** | 64.256 / 115.751 = **55,5 %** |
| Llamadas con caché > 0 | 5 de 35 | 25 de 35 |

**El salto no es mérito de los fixes.** Es el caché de prompts de OpenAI: premia repetir
prefijos idénticos poco después, y la corrida 2 repitió exactamente los prompts de la 1 con
minutos de diferencia. En uso real, con informes de pruebas distintas, el aprovechamiento se
parecerá más al 7,7 % que al 55,5 %.

Lo aprovechable de verdad: **el prefijo estable es `SYSTEM_PROMPT`**, y E1.1 documentó que viaja
**duplicado** en cada llamada (mensaje `system` + copia embebida). Ordenar eso es lo que haría
el caché rentable de forma sistemática. Material para la Etapa 4.

---

## 5. Variación natural entre corridas → **umbral para la Etapa 4**

| Medida | C1 | C2 | Diferencia |
|---|---|---|---|
| Latencia total de IA | 351,6 s | 357,0 s | **+1,5 %** |
| T1 − T0 (bloque general) | 119,1 s | 112,1 s | −5,9 % |
| T2 − T0 (percibido) | 354,3 s | 357,4 s | +0,9 % |

Por sección, en cambio, el ruido es mucho mayor: **media de |diferencia| 17,7 %**, con casos
extremos de −48 % y +65 %.

> **Umbral de mejora real declarado para la Etapa 4: 1,5 % sobre el total.**
> Es la variación total observada, tal como pide el enunciado.
>
> Dos advertencias sobre cómo usarlo, porque tomado a la ligera engaña:
> 1. Sale de **n = 2**. Es una estimación débil; conviene tratar como concluyente solo una
>    mejora que lo supere con holgura (varias veces), no uno que lo roce.
> 2. **No aplica sección a sección.** Ahí el ruido es ±18 %, así que una sección que "mejora"
>    un 10 % no ha mejorado nada demostrable. El umbral es para el agregado.

---

## 6. Tiempos percibidos

| | C1 (antes) | C2 (después) |
|---|---|---|
| T1 − T0 (bloque general) | 119,1 s | 112,1 s |
| T2 − T0 (total percibido) | 354,3 s | 357,4 s |

Sin cambio significativo, **como debía ser**: H4 no acelera la generación, solo impide que
bloquee al resto de la aplicación.

---

## 7. Sonda `/auth/me` — antes vs después

| Métrica | C1 (antes) | C2 (después) | Cambio |
|---|---|---|---|
| **Máximo** | **54.922,3 ms** | **21,0 ms** | **÷ 2.615** |
| **p95** | 7,9 ms | **4,9 ms** | −38 % |
| Media | 457,9 ms | 3,5 ms | ÷ 131 |
| Errores | 1 | **0** | — |
| Muestras en el mismo intervalo | 122 | 181 | +48 % |

El p95 de la corrida 1 (7,9 ms) es engañoso y conviene explicarlo: la sonda pasa la mayor parte
del tiempo durante el bloque **por transacción**, que ya estaba protegido con `to_thread` desde
N4.10. El daño se concentraba en el bloque general, y por eso aparece en el **máximo** y en la
**media**, no en el percentil.

Las 181 muestras frente a 122 en un intervalo equivalente confirman lo mismo por otra vía: antes
la sonda se quedaba colgada y perdía ciclos.

---

## 8. Holgura de tope (riesgo B6.3)

**Ninguna sección supera el 50 % de los 16.384 tokens.** El máximo observado en las 70 llamadas
es **1.349 tokens** (`txreport_conclusions`), un **8,2 %** del tope.

El patrón B6.3 —agotar el tope razonando y devolver vacío— **no está cerca de ocurrir** con esta
configuración. Si en la Etapa 4 se sube `reasoning_effort` o se alargan los topes de palabras,
este número es el que hay que volver a mirar.

---

## Estado

Sub-paso 1.7 completado. Se continúa con 1.8 (cierre de la etapa).
