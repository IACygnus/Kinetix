# N4.7 — Pantalla del mini-informe por transacción

**Fecha:** 2026-08-19
**Commit:** `7a5e95a666489ea7b9084789f422bb765ed82dc7` — *N4.7: pantalla del mini-informe por transaccion*
**Push:** `github` (`3425866..7a5e95a`, rama `backup-trabajo-local`). **`origin` (Azure) no se tocó.**
**Llamadas de IA:** **0.** Se usaron los 8 textos de `token` ya guardados.
**Archivos tocados:** **4** (máximo 5). **Backups:** `.bak_n47_20260819_215340`.
**Validación funcional: pendiente de Fredy.** Aquí solo hay `tsc`, `py_compile` y verificación por lectura.

---

## 1. Qué se hizo

| Archivo | Diff | Qué |
|---|---|---|
| `frontend/src/components/dashboard/TransactionReportSection.tsx` | **nuevo, 345 líneas** | El componente: 5 gráficas, 8 textos editables, botones, cola y sondeo |
| `backend/app/api/v1/endpoints/upload.py` | **+60 / −0** | `PUT …/transaction-report/{section}` + `report_labels` en el GET de N3.4 |
| `backend/app/services/jtl/transaction_series.py` | **+13 / −12** | N4.4b: `iterrows()` → `zip()` en las 5 series |
| `frontend/src/components/dashboard/Dashboard.tsx` | **+6 / −0** | Solo el montaje |

### 1.1 El presupuesto, otra vez por encima

Pediste 160-220 líneas; el neto es **~424**. El desglose de las 345 del componente:

| Parte | Líneas |
|---|---|
| JSX de la tarjeta, cabecera, progreso y las 8 secciones | ~110 |
| Gráfica reutilizable (pivote de códigos, serie dual, ejes, leyenda) | ~50 |
| Estado, carga, cola, sondeo y guardado | ~90 |
| Editor con autoguardado e indicador | ~45 |
| Constantes, tipos, comentarios y cabecera | ~50 |

No hay forma honesta de meter cinco gráficas de Recharts, ocho editores con
autoguardado, una cola en serie y un sondeo tolerante a fallos en 220 líneas sin
dejarlo ilegible. Lo declaro en vez de comprimirlo. Los archivos sí se
respetaron: 4 de 5.

---

## 2. Dashboard.tsx: el diff COMPLETO

Autorizaste tocarlo solo para el montaje. Son **6 líneas añadidas, cero
modificadas, cero borradas**:

```diff
@@ -9,6 +9,7 @@ import { testAPI } from '../../services/api';
 // LoadingSpinner replaced with inline loading indicator for better UX
 // Monitoring, Evidence, Capacity, and Comparison moved to standalone pages (R3-A)
 import ChartYAxisZoom from './ChartYAxisZoom';
+import TransactionReportSection from './TransactionReportSection';   // N4.7
 import {
   CHART_LAYOUT,
   CHART_LABELS,
@@ -1238,6 +1239,11 @@ export default function Dashboard({ executionId, onLogout: _onLogout, onBack, em
         </div>
         )}

+        {/* N4.7: mini-informe por transaccion critica — despues de las secciones
+            generales. Se monta solo aqui; el componente decide si hay algo que
+            mostrar y no altera nada de lo anterior. */}
+        {!embedded && <TransactionReportSection executionId={executionId} />}
+
         {/* PDF PROGRESS */}
         {isExportingPDF && (
           <div className="mb-6 p-5 bg-blue-50 border-2 border-blue-200 rounded-2xl">
```

**No se pudo evitar tocarlo.** El reporte individual se renderiza entero dentro
de ese componente y no expone ningún punto de extensión: no hay `children`, ni
slots, ni un contenedor padre que envuelva las secciones. La alternativa era
montarlo desde `ReportView.tsx`, pero entonces aparecería *debajo* del reporte
completo y no "después de las secciones generales", que es donde lo pediste.

Queda **fuera del informe integrado** (`!embedded`): ahí el reporte se embebe
como sección y el mini-informe tiene su propio sprint (N4.9).

