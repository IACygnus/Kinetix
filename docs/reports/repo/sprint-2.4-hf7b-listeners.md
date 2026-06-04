# Sprint 2.4-HF7.B — Agregar Listeners al árbol del Editor IA

**Fecha:** 2026-05-30
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** Aplicado y validado (sin gasto de cuota IA) — **SPRINT 2.4 COMPLETO**

---

## 1. Alcance

| Capacidad | Estado |
|---|---|
| Operación backend `add_listener` (refine quirúrgico) | ✅ |
| Aplicador con kind-aware defaults + Backend Listener config InfluxDB | ✅ |
| UI: botón "Agregar listener…" dentro del TreeFolder Listeners | ✅ |
| Modal con dropdown de 5 tipos | ✅ |

**5 tipos soportados:**
1. View Results Tree (debug)
2. Summary Report (resumen)
3. Aggregate Report (detallado)
4. Response Time Graph
5. Backend Listener (InfluxDB → Grafana, apunta al stack Kinetix por defecto)

---

## 2. Vía de integración elegida — **B (raw_xml inicial)**

### Por qué

El `ListenerModel` del schema solo guarda: `kind`, `guiclass`, `name`, `enabled`, `filename`, `raw_xml`. El regenerator del listener es **passthrough total**: si `raw_xml` no está vacío, lo usa tal cual; si está vacío, produce un `<ResultCollector>` mínimo sin `SaveConfig`. Y **el Backend Listener no es `<ResultCollector>` sino `<BackendListener>`** — el regenerator "mínimo" no funciona para él.

Conclusión: la única vía que cubre los 5 tipos (incluyendo Backend Listener) es **construir el raw_xml inicial completo en el applier**, con SaveConfig completo para los ResultCollectors y los `Arguments` de InfluxDB para Backend Listener. Cada listener queda con `is_dirty=False` para que el regenerator lo respete byte-por-byte.

### Mapeo `listener_kind` (op) → `ListenerModel.kind` (schema)

| listener_kind del op | guiclass JMeter | `ListenerModel.kind` |
|---|---|---|
| `view_results_tree` | `ViewResultsFullVisualizer` | `view_results_tree` |
| `summary_report` | `SummaryReport` | `summary_report` |
| `aggregate_report` | `StatVisualizer` | `aggregate_report` |
| `response_time_graph` | `RespTimeGraphVisualizer` | `other` (no en el enum) |
| `backend_listener` | `BackendListenerGui` | `other` (no es ResultCollector) |

### Backend Listener defaults

Apuntan al stack Kinetix por defecto (CLAUDE.md sección 12):

| Argument | Valor |
|---|---|
| `influxdbUrl` | `http://influxdb:8086/api/v2/write?org=performance&bucket=jmeter&precision=ms` |
| `TOKEN` | `jmeter-token-2024-super-secret` |
| `application` | `${__P(application,Kinetix Test)}` |
| `measurement` | `jmeter` |
| `percentiles` | `90;95;99` |
| `samplersRegex` | `.*` |
| Implementation | `org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient` |

El usuario puede customizar via `backend_listener_config` en el payload (op) o editando el listener tras crearlo desde el panel del editor.

---

## 3. Archivos modificados

