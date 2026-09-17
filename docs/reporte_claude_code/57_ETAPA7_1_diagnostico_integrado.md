7972efc · 2026-09-17

# ETAPA 7.1 — Por qué el informe integrado se ve incompleto (read-only)

**Llamadas reales a la IA: 0.** Ningún archivo tocado. Se volvieron a exportar dos
integrados ya guardados y se midió la pantalla con Playwright; nada se generó.

---

## 1. El hallazgo que cambia el encuadre

No es que "falten los bloques por transacción en el integrado". Es que **la pantalla y los
exportados del integrado ya dicen cosas distintas hoy**:

| Canal | Bloques por transacción |
|---|---|
| **Pantalla** del informe integrado | **0** |
| **HTML exportado** del integrado | **los tiene todos** |
| **PDF exportado** del integrado | **los tiene todos** |

Medido sobre los dos integrados reales:

```
E3-estilo — integrado (8713aad1)
  HTML exportado : 627.795 chars · 3 bloques
                   ['4. Get_Booking_Id', '5. Put_Update_Booking', '6. Delete_Booking_Id']
  PDF exportado  : 3.085.026 bytes

E2-validacion + E1.3-baseline-2 (998090d0)
  HTML exportado : 988.880 chars · 6 bloques (3 de cada ejecución)
  PDF exportado  : 2.560.163 bytes
```

y la pantalla, con Playwright, sobre el mismo `8713aad1`:

```
individual (E3-estilo-pruebakinetix suelto) : 26 gráficas · 4 "Response Times por Tx" · 5 tablas resumen
integrado  (las dos ejecuciones)            : 21 gráficas · 2 "Response Times por Tx" · 4 tablas resumen
```

En el individual hay **4** títulos "Response Times por Transacción" = 1 del general + 3 de
los bloques. En el integrado hay **2** = uno por ejecución, los generales, y **ni un bloque
por transacción**.

**Consecuencia:** quien revisa el integrado en pantalla, aprueba un documento que al
exportarse trae secciones que no vio. Eso es lo que hay que cerrar, y explica por qué D57 y
D59 tienen que ir juntos.

## 2. La causa, en una línea

`frontend/src/components/dashboard/Dashboard.tsx:929`

```tsx
{!embedded && (
  <TransactionReportSection
    executionId={executionId}
    byLabel={charts.by_label || []}
    durationSeconds={execution.duration_seconds}
    capas={capas}
  />
)}
```

La pantalla del integrado monta `DashboardEmbed`, que renderiza el **mismo `Dashboard`** con
`embedded={true}`. Esa guarda —puesta cuando los bloques por transacción todavía eran otra
cosa— es lo único que los quita.

Otras tres regiones llevan la misma guarda y **sí deben seguir ocultas**: las conclusiones y
recomendaciones de cada ejecución (v1.2 §0 las quiere una sola vez, y el integrado las
consolida), los botones de exportación individuales y el indicador de autoguardado propio.
La de `TransactionReportSection` es la única que sobra.

## 3. Cómo se carga una ejecución en la pantalla del integrado

```
IntegratedReportPage.tsx:463
  └── DashboardEmbed  (29 líneas: solo monta Dashboard)
        └── Dashboard  embedded={true}
              ├── GET /executions/{id}           (testAPI.getExecution)
              ├── GET /executions/{id}/charts    (testAPI.getCharts)
              ├── ReportBody      scope={kind:'general'}     ← sí se pinta
              └── TransactionReportSection                    ← BLOQUEADO por !embedded
                    ├── GET /executions/{id}/transaction-analyses
                    ├── GET /executions/{id}/transaction-charts?label=
                    └── GET /executions/{id}/transaction-report?label=
```

No hace falta ningún endpoint nuevo: los tres que alimentan los bloques ya existen y son de
lectura.

### Código muerto encontrado

**`frontend/src/components/integrated/ExecutionReportSection.tsx` (195 líneas) no lo importa
nadie.** Es una plantilla paralela —KPIs propios, dos gráficas propias, sus diez cajas de
análisis— que quedó huérfana cuando el integrado pasó a `DashboardEmbed`. Es exactamente el
tipo de gemelo que la Etapa 2 vino a eliminar. **No lo retiro en esta etapa**: no está en
las decisiones y no estorba. Queda señalado, como se hizo con `transaction_analyses_html`
antes de retirarla en la Etapa 6.

## 4. Cómo están indexados los overrides hoy

Guardados en `integrated_reports.sections[i].overrides`, por ejecución:

