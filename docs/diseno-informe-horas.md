# El diseño del informe de horas — valores medidos, no interpretados

> **ETAPA D1, SUB-PASO D1.1 (D-D1).** Commit base: `f5bf053` · 23 de septiembre de 2026.
>
> Este documento **no opina**. Todos los valores que siguen están **leídos del
> HTML de referencia** que Fredy aprobó —`docs/reporte horas/informe-ocupacion-agosto-2026 (1).html`—
> y comparados contra lo que hoy genera Kinetix
> —`docs/reporte horas/informe-horas-2026-09-fredy-gabriel-bonilla-becerra (2).html`,
> producido por `backend/app/services/horas/informe.py`—.
>
> **Es la fuente. A partir de aquí nadie vuelve a «interpretar» la referencia:
> se copia esta tabla.** Si un valor no está aquí, se mide y se añade aquí antes
> de usarlo.

---

## 0. Por qué los dos informes no se parecen

La causa no es de gusto, es estructural y se puede señalar con el dedo:

**El informe de Kinetix está maquetado entero en `pt` y `mm`.** `_BASE_CSS`
—que comparten la pantalla y el papel— dice `h1{font-size:26pt}`,
`h2{font-size:13pt}`, `td{font-size:9.5pt}`, `padding:1.8mm 2mm`. Eso es una
hoja de estilos de **impresión**, y la pantalla la hereda entera: `_WEB_CSS`
solo añade el fondo, la caja `.hoja`, la barra de controles y el orden de las
tablas. No toca ni un tamaño de letra.

La referencia es lo contrario: es un diseño **de pantalla**, en `px`, con su
propia regla `@media print` de nueve líneas al final.

De ahí salen las tres diferencias que se ven de lejos:

| Se ve | Porque |
|---|---|
| Todo apretado | `td{padding:1.8mm 2mm}` = 6,8 × 7,6 px. La referencia usa `13px 14px` |
| Las cifras del resumen no destacan | `.ind-val{font-size:17pt}` = 22,7 px, y todas en el mismo navy. La referencia: **32 px**, en Exo 2 de peso 800, **cada una de su color** |
| El documento no explica nada | La referencia lleva **un párrafo bajo cada título** (D-D4). Kinetix va del título a la tabla |

**Consecuencia para D1.2 y D1.3:** la rama de pantalla necesita su propia
tipografía y sus propios espaciados en `px`, encima del `_BASE_CSS` de
impresión. No basta con retocar valores sueltos: hoy la pantalla no tiene
ninguno propio.

---

## 1. Colores

### 1.1 La paleta de la referencia (literal, de su bloque `:root`)

| Variable | Hex | Dónde se usa |
|---|---|---|
| `--dark` | `#060B29` | Fondo de la portada a sangre y del pie |
| `--navy` | `#03287D` | Títulos de sección, cifras de indicador, borde superior de la fila de totales |
| `--azul` | `#0032A7` | Primer tramo de la banda, barras «facturable», foco de los campos |
| `--naranja` | `#FCA311` | Segundo tramo de la banda, barras «interno», línea de jornada, foco visible |
| `--amarillo` | `#FFC440` | Tercer tramo de la banda, **el período dentro del título** (`h1 em`), la sílaba `SA` de la marca |
| `--bg` | `#F2F5FA` | Fondo de la página |
| `--surface` | `#FFFFFF` | Fondo de tarjetas, gráficas y tablas |
| `--line` | `#DCE3EF` | Todos los bordes de caja |
| `--ink` | `#0E1730` | Texto principal |
| `--muted` | `#5C6B8A` | Rótulos, textos de apoyo, párrafos de sección, cabeceras de tabla |

Colores de serie (los que llevan significado, no decoración):

| Variable | Hex | Significado |
|---|---|---|
| `--facturable` | `#0032A7` | Hora cargada a cuenta de cliente |
| `--interno` | `#FCA311` | Hora interna |
| `--sinreg` | `#8E44AD` | Esfuerzo estimado sin registro |
| `--novedad` | `#94A3B8` | Novedades y vacaciones |

Grises de segundo orden, medidos uno a uno:

| Hex | Dónde |
|---|---|
| `#F7F9FD` | Fondo de `thead`, de la fila de totales, de la nota al pie de tarjeta y de la barra de filtros |
| `#EDF1F8` | Separador entre filas de `tbody`, rejilla de las gráficas, fondo del selector segmentado |
| `#E4EAF5` | Canal vacío de la barra en celda, franja de día no laboral |
| `#9AA7C0` | Rótulos de eje dentro del SVG |
| `#8497C0` | Rótulos de la portada (`dt`) y texto del pie |
| `#9FB0D4` | «Centro de Excelencia · Performance» sobre el fondo oscuro |
| `#1E2A4E` | Línea que separa el título de los datos, dentro de la portada |
| `#33406B` | Separador vertical junto a la marca |

