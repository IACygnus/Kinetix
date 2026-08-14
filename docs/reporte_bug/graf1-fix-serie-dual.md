# GRAF1-FIX — Serie dual avg/max a 1s: **detenido por presupuesto de archivos**

**Fecha:** 2026-08-13
**Estado:** ⏸ **No implementado.** Diagnóstico de alcance + salvaguarda. **Cero cambios de código.**
**Motivo de la parada:** la regla del prompt es "máx 5 archivos… si excede, DETENERSE y reportar".
El fix completo toca **10 archivos** (3 de ellos protegidos). El presupuesto de *líneas*
(~96 vs 80-140) sí alcanza; el de *archivos* se pasa al doble.

---

## 1. Dos correcciones de premisa antes de nada

### 1.1 `test_results` está vacía — no se puede re-agregar desde ahí

El prompt indica *"Re-agregación desde test_results (datos crudos ya en DB — sin re-subir JTL)"*.
Eso no es posible: el diagnóstico GRAF-1 (§4) ya estableció que **`test_results` tiene 0 filas
y ningún endpoint inserta en ella** (`grep -rn "TestResult("` sobre `backend/app` no devuelve
ninguna instanciación). El modelo y la tabla existen, pero nunca se escriben.

**Esto no bloquea el objetivo.** El crudo vive en el JTL del volumen `uploads_data`, y
`GET /executions/{id}/charts` **ya re-parsea el archivo en cada request** (`upload.py:573-582`).
Se obtiene exactamente lo que se pedía —re-agregación sin re-subir el JTL— haciéndolo en el
parser. La implementación propuesta abajo sigue esa vía.

### 1.2 Hay un 5º consumidor que el prompt no lista: el informe integrado

El prompt mapea 4 consumidores. El diagnóstico encontró **cinco**: falta
`integrated_report.py` (`:109/118` rama PDF, `:818/891-892` rama HTML), que pinta la misma
gráfica. Es el entregable que va al cliente. Si se deja fuera, **el informe integrado seguiría
ocultando los picos** justo después de dar el fix por cerrado.

---

## 2. Alcance real medido

| # | Archivo | Protegido | Líneas est. | Qué |
|---|---|:---:|---:|---|
| 1 | `services/jtl/jtl_parser.py` | 🔒 | ~8 | Intervalo 1s + columna `value_max` |
| 2 | `schemas/test.py` | | ~1 | `value_max: Optional[float]` |
| 3 | `endpoints/upload.py` | | ~1 | Pasar `value_max` en el endpoint de charts |
| 4 | `components/dashboard/Dashboard.tsx` | 🔒 | ~25 | 2ª línea por label + zoom Y |
| 5 | `services/export/report_generator.py` | 🔒 | ~10 | Estilo por serie en `chart_multiline` |
| 6 | `endpoints/export_pdf.py` | | ~10 | Serie dual matplotlib |
| 7 | `endpoints/export_html.py` | | ~15 | 2º trace Plotly + hover |
| 8 | `endpoints/integrated_report.py` | | ~15 | 5º consumidor (2 ramas) |
| 9 | `services/ai/analysis_pipeline.py` | | ~5 | Máximos al prompt |
| 10 | `services/ai/gemini.py` | | ~6 | Texto del prompt + `build_tier_summary` |
| | **Total** | **3 🔒** | **~96** | **10 archivos** |

Líneas dentro de presupuesto; **archivos al 200 % del tope**. Además, `Dashboard.tsx` y
`report_generator.py` son protegidos y **no estaban contemplados como protegidos** en la
lista del prompt.

### Por qué el PDF obliga a tocar `report_generator.py`

`chart_multiline()` (`report_generator.py:99-130`) dibuja **todas** las series igual:
`ax.plot(..., linewidth=1.5, label=...)` con color por índice. Sin un parámetro de estilo,
la serie de máximos saldría como una línea sólida más, del mismo grosor y otro color:
3 transacciones → **6 líneas sólidas** en 180 mm. Ilegible, justo lo que el prompt pide evitar.
Hacer el máximo "fino/punteado y del mismo color que su promedio" exige tocar ese helper.

---

## 3. Diseño propuesto (la clave para poder partirlo)

**Mantener `value` = promedio y AÑADIR `value_max`.** La forma del dato no cambia para quien
ya la consume.

```python
# jtl_parser.py — dentro de get_all_charts_data()
RT_INTERVAL_SECONDS = 1                      # solo esta serie; el resto sigue adaptativo
label_df['time_bucket'] = label_df['timestamp'].dt.floor(f'{RT_INTERVAL_SECONDS}s')
agg = label_df.groupby('time_bucket')['elapsed'].agg(['mean', 'max']).reset_index()
agg.columns = ['timestamp', 'value', 'value_max']
```

Ventaja decisiva: **cada consumidor se puede migrar por separado** sin romper a los demás.
Quien no lea `value_max` sigue pintando el promedio exactamente como hoy. Esto permite
partir el trabajo en 3 prompts sin dejar el sistema inconsistente en ningún punto intermedio.

⚠ Detalle a cubrir en la fase de exports: `apply_top_n_aggregation()`
(`high_cardinality_strategy.py:63-68`) reconstruye la serie "Resto" con
`.agg(value=('value','mean'))` y **descarta `value_max`**. Con ≥15 labels, esa serie llegaría
sin la columna → hay que agregar `value_max` ahí también o tolerar su ausencia. No afecta a
Coomeva (3 labels), pero sí a pruebas grandes.

---

