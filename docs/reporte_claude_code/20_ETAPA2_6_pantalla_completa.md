adeebcc · 2026-09-16

# ETAPA 2.6 — La pantalla, completa

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.

Cierra 2.6. Lo que se ve en pantalla ya cumple la especificación v1.2 salvo lo que se
declara pendiente en §5. El PDF, el HTML y el integrado siguen como estaban (2.7 a 2.9).

---

## 1. Los commits

| Commit | Qué |
|---|---|
| `0572b30` (2.6a) | Extracción pura a `ReportBody.tsx`. Equivalencia demostrada al 0,000 % |
| `52fc170` (2.6b) | D19 y D18 en pantalla; 6 secciones, títulos D16, textos D22, sin acordeón |
| `d5c69cd` (2.6c) | Fuera el encabezado de grupo «Informe por Transaccion» |
| `3d18fe1` (2.6d) | Carga en serie + `asyncio.to_thread` en `/transaction-charts` |
| `a0469c9` (2.6e) | `ReportBody` con alcance de transacción (D21) y cableado C2 |
| `adeebcc` (2.6f) | Las transacciones, antes de las conclusiones (D17) en pantalla |

---

## 2. El encabezado de grupo (ajuste 1)

Se va el `<h2>` «Informe por Transaccion» y con él la barra navy y la tarjeta que
envolvía a todos los bloques: esa tarjeta era justamente lo que pedía un título de
grupo. Tras el informe general, cada bloque empieza por el nombre exacto de la
transacción (v1.2 §0 y §1).

Sobrevive el botón **Generar todas (N)**, que es función y no encabezado; queda
alineado a la derecha, encima de los bloques. Los avisos de generación automática y de
cola no cambian.

Tildes corregidas en lo que se tocó: «Resumen de la transacción», «Análisis — …»,
«Cargando gráficas y textos…».

---

## 3. Carga en serie y event loop libre (ajuste 2)

Dos causas distintas, las dos reales, y se arreglan las dos:

1. **Frontend.** El efecto pedía las transacciones **a la vez**. Ahora recorre los
   labels uno tras otro, con un `Set` de intentados que se marca **antes** del `await`
   —eso es lo que impide que un re-render dispare dos veces la misma carga—. El efecto
   ya no depende de `datos`, así que no se reprograma en cada cambio de estado.
2. **Backend** (`upload.py`, no protegido). En `/transaction-charts`, el parseo del JTL
   y el cálculo de las 5 series van juntos a `asyncio.to_thread`: un solo salto de hilo
   por petición, el mismo patrón de D1/1.4. Antes corrían **dentro** del event loop.
   `jtl_parser.py` está protegido y **no se toca**: se envuelve la llamada, no el parser.

### Medición

Sonda a `/auth/me` cada 100 ms durante la carga, con
`Kinetix_pruebas/e2e/medir_serie.py`. La columna que importa es el **peor latido**:

| | ff186cc7 (3 tx · 10.075 muestras) | Coomeva `115346ea` (1 tx · 25.773 muestras · 1.800 s) |
|---|---|---|
| antes, en paralelo (lo que hacía la pantalla) | **200 ms — FALLA** | 91 ms |
| antes, en serie | 45 ms | 99 ms |
| **después, en serie** | **6 ms** | **11 ms** |
| después, en paralelo | 52 ms | 8 ms |

Carga total de los 3 bloques en serie: **127-159 ms** (30-56 ms de servidor cada uno).
Coomeva: 119-150 ms. El límite de **< 100 ms** se cumple en las dos ejecuciones.

Los dos arreglos son necesarios: el paralelo multiplicaba el parseo, y el parseo
síncrono dejaba sordo al proceso aunque fuese uno solo (los 99 ms de Coomeva son un
único parseo de 25.773 muestras bloqueando el loop).

---

## 4. `ReportBody` por transacción (ajuste 3) — D21 y C2

**Aquí muere la plantilla paralela.** Desaparece `GraficaTx`, la gráfica propia de
`TransactionReportSection` (260 px de alto, ejes, tooltip y leyenda propios), que era
la razón de que el informe por transacción no se pareciera al general.