### 1.2 Lo que usa Kinetix hoy

| Hex | Dónde | Equivalente en la referencia |
|---|---|---|
| `#0a1628` | Navy de todo: `h1`, `h2`, banda, barra de controles, cuadro numerado | Se reparte entre `--dark` `#060B29` y `--navy` `#03287D` |
| `#f5a623` | Naranja de todo: subrayado de `h2`, banda, botones, período | `--naranja` `#FCA311` y `--amarillo` `#FFC440` |
| `#4f46e5` | Relleno de `.barra` (indigo SQA) | No existe: la referencia colorea la barra **por significado** |
| `#1f2937` · `#374151` · `#4b5563` · `#6b7280` · `#9ca3af` | Escala de grises del texto | `--ink` `#0E1730` y `--muted` `#5C6B8A` (**dos**, no cinco) |
| `#e5e7eb` · `#d1d5db` · `#f3f4f6` · `#f9fafb` | Bordes y fondos | `--line` `#DCE3EF`, `#EDF1F8`, `#F7F9FD` |

**Los colores de estado de Kinetix no se tocan** y no tienen equivalente en la
referencia, porque la referencia no tiene esas secciones: `.pill.ojo`
(`#fef3c7`/`#92400e`), `.pill.mal` (`#fee2e2`/`#991b1b`), y los cinco del mapa
del mes (`#dcfce7` trabajado, `#fef3c7` incompleto, `#e0e7ff` festivo,
`#f3e8ff` ausencia, `#f3f4f6` fin de semana). Son semáforos ya aprobados.

#### Las cinco píldoras del estado del proyecto (ETAPA H8, H-D103)

La sección 6 del informe pasa a tener **una sola** columna de estado, la última,
y con color (H-D102). Estos son sus cinco tonos, **tomados de la paleta que ya
está en este documento** salvo uno, que se señala:

| Estado | Fondo | Texto | De dónde sale |
|---|---|---|---|
| **Pendiente** | `#f3f4f6` | `#4b5563` | Es `.pill.bien`, la píldora neutra que ya existe |
| **En ejecución** | `#bfdbfe` | `#03287D` | El azul de las horas extra del mapa (H-D85) sobre `--navy` de la referencia |
| **Detenido** | `#fef3c7` | `#92400e` | Es `.pill.ojo`, sin cambio |
| **No viable** | `#e5e7eb` | `#991b1b` | Gris de §1.2 con la tinta roja de `.pill.mal` |
| **Finalizado** | `#dcfce7` | `#166534` | El verde «trabajado» del mapa · **el texto es un tono NUEVO** |

**«No viable» es rojo apagado, no rojo de alarma**, y por eso es tinta roja
sobre gris y no el bloque `#fee2e2` de `.pill.mal`. Dos razones: un proyecto que
no se va a hacer no es una alarma que haya que atender, y `.pill.mal` **sigue
significando «desfase»** en la sección 8 del mismo documento. Dos cosas distintas
con la misma píldora en el mismo informe se leerían como la misma.

> **El único tono nuevo de H8 es `#166534`**, el verde oscuro del texto de
> «Finalizado». Hacía falta porque el fondo `#dcfce7` es demasiado claro para
> llevar texto de su propio color, y dejarlo en tinta negra habría hecho de
> «Finalizado» la única píldora sin color de letra. **Aprobado por Fredy el 23
> de septiembre de 2026.**

**El tinte de fila se retira** (aprobado por Fredy). La sección 6 teñía el fondo
de la fila cuando el proyecto iba desfasado (`tr.mal td{background:#fef2f2}`) o
por agotarse (`tr.ojo`). Ese tinte salía del **consumo**, que es lo que H-D102
saca de la tabla, y además una fila roja con una píldora verde de «Finalizado»
al final se contradice a la vista. El aviso lo da «Restantes».

**El consumo sale de la tabla** (H-D102): ninguna píldora `bien`/`ojo`/`mal` en
la sección 6. Las que quedan en el informe son las de la sección 8 —«extra» y
«desfase»— y no cambian.

**Y «Restantes» en negativo se pinta en rojo y en negrita** (`#991b1b`, la tinta
que ya existe), que es lo que deja ver un proyecto desfasado ahora que su columna
no está. **Solo en negativo**: un proyecto que va sobrado no es un aviso.
H-D106, aprobado por Fredy.

#### El azul de las horas extra (ETAPA H8, H-D85)

El sexto color del mapa, y el único que se añade después de D1: **`#bfdbfe`**,
aprobado por Fredy el 23 de septiembre de 2026.

| Parte de la casilla | Color | Qué es |
|---|---|---|
| Abajo | `#dcfce7` | Las horas **ordinarias**. Es el verde de «trabajado», sin cambio |
| Arriba | `#bfdbfe` | Las horas **extra** |

