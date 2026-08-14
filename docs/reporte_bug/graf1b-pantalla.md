# GRAF1-B — Línea de máximos en Response Times del dashboard

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado, `tsc --noEmit` exit 0, HMR sin errores. **Pendiente: validación visual de Fredy** (criterio único de éxito).
**Alcance:** 1 archivo — `Dashboard.tsx` (PROTEGIDO, autorización acotada de Fredy). **+25 / −3 líneas.** Presupuesto ~25-30. Dentro.
**Base:** `docs/reporte_bug/graf1-fix-serie-dual.md` §2 (fila 4) y §4. Consume el `value_max` que entrega GRAF1-A.

---

## 1. Qué cambió (4 hunks, todos en la misma gráfica)

| Hunk | Línea | Cambio |
|---|---:|---|
| 1 | 37-38 | `const MAX_SUFFIX = ' (max)'` a nivel de módulo |
| 2 | 402-419 | `prepareMultiLineData(data, withMax = false)` — con el flag, además de `value` escribe `${label} (max)` desde `item.value_max` |
| 3 | 508-514 | Sólo Response Times llama con `true`; `rtMaxLabels` / `rtMaxKeys` derivan qué transacciones traen máximos |
| 4 | 1008-1020 | Segunda `<Line>` por transacción + `extractY` incluye los máximos |

### Representación elegida (y por qué)

```tsx
<Line dataKey={`${label} (max)`}
      stroke={getColorForIndex(labels.indexOf(label))}  // MISMO color que su promedio
      strokeWidth={0.8} strokeDasharray="2 3" strokeOpacity={0.85}
      dot={false} connectNulls legendType="none"
      hide={hiddenLinesResponseTimes.has(label)} />
```

- **Fina y punteada, mismo color que su promedio** — el criterio de legibilidad de §2 del reporte de alcance (promedio 1.5 px sólido vs máximo 0.8 px punteado).
- **Sin entrada duplicada en la leyenda:** `legendType="none"` excluye la serie del `payload` que Recharts entrega al `<Legend>`. `ScrollableLegend` construye sus entradas desde ese `payload` (`allKeys = payload.map(e => e.dataKey || e.value)`), así que **la leyenda sigue mostrando 3 entradas, no 6**, y el contador del botón maestro "Ocultar todas" sigue siendo correcto. Es la opción limpia en Recharts — más que un filtro manual en el componente de leyenda, que habría tocado código compartido con las otras gráficas.
- **Ocultar por leyenda apaga las dos líneas:** el `hide` del máximo lee `hiddenLinesResponseTimes.has(label)` — la clave del **promedio**, no la suya.
- **Tooltip:** el máximo sí aparece (el payload del tooltip es independiente del de la leyenda) como `token (max)`, ordenado por valor descendente — sale justo encima de su promedio. Es lo que se quiere al inspeccionar un pico.

### Eje Y

`YAxis domain={getYDomain('rtByLabel')}` devuelve `['auto','auto']` mientras Fredy no fije un zoom manual, y Recharts auto-escala sobre **todas** las series visibles → **los ~21 s entran en el dominio**. Además `ChartYAxisZoom` ahora recibe `extractY(data, [...labels, ...rtMaxKeys])`, de modo que el control de zoom conoce el rango real (antes su tope habría sido ~12 s, el máximo del promedio).

### Tolerancia a ausencia de `value_max`

Dos guardas, ambas silenciosas:
1. En el builder: `if (withMax && item.value_max != null)` — si no viene, **no se crea la clave**.
2. En el render: `rtMaxLabels` filtra por transacciones que tengan al menos un punto con máximo; si ninguna lo trae, el `.map` no pinta nada y la gráfica queda **exactamente como hoy**.

Ejecuciones cacheadas o previas a GRAF1-A pintan sólo el promedio, sin error ni hueco en la leyenda.

---

## 2. Verificación de que las demás gráficas NO cambiaron

El builder es compartido por tres gráficas. El parámetro es **opt-in con default `false`**:

```
508:  const responseTimesByLabel = prepareMultiLineData(charts.response_times_by_label || [], true);
509:  const tpsByLabel          = prepareMultiLineData(charts.tps_by_label || []);
510:  const codesPerSecond      = prepareMultiLineData(charts.codes_per_second || []);
```

**Sólo la línea 508 activa el flag.** TPS por Transacción y Códigos por Segundo entran por la misma ruta de código que antes: con `withMax = false` el `if` nunca se cumple y el objeto por timestamp queda idéntico byte a byte.

