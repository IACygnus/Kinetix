2543726 · 2026-09-18

# ETAPA H5.2 — Los datos del informe

**0 llamadas a la IA.**

---

## 1. Un endpoint, diez secciones

`GET /time/informe` con los filtros de H-D53 —personas, rango, cliente, proyecto
y solo facturables— devuelve las diez secciones **ya calculadas**. La plantilla
pinta; no suma.

| Archivo | Qué es | Líneas |
|---|---|---|
| `backend/app/services/horas/informe_datos.py` | **nuevo** — las diez secciones en una pasada | 310 |
| `backend/app/api/v1/endpoints/time_informe.py` | **nuevo** — el endpoint y sus límites | 70 |
| `backend/app/schemas/time_tracking.py` | los diez schemas del informe | +120 |

**Un solo endpoint y no seis**, a propósito: seis llamadas desde la pantalla
darían seis momentos distintos de la base, y el resumen de las 10:00 con el
detalle de las 10:01 no cuadran. Cuadrar es justo lo que se le pide a un informe.

**Y ninguna definición nueva**: la jornada y el día incompleto salen de
`calendario.py`, el estado de desfase de `desfase.py`, y el detalle de
`_responder()` de H2. Si el informe las reescribiera, diría que un día está
completo mientras el calendario lo pinta en ámbar.

---

## 2. Tres decisiones, declaradas

**La jornada esperada llega hasta hoy, no hasta el final del periodo.** Un
informe del mes en curso pedido el día 2 habría enseñado una ocupación del 2 %
contra las 185 h del mes entero. Y peor: `pending_days` ya excluía el futuro
desde H2b, así que la ocupación y los días pendientes se habrían medido con
reglas distintas. Ahora las dos usan la misma.

**El filtro de «solo facturables» no toca la jornada esperada.** Lo que a una
persona le tocaba trabajar no depende de qué se le cobra a quién. Está probado:
con el filtro puesto, las horas esperadas siguen ahí.

**El mapa marca «incompleto» antes que «trabajado».** Un día con 4 de 8,5 tiene
horas y aun así hay que verlo en ámbar: es de lo que sirve el mapa.

Y una cuarta, heredada: el desfase de la sección 6 se mide contra **lo consumido
de siempre**, no contra el rango, igual que en la consulta de §5.

---

## 3. Validación — 60 comprobaciones, todas pasan

Lo que de verdad importa de un informe es que sus cifras cuadren. Se comprueba
**sección contra sección** y contra las dos pantallas que ya existían:

```
=== 2. Una cifra, una fuente ===
    resumen: 33.50 h · ord 31.50 · extra 2.00 · fact 29.50 (88.05 %) · pendientes 24
PASA  | la seccion 2 suma lo mismo que el resumen (33.50)
PASA  | la seccion 4 tambien (33.50)
PASA  | y la seccion 5 (33.50)
PASA  | y la seccion 3 (33.50)
PASA  | y la seccion 9, celda a celda (33.50)
PASA  | y el mapa de la seccion 7 (33.50)
PASA  | y el detalle de la seccion 10 (33.50)
PASA  | ordinarias + extra = total

--- contra la CONSULTA de §5 ---
PASA  | el informe y la consulta dicen lo mismo (33.50 h)
PASA  | y las extra tambien (2.00)

--- contra el CALENDARIO de §4 ---
PASA  | mis ordinarias: calendario 25.50 · informe 25.50
PASA  | mis extra: calendario 2.00 · informe 2.00
PASA  | mis dias pendientes: calendario 10 · informe 10
PASA  | la jornada del informe llega hasta hoy (109.50 de 177.00)
```

La última línea es la decisión del punto 2 vista en números: el mes entero pide
177 h, pero a día 18 solo se han devengado 109,5.

El resto: el festivo y el fin de semana salen con su estado en el mapa y **no**
en los días pendientes; ningún día futuro se pinta como incompleto; el proyecto
pasado de horas sale «Desfasado +1 h» y primero; los cuatro filtros funcionan; y
los bordes —rango sin datos, rango al revés, rango de años— responden lo que
deben (200 con todo en cero, 400, 400).

---

## 4. Lo que viene

H5.3 convierte estos datos en el documento HTML autocontenido. No habrá que
calcular nada ahí: solo pintarlo.