La casilla se parte **en proporción a las horas de cada tipo**, no por la mitad:
8,5 ordinarias y 2 extra dejan el azul ocupando 2 / 10,5 de la altura.

**Por qué `#bfdbfe` y no cualquier azul:** `#e0e7ff` ya es «festivo». Un azul
más claro que ese se confundiría con él en una tabla de 31 columnas donde cada
casilla mide tres milímetros. `#bfdbfe` es netamente más saturado y se distingue
de un vistazo, que es para lo único que sirve el mapa.

**Un día sin extras no cambia**: sale verde entero, como hasta ahora. El color
nuevo solo aparece donde hay horas extra, y la leyenda lo nombra igual que a los
otros cinco.

> **Medido en H8.4: WeasyPrint 61.2 SÍ honra el `linear-gradient`** de corte
> duro, y no hizo falta recurrir a dos rectángulos. **Pero solo con la sintaxis
> clásica** —el mismo porcentaje repetido en los dos colores—:
>
> ```css
> /* funciona */   linear-gradient(to top,#dcfce7 81%,#bfdbfe 81%)
> /* NO funciona */ linear-gradient(to top,#dcfce7 0 81%,#bfdbfe 81% 100%)
> ```
>
> La segunda es la forma de **doble posición** de CSS Images Level 4.
> WeasyPrint la descarta entera **sin avisar**, y la casilla se queda con el
> fondo de su clase: verde y sin partir, con aspecto de estar bien. Se descubrió
> rasterizando el PDF y contando píxeles **dentro de la fila**; medido aparte,
> una prueba al 81 % da 21.714 píxeles verdes contra 5.313 azules.
>
> Vale para cualquier gradiente que este producto mande a papel.

---

## 2. Tipografía

### 2.1 Las dos familias de la referencia

```
--serif: 'Exo 2', system-ui, sans-serif      /* titulares y cifras */
--sans:  'Montserrat', system-ui, -apple-system, sans-serif   /* todo lo demás */
```

Pesos que carga: **Exo 2** en 600 y 800; **Montserrat** en 300, 400, 500, 600 y 700.
Cuerpo del documento: `font-weight:400`, `line-height:1.55`, con
`-webkit-font-smoothing:antialiased`.

> ⚠ **Las carga de `fonts.googleapis.com`.** Kinetix no puede hacer eso sin
> decidirlo antes: ver §7, decisión abierta **A**.

### 2.2 Tabla de elementos (valores literales de la referencia)

| Elemento | Familia | Peso | Tamaño | Interlínea / espaciado | Color |
|---|---|---|---|---|---|
| Marca «SQA**SA**» | Exo 2 | 800 | 26 px | `letter-spacing:.03em` | `#fff`, `SA` en `--amarillo` |
| «Centro de Excelencia · Performance» | Montserrat | 500 | 12,5 px | borde izq. 1 px `#33406B`, `padding-left:14px` | `#9FB0D4` |
| **Título `h1`** | Exo 2 | **800** | `clamp(30px, 4.4vw, 48px)` | `line-height:1.05`, `letter-spacing:-.015em`, `max-width:20ch` | `#fff`, el período en `--amarillo` |
| Rótulo de portada `dt` | Montserrat | 500 | 11,5 px | `margin-bottom:3px` | `#8497C0` |
| Valor de portada `dd` | Montserrat | 600 | 14 px | — | `#fff` |
| **Título de sección `h2`** | Exo 2 | **600** | **22 px** | `letter-spacing:-.01em`, `margin-bottom:6px` | `--navy` |
| **Párrafo de sección `p`** | Montserrat | 400 | **13,5 px** | `line-height:1.6`, bloque a `max-width:76ch` | `--muted` |
| Rótulo de indicador `.k-l` | Montserrat | 600 | 11,5 px | `line-height:1.35`, `min-height:30px`, `margin-bottom:9px` | `--muted` |
| **Cifra de indicador `.k-v`** | Exo 2 | **800** | **32 px** | `line-height:1`, `letter-spacing:-.02em` | `--navy` / por variante |
| Unidad dentro de la cifra `small` | Montserrat | 600 | 13 px | `letter-spacing:0` | `--muted` |
| Pie de indicador `.k-s` | Montserrat | 400 | 11,5 px | `margin-top:8px` | `--muted` |
| Cabecera de tabla `thead th` | Montserrat | 600 | 11,5 px | `white-space:nowrap`, **sin mayúsculas** | `--muted` |
| Celda `tbody td` | Montserrat | 400 | 13,5 px | `font-variant-numeric:tabular-nums` | `--ink` |
| Primera columna `td:first-child` | Montserrat | 600 | 13,5 px | alineada a la izquierda | `--ink` |
| Fila de totales `tr.total td` | Montserrat | 700 | 13,5 px | — | `--navy` |
| Nota al pie de tarjeta `.note` | Montserrat | 400 | 12 px | `line-height:1.6` | `--muted`, los `<b>` en `--ink` peso 600 |
| Leyenda `.legend span` | Montserrat | 500 | 12 px | — | `--muted` |
| Texto dentro del SVG | Montserrat | según marca | 9 – 12,5 px | ver §5 | ver §5 |
| Pie de página | Montserrat | 400 | 12 px | — | `#8497C0`, los `<strong>` en `#fff` |

