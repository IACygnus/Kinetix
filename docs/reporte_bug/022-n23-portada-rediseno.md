# N2.3 — Portada rediseñada: fuera los datos duplicados

**Fecha:** 2026-08-15
**Commit:** `b12adfe` — *N2.3: portada rediseñada sin datos duplicados*
**Push:** `github/backup-trabajo-local` (`02b7a46..b12adfe`, arrastra los dos
commits de N2.2 que estaban pendientes de push). **`origin` NO se tocó.**
**Estado:** **IMPLEMENTADO — PENDIENTE VALIDACIÓN VISUAL DE FREDY.**

**Presupuesto:** ~60-100 líneas, máx 4 archivos → **98 insertadas / 40 borradas,
3 archivos** ✔

---

## 1. El diagnóstico (confirmado en el código, no supuesto)

Fredy tenía razón: N2.2 reordenó columnas pero la fila seguía repitiendo lo que
ya estaba arriba. En `report_generator.py`, antes del cambio:

| Línea | Qué pintaba | Duplicado de |
|---|---|---|
| 747 | badge `{meta['testTypeLabel']}` | — (origen) |
| 749 | `cover-title` = `{meta['project'] or meta['name']}` | — (origen) |
| **751** | columna **NOMBRE DEL PROYECTO** = `{meta['project'] or meta['name']}` | **línea 749** |
| **753** | columna **TIPO DE PRUEBA** = `{meta['testTypeLabel']}` | **línea 747** |
| 757 | pie: `Archivo … Inicio … Fin … Criterio …` a **8pt / opacidad 0.4** | — |

2 de las 4 columnas repetían; la información que sí era única (hora de inicio y
fin, criterios de aceptación) vivía en el pie gris diminuto. El mismo patrón
estaba clonado en `export_html.py:793/795` y en `integrated_report.py:589/591`.

---

## 2. Cómo queda la fila

```
REPORTE DE ANALISIS DE PERFORMANCE   [SCALABILITY TEST]      <- badge: tipo (unico)
24342-Coomeva_SendCode_Performance                           <- titulo: proyecto (unico)

EJECUCION              DURACION     CRITERIOS                          CLIENTE
31/07/2026             29m 59s      < 2500 ms /                         [ LOGO ]
18:45:50 → 19:15:50                 > 99% disponibilidad               Bancoomeva

Archivo: resultados.jtl
```

- **EJECUCION** — fecha arriba, `hora inicio → hora fin` debajo, en blanco al
  85% (`.cover-meta-sub`, 10pt), no el gris del pie anterior.
- **CRITERIOS** — columna propia y legible. **Sin criterios definidos la columna
  no se pinta** y la fila queda de 3 columnas, sin hueco.
- **CLIENTE** — última columna, alineada a la derecha: etiqueta / logo / nombre.
  Sin logo, etiqueta + nombre sin hueco (comportamiento de N1.6, intacto).
- **Pie** — solo `Archivo: <nombre>.jtl`, subido de 8pt/0.4 a **9.5pt/0.75**.
- **Fuera de la fila:** NOMBRE DEL PROYECTO y TIPO DE PRUEBA.

---

## 3. Los cambios

### 3.1 Helper compartido — `report_generator.py`

Las 4 salidas necesitan las mismas piezas, así que se calculan una vez:

```python
def cover_meta_parts(meta: Dict[str, Any]) -> Dict[str, str]:
    """N2.3: piezas de la fila de metadatos de la portada (PDF y HTML).
    ...
    ``criteria`` vuelve vacio cuando la ejecucion no tiene criterios definidos;
    quien lo consume no debe pintar la columna en ese caso.
    """
    start = str(meta.get('startTime') or '--')
    end = str(meta.get('endTime') or '--')
    date_part, _, t_ini = start.partition(' ')
    _, _, t_fin = end.partition(' ')
    ...
    return {'date': ..., 'range': f'{t_ini} → {t_fin}', 'criteria': ' / '.join(parts)}
```

