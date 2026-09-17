4464ca3 · 2026-09-17

# ETAPA H2.2 — Backend del registro de horas

**0 llamadas a la IA.** La prueba crea un proyecto y sus registros, y los borra al terminar,
incluso si falla a mitad.

Referencia: `docs/ESPECIFICACION-horas.md` v1.0 §1.1, §4 y §8.

---

## 1. Los endpoints

Todo bajo **`/time`**.

| Verbo | Ruta | Quién | Qué |
|---|---|---|---|
| GET | `/time/entries?user_id=&desde=&hasta=` | todos | los registros del rango, con cliente, proyecto y actividad resueltos y la marca de exceso |
| GET | `/time/week?user_id=&fecha=` | todos | la semana de esa fecha, **ya resuelta** |
| GET | `/time/pending-days?user_id=&desde=&hasta=` | todos | los días por completar (H-D18) |
| GET | `/time/projects/{id}/disponibilidad` | todos | estimado, consumido y restante por actividad |
| POST | `/time/entries` | todos (por otro, **solo admin**) | registrar |
| PUT | `/time/entries/{id}` | los propios; el admin, todos | editar |
| DELETE | `/time/entries/{id}` | **solo admin** | borrar |

`/time/week` devuelve por día `expected_hours`, `ordinary_hours`, `overtime_hours`,
`is_holiday`, `is_absence`, `incomplete` y `missing_hours`, más sus registros. **La pantalla
no calcula nada**: solo pinta.

## 2. El calendario, en un solo sitio

`backend/app/services/horas/calendario.py`. Las tres reglas viven juntas y en orden, que es
lo que las hace legibles:

```python
@property
def incompleto(self) -> bool:
    if self.no_laborable:   # festivo, ausencia o fin de semana
        return False
    if self.extra > 0:      # H-D17
        return False
    return self.ordinarias < self.esperadas
```

**El orden importa**: primero se descarta lo que no se reclama, después las extras, y solo
entonces se compara contra la jornada. Escrito al revés, un festivo con horas extra habría
dado resultados distintos según por dónde se entrara.

`dias_pendientes` recibe un tope: **nunca lista días futuros**. Sin él, abrir el panel un
lunes listaría el resto de la semana como si fuera una deuda.

### Decisiones que declaro

| Decisión | Por qué |
|---|---|
| **Festivos y ausencias se resuelven en la misma consulta**, y una ausencia propia pesa más que un festivo si coinciden | H1 los puso en la misma tabla precisamente porque aquí se usan igual. Si coinciden, nombrar la ausencia es más informativo |
| **`_excedidas` solo marca, nunca impide** | §4.2.4 dice que se avisa y **se permite guardar**. La función devuelve un conjunto de pares marcados, no lanza |
| **La marca de exceso se calcula en el backend** | si la sumara la pantalla, dos vistas del mismo dato podrían discrepar |
| **Dos consultas agregadas para todo el lote**, no una por registro | una semana son decenas de filas; un N+1 ahí se nota |
| **Sin `CHECK` de fecha futura en la base** | "hoy" cambia cada día: un `CHECK` con `current_date` se evalúa al insertar y no protege de nada útil. Va en el schema, con mensaje legible |
| **Al editar se comprueban los dos proyectos**, el de origen y el de destino si el registro se mueve | si no, se podrían meter horas en un proyecto cerrado moviéndolas desde uno abierto |

## 3. Validación por HTTP — 40 comprobaciones, todas pasan

`h22_backend.py`, contra el backend real.

| Bloque | Resultado |
|---|---|
| **1. Alta correcta** — 201, `created_by` guarda quién registró, resuelve *Avianca · Proyecto H2.2 · Diseño y generación de script* | PASA (4) |
| **2. Exceso (H-D16)** — 12 h sobre una estimación de 10 **se guarda** (201), viene marcada, y los restantes quedan en **−2,00** | PASA (5) |
| **3. El detalle del proyecto (H-D22)** — consumido 12,00, marca el exceso, total 20,50 | PASA (3) |
| **4. Errores** — paso 0,3 → 422 · fecha futura → 422 · horas cero → 422 · actividad ajena al proyecto → 400 | PASA (4) |
| **5. Proyecto cerrado (H-D20)** — 409 **con el motivo** | PASA (2) |
| **6. Horas extra (H-D17)** — las extra **consumen** la estimación: 20,50 → 23,50 | PASA (2) |
| **7. La semana (H-D14)** — empieza en lunes, 7 días, el miércoles con 3 h extra **separadas** y **no incompleto**, el jueves sin registros falta 8,50, el sábado no se reclama | PASA (9) |
| **8. Festivo (§4.2.7)** — sale como festivo, **no se reclama** y trae su nombre | PASA (3) |
| **9. Pendientes (H-D18)** — solo el jueves; ni el festivo, ni el día con extras, ni el sábado. Trae el lunes de su semana para el enlace | PASA (6) |
| **10. Editar y borrar** — editar 200, paso inválido al editar 422, el admin borra 204 | PASA (3) |
| **11. Registrar por otro (H-D13)** — el admin registra por `adrian`; las horas son de él y `created_by` es el admin | PASA (2) |

Totales de la semana de prueba: **esperadas 42,00 · ordinarias 20,50 · extra 3,00**.

## 4. `pytest` — 29 tests nuevos

`backend/tests/test_horas_calendario.py`. Cubre lo que la corrida por HTTP **no puede probar
bien**:

- **Los 403 de H-D13 y §8**: registrar por otro siendo analyst y borrar siendo analyst.
  Probarlos por HTTP exigiría la contraseña de otra persona, y no la tengo ni la voy a pedir.
  Se prueban las funciones reales (`_usuario_del_registro`, `require_role`, `_puede_editar`).
- **Los bordes del calendario**: por HTTP dependerían de qué día se corra la prueba. Aquí se
  fija un lunes concreto y el resultado no cambia nunca.

| Qué cubre | Tests |
|---|---|
| La jornada y el inicio de semana | 4 |
| Las tres reglas de §4.2.6 y §4.2.7, una a una | 7 |
| Una semana completa con festivo, extras y día flojo; pendientes sin futuro; pendientes que saltan festivos y fines de semana | 3 |
| Permisos: registrar por otro, borrar, editar los propios y los de todos | 5 |
| El schema: hoy sí, hace un año sí, mañana no; pasos de 0,25; facturable obligatorio | 10 |

**Suite completa: 550 pasan, 1 falla** — la misma anterior al plan. Eran 521 antes de H2.

## 5. Archivos

| Archivo | Líneas | Protegido |
|---|---|---|
| `backend/app/services/horas/calendario.py` | **nuevo**, 145 | no |
| `backend/app/services/horas/__init__.py` | **nuevo**, 1 | no |
| `backend/app/api/v1/endpoints/time_entries.py` | **nuevo**, 411 | no |
| `backend/tests/test_horas_calendario.py` | **nuevo**, 218 | no |
| `backend/app/schemas/time_tracking.py` | +118 | no |
| `backend/app/api/v1/api.py` | +4 | no |

**Ningún archivo protegido, ningún cambio de esquema.** Copia de seguridad
`api.py.bak_h2_H2.2_20260917`.

---

**Estado:** H2.2 cerrado. Los siete endpoints funcionan contra el backend real, el calendario
está en un solo sitio y las reglas que curl no podía probar están cubiertas en pytest. Sigue
H2.3 — la pantalla.