### 2.3 Lo que usa Kinetix hoy

Una sola familia: `'Segoe UI', system-ui, -apple-system, sans-serif`. Sin
titular diferenciado. Y todo en `pt`:

| Elemento | Hoy | Equivale a | La referencia |
|---|---|---|---|
| `h1` | 26 pt | 34,7 px | 30 – 48 px, Exo 2 800 |
| Período `.titulo .sub` | 16 pt peso 700 | 21,3 px | va **dentro** del `h1`, 30 – 48 px |
| `h2` | 13 pt | 17,3 px | **22 px**, Exo 2 600, **sin subrayado naranja y sin cuadro numerado** |
| `.ind-val` | 17 pt | 22,7 px | **32 px**, Exo 2 800, coloreada |
| `.ind-et` | 8 pt **mayúsculas** | 10,7 px | 11,5 px, **caja normal** |
| `th` | 8,5 pt **mayúsculas** | 11,3 px | 11,5 px, **caja normal** |
| `td` | 9,5 pt | 12,7 px | **13,5 px** |
| `.nota` | 9 pt | 12 px | 12 px ✓ |

---

## 3. Geometría y espaciado

| Concepto | Referencia | Kinetix hoy |
|---|---|---|
| Ancho del contenido | `max-width:1240px`, `padding:0 24px` | `.hoja` `max-width:1180px`, `padding:28px 34px` |
| Separación entre secciones | `section{padding:46px 0 6px}` | `.seccion{margin-bottom:26px}` |
| Ancho del bloque de texto de sección | `max-width:76ch` | no existe |
| Radio de tarjeta | **10 px** | no hay tarjeta |
| Borde de tarjeta | `1px solid #DCE3EF` | `.indicadores td.ind` `.5pt solid #e5e7eb` |
| Relleno de tarjeta de gráfica | `22px 24px` | — |
| Relleno de indicador | `20px` | `3mm` (11,3 px) |
| Separación entre indicadores | `gap:2px` sobre fondo `--line` (línea de 2 px, no borde) | bordes de `.5pt` |
| Rejilla de indicadores | `repeat(auto-fit, minmax(186px, 1fr))` | tabla de **3 columnas × 2 filas** fijas |
| Celda de tabla | `13px 14px` (`thead`: `12px 14px`) | `1.8mm 2mm` = 6,8 × 7,6 px |
| Separador de fila | `1px solid #EDF1F8`; **la última fila sin borde** | `.5pt solid #e5e7eb` en todas |
| Fila de totales | fondo `#F7F9FD` + **borde superior 2 px `--navy`** | no existe |
| Radio de campo de filtro | 7 px | 8 px |
| Radio de botón | 7 px | 8 px |
| Banda bajo la portada | **5 px** de alto, a sangre | `2.2mm` = 8,3 px |
| Reparto de la banda | azul `0 → 62 %` · naranja `62 → 88 %` · amarillo `88 → 100 %` | naranja `0 → 38 %` · navy el resto |
| Pie de página | `margin-top:60px`, `padding:28px 0`, fondo `--dark` | no existe |

### 3.1 La portada, pieza a pieza (D-D2)

```
header  fondo --dark #060B29, padding 38px arriba, 0 abajo, a sangre
│
├─ .brandline       margin-bottom 26px · flex, gap 14px, alineado a la base
│   ├─ .mark        «SQASA» Exo 2 800 26px, «SA» en --amarillo
│   └─ .unit        «Centro de Excelencia · Performance» 12,5px #9FB0D4,
│                   con línea vertical 1px #33406B a 14px
│
├─ h1               Exo 2 800, clamp(30px,4.4vw,48px), max-width 20ch,
│                   margin-bottom 16px · EL PERÍODO VA DENTRO, en --amarillo
│
├─ dl.meta          border-top 1px #1E2A4E · margin-top 26px
│                   padding 22px arriba / 34px abajo · flex, gap 44px
│   └─ cada bloque  dt 11,5px #8497C0 (+3px) · dd 14px peso 600 #fff
│
└─ header::after    banda de 5px a sangre, en el borde inferior
```

