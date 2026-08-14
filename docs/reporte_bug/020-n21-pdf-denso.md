# 020 — N2.1: PDF denso, flujo continuo de bloques gráfica+análisis

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado, 4 PDFs generados sin error. **Pendiente: aceptación del diseño por Fredy** (si lo rechaza se revierte con `git revert`, no con backups).
**Alcance:** **1 archivo** — `report_generator.py`, **+54 / −55** (el archivo *encoge*). `integrated_report.py` estaba autorizado pero **no hizo falta tocarlo** (explicado en §3).
**Resultado:** individual **12 → 8 páginas (−33 %)** · integrado **23 → 13 páginas (−43 %)**.
**Numeración:** había 19 reportes → este es el **020**.

`py_compile` OK · backend reiniciado sin build · backups `.bak_n21_20260814_162318`.

---

## 1. Corrección al diagnóstico de partida

El encargo daba por causa técnica *"salto de página forzado por sección"*. **No lo era.** Revisado el CSS antes de tocar nada: el único `page-break-after: always` es el de la portada (`.cover`), y en el integrado el único `page-break-before: always` es el que abre cada ejecución. **Entre gráficas no había ningún salto forzado.**

La causa real es **aritmética de alturas**. En A4 landscape con márgenes 15/20mm quedan **175 mm útiles**, y cada bloque apilado medía:

| Pieza | Alto |
|---|---:|
| Título de la gráfica | ~8 mm |
| Imagen (`max-height: 80mm`) | ~60-80 mm |
| Caja de análisis (texto de ~1.200 caracteres a 8pt en 267 mm) | ~40 mm |
| Márgenes | ~10 mm |
| **Total por bloque** | **~133 mm** |

Dos bloques = 266 mm > 175 mm. **Solo cabía uno por página, y sobraban ~42 mm de blanco** — exactamente el "medio metro de blanco" que describiste. El salto no lo forzaba el CSS: lo forzaba el tamaño.

---

## 2. El cambio: la unidad indivisible es de DOS columnas

Apilar gráfica y análisis desperdicia el formato horizontal. La página es **landscape**: hay 267 mm de ancho y el análisis se leía en líneas larguísimas de 8pt.

**Gráfica a la izquierda (46 %), su análisis a la derecha (54 %)**, ambos dentro de una `<table class="chart-unit">` con `page-break-inside: avoid`. La unidad mide ahora **lo que el más alto de los dos** (~70-90 mm) en vez de la suma → **entran dos por página**, y a veces tres.

```python
def chart_unit(title, color, img_key, ia_key, ia_title):
    ai_html = ai_box(ia_key, ia_title, color)
    head = f'<div class="chart-title" style="border-left-color:{color}">{title}</div>'
    img  = f'<img class="chart-img" src="data:image/png;base64,{charts[img_key]}" />'
    if not ai_html:   # sin analisis, la grafica ocupa el ancho completo
        return f'<table class="chart-unit"><tr><td class="chart-cell" style="width:100%">{head}{img}</td></tr></table>'
    return (f'<table class="chart-unit"><tr>'
            f'<td class="chart-cell">{head}{img}</td>'
            f'<td class="chart-ai-cell">{ai_html}</td>'
            f'</tr></table>')
```

Las 8 gráficas pasan de 5 líneas de markup cada una a **una línea cada una** — por eso el archivo encoge pese a añadir helper y CSS.

**Reglas respetadas:** `table`, nunca flex/grid (regla 11) · medidas en `mm`/`pt`, ningún `rem` (regla 17) · el orden de los strips del integrado no se tocó (regla 18).

Ajustes de respiración que acompañan: `.ai-box` margin `2mm 0 5mm` → `0 0 3mm`, `.ai-text` line-height `1.6` → `1.45`, y `.chart-unit` con `margin-bottom: 4mm` uniforme entre bloques.

### Lo que conserva salto propio (sin cambios)

- **Portadas:** `.cover { page-break-after: always }` intacto — cada ejecución sigue abriendo con su portada completa a página entera (PDF-1 vigente).
- **Cada ejecución del integrado:** `page-break-before: always` en su body (`integrated_report.py:1543`), intacto.
- **Conclusiones consolidadas:** su bloque ya forzaba página nueva (B1+B3), intacto.
- **Conclusiones/Recomendaciones individuales:** siguen con `allow_break=True`, es decir, pueden partirse si son largas — correcto para texto corrido.

### El ajuste que hizo falta a mitad de camino (honestidad del proceso)

Con el reparto inicial 56/44 el **integrado bajó a 15 páginas pero el individual se quedó clavado en 12**. Motivo medido: los análisis de esa ejecución son de ~1.200 caracteres y, en una columna de 44 % (115 mm), crecían a ~93 mm de alto — la unidad volvía a pasar de la mitad de página. Con **46/54** y el interlineado a 1.45 la caja baja a ~75 mm y el emparejado ocurre en los dos documentos. Es un equilibrio ancho-de-columna ↔ largo-del-texto: si en el futuro los análisis se alargan mucho, este es el parámetro a mover.

