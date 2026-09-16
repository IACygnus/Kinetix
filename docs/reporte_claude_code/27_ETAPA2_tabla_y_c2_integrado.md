c957047 · 2026-09-16

# ETAPA 2 — Tabla resumen por transacción (D15) y cableado C2 del integrado

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.

Dos requisitos de la etapa que faltaban: la tabla resumen filtrada dentro de cada bloque por
transacción, y la prueba de cableado del **tercer canal de textos**, el del informe
integrado.

---

## 1. La tabla resumen filtrada — `5323705` + `c957047`

v1.2 §1 pide que cada informe por transacción tenga «Tabla resumen (solo esa transacción)»
con **el mismo diseño** que el general. Hasta ahora el bloque empezaba directamente por el
análisis del resumen.

### Paso 1 — extracción pura (C1), `5323705`

`SummaryTable.tsx` (**nuevo, no protegido**): la tabla «Reporte Resumen» copiada tal cual de
`Dashboard.tsx`, con las mismas columnas.

| Prop | Para qué |
|---|---|
| `rows` | las filas de `by_label` de `/charts`, tal cual llegan |
| `durationSeconds` | el divisor del TPS cuando la fila no lo trae |
| `total` | la ejecución, para la fila **TOTAL PRINCIPALES**. Sin ella, esa fila no se pinta |

`Dashboard.tsx` pasa de 63 líneas de tabla a una llamada de 5. El único cambio de forma es el
helper `num()`, que sustituye la misma expresión ternaria repetida siete veces.

**Equivalencia demostrada:** DOM normalizado **idéntico**, **0,000 %** de píxeles, mismas
llamadas de datos, 26 gráficas.

### Paso 2 — la tabla dentro del bloque, `c957047`

- `Dashboard.tsx` (protegido, **6 líneas**): pasa a `TransactionReportSection` las filas de
  `by_label` **que ya pidió** a `/charts`, y la duración. Se pasan en vez de que el bloque
  vuelva a pedir el endpoint entero (850 KB) para leer una fila.
- `TransactionReportSection.tsx`: `<SummaryTable rows={[fila]} />` encima del análisis del
  resumen. **Sin fila TOTAL**: con una sola transacción sería la misma cifra repetida.

### Validación — `e2e/tabla_por_transaccion.py`, 15/15

Sobre la pantalla real de `ff186cc7`:

```
PASA | la tabla general trae 6 transacciones
PASA | hay 3 bloque(s) por transaccion
PASA | [cada bloque] tiene UNA tabla resumen
PASA | [cada bloque] la tabla tiene UNA fila y ninguna de TOTAL
PASA | [cada bloque] sus celdas son las mismas que en la tabla general
PASA | [cada bloque] mismas columnas que el general
PASA | siguen siendo 26 graficas (26)
```

La comparación es celda a celda contra la fila de esa transacción en la tabla general, no
«se parece».

> La prueba tropezó primero con **otra** tabla: la de criterios por transacción (KNX-09), que
> va antes en la página y tiene otras columnas. El selector ahora busca la tabla titulada
> «Reporte Resumen».

---

## 2. Cableado C2 del informe integrado

En 2.11 se probó el canal de la pantalla individual (general vs. transacción). Faltaba el
**tercero**: los *overrides* del integrado, que permiten que un informe integrado diga algo
distinto **sin pisar** el informe individual.

`e2e/cableado_c2_integrado.py`, sobre la pantalla real del integrado `fa724249` — **7 de 7**:

```
PASA | el informe trae secciones de ejecucion
PASA | la caja de Latency Over Time existe en el integrado
PASA | la edicion se guarda en sections[].overrides.analysis del integrado
PASA | la ejecucion original (test_executions) NO cambia
PASA | al recargar la pagina, el texto editado sigue ahi
PASA | el texto del integrado queda sin la marca
PASA | la ejecucion original sigue exactamente igual que al empezar
```

### Confirmado también por `SELECT`

```
override de 02da3924 en sections[].overrides.analysis.ai_analysis_latency : 933 caracteres
test_executions.ai_analysis_latency de esa ejecucion                      : 905 caracteres
test_executions.updated_at                                                : 2026-08-11
```

Los dos textos son distintos y conviven; y el `updated_at` de la ejecución **sigue siendo de
agosto**: la prueba no la tocó.

---

## 3. La verificación de la etapa pasa de 8 a 10 pasos

`verificar_etapa2.py` incorpora los dos nuevos (`2b` la tabla, `9` el C2 del integrado). Las
herramientas viven en `C:\proyectos\Kinetix_pruebas\e2e\` — fuera del repo a propósito: en el
repositorio solo van los reportes.
