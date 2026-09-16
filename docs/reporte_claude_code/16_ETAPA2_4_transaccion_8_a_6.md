0e6c80b · 2026-09-16

# ETAPA 2.4 — IA por transacción: 8 → 6 (D20)

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.
**Ningún archivo protegido tocado.** 3 archivos:
`db/models/transaction_chart_analysis.py`, `services/ai/transaction_report.py`,
`api/v1/endpoints/upload.py`.

---

## 1. Diseño: dos conjuntos, no un recorte

La tentación era recortar `SECTIONS` de 8 a 6. **No se hace**, porque esa tupla gobierna a la vez
cuatro cosas distintas: qué se genera, qué se valida al pedir, qué se puede editar y cómo se
ordenan las filas. Recortarla dejaría fuera de la ley a las filas ya guardadas.

```python
SECTIONS = ("summary", …5 charts…, "conclusions", "recommendations")   # 8 — CONOCIDAS
SECTIONS_GENERADAS = ("summary",) + tuple(f"chart_{c}" for c in CHART_TYPES)   # 6 — se generan
```

| Uso | Conjunto | Por qué |
|---|---|---|
| Generación (`transaction_report.py`) | **6** | v1.2 §1.1 |
| Construcción de prompts | **6** | no armar dos que nadie usa |
| Progreso y estado (`upload.py`) | **6** | si no, lo nuevo se queda en «generando» para siempre |
| Validación de `?sections=` | 8 | pedir una retirada no da 400, simplemente no genera |
| `PUT` de una sección | 8 | las filas antiguas se siguen pudiendo **editar** |
| `sort_order` | 8 | `SECTIONS_GENERADAS` es prefijo de `SECTIONS`: los índices 0-5 coinciden, así que el orden de las filas viejas y nuevas es el mismo |

---

## 2. El estado de progreso, que era lo delicado

La lógica anterior comparaba contra `len(SECTIONS)` = 8:

```python
elif len(suyas) < len(SECTIONS):      # 6 < 8  → "generando" PARA SIEMPRE
```

Un informe nuevo, ya terminado con sus 6 secciones, se habría quedado girando en la pantalla sin
llegar nunca a «completo». Ahora se **filtran las filas** por sección generada antes de contar:

```python
todas_suyas = por_label.get(label, [])
suyas = [f for f in todas_suyas if f.section in SECTIONS_GENERADAS]
```

Con eso, los dos casos salen bien sin migrar nada:

- **Informe nuevo (6 filas):** `suyas` = 6 → completo.
- **Informe antiguo (8 filas):** `suyas` = 6 (las dos sobrantes se ignoran) → completo.

También se filtró `con_texto` en el endpoint de detalle: sin eso, un informe antiguo habría
mostrado **«8/6»** en la barra de progreso.

---

## 3. Validación

### 3.1 Stubs — 11/11, 0 llamadas reales

| Comprobación | Resultado |
|---|---|
| `SECTIONS` sigue teniendo 8 (no se recorta) | PASA |
| `SECTIONS_GENERADAS` tiene 6 | PASA |
| Las 6 son resumen + las 5 gráficas | PASA |
| `conclusions`/`recommendations` siguen siendo conocidas | PASA |
| …pero no se generan | PASA |
| **Se piden 6 secciones por transacción** | PASA |
| No se pide `conclusions` ni `recommendations` | PASA |
| `counters` = `{'total': 6, 'generated': 6, 'failed': 0}` | PASA |
| Se persisten 6 filas | PASA |
| `?sections=conclusions,summary` → genera **solo** `summary` | PASA |

### 3.2 Retrocompatibilidad contra datos reales (D26)

`E1.3-baseline-2`, generada en la Etapa 1 con **8 filas por transacción, todas con texto**,
consultada por la API ya con el código nuevo:

```
status global: completed (3/3)
  4. Get_Booking_Id        completo   6/6
  5. Put_Update_Booking    completo   6/6
  6. Delete_Booking_Id     completo   6/6
detalle progress: 6/6 | persisted: 8
secciones devueltas: ['summary','chart_response_times','chart_latency',
                      'chart_error_rate','chart_codes','chart_tps',
                      'conclusions','recommendations']
```

Los tres puntos que importan:

1. **`completo 6/6`**, no «generando» ni «8/6».
2. **`persisted: 8`** — las filas antiguas siguen en base, no se ha borrado nada.
3. **Las 8 secciones se siguen devolviendo** en `sections`, así que las dos retiradas se pueden
   leer y editar. Dejarán de **pintarse** en 2.6-2.9, que es lo que pide la regla de ocultar.

`py_compile` OK en los 3 archivos.

---

## 4. Efecto en el coste de un informe

| | Antes | Ahora |
|---|---|---|
| General | 11 (12 con redirecciones) | **10** (11) |
| Por transacción | 8 | **6** |
| **Total con N transacciones** | 11 + 8N | **10 + 6N** |
| Con 3 transacciones (la línea base) | 35 | **28** |

Un 20 % menos de llamadas. **No es el objetivo de esta etapa** —es consecuencia de aplicar la
especificación— y el efecto en tiempo se medirá en 2.10 como dato informativo para la Etapa 4.

---

## Estado

Sub-paso 2.4 completado. Se continúa con 2.5 (datos del render parametrizado).
