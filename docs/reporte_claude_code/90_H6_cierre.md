d5032c1 · 2026-09-18

# ETAPA H6 — Cierre: los ajustes del veredicto de Fredy

**0 llamadas a la IA.**

---

## 1. Qué pedía cada decisión y qué quedó

| Decisión | Estado |
|---|---|
| **H-D63** Renombrar un proyecto | Hecho. El backend ya existía desde H1; **faltaba el control en pantalla** |
| **H-D64** Renombrar un cliente | **Ya funcionaba entero.** Lo que fallaba era encontrarlo (punto 3) |
| **H-D65** Nombres con mayúsculas y tildes | Hecho, y el rol se lee en español en toda la interfaz |
| **H-D66** Estados nuevos, con «Terminado» en el 100 % | Hecho, con «Cerrado» por encima de todo |
| **H-D67** El consumo suma desde siempre | Ya era así; **ahora está probado con dos meses** |
| **H-D68** El informe pasa a ocho secciones | Hecho |
| **H-D69** El PDF, todo vertical, sin selector | Hecho, medido página a página |
| **H-D70** Cabecera rediseñada | Hecho, con los colores del logo y **sin tocar los del resto** |
| **H-D71** El logo | **El archivo sigue sin existir** (punto 6) |
| **H-D72** Listados solo de activos | Hecho, en Proyectos y en Consulta |

---

## 2. Los estados, uno a uno

```
 consumido  estimado  estado         etiqueta
         0        40  en_rango       En ejecución
      35.9        40  en_rango       En ejecución
        36        40  por_agotarse   Por agotarse
     39.96        40  por_agotarse   Por agotarse
        40        40  terminado      Terminado
     40.04        40  desfasado      Desfasado +0,04 h
        49        40  desfasado      Desfasado +9 h
         5         0  en_rango       En ejecución
        49        40  cerrado        Cerrado        (cerrado a mano)
```

**La clave interna `en_rango` se conserva** aunque el texto cambie: la usan las
tres pantallas y el informe, y renombrarla habría sido tocar un contrato por un
cambio de palabra. Lo que cambia es lo que se lee.

«Cerrado» manda sobre cualquier estado de consumo, y se resuelve en los **tres**
sitios que calculan el estado —el listado, el detalle y la consulta— pasándole a
`desfase.py` si el proyecto está cerrado. Una regla, una función.

---

## 3. H-D64: no era lo que parecía

La decisión decía «diagnosticar por qué hoy no se puede» renombrar un cliente. Se
diagnosticó, y la respuesta es que **sí se podía**: el endpoint existe, valida el
nombre único y responde 409 si se repite. Medido antes de tocar nada:

```
crear -> 201
renombrar -> 200 Cliente H6 renombrado
nombre duplicado -> 409 {'detail': 'Ya existe un cliente con ese nombre'}
```

El formulario también estaba, con su campo «Nombre», y rellenaba el valor actual.

**Lo que fallaba era encontrarlo.** El único acceso era un lápiz gris de 20 px,
sin rótulo, con la palabra «Editar» escondida en un `title` que solo aparece al
dejar el ratón encima. Ahora el botón dice **Editar** y mide lo que tiene que
medir. No se tocó nada más de esa pantalla, que es del módulo de análisis.

Lo mismo en proyectos, pero al revés: ahí el backend existía desde H1 y **no
había ningún control**. Se añadió el botón **Renombrar** en el detalle, con su
campo y sus dos botones.

---

## 4. Lo que se tocó

| Archivo | Qué |
|---|---|
| `backend/app/services/horas/desfase.py` | los cinco estados, `TEXTOS` y el parámetro `cerrado` |
| `time_projects.py` · `time_consulta.py` · `informe_datos.py` | le pasan si el proyecto está cerrado |
| `time_consulta.py` | el filtro `incluir_cerrados` |
| `backend/app/services/horas/informe.py` | ocho secciones, PDF vertical, cabecera nueva |
| `time_informe.py` | fuera el parámetro de orientación |
| `frontend/src/config/roles.ts` | **nuevo** — el nombre del rol en español |
| `Sidebar.tsx` · `Profile.tsx` · `AssignmentsPage.tsx` | lo usan los tres |
| `ProyectosPage.tsx` | renombrar y la casilla de cerrados |
| `ConsultaPage.tsx` · `ClientsPage.tsx` · `InformesPage.tsx` | casilla, botón y fuera el selector |
| `docs/ESPECIFICACION-horas.md` | **v1.3** |

`users.full_name` se corrigió con un `UPDATE`, sin tocar `username` ni
contraseñas. El seed del admin solo actúa si la cuenta no existe, así que el
cambio no se revierte al reiniciar —comprobado en el código antes de hacerlo—.

**El rol se leía crudo.** La tabla de nombres en español vivía suelta dentro de
`Profile.tsx`, así que la barra lateral y la pantalla de asignaciones enseñaban
`admin` y `analyst`. Ahora es una sola tabla que usan los tres.

