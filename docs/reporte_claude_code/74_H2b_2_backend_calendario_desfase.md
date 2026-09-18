ca80f4a · 2026-09-17

# ETAPA H2b.2 — El backend del calendario y el estado de desfase

**0 llamadas a la IA.** Ni una: este módulo no las usa.

---

## 1. Qué se pidió y qué hay

El sub-paso pedía tres cosas: el mes entero servido por el backend, el estado de
desfase de §5.1 en proyectos y actividades, y la validación de los bordes.
Las tres están. Por el camino aparecieron **dos defectos de H2** que el
calendario dejaba a la vista, y se arreglaron aquí porque el calendario no se
puede entregar con ellos. Van explicados en el punto 4.

| Archivo | Qué es | Líneas |
|---|---|---|
| `backend/app/services/horas/desfase.py` | **nuevo** — el estado de §5.1, en un solo sitio | 93 |
| `backend/tests/test_horas_desfase.py` | **nuevo** — 26 tests, casi todos de bordes | 121 |
| `backend/app/api/v1/endpoints/time_entries.py` | `GET /time/month` | +77 −8 |
| `backend/app/api/v1/endpoints/time_projects.py` | el estado en el listado y en el detalle | +35 −9 |
| `backend/app/schemas/time_tracking.py` | `MonthResponse`, `MonthDayResponse` y 4 campos | +49 −2 |
| `backend/app/services/horas/calendario.py` | la cuarta regla y las horas que se reclaman | +44 −5 |
| `backend/tests/test_horas_calendario.py` | 6 tests de lo anterior | +51 |

Ningún archivo protegido. Ningún compose. Ningún ALTER: los cuatro campos nuevos
se calculan, no se guardan.

---

## 2. El estado de desfase (§5.1)

`desfase.py` es un módulo de cuatro funciones y ninguna dependencia. Existe por
la misma razón que `calendario.py` en H2 y que `criterios.py` en la Etapa 5b: el
listado de proyectos, el detalle del proyecto y —más adelante— los reportes
necesitan el mismo cálculo, y escribirlo tres veces acaba en tres respuestas
distintas para el mismo proyecto sin que nadie se entere.

```
    < 90 %          en rango
    90 % – 100 %    por agotarse
    > 100 %         desfasado
```

**Los dos bordes, decididos y declarados:**

- **El 90 % exacto ya avisa.** Un proyecto con 9 de 10 horas consumidas sale
  «Por agotarse». El aviso llega al llegar al umbral, no un cuarto de hora
  después; si no, el umbral no serviría de nada.
- **El 100 % exacto NO es desfase.** Consumir justo lo estimado es cumplir, no
  pasarse. Solo por encima. Un proyecto que cierra clavado en sus horas no puede
  salir en rojo.

Y una tercera, que no es un borde sino un agujero: **sin estimación no hay
desfase posible**. Los proyectos que crea la importación (§6.2.4) nacen sin
horas, y dividir por cero ahí habría tumbado el listado entero. Devuelven 0 % y
«En rango».

La etiqueta la arma el backend ya en español —`Desfasado +4,5 h`, con coma y sin
ceros de relleno— para que la pantalla no vuelva a formatear un número que ya
venía formateado.

**«Desfase», no «exceso» (H-D27).** Los nombres internos que ya existían
—`over_estimate`— se quedan como estaban: cambiarlos obligaría a tocar el
contrato que H1 y H2 dejaron cerrado, y lo que Fredy pidió cambiar es lo que se
lee, no lo que se llama por dentro. Lo que sí se comprobó es que la palabra
«exceso» **no sale del backend** en ninguna de las tres respuestas.

---

## 3. El mes (`GET /time/month`)

Un mes, casilla a casilla, ya resuelto: horas registradas, jornada esperada, si
es festivo o ausencia, si está incompleto y por cuánto, cuántos registros tiene y
si alguno toca una actividad desfasada. **La pantalla pinta, no calcula.**

Reutiliza `construir_dias` y `dias_pendientes`, los mismos que resuelven la
semana y el panel de pendientes. No hay una segunda definición de «día
incompleto» en el módulo, y por eso el calendario del mes y el panel de
pendientes no pueden contradecirse.

Los cuatro campos nuevos de proyectos y actividades —`consumed_pct`,
`overrun_status`, `overrun_hours`, `overrun_label`— son **añadidos**: todo lo que
ya consumía esas respuestas sigue recibiendo exactamente lo mismo.

