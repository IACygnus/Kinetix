9332fa9 · 2026-09-18

# ETAPA H3.6 — La importación, contra el archivo real

**0 llamadas a la IA.** El archivo es `horas_muestra.xlsx`, el de verdad de la
herramienta de horas: **21 filas, 75,5 h**.

---

## 1. Lo que el archivo resultó ser

Antes de importarlo lo leí con biblioteca estándar —sin `openpyxl`, que todavía
no estaba— para comprobar cada decisión contra el archivo y no contra una
suposición.

| | Medido |
|---|---|
| Hojas | **1**, llamada `Worksheet` (H-D47) |
| Filas de datos | **21** |
| Total de horas | **75,5** |
| Títulos con espacio final | **siete**: `Cliente `, `Proyecto `, `Tarea `, `Tipo de hora `, `Fecha `, `Tiempo total `, `Facturable ` |
| Fechas | texto `dd/mm/aaaa`, del 1 al 10 de septiembre |
| Horas | número con punto: `1`, `0.5`, `7`, `2.5`… todas múltiplo de 0,25 |
| `Facturable` | `Si` / `No` — 7 filas facturables |
| `Extra Hour` | `No` en las 21 |
| `Id` | 21, **todos distintos y ninguno vacío** |
| Observaciones | **9 filas** con saltos de línea y espacio fino U+202F |
| Clientes · proyectos · actividades | 6 · 9 · 6 |

**Una corrección a H-D42:** los títulos con espacio final son **siete**, no seis
— `Tipo de hora ` también lo lleva. No cambia nada, porque se comparan
normalizados, pero queda dicho.

Los 9 proyectos salen de contar **cliente + nombre**: «Preventa» aparece bajo dos
clientes distintos y son dos proyectos, no uno. Es lo que dice la restricción
`uq_project_cliente_nombre` que H1 puso.

---

## 2. La validación, paso a paso

`h36_importacion.py`. **Crea sus propios datos y los borra al terminar**, incluso
si falla a mitad (regla del reporte 38). Como la importación crea clientes,
proyectos y actividades en la base de verdad, **la limpieza va por diferencia**:
fotografía las cuatro tablas antes y borra solo lo que apareció después. Lo que
había de Fredy —8 clientes, 5 actividades, 1 proyecto, 2 registros— no se toca.

### La vista previa no escribe nada (§6.2.5)

```
PASA  | lee las 21 filas del archivo (21)
PASA  | las 21 son nuevas (21) · ninguna se actualiza todavia (0)
PASA  | ninguna invalida (0)
PASA  | suma 75.5 h (esperado 75.5)
PASA  | una sola hoja, «Worksheet» (H-D47)

    clientes:    ['Banco Occidente', 'Colcomercio', 'Ficohsa', 'SQ-AI Funcional', 'SQA CoE']
    actividades: ['Contextualización conocimiento proyecto', 'Gestión de proyectos', 'Preventa']
PASA  | y los proyectos nuevos (9)

--- la previa NO escribio nada ---
PASA  | no hay registros nuevos en la base · ni proyectos · ni clientes · ni actividades
```

Las tres actividades a crear son las que no estaban en el catálogo de cinco
(H-D48). `Ejecución`, `Planeación` y `Diseño y generación de script` **sí**
estaban y se reutilizan: la comparación normalizada hizo su trabajo.

### Confirmar, y que las horas se vean

```
PASA  | crea las 21 filas (21) · y no actualiza ninguna (0)
PASA  | 75.5 h importadas
PASA  | proyectos creados sin estimar: 9 (H-D37)
PASA  | el calendario de septiembre tiene 10 dias con horas
PASA  | la consulta ve 79.50 h en el rango
PASA  | los proyectos importados salen sin estimar (9)
PASA  | y NINGUNO sale desfasado: sin estimacion no hay desfase (H-D37)
```

Las 79,5 h de la consulta son las 75,5 del archivo más 4 que ya estaban: la
prueba no borra lo de Fredy y por eso la cifra es mayor.

### Reimportar: el total no cambia (H-D35)

```
PASA  | ninguna fila seria nueva (0)
PASA  | las 21 se actualizarian (21)
PASA  | y no habria que crear nada mas
PASA  | actualiza las 21 (21) · y no crea ninguna (0)
PASA  | EL TOTAL NO CAMBIA: 75.50 h antes, 75.50 h despues
PASA  | y siguen siendo 21 registros (21)
```

