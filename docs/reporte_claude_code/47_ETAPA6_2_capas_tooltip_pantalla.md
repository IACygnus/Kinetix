f68d6a6 · 2026-09-17

# ETAPA 6.2 — Capas y tooltip en pantalla (D46, D47, D48)

**Llamadas reales a la IA: 0.** Se valida sobre `E3-estilo-pruebakinetix`
(`20bb2356-410d-465f-8717-c9a025e26e03`), un informe **ya generado**: la prueba solo lee
lo guardado y mueve controles de pantalla. Sin `docker build`.

---

## 1. Qué se implementó

### D46 — selector de capas por gráfica

Un control segmentado **"Ambas · Promedio · Máximo"** en la cabecera de cada gráfica con
serie dual. Hoy eso es **Response Times** y solo Response Times, en los dos alcances: una
en el informe general y una en cada bloque por transacción. En `E3-estilo-pruebakinetix`
son 4 selectores para 4 gráficas duales — la prueba lo comprueba contando las gráficas que
tienen trazo punteado, no confiando en el número.

Va en la cabecera, junto al título, y **no** dentro de `ChartYAxisZoom`: ese componente
devuelve `null` cuando la serie tiene menos de 5 puntos
(`ChartYAxisZoom.tsx:56`), y el selector no puede desaparecer con él.

### D47 — el tooltip, una línea por transacción

Antes la serie de máximos entraba en el `payload` de recharts como una serie más y el
tooltip la listaba aparte: `1. Auth — 405 ms` y debajo `1. Auth (max) — 414 ms`. Es el
duplicado que denuncia v1.2 §3.

Ahora `CustomChartTooltip` pliega el máximo dentro de la fila de su promedio:

```
ambas capas    1. Auth              405 ms (máx. 414 ms)
una sola capa  1. Auth              414 ms
```

La detección es por sufijo `MAX_SUFFIX` — **el mismo criterio** que ya usaba
`ScrollableLegend` para descartarlas de la leyenda (`ReportBody.tsx:88`), de modo que no
hay dos convenciones compitiendo. Las series apagadas en la leyenda se filtran
explícitamente con el `Set` de ocultas, además del filtro que ya hace recharts.

### D48 — memoria de sesión de pantalla

El estado es un `Record<idGrafica, 'ambas'|'promedio'|'maximo'>` en el hook nuevo
`useChartLayers.ts`. No se persiste: al recargar, todo vuelve a "Ambas" (comprobado).
El hook se instancia **en `Dashboard`** —el ancestro común del informe general y de los
bloques por transacción— porque al exportar hay que leer la selección de toda la pantalla,
no solo la del bloque que se esté mirando (D49, sub-paso 6.4).

El id de cada gráfica es `alcance|gráfica`: `general|rt`, `tx:4. Get_Booking_Id|rt`. Es el
mismo identificador que viajará al backend en 6.4, así que los dos lados no necesitan dos
vocabularios.

## 2. Archivos tocados

| Archivo | +/− | Protegido | Qué |
|---|---|---|---|
| `frontend/src/hooks/useChartLayers.ts` | **nuevo**, 78 | no | el estado de capas, el id de gráfica y el serializador para el export |
| `frontend/src/components/dashboard/ReportBody.tsx` | +105 / −9 | no | tooltip plegado, `SelectorCapas`, `hide` por capa, dos campos nuevos en `ReportBodyCtx` |
| `frontend/src/components/dashboard/TransactionReportSection.tsx` | +11 / −2 | no | recibe el control de Dashboard y lo reparte a cada bloque |
| `frontend/src/config/chartConfig.ts` | +12 / −4 | no | formato español explícito en el tooltip |
| `frontend/src/components/dashboard/Dashboard.tsx` | **+8 / −0** | **sí** | una importación, una línea de hook y dos líneas de paso |

**Presupuesto del protegido (reporte 46): ≤ 60 líneas en `Dashboard.tsx`. Reales: 8.**
Muy por debajo del umbral de parada. Condición C3 cumplida: las 8 son cambios reales, no
líneas movidas; no hubo ninguna extracción, así que C1 no llegó a aplicar.

Copias de seguridad: `*.bak_etapa6_6.2_20260917` de los cuatro archivos existentes.

## 3. Decisión técnica que declaro: el formato de las cifras

D47 pide "formato español" y da el ejemplo `422 ms (máx. 1.013 ms)`. El tooltip usaba
`toLocaleString(undefined, {minimumFractionDigits: 2})`, que tiene dos problemas:

1. **`undefined` = la configuración del navegador.** El mismo informe se veía
   `1,013.00 ms` en una máquina y `1.013,00 ms` en otra. Ahora la configuración regional
   es explícita: `es-CO`.
