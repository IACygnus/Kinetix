# ETAPA H8, SUB-PASO H8.5 — el borrado de los registros de un periodo

Commit base `679f186` · 24 de septiembre de 2026 · rama `backup-trabajo-local`
· **0 llamadas a la IA** · `pg_dump` previo de H8.1 en
`C:\proyectos\Kinetix_pruebas\backup_20260923_h8.sql`

**Backend y validación cerrados: 40 comprobaciones, 0 fallos.**
**La pantalla está escrita en el plan pero NO tocada**, esperando el visto bueno
de la regla 31 (R4): la aplicación puede estar abierta.

---

## 1. Los dos endpoints

| Verbo | Path | Qué |
|---|---|---|
| GET | `/time/borrado/preview?desde=&hasta=` | Solo lee. Admin |
| POST | `/time/borrado/confirm` | Borra. Admin. Una transacción |

**La previa es un `GET` a propósito**: así no hay ninguna ruta por la que ese
endpoint pueda modificar la base, ni equivocándose. La suite lo comprueba
igualmente contando los registros antes y después de pedirla.

Router propio, `/time/borrado`, y no una ruta más dentro de `time_entries.py`:
así se ve de un vistazo qué endpoints pueden borrar en bloque.

### Lo que devuelve la previa

```json
{
  "periodo": "septiembre de 2026",
  "total_entries": 24, "total_hours": "182.50",
  "por_persona": [{"user_name": "…", "entries": 24, "hours": "182.50"}],
  "de_importacion": 0, "manuales": 24,
  "frase_de_confirmacion": "septiembre de 2026",
  "comando_copia": "docker exec jmeter_postgres pg_dump …",
  "lo_que_no_se_borra": "Se borran SOLO registros de horas. No se toca nada más: …"
}
```

**`de_importacion` / `manuales`** no estaba en las condiciones y lo añadí porque
es lo que dice si estás borrando lo que subiste tú o algo que alguien tecleó a
mano. Si no lo quieres, se quita.

**`lo_que_no_se_borra` cuenta de verdad las cuatro tablas**, no lo afirma. Si
algún día este endpoint empezara a borrar de más, esa frase sería lo primero en
delatarlo.

El periodo lo escribe **`describir_periodo()`**, la misma función del informe.
Si la duplicara, la frase que tecleas y la que lees en el informe podrían acabar
diciendo cosas distintas del mismo rango.

### Las condiciones del `confirm`, en orden

1. **Admin** → 403.
2. **`copia_hecha`** sin marcar → 400. Va primera porque es la que no tiene
   vuelta atrás si falta.
3. **La frase**, comparada con `normalizar()`: sin tildes, sin mayúsculas, sin
   espacios de más. `«Agosto de 2026»` vale; `«agosto 2026»` **no**.
4. **Nada que borrar** → 404, para no dejar constancia de un borrado vacío.
5. Y entonces **un solo `DELETE ... WHERE date BETWEEN`**, dentro de la
   transacción de la petición.

**Kinetix no ejecuta `pg_dump`** (H-D89). Da el comando con la fecha puesta.

---

## 2. La constancia — `time_entry_purges`

Tabla nueva, la crea `create_all`, **sin SQL que ejecutar**:

| Columna | Qué |
|---|---|
| `desde` · `hasta` | El rango, tal como se pidió |
| `entries_deleted` · `hours_deleted` | Cuánto se fue |
| `confirmation_text` | **Lo que se tecleó, literal** |
| `performed_by` · `performed_at` | Quién y cuándo |

Más el `logger.warning` con lo mismo.

Guardo el texto tecleado literal porque, si algún día hay dudas, dice que el
borrado se confirmó a mano y con qué palabras. Y la tabla existe porque **el log
del contenedor se pierde en cada reconstrucción**, y el 18 de septiembre de 2026
la pregunta que no se pudo contestar fue exactamente esa.

Del producto no se borra nunca: es el rastro, no un dato de trabajo.

---

## 3. La validación — `backend/pruebas_e2e/h85_borrado.py`

**40 comprobaciones, 0 fallos.** Contra el 8002 y `jmeter_analyzer_test`, con el
freno de la regla 34.

