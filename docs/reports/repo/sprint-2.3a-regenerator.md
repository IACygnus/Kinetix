# Sprint 2.3a — Regenerador AIScriptStructure → JMX

**Fecha:** 2026-05-25
**Estado:** ✅ Completado — 40/40 tests passing (27 parser + 13 regenerator)

## Objetivo

Implementar el regenerador `AIScriptStructure → JMX` con estrategia "edit-preserving" (Python puro, sin endpoint). Round-trip parse→regenerate→parse debe ser idempotente sobre los conteos editables.

## Cambios

### Backend

| Archivo | Tipo | Diff |
|---|---|---|
| `backend/app/schemas/ai_script_structure.py` | MOD | 519 → 546 (+27: campo `is_dirty: bool = False` en 24 modelos + docstring sprint) |
| `backend/app/services/engine/structure_to_jmx.py` | NUEVO | 799 líneas |
| `backend/tests/test_jmx_regenerator.py` | NUEVO | 197 líneas (13 tests) |

### Frontend

| Archivo | Tipo | Diff |
|---|---|---|
| `frontend/src/types/aiScriptStructure.ts` | MOD | 479 → 502 (+23: campo `is_dirty?: boolean` opcional en 24 interfaces) |

Backups creados:
- `backend/app/schemas/ai_script_structure.py.bak_sprint2_3a_20260525_122836`
- `frontend/src/types/aiScriptStructure.ts.bak_sprint2_3a_20260525_122836`

## Estrategia edit-preserving

```
is_dirty=False + raw_xml válido + ningún descendiente dirty → reusar raw_xml literal
is_dirty=True OR sin raw_xml OR descendiente dirty            → re-construir desde campos
sin atributo is_dirty (legacy)                                → asumir dirty (seguridad)
```

Implementado en `_should_reuse_raw_xml(model)` + `_has_dirty_descendant(model)` recursivo.

### Quién decide reusar vs reconstruir

| Tipo de elemento | Política |
|---|---|
| TestPlan | reuse-or-rebuild via flag |
| HttpDefaults / Cookie / Cache / CSV | reuse-or-rebuild via flag |
| ThreadGroup (con children) | reuse-or-rebuild — invalidado si hijo dirty |
| HTTPSampler (con children) | reuse-or-rebuild — invalidado si hijo dirty |
| SamplerChild data (HeaderManager, Assertion, Extractor, Timer) | reuse-or-rebuild via flag |
| Controllers (Generic/Loop/If/While/Throughput) | siempre reconstruidos (no tienen raw_xml propio) |
| Listener | **siempre reusa raw_xml** (passthrough total — props internas `save_config` no se editan) |
| ConfigElement | **siempre reusa raw_xml** |
| UnsupportedElement | **siempre reusa raw_xml** (semánticamente no se edita) |

### Stepping aliases

`SteppingConfig.model_dump(by_alias=True)` produce los nombres XML literales con espacios (`Start users count`, `rampUp`, `flighttime`, etc.) — el regenerador los emite como `<stringProp name="...">`, preservando la fidelidad del XML kg.apc.

## Tests (40/40 PASS)

### Parser (27 — sin regresión por añadir is_dirty)

Suite del Sprint 2.1 + 2.1.1 sigue verde. Ver `docs/reports/sprint-2.1-parser.md` y `docs/reports/sprint-2.1.1-fix-xml-comments.md`.

### Regenerator (13 tests nuevos)

| # | Test | Resultado |
|---|---|---|
| 1 | `test_regenerator_no_lanza_excepcion` | ✅ |
| 2 | `test_regenerator_produce_xml_valido` | ✅ |
| 3 | `test_roundtrip_conserva_thread_groups` | ✅ |
| 4 | `test_roundtrip_conserva_samplers` | ✅ |
| 5 | `test_roundtrip_conserva_csv_data_sets` | ✅ |
| 6 | `test_roundtrip_conserva_udvs` | ✅ |
| 7 | `test_roundtrip_conserva_listeners` | ✅ |
| 8 | `test_roundtrip_conserva_stepping_config` | ✅ |
| 9 | `test_edit_sampler_url_se_refleja_en_regen` | ✅ |
| 10 | `test_no_dirty_reusa_raw_xml` | ✅ |
| 11 | `test_dirty_descendiente_invalida_cache_padre` | ✅ |
| 12 | `test_structure_vacia_no_lanza` | ✅ |
| 13 | `test_jmx_regenerado_es_valido_para_re_parse` | ✅ |