**Posición:** después de Conclusiones y Recomendaciones, antes del progreso de
PDF. Nada de lo anterior cambia de sitio.

---

## 3. La pantalla

### 3.1 Qué transacciones aparecen

El componente pide `GET /executions/{id}/transaction-analyses` y usa la **unión**
de dos listas:

- las marcadas como críticas en el upload (N3.4), y
- las que ya tienen mini-informe generado — campo `report_labels`, añadido aquí.

La segunda no estaba prevista y resultó imprescindible: la ejecución de Coomeva
donde vive el mini-informe de `token` **no tiene ninguna transacción marcada**
(es anterior al premarcado), así que sin esta unión la pantalla habría salido
vacía justo en la ejecución con los datos. Comprobado contra la base:

```
--- Coomeva 115346ea (mini-informe generado) ---
report_labels: ['token'] | criticas: []
--- caso 1 5381abec (2 criticas, sin mini-informe) ---
report_labels: [] | criticas: ['token', 'Adapter VerifMethod']
```

Sin ninguna de las dos, el componente **no renderiza nada** (`return null`
después de todos los hooks, regla 16). El reporte queda exactamente como estaba.

### 3.2 Estructura de cada transacción

Tarjeta plegable por transacción. Al abrirla se piden en paralelo las series
(N4.4) y los textos (N4.6 GET), y se muestran las 8 secciones en orden, cada
gráfica encima de su texto:

| Sección | Gráfica encima |
|---|---|
| Resumen de la transacción | — |
| Tiempos de respuesta | serie dual promedio + máximo (GRAF1: el pico se ve) |
| Latencia | serie de latencia |
| Tasa de error | % por intervalo |
| Códigos de respuesta | una línea por código, pivotando las filas del endpoint |
| Transacciones por segundo | TPS |
| Conclusiones | — |
| Recomendaciones | — |

### 3.3 Botones y cola

- **"Generar mini-informe"** por transacción (dice "Regenerar" si ya tiene textos).
- **"Generar todas (N)"** en la cabecera: llena una cola y la consume **en serie**,
  una llamada por transacción, como decidió el CTO. Mientras hay cola o
  generación en curso, todos los botones se deshabilitan; no hay forma de lanzar
  dos a la vez.

La cola avanza en el `finally` de cada generación, así que **una transacción que
falla no bloquea las siguientes**: se muestra su error y se pasa a la siguiente.

### 3.4 Indicador de progreso

Mientras corre, la tarjeta muestra:

```
Generando 3 de 8 — token · 45 s
[barra de progreso]
Faltan: Analisis — Codigos de respuesta, Conclusiones, ...
```

El número sale de sondear cada 4 s el `GET …/transaction-report`, que devuelve
`progress: {done, total, persisted, pending}` — el mecanismo que N4.6 dejó
preparado commiteando sección por sección. Los segundos los lleva un reloj
propio. Al terminar, `cargar()` refresca gráficas y textos **sin recargar la
página**.

---

## 4. Tolerancia a fallos (verificación por lectura)

Cinco caminos por los que el sondeo puede romperse y qué hace cada uno:

| Situación | Comportamiento |
|---|---|
| El GET de progreso falla una o dos veces | Se ignora; el contador de fallos se reinicia al primer acierto |
| Falla **3 veces seguidas** | Se corta el sondeo y aparece: *"No se pudo consultar el progreso. Lo que se ve abajo es lo ultimo que quedo guardado; la generacion puede seguir en el servidor."* El usuario ve las secciones reales, **no un spinner eterno** |
| El POST devuelve error (429, 500, timeout) | El `finally` limpia el estado de generación pase lo que pase, refresca desde la base y avanza la cola; el detalle del error se muestra en rojo |
| El JTL original ya no está en disco | Las series fallan pero los textos se cargan igual (`Promise.allSettled`): se ve el aviso de gráficas y los 8 textos siguen editables |
| El usuario cierra la pestaña a medias | El backend sigue; al volver a abrir, el GET muestra las secciones ya guardadas y el botón dice "Regenerar" |

Los dos `setInterval` (sonda y reloj) se limpian en el `return` del efecto, así
que cambiar de transacción o desmontar el componente no deja temporizadores
vivos.

