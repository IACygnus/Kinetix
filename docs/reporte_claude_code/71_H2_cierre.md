cdb5e1c · 2026-09-17

# ETAPA H2 — Cierre: registro de horas

**0 llamadas a la IA en toda la etapa.** El módulo de horas no usa IA en ningún punto.

Referencia: `docs/ESPECIFICACION-horas.md` v1.0 §1.1, §4 y §8.

---

## 1. Qué pedía la etapa y qué quedó

| Decisión | Qué pedía | Estado |
|---|---|---|
| **H-D13** | Selector de usuario; registrar por otro solo admin | Hecho, y probado en pytest |
| **H-D14** | Vista semanal con navegación, «Hoy» y salto a fecha | Hecho |
| **H-D15** | Alta encadenada; facturable hereda del último registro | Hecho |
| **H-D16** | Exceso: avisa con la cifra, **deja guardar** y marca | Hecho, en registro y en proyecto |
| **H-D17** | Las extra consumen estimación y salen aparte; su día no es incompleto | Hecho |
| **H-D18** | Panel de pendientes con enlace que enfoca el día | Hecho |
| **H-D19** | Editar los propios; admin todos; borrar solo admin | Hecho |
| **H-D20** | Proyecto cerrado: ni alta ni edición, 409 con motivo | Hecho |
| **H-D21** | Sin fecha futura, 422 con motivo | Hecho |
| **H-D22** | El detalle de proyecto no cambia de contrato | Cumplido: **ni una línea** |

## 2. Los sub-pasos

| Sub-paso | Reporte | Commit |
|---|---|---|
| H2.1 Diagnóstico (read-only) | 68 | `4464ca3` |
| H2.2 Backend | 69 | `b49d617` |
| H2.3 y H2.4 Pantalla y validación | 70 | `cdb5e1c` |
| H2.5 Cierre | 71 (este), 72 | — |

## 3. Lo que se construyó

**Backend** — 4 archivos nuevos:

```
services/horas/calendario.py       las tres reglas, en un solo sitio
services/horas/__init__.py
api/v1/endpoints/time_entries.py   los siete endpoints
tests/test_horas_calendario.py     29 tests
```

**Frontend** — 1 archivo nuevo, `pages/horas/RegistroPage.tsx`, más los métodos del registro
en `horasApi.ts`.

Y cuatro archivos existentes con cambios pequeños: `schemas/time_tracking.py` (+118),
`api.py` (+4), `App.tsx` (+2), `Sidebar.tsx` (+6).

**Ningún archivo protegido. Ningún cambio de esquema.** `time_entries` se creó entera en
H1.2 y esa decisión se acaba de cobrar: H2 no ha tenido que alterar nada.

## 4. Verificación — 91 comprobaciones propias, todas pasan

| Prueba | Qué mira | Resultado |
|---|---|---|
| `h22_backend.py` | 40 por HTTP: alta, exceso, errores, proyecto cerrado, extras, semana, festivo, pendientes, editar, borrar, registrar por otro | TODO PASA |
| `test_horas_calendario.py` | 29 tests: jornada, las tres reglas una a una, semana completa, permisos y schema | 29 pasan |
| `h24_pantalla.py` | 22 de punta a punta en la pantalla real | TODO PASA |

### El módulo de análisis no se movió

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` — diez pasos, **cuatro salidas** | **LAS CUATRO SALIDAS PASAN** |
| `h13_backend.sh` y `h15_pantallas.py` (H1) | TODO PASA |
| `pytest tests/` | **550 pasan**, 1 falla — la anterior al plan |
| `npx tsc --noEmit` | sin errores |

## 5. Las decisiones técnicas de la etapa

| Decisión | Justificación |
|---|---|
| **El calendario en un solo módulo** | dos endpoints lo necesitan; escrito dos veces acabaría discrepando en algún borde sin que nadie lo note |
| **Las tres reglas, en orden**: no laborable → extras → jornada | escrito al revés, un festivo con horas extra daría resultados distintos según por dónde se entrara |
| **`dias_pendientes` recibe un tope de fecha** | un día que no ha llegado no es una deuda; sin el tope, abrir el panel un lunes listaría la semana entera |
| **El exceso solo marca, nunca impide** | §4.2.4 lo dice así, y el botón de guardar no se deshabilita por exceso |
| **La marca de exceso se calcula en el backend** | si la sumara la pantalla, dos vistas del mismo dato podrían discrepar |
| **Sin `CHECK` de fecha futura en la base** | «hoy» cambia cada día; va en el schema, con mensaje legible |
| **Al editar se comprueban los dos proyectos** | si no, se podrían meter horas en un proyecto cerrado moviéndolas desde uno abierto |
| **Ni `toISOString()` ni `new Date(iso)` en el frontend** | los dos pasan por UTC y en Colombia devolverían el día equivocado después de las siete de la tarde |
| **Una ausencia propia pesa más que un festivo** si coinciden | nombrar la ausencia es más informativo para quien la pidió |

## 6. Lo que no se pudo probar por HTTP, y dónde quedó cubierto

Igual que en H1, dos reglas de permisos exigían la contraseña de otra persona:

- **registrar por otro siendo analyst → 403** (H-D13);
- **borrar siendo analyst → 403** (§8).

Se prueban en `pytest` contra las funciones reales (`_usuario_del_registro`, `require_role`,
`_puede_editar`), que además no dependen de ninguna credencial. Los **bordes del calendario**
—festivo en viernes, día con solo extras, día futuro— también viven ahí: por HTTP dependerían
de qué día se corra la prueba, y así el resultado es el mismo siempre.

## 7. Una línea de despliegue, y sigo

Nada nuevo: no hay tablas ni columnas que crear, y el backend recoge los endpoints al
recargar. Sigue valiendo lo del reporte 63 — en el servidor, **ningún SQL**.

## 8. Lo que queda

- **H3** — consulta de proyectos: quién ha registrado y cuánto, con el desglose por días
  (§5). El endpoint `/time/entries` con filtros ya es la mitad del camino.
- **H4** — importación del archivo, que reusará `normalizar()` y `external_id`.
- **Reportes** — cuando llegue su etapa habrá que decidir si se reutiliza
  `report_generator.py`, que **es archivo protegido**. Señalado desde el reporte 62.

---

**Estado: Etapa H2 implementada, pendiente validación de Fredy.**
