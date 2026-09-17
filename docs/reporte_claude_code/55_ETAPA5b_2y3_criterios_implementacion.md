2f7192c · 2026-09-17

# ETAPA 5b.2 y 5b.3 — El botón "Criterios" y los criterios efectivos en la IA

**Llamadas reales a la IA: 16** de las 20 autorizadas. Contadas, no estimadas: el contador
`ai_config.daily_requests_used` pasó de **198 a 214**. Las 16 son las de la corrida real de
5b.3 (10 del informe general + 6 del bloque de "1. Auth"). **5b.2 gastó 0**: se validó con
un stub que cuenta y lanza.

---

## 1. Qué se implementó

### D54 — la columna "Criterios" (`UploadJTL.tsx`)

La tabla del panel pasa de

```
| ☐ | ▸ | Transacción | Muestras | Promedio | TPS | Errores |
```

a

```
| ☐ | Transacción | Muestras | Promedio | TPS | Errores | Criterios |
```

- **Sale la flecha** de la izquierda.
- **Entra un botón por fila** en la última columna: **"Globales"** en gris si la fila no
  tiene valores propios, **"Propios"** en índigo si los tiene. El botón es lo que despliega
  el panel de esa fila.
- El desplegable no cambia: los tres campos con el global como marca de agua y el botón
  "Usar globales" (D41). Siguen pudiendo quedar **varias filas abiertas a la vez** (D40).
- La criticidad se sigue recalculando al instante (D42).

### D55 — la IA usa los criterios efectivos

Módulo nuevo **`backend/app/services/ai/criterios.py`**, que es **la única resolución del
umbral efectivo**. No una copia de la que ya existía: `compute_per_transaction_verdicts`
—la función que calcula la tabla de veredictos— **pasa a llamarla también**. Así el texto
de la IA y la tabla no pueden hablar de umbrales distintos, que era el riesgo de fondo.

**En los 6 prompts de cada transacción** entra el límite que se le aplica, diciendo cuál es:

```
CRITERIO DE ACEPTACIÓN QUE SE LE APLICA A "1. Auth":
- Tiempo de respuesta máximo: 300 ms (límite propio de esta transacción)
- Disponibilidad mínima: 99,5% (límite propio de esta transacción)
- El tiempo se compara contra el P90: 1 de cada 10 usuarios no debería pasar de 300 ms.
Esta transacción tiene un límite PROPIO, distinto del general de la prueba: júzgala solo contra él.
```

y para una sin criterio propio, la otra rama:

```
- Tiempo de respuesta máximo: 2.000 ms (criterio general de la prueba)
Esta transacción no tiene límite propio, así que se mide con el criterio general de la prueba.
```

**En los prompts del informe general** —resumen, errores, las 6 gráficas, conclusiones y
recomendaciones— entra la lista de excepciones:

```
TRANSACCIONES CON CRITERIO PROPIO (1), que NO se miden con el criterio general:
- "1. Auth": tiempo de respuesta máximo 300 ms, disponibilidad mínima 99,5%
Las demás sí se miden con el criterio general de arriba.
IMPORTANTE: al hablar de cualquiera de estas transacciones usa SU límite, no el
general. La tabla de veredictos del informe ya está calculada así, y el texto no
puede contradecirla.
```

`analyze_errors` y `analyze_chart` **no recibían criterios en absoluto** (reporte 54): se
les añadió el parámetro y reciben el bloque global completo más la lista.

**Compatibilidad:** sin criterios, con criterios vacíos o con criterios en prosa
(`raw_text`), las funciones devuelven cadena vacía y **los prompts salen exactamente como
antes de esta etapa**. Comprobado en los tres casos.

`analyze_redirects` se deja fuera a propósito: habla de redirecciones, no de cumplir un
umbral, y D55 no lo lista.

### D56 — la especificación

`docs/ESPECIFICACION-informe.md` pasa a **v1.3**: §2.2 describe el botón por fila y añade
un párrafo con cómo usa la IA los criterios efectivos. CLAUDE.md apunta ya a v1.3.

## 2. Archivos tocados

