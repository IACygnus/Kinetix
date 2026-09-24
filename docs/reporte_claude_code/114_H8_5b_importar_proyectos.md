# ETAPA H8, SUB-PASO H8.5b — importar proyectos, estados y estimaciones

Commit base `679f186` · 24 de septiembre de 2026 · rama `backup-trabajo-local`
· **0 llamadas a la IA** · `pg_dump` previo de H8.1 en
`C:\proyectos\Kinetix_pruebas\backup_20260923_h8.sql`

**Sub-paso cerrado**, y con él la pantalla de H8.5 que quedaba pendiente.

| Suite | Comprobaciones |
|---|---|
| `h85_pantalla.py` (el borrado, en pantalla) | 22 |
| `h85b_proyectos.py` (el importador, por HTTP) | 53 |
| `h85b_pantalla.py` (el importador, en pantalla) | 24 |

---

## 1. La pantalla de H8.5, terminada

`components/horas/BorrarPeriodo.tsx`, al final de Importación, solo admin y
**plegado por defecto**.

Lo que la pantalla añade y el backend no puede hacer solo: **cambiar el rango
invalida la previa**. Un `useEffect` sobre `[desde, hasta]` borra la previa, la
casilla y el texto tecleado, y el botón desaparece con ellos. Sin eso se podría
revisar un rango y confirmar otro.

El botón se enciende solo con **la casilla marcada y la frase exacta**, y la
comparación de la pantalla es **la misma** que la del backend —sin tildes, sin
mayúsculas, sin espacios de más—: si fuera más estricta, el botón se quedaría
apagado con un texto que el backend sí acepta.

La suite lo comprueba en orden: apagado al ver la previa, apagado con la casilla
sin la frase, apagado con «agosto 2026», encendido con las dos, y **encendido
con `«  AGOSTO  de 2026 »`**.

---

## 2. El importador de proyectos

| Archivo | Qué |
|---|---|
| `services/horas/importacion_proyectos.py` | **NUEVO.** Las columnas, el lector de estados y la plantilla |
| `endpoints/time_import_proyectos.py` | **NUEVO.** Los tres endpoints |
| `schemas/time_tracking.py` | Los cuatro schemas |
| `components/horas/ImportarProyectos.tsx` | **NUEVO.** La pestaña |
| `pages/horas/ImportarPage.tsx` | Las dos pestañas |
| `api/horasApi.ts` | Tipos y llamadas |

**El importador de registros no se toca** (H-D94). De él se reutiliza el lector
—`filas_del_libro`, `leer_horas`, `limpiar_texto`, `FaltanColumnas`—, que ya está
medido contra los archivos reales de Fredy, y aquí solo vive lo propio de este
formato.

```
GET  /time/import/proyectos/plantilla   el .xlsx de ejemplo
POST /time/import/proyectos/preview     analiza y NO escribe
POST /time/import/proyectos/confirm     aplica, en una transacción
```

### Decisiones que tuve que tomar sobre la marcha

| Qué | Cómo, y por qué |
|---|---|
| **La misma actividad dos veces** en el mismo proyecto | La segunda fila se descarta, diciendo en qué fila estaba la primera. Dejarla pasar haría que el resultado dependiera del orden del archivo |
| **Un estado que no se reconoce** | Fuera, con la lista de los que valen. **No se adivina por parecido**: «terminado» se parece a «finalizado» y no es lo mismo |
| **§8 dentro del importador** | Una fila que ponga `no_viable` o `finalizado` **sin ser admin** se descarta con su motivo (H-D90). Si no, el importador sería la puerta de atrás del permiso |
| **El estado de un proyecto nuevo deja rastro** | Se escribe su `ProjectStatusChange` inicial, para que el historial de un proyecto importado empiece donde empieza el proyecto |
| **La ayuda de la plantilla, en otra hoja** | El lector toma la primera hoja (H-D47): una nota al pie en la columna «Cliente» se leería como una fila más y saldría en la previa como inválida |

### Lo que se acepta escrito en «Estado»

La clave interna, el rótulo de pantalla o el rótulo con espacios, todo
normalizado: `en_ejecucion`, `en ejecucion`, `En ejecución` y `EN EJECUCIÓN` son
el mismo estado. Vacío vale `en_ejecucion` (H-D95).

