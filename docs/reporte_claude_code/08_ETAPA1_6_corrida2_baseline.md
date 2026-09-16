5d2193c · 2026-09-15

# ETAPA 1.6 — Corrida 2: línea base DESPUÉS de los fixes

**Llamadas reales a la IA en este sub-paso: 35.** Total de la etapa: **70 de ~70 autorizadas.**
**Corrida VÁLIDA** — ninguna condición de PARADA se activó.

Ejecución creada: `E1.3-baseline-2` · datos crudos en `C:\proyectos\Kinetix_pruebas\baseline2.json`.

---

## Controles de validez — los tres pasan

| Control | Esperado | Obtenido |
|---|---|---|
| Nº de líneas `AI_TELEMETRY` | 11 + 24 | **11 + 24 = 35** ✓ |
| Todos los `outcome` | `ok` | **35/35 `ok`**, 35/35 `finish_reason="stop"` ✓ |
| Texto real en base | sí | 24/24 filas con texto · 3 labels · summary 972 ch · conclusiones 2.958 ch ✓ |

---

## El efecto de H4 — la sonda `/auth/me`

Es el resultado principal de esta corrida.

| Métrica | Corrida 1 (antes) | Corrida 2 (después) | Cambio |
|---|---|---|---|
| Muestras | 122 | 181 | — |
| Errores | 1 | **0** | — |
| Mínimo | 2,6 ms | 2,6 ms | = |
| **Máximo** | **54.922,3 ms** | **21,0 ms** | **÷ 2.615** |
| p95 | 7,9 ms | 4,9 ms | −38 % |
| **Media** | **457,9 ms** | **3,5 ms** | **÷ 131** |

Antes, una petición de sesión llegó a tardar **casi 55 segundos**. Ahora el peor caso de toda la
generación son **21 ms** — por debajo incluso del máximo en reposo medido en 1.2 (30,5 ms).

La media es el número que mejor lo resume: **457,9 ms → 3,5 ms**. Antes la sonda pasaba buena
parte del tiempo esperando a que el event loop la atendiera; ahora no espera.

Las 181 muestras frente a 122 son otra señal del mismo efecto: la sonda pide cada 2 s, y antes
**se quedaba colgada** en peticiones larguísimas, así que hacía menos. Con el loop libre mantiene
su cadencia.

---

## Tiempos

| Medida | Corrida 1 | Corrida 2 | Diferencia |
|---|---|---|---|
| T1 − T0 (bloque general) | 119,1 s | **112,1 s** | −7,0 s (−5,9 %) |
| T2 − T0 (percibido total) | 354,3 s | **357,4 s** | +3,1 s (+0,9 %) |
| Latencia sumada de IA | 351,6 s | 357,0 s | +5,4 s (+1,5 %) |

**El fix de H4 no acelera la generación, y no debía hacerlo.** Las llamadas siguen siendo
secuenciales: lo que cambia es que ahora esperan en un hilo aparte en vez de bloquear el
servidor entero. El tiempo total se mueve dentro del ruido natural del proveedor.

Esa diferencia es justamente la **variación natural** que 1.7 convertirá en el umbral de mejora
real para la Etapa 4.

---

## Tokens

| Métrica | Corrida 1 | Corrida 2 |
|---|---|---|
| Tokens de prompt | 115.810 | 115.751 |
| Tokens de salida | 27.782 | 28.461 |
| De ellos, razonamiento | 19.085 (**68,7 %**) | 19.924 (**70,0 %**) |
| **Tokens cacheados** | 8.960 (**7,7 %**) | **64.256 (55,5 %)** |

La proporción de razonamiento se repite casi exacta (68,7 % → 70,0 %) en dos corridas
independientes: es una propiedad estable del modelo con esta configuración, no una casualidad.

El salto de caché (7,7 % → 55,5 %) **no es mérito de los fixes**: es el caché de prompts de
OpenAI, que premia repetir prefijos idénticos poco después. La corrida 2 usó los mismos prompts
que la 1. Se anota para no atribuirle un efecto que no tiene; en 1.7 se analiza con cuidado.

---

## Estado

Sub-paso 1.6 completado. Presupuesto de IA de la etapa **agotado (70/70)**: 1.7 y el cierre no
consumen ninguna llamada.

Se continúa con la ADENDA A (liberación del flag de prueba) y después 1.7.