Tiempo total suite: 1.13s.

## Round-trip verificado con `Ejercicio_Booking.jmx`

| Métrica | Original | Regenerado | OK? |
|---|---|---|---|
| Tamaño JMX | 93 439 chars | 89 023 chars | ✅ (diferencia es whitespace/pretty-print) |
| Thread Groups | 3 | 3 | ✅ |
| Samplers (recursivo, incluyendo nietos del Recorder) | 18 | 18 | ✅ |
| CSVs | 2 | 2 | ✅ |
| UDVs | 4 | 4 | ✅ |
| Listeners | 6 | 6 | ✅ |
| Stepping aliases en XML (`Start users count`, `rampUp`, `flighttime`) | sí | sí | ✅ |
| Unmapped top-level | 1 (ProxyControl) | 1 | ✅ |
| Variables referenced | 10 | 10 | ✅ |
| Variables undefined | 0 | 0 | ✅ |

### Verificaciones edit-preserving

- ✅ `is_dirty=True` en sampler → path editado aparece en JMX regenerado.
- ✅ `is_dirty=False` + modificación de campo → cambio NO aparece (raw_xml reusado).
- ✅ Padre `is_dirty=False` + hijo `is_dirty=True` → padre se reconstruye y cambio del hijo aparece (cache invalidation recursiva).

## Adaptaciones del prompt original

Cero adaptaciones funcionales. Mejoras de robustez aplicadas:

1. **`raw = getattr(model, "raw_xml", None)` antes del `_should_reuse_raw_xml`** — el snippet original tenía `etree.fromstring(plan.raw_xml.encode("utf-8")) if getattr(plan, "raw_xml", None) else _build_test_plan(plan)` que evaluaba `_should_reuse_raw_xml(plan)` y LUEGO `getattr(plan, "raw_xml", None)`. Refactoré los serializadores a:
   ```python
   raw = getattr(model, "raw_xml", None)
   if _should_reuse_raw_xml(model) and raw:
       return etree.fromstring(raw.encode("utf-8"))
   return _build_xxx(model)
   ```
   Más legible y semánticamente idéntico.

2. **`for s in ra.test_strings:`** (sin `enumerate`) — el snippet usaba `enumerate` con `idx` no utilizado. Eliminado para limpieza.

3. **TS `is_dirty?: boolean` opcional** — añadido a `ControllerBase` (base interface) además de las 5 controllers, para evitar redundancia y permitir herencia natural.

## Decisiones técnicas

- **`lxml` ya en uso del parser** — reusado, sin nuevas dependencias.
- **`raw_xml` semánticamente significativo solo cuando el parser lo populó** — para elementos creados de cero desde la UI, `raw_xml=""` fuerza reconstrucción.
- **Listeners/ConfigElements/Unmapped siempre via raw_xml** — sus props internas (`save_config`, etc.) son demasiado verbosas para serializar campo por campo; passthrough total es la decisión correcta.
- **Cache invalidation recursiva en `_has_dirty_descendant`** — recorre la lista `children` buscando dirty en `data`/`sampler`/`controller`. Garantiza que cualquier edit en un nieto invalida toda la cadena hacia arriba.
- **`is_dirty` opcional en TS** (`is_dirty?: boolean`) — no rompe código del Sprint 2.0 que no conoce el campo. El backend asume dirty si falta, lo cual es seguro.

## Pendientes derivados

- **Sprint 2.3b:** endpoint `POST /script-designer/ai/regenerate-jmx` que recibe `AIScriptStructure` y devuelve JMX string.
- **Sprint 2.4:** frontend Editor IA que consume parse + regenerate. Debe setear `is_dirty=true` en cada campo editado.
- **Validación contra segundo JMX** (Timers reales + JSR223): cuando aparezca un fixture así, añadir tests específicos. El modelo ya soporta los timers; JSR223 cae a UnsupportedElement con passthrough.
- **Pretty-print diff:** el regenerado es 4 KB más chico que el original por whitespace normalizado. Si Fredy quiere diff byte-perfecto, evaluar preservar el formato original via `lxml.tostring(pretty_print=False)` o `xmlformatter`.

## Estado para Sprint 2.3b

**LISTO.** Regenerador estable, 40/40 tests passing, round-trip verificado sobre el fixture real con 18 samplers, 3 TGs, 6 listeners y 1 unmapped — todos preservados. El endpoint del Sprint 2.3b puede importar `regenerate_jmx_from_structure` directamente sin cambios.
