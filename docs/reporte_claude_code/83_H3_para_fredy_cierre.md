9332fa9 · 2026-09-18

# ETAPA H3 — para Fredy

---

## Qué se hizo

Dos cosas grandes: **consultar** las horas de cualquier proyecto y **subir el
Excel** de tu herramienta de horas sin volver a teclearlas.

**1. Consulta de proyectos.** Horas → **Consulta**. Filtras por cliente,
proyecto, persona y fechas, y ves por proyecto **quién ha registrado y cuántas
horas**, con lo estimado, lo consumido, lo que queda y el estado de desfase.
Amplías un proyecto y sale su gente; amplías una persona y salen **sus días**,
con actividad, horas, si se cobra y las observaciones.

**2. Dos cifras de horas que no son la misma**, y conviene saberlo: «En el rango»
es lo registrado en las fechas que consultaste; «Consumidas» es todo lo que lleva
el proyecto desde siempre. **El desfase se mide contra lo segundo**, porque si no,
consultar una semana tranquila dejaría «en rango» un proyecto que la pantalla de
Proyectos marca como desfasado.

**3. El aviso de desfase, completo.** Ahora cada proyecto lleva **una barra** de
consumido frente a estimado, y arriba un aviso dice **cuántos proyectos están
desfasados** con un botón para ver solo esos. Está en Consulta y en Proyectos.

**4. Importar el Excel.** Horas → **Importar**. Subes el archivo, eliges de quién
son las horas y pulsas **Ver qué va a pasar**. **No se guarda nada todavía**:
primero ves la vista previa, y solo entonces confirmas.

**5. La vista previa te dice todo antes de decidir:** qué clientes, proyectos y
actividades se van a crear; qué filas se crean y cuáles se actualizan; **qué
filas no entran y por qué, con su número de fila** para que puedas ir a mirarlas;
y cuáles quedan por encima de lo estimado.

**6. Subir el mismo archivo dos veces no duplica nada.** Cada fila trae su `Id` y
la segunda vez se actualiza en lugar de crearse. Probado con tu archivo: 75,5 h
antes, 75,5 h después.

**7. Los proyectos que nacen de la importación no tienen horas estimadas**, y el
resumen final te da **un enlace a cada uno** para que se las pongas. Mientras no
las tengan no pueden salir desfasados: sin estimación no hay contra qué comparar.

---

## Evidencia

- **219 comprobaciones automáticas** propias de la etapa, todas pasan. **0
  llamadas a la IA** en todo el módulo.
- Se probó con **tu archivo real**, no con uno inventado: 21 filas, 75,5 h, 6
  clientes, 9 proyectos y 6 actividades. De esas 6, tres ya estaban en el
  catálogo y se reutilizaron; tres se crearon.
- **Reimportarlo no cambió el total** ni creó un solo cliente, proyecto o
  actividad de más.
- Se comprobó que **la vista previa no escribe nada**: después de pedirla, la
  base tenía exactamente los mismos registros, proyectos y clientes que antes.
- Las horas importadas se ven **en el calendario** y **en la consulta**, en los
  días que les tocan.
- **El resto de Kinetix no se movió**: la suite de la Etapa 2 pasa en las cuatro
  salidas, y H1, H2 y H2b siguen verdes.
- Los datos de prueba se borran solos, **incluso si la prueba falla a mitad**, y
  sin tocar los tuyos: la limpieza apunta lo que había antes y borra solo lo que
  apareció.

---

## Guion para validar

Recargue con **Ctrl + Shift + R**. Esta vez **sí hubo rebuild** (el lector de
Excel), pero ya está hecho.

**1. Consultar.** Horas → **Consulta**. Arranca en el mes en curso. Pruebe los
filtros de cliente, proyecto y persona.

**2. Ampliar.** Pulse un proyecto: sale la gente que registró en él. Pulse una
persona: salen **sus días**, con la actividad, las horas, el cobro y las
observaciones. Vuelva a pulsar y se pliega.

**3. El aviso de desfase.** Si hay algún proyecto pasado de horas, arriba lo dice
con el número. Pulse **Ver solo los desfasados**. Lo mismo en Horas → Proyectos.

**4. Importar.** Horas → **Importar**. Suba `horas_muestra.xlsx`, elija de quién
son las horas y pulse **Ver qué va a pasar**. Revise la vista previa: lo que se
va a crear, las filas que entran, las que no y por qué.

**5. Confirmar.** Pulse **Importar 21 filas**. El resumen dice cuántas entraron y
le ofrece el enlace de cada proyecto nuevo.

**6. Que las horas están.** Horas → **Registro**, septiembre: verá las horas en
sus días. Y en **Consulta**, los proyectos importados con lo consumido.

**7. Reimportar.** Suba **el mismo archivo otra vez**. La previa dirá que las 21
filas **se actualizan** y que no hay nada que crear. Confirme y compruebe en el
calendario que el total **no cambió**.

**8. Ponerle horas a un proyecto importado.** Desde el enlace del resumen, o en
Horas → Proyectos, abra uno de los creados: verá 0 estimadas y sus horas
consumidas. Póngale horas a su actividad y verá aparecer el estado de desfase.

**9. Que el análisis sigue igual.** Abra un informe desde Historial Reporte y
expórtelo en PDF.

---

## Dos cosas que conviene que sepa

**Lo que la prueba encontró y usted no habría visto hasta usarlo.** La
importación funcionaba perfectamente por debajo, pero desde el navegador fallaba
de dos formas a la vez: el archivo viajaba con la cabecera equivocada y el error
que eso provocaba **dejaba la pantalla en blanco** en vez de explicarse. Las dos
están arregladas. Lo cuento porque explica por qué insisto en probar también con
navegador y no solo contra la API.

**Un rebuild se lleva las herramientas de prueba.** Playwright, su navegador y la
sesión de pruebas viven dentro del contenedor, no en la imagen —a propósito, para
no meter herramientas de prueba en el producto—. Al reconstruir hubo que
reponerlos. No es un fallo, pero cuente ese rato la próxima vez.

---

**Estado: Etapa H3 implementada, pendiente validación de Fredy.**