| Archivo | Tipo | Δ líneas |
|---|---|---|
| `backend/app/schemas/refine_operations.py` | MOD | +44 (`AddListenerOp` + sumario en Union) |
| `backend/app/services/engine/refine_operations_applier.py` | MOD | +216 (constantes `LISTENER_KIND_DEFAULTS` + `DEFAULT_BACKEND_LISTENER_ARGS`, helpers `_xml_escape`, `_result_collector_raw_xml`, `_backend_listener_raw_xml`, `_build_listener_raw_xml`, handler `_apply_add_listener`) |
| `backend/app/api/v1/endpoints/script_ai.py` | MOD | +17 (op #14 al `REFINE_SURGICAL_SYSTEM_PROMPT`) |
| `frontend/src/pages/AIScriptEditor.tsx` | MOD | +144 (extensión de `AddElementType` + defaults/titles, rama de formulario `listener`, handler de mutación local con raw_xml construido en JS, botón "Agregar listener…" en TreeFolder Listeners, folder visible aun sin listeners cuando hay `treeActions`) |
| `backend/tests/test_refine_operations.py` | MOD | +95 (5 tests) |

**Backups creados:**
- `backend/app/schemas/refine_operations.py.bak_hf7b_20260530_012129`
- `backend/app/services/engine/refine_operations_applier.py.bak_hf7b_20260530_012129`
- `backend/app/api/v1/endpoints/script_ai.py.bak_hf7b_20260530_012129`
- `frontend/src/pages/AIScriptEditor.tsx.bak_hf7b_20260530_012129`

---

## 4. Tests añadidos

| Test | Verifica |
|---|---|
| `test_add_listener_view_results_tree` | `name`, `guiclass`, `<ResultCollector>` en raw_xml |
| `test_add_listener_summary_report_con_nombre_custom` | Nombre custom respetado en raw_xml |
| `test_add_backend_listener_default_config` | `kind=other`, `BackendListenerGui`, `InfluxdbBackendListenerClient`, `http://influxdb:8086` |
| `test_add_listener_round_trip_summary_report` | parse → add → regenerate → re-parse mantiene nombre + kind |
| `test_add_backend_listener_round_trip` | Backend Listener queda en `unmapped` (esperado, no es ResultCollector) con su raw_xml preservado |

---

## 5. Validaciones

### 5.1. Tests backend

```
pytest tests/ -q
76 passed in 1.69s
```

- 71 tests pre-HF7.B (sin cambios).
- 5 nuevos tests HF7.B.

### 5.2. TypeScript check

```
npx tsc --noEmit → EXIT=0
```

### 5.3. Round-trip end-to-end con los 5 tipos

Sobre fixture `Ejercicio_Booking.jmx` (6 listeners + 1 unmapped iniciales):

```
Operaciones aplicadas: 5 (uno de cada tipo)
JMX regenerado:        98 037 chars
✅ Los 5 nombres en el XML (VRT/SR/AR/RTG/BL HF7B)
✅ Backend Listener tiene config InfluxDB (InfluxdbBackendListenerClient, http://influxdb:8086)
✅ Re-parse: 10 listeners (6 originales + 4 ResultCollectors nuevos) + 2 unmapped (1 original + Backend Listener nuevo)
```

El Backend Listener queda como `unmapped` tras el re-parse — comportamiento heredado del parser (que solo reconoce `ResultCollector` como listener). Su raw_xml se preserva intacto, por lo que el JMX descargado **funciona en JMeter normal** sin modificaciones.

---

## 6. Cómo validar visualmente

1. Abrir un diseño en el Editor IA (`/ai-script-designer/editor/{designId}`).
2. Expandir el folder **Listeners** del árbol — ahora siempre visible aunque el JMX no tenga listeners.
3. Click en el primer item: **"Agregar listener…"** → abre el modal "Nuevo Listener".
4. Probar cada uno de los 5 tipos:
   - View Results Tree → aparece en el árbol con nombre "View Results Tree".
   - Summary Report → con nombre custom si se completa.
   - Aggregate Report → idem.
   - Response Time Graph → idem.
   - Backend Listener → aparece con la nota de InfluxDB en el modal antes de crear; tras crear, el JMX descargado contiene la config completa.
5. Toggle checkbox + botón Trash deben funcionar en cada listener creado (vienen del HF7.A).
6. Indicador de auto-save: "Guardando…" → "Guardado".
7. Recargar la página: los listeners persisten.

---

## 7. Garantías de no-regresión

- 71/71 tests pre-HF7.B siguen verdes.
- `tsc --noEmit` → EXIT=0.
- Postman / OpenAPI / texto / HAR siguen funcionando intactos.
- El refine clásico (`/refine`) y el quirúrgico (`/refine-surgical`) siguen funcionando.
- `treeActions` sigue siendo **opcional**, sin riesgo de romper otros consumidores del árbol.
- El TreeFolder Listeners cambió su condición de visibilidad: ahora se renderiza si `listeners.length > 0` **O** si hay `treeActions` (para permitir agregar). En contextos sin `treeActions` (lectura-solo) el comportamiento anterior se mantiene.

---

## 8. Estado

**🎉 SPRINT 2.4 COMPLETO END-TO-END.**

Capacidades del Editor IA al cierre del Sprint 2.4 (todas las HFs):
- HF1-HF4: foundation del editor estructural + Data Files + AI Designer.
- HF5: refine clásico con `REFINE_SYSTEM_PROMPT` + `max_tokens` dinámico + validación anti-destructiva.
- HF5.1: refine quirúrgico (operaciones JSON estructuradas, 52× más rápido que el clásico).
- HF5.2: kind-awareness para Thread Groups (standard vs stepping).
- HF6: HARs hasta 50 MB con compresión inteligente (filtros + dedup, hasta 99.5% reducción).
- HF7.A: agregar/eliminar/toggle sobre samplers, sampler_children, UDVs, CSVs + checkbox visual.
- **HF7.B**: agregar listeners (5 tipos incluyendo Backend Listener para InfluxDB → Grafana).

**Listo para Sprint 2.5 (ejecución motor propio del Editor IA, integración con `/performance-executions`).**

No se hizo `docker compose build` ni `up`. Backend recargó automáticamente vía `--reload`.