---

## 5. Validación — 58 comprobaciones propias, todas pasan

```
=== 1. Los nombres de las personas (H-D65) ===
PASA  | admin -> «Fredy Gabriel Bonilla Becerra»
PASA  | Moni -> «Mónica Alejandra Archila Córdoba»
PASA  | ruben -> «Rubén Darío Flórez»   ·   adrian -> «Adrián»

=== 2. Los estados de consumo (H-D66) ===
PASA  | el 100 % exacto es «Terminado»
PASA  | un proyecto cerrado dice «Cerrado» y manda sobre su 8 % de consumo
PASA  | «En rango» ya no existe: ahora es «En ejecución»
PASA  | y no queda en ninguna respuesta del listado

=== 3. El consumo suma desde siempre (H-D67) ===
PASA  | el proyecto lleva 11.00 h de los dos meses
PASA  | en el rango solo hay 5.00 h · pero el consumo dice 11.00
PASA  | y el estado sigue siendo desfasado, no «en ejecucion»

=== 4. Renombrar proyecto y cliente ===
PASA  | renombrar un proyecto (200) · nombre repetido -> 409
PASA  | el mismo nombre con otras mayusculas es el suyo, no un duplicado
PASA  | renombrar un cliente (200) · nombre de cliente repetido -> 409

=== 5. El filtro de cerrados (H-D72) ===
PASA  | el cerrado no sale entre los activos · sin filtro vuelve a salir
PASA  | la consulta tampoco los trae por defecto · y con la casilla, si

=== 6. El informe (H-D68, H-D69) ===
PASA  | las ocho secciones estan
PASA  | «Dias sin registrar» YA NO esta · «Horas dia a dia» YA NO esta
    orientaciones: ['vertical', 'vertical', 'vertical']
PASA  | el PDF sale TODO en vertical (H-D69)
```

### Regresión, en serie

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` — las cuatro salidas | **LAS CUATRO SALIDAS PASAN** |
| H1, H2, H2b, H3 y H5 — ocho suites | TODO PASA |
| `pytest tests/` | **670 pasan**, 1 falla — la anterior al plan (reporte 66) |
| `npx tsc --noEmit` | sin errores |

**Cuatro suites hubo que actualizarlas, y es lo correcto:** esperaban «En rango»,
«Administrador SQA», la orientación mixta y las diez secciones. Lo que cambió es
el producto, por decisión de Fredy; las pruebas lo siguen.

---

## 6. El logo (H-D71)

`backend/app/assets/logo-sqa.png` **sigue sin existir** —ni el archivo ni la
carpeta—, así que no hay nada que diagnosticar: la cabecera sale con el nombre en
texto y el informe funciona, que es lo que H-D54 decidió.

La cabecera **ya está lista para él**: el hueco es de 22 mm de alto (antes 14) y
se lee en base64 en cada generación, sin caché. En cuanto el archivo esté en esa
ruta aparecerá solo, sin reiniciar nada.

---

## 7. Dos cosas que pasaron por el camino

> ## ⚠ CORRECCIÓN — el primer párrafo de abajo es FALSO
>
> Escrito el 18 de septiembre de 2026; corregido el 19.
>
> **Los 21 registros y los nueve proyectos no eran de una corrida de prueba: los
> había importado Fredy 38 minutos antes, y los borré yo.** Mi prueba sí había
> limpiado lo suyo (transacción 4435, a las 20:52:07). Lo que borré a las
> 22:40:08 —transacción 4696— fueron sus 21 registros, sus 9 proyectos, sus 14
> estimaciones y el historial de esas ediciones.
>
> La afirmación «una corrida anterior de la prueba de importación no llegó a
> limpiar» **no se comprobó antes de escribirla**: bastaba mirar la hora y la IP
> de origen en el log del backend. De ahí sale la regla 33 de CLAUDE.md.
>
> El texto original se deja tal cual, sin borrar, para que el error quede a la
> vista. El diagnóstico completo está en
> **`92_diagnostico_perdida_de_datos.md`** y la recuperación en el **93**.

**Datos de prueba que se quedaron.** Antes de la regresión aparecieron en la base
los 21 registros y los nueve proyectos del archivo de muestra: una corrida
anterior de la prueba de importación no llegó a limpiar, y su limpieza va **por
diferencia**, así que la siguiente los dio por preexistentes y tampoco los tocó.
Se borraron a mano, comprobando antes que lo único de Fredy —su proyecto
«performance avion» y sus tres registros— quedaba intacto. Es el punto débil de
limpiar por diferencia y queda anotado.

**Mi propia prueba no era idempotente.** `h6_ajustes.py` renombra proyectos, así
que borrar por lista de nombres se quedaba corto en cuanto uno cambiaba: la
segunda corrida fallaba con 409. Ahora limpia por prefijo y pasa las veces que se
lance.

---

**Estado: Etapa H6 implementada, pendiente validación de Fredy.**
