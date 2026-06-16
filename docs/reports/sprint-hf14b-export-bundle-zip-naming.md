# HF14b — Export bundle portable (ZIP + naming)

Origen: `docs/reports/diagnostico-forense-post-sprint-2.6.md` (bugs H/I).

## Bugs resueltos
- **H**: la UDV `Data` apuntaba a un path Docker interno
  (`/app/uploads/ai_data_files/{id}`) → el JMX no funcionaba en JMeter desktop.
  Ahora el JMX exportado dentro del ZIP usa `./Data` (path relativo) + los CSV
  físicos viajan en la carpeta `Data/`.
- **I**: el filename de descarga era solo el nombre del diseño (causaba `(1)`,
  `(2)` al reusar). Ahora: `{cliente}_{nombre}_{YYYYMMDD_HHMMSS}.{jmx|zip}`.

## Módulo nuevo
`backend/app/services/engine/export_bundle_builder.py` (122 líneas):
- `rewrite_data_udv_to_relative(jmx)` — regex que reescribe el value de la UDV
  `Data` a `./Data` (solo la primera coincidencia).
- `sanitize_for_filename(name)` — espacios→`_`, no-alfanuméricos→`_`, colapsa `_`.
- `build_export_filename(name, client, ext, now)` — `{cliente}_{nombre}_{ts}.{ext}`
  (omite cliente si es None/vacío).
- `build_export_bundle(jmx, csv_files)` — sin CSVs → JMX puro
  (`application/xml`); con CSVs → ZIP (`application/zip`) con `script.jmx` +
  `Data/` + `README.txt`. `os.path.basename` neutraliza path traversal en nombres.

## Endpoint nuevo
`GET /script-designer/ai/designs/{id}/export-bundle` (auth admin|analyst):
- Lee `design.current_jmx` + CSVs físicos (vía `df.file_path`, fallback a
  `uploads_base/stored_filename`).
- Resuelve el nombre del cliente por **query a `Client`** (el modelo solo tiene
  `client_id` FK, sin `relationship` → no se puede lazy-load).
- Devuelve `Response` con `Content-Disposition`, `X-Filename`, `X-Has-CSVs`.
- No toca el `/download` legacy (compatibilidad intacta).

## Fix CORS (necesario, no estaba en el borrador)
`backend/app/main.py`: `expose_headers` ampliado a
`["X-CSRF-Token", "Content-Disposition", "X-Filename", "X-Has-CSVs"]`. Sin esto
el navegador NO expone esos headers a JS y el frontend caería al filename genérico,
anulando el naming (Problema I). Verificado: sin este cambio el feature no funciona.

## Frontend
- `api.ts`: `aiScriptDesignsAPI.exportBundle(designId)` — descarga blob y toma el
  nombre de `Content-Disposition` (fallback `X-Filename` → genérico). Se mantienen
  `downloadJmx`/`downloadById` legacy (compat).
- `AIScriptEditor.tsx`: `handleDownloadJmx` usa `exportBundle(designId)`; botón
  renombrado "Descargar .jmx" → "Descargar" (puede ser ZIP).
- `AIScriptEditorList.tsx`: `handleDownloadDesign(designId)` usa `exportBundle`;
  caller actualizado a un solo argumento.

> Cambio de comportamiento menor: el editor ahora exporta el JMX **persistido en
> DB** (no el `originalJmx` en memoria). El auto-save (debounce 800ms) mantiene la
> DB al día; es además la fuente de verdad para los CSVs asociados.

## Tests
`backend/tests/test_export_bundle_builder.py` (10 tests): reescritura UDV,
sin-Data-no-cambia, saneamiento (incluye None), naming con/sin/empty cliente,
JMX puro, ZIP completo (verifica `./Data` y ausencia de `/app/uploads`), y
saneamiento anti path-traversal.

**Resultado:** `120 → 130 PASS` (+10), 2 deselected. Sin regresiones.

## Validación
- Backend: **130 passed, 2 deselected**.
- Frontend `tsc --noEmit`: **EXIT=0**.
- Curl `GET /designs/{performnace_1}/export-bundle`: **HTTP 200**,
  `application/zip`, 3206 bytes,
  `Content-Disposition: attachment; filename="Occidente_performnace_1_20260604_042814.zip"`,
  `X-Has-CSVs: 1`. ZIP contiene `script.jmx` (`./Data` presente, `/app/uploads`
  ausente) + `Data/Data_Create.txt` (contenido real) + `README.txt`.
- Líneas: `script_ai.py` 2605→2684 (+79), `export_bundle_builder.py` 122 (nuevo),
  `main.py` +0 neto (1 línea editada), `api.ts` 830→858 (+28),
  `AIScriptEditor.tsx` 7363→7368 (+5), `AIScriptEditorList.tsx` 199 (-? ajuste),
  test 106 (nuevo).

## Backups
`*.bak_14b_20260603_232523` para script_ai.py, main.py, api.ts, AIScriptEditor.tsx,
AIScriptEditorList.tsx.

## Estado: SPRINT 2.6 + HF14a + HF14b CERRADOS. Listo para validación visual final TOTAL.
```