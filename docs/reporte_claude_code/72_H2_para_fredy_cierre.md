cdb5e1c · 2026-09-17

# ETAPA H2 — para Fredy

---

## Qué se hizo

Ya se pueden **registrar horas**. Esta etapa pone la pantalla del día a día y todas las
reglas que la acompañan.

**1. La vista semanal.** Una tarjeta por día, con las horas registradas frente a la jornada
que le toca (8,5 de lunes a jueves, 8,0 el viernes). Se navega con las flechas, con el botón
**Hoy** o saltando a una fecha concreta.

**2. Registrar.** Se elige cliente, luego proyecto, luego actividad — cada selector se abre
cuando el anterior tiene valor —, las horas, si es facturable, si es hora extra y, si quiere,
unas observaciones. **Facturable se hereda del último registro de ese proyecto**, para no
marcarlo mal por descuido.

**3. Pasarse de lo estimado no bloquea.** Al elegir la actividad se ven las horas que quedan.
Si pone más, aparece un aviso con la cifra exacta, **se puede guardar igual**, y el registro
queda marcado en ámbar — tanto en la lista del día como en el proyecto. Es lo que pedía la
especificación: avisar, no impedir.

**4. Las horas extra van aparte.** Se marcan en el propio registro, se muestran separadas de
las ordinarias, **consumen las horas estimadas del proyecto**, y un día con extras deja de
contar como incompleto.

**5. Los días que faltan.** Un panel arriba lista los días sin registrar o por debajo de la
jornada, con las horas que faltan en cada uno. Cada uno es un botón: al pulsarlo se abre esa
semana **con el día resaltado**. Los festivos y las ausencias no se reclaman.

**6. Editar y borrar.** Cada quien edita los suyos; el administrador, todos. **Borrar es solo
del administrador**, como en el resto de la plataforma. Y cuando el administrador registra
horas por otra persona, queda guardado quién las registró.

---

## Evidencia

- **91 comprobaciones automáticas** propias de la etapa, todas pasan. **0 llamadas a la IA**.
- Las reglas se probaron donde se ven: registrar 6 horas en una actividad con 4 estimadas
  **se guarda** y sale marcado; marcar un registro como extra hace que ese día deje de
  aparecer como incompleto; bajar un lunes de 8,5 a 6 horas hace que **pase** a estar
  incompleto — no es un valor guardado, se recalcula.
- Un festivo puesto a propósito en la semana de prueba **no aparece** en la lista de
  pendientes.
- **Cero errores de JavaScript** en la pantalla.
- **El módulo de análisis sigue igual**: la suite completa de la Etapa 2 pasa en las cuatro
  salidas, y las pruebas de H1 siguen pasando. Los tests del backend van de 521 a **550**.
- **No se tocó ningún archivo protegido** ni hizo falta cambiar la base de datos: la tabla de
  registros se creó entera en H1, y esa decisión se acaba de cobrar.
- Los datos de prueba se borran solos al terminar, incluso si la prueba falla a mitad.

---

## Guion para validar

Recargue con **Ctrl + Shift + R**. No hace falta rebuild.

**1. La semana.** Horas → **Registro**. Verá la semana actual, con la jornada de cada día y
los totales arriba.

**2. Registrar.** En cualquier día, pulse **Registrar**: elija cliente, proyecto, actividad,
ponga las horas, marque si es facturable y guarde. El total del día y el de la semana se
actualizan.

**3. Pasarse de lo estimado.** Elija una actividad y fíjese en las horas que quedan. Ponga
más de las que quedan: aparece el aviso con la cifra. **Guarde igual** — el registro sale
marcado como exceso. Abra ese proyecto en Horas → Proyectos: también lo marca.

**4. Horas extra.** Registre unas horas marcando **Hora extra**: salen separadas, con su
propio total, y ese día deja de contar como incompleto.

**5. Un día incompleto.** Registre menos horas de las que toca en algún día. Aparecerá en el
panel de arriba con las horas que faltan. Pulse ese botón: se abre esa semana con el día
resaltado. Complételo y desaparece de la lista.

**6. Un festivo.** Navegue a una semana con festivo — por ejemplo la del 12 de octubre. El
día sale marcado y **no** se reclama como pendiente.

**7. Que el análisis sigue igual.** Abra un informe desde Historial Reporte y expórtelo en
PDF.

---

## Un detalle que conviene que sepa

Dos reglas de permisos no se pudieron probar por la interfaz sin entrar con la cuenta de otra
persona, y no pedí la contraseña de nadie: que **un analyst no pueda registrar horas por
otro** y que **no pueda borrar**. Las dos quedaron probadas en las pruebas automáticas,
contra el mismo guardia que usa el servidor. Si quiere verlo, basta con entrar como Moni,
adrián o rubén: el selector de persona aparece bloqueado y el botón de borrar no está.

---

**Estado: Etapa H2 implementada, pendiente validación de Fredy.**
