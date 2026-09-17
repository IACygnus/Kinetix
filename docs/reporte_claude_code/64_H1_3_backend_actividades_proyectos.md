1a2036c · 2026-09-17

# ETAPA H1.3 — Backend de Actividades y Proyectos

**0 llamadas a la IA.** Los datos de prueba son propios del módulo y se borran al terminar
(regla del reporte 38: estos endpoints persisten).

Referencia: `docs/ESPECIFICACION-horas.md` v1.0 §1.2, §3 y §8.

---

## 1. Los endpoints

Todo bajo **`/time`** (H-D9), registrado en `api.py` junto al resto.

### `/time/activities`

| Verbo | Ruta | Quién | Qué |
|---|---|---|---|
| GET | `/time/activities` | todos | el catálogo, con `projects_count` y `has_entries` de cada una |
| POST | `/time/activities` | todos | crear. **409** si el nombre normalizado ya existe |
| PUT | `/time/activities/{id}` | todos | renombrar y/o activar-desactivar |
| DELETE | `/time/activities/{id}` | **solo admin** | borrar, solo si no se usa |

`GET` acepta `?solo_activas=true` para el selector de los proyectos.

**El borrado distingue los dos estorbos**, y eso importa porque el mensaje es distinto:

- **con horas registradas** → 409 y *"Desactívala: dejará de ofrecerse en los proyectos
  nuevos y lo ya registrado se conserva"*. Es definitivo (H-D4).
- **solo en proyectos, sin horas** → 409 y *"Quítala de ellos o desactívala"*. Tiene arreglo.

### `/time/projects`

| Verbo | Ruta | Quién | Qué |
|---|---|---|---|
| GET | `/time/projects` | todos | listado con filtros `client_id`, `estado`, `texto` |
| POST | `/time/projects` | todos | crear con su estimación inicial |
| GET | `/time/projects/{id}` | todos | detalle con sus actividades |
| PUT | `/time/projects/{id}` | todos | renombrar / descripción |
| POST | `/time/projects/{id}/cerrar` | **solo admin** | cerrar (§8) |
| POST | `/time/projects/{id}/reabrir` | **solo admin** | reabrir |
| PUT | `/time/projects/{id}/actividades` | todos | añadir actividad o cambiar su estimación |
| DELETE | `/time/projects/{id}/actividades/{aid}` | todos | quitarla, si no tiene horas (H-D12) |
| GET | `/time/projects/{id}/historial` | todos | el historial de estimaciones (H-D11) |

### El contrato que no va a cambiar

El detalle devuelve **ya** por actividad `estimated_hours`, `consumed_hours`,
`remaining_hours` y `over_estimate`. Hoy lo consumido es 0 porque `time_entries` está vacía,
pero **la consulta ya está escrita** (`_consumido`, un `GROUP BY` sobre `time_entries`). H2 y
H3 se encontrarán el contrato hecho y no tendrán que cambiarlo.

## 2. Decisiones técnicas que declaro

| Decisión | Por qué |
|---|---|
| **Las actividades del proyecto van por su propio endpoint**, no dentro del `PUT` del proyecto | cada cambio de estimación tiene que escribir su historial (H-D11). Mezclarlo con el renombrado invitaría a olvidarlo |
| **Si la estimación no cambia, no se escribe historial** | una fila que dice "de 10 a 10" es ruido, no rastro. El historial se lee para entender qué pasó |
| **Hasta el alta y la baja dejan rastro** (`change_type` ∈ alta/cambio/baja) | así el historial se lee entero sin adivinar por qué una actividad apareció o desapareció |
| **El listado usa consultas agregadas**, no una por fila | el catálogo y el listado los pinta la pantalla enteros; un N+1 ahí se nota enseguida |
| **`_nombre_libre` compara normalizado y por cliente** | §3. Dos clientes pueden tener un proyecto con el mismo nombre; el mismo cliente, no |
| **Un proyecto cerrado rechaza cambios de actividades con 409** | §3 dice que no admite registros nuevos; cambiarle la estimación a un proyecto cerrado sería la misma incoherencia |

## 3. Validación por HTTP — 24 comprobaciones, todas pasan