---

## 3. La validación

### `h85b_proyectos.py` — 53 comprobaciones

El archivo es el que pediste, todo en uno: un proyecto nuevo con tres
actividades, uno que ya existe, **un estado de cada uno de los cinco**, una fila
con estado inventado, una con las horas mal y una sin actividad.

| Bloque | Qué fija |
|---|---|
| 0 | La plantilla: cinco columnas, dos filas **del mismo proyecto**, y la ayuda en otra hoja |
| 1 | La previa: 10 filas, 3 apartadas con su motivo, 5 proyectos, el bloque del nuevo con **sus 3 actividades y sus 80 h**, el que ya existe con su «actualiza» y las horas que había. **Y no escribió nada** |
| 2 | La importación: 4 creados, 1 tocado, 6 estimaciones nuevas, 1 actualizada, 1 cambio de estado, 3 fuera |
| 3 | **Los cinco estados quedaron puestos**, uno a uno |
| 4 | Suman 114 h, y el cambio de estimación dejó su historial |
| 5 | **Reimportar el mismo archivo**: 0 creados, 0 nuevas, 0 actualizadas, **las 7 salen «iguales»**, las horas no cambian y no se escribe historial de más |
| 6 | **«Estado» es opcional**: un archivo sin esa columna se acepta y todo queda en ejecución |
| 7 | Sin una obligatoria, se para antes de leer filas y dice cuál falta |
| 8 | **El orden de las columnas da igual**, y «Estado » con espacio final también |
| 9 | Tu base sigue con sus 10 proyectos |

### Tres fallos que eran míos, no del código

Los tres primeros intentos fallaron y **ninguno era un defecto**:

1. esperaba «1 proyecto» en la base de pruebas, y hay otro de H1.3 que no es mío
   y no se toca (regla 30). Ahora se compara contra la foto de antes;
2. esperaba 7 líneas de historial y son 8: me había olvidado del «alta» del
   proyecto que la propia prueba crea por la vía normal;
3. y la tercera **comprobaba lo contrario de lo que debía**: daba por inválido un
   archivo sin la columna «Estado», que es justo la que H-D95 declara opcional.
   Reescrita, ahora comprueba que **se acepta** y que el proyecto queda en
   ejecución.

Lo cuento porque una prueba que afirma lo contrario de la especificación es peor
que no tenerla: habría pasado en verde el día que alguien hiciera obligatoria la
columna.

### `h85b_pantalla.py` — 24 comprobaciones

Las dos pestañas; que **la de horas sigue entera** después del cambio (H-D94);
la plantilla descargada de verdad desde el navegador y abierta con `openpyxl`
para mirar sus columnas; la previa con **un bloque por proyecto**, sus 40 h y sus
dos actividades; la fila mala con su motivo; **que hasta confirmar no hay nada en
la base**; y los dos estados puestos después.

---

## 4. Ya puedes cargar

El orden, y por qué:

1. **`pg_dump`** — el comando te lo da la pantalla con la fecha puesta.
2. **Borrar el periodo** — pestaña de Importar, bloque rojo del final.
3. **Proyectos y estimaciones** — pestaña «Proyectos y estimaciones». Si no
   quieres adivinar el formato, **Descargar plantilla** y rellénala.
4. **Registros de horas** — pestaña «Registros de horas», el de siempre.

Los proyectos primero porque el importador de horas **crea los que no existen
pero sin estimaciones** (§6.2.4): cargando proyectos antes, las horas caen sobre
proyectos que ya tienen sus estimadas y el desfase sale bien desde el principio.

**Los proyectos que quedaron de la carga anterior no se tocan** (H-D107). Si los
traes en el Excel, se actualizan; si no, se quedan como están.

---

## 5. Lo que queda

**H8.6** — regresión en serie, retirar los alias de H-D91, estrechar el CHECK a
cinco, regenerar `d1_cifras`, arreglar las dos suites del laboratorio que no
corren, reporte de cierre, `NN_H8_para_fredy_cierre.md` con un guion, commit y
push.

Pendiente de **tu validación visual** (regla 9) de las dos pantallas.
