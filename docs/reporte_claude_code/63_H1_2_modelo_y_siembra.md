4a61f7c · 2026-09-17

# ETAPA H1.2 — Modelo de datos y siembra del módulo de horas

**0 llamadas a la IA.** El módulo no usa IA en ningún punto.

Referencia: `docs/ESPECIFICACION-horas.md` v1.0 §1.

---

## 1. Las siete tablas

Todas **nuevas** (H-D1). Las crea `Base.metadata.create_all` al arrancar: sin ALTER, sin
Alembic, sin script manual. La base pasó de **18 a 25 tablas**.

| Tabla | Qué guarda | Claves |
|---|---|---|
| `activities` | catálogo global de actividades (§1.2) | `name_normalized` **único** |
| `projects` | proyecto de un cliente (§3) | nombre único **por cliente**, `status` ∈ {activo, cerrado} |
| `project_activities` | horas estimadas de cada actividad del proyecto | única por (proyecto, actividad), `estimated_hours > 0` |
| `project_activity_changes` | historial de estimaciones (H-D11) | `change_type` ∈ {alta, cambio, baja} |
| `time_entries` | el registro de horas (§1.1) | `external_id` único, índice (user_id, date) |
| `work_calendar` | jornada por día de la semana (H-D5) | `weekday` único, 0-6 |
| `holidays` | festivos y ausencias (H-D5) | índice parcial único para los nacionales |

`time_entries` **se crea ya**, entera, aunque el registro de horas no llegue hasta H2. En
este proyecto alterar una tabla existente exige un ALTER a mano (regla 10), y definirla
desde el principio es justo lo que evita esa deuda.

### Decisiones técnicas que declaro

| Decisión | Por qué |
|---|---|
| **`Numeric`, no `Float`, para todas las horas** | son horas y se suman. Un `float` acumula error y la comparación "consumido frente a estimado" (§5) acabaría mintiendo por decimales |
| **`weekday` 0 = lunes … 6 = domingo** | es el mismo criterio que `date.weekday()` de Python: no hay que traducir en cada consulta |
| **Festivos y ausencias comparten tabla `holidays`**, con `user_id` nulo para los nacionales | los dos casos se consultan igual al decidir si un día se reclama como incompleto (§4.2.7). Dos tablas serían la misma lógica escrita dos veces |
| **`normalizar()` vive en el modelo**, junto a las columnas que guardan su resultado | la usan el catálogo (H-D3) y usará la importación (§6.2.3). Poniéndola en un solo sitio, backend e importación no pueden acabar con dos ideas distintas de "el mismo nombre" |
| **Las restricciones de negocio también en la base** | ver §3: son la última red bajo la validación de backend y frontend |

### Índices

27 en total sobre las siete tablas, incluidos los que pedía el plan:

```
time_entries :: ix_time_entries_user_date      (user_id, date)  <- sostiene la vista semanal
time_entries :: ix_time_entries_external_id    único            <- idempotencia de la importación
project_activities :: ix_..._project_id / ix_..._activity_id
projects :: ix_projects_client_id / ix_projects_status
holidays :: ux_festivo_nacional                único parcial    <- where user_id is null
```

> El índice de los festivos nacionales es **parcial**. El `UNIQUE(date, user_id)` no basta:
> en Postgres varios `NULL` no chocan entre sí, así que sin el índice parcial se podrían
> insertar dos "Año Nuevo" nacionales el mismo día.

## 2. La siembra

`backend/app/db/seed_time_tracking.py`, llamada desde `startup_event` después de
`seed_admin_user`. Sigue su molde, incluida la parte de **capturar la excepción**: un fallo
de siembra no puede tumbar el arranque del backend.

**Idempotente por construcción**: cada bloque lee lo que ya existe y solo inserta lo que
falta. Corrida dos veces seguidas:

```
--- primera corrida ---
Horas: siembra ya estaba completa, nada que insertar
--- segunda corrida ---
Horas: siembra ya estaba completa, nada que insertar
```