---

## 4. Dos defectos de H2 que el calendario destapó

Los encontró la validación por HTTP, no una lectura del código. Ninguno se ve en
una vista semanal; los dos se ven a la primera en un mes.

### 4.1 El resto del mes salía en rojo

`dias_pendientes` sabía no listar el futuro —«un día que no ha llegado no es una
deuda»—, pero el día en sí no lo sabía: `incompleto` era `True` para cualquier
día laborable sin horas, incluidos los que aún no han llegado. En la semana en
curso se notaba poco. En un calendario abierto el día 1, **todo el mes aparecería
incompleto**.

La regla sube al día, que es donde ya estaban las otras tres, con un `hoy`
opcional: sin él nada se recorta —que es como se comportaba H2 y como lo esperan
sus tests—, y los tres endpoints lo pasan. **Hoy no es futuro**: la jornada de
hoy se registra hoy, y así lo contaba ya el panel de pendientes; cambiar eso
habría cambiado H2 por la puerta de atrás.

Antes del arreglo: 8 días futuros marcados incompletos. Después: 0.

### 4.2 Un festivo sumaba 8 horas a lo esperado del mes

`expected_hours` devolvía la jornada del calendario laboral incluso en un
festivo. El día no se reclamaba —eso estaba bien—, pero la casilla decía «8 h
esperadas» y, peor, **el total del mes las sumaba**: 185 h esperadas en un
septiembre que solo pide 177.

Ahora el día distingue dos cosas: `esperadas`, la jornada que le tocaba —sigue
ahí, es útil saberlo—, y `se_reclaman`, que es 0 en festivo, ausencia y fin de
semana (§4.2.7). Los endpoints enseñan y suman la segunda.

---

## 5. Validación

### `pytest` — 90 pasan

```
tests/test_horas_desfase.py          26 nuevos
tests/test_horas_calendario.py       35 (29 de H2 + 6 nuevos)
tests/test_time_tracking_reglas.py   29 de H1
```

Los 26 de desfase son casi todos de borde: 89,375 %, 89,75 %, **90 %**, 97,5 %,
**100 %**, 100,62 %, 122,5 %, y el caso sin estimación. Los 29 de H2 pasan sin
tocarles una línea, que es la comprobación de que el `hoy` opcional no cambió lo
que ya funcionaba.

### HTTP — `h2b2_backend.py`, todo pasa

El script arma un mes con las cuatro situaciones de §4.1 a la vez —un festivo, un
día incompleto, un día con extras y un día con desfase— y tres proyectos, uno por
estado. Crea sus propios datos y los borra al terminar, **incluso si falla a
mitad** (regla del reporte 38).

```
--- el festivo (§4.2.7) ---
PASA  | sale como festivo
PASA  | y NO se reclama aunque no tenga horas
PASA  | no espera horas (0)

--- el dia incompleto (H-D24) ---
PASA  | faltan 6.50 de 8,5

--- el dia con extras (H-D17) ---
PASA  | un dia con extras NO se marca incompleto

--- el dia con desfase (H-D27) ---
PASA  | el martes avisa que toca una actividad desfasada
PASA  | el lunes, que no la toca, no avisa

--- fin de semana y totales ---
PASA  | ningun dia futuro se marca incompleto (0)
    totales: esperadas 177.00 · ordinarias 32.00 · extra 3.00 · pendientes 9

=== 3. Los tres estados en el listado de proyectos (§5.1) ===
PASA  | 'Proyecto H2b en rango': 33.75 % · en_rango · «En rango»
PASA  | 'Proyecto H2b por agotarse': 90.00 % · por_agotarse · «Por agotarse»
PASA  | 'Proyecto H2b desfasado': 212.50 % · desfasado · «Desfasado +4,5 h»
PASA  | 9 de 10 ya avisa, no espera a pasarse

=== 5. La palabra «exceso» no sale del backend (H-D27) ===
PASA  | ni en el listado, ni en el detalle, ni en el mes
```

### Regresión de H2 — `h22_backend.py`, todo pasa

Los 40 chequeos del registro de horas siguen verdes con la semana tocada: la
jornada, las extras, el festivo, los pendientes, los permisos y el proyecto
cerrado.

---

## 6. Lo que queda

La pantalla. El backend ya sirve el mes entero y los tres estados; H2b.3 lo
pinta, H2b.4 lleva la alerta al listado de proyectos y H2b.5 lo recorre de punta
a punta con Playwright.