Es la comprobación que más vale de todo el sub-paso. La segunda pasada no crea ni
un cliente, ni un proyecto, ni una actividad: `normalizar()` los reconoce a todos.

### El proyecto creado, y sus horas (H-D37)

```
    proyecto: «SQA CoE» de SQA CoE
PASA  | nace sin horas estimadas (0)
PASA  | pero SI ensena lo consumido (2.00 h)
PASA  | y no sale desfasado (en_rango)
PASA  | y lista sus actividades aunque no esten estimadas (2)
PASA  | se le ponen 0.25 h estimadas (200)
PASA  | y AHORA si avisa del desfase (desfasado · «Desfasado +1,75 h»)
PASA  | con una estimacion holgada, vuelve a rango
```

Las dos líneas del medio son las que justifican los dos arreglos del reporte 80:
sin ellos, el proyecto habría enseñado **0 consumidas** y sus 21 filas habrían
salido **todas marcadas en ámbar** por haberse pasado de cero.

---

## 3. Dos fallos que solo se veían desde el navegador

La parte de HTTP pasó entera a la primera. La pantalla, no — y los dos fallos
eran **de la pantalla, no del backend**, así que ningún script de `httpx` los
habría encontrado nunca.

### 3.1 Un 422 al subir el archivo desde el navegador

El cliente axios de Kinetix manda `Content-Type: application/json` por defecto.
Mi `FormData` viajaba con esa cabecera, así que el multipart llegaba **sin su
frontera** y FastAPI contestaba 422. Todas las demás subidas del producto pasan
`'multipart/form-data'` explícitamente; esta no lo hacía.

Arreglado en `horasApi.ts` con una constante `MULTIPART` compartida por las dos
llamadas, y con el porqué escrito al lado para que no se repita.

### 3.2 La pantalla entera en blanco al pintar ese error

Y encima el error no se veía, porque **React reventaba al intentar pintarlo**:

```
Objects are not valid as a React child (found: object with keys {type, loc, msg, input, url})
```

Un 422 de FastAPI trae `detail` como **lista de objetos**, no como cadena. Mi
`setError(e?.response?.data?.detail || …)` metía esa lista en el JSX y tumbaba el
componente: pantalla en blanco, sin mensaje y sin pista. El patrón
`?.detail || 'texto'` está por todo el módulo de horas y funciona porque el resto
de errores son 400 con `detail` de texto; con un 422 no.

Ahora hay `mensajeDeError(e, porDefecto)` en `horasApi.ts`, que **siempre
devuelve texto**: si `detail` es una lista, junta los `msg`; si no reconoce nada,
usa el mensaje por defecto.

**Lo que esto dice del método:** la validación por HTTP y la validación por
pantalla no se sustituyen. Las 41 comprobaciones de `httpx` daban verde con la
pantalla rota de las dos formas posibles.

---

## 4. Regresión

**50 comprobaciones propias en `h36_importacion.py`**: 41 por HTTP y 9 en la
pantalla real.

| Prueba | Resultado |
|---|---|
| `pytest tests/` | **665 pasan**, 1 falla — la anterior al plan (reporte 66) |
| `npx tsc --noEmit` | sin errores |
| `h22_backend.py` (H2) | TODO PASA |
| `h2b2_backend.py` (H2b) | TODO PASA |
| `h32_consulta.py` (H3.2) | TODO PASA |
| `h15_pantallas.py` (H1) | TODO PASA |
| `h2b5_pantalla.py` (calendario H2b) | TODO PASA |
| `h33_pantalla.py` (consulta H3.3) | TODO PASA |
| `verificar_etapa2.py` — las cuatro salidas | **LAS CUATRO SALIDAS PASAN** |

---

## 5. Dos cosas que conviene saber del entorno

**El rebuild borra las herramientas de prueba.** Playwright y su Chromium vivían
**dentro del contenedor**, no en la imagen: al reconstruir desaparecieron, junto
con la sesión de `/tmp/e2e_sesion.json` y los scripts. Se repusieron desde
`C:\proyectos\Kinetix_pruebas\e2e`, que es donde está la copia buena. Conviene
saberlo antes del próximo rebuild: **no es un fallo, es dónde viven**.

**El primer intento de rebuild no llegó a aplicarse.** La imagen siguió siendo la
de dos semanas antes y `pip list` no tenía `openpyxl`; lo que sí cambiaba era
`/app/requirements.txt`, pero eso es el bind-mount del host, no la imagen. Se
detectó comparando la fecha de la imagen con la del contenedor, y se rehízo.
