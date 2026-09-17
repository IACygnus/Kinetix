729be9f · 2026-09-17

# ETAPA 5.2 y 5.3 — El panel de selección: implementación y validación

**Llamadas reales a la IA: 22**, todas de la corrida `E5-panel` (5.3). El
sub-paso 5.2 consumió **cero**. **Ningún archivo protegido tocado.**

---

## 1. Qué se cambió

| Archivo | Líneas | Qué |
|---|---|---|
| `frontend/src/utils/criticidad.ts` *(nuevo)* | +125 | La regla de criticidad en TS, puerto literal de la del backend (D42) |
| `frontend/src/utils/criticidad.paridad.ts` *(nuevo)* | +75 | Los mismos casos que el lado Python |
| `backend/tests/fixtures/criticidad_casos.json` *(nuevo)* | +155 | Los casos, en un solo sitio, para los dos lenguajes |
| `backend/tests/test_criticidad_paridad.py` *(nuevo)* | +95 | La regla, lado Python |
| `backend/app/api/v1/endpoints/upload.py` | 34 | Devuelve `tps` (D39); reescribe el motivo (D45) |
| `frontend/src/services/api.ts` | 3 | `tps` en `TransactionMetrics` |
| `frontend/src/components/dashboard/UploadJTL.tsx` | 171 | Columnas (D39), fila desplegable (D40/D41), fuera el bloque (D43), tildes (D45) |

---

## 2. Las columnas (D39)

| Antes | Ahora |
|---|---|
| Transaccion · Muestras · Promedio · **p90** · **Max** · Errores | Transacción · Muestras · Promedio · **TPS** · Errores |

**El TPS no se recalcula en el navegador.** Es el `rendimiento` que ya calcula
`get_summary_table_data` —`muestras / duración de toda la prueba`, §2.1— y que
el endpoint **tenía y no devolvía**. Añadirlo fueron tres líneas. Por eso el TPS
del panel es, cifra a cifra, el de la tabla resumen del informe: §4 lo comprueba
sobre las seis transacciones.

---

## 3. La fila desplegable (D40, D41)

Cada fila tiene un chevron. Al abrirla aparecen sus tres criterios
—Concurrencia esperada, Tiempo de respuesta (ms), Disponibilidad (%)— con un
botón **«Usar globales»**. **Pueden estar abiertas varias a la vez** y el
checkbox de selección no cambió.

- **Sin valores propios**, cada campo muestra **el global como marca de agua**
  y la fila dice *«Sin valores propios se evalúa con los criterios generales de
  arriba»* (D41).
- **Con valores propios**, la fila lleva una etiqueta **«criterios propios»** y
  «Usar globales» se habilita: pulsarlo borra los tres y devuelve la fila a como
  estaba.
- Al pie: *«La marca de crítica se recalcula con el tiempo de respuesta y la
  disponibilidad. La concurrencia se guarda con el informe pero no interviene en
  ese cálculo»* — porque es la verdad (reporte 42 §5) y es mejor decirlo que
  dejar que se descubra.

El bloque desplegable **«Criterios por Transaccion» ya no existe** (D43), ni su
«aplicar el mismo criterio a todas».

---

## 4. La regla en dos lenguajes, con paridad probada (D42)

La regla **solo vivía en Python**. Editar un criterio de una fila no puede
resubir el JTL entero, así que se portó a TS —`criticidad.ts`, puro, sin React—
y la paridad **no se confía a la lectura**:

`backend/tests/fixtures/criticidad_casos.json` tiene **16 casos de veredicto y
6 de señales**, y lo corren **los dos lados contra el mismo `esperado`**.

| Lado | Cómo | Resultado |
|---|---|---|
| Python | `pytest tests/test_criticidad_paridad.py` | **25 de 25** |
| TypeScript | `tsc` + `node` sobre el mismo JSON | **25 de 25** |

```
PARIDAD TS/PYTHON: TODOS LOS CASOS COINCIDEN
```