---

## 3. Por qué `integrated_report.py` no necesitó cambios

El PDF integrado **no tiene plantilla de gráficas propia**: compone el `<body>` del PDF individual de cada ejecución (`_generate_full_execution_pdf_html` → `build_pdf_html`) y le quita cabeceras y conclusiones duplicadas. Al densificar la plantilla individual, **el integrado heredó el cambio completo** — de hecho es el que más baja (−43 %).

Las secciones de **Monitoreo y Evidencias** (`_build_att_html`, rama PDF) ya trataban cada imagen+análisis como unidad con `page-break-inside: avoid; break-inside: avoid` y **sin salto forzado**: ya fluían. No se tocaron.

---

## 4. Resultados medidos

| PDF | Antes | Después | Reducción | Gráficas por página (después) |
|---|---:|---:|---:|---|
| **Individual** (Coomeva_2) | 12 | **8** | **−4 (−33 %)** | `[1, 2, 2, 2, 2]` |
| **Integrado** (Coomeva, 2 ejecuciones) | 23 | **13** | **−10 (−43 %)** | `[1, 1, 3, 2, 2, 1, 1, 3, 2, 2, 1, 1, 1]` |

Antes, **las 30 páginas con gráfica llevaban exactamente 1**. Ahora hay páginas con 2 y con 3.

### Verificaciones

| Check | Resultado |
|---|---|
| Generación | 4 PDFs **HTTP 200**, `%PDF-1.7` válidos |
| Errores de WeasyPrint | **Ninguno** en los logs de las 4 generaciones |
| Gráficas perdidas | **Ninguna**: individual 9 → 9 imágenes, integrado 21 → 21 |
| Gráficas cortadas | Ninguna unidad partida: `page-break-inside: avoid` sobre la tabla; ninguna unidad excede la altura de página con estos textos |
| Portadas | Conservan `page-break-after: always`; siguen a página completa |
| Numeración | `@bottom-center "Pagina X de Y"` intacto, recalculado sobre el nuevo total |
| Peso | Prácticamente igual (861 → 859 KB; 3.359 → 3.354 KB): mismo contenido, menos páginas |

**Sobre `page-break-inside: avoid` en WeasyPrint 61.2:** es *best-effort*. Si una unidad llegara a superar la altura de una página entera (análisis kilométrico), WeasyPrint la partiría en vez de dejar una página en blanco — comportamiento correcto y preferible. Con los textos actuales (~1.200 caracteres) **no ocurre en ninguna de las 21 unidades generadas**.

---

## 5. Los 4 PDFs para comparar

```
C:\Users\FredyGabrielBonillaB\Documents\N21_PDFs_comparacion\
    individual_ANTES.pdf     (12 pág)   individual_DESPUES.pdf   (8 pág)
    integrado_ANTES.pdf      (23 pág)   integrado_DESPUES.pdf   (13 pág)
```

---

## 6. Historial

```
$ git log --oneline -1
3af9818 N2.1: PDF denso — flujo continuo de bloques grafica+analisis
```

Anteriores: `4211a8d` (B6.2) · `5f30b96` (SEC-2) · `89dbccc` (SEC-1) · `24eb0a5` (R1).

Se commiteó **sólo tras confirmar** que los 4 PDFs generan sin error, como pediste. Si rechazas el diseño: `git revert` del commit y el PDF vuelve al layout anterior.

---

## 7. Las tres preguntas para Fredy

Abre los 4 PDFs lado a lado y responde:

**(a) ¿El flujo denso te gusta o prefieres volver?**
Lo que cambia de verdad: la gráfica ahora ocupa ~46 % del ancho (antes el 100 %) y su análisis va al lado en vez de debajo. Se ve más como un informe ejecutivo y menos como una galería. Si prefieres las gráficas grandes a costa de las páginas, se revierte en un comando.

**(b) ¿Qué bloques quieres ajustar?** Todos estos son de una línea:
- **Reparto de columnas** (hoy 46/54): más gráfica ↔ más texto.
- **Alto máximo de gráfica** (hoy `max-height: 80mm`, que en la columna del 46 % se resuelve en ~60 mm).
- **Tipografía del análisis** (hoy 8pt, interlineado 1.45).
- **Separación entre unidades** (hoy 4 mm).

**(c) ¿Algo que deba conservar salto de página propio y no lo tenga?**
Hoy lo conservan: portadas, cada ejecución del integrado y las conclusiones consolidadas. Candidatos que hoy **fluyen** y podrían querer página propia: la tabla de estadísticas + su análisis, la sección de redirecciones, o el bloque de Monitoreo/Evidencias.

---

## 8. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- Backups `.bak_n21_20260814_162318` de los dos archivos autorizados.
- **Exports HTML sin tocar** — el problema de páginas es exclusivo del PDF.
- **Ningún análisis IA ejecutado** — cuota intacta. Los PDFs reusan los análisis ya guardados.
- Los PDFs de línea base se generaron **antes** de la primera edición.