`startTime` / `endTime` ya llegaban como `'31/07/2026 18:45:50'` desde los tres
endpoints (`export_pdf.py:256`, `export_html.py:228`, `integrated_report.py:186`),
así que el helper solo parte la cadena — no toca la construcción de `meta`.

### 3.2 Rama PDF (individual **e** integrado)

- Se elimina el bloque `criteria_str` que colgaba los criterios del pie.
- La fila pasa a `EJECUCION | DURACION | {cover_cell_criterios} | CLIENTE`,
  con `cover_cell_criterios` vacío cuando no hay criterios.
- CSS nuevo `.cover-meta-sub` (10pt, blanco 85%) y `.cover-info-footer` subido
  a 9.5pt / 75%.
- Todo en `mm`/`pt` y dentro de la `<table>` existente — reglas 11 y 17
  respetadas, ni un `flex`/`grid`/`rem` en la rama PDF.

### 3.3 Ramas HTML (individual e integrado)

Misma composición con `<div>`s; la rejilla conmuta entre `repeat(4,1fr)` y
`repeat(3,1fr)` según haya criterios. Aquí sí se usan `rem`/`grid` porque son
para navegador.

### 3.4 Ajuste de altura de portada (necesario, no cosmético)

La segunda línea de EJECUCION desbordaba la portada **~4 mm**: el primer PDF
generado salió con **9 páginas y una página 2 en blanco** (39 caracteres, solo
el pie de paginación). Se recuperó ese espacio del propio ritmo vertical:

| Regla | Antes | Ahora |
|---|---|---|
| `.cover-info-box` padding | `6mm 8mm` | `5mm 8mm` |
| `.cover-info-box` margin-bottom | `6mm` | `4mm` |
| `.cover-title` margin-bottom | `5mm` | `3mm` |
| `.cover-meta-grid` margin-top | `3mm` | `2mm` |

Sin tocar tamaños de fuente ni nada del cuerpo del reporte.

---

## 4. Validación — conteos, no declaraciones

### 4.1 Las 4 combinaciones, sobre el PDF real

Se renderizó la portada con WeasyPrint **dentro del contenedor** en las 4
combinaciones (incluida *con logo + sin criterios*, que no existe hoy en la BD)
y se extrajo el texto de la página 1:

```
-- con logo  + con criterios --  OK
   nombre proyecto x1   tipo de prueba x1   (esperado 1 y 1)
   EJECUCION=True  horas 18:45:50->19:15:50=True  CRITERIOS=True (esperado True)
   'Archivo: ...jtl'=True   pie sin Inicio/Fin=True
-- con logo  + SIN criterios --  OK
   nombre proyecto x1   tipo de prueba x1   (esperado 1 y 1)
   EJECUCION=True  horas 18:45:50->19:15:50=True  CRITERIOS=False (esperado False)
-- SIN logo  + con criterios --  OK
   nombre proyecto x1   tipo de prueba x1   (esperado 1 y 1)
-- SIN logo  + SIN criterios --  OK
   nombre proyecto x1   tipo de prueba x1   (esperado 1 y 1)

RESULTADO 4 CASOS: TODOS OK
```

**El nombre del proyecto aparece 1 vez y el tipo de prueba 1 vez en los 4 casos.**

### 4.2 PDF individual contra ejecuciones reales

| Ejecución | Caso | Págs | proyecto | tipo | CRITERIOS |
|---|---|---|---|---|---|
| `115346ea` Bancoomeva | con logo + con criterios | **8** | x1 | x1 | sí (esperado sí) |
| `02da3924` Nutresa | sin logo + con criterios | 9 | x1 | x1 | sí (esperado sí) |
| `94502c3b` Editor IA | sin logo + SIN criterios | 8 | x1 | x1 | no (esperado no) |

Fila extraída del PDF de Bancoomeva:

```
EJECUCION 31/07/2026 18:45:50 → 19:15:50 DURACION 29m 59s
CRITERIOS < 2500 ms / > 99% disponibilidad CLIENTE Bancoomeva Archivo: resultados.jtl
```

y sin criterios (Editor IA), la columna simplemente no está:

```
EJECUCION 03/06/2026 16:59:15 → 16:59:25 DURACION 0m 10s CLIENTE Editor IA
Archivo: aiexec_25_result.jtl
```

### 4.3 Conteo de páginas estable

| Salida | Esperado | Obtenido |
|---|---|---|
| PDF individual (`115346ea`) | 8 | **8** ✔ (igual que `individual_N22.pdf`) |
| PDF integrado | 13 cuerpo + 5 conclusiones = 18 | **18** ✔, «Conclusiones y Recomendaciones» en página **14** |

Ninguna de las tres ejecuciones tiene páginas casi vacías (comprobado: 0 páginas
con <80 caracteres). Las 9 páginas de Nutresa son de su propio contenido
(21 transacciones), no un desbordamiento de portada.

### 4.4 HTML (individual e integrado)

Etiquetas de la fila extraídas del HTML generado:

```
HTML individual [con logo + con criterios] ['Ejecucion','Duracion','Criterios','Cliente'] logo=True  proyecto x1  'Inicio:' en cabecera=False
HTML individual [sin logo + con criterios] ['Ejecucion','Duracion','Criterios','Cliente'] logo=False proyecto x1  'Inicio:' en cabecera=False
HTML individual [sin logo + SIN criterios] ['Ejecucion','Duracion','Cliente']             logo=False proyecto x1  'Inicio:' en cabecera=False
HTML integrado  [con logo + con criterios] ['Ejecucion','Duracion','Criterios','Cliente'] logo=True             'Inicio:' en cabecera=False
```

`proyecto x1` = el nombre del proyecto aparece una sola vez en toda la cabecera.

---

## 5. Archivos tocados

| Archivo | Qué | Backup |
|---|---|---|
| `backend/app/services/export/report_generator.py` | helper + portada PDF (individual e integrado) + CSS | `.bak_n23_20260815_100935` |
| `backend/app/api/v1/endpoints/export_html.py` | cabecera HTML individual | `.bak_n23_20260815_100935` |
| `backend/app/api/v1/endpoints/integrated_report.py` | cabecera HTML integrado | `.bak_n23_20260815_100935` |

`py_compile` limpio en los tres. Backend reiniciado **sin build** (`docker
restart jmeter_backend`); el compose de dev monta `./backend:/app`, así que el
código nuevo entra con el reinicio.

`export_html.py` sigue en la lista de «no tocar salvo mención explícita»; el
encargo nombra la salida **HTML individual** como una de las 4, que es
exactamente esa función.

---

## 6. Cabo suelto que dejo señalado (no tocado)

`report_generator.py` tiene una segunda función, **`build_standalone_html()`**
(línea ~856), cuya cabecera conserva la fila vieja con *Nombre del Proyecto* y
*Tipo de Prueba*. **No está enganchada a ningún endpoint**: el export HTML
individual pasó a `_build_plotly_html()` en `export_html.py` y la única
referencia a `build_standalone_html` que queda en el repo está en archivos
`.bak_*`. Es código muerto, así que no lo toqué — no puedo validarlo por
ninguna salida real. Si en algún momento se revive, hay que aplicarle el mismo
rediseño.

---

## 7. Entregables

- `C:\Users\FredyGabrielBonillaB\Documents\N21_PDFs_comparacion\individual_N23.pdf` (852.686 B, 8 págs)
- `C:\Users\FredyGabrielBonillaB\Documents\N21_PDFs_comparacion\integrado_N23.pdf` (3.365.693 B, 18 págs)

**Criterio de éxito: la validación visual de Fredy.** Lo de arriba es
verificación estructural, no aprobación.
