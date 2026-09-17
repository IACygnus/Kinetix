441575b · 2026-09-16

# ETAPA 3.5 — Las corridas reales de validación

**Llamadas reales a la IA en este sub-paso: 40.** 28 de
`E3-estilo-pruebakinetix`, 10 de `E3-estilo-avianca` y 2 del informe integrado
(las conclusiones unificadas y el consolidado). **Total de la etapa: 40 de 50.**

Backend estable durante las corridas: ningún archivo se tocó mientras corrían.

---

## 1. El resultado que importa

| Avisos del detector D35, por tipo | `E2-validacion` | **`E3-estilo-pruebakinetix`** | **`E3-estilo-avianca`** |
|---|---|---|---|
| `formato_ingles` | 105 | **0** | **0** |
| `jerga` (tier, variabilidad, dispersión…) | 9 | **0** | **0** |
| `percentil_sin_traducir` | 9 | **0** | **0** |
| `veredicto_fuera_de_conclusiones` | 1 | **0** | **0** |
| **TOTAL** | **124** | **0** | **0** |

Mismo JTL, mismos criterios, mismas tres transacciones, mismo modelo y mismo
`reasoning_effort`. Lo único que cambió son los prompts.

**38 secciones de texto nuevas, cero avisos.** No hay ninguna que listar.

---

## 2. Cómo se lee ahora un análisis

Resumen de `E3-estilo-pruebakinetix`, tal cual está guardado:

> 10.075 transacciones se ejecutaron en 300 segundos, con tiempo promedio global
> de 180 ms y 33,59 Transacciones por segundo (TPS). Auth, Get Booking y Post
> Create_Booking completaron el inicio del recorrido sin errores, lo que apunta
> a que el usuario puede autenticarse, consultar la información base y crear la
> reserva con respuesta rápida; Auth fue la más lenta con 422 ms, 3,9 veces más
> lenta que Delete_Booking_Id, pero dentro del máximo aceptable de 2.000 ms.
>
> La ruptura funcional aparece después de crear la reserva: Get_Booking_Id
> registró 692 errores, Put_Update_Booking 952 errores y Delete_Booking_Id 1.197
> errores, con tasas de 41,26%, 56,77% y 71,42%. […]
>
> En el consolidado, la mitad de los usuarios espera mas de 110 ms (P50: 110 ms),
> 1 de cada 10 usuarios espera mas de 406 ms (P90: 406 ms) […]. En producción,
> una persona podría crear una reserva y luego fallar al consultarla, cambiarla
> o eliminarla.

El mismo bloque en `E2-validacion`:

> 6 transacciones quedaron en tier excelente, con promedio global de 179.73ms y
> 33.59 Transacciones por segundo (TPS) […] Auth fue la más lenta con 422ms,
> 3.9x mayor […] **No debería liberarse** sin corregir los errores de consulta,
> actualización y eliminación.

Cambió lo que se pidió: sin «tier», sin `3.9x`, sin `179.73ms`, con los
percentiles leídos en personas, narrando el flujo de negocio en orden, y **sin
dictaminar** sobre producción dentro de una sección.

### 2.1 Un defecto cosmético que sí se ve

La frase de percentil salía del helper **sin la tilde de «más»** («espera mas
de»), y el modelo la copia literalmente porque así se le pide. **Está corregido
en `estilo.py`**, pero los textos de estas dos corridas ya quedaron guardados
con «mas». La próxima generación los escribirá con tilde.

No se regeneró para arreglarlo: habría costado 40 llamadas más por una tilde, y
el presupuesto de la etapa es de 50.

---

## 3. Que el modelo no copia el ejemplo aprobado (D31)

El ejemplo de estilo de §4.3 es, literalmente, el dataset de `ff186cc7`
(reporte 30 §4.3). Sobre ese JTL no hay forma de distinguir «usó los datos» de
«copió el ejemplo». Por eso existe `E3-estilo-avianca`, con otro JTL, otras
transacciones y otras cifras.

Se buscaron en sus diez textos las cifras y los nombres del ejemplo:

`10.075` · `10,075` · `28,20` · `28.20` · `2.841` · `2,841` · `41,26` · `41.26`
· `56,77` · `56.77` · `71,42` · `71.42` · `Get_Booking_Id` ·
`Put_Update_Booking` · `Delete_Booking_Id` · `Post Create_Booking` ·
`Get Booking` · `Auth`

**Resultado: ninguna.** Los textos de avianca hablan de `auth`, `crear`,
`Paso 2` y `Paso 4`, de sus 81.714 peticiones y de su 0,06 % de error.

---

## 4. Trazabilidad de cifras (D37)

Cada número de cada análisis, comprobado contra los datos que se le enviaron al
modelo en ese prompt exacto:

| | Cifras | Trazables | % |
|---|---|---|---|
| `E3-estilo-pruebakinetix` (28 secciones) | 435 | 429 | **98,6 %** |
| `E3-estilo-avianca` (10 secciones) | 178 | 174 | **97,8 %** |

**Veintidós de las 38 secciones dan 100 %.** Las diez cifras restantes están
todas identificadas, y **ninguna es inventada**: son cuentas que el modelo hizo
con los datos que tenía.

