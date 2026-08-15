# 021 — N2.2: conclusiones consolidadas en el integrado + fila de metadatos

**Fecha:** 14/08/2026 · **Rama:** `backup-trabajo-local` · **Commit:** `__HASH__`

**Resumen:** (A) la falta de conclusiones **no era una regresión de UI-2 ni de
N2.1**, y tampoco el orden de los strips (regla 18). Los exports integrados nunca
leían el consolidado guardado en base de datos: solo pintaban lo que el frontend
les mandaba en el request. (B) la fila de metadatos pasa a orden fijo
**NOMBRE | DURACIÓN | TIPO DE PRUEBA | CLIENTE** en las 4 salidas.

---

## (A) Diagnóstico — dónde se perdían las conclusiones

### 1. El informe de prueba SÍ tiene consolidado

El informe de Coomeva usado en N2.1 es
`2c5ba18e-f7a4-4c25-979a-05b39b32ae01` — *Informe Integrado 13/08/2026 18:09*,
2 ejecuciones de carga + 1 monitoreo:

```
consolidated_analysis: 10.933 bytes · clave `load` con
  conclusions · recommendations · generated_at · edited
```

No es el caso «no había nada que pintar». Había 10.716 caracteres de texto útil.

### 2. Los descartes

| Sospechoso del encargo | Veredicto |
|---|---|
| (a) UI-2 arrastró el bloque al quitar *Response Time Over Time* | **NO.** `git show 4ed0957` sobre `integrated_report.py` no toca ni el bloque de conclusiones ni su condicional ni la recolección de `all_conclusions`. |
| (b) N2.1 dejó el bloque fuera del render | **NO.** `git show 3af9818` toca 1 solo archivo, `report_generator.py` (plantilla individual). El bloque consolidado se compone en `integrated_report.py`, que N2.1 no abrió. |
| (c) Orden `_strip_pdf_individual_conclusions` / `_strip_individual_report_extras` (regla 18) | **NO.** El orden en `integrated_report.py:1540-1542` sigue siendo el correcto — primero conclusiones, después extras. Y aunque estuviera invertido no explicaría nada: los strips operan sobre el `<body>` de **cada ejecución**, y el bloque consolidado se concatena **después**, fuera de ese texto. |

### 3. La causa real

Los dos endpoints de export integrado pintaban el bloque **exclusivamente** desde
el payload del request:

```python
# antes — export-pdf
if request.unified_conclusions:      # <- unico origen
    conclusions_html = ...
```

Y `request.unified_conclusions` lo arma el frontend desde el estado React
`conclusions` (`IntegratedReportPage.tsx:82`), que se rellena en cuatro sitios
distintos y se puede quedar vacío — el más claro, `handleGenerate`:

```tsx
setConclusions(data.unified_conclusions || '');   // linea 368
```

Si se vuelve a pulsar **Generar informe** sobre un informe que ya tenía
consolidado y la IA devuelve vacío (cuota 429, respuesta truncada, o
`all_conclusions` sin material), ese `|| ''` **pisa** el texto bueno con cadena
vacía. El export siguiente sale sin el bloque y **sin ningún aviso**: el PDF se
descarga normal, simplemente cinco páginas más corto.

El consolidado, mientras tanto, sigue intacto en
`integrated_reports.consolidated_analysis`. Nunca se perdió — nadie lo leía.

### 4. Reproducción

Contra el backend vivo, mismo informe, dos payloads:

| `unified_conclusions` | PDF resultante | Bloque |
|---|---|---|
| 10.716 chars (lo que hay en DB) | 3.365.707 B · **18 páginas** | sí, pág. 14 |
| `""` | 3.354.171 B · **13 páginas** | **no** |

El backend hacía bien su trabajo en los dos casos. El bug estaba en depender de
un dato volátil.

### 5. Los PDFs de comparación de N2.1 eran una falsa alarma

`integrado_DESPUES.pdf` pesa **3.354.171 bytes**, byte a byte el mismo tamaño que
mi reproducción con `unified_conclusions=""`. El script con el que la sesión
anterior regeneró los PDFs de comparación **no mandaba las conclusiones**. Por eso
faltaban también en `integrado_ANTES.pdf` (23 páginas, verificado con extracción
de texto: ni rastro del título), que es anterior a N2.1. Los dos PDFs de la
carpeta de comparación estaban ciegos al bloque desde el principio.

### 6. Export HTML

Le pasaba lo mismo, con un agravante: el bloque era **incondicional**, así que sin
consolidado emitía un título *Conclusiones y Recomendaciones* con una caja vacía
debajo.

### 7. El fix

`_resolve_unified_conclusions()` — si el request llega vacío y trae `report_id`,
se lee el consolidado de DB y se aplana con **el mismo formato exacto** que
`flattenConsolidated()` del frontend. Es el patrón que F6 ya usa para los textos
editados de cada sección: *el dato bueno está en DB, no en el request*.

```python
text = (request.unified_conclusions or "").strip()
if text or not getattr(request, "report_id", None):
    return text
report = await db.get(IntegratedReport, uuid.UUID(request.report_id))
text = _flatten_consolidated((report.consolidated_analysis or {}) if report else {}).strip()
```

Se aplica en **PDF y HTML**, y el bloque HTML pasa a condicional. Si un informe
realmente no tiene consolidado, no se pinta nada y queda un `warning` en el log
en vez de una caja hueca.