## 4. División propuesta (3 prompts, cada uno dentro del tope)

| Prompt | Archivos | Líneas | Entrega |
|---|---:|---:|---|
| **GRAF1-A — serie + IA** | 5 (1,2,3,9,10) | ~21 | Los picos existen en el dato y **llegan a la IA**. Nada visual cambia todavía. |
| **GRAF1-B — pantalla** | 1-2 (4) | ~25 | Dual en el dashboard. |
| **GRAF1-C — exports** | 4 (5,6,7,8) | ~50 | Dual en PDF, HTML e integrado. |

Recomiendo **empezar por GRAF1-A**: es el que cumple el objetivo de negocio más crítico
("los picos deben LLEGAR al análisis IA"), es el más barato, no toca ningún archivo
protegido del frontend y no cambia nada visualmente —riesgo de regresión visual nulo.

Recordatorio del diagnóstico (§3.1): **la IA hoy no falla por la serie suavizada** —recibe
`max=21.060` correcto en `rt_lines`— sino por el encuadre: el tier se asigna sólo por `avg`
(`gemini.py:565`), `build_tier_summary()` no emite `max` (`:617`) y la variabilidad se mide
con `p99/avg` (`:575`). GRAF1-A debe corregir eso, o el texto seguirá diciendo
*"tier excelente, picos de hasta 1070ms"* sobre una transacción con 23 timeouts de 21 s.

---

## 5. Rendimiento — línea base medida (el "antes" del punto 3)

Medido dentro del contenedor sobre el JTL real de Coomeva (25.773 muestras, 3 labels,
1.799,9 s). El "después" queda pendiente de implementar.

| Configuración | Agregación | Puntos | Payload JSON |
|---|---:|---:|---:|
| **3 s avg (ACTUAL)** | 78 ms | 1.795 | 141,4 KB |
| 1 s avg | 170 ms | 4.977 | 392,0 KB |
| **1 s DUAL avg+max (objetivo)** | **230 ms** | **4.977** | **490,9 KB** |

Lectura honesta: el coste de CPU es despreciable (+152 ms en un endpoint que ya re-parsea
un JTL de 25 K filas), pero **el payload se multiplica por 3,5** (141 → 491 KB) en la
respuesta al frontend y en el HTML de Plotly. Es asumible para 3 transacciones; con 15+
labels sin cap en pantalla conviene vigilarlo. El render de matplotlib ya se midió
indiferente en el diagnóstico (0,27 → 0,33 s).

---

## 6. Salvaguarda — ejecución `4b4e5977` (read-only)

**Confirmado que no existe** en `test_executions` (`SELECT ... LIKE '4b4e5977%'` → 0 filas).

**No existe ningún camino de borrado no-manual.** Verificado por código y por esquema:

- **Único borrado posible:** `DELETE /executions/{id}` (`upload.py:468-495`), que hace
  `delete(TestExecution)` explícito. Es la única sentencia del repo que borra ejecuciones.
- **Sin retención ni tareas programadas:** no hay APScheduler, cron, TTL, purge ni
  `older_than` en `backend/`. Los `cleanup` que aparecen son de workdir y caché del motor,
  no tocan `test_executions`.
- **Sin cascade entrante:** la única FK hacia `test_executions` es
  `execution_attachments.execution_id` (CASCADE) — borra hijos, nunca la ejecución.
  `test_executions.client_id → clients` es **NO ACTION**: borrar un cliente **no** arrastra
  sus ejecuciones.

**Conclusión:** la ejecución sólo pudo desaparecer por una llamada explícita al endpoint DELETE
hecha por un usuario autenticado. No hay borrado automático que la explique.

> 🔓 **Hallazgo lateral de seguridad:** ese DELETE **no exige rol admin**. Depende de
> `get_current_active_user` + `_check_execution_access` (`upload.py:51-60`), que permite la
> operación a **cualquier rol** —incluido `viewer`— con tal de tener asignado el cliente de
> la ejecución. Un `viewer` puede borrar ejecuciones. Recomiendo evaluarlo aparte
> (¿`require_role('admin','analyst')` en el DELETE?).

---

## 7. Validación pendiente (cuando se implemente)

No aplicable todavía —no hay cambios—. Al ejecutar GRAF1-A/B/C habrá que cubrir:

1. Endpoint de charts devolviendo buckets de 1 s con `avg` y `max`, y comparación
   `max(serie)` vs `max(elapsed)` crudo por transacción (esperado: **21.060 ms** en `token`
   y `Adapter VerifMethod`, contra los 2.914 / 6.148 ms actuales).
2. Export HTML: grep del trace de máximos en la traza Plotly + peso antes/después.
3. PDF: genera sin error, conteo de páginas estable, máximo presente en la gráfica.
4. Rendimiento real del endpoint contra la línea base de §5.
5. **Validación visual de Fredy** (criterio único de éxito): abrir el dashboard de la
   ejecución `115346ea` (Coomeva 31-jul), comparar contra JMeter a 500 ms —los picos de
   ~21 s deben verse—, y exportar HTML y PDF confirmando legibilidad con 3 transacciones.

---

## 8. Cierre

Trabajo **read-only**. `git status` de `backend/` y `frontend/` limpio: no se creó ningún
`.bak_graf1_*` porque no se editó ningún archivo. No se ejecutaron análisis IA (cuota
intacta). `origin` no se tocó.

**Decisión pendiente de Fredy:** confirmar la división en GRAF1-A / B / C (recomendado), o
autorizar explícitamente los 10 archivos en un solo prompt saltándose el tope de 5.