`MAX_SUFFIX`, `rtMaxLabels` y `rtMaxKeys` sólo aparecen en las líneas 38, 417, 512-514 y 1012-1020 — todas dentro del bloque de Response Times. **0 consumidores fuera de `Dashboard.tsx`** (`prepareMultiLineData` es local al componente).

Las otras 7 gráficas del panel (Response Time Over Time, Throughput, Latencia, Error Rate, Hilos Activos, Códigos/s, TPS por label) no se tocaron: los hunks 3 y 4 son las únicas ediciones fuera del builder, y ambas están dentro del `<div>` de "Response Times por Transaccion".

### Regla 16 (hooks antes de early returns)

**No se añadió ningún hook.** `rtMaxLabels` / `rtMaxKeys` son `const` planas —no `useMemo`— colocadas junto a las demás derivaciones de datos, después de los early returns, exactamente donde ya vivían `responseTimesByLabel` y compañía. El orden de hooks del componente no cambia. Verificado: `git diff | grep -c "^+.*use(State|Effect|Memo|Callback|Ref)("` → **0**.

---

## 3. Validación ejecutada

| Check | Resultado |
|---|---|
| `npx tsc --noEmit` | **exit 0** |
| Vite HMR (contenedor `jmeter_frontend`) | `hmr update /src/components/dashboard/Dashboard.tsx` sin errores |
| `GET http://localhost:5173/` | **200** |
| Diff | 4 hunks, +25/−3, todos en la gráfica objetivo |
| Backup | `Dashboard.tsx.bak_graf1b_20260814_100707` |

**No se tocaron los exports** (PDF, HTML, informe integrado) — eso es GRAF1-C. Hoy el dashboard muestra los máximos y los exports **todavía no**: es la inconsistencia esperada entre B y C.

---

## 4. ⚠️ Punto (2) del prompt NO implementado — falta confirmación

El prompt condicionaba el cambio de umbral en `gemini.py` (alerta de variabilidad disparando también con `max >= 10000ms` absolutos) a que *"el mensaje que acompaña este prompt lo confirme"*. **Ese mensaje no llegó con la confirmación**, así que **no lo apliqué** — `gemini.py` queda como lo dejó GRAF1-A (`P99/avg > 3x` **o** `max/avg > 10x`).

Recordatorio del caso que motiva la opción 2: `Adapter VerifMethod` tiene `max = 21.058 ms` pero `max/avg = 7,2x` (< 10), así que **no dispara la alerta** aunque su máximo sea de 21 s. Con umbral absoluto de 10.000 ms sí lo haría. Es 1 línea:

```python
if tx['avg'] > 0 and (tx['p99'] / tx['avg'] > 3 or tx['max'] / tx['avg'] > 10 or tx['max'] >= 10000):
```

Dilo y lo aplico en 2 minutos.

---

## 5. Qué debe ver Fredy al validar

Ejecución **115346ea** (Coomeva 31-jul), gráfica "Response Times por Transaccion":

1. **3 líneas sólidas** (promedios) + **3 punteadas finas** del mismo color.
2. El eje Y llega a **~21.000 ms** — antes topaba en ~12.000 (y en ~6.100 antes de GRAF1-A).
3. Los picos de `token` (21.060 ms) y `Adapter VerifMethod` (21.058 ms) **deben verse** como espigas punteadas. `Adapter SendCode` (388 ms) queda pegado al suelo.
4. La leyenda sigue con **3 entradas**; al ocultar una, desaparecen su sólida y su punteada juntas.
5. Comparación contra su gráfica de JMeter a 500 ms: las espigas deben coincidir en posición temporal.
6. **Legibilidad con 3 transacciones** — el juicio pendiente. Si con 3 transacciones ya satura, el candidato a ajuste es la opacidad (0.85) o el patrón de puntos (`"2 3"`), ambos de un carácter.

Pendiente del backlog GRAF1: **C** — dual en PDF, HTML e informe integrado (incluye el 5º consumidor `integrated_report.py` y el `value_max` que `apply_top_n_aggregation` descarta en la serie "Resto" con ≥15 labels).

---

## 6. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- Sin `docker compose build` — el contenedor de frontend recogió el cambio por HMR (volumen montado).
- Ningún análisis IA ejecutado; cuota intacta.
- Backup `.bak_graf1b_20260814_100707` junto al archivo original.
