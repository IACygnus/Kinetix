0572b30 · 2026-09-16

# ETAPA 2 — PARADA por condición C3 (diff mayor que lo estimado)

La extracción pura de 2.6 está hecha, **verificada y commiteada** (`0572b30`). Me detengo
**antes** de los cambios funcionales porque el diff de `Dashboard.tsx` supera mi estimación por
encima del margen que fija C3.

---

## La medición

| | Líneas |
|---|---|
| Estimación del reporte 13 para `Dashboard.tsx` | **~120-160** |
| Umbral de C3 (estimación + 50 %) | **240** |
| **Diff real** (18 insertadas + 282 eliminadas) | **300** |

Son un **87 % por encima** del extremo alto de mi estimación. C3 dice parar, y paro.

## Por qué me quedé corto

Estimé solo el bloque de gráficas (141 líneas). **No conté los tres helpers** —
`CustomChartTooltip`, `ScrollableLegend` y `getXAxisProps`, más sus tipos: **130 líneas** — que
solo se usaban dentro de ese bloque y tenían que viajar con él. Es un error mío de medición en el
diagnóstico, no un ensanchamiento del alcance: lo que se movió es exactamente lo que el reporte
13 describía.

## Lo que el número no dice

De las 282 líneas eliminadas de `Dashboard.tsx`, **271 están movidas**, no borradas: viven en
`ReportBody.tsx`. Solo ~11 son bajas reales (imports que quedaron sin uso y `MAX_SUFFIX`, que
subió a `chartConfig.ts` para evitar un import circular).

`Dashboard.tsx` pasa de **1.317 a 1.053 líneas** y queda como orquestador.

## La equivalencia sí está demostrada

Con Playwright y Chromium, sobre `ff186cc7` y `E1.3-baseline-2`:

```
DOM normalizado     identico en las dos ejecuciones
pixeles             0.000 %  (umbral 1 %; ruido de base medido 0.000-0.348 %)
llamadas de datos   identicas
PNG de pagina completa, byte a byte del mismo tamano
tsc --noEmit        exit 0
```

El refactor **no cambió nada visible ni funcional**. Eso está fuera de duda.

---

## Opciones

**A. Ampliar la estimación y continuar (mi recomendación).**
El exceso es un fallo de mi estimación, no trabajo de más: se movió lo que había que mover, la
equivalencia está probada al 0,000 % y el archivo quedó más pequeño y más simple. Continuar
significa entrar en los cambios funcionales de 2.6 (Throughput, orden D17, alcance por
transacción, D22).

**B. Rehacer la extracción más pequeña.**
Dejar los tres helpers en `Dashboard.tsx` y exportarlos. Bajaría el diff a ~170 líneas, pero
crea un **import circular** (`Dashboard → ReportBody → Dashboard`), que es frágil con Vite y
peor solución técnica. No la recomiendo.

**C. Parar la etapa aquí.**
`0572b30` es un refactor equivalente y seguro; la aplicación funciona igual que antes. Se podría
dejar así y retomar los cambios funcionales más adelante.

---

## Lo que ya sé que costarán los otros tres protegidos

Para que decidas con el cuadro completo, reviso mis estimaciones del reporte 13 con lo aprendido:

| Archivo | Estimación reporte 13 | Riesgo de quedarme corto |
|---|---|---|
| `report_generator.py` | ~150-200 | **Alto.** Igual que aquí, hay helpers (`transaction_reports_html`, `TRANSACTION_CHARTS`, `_SIN_TEXTO`) que se moverán con el render |
| `export_html.py` | ~120-160 | Medio |
| `export_pdf.py` | ~30-40 | Bajo |

Si eliges A, propongo **subir esas tres estimaciones un 60 %** de entrada
(240-320 / 190-260 / 50-65) para no volver a pararnos por lo mismo, y que C3 siga midiendo
contra algo realista.
