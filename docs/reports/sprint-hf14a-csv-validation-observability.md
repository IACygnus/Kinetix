# HF14a — Validación CSV pre-ejecución + Observabilidad runner

Origen: `docs/reports/diagnostico-forense-post-sprint-2.6.md` (bugs G/E/F).

## Bugs resueltos
- **G** (núcleo): un CSV agregado por la IA vía refine queda referenciado en el
  JMX pero sin archivo físico → ahora **fail-fast pre-ejecución** con HTTP 400 guiado.
- **E/F** (consecuencias): la ejecución ya no se lanza si falta un CSV → se acaba
  el "completed con 0 samples" y el Summary "esperando samples".
- **Observabilidad**: aunque JMeter salga con exit 0, el runner FULL detecta
  fallos silenciosos (CSV faltante, `Test failed!`, JTL vacío) y marca `error`.

## Módulo nuevo
`backend/app/services/engine/csv_reference_validator.py` (135 líneas):
- `extract_csv_filenames_from_jmx(jmx)` — parsea XML y extrae `<CSVDataSet>` → filenames.
- `resolve_csv_filename(raw, resolver)` — resuelve `${Data}` etc.
- `find_missing_csv_files(jmx, workdir, resolver, available_filenames)` — compara
  contra los archivos realmente copiados al workdir.
- `build_missing_csv_error_message(missing)` — mensaje guiado (subir / eliminar CSV).

> **Desviación documentada**: el borrador proponía
> `backend/app/services/ai_script_designer/`, paquete que **no existe** (CLAUDE.md:
> el motor vive en `services/engine/`). Para respetar la estructura, el módulo se
> colocó en `services/engine/csv_reference_validator.py`.

## Integraciones backend (`script_ai.py`)
- **Smoke** (`run_smoke_test`): tras copiar Data Files y definir `data_dir_resolver`,
  valida con `available_filenames=set(copied_files)`. Si falta un CSV →
  `cleanup_workdir` + `HTTPException(400, detail={error_type:"csv_missing", message, missing_csvs})`.
- **FULL** (`execute`): misma validación; además marca `perf_exec.status="error"` +
  `error_message` + commit antes del 400 (la ejecución ya existe en DB).
- Se valida el **JMX original** (no el patched), resolviendo `${Data}` con el
  resolver → robusto ante sustitución de variables. `available_filenames` se deriva
  de `copied_files` (lo realmente materializado), consistente en ambos flujos.

## Observabilidad runner (`jmeter_runner.py`)
- `_detect_silent_failure(workdir, jtl_path)`: escanea `jmeter.log` por patrones
  críticos (`must exist and be readable`, `Test failed!`, `IllegalArgumentException`,
  `FileNotFoundException`) y detecta JTL vacío (<100 bytes / ≤1 línea).
- `_run_full_execution_background`: cuando `exit_code==0 && !error`, llama
  `_detect_silent_failure`; si hay fallo → `status="error"` + `error_message`.

## Frontend (`AIScriptEditor.tsx`)
- `runSmokeTest` y `handleStartExecution`: el `catch` ahora detecta `detail` objeto
  (`{error_type, message}`) y muestra `detail.message` (antes daba `[object Object]`).
  Smoke lo muestra en el modal (`setSmokeError`); FULL vía `alert`.

## Tests
`backend/tests/test_csv_reference_validator.py` (10 tests, +1 sobre los 8 planeados
para el caso de path absoluto existente): extracción, resolución de vars, XML
inválido, todos-disponibles, uno-faltante, path absoluto, mensajes guiados.

**Resultado:** `110 → 120 PASS` (+10), 2 deselected (slow). Sin regresiones.

## Validación
- Backend: **120 passed, 2 deselected**.
- Frontend `tsc --noEmit`: **EXIT=0**.
- Curl `POST /designs/{performnace_1}/smoke-test`: **HTTP 400**,
  `error_type=csv_missing`, `missing_csvs=['Data_Update.txt']`, mensaje guiado completo.
- Líneas: `script_ai.py` +47 (→2605), `jmeter_runner.py` +54 (→612),
  `csv_reference_validator.py` 135 (nuevo), `AIScriptEditor.tsx` +10 (→7363),
  test 122 (nuevo).

## Backups
`*.bak_14a_20260603_230941` para script_ai.py, jmeter_runner.py, AIScriptEditor.tsx.

## NO incluido (HF14b)
- Export ZIP + naming `{cliente}_{proyecto}_{timestamp}.jmx` (Problema H/I).
- Fix prompt Diseñador IA (2.9), botón "+" Thread Group (2.10).

## Estado: LISTO para validación visual + HF14b.
```