**No se tocó el frontend.** El `|| ''` de la línea 368 sigue ahí, pero ya no puede
hacer daño: el backend recupera el texto por su cuenta. Si en algún momento se
quiere arreglar también el lado React, ese es el sitio.

---

## (B) Fila de metadatos

### Antes

El orden **cambiaba según hubiera logo o no**. Con logo, N1.8 movía TIPO DE PRUEBA
a la primera columna para hacerle sitio al logo a la derecha, y UI-2 metió después
la etiqueta CLIENTE y el nombre en esa misma celda. Resultado: TIPO DE PRUEBA
abriendo la fila, el logo pisando la zona de CLIENTE y el nombre del cliente
flotando desalineado — exactamente lo de la captura.

### Ahora

```
NOMBRE DEL PROYECTO  |  DURACION  |  TIPO DE PRUEBA  |        CLIENTE
                                                      [ logo del cliente ]
                                                        Nombre del cliente
```

Las tres primeras columnas son fijas. La cuarta es siempre CLIENTE, alineada a la
derecha (`text-align:right` en el `<td>`/`<div>`, logo con `margin-left:auto`), con
etiqueta / logo / nombre apilados y alineados entre sí. **Sin logo desaparece solo
la imagen** — mismo orden, misma alineación, sin hueco.

Desaparecen las dos ramas `if _client_logo` de cada salida: ahora la única
diferencia es si se emite el `<img>` o no.

### Reglas respetadas

- **Regla 11** — la portada PDF sigue siendo `<table><tr><td>`, sin flex ni grid.
- **Regla 17** — rama PDF en `mm`/`pt` (`max-height:26mm`, `max-width:58mm`);
  los `rem`/`px` solo en las ramas HTML de navegador.
- **Altura de portada intacta** — con logo la celda ya tenía 3 elementos y sin
  logo 2, igual que antes. Solo cambia en qué columna caen.

---

## Archivos tocados

| Archivo | Qué | Backup |
|---|---|---|
| `backend/app/api/v1/endpoints/integrated_report.py` | (A) helper + los 2 exports · (B) cabecera Plotly | `.bak_n22_20260814_194358` |
| `backend/app/services/export/report_generator.py` | (B) portada PDF (individual **e** integrado) | `.bak_n22_20260814_194358` |
| `backend/app/api/v1/endpoints/export_html.py` | (B) cabecera HTML individual | `.bak_n22_20260814_194358` |

3 archivos, 97 inserciones / 92 supresiones. `py_compile` limpio, restart sin build.

`export_html.py` está en la lista de «no tocar salvo mención explícita». El encargo
pide la fila corregida en el **HTML individual**, y esa cabecera vive ahí y solo
ahí — el cambio se limita a la fila de metadatos, nada más del archivo.

> **Nota:** `report_generator.build_standalone_html()` también tiene una fila de
> metadatos, pero **es código muerto**: nadie la importa (`grep` en todo
> `backend/app` solo devuelve su propio `def`). El HTML individual sale por
> `export_html.py`. No se tocó.

---

## Validación

Todo contra el backend vivo, sin rebuild.

**(A)** — request con `unified_conclusions=""`, que es justo el caso que fallaba:

```
PDF integrado : 18 paginas | titulo en paginas [14]
HTML integrado: titulo presente = True
```

13 páginas de cuerpo (el conteo estable de N2.1) + 5 de conclusiones.

**(B)** — orden de la fila, con y sin logo:

```
PDF individual   CON logo (Bancoomeva): 8 pag | NOMBRE · DURACION · TIPO · CLIENTE
PDF individual   SIN logo (Nutresa)   : 9 pag | NOMBRE · DURACION · TIPO · CLIENTE
HTML individual  CON logo             : [Nombre, Duracion, Tipo de Prueba, Cliente] logo=si
HTML individual  SIN logo             : [Nombre, Duracion, Tipo de Prueba, Cliente] logo=no
HTML integrado   CON logo             : [Nombre, Duracion, Tipo de Prueba, Cliente] logo=si
```

Conteo estable: individual **8** ✓ · integrado **13** de cuerpo ✓. (Las 9 páginas
de Nutresa son otra ejecución con más contenido, no una variación de portada.)

**PDFs para revisar** en `C:\Users\FredyGabrielBonillaB\Documents\N21_PDFs_comparacion\`:

```
individual_N22.pdf   (8 pag)   — fila de metadatos con logo
integrado_N22.pdf   (18 pag)   — fila de metadatos + conclusiones en pag. 14
```

Comparables contra `individual_DESPUES.pdf` / `integrado_DESPUES.pdf` de N2.1.

---

## Qué mirar

1. **Portada** de los dos: la fila debe leerse NOMBRE → DURACIÓN → TIPO DE PRUEBA
   → CLIENTE, con el logo colgando bajo la etiqueta CLIENTE y el nombre debajo,
   los tres pegados al margen derecho y sin solaparse con la columna del tipo.
2. **`integrado_N22.pdf` página 14**: debe abrir *Conclusiones y Recomendaciones*
   con el consolidado de la prueba de carga.
3. Un informe **sin consolidado generado** ya no debería sacar caja vacía en el
   HTML — ahora simplemente no emite el bloque.
