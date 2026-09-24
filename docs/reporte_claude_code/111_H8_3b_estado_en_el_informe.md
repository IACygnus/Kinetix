# ETAPA H8, SUB-PASO H8.3b — el estado en el informe: una sola columna, al final y con color

Commit base `679f186` · 23 de septiembre de 2026 · rama `backup-trabajo-local`
· **0 llamadas a la IA** · `pg_dump` previo de H8.1 en
`C:\proyectos\Kinetix_pruebas\backup_20260923_h8.sql`

**Sub-paso cerrado.** Suite nueva: **51 comprobaciones, 0 fallos**. Capturas del
PDF rasterizado en `C:\proyectos\Kinetix_pruebas\h83b_capturas\`.

**Una cosa no salió como la validación pedía y no la he forzado**: `d1_cifras.py`
da un fallo, y es el correcto. Está en §4.

---

## 1. Lo que cambió

| Archivo | Qué |
|---|---|
| `docs/diseno-informe-horas.md` | **Primero**: las cinco píldoras del estado, con su origen (CLAUDE.md §1) |
| `services/horas/informe.py` | La columna, su CSS, el párrafo, y el rojo de «Restantes» |
| `pages/horas/InformesPage.tsx` | La vista previa dice lo mismo que el documento |
| `pruebas_e2e/h83b_informe.py` · `h83b_datos_informe.py` | **NUEVAS** |
| `pruebas_e2e/h83_pantallas.py` | Sus comprobaciones del informe se mudan a la de arriba |

### Los colores (H-D103)

Cuatro de los cinco salen de la paleta que ya estaba en el documento:

| Estado | Fondo | Texto | De dónde |
|---|---|---|---|
| Pendiente | `#f3f4f6` | `#4b5563` | `.pill.bien`, la neutra de siempre |
| En ejecución | `#bfdbfe` | `#03287D` | El azul de las extra (H-D85) sobre `--navy` |
| Detenido | `#fef3c7` | `#92400e` | `.pill.ojo`, sin cambio |
| No viable | `#e5e7eb` | `#991b1b` | Gris de §1.2 con la tinta roja de `.pill.mal` |
| Finalizado | `#dcfce7` | **`#166534`** | El verde del mapa · **el texto es el único tono nuevo** |

**«No viable» es rojo apagado, no rojo de alarma**: tinta roja sobre gris, no el
bloque `#fee2e2`. Por dos razones: un proyecto que no se va a hacer no es una
alarma que atender, y **`.pill.mal` sigue significando «desfase» en la sección
8** del mismo documento. La misma píldora para dos cosas se leería como una.

**El único tono nuevo es `#166534`.** Hacía falta porque `#dcfce7` es demasiado
claro para llevar texto de su color, y dejarlo en tinta negra habría hecho de
«Finalizado» la única píldora sin color de letra. Si prefieres no añadir tonos,
la alternativa es `--ink` `#0E1730` y se pierde solo esa coherencia.

Las clases son `est-<estado>`, **no** `bien`/`ojo`/`mal`. La suite comprueba que
ninguna de esas tres aparece en la sección 6.

---

## 2. Una consecuencia que conviene que sepas

Las filas de la sección 6 se teñían de fondo cuando el proyecto iba desfasado
(`tr.mal td{background:#fef2f2}`) o por agotarse (`tr.ojo`). **Ese tinte salía
del consumo**, que es justo lo que se retira, así que se ha ido con él.

Lo he quitado en vez de conservarlo por dos razones, y las dos son discutibles:

1. era la otra forma en que el consumo se colaba en la tabla, y H-D102 lo saca;
2. una fila teñida de rojo con una píldora verde de «Finalizado» al final se
   contradice a la vista.

El aviso lo da ahora **«Restantes» en rojo y en negrita** (H-D106). Si lo
prefieres más fuerte, **recuperar el tinte es una línea de CSS y una marca en el
`<tr>`**, y lo he dejado dicho en el propio código para que se encuentre.

---

## 3. La captura

`C:\proyectos\Kinetix_pruebas\h83b_capturas\h83b_p3.png` — la sección 6 con los
cinco estados, uno por fila:

```
Cliente          Proyecto                 En el periodo  Estimadas  Consumidas  Restantes   Estado
ZZTEST-Cliente…  ZZTEST-H83B-en-ejecucion       8,5 h        4 h        8,5 h    -4,5 h    [En ejecución]   azul
ZZTEST-Cliente…  ZZTEST-H83B-detenido             4 h       20 h          4 h      16 h    [Detenido]       ámbar
ZZTEST-Cliente…  ZZTEST-H83B-finalizado           4 h       20 h          4 h      16 h    [Finalizado]     verde
ZZTEST-Cliente…  ZZTEST-H83B-no-viable            4 h       20 h          4 h      16 h    [No viable]      rojo apagado
ZZTEST-Cliente…  ZZTEST-H83B-pendiente            4 h       20 h          4 h      16 h    [Pendiente]      neutro
```

El `-4,5 h` sale en rojo y en negrita; los `16 h` no. Ninguna fila lleva fondo
de color y no hay rastro de «Desfasado» ni de «En rango» en la tabla.

Las páginas 2 y 4 van también, para ver que el resto del informe no se movió.

---

## 4. `d1_cifras.py` falla, y el fallo es el correcto

La validación pedía que no cambiara ninguna cifra. **Cambia una, y es la que
mandaste retirar.**

```
FALLA | tabla 8: 26 cifras antes, 25 ahora
        primera diferencia en la posicion 5: antes «4,5», ahora «83»
FALLA | el mismo conjunto de cifras en todo el documento (124 antes, 123 ahora)
        solo antes: ['4,5']
        solo ahora: []
```

El `4,5` que falta es el de **«Desfasado +4,5 h»**, el texto de la columna de
consumo. Las otras **113 cifras son idénticas una a una**, y las nueve tablas
restantes pasan enteras. La misma magnitud sigue en el documento, en la columna
«Restantes», como `-4,5 h`.

**No he tocado `d1_cifras.py` para ponerlo en verde.** Esa prueba existe para
que el rediseño de D1 no pudiera mover un número, y enseñarle a ignorar la
sección 6 la dejaría sin filo justo donde acabamos de trabajar. Lo honesto es
que falle, que se lea por qué, y que quede escrito aquí. Cuando H8 cierre, en
H8.6, se decide si se regenera su `informe_antes.py` contra el estado nuevo —que
es lo que corresponde— o si se retira.

---

## 5. La validación

```
docker exec jmeter_backend python3 /tmp/e2e/h83b_datos_informe.py crear
docker exec jmeter_backend python3 /tmp/e2e/h83b_informe.py
docker exec jmeter_backend python3 /tmp/e2e/h83b_datos_informe.py limpiar
```

**51 comprobaciones, 0 fallos.** Los datos son un proyecto por cada estado, uno
de ellos desfasado a propósito, marcados `ZZTEST-H83B` (regla 29) y borrados
solo por ese prefijo (regla 30).

| Bloque | Qué fija |
|---|---|
| 1 | Las siete cabeceras en orden; «Estado» aparece **una** vez y es **la última**; «Consumo» no está |
| 2 | Ni «En rango», ni «Por agotarse», ni «Desfasado», ni «Terminado», ni las píldoras `bien`/`ojo`/`mal` en la tabla |
| 3 | Los cinco estados, cada uno con su píldora, su rótulo, **una sola píldora por fila** y **los colores exactos del documento de diseño** |
| 4 | «Restantes» en rojo solo cuando es negativo — el que va sobrado **no** lo lleva |
| 5 | El párrafo dice quién decide el estado y explica el rojo, y **ya no habla de dos columnas** |
| 6 | **Las pantallas no cambian** (H-D105): Proyectos y Consulta siguen trayendo estado *y* consumo |
| 7 | El PDF se genera y se rasteriza |

El bloque 3 compara los hexadecimales contra los del documento: **si alguien
cambia un color en el código sin pasar por `diseno-informe-horas.md`, falla.**

Las que ya existían —`h83_pantallas`, `h82_estados`, `h52_informe`,
`h53_h54_documento`— pasan. **Tu base: 10 proyectos, 24 registros, ningún
`ZZTEST`.**

---

## 6. Pendiente de tu visto bueno

1. **H-D106**, implementado: «Restantes» en negativo, en rojo y negrita.
2. **El tinte de fila retirado** (§2). Una línea si lo quieres de vuelta.
3. **`#166534`**, el único tono nuevo (§1).
4. **Qué hacer con `d1_cifras.py`** (§4).

Sigo con H8.4 — las horas extra en el mapa.
