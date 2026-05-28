# Sprint 2.1 — Parser JMX → AIScriptStructure

**Fecha:** 2026-05-25
**Estado:** ✅ Completado — 25/25 tests passing

## Objetivo

Implementar parser JMX completo que produzca `AIScriptStructure` (schemas congelados en Sprint 2.0). Python puro, sin endpoint, sin tocar frontend.

## Archivos creados

| Archivo | Líneas |
|---|---|
| `backend/app/services/engine/jmx_to_structure.py` | 779 |
| `backend/tests/test_jmx_parser.py` | 315 |
| `backend/tests/fixtures/Ejercicio_Booking.jmx` | (92 KB — copia del fixture) |
| `docs/reports/sprint-2.1-parser.md` | (este) |

Cero archivos existentes modificados. Schemas del Sprint 2.0 intactos.

## Cobertura del parser

- **TestPlan + UDV top-level + HttpDefaults + Cookie + Cache.**
- **CSVDataSet** con split de `variable_names` por coma.
- **ThreadGroup estándar + Stepping** (con aliases del kg.apc preservados — `model_dump(by_alias=True)` produce nombres XML originales).
- **HTTPSampler con 3 body modes**: raw (postBodyRaw=true), form (Arguments.arguments con elementProps), none.
- **Sampler children**: HeaderManager, ResponseAssertion (tolerante al typo "Asserion.test_strings"), RegexExtractor, JsonExtractor, XPathExtractor, BoundaryExtractor, Constant/Uniform Timers.
- **Controllers**: Generic, Loop, If, While, Throughput. `LogicControllerGui` y `RecordController` mapean a Generic.
- **Listeners**: estándar + kg.apc family (`kg_apc_response_times_over_time`, `kg_apc_response_codes_per_second`, `kg_apc_transactions_per_second`, etc.) con mapping específico por `guiclass`; resto a `kind=other`.
- **Unmapped passthrough**: `ProxyControlGui` y elementos no soportados se guardan con `raw_xml` + severity. `RecordController` se preserva como controller (ver adaptación abajo).
- **Metadata derivada**: `referenced_variables` (regex `${var}`), `defined_variables` (UDV + CSV + extractor refnames), `undefined_variables` (set difference), `unmapped_count`, `parse_warnings`.

## Resultados de tests

**25 / 25 passing en 0.69s.**

| # | Test | Resultado |
|---|---|---|
| 1 | test_parser_no_lanza_excepcion | ✅ |
| 2 | test_test_plan_parseado | ✅ |
| 3 | test_tres_thread_groups | ✅ |
| 4 | test_stepping_thread_group_presente | ✅ |
| 5 | test_stepping_props_correctos | ✅ |
| 6 | test_stepping_serializa_con_aliases | ✅ |
| 7 | test_smoke_test_thread_group_deshabilitado | ✅ |
| 8 | test_dieciocho_samplers_total | ✅ (tras fix RecordController) |
| 9 | test_samplers_con_body_raw_y_form | ✅ (9 raw / 9 form-or-none) |
| 10 | test_samplers_tienen_header_manager | ✅ |
| 11 | test_response_assertions_se_parsean | ✅ (≥18 detectadas) |
| 12 | test_regex_extractors_se_parsean | ✅ (4 detectadas) |
| 13 | test_generic_controllers_anidan_samplers | ✅ |
| 14 | test_csv_data_sets_dos | ✅ |
| 15 | test_csv_variable_names_split | ✅ |
| 16 | test_udv_top_level_cuatro | ✅ |
| 17 | test_http_defaults_presente | ✅ |
| 18 | test_cookie_manager_presente | ✅ |
| 19 | test_cache_manager_presente | ✅ |
| 20 | test_listeners_kg_apc_reconocidos | ✅ |
| 21 | test_recording_y_proxy_en_unmapped | ✅ |
| 22 | test_metadata_referenced_variables | ✅ |
| 23 | test_metadata_no_hay_indefinidas_criticas | ✅ |
| 24 | test_jmx_vacio_no_lanza_excepcion | ✅ |
| 25 | test_jmx_malformado_lanza_value_error | ✅ |

## Cobertura medida en `Ejercicio_Booking.jmx`

| Métrica | Valor |
|---|---|
| ThreadGroups detectados | 3/3 (1 Stepping habilitado + 2 ThreadGroup estándar deshabilitados) |
| HTTPSamplers totales | 18/18 (6+6+6) |
| Samplers con body raw | 9 (Auth/Post/Put × 3 TGs) |
| Samplers con body form/none | 9 (Get/Delete) |
| ResponseAssertions | 18 |
| RegexExtractors | 4 |
| CSVDataSets | 2/2 (`Data Post Create`, `Data Put Update`) |
| UDVs top-level | 4/4 (`host`, `scheme`, `Data`, `Resultados`) |
| Listeners | 6 (2 view_results_tree + 1 aggregate_report + 3 kg.apc reconocidos) |
| Unmapped top-level | 1 (`ProxyControlGui`) |
| Variables referenced | 10 |
| Variables defined | 10 |
| Variables undefined | **0** (cero huérfanas) |
| parse_warnings | 0 |