---

## 5. Textos editables (patrón F3/R1/R2)

Cada uno de los 8 textos es un `textarea` con:

- **debounce de 1.800 ms** al escribir + guardado al perder el foco,
- indicador propio: *Autoguardado activo · Guardando... · Guardado · Error al guardar*,
- botón **Reintentar** si el guardado falla,
- etiqueta **"editado a mano"** cuando la sección tiene `is_edited`.

### 5.1 El endpoint que faltaba

N4.6 §8 avisaba de que no existía. Se creó aquí:

```
PUT /api/v1/executions/{id}/transaction-report/{section}?label=...
body: {"ai_analysis": "..."}
```

Rol `admin | analyst`. Marca `is_edited=true` y `ai_analysis_updated_at`, igual
que el consolidado desde F5. **Si la sección no tiene fila, la crea**: editar no
puede fallar por un texto que la IA nunca llegó a generar.

Probado sin gastar IA, contra una ejecución de prueba:

```
$ PUT .../transaction-report/summary?label=token
{"section":"summary","label":"token","is_edited":true,"ai_analysis_updated_at":"2026-08-20T02:58:50.975787"}

 label | section | is_edited |                     texto                     | con_fecha
-------+---------+-----------+-----------------------------------------------+-----------
 token | summary | t         | PRUEBA N4.7 - edicion manual de una seccion s | t

$ PUT .../transaction-report/inventada?label=token
{"detail":"Seccion desconocida: inventada. Validas: summary, chart_response_times, ..."}
```

La fila de prueba se borró (`DELETE 1`); la ejecución quedó con 0 filas.

Un detalle encontrado al probar: `generated_at` lleva `default=datetime.utcnow`
en el modelo, así que una sección creada por edición manual queda con fecha
aunque la IA no la haya tocado. En vez de forzar `NULL` desde el endpoint, la
pantalla **solo muestra la marca "IA hh:mm" cuando `is_edited` es falso**. Un
texto escrito a mano nunca se atribuye a la IA.

---

## 6. N4.4b absorbido: `iterrows()` → `zip()`

Las 5 series pasaron a construirse con `zip()` sobre las columnas. `iterrows()`
crea una `Series` de pandas por fila; con ~1.666 buckets por serie, eso es tiempo
que se nota al abrir una transacción tras otra.

**Salida byte-idéntica**, comprobada contra el backup del propio archivo sobre el
JTL real de Coomeva (25.773 muestras), en las 3 transacciones:

```
token
  puntos totales: 8353 | bytes JSON: 515659
  IDENTICO: True  (hash viejo=4170225448626755434 nuevo=4170225448626755434)
  iterrows:   351.6 ms | zip:    47.5 ms | x7.4 mas rapido

Adapter VerifMethod
  puntos totales: 8303 | bytes JSON: 517398
  IDENTICO: True  (hash viejo=-7611206598151830927 nuevo=-7611206598151830927)
  iterrows:   387.4 ms | zip:    36.4 ms | x10.6 mas rapido

Adapter SendCode
  puntos totales: 8328 | bytes JSON: 513047
  IDENTICO: True  (hash viejo=5431739211132741730 nuevo=5431739211132741730)
  iterrows:   368.9 ms | zip:    62.3 ms | x5.9 mas rapido
```

Mismo JSON exacto (comparado con `json.dumps(sort_keys=True)` y su hash), entre
**6 y 11 veces más rápido**. El endpoint completo, que además parsea el JTL,
respondía en 769 ms antes; el cálculo de series ya no es lo que pesa.

---

## 7. Validación técnica

```
$ npx tsc --noEmit          -> sin errores
$ python -m py_compile upload.py transaction_series.py   -> OK
$ docker restart jmeter_backend                          -> sin build, arranque limpio
$ curl /openapi.json | grep transaction-report
POST /api/v1/executions/{execution_id}/transaction-report
GET  /api/v1/executions/{execution_id}/transaction-report
PUT  /api/v1/executions/{execution_id}/transaction-report/{section}
```

