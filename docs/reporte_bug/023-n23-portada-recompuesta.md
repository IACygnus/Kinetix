# N2.3 (2ª pasada) — Portada recompuesta: dos zonas, cliente amplio

**Fecha:** 2026-08-15
**Commit:** `7e92b66` — *N2.3: portada recompuesta sin duplicados + bloque de
cliente amplio*
**Push:** `github/backup-trabajo-local` (`38836bd..7e92b66`). El push pendiente
de N2.2 ya se resolvió en la pasada anterior (`02b7a46..b12adfe`).
**`origin` NO se tocó.**
**Estado:** **IMPLEMENTADO — PENDIENTE VALIDACIÓN VISUAL DE FREDY.**

**Presupuesto:** ~70-110 líneas, máx 4 archivos → **117 insertadas / 72
borradas, 3 archivos**. Se pasó ~7 líneas del techo: el desbordamiento de
portada obligó a añadir comentarios de por qué cambia cada milímetro (ver §4).

Antecedente: el reporte **022** dejó la fila en una sola línea de 4 columnas.
Esta pasada implementa el bloque de dos zonas aprobado.

---

## 1. Cómo queda la portada

```
sqa_                                              Realizado por:
Software Quality Assurance                        Celula de Performance SQA
──────────────────────────────────────────────────────────────────────────────
 REPORTE DE ANALISIS DE PERFORMANCE  [SCALABILITY TEST]   <- tipo, aqui y solo aqui
 24342-Coomeva_SendCode_Performance                       <- proyecto, aqui y solo aqui

 EJECUCION              DURACION          │            CLIENTE
 31/07/2026             29m 59s           │
 18:45:50 → 19:15:50                      │          ┌─────────────┐
                                          │          │    LOGO     │
 CRITERIOS DE ACEPTACION                  │          └─────────────┘
 < 2500 ms · > 99% disponibilidad         │           Bancoomeva
                                          │
 ARCHIVO                                  │
 resultados.jtl                           │
──────────────────────────────────────────────────────────────────────────────
```

- **Zona izquierda (62%)**: tres filas apiladas — `EJECUCION` + `DURACION` lado
  a lado, `CRITERIOS DE ACEPTACION`, `ARCHIVO`. El nombre del `.jtl` ya no es un
  texto suelto en gris al pie: tiene su etiqueta y el mismo tamaño que el resto.
- **Zona derecha (38%)**: `CLIENTE` con etiqueta, logo (hasta 28×72 mm, con
  3 mm de aire arriba y 2 mm abajo) y nombre a 14 pt, los tres centrados entre
  sí. La separación es el `border-left` del `<td>` derecho.
- **Sin criterios** → la fila no se pinta y las otras dos se juntan.
- **Sin logo** → la zona derecha no se mueve: etiqueta + nombre centrados.
- Fuera del bloque: **NOMBRE DEL PROYECTO** y **TIPO DE PRUEBA**.

---

## 2. Reglas respetadas

| Regla | Cómo |
|---|---|
| 11 — WeasyPrint sin flex/grid | El bloque es una `<table>` de 2 `<td>` con una `<table>` anidada dentro del izquierdo. La línea vertical es `border-left`, no un flex. |
| 17 — nada de `rem` en PDF | Todo el bloque en `mm`/`pt`. Las ramas HTML sí usan `rem`/`flex`, que es lo suyo. |
| Ancho real del A4 apaisado | La zona del cliente pasa de 58 mm a **72 mm** de ancho útil y el logo de 26 mm a 28 mm de alto, con márgenes propios. |

---

## 3. Archivos tocados

| Archivo | Qué | Backup |
|---|---|---|
| `backend/app/services/export/report_generator.py` | bloque de 2 zonas en la portada PDF (individual **e** integrado) + CSS | `.bak_n23_20260815_103020` |
| `backend/app/api/v1/endpoints/export_html.py` | cabecera HTML individual (flex, 2 zonas) | `.bak_n23_20260815_103020` |
| `backend/app/api/v1/endpoints/integrated_report.py` | cabecera HTML integrado (flex, 2 zonas) | `.bak_n23_20260815_103020` |

