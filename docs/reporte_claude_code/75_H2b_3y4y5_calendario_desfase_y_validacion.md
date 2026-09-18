b65f4b4 · 2026-09-17

# ETAPA H2b.3, H2b.4 y H2b.5 — El calendario, la alerta de desfase y la validación

**0 llamadas a la IA.**

---

## 1. La pantalla que pidió Fredy

H2 funcionaba y estaba desordenada. La vista semanal apilaba siete tarjetas, cada
una con su tabla y su botón, y para ver un mes había que pasar cuatro veces de
semana. El diseño aprobado la sustituye por **un calendario mensual**, y la
especificación v1.1 §4.1 lo dice sin rodeos: *«Es la única vista: la vista por
semana se retira, no convive con ella — dos formas de hacer lo mismo confunden.»*

Se retiró entera. No quedó ni el botón de semana anterior ni la tarjeta por día:
la comprobación 1 de la validación busca los dos y exige que no estén.

| Archivo | Qué es | Líneas |
|---|---|---|
| `frontend/src/pages/horas/RegistroPage.tsx` | **reescrita** — calendario, detalle del día y estado | 335 (antes 546) |
| `frontend/src/components/horas/CalendarioMes.tsx` | **nuevo** — la rejilla del mes y la leyenda | 146 |
| `frontend/src/components/horas/PopupRegistro.tsx` | **nuevo** — el popup de registro y de edición | 317 |
| `frontend/src/components/horas/AvisoDesfase.tsx` | **nuevo** — el aviso de §5.1, compartido | 50 |
| `frontend/src/api/horasApi.ts` | el mes, el desfase y cuatro ayudas de fecha | +71 −6 |
| `frontend/src/pages/horas/ProyectosPage.tsx` | la alerta en el listado y en el detalle | +29 −4 |
| `backend/app/api/v1/endpoints/time_projects.py` | el desfase del proyecto en su detalle | +7 |

La pantalla queda en **335 líneas frente a las 546 de H2**, y eso que hace más:
lo que antes era una sola pieza ahora son tres, cada una con un trabajo.
`RegistroPage` decide qué se carga, `CalendarioMes` pinta y `PopupRegistro`
registra. Copia de seguridad de la anterior en `RegistroPage.tsx.bak_h2b_*`.

---

## 2. El calendario (H-D23, H-D24)

Una casilla por día. Cada una dice su estado **con color y con palabras**: el
color solo no basta —hay quien no lo distingue— así que la casilla incompleta
pone «faltan 6,5 h» o «sin registrar», la del festivo pone su nombre, y la que
toca una actividad desfasada pone «desfase».

| Estado | Cómo se ve |
|---|---|
| Jornada completa | verde, con las horas registradas |
| Incompleto o sin registrar | ámbar, con las horas que faltan |
| Festivo / ausencia | índigo / morado, **con su nombre** |
| Fin de semana | apagado |
| Por venir | neutro: un día que no ha llegado no es una deuda |
| Elegido | anillo naranja |

Encima, el resumen del mes —jornada, registradas, extra y días pendientes—; a la
derecha, navegación por mes y el botón **Hoy**; debajo, la leyenda.

**El panel de días pendientes de H2 desaparece, y no se pierde nada**: en un
calendario, los días pendientes son las casillas ámbar y el «enlace que abre ese
día» de §4.2.6 es pulsarlas. El contador sigue en el resumen.

Ni un `toISOString()` ni un `new Date(iso)` en toda la pantalla: en Colombia,
después de las siete de la tarde, los dos devuelven el día siguiente. Las fechas
se parten por guiones y se arman con los constructores locales, como en H2.

---

## 3. El detalle del día (H-D25)

Debajo del calendario, el día elegido: cliente y proyecto, actividad, horas, si
se cobra, observaciones, y editar y borrar. Arriba, el total del día frente a su
jornada, **con las horas extra aparte**.

Los registros con todos sus campos vienen de `/time/week`, que es el único sitio
donde están. **El endpoint de H2 se conserva entero**: lo que se retiró es la
vista, no el backend, y reusarlo evitó un endpoint nuevo para un solo día.

---

## 4. El popup (H-D26)

Lo que §4.1 pide, campo por campo:

- **la franja del día**, con su jornada y lo que falta: *«martes, 8 de septiembre
  · jornada de 8,5 h · registradas 0 h · faltan 8,5 h»*;
- **la fecha, editable dentro del popup**, por si uno se equivocó de día;
- cliente → proyecto → actividad encadenados, y al elegir la actividad se lee
  *«De 100 h estimadas se han registrado 0 h: quedan 100 h»*;
- **Facturable / No facturable como dos botones de opción**, sin valor por
  defecto;
- la casilla de hora extra, las observaciones;
- y **Guardar**, **Guardar y añadir otra** y Cancelar.

**Dos decisiones, declaradas:**

1. **Registrar y editar son el mismo popup.** Son los mismos campos; mantener dos
   formularios habría dejado uno de los dos atrás en el primer cambio. La edición
   en línea de H2 —que solo dejaba tocar horas y observaciones— se retira: ahora
   se puede corregir también el día, el proyecto y la actividad, que es donde
   están los errores de verdad.
2. **«Facturable» ya no se hereda del registro anterior.** H2 lo heredaba
   (H-D15); v1.1 dice *«hay que elegir, no dejarlo como venga»*. Sin elegirlo, el
   botón de guardar está apagado. Se gana un clic de trabajo y se pierde una
   fuente de facturación equivocada por inercia.

