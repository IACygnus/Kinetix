e1a5bc6 · 2026-09-16

# ETAPA 2.10 — Cuánto tiempo recorta la etapa

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.

El cálculo **no estima**: toma la telemetría real de las dos corridas de línea base de la
Etapa 1 (`baseline1.json`, `baseline2.json`, 70 llamadas con `outcome="ok"`) y le quita
exactamente las llamadas que la Etapa 2 ha retirado del producto.
Herramienta: `Kinetix_pruebas/e2e/proyeccion_2_10.py`.

> **AVISO (añadido después): esta proyección NO sirve como dato de la Etapa 2.**
> La línea base se midió con el `reasoning_effort` **por defecto**, y desde 2.2 la
> configuración está en **`low`**. Las llamadas que quedan no tardan lo que tardaban
> entonces, así que restar llamadas de aquel total mezcla dos configuraciones distintas.
> Lo único que esta proyección sigue demostrando es **cuántas llamadas se retiran y qué
> parte del tiempo ocupaban en aquella configuración**. El dato bueno es la corrida real:
> **reporte 28**.

---

## 1. Resultado

| | Corrida 1 | Corrida 2 |
|---|---|---|
| Llamadas de IA | 35 → **28** | 35 → **28** |
| Latencia total de IA | 351,6 s → **282,4 s** | 357,0 s → **279,6 s** |
| Ahorro | **69,2 s (19,7 %)** | **77,3 s (21,7 %)** |
| Tiempo percibido (T2−T0) | 354,3 s → **285,1 s** | 357,4 s → **280,1 s** |

**De ~5,9 minutos a ~4,7 minutos.** Una quinta parte del tiempo, sin tocar el modelo.

### De dónde sale

| Recorte | Llamadas | Coste medido |
|---|---|---|
| **D19** — gráfica Throughput Over Time (general) | 1 | 8,4-8,8 s |
| **D20** — conclusiones por transacción | 3 | 29,3-38,3 s |
| **D20** — recomendaciones por transacción | 3 | 30,6-31,2 s |

Las secciones por transacción pesan porque se multiplican por el número de transacciones:
con 3 transacciones son 6 llamadas, y con 6 transacciones serían 12. **El ahorro de D20
crece con el tamaño de la prueba; el de D19 es fijo.**

---

## 2. Lo que este número NO dice

- **No convierte 6 minutos en 40 segundos.** La especificación v1.2 §5 recuerda que el
  informe tardaba ~40 s y hoy tarda más de 5 minutos. Esta etapa recorta un 20 %; el resto
  está en el número de llamadas, la secuencialidad y el razonamiento del modelo — material
  de la Etapa 4, ya cuantificado en el reporte 10:
  - bajar el razonamiento a la mitad: **−1,6 min (≈27 %)** más;
  - el `SYSTEM_PROMPT` viaja **duplicado** en cada llamada, lo que estropea el caché.
- **No incluye el tiempo de parseo ni el de pintado.** Es latencia de IA, que es donde está
  el grueso: en las dos corridas, T2−T0 y la suma de latencias coinciden casi exactamente.
- **Es una proyección, no una corrida nueva.** Quita llamadas medidas de un total medido;
  no reejecuta nada. Las llamadas que quedan tienen el mismo prompt y el mismo tope de
  tokens que en la línea base, así que su latencia no tiene por qué cambiar — pero eso, de
  momento, es razonamiento, no medición.

---

## 3. Corrida real de confirmación — AUTORIZADA, ver reporte 28

Confirmar el número con una generación de verdad cuesta **28 llamadas reales** a `gpt-5.5`
(10 generales + 6 × 3 transacciones), unos **4,7 minutos** y consume cupo de presupuesto:
pasaría de **1/50 a 29/50**.

No la lanzo sin que Fredy lo diga. Cuando se autorice, la corrida sería la misma de la
Etapa 1 (`Kinetix_pruebas/etapa1_corrida.py`) sobre el mismo JTL, para que los números
sean comparables uno a uno con `baseline2.json`.

**Criterio de éxito propuesto:** 28 llamadas, latencia total entre **265 y 295 s** (la
proyección ±5 %, que es el doble de la variación natural entre corridas medida en el
reporte 10: 1,5 %).