Los casos son los límites, no los cómodos: `p90` exactamente en el umbral (no
falla, la comparación es `>`), justo en el 80 % (no avisa) y un milisegundo por
encima (avisa); error exactamente en `100 − disponibilidad` y un pelo por
encima; disponibilidad al 100 %; criterios como texto, tal como salen del
formulario; pico relativo justo en 10 veces y justo por debajo; promedio cero.

**No hay runner de pruebas en el frontend y no se añadió uno**: habría metido
una dependencia de desarrollo y obligado a rehacer la imagen. El lado TS se
compila con el `tsc` que ya está y se ejecuta con `node`.

---

## 5. El texto bajo el nombre (D45)

| Antes | Ahora |
|---|---|
| `no apto por criterios (p90 175ms, 64.79% error)` | `no cumple: 1 de cada 10 usuarios espera más de 462 ms (el límite son 300 ms)` |
| `pico de 21060ms, 47x el promedio` | `pico de 21.060 ms, 47,3 veces su promedio` |
| `pico absoluto de 21060ms (>=10s, posible timeout)` | `pico de 21,1 segundos, que apunta a una espera agotada` |

Se redacta con los mismos helpers de `estilo.py` que usa el informe (`ms`,
`pct`, `veces`, `num`), así que el panel y el informe hablan igual. Y se redacta
**en los dos lenguajes**: el backend para la primera carga, el TS para los
recálculos.

---

## 6. Validación en pantalla (5.3, sin generar nada)

`panel_seleccion.py` con Playwright, subiendo el JTL de `ff186cc7` a «Nuevo
Reporte» y **sin generar el informe** — **24 de 24**:

```
columnas: ['transacción', 'muestras', 'promedio', 'tps', 'errores']
PASA  | esta la columna 'Transacción' / 'Muestras' / 'Promedio' / 'TPS' / 'Errores'
PASA  | NO esta la columna 'p90' / 'P90' / 'Max'
panel: 6 transacciones
PASA  | el panel lista las mismas 6 transacciones (6)
PASA  | el TPS de cada fila es el de la tabla resumen del informe
PASA  | el bloque 'Criterios por Transaccion' ya no existe
PASA  | tampoco su 'aplicar el mismo criterio a todas'
PASA  | al apretar el tiempo global aparece una critica SOLO por tiempo (1. Auth)
PASA  | la fila desplegada muestra 'Concurrencia esperada' / 'Tiempo de respuesta (ms)'
        / 'Disponibilidad (%)' / 'Usar globales'
PASA  | tres campos editables (3)
PASA  | el tiempo de respuesta muestra el global como marca de agua (100)
  antes:   1. Authcrítica / no cumple: 1 de cada 10 usuarios espera más de 462 ms
           (el límite son 100 ms)
  despues: 1. Authcriterios propios
PASA  | al relajar su tiempo de respuesta deja de ser critica
PASA  | el texto bajo el nombre cambio al instante
PASA  | 'Usar globales' la devuelve exactamente a como estaba

PANEL DE SELECCION: TODO EN VERDE
```

Una nota sobre cómo se montó ese caso: con los criterios de fábrica, las
críticas de ese JTL lo son **por errores**, y relajar el tiempo no las cambiaría.
Para probar justo lo que pide el guion —tocar el tiempo de respuesta de una
fila— la prueba **aprieta primero el criterio global a 100 ms**, con lo que
`1. Auth` (sin errores, `p90` 462 ms) pasa a ser crítica **solo por tiempo**; y
entonces su criterio propio la devuelve. Es el camino D41 + D42 completo.

---

## 7. La corrida real `E5-panel`

**22 llamadas, todas `outcome=ok`.** Ejecución
`c33488cb-5f1c-499b-86b3-4b58642c31cb`, el JTL de `ff186cc7`, dos transacciones:

- **`1. Auth`** con criterio **propio** de 300 ms (su `p90` es 462).
- **`2. Get Booking`** **sin** criterios propios, con el global de 2.000 ms.

Lo que quedó guardado:

```json
"per_transaction": { "1. Auth": { "response_time": 300, "availability": 99.5,
                                  "concurrency": 30, "error_rate": 0.5 } },
"verdicts_per_transaction": { "1. Auth": "NO APTO", "2. Get Booking": "APTO", ... }
```

`e5_verdictos.py` — **8 de 8**:

```
PASA  | los criterios propios del panel quedaron guardados
PASA  | su tiempo de respuesta propio es 300 ms
PASA  | '2. Get Booking' NO tiene criterios propios: va con los globales
PASA  | el veredicto guardado coincide con el que da la regla
PASA  | '1. Auth' es NO APTO por su criterio propio (NO APTO)
PASA  | '2. Get Booking' es APTO por los globales (APTO)
PASA  | con el criterio GLOBAL '1. Auth' seria APTO: la diferencia la hace el
        criterio propio
```

Esa última línea es la que cierra el círculo: **con el global la transacción
cumpliría; es el criterio propio del panel el que la hace fallar**, y así llegó
al informe.

Y la regla de TS, corrida sobre **las métricas reales de ese informe**, da lo
mismo:

```
PASA  | 1. Auth (informe E5-panel): esperado NO APTO, obtenido NO APTO
PASA  | 2. Get Booking (informe E5-panel): esperado APTO, obtenido APTO
```

| | `E5-panel` |
|---|---|
| Llamadas | **22 / 22 `ok`** |
| T1 − T0 | 68,8 s |
| T2 − T0 | **128,9 s** |
| Caché de prompt | 28,4 % |
| Sonda `/auth/me` | 67 muestras, 0 errores, máx 8,9 ms |

---

## 8. Regresión

| Prueba | Resultado |
|---|---|
| `tsc --noEmit` del frontend | **0 errores** |
| `pytest tests/` | **492 pasan**, 1 falla anterior a esta etapa (`37_HF-3_deuda.md` §6) |
| `verificar_etapa2.py` sobre `E5-panel` | **LAS CUATRO SALIDAS PASAN** |
| `verificar_etapa2.py` sobre `E3-estilo-pruebakinetix` | **LAS CUATRO SALIDAS PASAN** |

### Un defecto del arnés que salió a la luz

`verificar_etapa2.py` y `tabla_por_transaccion.py` esperaban **26 gráficas
fijas** — 11 del general más 5 × **3** transacciones. `E5-panel` tiene **2**, o
sea 21, y los dos pasos fallaban. **No era el producto**: todo lo demás pasaba,
incluidas las tablas de las dos transacciones.

Arreglado en el arnés: el número de bloques se lee del propio informe
(`transaction_chart_analyses`) y se espera `11 + 5 × n`. Con eso pasan tanto el
informe de 2 transacciones como el de 3.

---

## 9. Decisiones técnicas de estos sub-pasos

| # | Decisión | Por qué |
|---|---|---|
| **T18** | Se retira el `useEffect` con 800 ms de debounce que resubía el JTL al cambiar un criterio global | Con criterios por fila sería una resubida por tecla. La regla se recalcula en el cliente; las métricas siguen viniendo del endpoint |
| **T19** | El respaldo a `/extract-jtl-labels` deja de pintar panel | Los criterios viven dentro de la fila y una fila necesita sus métricas. Sin métricas no hay fila; quedan los criterios generales. El endpoint nuevo usa `JTLParser` y es estrictamente más capaz que el viejo |
| **T20** | La paridad TS se ejecuta con `tsc` + `node`, sin runner de pruebas | Añadir vitest o jest son dependencias nuevas y una imagen nueva, por una prueba |
| **T21** | El panel avisa por escrito de que la concurrencia no mueve la marca | Es editable (D40) y se guarda (D44), pero no entra en la regla (D42). Decirlo evita que se descubra por sorpresa |
| **T22** | El número de gráficas esperadas se deriva del informe, no se fija | Estaba clavado en 3 transacciones y rompía con cualquier otro número |

Siguiente: 5.4, el cierre.