Los cuatro bloques, en este orden: **Dirigido a · Período · Equipo ·
Capacidad base**. Es el mismo contenido que ya tiene Kinetix (H-D73) y que
D-D8 manda conservar; cambia dónde vive y cómo se ve, no qué dice.

### 3.2 El indicador, pieza a pieza (D-D3)

```
.kpis    rejilla auto-fit minmax(186px,1fr) · gap 2px · fondo --line
         borde 1px --line · radio 10px · overflow hidden
         margin-top:-18px  (se monta sobre el aire de la sección)
│
└─ .kpi  fondo blanco · padding 20px
    ├─ .k-l   rótulo   11,5px peso 600 --muted · min-height 30px (alinea las cifras)
    ├─ .k-v   CIFRA    Exo 2 800 32px · line-height 1 · con <small> para la unidad
    └─ .k-s   pie      11,5px --muted · margin-top 8px · el desglose
```

Las variantes de color de la cifra, literales: por defecto `--navy`;
`.kpi.bill` → `--azul`; `.kpi.hot` → `--naranja`; `.kpi.est` → `--sinreg`.

El `min-height:30px` del rótulo no es decoración: **es lo que deja las cinco
cifras a la misma altura** aunque unos rótulos ocupen una línea y otros dos.

---

## 4. Las tablas (D-D7)

| Detalle | Valor |
|---|---|
| Caja | dentro de `.card`: blanco, borde 1 px `--line`, radio 10 px, `overflow:hidden` |
| Ancho | 100 %, `border-collapse:collapse`, base 13,5 px |
| `thead th` | fondo `#F7F9FD`, 11,5 px, peso 600, `--muted`, `padding:12px 14px`, borde inferior 1 px `--line` |
| Alineación | **todo a la derecha salvo la primera columna**, que va a la izquierda |
| `tbody td` | `padding:13px 14px`, borde inferior 1 px `#EDF1F8`, `tabular-nums` |
| Primera columna | peso 600, a la izquierda |
| Última fila | **sin borde inferior** |
| Fila de totales | fondo `#F7F9FD`, peso 700, `--navy`, **borde superior 2 px `--navy`** |
| Nota al pie | dentro de la tarjeta, fondo `#F7F9FD`, borde superior 1 px `--line`, `padding:13px 16px` |

**La barra dentro de una celda** (`.bar-mini`) — el equivalente de la `.barra`
que Kinetix ya tiene:

| Detalle | Referencia | Kinetix hoy |
|---|---|---|
| Ancho | **48 px fijo** | `min-width:25mm` (94 px), elástico |
| Alto | **6 px** | `3mm` = 11,3 px |
| Radio | 3 px | `2mm` = 7,6 px |
| Canal | `#E4EAF5` | `#e5e7eb` |
| Relleno | `--azul`; `.over` → `--naranja`; `.est` → `--sinreg` | siempre `#4f46e5` |
| Colocación | `inline-flex` con el porcentaje, `gap:8px`, alineado a la derecha | columna propia, sin cifra al lado |

---

## 5. Las gráficas de barras (D-D6)

Las cuatro son **SVG dibujado a mano con un `viewBox`**, sin biblioteca. El
texto va en `Montserrat, sans-serif` y el color por defecto es `#5C6B8A`.

| Gráfica | `viewBox` | Canal izq. | Canal der. | Alto de barra | Separación | Radio |
|---|---|---|---|---|---|---|
| Composición por persona | `0 0 1080 H` | 178 | 8 | **30** | 16 | 2 |
| Cobertura por cliente | `0 0 1080 H` | 200 | 70 | **24** | 8 | 2 |
| En qué se fue el tiempo | `0 0 560 H` | 176 | 52 | **20** | 8 | 2 |
| Carga día a día (columnas) | `0 0 560 232` | 30 | 8 | ancho `PW/31`, hueco 3 px | — | 1,5 |

Reglas comunes, medidas:

- **Etiqueta de fila**: a `canal-12` px del borde, `text-anchor:end`, 11 – 12,5 px,
  color `#0E1730`, peso 500 – 600. Va **fuera** de la barra, a su izquierda.
- **El porcentaje va dentro de la barra, centrado, solo si cabe**: la condición
  literal es `w > 52` px. Entonces se pinta a 12 px, peso 700, en blanco.
- **El total va fuera**, a la derecha de la barra: `x + 8…9` px, 10,5 – 11,5 px,
  peso 700, `#0E1730`.
- **Rejilla**: líneas verticales `#EDF1F8` con su rótulo arriba a 10 px `#9AA7C0`.
  El paso se elige solo: 40 h si el máximo pasa de 120, 20 h si pasa de 60, 10 h si no.
- **Ancho mínimo de barra `1.5` px**, para que un valor pequeño no desaparezca.
- **Línea de jornada de referencia**: `--naranja`, `stroke-width:1.3`,
  `stroke-dasharray:"4 3"`, con su rótulo a 9,5 px en naranja y peso 700.
