# N2.4 — Fondo claro sobre los criterios + logo del cliente

**Fecha:** 2026-08-15
**Commit:** `d7fde86` — *N2.4: quitar fondo claro de criterios + logo sin
filtros en portada*
**Push:** `github/backup-trabajo-local` (`af63405..d7fde86`). No quedaban pushes
pendientes: N2.2 y N2.3 se subieron en sus respectivas pasadas.
**`origin` NO se tocó.**
**Estado:** **DEFECTO 1 CORREGIDO Y VERIFICADO · DEFECTO 2 = FALSO POSITIVO
(medido). PENDIENTE VALIDACIÓN VISUAL DE FREDY.**

**Presupuesto:** ~20-40 líneas → **32 insertadas / 20 borradas, 3 archivos** ✔

---

## 1. Diagnóstico (antes de tocar nada)

### 1.1 El fragmento tal como se emitía

Generado con `build_pdf_html()` (logo recortado para que quepa en el reporte):

```html
<table class="cover-meta-grid"><tr>
    <td class="cover-zona-izq">
        <table class="cover-meta-inner">
            <tr>
                <td class="cover-meta-fila" style="width:52%">...EJECUCION...</td>
                <td class="cover-meta-fila">...DURACION...</td>
            </tr>
            <tr><td colspan="2" class="cover-meta-fila">
                <div class="cover-meta-label">CRITERIOS DE ACEPTACION</div>
                <div class="cover-meta-value">&lt; 2500 ms &middot; &gt; 99% disponibilidad</div>
            </td></tr>
            <tr><td colspan="2" class="cover-meta-fila">
                <div class="cover-meta-label">ARCHIVO</div>
                <div class="cover-meta-value" style="font-size:10.5pt">resultados.jtl</div>
            </td></tr>
        </table>
    </td>
    <td class="cover-zona-der">...CLIENTE / img / nombre...</td>
</tr></table>
```

**En el marcado no hay ningún `background`.** El fondo no venía del HTML.

### 1.2 La regla culpable

`backend/app/services/export/report_generator.py:682-684` (numeración previa al
fix), la regla genérica de zebra de las tablas del cuerpo del informe:

```css
tbody tr:nth-child(even) {
    background: #f8fafc;
}
```

La tabla anidada `.cover-meta-inner` genera un `<tbody>` implícito. Sus filas:

| Fila | Contenido | nth-child | ¿zebra? |
|---|---|---|---|
| 1 | EJECUCION + DURACION | impar | no |
| **2** | **CRITERIOS DE ACEPTACION** | **par** | **sí → `#f8fafc`** |
| 3 | ARCHIVO | impar | no |

Por eso el rectángulo claro caía **exactamente** sobre los criterios y sobre
nada más. Y explica un detalle que Fredy no llegó a ver: **sin criterios
definidos la fila 2 pasa a ser ARCHIVO**, así que el mismo defecto se habría
mudado a esa fila.

Dato importante para el fix: `#f8fafc` se pinta en el **`<tr>`**, no en el
`<td>`. Poner la celda transparente no habría servido de nada — el fondo de la
fila se sigue viendo por debajo. Hay que anular la regla **en la fila**.

### 1.3 El logo: medido, no supuesto

Búsqueda en las tres salidas: **no existe** `opacity`, `filter`,
`mix-blend-mode` ni `background-color` aplicado al `<img>` ni a ningún wrapper
suyo. El `<img>` se emite así, sin más:

```html
<img src="data:image/png;base64,..." alt="Logo del cliente"
     style="max-height:28mm;max-width:72mm;display:block;margin:3mm auto 2mm auto" />
```

`client_logo.py` tampoco transforma nada: hace `base64.b64encode(logo.data)`
sobre los bytes de la DB.

Comparación **píxel a píxel** entre el logo que sirve `GET /clients/{id}/logo` y
la imagen embebida en la página 1 del PDF (Pillow, solo píxeles opacos):

```
logo DB (GET /clients/../logo)   400x133  RGB medio=(194.1, 31.8, 39.4)  saturacion=219.1  alfa=131.4  opacos=27187
PDF pagina 1 imagen #0           400x133  RGB medio=(194.1, 31.8, 39.4)  saturacion=219.1  alfa=131.4  opacos=27187
```

