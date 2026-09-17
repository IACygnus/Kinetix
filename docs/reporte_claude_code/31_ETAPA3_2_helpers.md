9ed042e · 2026-09-16

# ETAPA 3.2 — Helpers deterministas

**Llamadas reales a la IA en este sub-paso: 0.** Todo lo que hay aquí es
determinista y se prueba con pytest. Ningún archivo protegido tocado.

---

## 1. Qué se creó

| Archivo | Líneas | Qué es |
|---|---|---|
| `backend/app/services/ai/estilo.py` | 400 | Módulo nuevo: formato, frases de percentil, bloque de estilo y los dos detectores |
| `backend/tests/test_estilo.py` | 340 | **57 pruebas unitarias**, todas en verde |

Nada más se modificó. `estilo.py` no importa nada del proyecto: solo `re`,
`unicodedata` y `typing`. Es un módulo hoja, así que puede importarlo cualquiera
sin riesgo de ciclos.

---

## 2. Las cinco piezas

### 2.1 Formato español (D32)

| Función | Entrada | Salida |
|---|---|---|
| `num(10075)` | 10075 | `10.075` |
| `pct(0.2734)` | 0.2734 | `0,27%` |
| `ms(125)` | 125 | `125 ms` |
| `tiempo(3515)` | 3515 | `3,5 segundos` |
| `tiempo(125)` | 125 | `125 ms` |
| `veces(3.79)` | 3.79 | `3,8 veces` |
| `kbs(259.85)` | 259.85 | `259,85 KB/s` |

Reglas fijadas: miles con punto, decimales con coma, unidad **separada**
(`125 ms`), porcentaje **pegado** (`0,27%`), y por encima de 1.000 ms el tiempo
pasa a segundos con un decimal. `num(None)` devuelve `0` y `num("hola")`
devuelve `hola`: un formateador no puede tumbar la generación de un informe.

### 2.2 Frases de percentil (D33)

```
percentil_frase(90, 3515)
  -> "1 de cada 10 usuarios espera mas de 3,5 segundos (P90: 3.515 ms)"
percentil_frase(50, 103)
  -> "la mitad de los usuarios espera mas de 103 ms (P50: 103 ms)"
```

P90 = 1 de cada 10, P95 = 1 de cada 20, P99 = 1 de cada 100, P50 = la mitad.
`percentiles_bloque(p50, p90, p95, p99)` arma las cuatro y omite las que no
llegan. La frase se genera en el **bloque de datos**, no se le pide al modelo
que la construya: el modelo solo tiene que copiarla.

### 2.3 El bloque de estilo único (D28)

`BLOQUE_ESTILO` son **14 reglas** que sustituyen a lo que estaba repartido en
cuatro sitios distintos (`SYSTEM_PROMPT`, `STYLE_REMINDER`, `UX_RULE`,
`FORMATO_NUMERICO`). Orden: vocabulario prohibido · percentiles en personas ·
formato español · cifras exactas · ratios en palabras · sin markdown · apertura
con dato · razonar no describir · narrar el flujo de negocio · **el veredicto
no va aquí** · cierre con impacto · densidad · picos · párrafos narrativos.

Se conservan, tal como pide D28: cifras exactas, formato español, cierre con
impacto al usuario, sin markdown y las palabras prohibidas ya vigentes. Se
añaden las de D29 (tier, variabilidad, dispersión, latencia crítica) y la
prohibición del veredicto (D30).

`bloque_estilo(permite_veredicto=True)` le añade `PERMISO_VEREDICTO`, que es la
excepción explícita para conclusiones, recomendaciones y consolidado. Una sola
fuente de verdad con un interruptor, no dos textos que se puedan desincronizar.

`REFERENCIA_ESTILO` lleva el ejemplo aprobado de §4.3 **con la prohibición de
copiar delante** (D31), por la razón del reporte 30 §4.3: ese ejemplo usa el
mismo dataset que una de las pruebas reales.

### 2.4 Detector de estilo (D35)

`detectar_estilo(texto, seccion)` devuelve una lista de
`{tipo, termino, contexto}` con cuatro tipos: `jerga`,
`percentil_sin_traducir`, `veredicto_fuera_de_conclusiones` y
`formato_ingles`. `terminos_de(avisos)` la resume para la pantalla
(`["tier", "P99 sin traducir"]`).

**Solo detecta.** No regenera, no reescribe, no llama a la IA y está envuelto en
un `try/except` que devuelve lista vacía: un detector no puede romper una
lectura de informe.

