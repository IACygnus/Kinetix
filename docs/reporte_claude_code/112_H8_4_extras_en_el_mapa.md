# ETAPA H8, SUB-PASO H8.4 — las horas extra en el mapa del mes

Commit base `679f186` · 23 de septiembre de 2026 · rama `backup-trabajo-local`
· **0 llamadas a la IA** · `pg_dump` previo de H8.1 en
`C:\proyectos\Kinetix_pruebas\backup_20260923_h8.sql`

**Sub-paso cerrado.** Suite nueva: **21 comprobaciones, 0 fallos**. Capturas en
`C:\proyectos\Kinetix_pruebas\h84_capturas\`.

Las cuatro decisiones de H8.3b quedan anotadas como aprobadas en
`docs/diseno-informe-horas.md`.

---

## 1. Lo que se hizo (H-D85, H-D86)

Un día con horas extra se pinta **partido**: abajo las ordinarias con el color
del día, arriba las extra en `#bfdbfe`, **en proporción**. 8,5 ordinarias y 2
extra dejan el corte al **81,0 %**.

| Archivo | Qué |
|---|---|
| `schemas/time_tracking.py` | `InformeMapaPersona.extra_por_dia` |
| `services/horas/informe_datos.py` | Lo rellena desde `DiaDelCalendario.extra` |
| `services/horas/informe.py` | `_casilla_mapa()`, el CSS, la leyenda y el párrafo |
| `api/horasApi.ts` · `pages/horas/InformesPage.tsx` | Lo mismo en pantalla |
| `pruebas_e2e/h84_mapa.py` | **NUEVA** |

**El dato ya existía**: `DiaDelCalendario` lleva `ordinarias` y `extra` por
separado desde H2. El mapa solo usaba `total` y tiraba la mitad.

Es un `linear-gradient` de corte duro, no dos cajas apiladas: la regla 11 prohíbe
`flex` y `grid` en la rama de papel, y dos `div` con altura en porcentaje dentro
de un `<td>` no se comportan igual en los dos motores.

---

## 2. El hallazgo: WeasyPrint y la sintaxis de doble posición

**Sí honra `linear-gradient`** —no hizo falta recurrir a dos rectángulos—, **pero
no la forma de doble posición**, que es CSS Images Level 4:

```css
/* funciona */     linear-gradient(to top,#dcfce7 81%,#bfdbfe 81%)
/* NO funciona */  linear-gradient(to top,#dcfce7 0 81%,#bfdbfe 81% 100%)
```

La descarta **entera y sin avisar**. Y lo peor es cómo falla: la casilla se
queda con el fondo de su clase —verde— y **tiene aspecto de estar bien**. No hay
error, no hay hueco, no hay nada que mirar.

Medido aparte, en una prueba mínima al 81 %:

| Sintaxis | Píxeles verdes | Píxeles azules |
|---|---|---|
| doble posición | 0 | 0 |
| clásica | 21.714 | 5.313 |

(Con la doble posición los dos son cero porque la celda se queda sin fondo
ninguno; en el informe el fondo venía de la clase.)

Está anotado en `docs/diseno-informe-horas.md`, porque vale para **cualquier
gradiente que este producto mande a papel**.

---

## 3. Dos veces estuve a punto de dar por bueno lo que no lo era

Merece contarse porque las dos son la misma trampa de siempre —una comprobación
que pasa sin mirar lo que dice mirar— y las dos las pilló la imagen, no el
código.

### 3.1 La prueba pasaba mirando la leyenda

La primera versión contaba píxeles azules **en toda la página** y daba verde.
Pero la leyenda lleva su propia muestra azul de 3,5 mm: el azul que veía era
ese, y el gradiente estaba roto. Al mirar la captura no había ninguna casilla
partida.

Ahora se cuenta **dentro de la fila del mapa**, separando las bandas por altura
—una casilla mide unos 65 px a escala 3, la leyenda menos de 40—.

### 3.2 Y luego, contando sobre PNG de otra corrida

`pdf_a_png.py` escribe `_p1.._pN` y **no borra nada**. Una corrida anterior había
dejado un `_p4` del informe completo, con la píldora azul «En ejecución» de la
sección 6 (que usa **el mismo `#bfdbfe`**, H-D103), y el barrido lo contaba como
si fuera de este documento. La suite ahora los borra antes de rasterizar.

Por lo mismo, el PDF de la comprobación se pide **solo con la sección del mapa**:
con el informe entero, la píldora de la sección 6 contamina la cuenta.

Y una tercera, menor: el barrido miraba un píxel de cada dos, así que la
proporción que comprobaba era la mitad de la real.

---

## 4. Un arreglo de paso

Con la séptima entrada, la leyenda partía **«horas / extra»** en dos líneas —y
es justo la que hay que leer para entender una casilla partida—. Cada entrada va
ahora en su propio `span` que no se rompe: la leyenda sigue ocupando dos líneas,
pero corta **entre** entradas.

---

## 5. La validación

```
docker exec jmeter_backend python3 /tmp/e2e/h84_mapa.py
```

**21 comprobaciones, 0 fallos.**

| Bloque | Qué fija |
|---|---|
| 1 | `extra_por_dia` llega alineado con `por_dia`; el día con extras suma 10,5 h y 2 son extra; el día normal trae 0 |
| 2 | En el HTML hay **una** casilla partida, con el corte al **81,0 %**, el verde abajo y el azul arriba |
| 3 | La leyenda nombra el azul con el color del documento, y el párrafo lo explica |
| 4 | **En el PDF rasterizado, azul DENTRO de la fila** y en la proporción que toca |

La medida del bloque 4, que es la que importa:

```
banda y=501..566: verde 4085 · azul 403     <- la fila del mapa
banda y=605..634: verde 759  · azul 0       <- la leyenda, primera línea
banda y=660..689: verde 0    · azul 759     <- la leyenda, segunda línea
PASA | el azul es el 9.9 % del verde (se espera ~10 %: 0,19 casillas contra 1,81)
```

Dos casillas de día trabajado, una partida al 81 %: el azul es 0,19 de casilla
contra 1,81 de verde. **9,9 %.**

### Las capturas

- `h84_fila.png` — la fila ampliada: el día 8 verde entero, el **día 9 con su
  franja azul arriba**, y la leyenda con «horas extra» sin partir.
- `h84_p2.png` — la página completa.

Las que ya existían —`h82_estados`, `h83_pantallas`, `h83b_informe`,
`h52_informe`, `h53_h54_documento`— pasan, y el frontend compila.

---

## 6. Lo que queda

- **H8.5** — el borrado del periodo (H-D88, H-D89).
- H8.6 — regresión, retirar los alias de H-D91, estrechar el CHECK a cinco,
  regenerar `d1_cifras.py`, las dos suites del laboratorio que no corren, y
  cierre.

Pendiente de **tu validación visual** (regla 9).