**Idénticos en todo: dimensiones, RGB medio, saturación y número de píxeles
opacos.** El PDF incrusta el PNG tal cual, sin recomprimir ni desaturar.
Confirmado además por el `/ExtGState` de la página: no hay ningún estado de
transparencia aplicado a la imagen.

**Conclusión honesta del defecto 2: no hay nada que eliminar en el código.** Lo
que se percibe como «apagado» es contraste: ese logo es rojo (194,32,39) y en
la pantalla de Clientes se ve sobre blanco, mientras que en la portada va sobre
la tarjeta oscura. La misma tinta sobre fondo oscuro se lee menos vibrante, y
los bordes con antialias del PNG se funden con el navy. **No lo he "arreglado"
por mi cuenta porque cualquier arreglo real contradice tu propia
especificación** (la única forma de devolverle el brillo sería ponerle una
plancha blanca detrás, y el punto (2) dice que ningún elemento del bloque lleva
fondo blanco). Ver §5: te dejo las opciones.

---

## 2. El fix del defecto 1

```css
/* N2.4: el bloque de metadatos NO lleva zebra. La regla generica
   `tbody tr:nth-child(even)` (mas abajo en esta misma hoja) pintaba de #f8fafc
   la 2a fila de la tabla anidada — justo la de CRITERIOS DE ACEPTACION — y
   dejaba texto claro sobre fondo claro. El fondo va en el <tr>, asi que no
   basta con poner el <td> transparente: hay que anular la regla en la fila. */
.cover-meta-grid tr, .cover-meta-inner tr,
.cover-meta-grid td, .cover-meta-inner td {
    background: none !important;
}
```

`!important` porque `tbody tr:nth-child(even)` tiene mayor especificidad
(0,1,2) que `.cover-meta-inner tr` (0,1,1) y además está definida después. Está
acotado al bloque de la portada: **la zebra de las tablas del cuerpo del informe
no se toca**.

## 3. Especificación de estilo aplicada

| Elemento | Antes | Ahora |
|---|---|---|
| Fondo de filas/celdas del bloque | `#f8fafc` en la fila par | **transparente** (`background:none`) |
| Etiquetas (EJECUCION / DURACION / CRITERIOS / ARCHIVO / CLIENTE) | `rgba(255,255,255,0.5)` | **`#94a3b8`**, 7pt, `letter-spacing .5px`, todas iguales |
| Valores principales (fecha, duración, criterios, cliente) | `rgba(255,255,255,0.9)`, peso 600 | **`#ffffff`, peso 500** |
| Valores secundarios (hora inicio→fin, archivo) | `rgba(255,255,255,0.85)` / el archivo iba como principal | **`#cbd5e1`** |
| Separador vertical | `rgba(255,255,255,0.25)` | **`rgba(255,255,255,0.13)`** |

El nombre del archivo pasó de valor principal a secundario, que es lo que dice
la especificación. En las ramas HTML se añadió la clase `.meta-sec` /
`.plotly-meta-sec` para los secundarios, en vez del `opacity:.85` que se usaba
antes (una opacidad apaga el texto en lugar de darle color).

**El layout aprobado en N2.3 no se tocó:** EJECUCION+DURACION arriba, CRITERIOS
debajo, ARCHIVO debajo, CLIENTE a la derecha.

---

## 4. Validación por evidencia

### 4.1 El rectángulo claro, antes y después

No hay rasterizador en el contenedor (`pdftoppm`/`gs`/`pypdfium2` no están), así
que en vez de muestrear píxeles fui **al content stream del PDF**, que es la
fuente: el fondo blanco es una operación de relleno. Se recorre el stream
siguiendo el color de relleno (`rg`/`g`/`sc`) y se anotan los rectángulos
(`re … f`). Página 1 del PDF individual de Bancoomeva:

```
===== ANTES — rectangulos claros (RGB>=0.85) en la pagina 1 =====
color RGB                     x_mm  y_mm(desde arriba)   ancho    alto
(0.973,0.980,0.988)          44.0                57.3   180.1    16.7   <-- CRITERIOS
(1.000,1.000,1.000)          33.3                24.3   329.3   116.3   <-- tarjeta (alfa 0.08)
...
total rectangulos claros: 11   en la zona del bloque: 1

===== DESPUES =====
(1.000,1.000,1.000)          33.3                24.6   329.3   116.0   <-- tarjeta (alfa 0.08)
...
total rectangulos claros: 10   en la zona del bloque: 0
```

