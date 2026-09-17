07fcdda · 2026-09-17

# ETAPA 6.5 — Tildes y limpieza (D52, D53)

**Llamadas reales a la IA: 0.** Se valida sobre `E3-estilo-pruebakinetix`
(`20bb2356-410d-465f-8717-c9a025e26e03`, 3 transacciones) y `E5-panel`
(`c33488cb-5f1c-499b-86b3-4b58642c31cb`, 2 transacciones), los dos informes **ya
generados**. Sin `docker build`.

---

## 1. D52 — las tildes

Se acentuaron **las cadenas visibles** de las cuatro salidas. No se tocaron ni los
comentarios del código, ni los identificadores, ni las claves de sección
(`chart_response_times`), ni los nombres de gráfica que la especificación fija en inglés
("Response Times", "Latency Over Time", "Transactions per Second"…).

| Archivo | Cadenas | Ejemplos |
|---|---|---|
| `report_generator.py` | 15 | "Reporte Resumen por **Transacción**", "**Códigos** de Respuesta", "**Análisis** - Response Times por **Transacción**", "**Distribución** de Response Codes", "**Análisis** de la **Transacción**" |
| `export_html.py` | 22 | los mismos, más "**Ejecución**", "**Duración**", "Criterios de **Aceptación**", "Reporte de **Análisis** de Performance", "Errores por **Transacción**" |
| `integrated_report.py` | 20 | los mismos del HTML, más "**Análisis** Global", "**Métricas** de Monitoreo" |
| `export_pdf.py` | 1 | la columna "**Análisis**" de la tabla de capacidad |
| `Dashboard.tsx` | 20 | "Veredicto por **Transacción**", "**Distribución** de **Códigos** de Error", "Detalle de Errores por **Transacción**", "**Código**", "**Duración**", "**Sesión** expirada… inicie **sesión**", los siete "**Análisis**", "Capturando **gráficas**…" |
| `SummaryTable.tsx` | 1 | la cabecera "**Transacción**" |
| `ReportBody.tsx` | 1 | "Response Times por **Transacción**" (hecha ya en 6.2) |

**Total: 80 cadenas.** El inventario del reporte 46 estimaba ~57; la diferencia son las del
informe integrado, que el diagnóstico no había contado archivo por archivo, y una decena
de textos en minúscula (placeholders, avisos) que aparecieron al revisar.

Palabras que **no** llevan tilde y por tanto no entraron: "Resumen", "Promedio",
"Latencia", "Errores", "Muestras", "Transacciones", "Criterios".

### Una dependencia que había que arreglar a la vez

`hf4_check.py` —el paso 10 de la verificación— comprueba que las tablas por transacción
usen **exactamente** el mismo título y las mismas columnas que la del informe general, y
los tenía escritos sin tilde:

```python
TITULO_TABLA = "Reporte Resumen por Transaccion"
COLUMNAS = ("Transaccion", "Muestras", …)
```

Se actualizaron los dos. Sin ese cambio, la comprobación habría fallado en las cuatro
salidas por el propio acierto del cambio.

### Un tropiezo de método que dejo escrito

El primer intento usó `perl -CSD`, que trata los bytes del argumento `-e` como Latin-1 y
los vuelve a codificar al escribir: los archivos quedaron con `TransacciÃ³n` en lugar de
`Transacción`, en los seis a la vez. Se detectó con un `grep -c "Ã"` antes de ejecutar
nada, se revirtió con `git checkout --` (el trabajo de 6.4 ya estaba en el commit
`07fcdda`, así que no se perdió nada) y se rehízo **sin `-CSD`**, en modo bytes, donde el
UTF-8 pasa intacto. La comprobación `grep -c "Ã"` quedó como paso fijo después de cada
tanda: da 0 en los seis archivos.

## 2. D53 — `transaction_analyses_html` retirada

Las **62 líneas** de la función que pintaba el bloque "Analisis por Transaccion Critica"
(`report_generator.py:215-269`) se borraron. El reporte 46 ya había confirmado que era
código muerto: una sola aparición en todo el repositorio, su propia definición. Su
docstring, escrita en HF-4, decía *"si al leer esto sigue sin usarse, se puede retirar
entera"*.