### 2.5 Trazabilidad de cifras (D37)

`trazar_cifras(texto, datos_prompt)` devuelve
`{total, trazables, pct, no_trazables}`. Extrae cada número del análisis, lo
normaliza (`10.075` → 10075, `0,27` → 0.27, `2,841` → 2841) y comprueba que
exista en los datos que se le enviaron al modelo. Tolerancia: 0,5 en absoluto o
el 0,5 % del valor, lo que sea mayor — cubre el redondeo legítimo sin dejar
pasar una cifra inventada. La numeración de una lista (`1.`, `2.`) no cuenta
como cifra.

---

## 3. Las pruebas

**57 pruebas, 57 en verde**, en 0,38 s:

```
docker exec -w /app jmeter_backend python3 -m pytest tests/test_estilo.py -q
.........................................................  [100%]
57 passed in 0.38s
```

Los casos límite que pedía el plan, uno por uno:

| Caso | Prueba | Resultado |
|---|---|---|
| `10075` → `10.075` | `test_miles_con_punto` | ✔ |
| `0.2734` → `0,27%` | `test_porcentaje_con_coma` | ✔ |
| `3515 ms` → `3,5 segundos` | `test_tiempo_sobre_un_segundo_va_en_segundos` | ✔ |
| ratio `3.79` → `3,8 veces` | `test_ratio_en_palabras` | ✔ |
| «tier excelente» detectado | `test_tier_excelente_detectado` | ✔ |
| `P90: 3.515 ms` dentro de la frase de usuario **no** detectado | `test_percentil_dentro_de_la_frase_de_usuario_no_se_marca` | ✔ |
| `P99` suelto detectado | `test_percentil_suelto_se_marca` | ✔ |
| «listo para producción» detectado en sección y **no** en conclusiones | `test_listo_para_produccion_se_marca_en_una_seccion` + `..._no_se_marca_en_conclusiones` | ✔ |
| `10.075` trazable contra el dato `10075` | `test_cifra_espanola_es_trazable_contra_el_dato_crudo` | ✔ |

Y los que hicieron falta para dejar las decisiones del reporte 30 clavadas:

- **T1** — `test_el_cierre_de_impacto_no_es_veredicto`: «En producción, el
  usuario percibirá reservas que no cargan» **no** deja ningún aviso. Esa frase
  la exige la regla 11 del estilo; marcarla habría vuelto el detector inútil.
- **T2** — `test_miles_a_la_espanola_no_se_marca`: `3.515` (tres dígitos) es
  separador de miles y no se marca; `179.73` (dos) sí.
- **T3** — `test_variacion_no_es_variabilidad`: «variación» no es jerga.
- **T4** — `test_porcentaje_pegado_no_se_marca`: `28,20%` es correcto.
- **La traducción cubre solo su frase** — `test_la_traduccion_solo_cubre_su_propia_frase`:
  en «1 de cada 10 usuarios espera más de 123 ms (P90: 123 ms). El P99 llegó a
  206 ms.» marca **uno** (el P99), no cero ni dos.

---

## 4. El detector reproduce la línea base del reporte 30

La línea base de 3.1 se midió con un prototipo en el scratchpad. Corrida otra
vez con el módulo real, sobre los mismos textos guardados, da **exactamente lo
mismo**:

| | `E2-validacion` | `E1.3-baseline-2` |
|---|---|---|
| `formato_ingles` | 105 | 108 |
| `jerga` | 9 | 18 |
| `percentil_sin_traducir` | 9 | 8 |
| `veredicto_fuera_de_conclusiones` | 1 | 1 |
| **Total** | **124** | **135** |
| — en el informe general | 121 (11 secciones) | 127 (11 secciones) |
| — en los bloques por transacción | 3 (18 secciones) | 8 (24 secciones) |

Esta tabla es la referencia contra la que se comparará `E3-estilo-pruebakinetix`
en 3.5.

---

## 5. Lo que este sub-paso NO hizo

- **Ningún prompt cambió todavía.** `estilo.py` existe y está probado, pero
  nadie lo importa aún. Eso es 3.3.
- **Ningún endpoint devuelve `style_warnings` todavía.** Eso es 3.4.
- La parada de D36 en `Dashboard.tsx` (reporte 30 §3) sigue abierta y no se
  toca.

Siguiente: 3.3, aplicar D28-D34 a los diecinueve prompts y validarlo con stubs.
