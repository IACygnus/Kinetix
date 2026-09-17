181bd5e · 2026-09-17

# ETAPA H1 — para Fredy

---

## Qué se hizo

Arranca el **módulo de horas**. Esta primera etapa pone los cimientos y las dos pantallas
que hacen falta antes de poder registrar nada: **Proyectos** y **Actividades**.

**1. La base de datos del módulo.** Siete tablas nuevas, creadas solas al arrancar el
backend: **no hay que ejecutar ningún SQL**, ni aquí ni en el servidor. El módulo de
análisis no se tocó — se comprobó columna por columna que `test_executions`, `clients` y
`users` quedan idénticos.

**2. Lo que ya viene cargado.** Las cinco actividades iniciales (Planeación, Diseño y
generación de script, Ejecución, Análisis de resultados, Administrativas o gerenciales), la
jornada (lunes a jueves 8,5 horas y viernes 8,0) y **los 40 festivos de Colombia de 2026 y
2027**. Los festivos van en una lista literal por fecha, como pidió: se revisan de un vistazo
y se amplían a mano, en vez de calcularlos con un algoritmo que se equivoca en silencio.

**3. Actividades.** Crear, renombrar, activar y desactivar. Una actividad **con horas
registradas no se puede borrar**: se desactiva y deja de ofrecerse en los proyectos nuevos,
sin tocar lo ya registrado. La pantalla lo dice antes de que lo intente — el botón de borrar
aparece deshabilitado con el motivo escrito debajo.

**4. Proyectos.** Se crean a mano, con cliente, nombre y las horas estimadas de al menos una
actividad. Se pueden ampliar o reducir después, y **cada cambio deja rastro**: qué actividad,
de cuántas horas a cuántas, quién y cuándo. El historial se ve desplegando un botón en el
propio proyecto.

**5. Lo que todavía no hace.** No se registran horas: eso es H2. Por eso la columna
"Consumidas" sale en 0 en toda la etapa. Está puesta desde ahora para que la pantalla no
cambie de forma cuando empiecen a entrar datos.

---

## Evidencia

- **75 comprobaciones automáticas** propias de la etapa, todas pasan. **0 llamadas a la IA**:
  este módulo no usa IA en ningún punto.
- Las reglas no están solo declaradas, están **probadas contra la base**: se intentó guardar
  0,3 horas (rechazado, van en pasos de 0,25), una estimación de cero (rechazada) y un
  proyecto con nombre repetido en el mismo cliente (rechazado, comparando sin tildes ni
  mayúsculas).
- **El módulo de análisis sigue exactamente igual**: la suite completa de la Etapa 2 pasa en
  las cuatro salidas, y siguen pasando las pruebas de las Etapas 5b, 6 y 7. Los tests del
  backend pasan de 492 a **521**, con los 29 nuevos; la única falla es la misma de siempre,
  anterior a todo el plan.
- **No se tocó ningún archivo protegido.**
- Los datos de prueba se borran solos al terminar cada prueba, incluso si falla a mitad.

---

## Guion para validar

Recargue con **Ctrl + Shift + R**. No hace falta rebuild.

**1. El menú.** En el lateral aparece una sección nueva, **Horas**, con **Proyectos** y
**Actividades**.

**2. Actividades.** Abra Actividades: están las **cinco iniciales**, con sus tildes. Cree una
nueva escribiendo el nombre y pulsando Crear. Desactive una con el botón **Desactivar** —
verá que queda tachada y marcada como Inactiva. Fíjese en el botón rojo de borrar de las
cinco iniciales: si alguna está usada en un proyecto, aparece **deshabilitado y con el motivo
escrito debajo**.

**3. Crear un proyecto.** Abra Proyectos → **Proyecto nuevo**. Verá que el botón de guardar
**no se habilita** hasta que haya cliente, nombre y al menos una actividad con horas: es la
regla de la especificación, visible antes de enviar nada. Ponga dos actividades con horas
distintas y créelo.

**4. El historial.** Dentro del proyecto, cambie las horas estimadas de una actividad y salga
del campo. El total se actualiza al instante. Pulse **Ver historial de estimaciones**: ahí
está el cambio, con el valor anterior, el nuevo, su nombre y la fecha.

**5. Que el análisis sigue igual.** Abra un informe cualquiera desde Historial Reporte y
expórtelo en PDF. Tiene que salir exactamente como antes.

---

## Un detalle que conviene que sepa

Probar que **un analyst no puede cerrar un proyecto** por la interfaz exigía entrar con la
cuenta de otra persona, y no pedí la contraseña de nadie. Esa regla quedó probada en las
pruebas automáticas, contra el mismo guardia que usa el servidor — está anotado en el
reporte 64. Si quiere verlo con sus ojos, basta con entrar como Moni, adrián o rubén y
comprobar que el botón de cerrar no aparece.

---

**Estado: Etapa H1 implementada, pendiente validación de Fredy.**