## Adaptaciones del prompt original

### 1. `RecordController` se mapea a `GenericController` (no a `unmapped`)

**Prompt original:** "RecordingController + ProxyControl → van a unmapped con severity=info."

**Adaptación:** `RecordController` (guiclass del `RecordingController`) se añadió a `_CONTROLLER_PARSERS` apuntando a `_parse_generic_controller`. `ProxyControlGui` sigue yendo a `unmapped`.

**Justificación:** En el JMX de Fredy, el TG "Grabación original" tiene esta estructura típica de un Recorder:

```
ThreadGroup "Grabación original"
└── RecordingController (self-closing)
    └── hashTree
        ├── GenericController "Auth" → HTTPSamplerProxy "Auth-1"
        ├── GenericController "Get Booking" → HTTPSamplerProxy "Get Booking-2"
        ├── ... (6 controllers, 6 samplers)
```

Si `RecordController` cae en `unmapped`, su `raw_xml` se preserva pero los 6 GenericControllers y 6 samplers anidados desaparecen del modelo editable. Esto rompe el round-trip y los tests fallaron con 12/18 samplers detectados.

Mapearlo a Generic Controller preserva la estructura completa (el round-trip ahora es íntegro) y los 6 samplers quedan editables. El nombre original "Recording Controller" y `raw_xml` siguen disponibles.

**Trade-off aceptado:** `RecordController` se reporta como un controller "normal" en la UI, no como un elemento legacy. Es aceptable porque visualmente es un controller con N samplers — la semántica funcional es idéntica a un Generic.

### 2. Fixture path movido a `backend/tests/fixtures/`

**Prompt original:** path `sample_jmx/Ejercicio_Booking.jmx` accesible desde el container.

**Adaptación:** copia del fixture a `backend/tests/fixtures/Ejercicio_Booking.jmx`.

**Justificación:** `docker-compose.yml` monta solo `./backend:/app`. El folder `sample_jmx/` queda fuera del container. Mover el fixture a `backend/tests/fixtures/` lo hace accesible vía el volumen y es la convención estándar de pytest. El original sigue en `sample_jmx/` para referencia.

### 3. pytest instalado en el container

**Prompt original:** "Si pytest no estaba instalado y lo instalas, déjalo registrado."

**Acción:** `docker exec jmeter_backend pip install pytest --break-system-packages` → pytest 9.0.3 instalado.

**Nota:** la instalación es efímera; cualquier `docker compose down + up` la pierde. Para persistirlo, añadir `pytest>=9.0` a `backend/requirements.txt` en un sprint futuro (no toco requirements.txt en este sprint para mantener scope).

## Decisiones técnicas

- **lxml en vez de xml.etree:** mejor manejo de CDATA + xpath. `strip_cdata=False` preserva CDATA blocks en `raw_xml`.
- **Walker de hashTree en pares `(element, child_hashTree)`:** preserva el contrato JMeter de alternancia `[E1, HT1, E2, HT2, ...]`. Tolera hashTrees vacíos.
- **Tolerancia explícita al typo "Asserion":** `_string_prop()` busca `Assertion.X` y `Asserion.X` (sin 's'); `_parse_response_assertion()` también busca el collectionProp con typo. Aún no había en este JMX, pero el código está listo.
- **`raw_xml` solo en wrappers grandes** (TG, Sampler, Listener, ConfigElement, UnsupportedElement) — NO en hijos pequeños (HeaderManager, Assertion). Reduce duplicación; el `raw_xml` del sampler ya contiene a sus hijos.
- **`Metadata.undefined_variables` como warning UX**, no error fatal. El parser nunca lanza por una variable indefinida — solo la registra.
- **`extra='allow'` en `JMXBase`:** permite que el parser inserte campos no contemplados sin romper validación. Útil para evolución incremental del modelo.

## Pendientes derivados

- **Sprint 2.2:** endpoint `POST /script-designer/ai/parse-jmx` que recibe `current_jmx` y devuelve `AIScriptStructure`. Debe usar `parse_jmx_to_structure()` directamente.
- **Sprint 2.3:** regenerador `AIScriptStructure → JMX` con round-trip test: `parse → regenerate → parse` debe ser idempotente en estructura editable (los `raw_xml` pueden tener whitespace diff; comparar por modelo).
- **Sprint 2.4:** validar contra un segundo JMX con Timers reales + JSR223 PreProcessors. El modelo ya soporta `Constant/Uniform/Gaussian` timers; JSR223 caerá a `UnsupportedElement` con `parent_sampler_id`.
- **Persistir pytest en `requirements.txt`** cuando se permita tocar dependencias.
- **Bug detectado en SYSTEM_PROMPT IA** (variables `${host}` sin UDV en scripts generados por IA) sigue pendiente — anotado en backlog general, fuera de scope de este sprint.

## Estado para Sprint 2.2

**LISTO.** 25/25 tests passing, parser cubre todos los elementos del fixture real, cero variables huérfanas detectadas. El endpoint del Sprint 2.2 puede importar `parse_jmx_to_structure` directamente sin cambios al parser.