| Archivo | +/− | Protegido |
|---|---|---|
| `backend/app/services/ai/criterios.py` | **nuevo**, 133 | no |
| `backend/app/services/ai/gemini.py` | +22 / −9 | no |
| `backend/app/services/ai/transaction_report.py` | +21 / −4 | no |
| `backend/app/services/ai/analysis_pipeline.py` | +7 | no |
| `backend/app/api/v1/endpoints/upload.py` | +6 / −1 | no |
| `frontend/src/components/dashboard/UploadJTL.tsx` | +30 / −12 | no |
| `docs/ESPECIFICACION-informe.md` · `CLAUDE.md` | documentación | — |

**Ningún archivo protegido.** El reporte 54 ya lo había verificado y así se mantuvo.
Copias de seguridad: `*.bak_etapa5b_5b.2_20260917`.

## 3. Verificación de 5b.2 — 0 llamadas a la IA

### Los prompts (`criterios_5b2.py`, 26 comprobaciones)

Mismo stub que el diagnóstico: cuenta y lanza. Contó 7 intentos y lanzó en los siete.

| Bloque | Resultado |
|---|---|
| **1. "1. Auth" (300 ms propios)** — las 6 secciones traen 300 ms marcado como límite propio; ninguna presenta 2.000 ms como suyo | PASA (7) |
| **2. "2. Get Booking" (sin propios)** — las 6 traen 2.000 ms marcado como criterio general; no se le cuela el límite de otra | PASA (7) |
| **3. Los generales** — resumen, errores, gráfica response_times, gráfica error_rate, conclusiones y recomendaciones listan "1. Auth" con sus 300 ms | PASA (6) |
| **4. Sin criterios** — con `None`, con `{}` y con `raw_text`, ninguna sección trae bloque de criterios | PASA (3) |
| **5. La tabla de veredictos** — los 6 veredictos coinciden con los guardados; "1. Auth" sigue NO APTO y "2. Get Booking" APTO | PASA (3) |

> **Una comprobación mía mal escrita.** La primera pasada marcaba FALLA en las seis
> secciones de "2. Get Booking" porque exigía que no apareciera la frase "límite propio".
> Aparece —en negativo: *"Esta transacción **no tiene límite propio**"*—. Se cambió a
> comprobar la marca que acompaña a la cifra, `(criterio general de la prueba)` frente a
> `(límite propio de esta transacción)`. Era un error de la prueba, no del texto.

### La pantalla (`panel_boton_criterios.py`, 26 comprobaciones con Playwright)

Sobre Nuevo Reporte, **sin generar ningún informe**.

| Bloque | Resultado |
|---|---|
| **1.** "Criterios" existe y es la última columna; siguen las cinco de §2.1 | PASA (7) |
| **2.** Ya solo hay una columna sin título, la del checkbox; el nombre está en la segunda celda | PASA (2) |
| **3.** Los 6 botones abren en "Globales" | PASA (3) |
| **4.** El botón despliega su fila con los tres campos y "Usar globales"; una segunda fila se abre sin cerrar la primera | PASA (7) |
| **5.** Editar un criterio pasa ese botón a "Propios" y **ningún otro se mueve** | PASA (4) |
| **7.** "Usar globales" lo devuelve a "Globales" y la fila vuelve a como estaba | PASA (2) |
| **8.** Criticidad: apretando el tiempo global, "1. Auth" queda crítica solo por tiempo; subir **su** límite la deja de marcar, sin volver a subir el archivo | PASA (4) |

> **Otra comprobación mía que pasaba en vacío.** La primera versión daba por probado el
> recálculo de criticidad porque "el texto bajo el nombre cambió" — pero lo que había
> cambiado era la aparición del chip "criterios propios": la fila era crítica **por
> errores**, y tocar el tiempo no podía cambiarla. Se rehízo como el bloque 8: apretar
> primero el criterio global para tener una crítica **solo por tiempo** y devolverla con su
> criterio propio. Eso sí demuestra D42.

### Regresiones

- **Paridad de criticidad: 25/25.** `compute_per_transaction_verdicts` cambió de
  implementación y sigue dando lo mismo.
- `pytest`: **492 pasan**, 1 falla — la anterior al plan (`analysis_pipeline.time`),
  documentada en el checklist de despliegue.
- `npx tsc --noEmit`: sin errores.
- `panel_seleccion.py` (la prueba de la Etapa 5) **se actualizó a las columnas nuevas** —
  el nombre pasó de la celda 2 a la 1 y el TPS de la 5 a la 4, y la fila se abre ahora con
  el botón. Vuelve a pasar entera.

## 4. La corrida real — `E5b-criterios`