«Guardar y añadir otra» deja el día, el cliente y el proyecto puestos —un día
suele tener varios renglones del mismo sitio— y vacía la actividad y las horas.

---

## 5. La alerta de desfase en Proyectos (H-D28)

Tres sitios, un solo componente, y el estado **ya resuelto por el backend**: la
pantalla elige el color, no el umbral.

- **En el listado**, una columna «Consumo» con el porcentaje y el aviso. En rango
  no pinta nada: un chip gris en cada fila es ruido, y el aviso deja de avisar.
- **En la cabecera del proyecto**, siempre, junto a las horas: *«212,5 % · 8,5 de
  4 h · Desfasado +4,5 h»*.
- **En cada actividad**, para ver **cuál** tira del proyecto, no solo que el
  proyecto va mal.

Un defecto que salió aquí: `_detalle()` calculaba el desfase de cada actividad
pero no el del proyecto entero, así que el detalle habría dicho «En rango» de un
proyecto que el listado acababa de marcar como desfasado. Corregido en el mismo
sitio donde ya estaba el resto del cálculo.

---

## 6. Validación — `h2b5_pantalla.py`, todo pasa

Playwright contra la pantalla real, con datos propios que se borran al terminar
aunque falle a mitad (regla del reporte 38). Tres proyectos, uno por estado, y un
festivo colocado a propósito.

```
--- 1. El calendario del mes (H-D23) ---
PASA  | una casilla por día del mes: 30 de 30
PASA  | hay leyenda de colores
PASA  | la vista por semana se retiró: no queda ni un resto de ella

--- 2. El estado de cada día (H-D24) ---
PASA  | el festivo sale como festivo, y con su nombre
PASA  | el martes, sin registrar, es incompleto
PASA  | y lo dice con palabras, no solo con color
PASA  | ningún día futuro se pinta como incompleto (0)

--- 3. Navegación por mes ---
PASA  | «Septiembre de 2026» → «Agosto de 2026»
PASA  | el botón Hoy vuelve al mes en curso y deja hoy seleccionado

--- 4. El detalle del día elegido (H-D25) ---
PASA  | el detalle sigue al día que se pulsa, con cliente y proyecto

--- 5. El popup de registro (H-D26) ---
    franja: «martes, 8 de septiembre · jornada de 8,5 h · registradas 0 h · faltan 8,5 h»
PASA  | la fecha se puede corregir dentro del popup
PASA  | Facturable y No facturable son dos opciones explícitas
PASA  | con las horas puestas pero sin decidir si se cobra, sigue sin poder guardarse

--- 6. Guardar y añadir otra (§4.1) ---
PASA  | el popup sigue abierto para el siguiente renglón
PASA  | el calendario se actualiza solo: el martes pasa a completo

--- 7. El desfase (H-D27, §4.2.4) ---
    «Vas a registrar 6 h y solo quedan 4 h en esta actividad. Se puede guardar
     igual: el registro quedará marcado como desfase.»
PASA  | SE PUEDE guardar igual: ni se bloquea ni se pierde el dato
PASA  | el registro y la casilla del calendario quedan marcados

--- 8. La alerta de desfase en Proyectos (H-D28, §5.1) ---
PASA  | 'largo': en_rango · 'al limite': por_agotarse «Por agotarse»
PASA  | 'corto': desfasado «Desfasado +2 h»
PASA  | el detalle marca la actividad desfasada

--- 9. Se dice «desfase», no «exceso» (H-D27) ---
PASA  | /horas/registro, /horas/proyectos, /horas/actividades: sin la palabra
PASA  | el popup con aviso: tampoco

--- 10. Los tamaños y los rótulos (H-D29) ---
PASA  | todos los botones del módulo llegan a 44 px
PASA  | todos los campos del popup tienen rótulo
PASA  | sin errores de JavaScript
```

**Un hallazgo del punto 10, que no se tocó:** el único botón de menos de 44 px en
toda la página es el tirador que pliega la barra lateral (24 px), que es de
`components/layout/Sidebar.tsx` y lo comparten todas las pantallas de Kinetix.
Arreglarlo se sale de esta etapa; queda anotado.

---

## 7. Regresión

| Qué | Resultado |
|---|---|
| `pytest tests/` | **582 pasan, 1 falla** (ver abajo) |
| `tsc --noEmit` | limpio |
| `verificar_etapa2.py` — las cuatro salidas del informe | todo pasa |
| `h15_pantallas.py` — las dos pantallas de H1 | todo pasa |
| `h2b2_backend.py` — el mes y el desfase | todo pasa |
| `h22_backend.py` — el backend del registro de H2 | todo pasa |
| `h24_pantalla.py` — la **pantalla semanal** de H2 | ya no aplica |

**El fallo de `pytest`** es `test_analysis_pipeline.py::test_pipeline_parsea_jtl_…`
(`AttributeError: module 'app.services.ai.analysis_pipeline' has no attribute
'time'`): **el mismo que ya venía de antes del plan**, anotado en el reporte 66 y
otra vez en el 71. No viene de esta etapa —falla igual con todos los cambios de
H2b.3 a H2b.5 guardados aparte— y es del módulo de análisis, que el de horas no
toca.

**`h24_pantalla.py` ya no aplica** a propósito: conducía la vista semanal, que es
justo lo que esta etapa retira. Lo sustituye `h2b5_pantalla.py`, que cubre lo
mismo sobre el calendario. Su limpieza de datos corrió igual al fallar, y la base
quedó sin restos (comprobado).

---

## 8. Lo que queda

La validación visual de Fredy, que es el único criterio de éxito.