`(0.973, 0.980, 0.988)` es exactamente `#f8fafc` (248/250/252). El content
stream lleva una transformación de escala `0.75`, así que en milímetros reales
ese rectángulo medía **135 × 12.5 mm** — el ancho y el alto de la fila de
criterios. **Desapareció.**

El rectángulo blanco que queda es la tarjeta `.cover-info-box`, y **no es
opaco**: el `/ExtGState` de la página confirma `/a0.08` (relleno al 8%). También
aparece `/A0.13`, que es el nuevo hairline del separador. Es el fondo que tú
llamas «la tarjeta oscura»; no es una caja del bloque.

Comprobado también en la ejecución **sin criterios** (Editor IA): 0 rectángulos
de fila en el bloque — el defecto no se mudó a ARCHIVO.

### 4.2 Grep sobre el HTML de navegador

Fragmento `<div class="meta-block">…</div>` extraído del HTML generado:

```
HTML individual [con logo + con criterios]: apariciones de background/blanco = 0
HTML individual [sin logo + con criterios]: apariciones de background/blanco = 0
HTML individual [sin logo + SIN criterios]: apariciones de background/blanco = 0
HTML integrado:                             apariciones de background/blanco = 0
```

(patrón buscado: `background`, `#f8fafc`, `#fff`, `white`,
`rgba(255,255,255,.2-.9)`).

### 4.3 Colores de la spec en el CSS emitido

```
etiquetas #94a3b8:        OK
valores #fff peso 500:    OK
secundarios #cbd5e1:      OK
hairline 13%:             OK
```

### 4.4 Nada se rompió

```
[con logo + con criterios] 8 pags | spill=[] | proyecto x1 | CRITERIOS=True
[sin logo + con criterios] 9 pags | spill=[] | proyecto x1 | CRITERIOS=True
[sin logo + SIN criterios] 8 pags | spill=[] | proyecto x1 | CRITERIOS=False
PDF integrado: 18 pags | conclusiones en [14]
```

Individual 8 · integrado 18 (13 + 5) · sin páginas de desbordamiento · el
nombre del proyecto sigue apareciendo una sola vez.

---

## 5. Defecto 2: qué quieres que haga

La medición dice que el logo se pinta sin alterar. Si aun así lo ves apagado
respecto a la pantalla de Clientes, es el fondo oscuro. Opciones, **ninguna
aplicada** porque las tres tocan la spec que aprobaste:

1. **Dejarlo como está** — el logo mantiene su color real sobre la tarjeta.
2. **Plancha blanca detrás del logo** (un `<div>` blanco con esquinas
   redondeadas y ~2mm de padding, solo bajo la imagen): el logo se vería
   idéntico a la pantalla de Clientes, pero es un fondo claro dentro del
   bloque — justo lo que el punto (2) prohíbe.
3. **Subir el logo a la zona superior**, junto a `sqa_`, donde el fondo es el
   mismo pero hay más aire.

Dime cuál y lo hago en un cambio de 5 líneas.

---

## 6. Archivos tocados

| Archivo | Qué | Backup |
|---|---|---|
| `backend/app/services/export/report_generator.py` | anulación de la zebra + colores del bloque (PDF individual e integrado) | `.bak_n24_20260815_124909` |
| `backend/app/api/v1/endpoints/export_html.py` | colores del bloque + clase `.meta-sec` | `.bak_n24_20260815_124909` |
| `backend/app/api/v1/endpoints/integrated_report.py` | colores del bloque + clase `.plotly-meta-sec` | `.bak_n24_20260815_124909` |

`py_compile` limpio · backend reiniciado **sin build**.

---

## 7. Entregables

- `…\N21_PDFs_comparacion\individual_N24.pdf` — 852.917 B, **8 págs**
- `…\N21_PDFs_comparacion\integrado_N24.pdf` — 3.365.932 B, **18 págs**

**Criterio de éxito: tu validación visual.** Lo de arriba es verificación
estructural.