- **Día no laboral**: rectángulo `#E4EAF5` a `opacity:.55` de fondo de columna.
- Cada rectángulo lleva un `<title>` dentro: es el texto que sale al posar el
  ratón, y es lo que hace la gráfica legible sin tener que etiquetarlo todo.

**La leyenda va debajo** (D-D6), separada por `border-top:1px solid #EDF1F8`,
`padding-top:15px`, `margin-top:16px`, en `flex` con `gap:18px`. Cada entrada:
un cuadro `.sw` de **11 × 11 px** con radio 2, `gap:7px`, y el texto a 12 px
peso 500 en `--muted`.

---

## 6. Los párrafos de sección (D-D4) — lo que más separa a los dos informes

La referencia pone, **bajo cada título y antes de la tabla**, un párrafo de una
a tres líneas que dice *qué se está mirando y por qué importa*. Son suyos,
literales, y sirven de patrón de tono:

| Sección | Su párrafo |
|---|---|
| Ocupación frente a la capacidad | «Agosto tuvo 19 días hábiles descontando el 7 y el 17: 152 horas por analista. Los tres cerraron exactamente 160 horas ordinarias, que es el techo del registro y no la medida del esfuerzo.» |
| Cuánto llegó a una cuenta de cliente | «El dato que ordena todo el informe. Una hora facturable está cargada a una cuenta abierta; una hora interna es trabajo real y medido que no tiene dónde cargarse porque el cliente todavía no tiene código.» |
| Cobertura por cliente | «Tres estados por cuenta: horas cargadas al cliente, horas reales cargadas a interno y sesiones atendidas que nunca entraron al timesheet.» |
| En qué se fue el tiempo | «Clasificación por actividad principal de cada registro.» |
| Carga día a día | «La línea punteada marca la jornada de referencia donde el registro se satura.» |
| Detalle de registros | «N registros del mes. Filtra, ordena por cualquier columna o descarga el conjunto filtrado.» |

Lo que se lee de ellos, y que hay que respetar al escribir los ocho de Kinetix
en D1.3:

1. **Longitud: de una a tres líneas.** Ninguno llega a cuatro.
2. **Meten cifras del propio informe** («19 días hábiles», «152 horas»,
   «N registros»). No son texto muerto: se interpolan.
3. **Definen el término cuando hace falta.** El de facturación no describe la
   tabla: explica qué es una hora facturable y qué es una interna, que es lo
   que el lector no sabe.
4. **Avisan de lo que el dato NO dice.** «que es el techo del registro y no la
   medida del esfuerzo» vale más que toda la tabla que sigue.
5. **Sin jerga, sin markdown, en español llano.** Ninguno dice «hallazgo»,
   «se evidencia» ni «cabe destacar» (regla 15).

---

## 7. Las tres decisiones, resueltas

Tres cosas de la referencia no se podían copiar tal cual. **Fredy las decidió el
23 de septiembre de 2026**, con condiciones. Aquí queda lo que se decidió y lo
que se hizo; el planteamiento original se conserva debajo de cada una.

| | Decisión | Condiciones |
|---|---|---|
| **A** | **Incrustar las dos familias** en el documento | Licencia SIL OFL al lado de los `.woff2`; solo los pesos que se usan; subconjunto latino; declarar el peso; **tope de 400 KB**; base64 **sin ninguna referencia a la red**; comprobar que WeasyPrint las usa de verdad |
| **B** | **Adoptar la paleta de la referencia**, que **sustituye a la de H-D73** (provisional) | Aplicarla al informe entero para que no queden dos paletas; dejar los valores aquí; **el logo no se toca** |
| **C** | **Añadir también las gráficas SVG** | Solo cifras que el informe **ya calcula**; las tablas se quedan y la gráfica va **encima**, no en su lugar; SVG del servidor, sin biblioteca y **sin JavaScript**; leyenda siempre y **el color nunca es lo único que distingue**; comprobar en el PDF que sale, que no se parte y que nada baja de 8 pt; empezar por **facturable frente a interno por persona** y **horas por actividad** |

### A resuelta — qué se incrustó y cuánto pesa

Las dos familias viven en **`backend/app/assets/fuentes/`** con sus dos
licencias (`OFL-Exo2.txt`, `OFL-Montserrat.txt`). Google ya solo sirve estas
familias como **fuente variable**; de ahí se cortaron **instancias estáticas por
peso** con `fontTools`, para que WeasyPrint elija el peso por `@font-face` y no
dependa de saber manejar un eje variable.

| Archivo | Bytes |
|---|---|
| `Exo2-600.woff2` | 17.084 |
| `Exo2-800.woff2` | 17.076 |
| `Montserrat-400.woff2` | 18.492 |
| `Montserrat-500.woff2` | 18.604 |
| `Montserrat-600.woff2` | 18.492 |
| `Montserrat-700.woff2` | 18.612 |
| **En disco** | **108.360** |
| **Ya en base64, dentro del documento** | **144.480** |

