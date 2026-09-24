# ETAPA H8, SUB-PASO H8.2 — el estado del proyecto en el backend

Commit base `679f186` · 23 de septiembre de 2026 · rama `backup-trabajo-local`
· **0 llamadas a la IA** · `pg_dump` previo de H8.1 en
`C:\proyectos\Kinetix_pruebas\backup_20260923_h8.sql`

**Sub-paso cerrado.** SQL de H8.1 aplicado por Fredy en las dos bases; el
recuento salió 10 en `en_ejecucion`. Suite nueva: **91 comprobaciones, 0 fallos**.
**Ni una línea de `frontend/`** (R4).

---

## 1. Lo que se hizo

Nueve archivos, 538 líneas añadidas y 102 quitadas. Ninguno protegido.

| Archivo | Qué |
|---|---|
| **`services/horas/estados.py`** | **NUEVO.** La definición única de §3.1 |
| `db/models/time_tracking.py` | `Project.status` y la tabla `project_status_changes` |
| `schemas/time_tracking.py` | Los campos de estado, el aviso de la importación |
| `services/horas/desfase.py` | El consumo baja a cuatro valores; «En rango» |
| `endpoints/time_projects.py` | El cambio de estado, su historial y el filtro |
| `endpoints/time_entries.py` | Qué estados admiten registros |
| `endpoints/time_import.py` | La excepción de §6.2.8 y su aviso |
| `endpoints/time_consulta.py` | El mismo filtro y las dos columnas |
| `services/horas/informe_datos.py` | La llamada; lo visual es H8.3 |
| `pruebas_e2e/h82_estados.py` | **NUEVA.** La suite |
| `pruebas_e2e/h2b2_backend.py` | Una línea: afirmaba el rótulo viejo |

### `estados.py`, y por qué existe

`cerrado` bloqueaba en **cuatro sitios distintos**, cada uno con su `if` y su
mensaje. Con cinco estados y dos reglas distintas —una para registrar, otra para
estimar, más la excepción de la importación— eso son quince condiciones sueltas,
y basta con que una se quede atrás.

Así que la tabla de §3.1 vive en un módulo y los endpoints preguntan:

```python
BLOQUEAN_REGISTRO    = {pendiente, detenido, no_viable, finalizado}
BLOQUEAN_ESTIMACION  = {no_viable, finalizado}
BLOQUEAN_IMPORTACION = {no_viable}          # §6.2.8, la excepción
SOLO_ADMIN           = {no_viable, finalizado}
OCULTOS_POR_DEFECTO  = {no_viable, finalizado}
```

Mismo criterio que `calendario.py` —la jornada— y `desfase.py` —el consumo—.

### `can_log_hours` y `can_edit_estimates`

Salen ya resueltos en `ProjectResponse`, como pediste. La pantalla de H8.3 los
consume; **no vuelve a escribir la tabla de §3.1 en TypeScript**. La suite
comprueba los dos contra la tabla, estado por estado, así que si alguien cambia
una regla en el backend y no en el otro lado, la prueba lo dice.

---

## 2. Tres cosas que aparecieron por el camino

### 2.1 La pantalla de Proyectos se iba a quedar en blanco hoy

`ProyectosPage.tsx:42` arranca con `filtroEstado = 'activo'` y lo manda en cada
carga. Mi validación nueva —«el estado tiene que ser uno de los cinco»— le
habría contestado **400**, y el listado de Fredy se habría quedado vacío entre
H8.2 y H8.3, sin que nadie lo hubiera pedido.

El arreglo no es aceptar `activo` a secas, porque **`activo` no equivale a
`en_ejecucion`**: quería decir «lo que no está cerrado», que ahora son tres
estados. Traducirlo a uno solo escondería los pendientes y los detenidos. Así
que `?estado=activo` se traduce al **filtro por defecto de H-D84** y
`?estado=cerrado` a `finalizado`. Dos comprobaciones de la suite lo fijan, una
de ellas justamente con un proyecto **detenido**.

Mismo criterio que el alias `incluir_cerrados`, y con la misma fecha de
caducidad: H8.6.

### 2.2 `desfase.py` cambió menos de lo que parecía, y `estado()` perdió un argumento

La clave interna ya era `en_rango`; solo cambió el rótulo. Lo que sí desapareció
es el quinto valor y el parámetro `cerrado: bool`, y eso obligó a tocar sus
**seis llamadas** en el mismo paso —por eso H8.2 no se podía partir—.

El efecto de fondo es el que quería H-D82: **antes, un proyecto cerrado tapaba
su consumo con la palabra «Cerrado»** y ya no se sabía si se había pasado de
horas. La suite lo fija con un proyecto que está `finalizado` **y** `desfasado`
a la vez, y comprueba que las dos columnas dicen cosas distintas.

### 2.3 Los dos atajos viejos se quedan, pero delegando