```json
{ "order": 0, "type": "load_test", "source_id": "<execution_id>", "source_name": "…",
  "overrides": {
    "analysis": { "ai_analysis_summary": "texto editado", "ai_conclusions": "…" },
    "images":   { "<attachment_id>": "texto editado" } } }
```

- **Las claves de `analysis` son nombres de columna** de `test_executions`.
- Los escribe `IntegratedReportPage.handleSectionAnalysisEdit(execId, field, value)`, que los
  deja en un `ref` y los persiste con el autoguardado (F4).
- Los lee el backend con `_load_section_overrides` y los aplica con `_apply_ia_overrides`:

  ```python
  for column, text in ((overrides or {}).get("analysis") or {}).items():
      key = _IA_KEY_BY_COLUMN.get(column)
      if key and text is not None:
          ia[key] = text
  ```

**Esto es una buena noticia para D58:** una clave que no esté en `_IA_KEY_BY_COLUMN` —como
`tx|<label>|<section>`— **se ignora en silencio** en la ruta actual. Se pueden guardar en el
mismo diccionario sin riesgo de que se cuelen donde no deben, y aplicarlas aparte.

Hay además precedente de convivencia: `ai_analysis_throughput` salió del mapa en la Etapa 2
y sus overrides siguen en la base, sin pintarse y sin borrarse. **D60 ya está cubierto por
ese mismo criterio**: un integrado sin overrides de transacción se verá con los textos
originales, porque el diccionario simplemente no tendrá esas claves.

## 5. Cómo llegan hoy los bloques por transacción al export (y qué les falta)

```
integrated_report.py:223   meta['transaction_reports'] = await _build_transaction_reports(db, execution, _df_tx, statistics)
integrated_report.py:1002  _tx_reports = await build_transaction_reports_plotly(db, execution, _df_tx, statistics)
```

Las dos funciones son las del informe individual (se reusan, no se copian) y **leen los
textos directo de `transaction_chart_analyses`**. Ninguna recibe los overrides.

**Para D59 hay que aplicarlos ahí**, y es el único punto: los dos exportadores ya tienen los
overrides cargados en esa misma función (`_load_section_overrides`), solo hay que pasarlos.

## 6. El canal de guardado de D58

Hoy `TransactionReportSection` guarda **directo**:

```ts
await api.put(`/executions/${executionId}/transaction-report/${section}?label=…`,
              { ai_analysis: texto });
```

Dentro del integrado eso escribiría en `transaction_chart_analyses`, que es justo lo que la
regla F4 prohíbe. Hace falta el mismo patrón que ya usa `Dashboard`: un canal opcional
(`onAnalysisEdit`) que, cuando viene, sustituye a la escritura directa. Sin la prop, el
componente se comporta exactamente como hoy en el informe individual.

## 7. Presupuesto de `Dashboard.tsx` (D62)

Autorizadas 40 líneas reales. Lo que hace falta:

| Cambio | Estimación |
|---|---|
| Quitar la guarda `!embedded` de `TransactionReportSection` | 2 |
| Pasarle el canal de edición y los overrides cuando está embebido | 6 |
| Comentario que explique por qué esa guarda sí sale y las otras no | 4 |
| **Total** | **≤ 12** |

Muy por debajo del tope. **No hace falta ningún otro archivo protegido**: el trabajo grueso
va en `TransactionReportSection.tsx`, `IntegratedReportPage.tsx`, `DashboardEmbed.tsx` y
`integrated_report.py`, ninguno protegido.

## 8. Datos para los sub-pasos siguientes

| Integrado | id | Secciones | Transacciones con informe |
|---|---|---|---|
| `E3-estilo — integrado` | `8713aad1-5de9-4dcb-b294-360ce8ecaee8` | 2 | 3 en la primera, 0 en la segunda |
| `E2-validacion + E1.3-baseline-2` | `998090d0-9bab-4935-8a2e-ffd7f23000fb` | 2 | 3 y 3 |

Ninguno tiene overrides todavía — sirven igual de punto de partida y de comprobación de D60.

`8713aad1` es el mejor banco de pruebas: tiene una ejecución **con** transacciones y otra
**sin**, así que prueba a la vez que los bloques aparecen y que una ejecución sin ellos no
pinta un hueco.

## 9. Presupuesto

| | |
|---|---|
| Llamadas a la IA en 7.1 | **0** |
| Archivos tocados | **0** |

---

**Estado:** 7.1 cerrado. Ninguna condición de parada: el único protegido en juego es
`Dashboard.tsx`, dentro de lo autorizado por D62 y con holgura. Sigue 7.2 —
implementación de D57 a D61.