Vite recompiló el componente nuevo y el `Dashboard.tsx` modificado sin errores
(`hmr update /src/components/dashboard/Dashboard.tsx` en el log, y el módulo
nuevo se sirve transformado).

**Regla 16 respetada:** el único `return null` del componente va después de los
7 `useState`, los 5 `useEffect` y los 3 `useCallback`.

---

## 8. Lo que tiene que validar Fredy (visual, único criterio de éxito)

**En la ejecución de Coomeva** `24342-Coomeva_SendCode_Performance`
(`115346ea…`, la del 13 de agosto con el JTL del 31-jul):

1. Bajar hasta después de Conclusiones y Recomendaciones → aparece
   **"Mini-informe por Transaccion"** con la tarjeta de `token` ("8 de 8 secciones").
2. Abrirla → 5 gráficas y los 8 textos ya generados (los del reporte 042).
3. Editar cualquiera de los 8, esperar ~2 s → *Guardando... → Guardado*, y la
   etiqueta "editado a mano". Recargar la página: el texto editado sigue ahí.

**En la ejecución `caso 1`** (`5381abec…`, que tiene `token` y
`Adapter VerifMethod` marcadas como críticas y **ningún** texto generado):

4. Pulsar "Generar mini-informe" en `Adapter VerifMethod` → ver el contador
   avanzar *Generando 1 de 8 … 8 de 8* durante ~110 s, la barra llenarse, y al
   terminar los textos aparecer solos. **Esto sí gasta 8 llamadas de IA.**
5. Opcional: "Generar todas (2)" para ver la cola en serie.

Se necesitan dos ejecuciones porque los datos están repartidos: los textos de
`token` viven en la de Coomeva, y las transacciones marcadas están en `caso 1`.
No fabriqué filas para juntarlo todo en una.

---

## 9. Lo que este sprint NO hizo

- **No lo probé funcionalmente en el navegador.** `tsc` verde no es una pantalla
  que funcione; eso lo dice tu validación visual.
- **No aparece en el informe integrado** (`embedded`): es N4.9.
- **No sale en los exports** PDF ni HTML: son N4.8 y N4.9.
- **No hay botón para regenerar UNA sección**, aunque el backend ya lo soporta
  (`sections=` de N4.6b). La pantalla regenera las 8.
- **No hay borrado** de un mini-informe desde la interfaz.
- **No se tocó el bloque N3.5** de los exports ni el panel de transacciones
  críticas del upload.
- **El sondeo es cada 4 s por HTTP.** Con el WebSocket de métricas ya existente
  podría ser push, pero eso es maquinaria nueva para un caso de 8 eventos.

---

## 10. Estado del plan N4

| # | Sub-sprint | Estado |
|---|---|---|
| N4.2 | Diagnóstico read-only | ✅ 036, `d96c398` |
| N4.3 | Servicio de series | ✅ 037, `5168a48` |
| N4.4 | Endpoint de series | ✅ 038, `c7f389f` |
| N4.4b | `iterrows()` → `zip()` | ✅ **absorbido aquí** |
| N4.5 | Tabla `transaction_chart_analyses` | ✅ 039, `1879401` |
| N4.6 | Generación IA bajo demanda | ✅ 040, `d6ba2f7` |
| N4.6b | Latencia, formato numérico, pico | ✅ 041, `8245bff` |
| — | Mini-informe de `token` completo | ✅ 042, `3425866` |
| **N4.7** | **Pantalla + botón + progreso + edición** | ✅ **este reporte, `7a5e95a`** — pendiente tu validación visual |
| N4.8 | Export PDF con gráficas y textos | ⏳ 🔴 `report_generator.py` protegido |
| N4.9 | Export HTML e informe integrado | ⏳ 🔴 `export_html.py` bajo regla de memoria |

---

## 11. Cierre

```
$ git log -1 --format='%H %s'
7a5e95a666489ea7b9084789f422bb765ed82dc7 N4.7: pantalla del mini-informe por transaccion

$ git push github HEAD
   3425866..7a5e95a  HEAD -> backup-trabajo-local
```

El script de comprobación de `zip()` se borró del repositorio.

**Parado aquí. N4.8 no se encadenó.**
