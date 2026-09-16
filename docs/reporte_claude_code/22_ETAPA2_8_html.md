28caf93 · 2026-09-16

# ETAPA 2.8 — El HTML individual

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.

Archivo protegido tocado, **autorizado**: `export_html.py`. Mismo trabajo que 2.7, con
Plotly en vez de matplotlib.

| Commit | Qué |
|---|---|
| `a1788af` (2.8a) | Extracción pura: `HTML_BODY_CHARTS`, `HTML_GENERAL_ONLY` y `_bloque_grafica_html`; la plantilla deja de repetir siete veces el mismo HTML |
| `28caf93` (2.8b) | D19, D21, D17, D20, D16, D22 |

---

## 1. Equivalencia de 2.8a

HTML real de `ff186cc7` por HTTP, antes y después: **512.940 caracteres los dos**. La
única diferencia del diff es que el comentario de UI-2 sube siete líneas, porque ahora
encabeza el bloque en vez de vivir entre la primera y la segunda gráfica. Ni una
etiqueta renderizada cambia.

---

## 2. Qué cambia

| Decisión | Antes | Ahora |
|---|---|---|
| **D19** | Gráfica «Throughput Over Time» | Fuera, y con ella sus *traces*: ya no se calculan ni viajan en el documento descargado. **El HTML baja de 513.405 a 497.252 bytes.** El KPI Throughput (req/s) y la tabla resumen no se tocan |
| **D21** | El bloque por transacción tenía títulos propios («Tiempos de Respuesta»), colores propios y **ningún control** | Pinta con `_bloque_grafica_html`, la misma pieza del general, y toma el título, el color y la sección de `HTML_BODY_CHARTS`. Lleva los mismos botones. `_ctrl_basic` sube a nivel de módulo por eso |
| **D17** | `{tx_body}` después de las conclusiones | Antes |
| **D20** | 5 gráficas + conclusiones + recomendaciones | Solo resumen + 5 gráficas; el origen se filtra por `SECTIONS_GENERADAS` |
| **D16 / D22** | Rótulo «Mini-informe por transaccion» + nombre + criticidad | Solo el nombre. Se limpian `_TX_SIN_TEXTO` y **los dos comentarios que viajan dentro del documento entregado** (el de HTML y el de JavaScript): quien mire el fuente del archivo no debe leer la palabra |

`_TX_GRAFICAS` se **deriva** de `HTML_BODY_CHARTS` en vez de ser una segunda lista: no
hay dos sitios donde mantener el mismo orden.

---

## 3. Validación

Sobre el HTML real de `ff186cc7` (`e2e/html_check.py`) — **11 de 11**:

```
sin la grafica Throughput Over Time · sin el div chart-throughput · el KPI Throughput
sigue · sin la palabra prohibida · transacciones ANTES de conclusiones · 3 bloques ·
15 graficas por transaccion · sin conclusiones ni recomendaciones por transaccion ·
las graficas por transaccion llevan controles · titulos del general en el bloque
```

Y el documento **se abre de verdad** (`e2e/html_render.py`, Chromium sobre
`file:///tmp/export.html`): **22 divs de gráfica, 22 pintadas por Plotly, cero errores
de consola**. Esto importa porque un fallo de JavaScript dejaría el HTML en blanco sin
que ninguna comprobación de texto lo notara.

### C3 — cambios reales en el protegido

| Archivo | 2.8a | 2.8b | Total | Estimación revisada |
|---|---|---|---|---|
| `export_html.py` | 85 | 92 | **177** | 190-260 |

---

## 4. Pendiente

- **Integrado** (`integrated_report.py`) — 2.9. Tiene **su propia copia** de `_ctrl_basic`,
  `_ctrl_y_axis` y del cuerpo de gráficas (`_build_plotly_html_isolated`), más D23 al
  renderizar los overrides.
- El selector «qué incluir» al exportar (v1.2 §6) no es de este sub-paso.

**Falta la validación visual de Fredy** sobre el HTML descargado (regla 9).