La suite está escrita al revés de lo normal: la mayor parte comprueba **lo que
no tiene que pasar**.

| Bloque | Qué fija |
|---|---|
| 1 | La previa cuadra —registros, horas, personas, origen—, trae la frase y el comando, dice con esas palabras qué sobrevive, y **no escribe nada** |
| 2 | **Seis intentos rechazados**: analista (403 al borrar y 403 hasta para ver la previa), sin casilla, frase vacía, frase casi bien, frase de otro periodo, rango cambiado. **Y después no falta ni un registro** |
| 3 | `«  JULIO  de 2026 »` se acepta como `julio de 2026` |
| 4 | El borrado: 3 registros, 12 h, y quién |
| 5 | **Se fueron solo los del rango** —el de fuera sigue— y `projects`, `project_activities`, `activities`, `clients` y `project_activity_changes` **siguen contados igual** |
| 6 | La fila en `time_entry_purges`, con el texto literal |
| 7 | **Tu base sigue con sus 24 registros** y sin ningún borrado registrado |

El bloque 7 es el que pediste, y lo hago aunque esta suite no pueda tocar tu
base: después de un borrado en bloque eso se comprueba, no se supone (regla 33).

### Un arreglo de paso en las suites

`h82_estados` creaba el analista, entraba y **lo borraba al terminar**. Eso
obligaba a un login nuevo en cada pasada, y `/auth/login` admite **cinco por
cuarto de hora y por IP, contando los correctos** (regla 26): tres corridas
seguidas dejaban la plataforma sin acceso.

Ahora el analista es un fixture compartido en `pruebas_e2e/analista_de_pruebas.py`
—una sola definición, la usan `h82` y `h85`—, **persistente y marcado
`zztest_`**. Es la excepción razonada a la limpieza por prefijo: el dato existe
para las pruebas, está marcado como tal, y borrarlo en cada pasada cuesta más de
lo que protege. Se retira a mano con
`python3 /tmp/e2e/analista_de_pruebas.py`.

---

## 4. La pantalla, pendiente de tu visto bueno (R4)

**No he tocado `frontend/`.** Cuando digas, va así:

- **`components/horas/BorrarPeriodo.tsx`**, nuevo, y un bloque al final de
  `ImportarPage`, **solo admin**;
- **plegado por defecto**, con un encabezado que hay que abrir;
- **la previa se invalida al cambiar el rango**: cualquier cambio en las fechas
  borra la previa, la casilla y el texto tecleado, y el botón vuelve a
  desactivarse. No se puede confirmar un rango distinto del revisado;
- el comando de la copia con botón de copiar;
- el botón se activa solo con la casilla marcada **y** la frase exacta;
- y `horasApi.ts` con los dos métodos.

---

## 5. Lo que tienes que tener listo antes de borrar

### La copia

```
docker exec jmeter_postgres pg_dump -U jmeter_user -d jmeter_analyzer_db \
  > C:/proyectos/Kinetix_pruebas/backup_antes_de_borrar_20260924.sql
```

La pantalla te lo dará ya escrito con la fecha del día.

### Los dos Excel, en este orden

1. **Proyectos y estimaciones** — el importador es H8.5b, que va ahora.
2. **Registros de horas** — el formato de §6.1, que ya funciona.

El orden importa: el importador de horas **crea los proyectos que no existen,
pero sin estimaciones** (§6.2.4). Cargando proyectos primero, las horas caen
sobre proyectos que ya tienen sus horas estimadas y el desfase sale bien desde
el principio.

### Dos avisos

- **Los proyectos de la importación anterior siguen ahí**, sin horas. El borrado
  solo quita registros (H-D107 dice que el importador tampoco los toca).
- Como se borran los `external_id`, **volver a subir el mismo archivo lo carga
  de nuevo** en vez de actualizarlo. Que es lo que quieres para empezar de cero.

---

## 6. Lo que queda

- La pantalla de H8.5 (§4, esperando tu visto bueno).
- **H8.5b** — el importador de proyectos, estados y estimaciones.
- H8.6 — regresión, alias de H-D91 fuera, CHECK a cinco, `d1_cifras`
  regenerada, las dos suites del laboratorio, y cierre.