Con ella se van también las dos últimas cadenas "Analisis por Transaccion Critica" del
backend. Las filas de `transaction_analyses` en la base **no se tocan**: siguen ahí, de
solo lectura, como desde N3.4.

## 3. Archivos tocados

| Archivo | +/− | Protegido |
|---|---|---|
| `report_generator.py` | +18 / −71 | **sí** |
| `export_html.py` | +25 / −25 | **sí** |
| `integrated_report.py` | +20 / −20 | no |
| `export_pdf.py` | +1 / −1 | **sí** |
| `Dashboard.tsx` | +21 / −21 | **sí** |
| `SummaryTable.tsx` | +1 / −1 | no |
| `/tmp/e2e/hf4_check.py` | +3 / −2 | no (script de prueba) |

Copias de seguridad: `*.bak_etapa6_6.5_20260917`.

### Presupuestos, acumulado de toda la Etapa 6

| Archivo protegido | Presupuesto | Parada (+50 %) | Real |
|---|---|---|---|
| `export_html.py` | 90 | 135 | **99** |
| `Dashboard.tsx` | 60 | 90 | **54** |
| `export_pdf.py` | 55 | 83 | **43** |
| `report_generator.py` | 60 | 90 | **33 añadidas, 75 retiradas** |

`export_html.py` queda 9 líneas por encima de su estimación y **36 por debajo del umbral
de parada**: las tildes cuentan como línea modificada, y son 25 en ese archivo. Ninguno de
los cuatro dispara la condición de parada.

## 4. Verificación

### `verificar_etapa2.py` — diez pasos, las cuatro salidas, sobre las DOS ejecuciones

| Ejecución | Resultado |
|---|---|
| `E3-estilo-pruebakinetix` (3 transacciones) | **ETAPA 2 — LAS CUATRO SALIDAS PASAN** |
| `E5-panel` (2 transacciones) | **ETAPA 2 — LAS CUATRO SALIDAS PASAN** |

El paso 10 confirma la coherencia del cambio en las cuatro salidas:

```
PASA | Pantalla:  4 tablas 'Reporte Resumen' (general + transacciones)
PASA | PDF:       el titulo 'Reporte Resumen por Transacción' aparece 4 veces
PASA | HTML:      el titulo 'Reporte Resumen por Transacción' aparece 4 veces
PASA | Integrado: el titulo 'Reporte Resumen por Transacción' aparece 4 veces
PASA | …las 4 tablas llevan las mismas columnas   (en las tres salidas)
```

> La primera corrida de la suite sobre `E3` marcó dos pasos en rojo (5 y 7). Ejecutados
> por separado los dos pasaron enteros, y la corrida siguiente de la suite completa pasó
> también: era la sesión guardada, que caducó a mitad de la corrida. No hay ningún fallo
> de producto detrás; queda anotado por si vuelve a aparecer.

### Las pruebas de la Etapa 6, repetidas después de las tildes

| Prueba | Resultado |
|---|---|
| `capas_tooltip.py` (6.2, 22 comprobaciones de pantalla) | **TODO PASA** |
| `export_alcance.py` (6.3, 20 comprobaciones de PDF y HTML) | **TODO PASA** |
| `dialogo_export.py` (6.3, 13 comprobaciones de pantalla) | **TODO PASA** |
| `capas_exportadas.py` (6.4, 21 comprobaciones) | **TODO PASA** |
| `capas_html_render.py` (6.4, 13 en Chromium) | **TODO PASA** |

### Compilación

- `npx tsc --noEmit`: sin errores.
- Importación del backend: los cuatro módulos cargan y `transaction_analyses_html` ya no
  existe (`hasattr → False`).

## 5. Lo que NO se tocó

- Los comentarios del código y los nombres de variables: acentuarlos habría inflado el
  diff sin cambiar nada de lo que Fredy ve.
- Los nombres de gráfica en inglés que fija la especificación.
- El panel de selección (`UploadJTL.tsx`): sus textos visibles ya llegaron con tilde en la
  Etapa 5, y "Transacciones del JTL" y "TPS (Transacciones por segundo)" no llevan ninguna.
- Las filas de `transaction_analyses` en la base.

---

**Estado:** 6.5 implementada y verificada sobre las dos ejecuciones, pendiente validación
de Fredy. Ninguna condición de parada activada. Sigue 6.6 — cierre del plan.