`py_compile` limpio en los tres · backend reiniciado **sin build**.

---

## 4. El desbordamiento de portada, medido (no adivinado)

Al montar el bloque de tres filas la portada **se partía en dos páginas**: el
PDF individual salía con 9 páginas y una página 2 con 39 caracteres (solo el
pie de paginación). Dos intentos de recortar «a ojo» no lo arreglaron, así que
instrumenté la geometría real de WeasyPrint (`page._page_box.descendants()`,
alturas convertidas a mm):

```
### con logo + con criterios   (pagina util = 210.0mm)
   cover-info-box     alto=  90.2mm
   cover-kpi-table    alto=  55.7mm   termina en y= 204.0mm
   FONDO REAL         el contenido termina en y= 214.0mm  -> SE PASA

### con logo + SIN criterios   (pagina util = 210.0mm)
   cover-info-box     alto=  76.7mm
   FONDO REAL         el contenido termina en y= 199.4mm  -> CABE
```

Diagnóstico exacto: **la fila de criterios cuesta 13.6 mm** (90.2 − 76.7) y ese
era justo el margen que faltaba. Por eso solo desbordaban las ejecuciones *con*
criterios — la de Editor IA, sin criterios, siempre salió en 8 páginas.

Espacio recuperado, todo fuera del bloque de metadatos:

| Regla | Antes | Ahora | Gana |
|---|---|---|---|
| `.cover` padding vertical | `15mm / 10mm` | `10mm / 6mm` | 9 mm |
| `.cover-kpi-table td` padding | `4mm 5mm` | `2.5mm 5mm` | ~6 mm (2 filas) |
| `.cover-kpi-table` margin-top | `5mm` | `3mm` | 2 mm |
| pie «Celula de Performance SQA» | `5mm` | `3mm` | 2 mm |
| `.cover-meta-fila` padding-bottom | `2.5mm` | `1.5mm` | ~3 mm (3 filas) |

Medición final, las 4 combinaciones:

```
### con logo + con criterios   FONDO REAL y=210.0mm (limite 210mm) -> CABE
### con logo + SIN criterios   FONDO REAL y=210.0mm (limite 210mm) -> CABE
### SIN logo + con criterios   FONDO REAL y=210.0mm (limite 210mm) -> CABE
### SIN logo + SIN criterios   FONDO REAL y=210.0mm (limite 210mm) -> CABE
```

**Nota para el futuro:** probé `min-height: 194mm` (página − padding), que sobre
el papel es lo «correcto», y **empeora**: la portada deja de llenar la página y
aparece una franja blanca abajo. `min-height: 210mm` se queda como está.

---

## 5. Validación por evidencia

### 5.1 Las 4 combinaciones sobre el PDF real

Portada renderizada con WeasyPrint dentro del contenedor en las 4 combinaciones
(incluida *con logo + sin criterios*, que hoy no existe en la BD), contando
sobre el texto extraído de la página 1:

```
-- con logo  + con criterios --  OK
   nombre proyecto x1   tipo de prueba x1   (esperado 1 y 1)
   EJECUCION=True  horas 18:45:50->19:15:50=True  CRITERIOS=True (esperado True)
   ARCHIVO resultados.jtl=True   pie sin Inicio/Fin=True
-- con logo  + SIN criterios --  OK
   nombre proyecto x1   tipo de prueba x1   CRITERIOS=False (esperado False)
-- SIN logo  + con criterios --  OK
   nombre proyecto x1   tipo de prueba x1   CRITERIOS=True (esperado True)
-- SIN logo  + SIN criterios --  OK
   nombre proyecto x1   tipo de prueba x1   CRITERIOS=False (esperado False)

RESULTADO 4 CASOS: TODOS OK
```

### 5.2 PDF individual contra ejecuciones reales