(La primera ya salió completa porque el backend corre con `--reload` y había sembrado solo
al recargar `main.py`. Es la prueba más honesta que se podía pedir: sembró en el arranque
real, no en un script.)

### Qué quedó sembrado

**Las 5 actividades de §1.2**, con su nombre normalizado:

```
Planeación                     -> planeacion
Diseño y generación de script  -> diseno y generacion de script
Ejecución                      -> ejecucion
Análisis de resultados         -> analisis de resultados
Administrativas o gerenciales  -> administrativas o gerenciales
```

**La jornada (H-D5):** lunes a jueves `8.50`, viernes `8.00`, sábado y domingo `0.00`.

**40 festivos nacionales**, 20 de 2026 y 20 de 2027, de una **lista literal por fecha**
(H-D5). La decisión de Fredy de no calcularlos es la correcta: un algoritmo de Ley Emiliani
se equivoca en silencio y nadie lo nota hasta que alguien reclama un día; esta lista se
revisa de un vistazo y se amplía a mano.

> **La jornada no se pisa.** `_sembrar_jornada` solo inserta los días que falten, así que si
> alguien cambia las horas de un viernes a mano, la siembra del siguiente arranque las
> respeta.

## 3. Las restricciones, probadas contra la base

No basta con declararlas: se comprobó que **rechazan de verdad**, con inserciones reales en
una transacción que se limpia al final.

| Prueba | Resultado |
|---|---|
| `hours = 0,3` (no es paso de 0,25, H-D8) | **rechazada** por `ck_horas_cuarto` |
| `hours = 0,25` | **aceptada** |
| `estimated_hours = 0` | **rechazada** por `ck_estimacion_positiva` |
| Proyecto "Prueba H12" con "PRUEBA-H12" ya existente en el mismo cliente | **rechazado** por `uq_project_cliente_nombre` |

El último es el que más valor tiene: prueba que la unicidad funciona **sobre el nombre
normalizado**, no sobre el literal, y **por cliente**, no globalmente.

Los datos de prueba se borraron: `projects` y `time_entries` quedan en **0 filas**.

## 4. El módulo de análisis no se movió

Comparación columna a columna de `test_executions`, `clients` y `users`, **antes y después**
de crear las siete tablas:

```
$ diff /tmp/esquema_antes.txt /tmp/esquema_despues.txt
IDENTICO: test_executions, clients y users no cambiaron (68 columnas)
```

Sin una sola diferencia. Es lo que garantiza H-D1: el módulo de horas **solo añade**.

Además: `pytest` sigue en **492 pasan, 1 falla** — la misma anterior al plan
(`analysis_pipeline.time`), documentada en el checklist. Y `/health` responde **200**.

## 5. Archivos

| Archivo | Líneas | Protegido |
|---|---|---|
| `backend/app/db/models/time_tracking.py` | **nuevo**, 243 | no |
| `backend/app/db/seed_time_tracking.py` | **nuevo**, 174 | no |
| `backend/app/main.py` | +11 | no |

En `main.py`, los dos cambios son los que el diagnóstico había señalado como fáciles de
olvidar: **importar los modelos** (sin eso `create_all` no los ve) y **llamar a la siembra**
al final de `startup_event`. Copia de seguridad `main.py.bak_h1_H1.2_20260917`.

## 6. Una línea de despliegue, y sigo

Las siete tablas aparecen solas al arrancar el backend, así que **en el servidor no hay que
ejecutar ningún SQL**. Es la diferencia con `reasoning_effort` de la Etapa 2, que sí era una
columna sobre una tabla existente. Nada más que anotar.

---

**Estado:** H1.2 cerrado. Las siete tablas creadas y verificadas, la siembra es idempotente
y comprobada, y el esquema de análisis está intacto. Sigue H1.3 — backend de Actividades y
Proyectos.