| Pieza nueva | Qué hace |
|---|---|
| `seriesParaReportBody(label, series)` | Adapta las 5 series de `/transaction-charts` a las estructuras del general: `displayTime`, serie dual avg/max con `MAX_SUFFIX`, códigos pivotados a una columna por código. Solo cambia la forma del dato |
| `BloqueGraficasTx` | Monta `<ReportBody scope={{kind:'transaction', label}}>`. Es un componente aparte porque cada bloque necesita su estado (leyendas plegadas, zoom de eje Y) y los hooks no pueden vivir dentro de un `.map`. Regla 16: todos los hooks antes de cualquier return |
| `SECCION_DE_CAMPO` | **El cableado C2.** Traduce el campo que usa `ReportBody` (`ai_analysis_latency`…) a la sección de `transaction_chart_analyses` (`chart_latency`…) |

`AnalysisBox` se crea con `useCallback` de dependencias vacías: si su identidad
cambiara en cada render, React desmontaría el textarea y se perdería el foco al
escribir.

### Prueba de cableado (C2), Playwright sobre la pantalla real

`Kinetix_pruebas/e2e/cableado_c2.py` — **10 de 10**, y deja los dos textos como
estaban:

```
PASA | la caja de Latency Over Time existe dentro del bloque de 4. Get_Booking_Id
PASA | la caja de Latency Over Time existe en el informe general
PASA | editar dentro del bloque escribe en transaction_chart_analyses/chart_latency
PASA | esa edicion NO toca el campo general ai_analysis_latency
PASA | esa edicion NO toca las demas secciones de la transaccion
PASA | editar en el informe general escribe en ai_analysis_latency
PASA | esa edicion NO toca la fila por transaccion
PASA | el texto de la transaccion queda como estaba
PASA | el texto general queda como estaba
```

> **Aviso para quien reutilice la sesión de Playwright:** `csrf_token` **no** puede
> guardarse como `httpOnly`. El interceptor de axios lo lee de `document.cookie`; si
> está oculto, la cabecera `X-CSRF-Token` viaja vacía, toda mutación responde **403** y
> el navegador lo reporta como error de **CORS** (la respuesta del middleware no lleva
> `Access-Control-Allow-Origin`). Se perdió un rato con este falso positivo y ya está
> corregido en `medir_serie.py`.

### Recuento de gráficas

Referencia fijada **a mano en 26 antes de capturar**. La captura dio **26** a la
primera: 11 generales (12 − Throughput) + 5 × 3 transacciones. No hubo que investigar
ni ajustar nada.

---

## 5. D17 en pantalla y lo que queda

`Dashboard.tsx` (protegido, autorizado): el montaje de `TransactionReportSection` sube
por encima del bloque de conclusiones. **11 líneas** (6 añadidas, 5 quitadas), 5 de
ellas el comentario, que se reescribe porque el viejo decía «despues de las secciones
generales» y habría quedado mintiendo.

Comprobado en la pantalla real: transacciones en `y` = 10.353 · 16.450 · 22.547;
Conclusiones y Recomendaciones en `y` = 28.655. **26 gráficas.**

### Pendiente declarado

| Qué | Dónde se hace |
|---|---|
| **Tabla resumen filtrada** a cada transacción (v1.2 §1) | El dato existe en `by_label` de `/charts`; falta bajarlo al bloque. No entraba en los tres ajustes pedidos |
| `throughputData` y `analysisThroughput` siguen viajando en el `ctx` | Se quitan en el próximo paso que ya toque `Dashboard.tsx` |
| Columnas del panel de selección y criterios por fila (v1.2 §2) | No es 2.6 |
| Control de capas avg/max y tooltip de una sola capa (v1.2 §3) | No es 2.6 |
| D17, D19, D21, D22, D24 en PDF, HTML e integrado | 2.7, 2.8 y 2.9 |

---

## 6. Validación

| Qué | Resultado |
|---|---|
| `tsc --noEmit` | exit 0 en cada commit |
| `py_compile` de `upload.py` | OK |
| Cableado C2 (Playwright) | 10/10, datos restituidos |
| Sonda `/auth/me` durante la carga | peor latido 6-11 ms (límite 100 ms) |
| Gráficas en la página | 26, contra referencia fijada a mano |
| Orden D17 en pantalla | transacciones antes de conclusiones |
| Llamadas reales a la IA | **0** |

**Falta la validación visual de Fredy**, que es el único criterio de éxito (regla 9).
