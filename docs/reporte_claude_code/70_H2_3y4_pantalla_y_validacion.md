b49d617 · 2026-09-17

# ETAPA H2.3 y H2.4 — La pantalla de registro y su validación

**0 llamadas a la IA.** La prueba crea un proyecto, un festivo y sus registros, y lo borra
todo al terminar, incluso si falla a mitad.

Referencia: `docs/ESPECIFICACION-horas.md` v1.0 §4.

---

## 1. La pantalla

`/horas/registro`, con entrada nueva **Registro** al principio de la sección «Horas».

| Zona | Qué hace |
|---|---|
| **Cabecera** | selector de usuario (H-D13), flechas de semana, «Hoy» y un campo de fecha para saltar |
| **Totales** | jornada esperada, registradas, horas extra y número de días pendientes |
| **Días pendientes** | los días por completar, cada uno un botón que abre su semana (H-D18) |
| **Siete tarjetas** | una por día, con su total frente a la jornada, las extras aparte y la marca de incompleto |
| **Alta** | cliente → proyecto → actividad → horas → facturable → extra → observaciones (H-D15) |
| **Edición en línea** | horas y observaciones; borrar solo el admin (H-D19) |

**La pantalla no calcula nada.** La jornada, los totales, el «incompleto» y la marca de
exceso vienen resueltos de `/time/week`, que a su vez los saca de
`services/horas/calendario.py`. Si la jornada cambiara en `work_calendar`, cambia en un sitio.

### Decisiones que declaro

| Decisión | Por qué |
|---|---|
| **`hoyISO()` no usa `toISOString()`** | eso convierte a UTC y en Colombia (UTC−5) a partir de las siete de la tarde devolvería **el día siguiente**. En un módulo que va de fechas, eso es un registro puesto en el día equivocado |
| **`fechaLarga()` tampoco pasa por `new Date(iso)`** | el constructor interpreta `"2026-09-14"` como UTC y pinta el día anterior. Se parte la cadena y se construye la fecha local |
| **El selector de usuario se deshabilita para los no-admin** | H-D13. Y solo el admin pide `GET /users`, que es admin-only: los demás ni lo intentan |
| **Facturable hereda del último registro de ese proyecto en la semana visible** | H-D15. Si no hay ninguno, queda en «No» — nunca se marca facturable por descuido |
| **El aviso de exceso no bloquea el botón** | §4.2.4 dice avisar y permitir. El botón solo se deshabilita por horas inválidas, nunca por exceso |
| **Los selectores se encadenan** (cliente → proyecto → actividad) | §4.1. Cada uno se deshabilita hasta que el anterior tiene valor, y el de actividad muestra las horas que quedan |

## 2. Validación de punta a punta — 22 comprobaciones, todas pasan

`h24_pantalla.py`, sobre la pantalla real, con un proyecto cuya actividad tiene **4 horas
estimadas** para poder forzar el exceso, y un festivo el viernes.

| Bloque | Resultado |
|---|---|
| **1. Tres días** — 8,5 + 8,5 + 4; el total de la semana es **21** y el miércoles, con 4 de 8,5, queda incompleto | PASA (5) |
| **2. Exceso (H-D16)** — al elegir la actividad se lee *«De 4 h estimadas se han registrado 0 h: quedan 4 h»*; con 6 h aparece el aviso, **se puede guardar**, el registro queda marcado y el detalle del proyecto lo marca (6,00 de 4,00) | PASA (5) |
| **3. Horas extra (H-D17)** — salen aparte («3 h extra») y ese día **deja de contar como incompleto** | PASA (2) |
| **4. Pendientes (H-D18)** — el panel está; **el festivo no aparece** y el día con extras tampoco | PASA (3) |
| **5. El festivo (§4.2.7)** — sale marcado con su nombre y no se reclama | PASA (2) |
| **6. El enlace** — abre la semana de ese día y **lo deja enfocado** | PASA (2) |
| **7. Editar y borrar** — el lunes pasa de 8,5 a 6 y **entonces sí queda incompleto**; el admin borra | PASA (3) |
| **8. Consola** — **cero errores de JavaScript** | PASA |

El aviso de exceso, literal:

> «Vas a registrar **6 h** y solo quedan **4 h** en esta actividad. Se puede guardar igual:
> el registro quedará marcado como exceso.»

> La comprobación 7 es la que más me gusta de esta tanda: al bajar el lunes de 8,5 a 6 el día
> **pasa a estar incompleto**, lo que prueba que el «incompleto» se recalcula de verdad
> contra la jornada y no es un valor guardado.

## 3. Regresión — nada se movió

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` — diez pasos, **las cuatro salidas** | **LAS CUATRO SALIDAS PASAN** |
| `h13_backend.sh` (H1, backend) | TODO PASA |
| `h15_pantallas.py` (H1, pantallas) | TODO PASA |
| `pytest tests/` | **550 pasan**, 1 falla — la anterior al plan |
| `npx tsc --noEmit` | sin errores |

Eran 521 antes de H2; los 29 nuevos son los del calendario y los permisos.

## 4. Archivos

| Archivo | Líneas | Protegido |
|---|---|---|
| `frontend/src/pages/horas/RegistroPage.tsx` | **nuevo**, 546 | no |
| `frontend/src/api/horasApi.ts` | +130 | no |
| `frontend/src/App.tsx` | +2 | no |
| `frontend/src/components/layout/Sidebar.tsx` | +6 | no |

**Ningún archivo protegido.** Copias de seguridad `*.bak_h2_H2.3_20260917`.

---

**Estado:** H2.3 y H2.4 cerradas. La pantalla funciona contra el backend real, las cifras van
en formato español y el módulo de análisis sigue intacto. Sigue H2.5 — cierre.