`POST /{id}/cerrar` y `/reabrir` siguen existiendo —el frontend los llama hasta
H8.3— y pasan por `_cambiar_estado`, así que escriben su historial y respetan el
permiso igual que el endpoint nuevo. No hay dos implementaciones: una de las dos
acabaría olvidándose de escribir el historial.

---

## 3. Lo que se decidió aquí

| # | Decisión |
|---|---|
| **H-D90** | **Poner un proyecto en `no_viable` o `finalizado` es del administrador** (§8). Son los dos que cierran el proyecto: lo esconden del listado y bloquean sus estimaciones. Los otros tres los cambia cualquier usuario. Es coherente con el 403 que ya existía al cerrar. Propuesta mía, aprobada por Fredy |
| **H-D91** | **Los nombres viejos se siguen aceptando hasta H8.6**: `?estado=activo\|cerrado` y `?incluir_cerrados`. Sin eso, la pantalla se rompe entre H8.2 y H8.3. `activo` se traduce al filtro por defecto, **no** a `en_ejecucion` |
| **H-D92** | **El historial del estado va en su propia tabla** (`project_status_changes`) y en su propio endpoint (`/historial-estado`). `project_activity_changes` exige `activity_id` y un tipo alta/cambio/baja, y un cambio de estado no tiene actividad ninguna. La pantalla los enseña juntos (H8.3), que es otra cosa |
| **H-D93** | **`normalizar_legado` traduce al leer.** El SQL ya migró las filas, así que no debería hacer nada; está porque el precio de equivocarse es asimétrico: en una base sin el script —la de pruebas que se recrea, la del servidor el día del despliegue— la API contestaría `activo` a una pantalla que solo entiende los cinco nuevos. Lo que se **escribe** siempre es uno de los cinco |

---

## 4. La validación — `backend/pruebas_e2e/h82_estados.py`

```
docker exec jmeter_backend python3 /tmp/e2e/h82_estados.py
```

**91 comprobaciones, 0 fallos.** Contra el 8002 y `jmeter_analyzer_test`
(regla 34), con datos `ZZTEST-H8` (regla 29) y limpieza solo por ese prefijo
(regla 30). El `limpiar()` se planta si la base no lleva «test» en el nombre.

| Bloque | Qué fija |
|---|---|
| 0 | El CHECK de la base acepta los cinco, y **no queda ningún proyecto en `activo` ni `cerrado`** |
| 1 | Un proyecto nace `en_ejecucion` |
| 2 | El consumo se lee **«En rango»**, y el estado sigue diciendo «En ejecución»: son dos columnas |
| 3 | **La tabla de §3.1 entera**: los cinco estados × registrar × estimar × `can_*`, y que el 409 dice en qué estado está |
| 4 | El historial: cinco cambios, el más reciente primero, de dónde venía y quién |
| 5 | Un estado inventado da 400; repetir el que ya tiene, 409 |
| 6 | Un analista pone `detenido` (200) y **no** `no_viable` ni `finalizado` (403); el admin sí |
| 7 | El filtro por defecto, los dos parámetros, y **los dos nombres viejos** |
| 8 | Un proyecto `finalizado` **y** `desfasado +2 h` a la vez |
| 9 | La consulta usa el mismo criterio y separa las dos columnas |
| 10 | §6.2.8: la fila del proyecto **detenido entra**, la del **no viable se rechaza** con su motivo, el aviso dice **1 fila, en qué proyecto, en qué estado y cuántas horas**, y la previa **no escribió nada** |

La suite crea un analista de prueba y **guarda su sesión** en
`/tmp/e2e_analista_h8.json` para reutilizarla: `/auth/login` admite cinco
intentos por cuarto de hora y los correctos también consumen cupo (regla 26);
repetir la suite tres veces bastaría para dejar la plataforma sin acceso.

### Las que ya existían

`h22_backend`, `h32_consulta` y `h52_informe` pasan sin tocarlas. **`h2b2_backend`
falló**, y con razón: afirmaba el rótulo «En ejecución» para el consumo, que es
justo lo que H-D82 cambió. Una línea.

### La base de Fredy, antes y después

```
proyectos=10   en_ejecucion=10   horas=24   cambios_estado=0
```

Intacta. Los residuos `ZZTEST-` que quedan en la base de **pruebas** —cuatro
clientes y un usuario— son de O2a, O2c y H7, no de esta etapa, y por la regla 30
no se tocan.

---

## 5. Lo que queda

- **H8.3** — las dos columnas en Proyectos, Consulta y el informe; el selector de
  estado; el historial junto al de estimaciones. **Que la pantalla consuma
  `can_log_hours` y `can_edit_estimates`**, no que los deduzca. Y pasar la
  casilla y el filtro a los nombres nuevos.
- H8.4 — las horas extra en el mapa.
- H8.5 — el borrado del periodo.
- H8.6 — regresión, retirar los alias de H-D91, estrechar el CHECK a cinco
  (`h8_estado_proyecto_cierre.sql`), las dos suites del laboratorio que no
  corren, y cierre.
