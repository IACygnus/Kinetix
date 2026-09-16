55a1d26 · 2026-09-16

# ETAPA 2.7 — El PDF individual

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.

Archivos protegidos tocados, los dos **autorizados** para esta etapa:
`report_generator.py` y `export_pdf.py`.

---

## 1. Los dos pasos (condición C1)

| Commit | Qué |
|---|---|
| `9693ab2` (2.7a) | **Extracción pura.** `_ai_box_html`, `_chart_unit_html`, `BODY_CHARTS`, `GENERAL_ONLY_CHARTS` y `report_body_html` suben a nivel de módulo; `build_pdf_html` los llama. Sin cambio de orden, contenido ni estilos |
| `55a1d26` (2.7b) | **Los cambios funcionales**: D19, D21, D17, D20, D16, D22 |

### Equivalencia de 2.7a

`build_pdf_html` es una función pura: con la misma entrada devuelve el mismo HTML. Se
llama con una entrada fija antes y después (`e2e/pdf_equivalencia.py`) y se comparan:

```
/tmp/pdf_antes.html    30.648 chars
/tmp/pdf_despues.html  30.648 chars
diff                   VACIO
```

Única diferencia de comportamiento declarada: `_chart_unit_html` devuelve cadena vacía
si no hay imagen, donde el cierre anterior reventaba con `KeyError`. En el alcance
general no cambia nada —todas las claves existen— y es el criterio que ya tenía el
bloque por transacción.

---

## 2. Qué cambia en el PDF

| Decisión | Antes | Ahora |
|---|---|---|
| **D19** | Gráfica «Throughput Over Time» + su análisis | Fuera. `export_pdf` ya no genera ni la imagen ni manda `ai_analysis_throughput`. **El escalar `throughput` (req/s) de la portada y de la tabla resumen no se toca** |
| **D21** | `transaction_reports_html` tenía plantilla propia (títulos «Tiempos de Respuesta», colores propios, caja de análisis siempre índigo) | Llama a `report_body_html(..., 'transaction')`: mismos títulos, mismos colores y mismo layout que el general |
| **D17** | Transacciones **después** de las conclusiones | Transacciones **antes**; conclusiones una sola vez, al final, de toda la prueba |
| **D20** | 5 gráficas + conclusiones + recomendaciones por transacción | Solo resumen + 5 gráficas. `export_pdf` filtra por `SECTIONS_GENERADAS`: una transacción que **solo** tenga las dos filas antiguas ya no abre un bloque vacío |
| **D16 / D22** | Rótulo «Mini-informe por transaccion» + nombre + criticidad | Solo el nombre de la transacción. `_SIN_TEXTO` reescrito sin la palabra prohibida |
| **D24** | Ya estaba | Cada bloque abre página |

**Se conserva el criterio de N3.5:** una gráfica cuyo análisis falló o quedó pendiente
se pinta igual, con su aviso. Para eso `_ai_box_html` acepta `vacio_html`, que en el
alcance general no se usa y por tanto no cambia nada allí.

**Se retira la criticidad** del encabezado del bloque, porque v1.2 §0 dice que el título
es el nombre de la transacción y nada más. El dato se sigue calculando
(`_criticidad()` en `export_pdf`) y está disponible si Fredy lo quiere de vuelta.

---

## 3. Validación

Sobre datos **reales** (`ff186cc7`), ejecutando el endpoint en proceso y espiando el
HTML que se renderiza (`e2e/pdf_real_html.py`) — **8 de 8**:

```
PASA | sin la grafica Throughput Over Time
PASA | el KPI Throughput de la portada sigue
PASA | sin la palabra prohibida mini-informe
PASA | las transacciones van ANTES de las conclusiones
PASA | un bloque por transaccion (3)
PASA | sin conclusiones por transaccion
PASA | sin recomendaciones por transaccion
PASA | cada bloque abre pagina (D24)
paginas del PDF: 16
```

PDF real por HTTP: **200**, 2.521.145 bytes, **5,1 s**.

### C3 — cambios reales en los protegidos

| Archivo | 2.7a | 2.7b | Total | Estimación revisada (reporte 18) |
|---|---|---|---|---|
| `report_generator.py` | 103 | 85 | **188** | 240-320 |
| `export_pdf.py` | 0 | 19 | **19** | 50-65 |

Dentro de lo estimado en los dos casos.

---

## 4. Pendiente

- **HTML individual** (`export_html.py`) — 2.8. Tiene su propia copia del cuerpo con
  Plotly; el mismo trabajo, con otro motor de gráficas.
- **Integrado** (`integrated_report.py`) — 2.9, incluido D23 al renderizar.
- El selector «qué incluir» al exportar (v1.2 §6) no es de este sub-paso.

**Falta la validación visual de Fredy** sobre el PDF generado (regla 9): que los
bloques por transacción se lean como el informe general y que el salto de página caiga
donde debe.
