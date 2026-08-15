# N3.5 — Bloque «Análisis por transacción crítica» en los 4 exports (cierre N3)

**Fecha:** 2026-08-15
**Commit:** `d70f65f` — *N3.5: bloque de analisis por transaccion critica en los
4 exports (cierre N3)*
**Push:** `github/backup-trabajo-local` (`a8736e8..d70f65f`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO Y VALIDADO SIN GASTAR CUOTA DE IA** (filas sembradas
con textos marcadores, borradas al terminar).

**Presupuesto:** máx 4 archivos → **100 insertadas, 0 borradas, 4 archivos.**
Ni una línea existente modificada: todo es añadido.

`report_generator.py` tocado con tu autorización **D5**, acotado a este bloque.

---

## 1. Lo que se añadió

| Archivo | Qué | Líneas |
|---|---|---|
| `report_generator.py` | helper `transaction_analyses_html()` + su llamada antes de `ai_box('conclusions')` | +47 |
| `export_pdf.py` | carga las filas de la ejecución → `meta['transaction_analyses']` | +13 |
| `export_html.py` | ídem + render en la plantilla | +15 |
| `integrated_report.py` | `_load_transaction_analyses()` + 2 llamadas (PDF y HTML) + render | +25 |

### 1.1 El helper

`ai_box` pinta **una** sección desde **una** clave fija; aquí el número de cajas
es variable, así que hacía falta uno nuevo (§5.3 del diagnóstico 025). Rama PDF
en `mm`/`pt` con `break-inside:avoid` y sin flex/grid (reglas 11/17); rama web
con `rem`/`px`. Estilo coherente con las cajas de análisis existentes (fondo
`#fff7ed`, borde izquierdo indigo `#4f46e5`).

Cada caja: **nombre de la transacción** → línea compacta de métricas → análisis.

```
Analisis por Transaccion Critica

token
8,600 muestras · promedio 443 ms · p90 529 ms · max 21060 ms · 23 errores (0.27%)
MARCADOR_EJEC_A_TOKEN. La transaccion mantiene un promedio saludable de 443 ms,
pero acumula picos de 21 segundos que apuntan a timeouts puntuales.
```

*(texto extraído del PDF real generado en la validación)*

### 1.2 Cómo llegan los datos

Por `meta['transaction_analyses']`, que ya es un dict **por ejecución** que
recorre las 4 salidas. No cambió la firma de `build_pdf_html` ni la de ningún
render. En el integrado, cada sección llama a `_load_transaction_analyses(db,
execution.id)` con **su** id, así que no hay forma de que se mezclen.

---

## 2. Validación

### 2.1 Sin filas: el documento sale idéntico (requisito de tolerancia)

Estado de partida, `transaction_analyses` vacía:

```
PDF individual : 8 pags  | bloque en pags []
PDF integrado  : 18 pags | bloque en pags []
HTML individual: bloque presente = False
HTML integrado : bloque presente = False
```

Después de sembrar 4 filas, exportar, y **borrarlas**:

| Métrica | sin filas | con filas | tras borrar | |
|---|---|---|---|---|
| PDF individual (págs) | 8 | 8 | **8** | idéntico ✔ |
| PDF integrado (págs) | 18 | 20 | **18** | idéntico ✔ |
| HTML individual (bytes) | 591.382 | 592.669 | **591.382** | idéntico ✔ |
| HTML integrado (bytes) | 4.048.798 | 4.051.287 | **4.048.798** | idéntico ✔ |

Los HTML vuelven al **mismo número de bytes** que antes de N3.5. No es «se ve
igual»: es el mismo documento. Sin título huérfano, sin caja vacía, sin hueco —
exactamente el criterio que N1 aplicó con el logo.

### 2.2 Con filas: el bloque aparece donde debe

```
PDF individual : 8 pags  | bloque en pag [6] | 'conclusiones' en [6]
                 -> BLOQUE ANTES DE CONCLUSIONES
PDF integrado  : 20 pags | bloque en pags [5, 11] | 'conclusiones' en [16, 17, 19]
HTML individual: bloque presente = True (1 vez)
HTML integrado : bloque presente = True (2 veces, una por ejecucion)
```

El PDF individual **no creció**: el bloque cupo en la página 6, delante de las
conclusiones. El integrado pasó de 18 a 20 páginas, que es el crecimiento
esperado al añadir contenido de dos ejecuciones.

### 2.3 En el integrado, cada ejecución muestra las suyas

Sembré marcadores distintos por ejecución (`115346ea` y `d1efb084`, las dos que
componen el reporte integrado):

```
=== PDF INTEGRADO: en que pagina cae cada marcador ===
  pag  5: ['MARCADOR_EJEC_A_TOKEN']
  pag  6: ['MARCADOR_EJEC_A_VERIF']
  pag 12: ['MARCADOR_EJEC_B_SENDCODE']

cada marcador aparece exactamente 1 vez:
  {'MARCADOR_EJEC_A_TOKEN': 1, 'MARCADOR_EJEC_A_VERIF': 1, 'MARCADOR_EJEC_B_SENDCODE': 1}

=== HTML INTEGRADO ===
  marcador A en offset 82.000, marcador B en offset 660.690 -> bloques separados

=== HTML INDIVIDUAL (solo ejecucion A) ===
  contiene marcadores de A: True | contiene marcador de B: False
```

Las transacciones de A caen en las páginas de A, las de B en las de B, cada una
una sola vez, y el export individual de A no arrastra nada de B.

### 2.4 Fila sin análisis: se pinta con una nota

Elegí **mostrarla** en vez de omitirla. Razón: esa transacción la marcaste tú;
si desaparece del informe sin decir nada, quedas creyendo que se analizó y salió
bien. Extraído del PDF integrado:

```
Transaccion sin analisis
500 muestras · promedio 100 ms · p90 120 ms · max 15000 ms · 0 errores (0.00%)
Esta transaccion se marco como critica pero no se genero su analisis individual.
```

### 2.5 Datos de prueba borrados

```
SELECT count(*) FROM transaction_analyses;  ->  4     (antes)
DELETE FROM transaction_analyses;           ->  DELETE 4
SELECT count(*) FROM transaction_analyses;  ->  0     (despues)
```

Cero filas de prueba en tu base, y cero llamadas de IA gastadas: los análisis
sembrados eran texto fijo con marcadores.

---

## 3. N3 cerrado

| Sprint | Commit | Qué entregó |
|---|---|---|
| N3.1 | `748c262` | diagnóstico read-only |
| N3.2 | `671aa23` | endpoint con métricas + criticidad determinista (y XML arreglado) |
| N3.3 | `0b78e33` | panel con tabla, checks premarcados y aviso del tope |
| N3.4 | `f07bce4` | tabla nueva, análisis IA individual, endpoint de lectura |
| **N3.5** | **`d70f65f`** | **bloque en las 4 salidas** |

**Lo que falta es tuyo y es lo único que no puedo hacer yo:** subir un JTL con
transacciones marcadas y ver el ciclo completo de punta a punta — panel →
análisis real de la IA → bloque en el PDF y el HTML. Eso consume cuota, por eso
todas las validaciones de N3.4 y N3.5 se hicieron con stubs y filas sembradas.

Recordatorio de dos cabos sueltos ya documentados, por si quieres cerrarlos:

- **`marked_by` siempre sale `'user'`** (reporte 028 §3.1): el panel no manda el
  origen de la marca. ~5 líneas si quieres distinguir premarcada de manual.
- **`build_standalone_html()`** sigue con la cabecera vieja y **sin** este bloque
  (reportes 022/023 §6): es código muerto, ningún endpoint la llama.
