d5032c1 · 2026-09-18

# ETAPA H6 — para Fredy

---

## Qué se hizo

Sus diez ajustes, uno por uno.

**1. Su nombre, bien escrito.** La cuenta `admin` se llama ahora **Fredy Gabriel
Bonilla Becerra**, y debajo, en gris, **Administrador**. También están
corregidos **Mónica Alejandra Archila Córdoba**, **Rubén Darío Flórez** y
**Adrián**. El rol se lee en español en toda la interfaz; antes la barra lateral
y la pantalla de asignaciones enseñaban `admin` y `analyst` en crudo.

**2. Los estados dicen algo.** «En rango» no decía nada. Ahora:

| Estado | Cuándo |
|---|---|
| **En ejecución** | por debajo del 90 % |
| **Por agotarse** | del 90 % al 99,9 % |
| **Terminado** | justo el 100 %: se consumió lo estimado, ni una hora más |
| **Desfasado +X h** | por encima, con las horas de más |
| **Cerrado** | el proyecto se cerró a mano; manda sobre todo lo demás |

**3. El consumo suma desde siempre.** Ya era así, pero ahora está probado: un
proyecto con 6 horas de agosto y 5 de septiembre sobre 10 estimadas sale
**Desfasado +1 h**, y sigue saliendo así aunque usted consulte solo septiembre,
donde solo hay 5.

**4. Renombrar proyectos.** Desde el detalle del proyecto, botón **Renombrar**.
Si el nombre ya existe en ese cliente, lo dice y no lo deja.

**5. Renombrar clientes: ya se podía.** Aquí le debo una explicación, en el punto
de abajo.

**6. Los listados enseñan lo que está en marcha.** Proyectos y Consulta traen
solo los **activos**; una casilla **Incluir cerrados** los recupera. Cerrar y
reabrir siguen donde estaban.

**7. El informe pasa a ocho secciones.** Salieron «Días sin registrar» y «Horas
día a día». Los datos siguen calculándose y viéndose donde sirven —el calendario
y la consulta—, pero en un informe para leer no aportaban lo que ocupaban.

**8. El PDF va todo en vertical**, y desapareció el selector de orientación: la
única sección que obligaba a girar la hoja era justo «Horas día a día».

**9. La cabecera, rediseñada.** El hueco del logo pasa de 14 a 22 mm para que se
lea, el título y el periodo quedan jerarquizados y usa los dos colores del logo
—el azul marino y el naranja—. **El resto del informe no cambió de colores**,
como pidió.

---

## Evidencia

- **58 comprobaciones automáticas** propias de estos ajustes, todas pasan. **0
  llamadas a la IA**.
- Los bordes del estado, medidos uno a uno: 89,75 % · 90 % · 99,9 % · **100 %
  exacto** · 100,1 % · sin estimación · proyecto cerrado.
- La orientación del PDF está **medida página a página**: vertical, vertical,
  vertical.
- **El resto de Kinetix no se movió**: la suite de la Etapa 2 pasa en las cuatro
  salidas, y H1, H2, H2b, H3 y H5 siguen verdes. `pytest` 670, `tsc` limpio.
- Sus nombres se cambiaron con un `UPDATE` sobre `full_name`: **no se tocó ningún
  usuario ni ninguna contraseña**.

---

## Guion para validar

Recargue con **Ctrl + Shift + R**. No hace falta rebuild.

**1. Su nombre.** Mire abajo a la izquierda: **Fredy Gabriel Bonilla Becerra** y,
debajo, **Administrador**.

**2. Renombrar un proyecto.** Horas → Proyectos → abra uno → **Renombrar**.
Cámbielo y guarde. Pruebe a ponerle el nombre de otro proyecto del mismo cliente:
tiene que avisarle.

**3. Renombrar un cliente.** Administración → Clientes → botón **Editar** de
cualquier fila → cambie el nombre → Guardar.

**4. Los estados.** En Proyectos, mire la columna «Consumo». Ponga a un proyecto
unas horas estimadas exactamente iguales a las consumidas: dirá **Terminado**.

**5. Cerrar y volver a ver.** Cierre un proyecto desde su detalle. Vuelva al
listado: ya no está. Marque **Incluir cerrados**: vuelve, y con la etiqueta
**Cerrado**. Lo mismo en Horas → Consulta.

**6. El informe.** Horas → Informes. Cuente las secciones: ocho. Descargue el PDF
y compruebe que **todas las páginas están en vertical** y que la cabecera se ve
como quería.

---

## Lo del renombrar clientes, que conviene que sepa

Miré por qué no se podía, y resulta que **sí se podía**: el endpoint existía,
validaba que el nombre no se repitiera y el formulario tenía su campo con el
valor puesto. Lo comprobé antes de tocar nada —crear, renombrar y repetir un
nombre— y respondió 201, 200 y 409.

**Lo que fallaba era encontrarlo.** El único acceso era un lápiz gris pequeño,
sin ninguna palabra, con «Editar» escondido en el globito que solo sale al dejar
el ratón encima. No es raro no haberlo visto. Ahora el botón dice **Editar** y
tiene el tamaño de un botón. No toqué nada más de esa pantalla.

Y el caso contrario: en proyectos el backend estaba desde H1 y **no había ningún
botón**. Ese sí hubo que ponerlo.

---

## Y una cosa que sigue pendiente, que es suya

**El logo.** `backend/app/assets/logo-sqa.png` sigue sin existir, así que la
cabecera lleva el nombre en texto. El hueco ya está preparado a 22 mm y el
informe lo lee en cada generación: **en cuanto deje el archivo ahí aparecerá
solo**, sin reiniciar nada ni volver a pedirme nada.

---

**Estado: Etapa H6 implementada, pendiente validación de Fredy.**
