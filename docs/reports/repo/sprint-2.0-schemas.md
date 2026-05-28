# Sprint 2.0 — Congelado de schemas AIScriptStructure

**Fecha:** 2026-05-25
**Estado:** ✅ Completado (validación funcional) — ⏳ Pendiente validación visual de Fredy

## Objetivo

Congelar los tipos Pydantic + TypeScript que el parser JMX (Sprint 2.1) y el regenerador (Sprint 2.3) consumirán/producirán. Sin lógica, sin endpoints — solo tipos.

## Decisiones aplicadas

1. **Roundtrip elementos no soportados:** `UnsupportedElement` con `raw_xml` + `severity` (`warning`/`info`).
2. **Children mixto:** discriminado por `type` (`sampler`/`controller`/`unsupported`) en `TGChild`, y por `type` (`header_manager`/`response_assertion`/...) en `SamplerChild`. Preserva orden semántico (ej. extractor antes que assertion).
3. **Controllers MVP:** `GenericController`, `LoopController`, `IfController`, `WhileController`, `ThroughputController`. ForEach queda v2.
4. **Aliases Stepping:** `Field(alias="Start users count")` + `populate_by_name=True` en `JMXBase`. Construcción por field name y por alias funcionan; serialización con `by_alias=True` produce nombres XML originales.

## Archivos creados

| Archivo | Líneas |
|---|---|
| `backend/app/schemas/ai_script_structure.py` | 518 |
| `frontend/src/types/aiScriptStructure.ts` | 479 |
| `docs/reports/sprint-2.0-schemas.md` | (este) |

Cero archivos existentes modificados. `backend/app/schemas/ai_script_design.py` (persistencia de sesión) queda intacto.

## Modelos principales

- **`AIScriptStructure`** (raíz, 11 campos top-level)
- **`TestPlanModel`** — name, functional_mode, serialize_threadgroups, tearDown_on_shutdown
- **`UserDefinedVariable`** — name/value/metadata
- **`HttpDefaultsModel`**, **`CookieManagerModel`**, **`CacheManagerModel`**
- **`CSVDataSetModel`** — share_mode con Literal, variable_names como List[str]
- **`ThreadGroupModel`** con `SteppingConfig` opcional (4 kinds soportados: standard/stepping/concurrency/ultimate)
- **`HTTPSamplerModel`** con `SamplerBody` (mode raw/form/none) y `children: List[SamplerChild]` ordenados
- **5 Controllers** (Generic/Loop/If/While/Throughput), todos con `children: List["TGChild"]` y forward refs resueltos via `model_rebuild()`
- **`UnsupportedElement`** (passthrough con raw_xml)
- **`StructureMetadata`** (variables referenced/defined/undefined, parse_warnings)

## Validaciones ejecutadas

| # | Validación | Resultado |
|---|---|---|
| 4.1 | Importación de 11 modelos Pydantic | ✅ `OK: todos los modelos importan correctamente` |
| 4.2 | Construcción y serialización de `AIScriptStructure()` vacío | ✅ 11 campos top-level, todos presentes |
| 4.3 | Aliases `SteppingConfig` bidireccionales | ✅ Construcción por field name y por alias OK; `model_dump(by_alias=True)` produce `'Threads initial delay'`, `'Start users count'`, `'rampUp'`, `'flighttime'` |
| 4.4 | Discriminated union `SamplerChild` con `HeaderManagerModel` y `ResponseAssertionModel` | ✅ `data` se hidrata al tipo correcto según el wrapper |
| 4.5 | `npx tsc --noEmit` sobre todo el frontend | ✅ EXIT=0, cero errores TS |
| 4.6 | Conteo de exports en TS | ✅ 49 `export interface` + `export type` (snippet esperaba ~25 — la diferencia viene de contar también los Literal-string types; sin duplicados) |
| 4.7 | Validación cruzada campos Pydantic ↔ TypeScript | ✅ 11/11 coincidencia en `AIScriptStructure` raíz: `test_plan, user_defined_variables, http_defaults, cookie_manager, cache_manager, csv_data_sets, thread_groups, config_elements, listeners, unmapped, metadata` |

## Adaptaciones del prompt original

Cero adaptaciones de código. Snippets de PASO 2 y PASO 3 escritos textualmente.

Ajuste menor en este reporte: el snippet de validación 4.6 esperaba "~25 exports" pero el archivo TS tiene 49 (`export interface` + `export type`). No es regresión — el conteo más alto refleja que también se exportaron los aliases de tipo (`UUID`, `CSVShareMode`, `AssertionTestField`, `BodyMode`, etc.) que ayudan a discoverability en IDEs. Documentado arriba.

## Pendientes derivados

- **Sprint 2.1:** parser JMX → AIScriptStructure usando `sample_jmx/Ejercicio_Booking.jmx` como fixture. Cubrir explícitamente:
  - 3 ThreadGroups (1 SteppingThreadGroup "Carga" habilitado + 2 ThreadGroup deshabilitados "Smoke test" / "Grabación original").
  - 18 HTTPSamplers (9 body raw, 9 form/sin body) con ResponseAssertion + HeaderManager + RegexExtractor.
  - 2 CSVDataSets, 4 UDVs top-level, 6 GenericControllers anidados.
  - Listeners kg.apc (TPS, RT-over-time, RC-per-sec) + ViewResultsFullVisualizer + StatVisualizer.
  - RecordingController + ProxyControl → debe ir a `unmapped[]` con severity=info.
- **Sprint 2.2:** endpoint `POST /script-designer/ai/parse-jmx` que devuelve `AIScriptStructure`.
- **Sprint 2.3:** regenerador AIScriptStructure → JMX con round-trip test (parse → regenerate → diff debe ser idempotente en estructura).
- **Sprint 2.4:** validar contra un segundo JMX con Timers + JSR223 PreProcessors (cuando aparezca un fixture así); el modelo ya tiene `ConstantTimer`/`UniformRandomTimer`/`GaussianRandomTimer` y `JSR223*` cae a `UnsupportedElement`.

## Estado para Sprint 2.1

**LISTO.** Schemas estables, validados estructural y funcionalmente. El parser puede empezar a hidratar instancias contra estos tipos sin riesgo de cambios de forma.
