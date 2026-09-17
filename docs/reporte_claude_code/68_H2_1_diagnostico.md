9f00ef7 · 2026-09-17

# ETAPA H2.1 — Diagnóstico del registro de horas (read-only)

**0 llamadas a la IA.** Ningún archivo tocado, nada escrito en la base.

Referencia: `docs/ESPECIFICACION-horas.md` v1.0 §1.1, §4 y §8.

---

## 1. Lo que H1 dejó hecho y H2 reutiliza

### `time_entries` está completa — **no hace falta ningún cambio de esquema**

Verificado contra la base. Las catorce columnas de §1.1 están, con sus restricciones:

```
id · external_id (único) · user_id · created_by · date · project_id · activity_id
hours numeric(6,2) · billable · overtime · notes · source · created_at · updated_at

ck_horas_positivas      hours > 0
ck_horas_cuarto         (hours * 100)::int % 25 = 0      <- H-D8, la última red
ck_origen               source in ('manual','import')
ix_time_entries_user_date  (user_id, date)               <- el índice de la vista semanal
```

Fue la decisión de H1.2 de crearla entera aunque no se usara: se paga ahora, y **H2 no tiene
que alterar nada**.

### El calendario, sembrado

```
jornada  : 0=8.50  1=8.50  2=8.50  3=8.50  4=8.00  5=0.00  6=0.00
festivos : 40 nacionales (2026 y 2027)   ·   ausencias: 0
```

### `_consumido` ya suma lo que hay que sumar (H-D22)

`time_projects._consumido` hace `SUM(hours) GROUP BY activity_id` **sin filtrar por
`overtime`**. Eso es justo lo que pide H-D17: las horas extra consumen la estimación del
proyecto. **No hay que tocar el detalle de proyecto ni su contrato**; hoy devuelve 0 porque
la tabla está vacía y empezará a devolver datos reales en cuanto H2 escriba el primer
registro.

`over_estimate` y `remaining_hours` también existen ya en `ProjectActivityResponse`: el aviso
de exceso de H-D16 se alimenta de campos que ya están.

### `horasApi.ts`

Trae el cliente de `/time`, el formateador español `horas()` y `esPasoValido()` para el paso
de 0,25. H2 añade los métodos del registro al mismo objeto, sin tocar lo existente.

### Estado de los datos

`projects: 0` y `time_entries: 0` — las pruebas de H1 limpiaron lo suyo. **H2 crea sus
propios datos de prueba y los borra**, igual que H1.

## 2. Dónde vive el cálculo de la jornada y de los días pendientes

**Decisión: un módulo nuevo, `backend/app/services/horas/calendario.py`.** No es un archivo
protegido y no existe todavía la carpeta `services/horas/`.

Por qué ahí y no dentro del endpoint: la misma cuenta la necesitan **dos** endpoints —
`/time/week` y `/time/pending-days`— y si se escribe dos veces acabarán discrepando en algún
borde (un festivo en viernes, un día con extras). Es el mismo criterio que llevó a
`services/ai/criterios.py` en la Etapa 5b, donde el texto de la IA y la tabla de veredictos
resolvían el umbral por separado y podían contradecirse.

Lo que expone:

| Función | Qué responde |
|---|---|
| `jornada_de(fecha, calendario)` | horas esperadas ese día de la semana |
| `resumen_de_dia(...)` | esperado, ordinario, extra, si es festivo o ausencia, si está incompleto y por cuánto |
| `dias_pendientes(...)` | los días del rango sin registro o por debajo de la jornada |

**La pantalla no recalcula nada.** El backend devuelve por día `expected`, `ordinary`,
`overtime`, `is_holiday`, `incomplete` y `missing_hours`, y la pantalla solo los pinta. Si la
jornada cambiara en `work_calendar`, cambia en un sitio.

Las tres reglas de §4.2.6 y §4.2.7 quedan dentro de esa función, no repartidas:

1. un día por debajo de su jornada está incompleto, y falta la diferencia;
2. **un día con horas extra nunca se marca incompleto** (H-D17);
3. **festivos y ausencias no se reclaman** — y se consultan igual, porque H1 los puso en la
   misma tabla `holidays` con `user_id` nulo o con valor.

## 3. Nada protegido, nada de esquema

| Qué hace falta | Archivo | ¿Protegido? |
|---|---|---|
| Cálculo del calendario | `services/horas/calendario.py` (**nuevo**) | no |
| Endpoints del registro | `api/v1/endpoints/time_entries.py` (**nuevo**) | no |
| Schemas | `schemas/time_tracking.py` (existente, se amplía) | no |
| Registro del router | `api/v1/api.py` | no |
| Pantalla | `pages/horas/RegistroPage.tsx` (**nuevo**) | no |
| Menú y ruta | `Sidebar.tsx`, `App.tsx` | no |
| Cliente de API | `api/horasApi.ts` | no |

Los protegidos son `Dashboard.tsx`, `ScriptDesigner.tsx`, `jtl_parser.py`, `virtual_user.py`,
`report_generator.py`, `export_html.py`, `export_pdf.py` y `services/engine/`. **Ninguno
entra.** Y no hay cambio de esquema: `create_all` no tiene nada que crear.

**Ninguna condición de parada.**

## 4. Un detalle de permisos que conviene dejar escrito

`GET /users` es **solo admin** (`users.py:72`). Encaja con H-D13 sin endpoint nuevo:

- **El admin** llena su selector con `GET /users` y puede cambiarlo.
- **Los demás** no pueden listar usuarios, pero tampoco lo necesitan: su selector está fijo
  en sí mismos y el nombre lo sacan de `/auth/me`, que ya tienen.

Si en algún momento se quisiera que un analyst *viera* las horas de otro —hoy §8 dice que
todos ven los registros de todos— haría falta un listado de usuarios accesible a no-admin.
**No lo abro en H2**: §4.2.1 solo exige que el admin pueda *registrar* por otros, y abrir el
listado de usuarios es una decisión de producto que no me toca. Queda señalado.

## 5. Dos reglas nuevas que no estaban en H1

| Regla | Dónde se aplica |
|---|---|
| **H-D21 — sin fecha futura**: un registro posterior a hoy es 422 | en el backend. `date` no tiene restricción en la base y no se la voy a poner: "hoy" cambia cada día y un `CHECK` con `current_date` se evalúa al insertar pero no protege de nada útil |
| **H-D20 — proyecto cerrado**: ni alta ni edición, 409 con motivo | en el backend, junto a la comprobación que H1 ya hace al cambiar estimaciones |

## 6. Presupuesto

| | |
|---|---|
| Llamadas a la IA | **0** de 0 |
| Archivos tocados | **0** |
| Escrituras en base | **0** |

---

**Estado:** H2.1 cerrado. `time_entries` está completa, el calendario sembrado y el contrato
del detalle de proyecto no cambia. El cálculo de la jornada y de los días pendientes vivirá
en un solo sitio. Sigue H2.2 — backend del registro.