`2b412839-11f4-42b3-a489-c07b74e13568`. JTL de `pruebakinetix`, criterio global
2.000 ms · 99,5% · 30 usuarios, **"1. Auth" con 300 ms propios**, y solo "1. Auth" marcada
como crítica (marcar también "2. Get Booking" serían 22 llamadas, por encima del
presupuesto).

| | |
|---|---|
| `POST /upload` | **200 en 79 s** |
| `ai_status` | `{"provider": "openai", "model": "gpt-5.5", "success": true, "error": null}` |
| Llamadas | **16** (198 → 214) |
| `outcome` | **`ok` en todas**; ni un `outcome` distinto en todo el log |
| Secciones por transacción | **6/6 con texto** |

### Lo que escribió la IA

**El bloque de "1. Auth"** (resumen):

> "El tiempo promedio fue 422 ms […] **más lento que el objetivo definido para esta
> transacción**. **Con límite de 300 ms**, 1 de cada 10 usuarios espera más de 462 ms
> (P90: 462 ms), por lo que la experiencia supera el tiempo esperado para el ingreso."

y su gráfica de tiempos:

> "**El límite propio de esta transacción es 300 ms** y 1 de cada 10 usuarios espera más de
> 462 ms (P90: 462 ms), **por encima de ese umbral**."

**El informe general** (análisis de Response Times):

> "**Auth promedió 422 ms y quedó por encima de su límite propio de 300 ms**, lo que apunta
> a que el ingreso puede sentirse más lento desde el inicio del flujo."

Antes de esta etapa el prompt general solo conocía los 2.000 ms: con 422 ms de promedio,
lo natural era darla por buena — y la tabla la marcaba NO APTO. **Ahora coinciden.**

### Controles (`controles_5b3.py`, 15 comprobaciones, 0 llamadas)

| Control | Resultado |
|---|---|
| Los criterios quedaron guardados: propio 300 ms, global 2.000 ms, "1. Auth" NO APTO | PASA (3) |
| 6/6 secciones con texto | PASA |
| Las 6 mencionan 300 y **ninguna presenta 2.000 ms como su límite** | PASA (2) |
| **Detector de estilo en 0**, en el bloque por transacción y en el informe general | PASA (2) |
| El informe general nombra a "Auth" en 11 frases; **6 la juzgan contra sus 300 ms**; ninguna dice que cumple por estar bajo 2.000 ms | PASA (4) |

> **Tercera comprobación mía mal escrita.** Buscaba la etiqueta literal `"1. Auth"` en el
> texto general y encontraba **0 frases**: el control pasaba sin mirar nada. El modelo narra
> el flujo de negocio y escribe "Auth", sin el prefijo numérico — que es justo lo que pide
> §4.3. Corregida para buscar el nombre sin prefijo, y reforzada con una comprobación
> **positiva**: al menos una frase tiene que juzgarla contra sus 300 ms. Son 6.

### Regresiones sobre la ejecución nueva

- `verificar_etapa2.py` sobre `E5b-criterios`: **LAS CUATRO SALIDAS PASAN**.
- `criterios_5b2.py` sobre `E5b-criterios`: **TODO PASA**.
- Etapa 6 sobre `E3-estilo-pruebakinetix`: `export_alcance.py` y `capas_exportadas.py`
  **TODO PASA**.

> `export_alcance.py` no se puede correr sobre `E5b-criterios`: necesita 2 o más
> transacciones con informe y esta tiene una sola, por presupuesto. No es un fallo; es la
> prueba equivocada para este dato.

## 5. Una decisión visual que dejo señalada

Junto al nombre de la transacción sigue apareciendo el chip índigo **"criterios propios"**,
y el botón nuevo dice lo mismo en la última columna. Se ve así:

```
1. Auth  crítica  criterios propios   …   [Propios ▸]
```

**No lo he retirado**: D54 no lo pide y es una decisión visual de Fredy. Si al validar
prefiere que el botón sea el único indicador, es quitar una línea.

## 6. Presupuesto

| | |
|---|---|
| Llamadas a la IA autorizadas | 20 |
| **Gastadas** | **16** (10 generales + 6 del bloque de "1. Auth") |
| Sobrantes | 4 |

---

**Estado:** 5b.2 y 5b.3 implementadas y verificadas, pendiente validación de Fredy.
Ninguna condición de parada. Sigue 5b.4 — cierre.