De **400 KB de tope, se usan 144**. No hace falta recortar nada. Para
referencia: el subconjunto latino cubre tildes, eñe, diéresis y los signos de
apertura, que es todo lo que el informe escribe.

El HTML pasa de **53 KB a 201 KB** por esto. Las incrusta
`services/horas/fuentes.py`, una sola vez por proceso.

**Comprobado mirando** (no leyendo): se imprimió con WeasyPrint una hoja con los
seis pesos y una línea de control en una familia inexistente. Los seis salen
distintos entre sí y la línea de control cae en una serif sustituta, que es la
prueba de que los otros seis **no** están cayendo en la sustituta.

### B resuelta — la paleta vive en un sitio

Los valores de §1.1 están ahora en un bloque `:root` de `_BASE_CSS`, como
variables CSS, y el resto de la hoja los usa con `var()`. No queda ni un
`#0a1628` ni un `#f5a623` en el informe de horas: lo comprueba
`pruebas_e2e/diseno/d1_diseno.py`. Los `#0a1628` que siguen en el repositorio
son del **módulo de análisis** (`export_pdf.py`, `export_html.py`), que tiene su
propia identidad y no entra en esta etapa.

**El logo no se tocó.** Tiene fondo propio sólido `#111D52` y sin
transparencia, así que sobre el `#060B29` de la portada se ve su placa. Es una
consecuencia visible de la decisión B, no un descuido.

### C resuelta — las dos gráficas, y por qué no copian la geometría de §5

Las dibuja `services/horas/graficas.py`: **SVG del servidor, sin biblioteca y
sin JavaScript**, para que el HTML sin red y el PDF enseñen lo mismo. La
referencia dibuja con JavaScript en el navegador, y por eso su código no sirve
aquí; lo que sí se copia es su **forma**: barra horizontal, nombre fuera a la
izquierda, cifra dentro del tramo si cabe, total fuera a la derecha, leyenda
debajo separada por una línea.

**La geometría de §5 no se puede copiar en unidades.** El SVG se estira hasta el
ancho de su caja, así que el mismo `viewBox` da tamaños de letra distintos en
cada rama. Con el `viewBox` de 1080 de la referencia, una letra de 12 unidades
son 13 px en pantalla y **5,9 pt** en el PDF: por debajo del mínimo de 8 pt de
la regla 17.

La solución es **una geometría medida en múltiplos de un tamaño base**, y un
base distinto por rama. La forma es idéntica; solo cambia lo gruesa que sale:

| | `viewBox` | base | En pantalla | En el PDF |
|---|---|---|---|---|
| Pantalla | `0 0 1000 H` | **12** | ~13 px | — |
| Papel | `0 0 1000 H` | **17** | — | **~9 pt** |

Todo lo demás se deriva del base: altura de barra `×2,1`, hueco `×0,75`, canal
derecho `×5,5`, nombre `×1,04`, cifras `×0,95`. El canal izquierdo se ajusta al
nombre más largo, entre `×9` y `×23`.

### ⚠ WeasyPrint recorta los descendentes con `text-anchor="end"`

**Comprobado**, no supuesto: la misma frase impresa dos veces en la misma línea,
una anclada a `start` y otra a `end`. La de `start` sale entera; la de `end`
pierde las colas de la «y», la «g» y la «p». Es independiente de la familia, del
peso y de `dominant-baseline`.

Por eso **no se emite `text-anchor` en ninguna parte**: la posición se calcula
midiendo el texto con las métricas de la fuente que se está incrustando
(`fuentes.ancho_texto`, con `fontTools`). Sale exacto, y el recorte de un nombre
largo pasa a ser el justo en vez de una estimación.

Vale para **cualquier SVG que este producto mande a WeasyPrint**, no solo para
este informe.

---

## 7 bis. El planteamiento original de las tres decisiones

### A. Las letras

La referencia carga **Exo 2** y **Montserrat** desde `fonts.googleapis.com`.
El informe de Kinetix no puede depender de eso: H-D54 fijó que el documento
funcione **sin red** (por eso el logo va embebido en base64), y el PDF lo
imprime WeasyPrint, que no va a buscar una fuente a internet.

Sin una de las dos familias, **la portada y las cifras pierden justo lo que las
hace destacar**: el titular de 48 px y la cifra de 32 px son Exo 2 de peso 800.