2. **Dos decimales de milisegundo es precisión inventada** y no es lo que pide el ejemplo
   de la decisión. `formatMs` pasa a cero decimales.

`formatTps`, `formatPercent` y `formatCount` conservan sus decimales y solo fijan el
idioma. El cambio vive en `chartConfig.ts` (no protegido) y afecta únicamente a los
tooltips de pantalla.

Segundo cambio declarado: el título de la gráfica pasó a **"Response Times por
Transacción"**, con tilde. Es trabajo de 6.5, pero la línea del título se reescribía de
todos modos para meter el selector y dejarla sin tilde para volver dos sub-pasos después
habría sido un diff peor.

## 4. Verificación

`capas_tooltip.py` — Playwright, Chromium dentro de `jmeter_backend`, **22 comprobaciones
sobre el informe real**:

```
docker exec -e KX_PWD=… jmeter_backend python3 /tmp/e2e/capas_tooltip.py \
    20bb2356-410d-465f-8717-c9a025e26e03
```

| Bloque | Resultado |
|---|---|
| **1. Dónde están los selectores** — 4 selectores para 4 gráficas con serie dual; todos en Response Times; el título con tilde | PASA (4) |
| **2. Las tres capas** — "Ambas" 6 sólidas + 6 punteadas · "Máximo" 0 + 6 · "Promedio" 6 + 0 · "Ambas" marcado por defecto | PASA (4) |
| **3. El tooltip** — 6 filas para 6 transacciones · ninguna "(max)" · sin nombres repetidos · las 6 pliegan su máximo · formato exacto `^[\d.,]+ ms \(máx\. [\d.,]+ ms\)$` · con una capa, solo ese valor | PASA (7) |
| **4. Capa y leyenda, ejes independientes** — apagar "1. Auth" quita sus dos capas (5+5), sigue apagada en "Máximo" (0+5) y no aparece en el tooltip | PASA (3) |
| **5. Selección por gráfica** — el bloque pasa a "Máximo" y el general se queda en "Ambas" (6+6); el tooltip del bloque trae 1 fila | PASA (4) |
| **6. Sin persistencia (D48)** — tras recargar, las 4 gráficas vuelven a "Ambas" | PASA |

Se cuentan **los trazos reales del SVG** (`path.recharts-line-curve`, punteados por
`stroke-dasharray`), no las clases del botón: recharts no pinta una `<Line hide>`, así que
contar trazos es contar lo que se ve.

Salida literal de la fila del tooltip con las dos capas:

```
1. Auth -> 405 ms (máx. 414 ms) | 2. Get Booking -> 200 ms (máx. 227 ms) |
5. Put_Update_Booking -> 107 ms (máx. 110 ms) | 3. Post Create_Booking -> 106 ms (máx. 121 ms) |
4. Get_Booking_Id -> 105 ms (máx. 111 ms) | 6. Delete_Booking_Id -> 104 ms (máx. 109 ms)
```

y con una sola capa:

```
1. Auth -> 414 ms | 2. Get Booking -> 227 ms | 3. Post Create_Booking -> 121 ms |
4. Get_Booking_Id -> 111 ms | 5. Put_Update_Booking -> 110 ms | 6. Delete_Booking_Id -> 109 ms
```

### Cableado C2 intacto

`cableado_c2.py` sobre la misma ejecución: **10 de 10 comprobaciones PASAN**. Editar
dentro de un bloque escribe en `transaction_chart_analyses/chart_latency` de esa
transacción y no toca el campo general; editar en el general escribe en
`ai_analysis_latency` y no toca la fila por transacción. La edición y el autoguardado
siguen exactamente como estaban.

### Compilación

`npx tsc --noEmit` dentro de `jmeter_frontend`: **sin errores**. No hace falta rebuild:
el compose de desarrollo monta `./frontend:/app` y Vite recarga solo.

## 5. Lo que NO se tocó

- Ninguna gráfica de una sola capa recibió selector: no tendría qué alternar.
- El zoom de eje Y sigue calculándose sobre las dos series aunque una esté apagada, para
  que cambiar de capa no mueva la escala bajo los pies de quien está mirando.
- La leyenda sigue listando transacciones, no capas: son dos ejes distintos y se compusieron
  sin pisarse (bloque 4 de la prueba).
- El informe integrado, el PDF y el HTML exportado: sin cambios en este sub-paso.

---

**Estado:** 6.2 implementada y verificada en pantalla, pendiente validación de Fredy.
Ninguna condición de parada activada. Sigue 6.3 — selector de exportación.
