a2c3ee3 · 2026-09-17

# ETAPA H2b — para Fredy

---

## Qué se hizo

La pantalla de registro estaba desordenada. Se rehízo entera: **ahora es un
calendario del mes**, y la vista por semana se retiró — no conviven, porque dos
formas de hacer lo mismo confunden.

**1. El calendario.** Una casilla por día. Cada una dice su estado de un vistazo
y **también con palabras**, no solo con color: verde si la jornada está completa,
ámbar con «faltan 6,5 h» o «sin registrar» si no, el nombre del festivo cuando lo
hay, apagado el fin de semana. Arriba, el resumen del mes —jornada, registradas,
extra y días pendientes—, la navegación por mes y el botón **Hoy**. Debajo, la
leyenda de colores.

**2. Los días que aún no han llegado ya no salen en rojo.** Antes, el resto del
mes habría aparecido como deuda. Ahora solo se reclama lo que ya pasó.

**3. El detalle del día.** Debajo del calendario, el día que usted pulse: cliente,
proyecto, actividad, horas, si se cobra, observaciones, y editar y borrar. Con el
total del día frente a su jornada y **las horas extra aparte**.

**4. El popup de registro.** Se abre al pulsar un día o el botón de registrar.
Trae una franja con la jornada de ese día y lo que falta; **la fecha se puede
corregir sin cerrarlo**; cliente → proyecto → actividad encadenados, y al elegir
la actividad se leen las horas que le quedan. **Facturable y No facturable son
dos botones**: hay que elegir, ya no se hereda del registro anterior. Y hay
**Guardar y añadir otra**, porque un día suele tener varios renglones.

**5. Se dice «desfase», no «exceso».** En toda la pantalla. Un registro sale
marcado como «desfase» y un proyecto como **«Desfasado +4,5 h»**. La palabra
describe el proyecto, que va por encima de lo estimado; no culpa a quien registró
las horas.

**6. Proyectos avisa antes de que sea tarde.** Además del desfase, hay un aviso
intermedio: por debajo del 90 % «en rango», del 90 al 100 % **«Por agotarse»**, y
por encima **«Desfasado»** con las horas de más. Se ve en el listado, en la
cabecera del proyecto y **en cada actividad**, para saber cuál es la que tira.

---

## Evidencia

- **138 comprobaciones automáticas** propias de la etapa, todas pasan. **0
  llamadas a la IA** en todo el módulo.
- Se probó en la pantalla real: registrar 6 horas donde quedan 4 **avisa con la
  cifra y deja guardar**; el calendario se actualiza solo al guardar; «Guardar y
  añadir otra» deja el popup abierto con el proyecto puesto.
- **La palabra «exceso» no aparece en ninguna pantalla del módulo** — se
  comprueba leyendo el texto de Registro, Proyectos y Actividades, y también con
  el popup de aviso abierto.
- **Cero errores de JavaScript.** Todos los botones del módulo llegan a 44 px y
  todos los campos tienen su rótulo.
- **El resto de Kinetix no se movió**: la suite de la Etapa 2 pasa en las cuatro
  salidas, H1 y el backend de H2 siguen verdes, `tsc` limpio.
- No se tocó ningún archivo protegido, ningún compose y **ninguna columna de la
  base**: los cuatro datos del desfase se calculan.

---

## Guion para validar

Recargue con **Ctrl + Shift + R**. No hace falta rebuild.

**1. El calendario.** Horas → **Registro**. Verá el mes en curso. Compruebe que
los días pasados sin registrar están en ámbar, que **los que aún no han llegado
no**, y que el fin de semana está apagado. Mire la leyenda de abajo.

**2. Navegar.** Con ‹ y › cambie de mes; con **Hoy** vuelva. Al volver, el día de
hoy queda seleccionado.

**3. Registrar.** Pulse un día de la semana pasada y luego **Registrar**. Fíjese
en la franja de arriba: dice la jornada de ese día y lo que falta. Elija cliente,
proyecto y actividad —verá las horas que le quedan—, ponga las horas y **elija
Facturable o No facturable**: hasta que no lo elija, Guardar está apagado. Guarde
y vea la casilla cambiar de color sola.

**4. Guardar y añadir otra.** Repita y pulse **Guardar y añadir otra**: el popup
se queda abierto con el día y el proyecto puestos, listo para el siguiente
renglón.

**5. El desfase.** Elija una actividad con pocas horas estimadas y ponga más de
las que quedan. Sale el aviso con la cifra; **guarde igual**. El registro queda
marcado como «desfase» y la casilla del calendario también lo avisa.

**6. La alerta en Proyectos.** Horas → **Proyectos**. La columna «Consumo» enseña
el porcentaje y, cuando toca, «Por agotarse» o «Desfasado +N h». Entre a ese
proyecto: el aviso está junto al nombre y **también en la actividad concreta** que
lo provoca.

**7. Corregir un día equivocado.** En el detalle de un día, pulse el lápiz de un
registro: se abre el mismo popup y ahí puede cambiar **la fecha**, el proyecto, la
actividad y las horas. Antes solo dejaba tocar horas y observaciones.

**8. Que el análisis sigue igual.** Abra un informe desde Historial Reporte y
expórtelo en PDF.

---

## Dos cosas que conviene que sepa

**El panel de «días pendientes» ya no está, y no se perdió nada.** En un
calendario, los días pendientes **son** las casillas ámbar, y pulsarlas es el
enlace que abría ese día. El contador sigue arriba, en el resumen del mes.

**Un botón pequeño que no toqué.** El tirador que pliega la barra lateral mide 24
px, por debajo de los 44 que pide el criterio. No es del módulo de horas: es de la
barra que comparten todas las pantallas de Kinetix, y cambiarlo se salía de esta
etapa. Queda anotado por si quiere que se arregle.

---

**Estado: Etapa H2b implementada, pendiente validación de Fredy.**