| Camino | Qué cuesta |
|---|---|
| **1. Incrustar las dos familias** en el HTML como `woff2` en base64 | El documento se ve igual siempre, con red y sin ella, en pantalla y en papel. Añade peso al archivo: hay que medirlo, pero con los pesos justos (Exo 2 en 600 y 800; Montserrat en 400, 500, 600, 700) son del orden de varios cientos de KB. Hay que meter los `.woff2` en el repositorio |
| **2. Enlazar a Google Fonts solo en la rama de pantalla**, y pila del sistema en el PDF | Archivo ligero. Pero el HTML descargado **deja de verse igual sin red**, que es lo que H-D54 vino a evitar, y el PDF sale con otra letra que la pantalla |
| **3. No usar esas familias**: aproximar con la pila del sistema y jugar solo con peso y tamaño | Cuesta cero y no rompe nada. Se parecerá en estructura, aire y color, **pero el titular y las cifras no tendrán el carácter de la referencia** |

### B. La paleta de la portada

La portada de Kinetix usa `#0a1628` y `#f5a623`, **aprobados en H-D73**. La
referencia usa `#060B29`, `#03287D`, `#FCA311` y `#FFC440`. D-D1 dice que la
referencia manda, así que lo natural es adoptar sus cuatro. Antes de hacerlo,
dos avisos concretos:

- **El logo es un PNG con fondo propio.** Sobre `#0a1628` se funde; sobre
  `#060B29` puede verse el recuadro. Se comprueba mirando, en D1.2.
- Cambiar el naranja de `#f5a623` a `#FCA311` toca **también** los botones, el
  subrayado y los semáforos de la pantalla de horas, no solo el informe.

### C. Las gráficas

La referencia trae **cuatro gráficas de barras en SVG**. El informe de Kinetix
hoy **no tiene ninguna**: tiene tablas y la barra de celda de `_sec_reparto`
(secciones «Cobertura por cliente» y «En qué se fue el tiempo»).

D-D6 habla de «barras», y cabe leerlo de dos maneras:

- **Estrecha** — restilar la `.barra` que ya existe con los valores de §4
  (48 × 6 px, coloreada por significado, con el porcentaje al lado). Es
  presentación pura y no añade nada al informe.
- **Ancha** — añadir además las gráficas de §5 donde el dato ya está
  calculado: composición facturable/no facturable por persona, y horas por
  actividad.

La segunda **no cambia ninguna cifra** —las pinta, no las calcula—, pero sí
**añade contenido**, y D-D8 dice que el contenido no se toca. Por eso se
pregunta en vez de decidirlo.

---

## 8. El plan de verificación (D-D10)

Ya está en pie y probado con los dos informes de hoy:

```
backend/pruebas_e2e/diseno/rasterizar.py <entrada.html> <salida.png> [--ancho=1280] [--alto=N]
```

Corre dentro de `jmeter_backend` con Playwright (regla 36: versionado, no vive
en `/tmp`). Toma la página entera por defecto, o recorta a `--alto` para
comparar solo la portada. `device_scale_factor=2`, para que el texto pequeño se
pueda leer en la comparación.

En cada sub-paso: se genera el informe, se rasteriza, se pone al lado de la
captura equivalente de la referencia y **se adjuntan las dos**. Nada se declara
terminado leyendo el código.

---

## 8 bis. La portada en el PDF (D1.4)

`@page :first { margin: 0 }` es la única forma fiable de que un fondo de color
llegue al borde del papel, y es la que ya usa el informe de análisis. Deja la
**primera hoja entera** sin márgenes, así que la portada tiene que ocuparla
toda.

| Medida | Valor | Por qué |
|---|---|---|
| `.portada-fondo` | `height:289mm`, `padding:22mm 16mm 0` | Ocupa la hoja; el logo arriba |
| `.banda` | `7mm` | 289 + 7 = **296 de 297 mm**. El milímetro que sobra evita que un redondeo empuje la banda a la hoja siguiente y salga una página en blanco |
| `.titulo` | `padding-top:78mm`, `h1` a **40 pt** | En una hoja entera el título respira |
| `.cabecera` | `page-break-after:always` | El cuerpo empieza limpio en la hoja 2 |
| `@bottom-right` | `content:none` en `:first` | Sin márgenes no hay caja de margen, **pero el número de página se sigue dibujando** y cae sobre la banda |

---

## 9. Lo que no se toca (D-D8)

Las ocho secciones y su orden (`SECCIONES` en `informe.py`), las cifras, los
filtros del HTML, el CSV, y la portada con destinatario y capacidad base.
**Ni una cifra cambia.** En D1.5 se comprueba generando el informe antes y
después y comparando los números.

Y las reglas del PDF siguen mandando en su rama (D-D9, reglas 11 y 17): solo
tablas, `pt`/`mm`, sin `flex` ni `grid`, nada por debajo de 8 pt. Donde el
diseño de pantalla no se pueda reproducir en papel se adapta conservando la
jerarquía —cifra grande, color, aire— y se declara qué cambió y por qué.