| Cifra | Sección | Qué es |
|---|---|---|
| `90` | latencia (kinetix) | «El 90% del tiempo que espera una persona…» — 162 ms de latencia sobre 180 ms de tiempo total |
| `18` | latencia (kinetix) | 180 − 162 = 18 ms de descarga |
| `71,80` | tasa de error y códigos (kinetix) | 100 − 28,20 = disponibilidad efectiva |
| `28,20` | códigos (kinetix) | (2.149 + 692) / 10.075, calculado desde los conteos por código |
| `2,0` | TPS de Get_Booking_Id | 11,00 / 5,61 = pico sobre promedio |
| `6,1` | resumen (avianca) | 6.115 ms expresados en segundos — el trazador compara valores, no unidades |
| `10` | latencia (avianca) | «sin máximos por encima de 10 segundos» — el umbral sale de la regla 13 del estilo, no de los datos |
| `99,94` | códigos (avianca) | 100 − 0,06 = disponibilidad |
| `0,18` | TPS (avianca) | diferencia entre la transacción de más y la de menos caudal |

Las dos limitaciones conocidas del trazador quedan a la vista y se declaran:
**no sigue conversiones de unidad** (6.115 ms → 6,1 segundos) y **no reconoce
cifras que vienen de las reglas de estilo** (el umbral de 10 segundos). Ambas
producen falsos positivos, nunca falsos negativos: una cifra inventada seguiría
saliendo marcada.

---

## 5. Lo que cuesta

| | `E2-validacion` | **`E3-estilo-pruebakinetix`** | |
|---|---|---|---|
| Llamadas por informe | 28 | **28** | igual |
| Caracteres enviados en total | 356.293 | **230.872** | **−35,2 %** |
| Tokens de prompt | 92.379 | **63.201** | **−31,6 %** |
| **Cacheados** | 7.168 (**7,8 %**) | **23.296 (36,9 %)** | **×4,7** |
| Razonamiento por llamada | 113 | **110** | igual |
| **Texto visible por llamada** | 226 | **263** | **+16 %** |
| Latencia media por llamada | 4,9 s | **5,5 s** | +12 % |
| T1 − T0 (bloque general) | 55,9 s | **68,9 s** | +23 % |
| **T2 − T0 (lo que espera el usuario)** | **141,0 s** | **159,0 s** | **+12,8 %** |
| Peor latido de `/auth/me` | 10,7 ms | **5,5 ms** | mejor |

El informe **tarda 18 segundos más** y hay que decirlo sin adornos. El prompt
bajó un tercio, pero el modelo **escribe un 16 % más de texto visible** y tarda
más en hacerlo. Dato informativo: el tiempo no era el objetivo de esta etapa
(lo era de la 2, que lo bajó de 354 s a 141 s) y sigue muy por debajo de la
línea base de la Etapa 1.

El **7,8 % de caché que el reporte 28 dejó como deuda pasa al 36,9 %** sin
haberlo buscado: al enviar el bloque de estilo una sola vez y siempre igual, el
proveedor lo reconoce. Esa era una de las tareas que el reporte 25 §5 dejaba
apuntadas para la Etapa 4.

---

## 6. Las corridas, una por una

| | `E3-estilo-pruebakinetix` | `E3-estilo-avianca` |
|---|---|---|
| Ejecución | `20bb2356-410d-465f-8717-c9a025e26e03` | `aebed470-d8b1-4705-aa57-4f1bceae61d5` |
| JTL | el de `ff186cc7` (10.075 muestras) | el de `1e592533` (81.714 muestras) |
| Cliente | iaperformance | prueba avianca |
| Criterios | 30 usuarios · 2.000 ms · 99,5 % | 30 usuarios · 1.000 ms · 99,5 % |
| Transacciones | 3 | ninguna (a propósito) |
| Llamadas | 28, **todas `outcome=ok`** | 10, **todas `outcome=ok`** |
| T2 − T0 | 159,0 s | 63,5 s |
| Sonda `/auth/me` | 82 muestras, 0 errores, máx 5,5 ms | 34 muestras, 0 errores, máx 5,7 ms |

**Informe integrado** `8713aad1-5de9-4dcb-b294-360ce8ecaee8`, con las dos
ejecuciones y su consolidado: 2 llamadas, ambas correctas. Su consolidado
también sale limpio y cruza las dos pruebas por su cuenta:

> «81.714 peticiones en 180 segundos cerraron con 0,06% de error, 101 ms de
> tiempo promedio y 453,93 por segundo, mientras la ejecución previa de 10.075
> peticiones en 300 segundos había cerrado con 28,20% de error, 180 ms y 33,59
> por segundo.»

Ahí sí dictamina, que es donde le corresponde: «la primera prueba es NO APTO
porque la disponibilidad efectiva fue 71,80%…».

---

## 7. Regresión

`verificar_etapa2.py` sobre `E3-estilo-pruebakinetix`
(`KX_EID=20bb2356-…`) — **diez pasos, las cuatro salidas**:

```
ETAPA 2 — LAS CUATRO SALIDAS PASAN
```

Pantalla, PDF, HTML e integrado siguen pasando con los textos nuevos: sin la
gráfica Throughput, sin la palabra prohibida, sin conclusiones por transacción,
con los tres bloques por transacción vivos y con el cableado C2 intacto.

---

## 8. Lo que queda para la validación de Fredy

Compilación verde y 0 avisos del detector **no son** una feature funcional
(regla 9). El guion está en el reporte 36.