| Ejecución | Caso | Págs | proyecto | tipo | CRITERIOS |
|---|---|---|---|---|---|
| `115346ea` Bancoomeva | con logo + con criterios | **8** | **x1** | **x1** | sí (esperado sí) |
| `02da3924` Nutresa | sin logo + con criterios | 9 | **x1** | **x1** | sí (esperado sí) |
| `94502c3b` Editor IA | sin logo + SIN criterios | **8** | **x1** | **x1** | no (esperado no) |

Texto extraído de la portada de Bancoomeva:

```
EJECUCION 31/07/2026 18:45:50 → 19:15:50 DURACION 29m 59s
CRITERIOS DE ACEPTACION < 2500 ms · > 99% disponibilidad
ARCHIVO resultados.jtl CLIENTE Bancoomeva
```

y sin criterios (Editor IA), esa fila no aparece:

```
EJECUCION 03/06/2026 16:59:15 → 16:59:25 DURACION 0m 10s
ARCHIVO aiexec_25_result.jtl CLIENTE Editor IA
```

Ninguno de los tres PDF tiene páginas de desbordamiento (0 páginas con <80
caracteres). Las 9 páginas de Nutresa son de su propio contenido
(21 transacciones), no de la portada.

### 5.3 Conteo de páginas

| Salida | Esperado | Obtenido |
|---|---|---|
| PDF individual (`115346ea`) | 8 | **8** ✔ |
| PDF integrado | 13 cuerpo + 5 conclusiones = 18 | **18** ✔, «Conclusiones y Recomendaciones» en página **14** |

### 5.4 HTML — las dos zonas

Etiquetas extraídas por zona del HTML generado:

```
HTML individual [con logo + con criterios]
    izquierda=['Ejecucion','Duracion','Criterios de Aceptacion','Archivo']
    derecha=['Cliente'] logo=True     proyecto x1 | tipo x1 | 'Inicio:'=False
HTML individual [sin logo + con criterios]
    izquierda=['Ejecucion','Duracion','Criterios de Aceptacion','Archivo']
    derecha=['Cliente'] logo=False    proyecto x1 | tipo x1 | 'Inicio:'=False
HTML individual [sin logo + SIN criterios]
    izquierda=['Ejecucion','Duracion','Archivo']
    derecha=['Cliente'] logo=False    proyecto x1 | tipo x1 | 'Inicio:'=False
HTML integrado  [con logo + con criterios]
    izquierda=['Ejecucion','Duracion','Criterios de Aceptacion','Archivo']
    derecha=['Cliente'] logo=True                             'Inicio:'=False
```

`proyecto x1` / `tipo x1` = una sola aparición de cada uno en toda la cabecera.
Las cabeceras HTML además colapsan a una columna por debajo de 768 px, con la
línea vertical convertida en horizontal.

---

## 6. Cabo suelto (el mismo del reporte 022)

`build_standalone_html()` en `report_generator.py` conserva la cabecera vieja.
**No está enganchada a ningún endpoint** — el HTML individual lo genera
`_build_plotly_html()` en `export_html.py` y las únicas referencias vivas a
`build_standalone_html` están en archivos `.bak_*`. Código muerto: no lo toqué
porque no puedo validarlo contra ninguna salida real.

---

## 7. Entregables

- `…\N21_PDFs_comparacion\integrado_N23.pdf` — 3.365.937 B, **18 págs** ✔
- `…\N21_PDFs_comparacion\individual_N23_nuevo.pdf` — 852.838 B, **8 págs** ✔

> `individual_N23.pdf` estaba **abierto en un visor** y Windows bloqueó la
> escritura (`PermissionError`). El PDF nuevo quedó como
> `individual_N23_nuevo.pdf` en la misma carpeta. Al cerrar el visor se puede
> renombrar, o pídemelo y lo reescribo con el nombre original.

**Criterio de éxito: la validación visual de Fredy.** Lo anterior es
verificación estructural, no aprobación.
