# ETAPA H8, SUB-PASO H8.3 — el estado en las pantallas y en el informe

Commit base `679f186` · 23 de septiembre de 2026 · rama `backup-trabajo-local`
· **0 llamadas a la IA** · `pg_dump` previo de H8.1 en
`C:\proyectos\Kinetix_pruebas\backup_20260923_h8.sql`

**Sub-paso cerrado.** Fredy cerró la aplicación antes de empezar (R4). Suite
nueva de navegador: **37 comprobaciones, 0 fallos**; `h82_estados` sigue en 91.

---

## 1. El hallazgo que explica lo que Fredy veía

**La columna «Estado» del informe enseñaba el consumo, no el estado.** En los
dos sitios a la vez: `_sec_proyectos` de `informe.py` titulaba «Estado» y pintaba
`overrun_label`, y `InformesPage` hacía lo mismo en la vista previa.

Por eso el informe decía **«En ejecución» de diez proyectos a los que nadie les
había puesto ese estado**: era el `en_rango` del consumo con el rótulo que le
puso v1.3. La columna no existía; existía una sola con el nombre de la otra.

Así que en la sección 6 esto no fue añadir una columna, fue **renombrar la que
había a «Consumo» y meter la de verdad**.

---

## 2. Lo que se hizo

Siete archivos. Ninguno protegido.

| Archivo | Qué |
|---|---|
| **`components/horas/EstadoProyecto.tsx`** | **NUEVO.** El chip y el selector, en un solo sitio |
| `api/horasApi.ts` | `EstadoProyecto`, `ConEstado`, `can_*`, `CambioDeEstado`; `EstadoDesfase` baja a cuatro; `cambiarEstadoProyecto` e `historialEstado`; los filtros pasan a `incluir_finalizados` |
| `components/horas/AvisoDesfase.tsx` | Fuera `cerrado` del mapa de colores y de la barra |
| `pages/horas/ProyectosPage.tsx` | Selector en el detalle y en el listado, la casilla nueva, `can_edit_estimates` en los cuatro controles, y el historial de estados |
| `pages/horas/ConsultaPage.tsx` | Columna **Estado** propia y la casilla nueva |
| `pages/horas/InformesPage.tsx` | Sección 6 con las dos columnas |
| `components/horas/PopupRegistro.tsx` | El selector de proyecto ofrece **solo los que admiten horas** |
| `services/horas/informe.py` | La columna nueva y el párrafo de la sección |
| `pruebas_e2e/h83_pantallas.py` | **NUEVA.** La suite |
| `pruebas_e2e/h7_pantallas_horas.py` | Una línea: el testid de la casilla |

### `EstadoProyecto.tsx`

Mismo criterio que `estados.py` en el backend. Lo usan el listado, el detalle,
la Consulta y el historial. Y **no lleva la tabla de §3.1 dentro**: lo que se
puede hacer en cada estado llega del backend.

Los colores del chip son distintos de los del consumo a propósito. Si los dos
juegos se parecieran, las dos columnas volverían a leerse como una sola, que es
el problema del que viene H-D82.

### El popup de registro, que no estaba en el plan

`PopupRegistro` pedía los proyectos con `estado: 'activo'`, y el compilador lo
señaló al estrechar el tipo. Con cinco estados, lo correcto no es traducirlo:
**el único estado que admite horas es `en_ejecucion`** (§3.1), así que eso es lo
que pide ahora. Antes ofrecía un proyecto detenido y el guardado devolvía un 409
con el formulario ya relleno.

### El informe

La columna «Estado» va en **texto plano, sin píldora**, como acordamos: dos
juegos de píldoras en la misma tabla compiten, y la que hay que ver de un
vistazo es la del consumo. **`docs/diseno-informe-horas.md` no cambia**: ni un
color nuevo en el documento.

El párrafo de la sección lo dice con el estilo de D-D4:

> *«Estado y consumo contestan dos preguntas distintas: el estado dice en qué
> punto está el proyecto y lo decide una persona; el consumo dice cuántas horas
> lleva de las estimadas y lo calcula el sistema. Un proyecto finalizado puede
> haber gastado la mitad, y uno en ejecución ir desfasado.»*

Ojo al escribir estos párrafos: se insertan con `esc(intro(d))`, así que **el
markdown no se interpreta**. Unos asteriscos de negrita habrían salido impresos.

---

## 3. La comprobación que pidió Fredy, y cómo se demuestra

> *«Que los campos de estimación se deshabiliten según `can_edit_estimates` y
> **no** según una regla escrita en TypeScript.»*

Comprobar que el campo se deshabilita en un proyecto finalizado **no demuestra
nada**: pasaría igual si la pantalla dedujera de `status`. Lo que lo demuestra es
**mentirle a la pantalla**: se intercepta la respuesta del backend y se le pone
`can_edit_estimates: false` **sin tocar `status`**, que sigue diciendo
`en_ejecucion`.

```
PASA | el estado que ve la pantalla sigue siendo «en_ejecucion»
PASA | y AUN ASÍ la estimación queda bloqueada: la pantalla obedece a
       `can_edit_estimates`, no a una regla suya
PASA | lo mismo con el botón de quitar la actividad
```

Si alguien vuelve a escribir la regla en TypeScript, esas tres líneas fallan.

---

## 4. Tres cosas del oficio que costaron una vuelta

- **El detalle del proyecto no es una URL.** Es estado interno de la página, así
  que `page.reload()` devuelve al listado. Para volver a entrar con la respuesta
  interceptada hay que salir al listado y pulsar otra vez.
- **Una ruta de Playwright registrada después gana a la anterior.** El `mentir`
  tapaba al desvío al 8002, y la petición se iba al 8001 —otra base— sin decir
  nada. El desvío hay que rehacerlo dentro del interceptor.
- **Las cabeceras salen en mayúsculas** por el `uppercase` del CSS, no en el
  HTML. Comparar `"Estado"` contra lo que devuelve `inner_text` falla.

Y una de diseño que la prueba confirmó: pulsar el selector de estado en una fila
**no abre el proyecto**, porque el `onClick` para la propagación. La suite pulsa
la celda del nombre.

---

## 5. La validación

```
docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/h83_pantallas.py
```

**37 comprobaciones, 0 fallos**, consola del navegador limpia.

| Bloque | Qué fija |
|---|---|
| 1 | Proyectos: «Estado» y «Consumo» son dos cabeceras, en ese orden; el selector está en la fila; el finalizado se esconde y el **detenido no**; y una misma fila dice «finalizado» en una celda y «Desfasado +4,5 h» en otra |
| 2 | **`can_edit_estimates` manda** (§3) |
| 3 | El historial de estados, con su línea «En ejecución → Finalizado», encima del de estimaciones |
| 4 | La consulta: columna Estado propia, y la casilla nueva |
| 5 | El informe en los tres soportes: los datos traen estado y consumo separados; el HTML tiene las dos cabeceras y **una sola píldora por fila**; el párrafo dice «dos preguntas distintas»; el PDF se genera |

Las que ya existían —`h15_pantallas`, `h2b3_pantalla`, `h7_pantallas_horas`,
`h52_informe`, `h53_h54_documento`, `h82_estados`— pasan. La de H7.4 necesitó
una línea: buscaba el testid `incluir-cerrados`.

**La base de Fredy: 10 proyectos, 24 registros, ningún `ZZTEST`.** Intacta.

---

## 6. Lo que queda

- **H8.4** — las horas extra en el mapa (`#bfdbfe`, y rasterizar el PDF para
  saber si WeasyPrint honra el gradiente).
- H8.5 — el borrado del periodo.
- H8.6 — regresión, retirar los alias de H-D91, estrechar el CHECK a cinco, las
  dos suites del laboratorio que no corren, y cierre.

Pendiente de **la validación visual de Fredy** (regla 9): compilar en verde y
pasar las suites no es que la pantalla se vea bien.