`h13_backend.sh`, contra el backend real, creando y borrando sus propios datos.

| Bloque | Resultado |
|---|---|
| **1. Catálogo** — las cinco actividades sembradas, todas activas | PASA (3) |
| **2. Crear** — nueva 201 · duplicado `"  PRUEBAS H1.3  "` **409** · nombre vacío 400 | PASA (3) |
| **3. Editar** — renombrar, desactivar y volver a activar | PASA (3) |
| **4. Crear proyecto** — 201 con dos actividades, total estimado `50.50` | PASA |
| **5. Errores esperados** — nombre duplicado normalizado 409 · estimación 0 **422** · `0.3` **422** · sin actividades **422** · borrar actividad en uso **409** | PASA (5) |
| **6. Historial (H-D11)** — ampliar 40 → 60 y leer las **3 filas**: dos altas y un cambio, con autor | PASA (4) |
| **7. Quitar actividad sin horas (H-D12)** — 200 y queda una | PASA (2) |
| **8. Cerrar (§8)** — admin cierra 200 · cerrado rechaza cambios **409** · admin reabre 200 | PASA (3) |

El historial, literal:

```
- cambio  Planeación                      : 40.00 -> 60.00  por Administrador SQA
- alta    Diseño y generación de script   : None  -> 10.50  por Administrador SQA
- alta    Planeación                      : None  -> 40.00  por Administrador SQA
```

> **Una comprobación quedó fuera de la corrida de curl** y lo dejo escrito: el **403 de un
> analyst al cerrar un proyecto**. Probarlo por HTTP exige la contraseña de otra persona, y
> no la tengo ni la voy a pedir. Se cubrió en el pytest, que además es mejor sitio: prueba
> el guardia real (`require_role(["admin"])`) sin depender de ninguna credencial.

## 4. `pytest` — 29 tests nuevos

`backend/tests/test_time_tracking_reglas.py`, en el estilo del repo (unitarios sobre
funciones y dobles, sin infraestructura HTTP).

| Qué cubre | Tests |
|---|---|
| **§8 — cerrar es solo de admin**: analyst 403, viewer 403, admin pasa | 3 |
| **H-D3 — normalización**: tildes, mayúsculas, espacios de más e interiores, vacío | 5 |
| **H-D8 — pasos de 0,25**: 6 múltiplos aceptados, 5 rechazados, cero y negativos, mensaje con el campo | 14 |
| **§3 — reglas de `ProjectCreate`**: sin actividades, actividad repetida, estimación no-paso, estimación cero, proyecto válido, y que la estimación sea `Decimal` y no `float` | 7 |

Uno de ellos fija a propósito un comportamiento que podría sorprender:

```python
def test_normalizar_la_enie_no_es_una_tilde():
    assert normalizar("Diseño y generación de script") == "diseno y generacion de script"
```

La eñe es una letra, no una vocal acentuada, pero la normalización Unicode la descompone
igual. **El catálogo ya tiene filas guardadas con esa forma**, así que el test está para que
nadie lo "arregle" sin darse cuenta de que rompería la comparación de lo ya sembrado.

**Suite completa: 521 pasan, 1 falla** — la misma anterior al plan
(`analysis_pipeline.time`), documentada en el checklist. Eran 492 antes de esta etapa.

## 5. Archivos

| Archivo | Líneas | Protegido |
|---|---|---|
| `backend/app/schemas/time_tracking.py` | **nuevo**, 148 | no |
| `backend/app/api/v1/endpoints/time_activities.py` | **nuevo**, 184 | no |
| `backend/app/api/v1/endpoints/time_projects.py` | **nuevo**, 352 | no |
| `backend/tests/test_time_tracking_reglas.py` | **nuevo**, 160 | no |
| `backend/app/api/v1/api.py` | +10 | no |

Copia de seguridad `api.py.bak_h1_H1.3_20260917`. **Ningún archivo protegido.**

---

**Estado:** H1.3 cerrado. Los dos endpoints funcionan contra el backend real, las reglas de
negocio están probadas y el contrato del detalle ya es el que necesitarán H2 y H3. Siguen
H1.4 y H1.5 — las dos pantallas.
