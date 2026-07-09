# Diagnóstico Forense — Estado real post Sprint 2.6

> READ-ONLY. No se modificó ningún archivo del proyecto, DB ni git. Este archivo
> es el único output (nuevo, no altera nada).
> Fecha: 2026-06-03. Diseño investigado: **performnace_1**.

## 1. Estado del diseño "performnace_1" en DB
- **design_id**: `d9685f4a-0a96-451b-89a2-47e411580e3f`
- **updated_at**: `2026-06-03 22:30:24` UTC
- **Tamaño del JMX**: 25,392 chars
- **Listeners en el JMX (2)**: `View Results Tree` (ViewResultsFullVisualizer),
  `Summary Report` (SummaryReport). *(El `grep -c "ResultCollector"` daba 6 por
  contar el atributo `testclass="ResultCollector"` en props hijas, no listeners
  distintos. Real = 2.)*
- **CSV Data Sets en el JMX (2)**:
  - `Data Data_Create.txt` → filename `${Data}/Data_Create.txt`
  - `Data Data_Update.txt` → filename `${Data}/Data_Update.txt`
- **Variables UDV relevantes**: `host`, `scheme`, `port`, y **`Data` =
  `/app/uploads/ai_data_files/d9685f4a-0a96-451b-89a2-47e411580e3f`** (ruta
  absoluta Docker-interna).
- Estructura: 6 HTTP samplers (Auth, Get IDs, Create, Get by ID, Update, Delete).

## 2. Archivos físicos vs registros en DB — **DISCREPANCIA CRÍTICA**
- **Archivos físicos** en `/app/uploads/ai_data_files/{design}/`: **1 archivo**
  (`c8db357a-...csv`, 39 bytes = Data_Create.txt).
- **`ai_design_data_files` (DB)**: **1 registro** — solo `Data_Create.txt`
  (stored `c8db357a-...csv`, creado 15:41:02).
- **Data_Update.txt**: **NO existe** ni en disco (find en todo `/app/uploads`
  no lo encuentra) ni en DB. Sin embargo el JMX SÍ lo referencia.
- Data_Create.txt sí fue copiado a cada workdir de ejecución
  (`jtl_results/23..28/Data_Create.txt`).

**→ DISCREPANCIA: el JMX referencia 2 CSVs; solo 1 está materializado (archivo+DB).**

## 3. Código del refine — ¿crea archivos físicos? **NO**
- Existe la operación `add_csv_dataset` (`_apply_add_csv_dataset`,
  `refine_operations_applier.py:584`). Su cuerpo **solo** hace
  `structure.csv_data_sets.append(new_csv)` (líneas 588-602).
- **NO crea archivo físico. NO inserta registro en `ai_design_data_files`.**
- Operaciones MVP del refine quirúrgico: updates + `set_enabled` + add/delete de
  csv/listener sobre la estructura. Ninguna materializa archivos.

**→ Cuando la IA agrega un CSV (Data_Update.txt), solo aparece en el JMX; el
archivo nunca se crea.**

## 4. Código de copia al workdir — **CAUSA RAÍZ del error CSV**
- Smoke: `script_ai.py:2229-2256`. FULL: `script_ai.py:2331-2368`.
- Ambos iteran `select(AIDesignDataFile).where(design_id == design.id)` (solo DB):
  ```python
  for df in data_files:
      src = os.path.join(uploads_base, df.stored_filename)
      dst = os.path.join(workdir, df.original_filename)
      if os.path.exists(src): shutil.copy2(src, dst)
      else: skipped_files.append(...)
  data_dir_resolver = {"Data": workdir}   # ${Data} → workdir local
  ```
- Como Data_Update.txt **no tiene registro `AIDesignDataFile`**, nunca entra al
  loop → nunca se copia → `${Data}/Data_Update.txt` no existe en el workdir →
  JMeter falla al leer el CSV Data Set.

**→ CAUSA RAÍZ "File Data_Update.txt must exist": el CSV fue añadido por la IA
vía refine (solo al JMX), pero no existe como archivo ni registro DB, y la copia
al workdir solo materializa archivos con registro en `ai_design_data_files`.**

## 5. Mensaje "Edición disponible próximamente"
- **Ubicación**: `frontend/src/pages/AIScriptEditor.tsx:2540`, dentro del
  **fallback de `DetailPanel`** (rama final tras agotar los `if selected.kind`).
- **Cuándo aparece**: al seleccionar un listener (o cualquier kind sin editor)
  **FUERA de modo ejecución** — el routing del panel central muestra `DetailPanel`,
  que no tiene rama para `kind: 'listener'` → cae al fallback.
- **¿Bug del Sprint 2.6?** **NO.** Es pre-existente de HF7.B (Sprint 2.4). El
  Sprint 2.6 solo añadió el viewer en vivo (en modo ejecución); fuera de
  ejecución el comportamiento es el mismo de siempre (listeners no son
  estructuralmente editables).

## 6. Persistencia de listeners
- Auto-save: `persistJmx` (`AIScriptEditor.tsx:351`) llama
  `aiScriptDesignsAPI.upsert({ current_jmx: jmxText })` donde `jmxText =
  regenerateJmx(structure)` → **reemplaza el `current_jmx` completo**.
- El regenerador `structure_to_jmx.py` **SÍ preserva listeners** vía passthrough
  de `raw_xml` (`_serialize_listener:687-699`, itera `structure.listeners:781`).
- **¿Riesgo de pérdida?** El round-trip estructura→JMX **no** pierde listeners.
  El riesgo real está en el **full-refine de la IA** (`fallback_to_full_refine`):
  ahí el JMX se regenera desde la salida del modelo, que puede **omitir listeners
  no re-emitidos**. Confianza media; requiere repro para confirmar la ruta exacta.

## 7. Logs recientes y ejecuciones — **timeline confirma la cadena causal**
- Logs backend (últimas 300 líneas): sin coincidencias CSV/smoke (rotados).
- Ejecuciones del diseño (`performance_executions.ai_design_id`):

  | exec | hora (UTC) | status | total_samples |
  |---|---|---|---|
  | 23 | 15:44 | completed | **60** |
  | 24 | 16:54 | completed | **60** |
  | 25 | 16:59 | completed | **60** |
  | 26 | 22:29 | completed | **0** |
  | 27 | 22:30 | completed | **0** |
  | 28 | 22:33 | completed | **0** |

- **El diseño funcionaba (60 samples) hasta las ~16:59.** Tras `updated_at
  22:30:24` (la IA agregó Data_Update.txt), las ejecuciones 26/27/28 dan **0
  samples**. `error_message` vacío y status `completed` porque el runner marca
  completado al salir el proceso JMeter aunque el CSV falle (el fallo queda en
  jmeter.log, no se propaga al status).

## 8. Naming del JMX descargado
- `aiScriptDesignsAPI.downloadJmx` (`api.ts:493`) usa `filename ||
  'ai_generated_test.jmx'`.
- Handler editor (`AIScriptEditor.tsx:405-406`):
  `safeName = (designName || 'diseno').replace(/[^\w\-]/g,'_')` →
  `${safeName}.jmx`.
- **Patrón actual**: solo el nombre del diseño saneado. **Sin timestamp, sin
  cliente, sin proyecto.**
- **Mejora requerida**: `{cliente}_{proyecto}_{YYYYMMDD_HHMMSS}.jmx`.

---

## CAUSA RAÍZ POR PROBLEMA

| Problema | Causa raíz REAL (evidencia) | Fix propuesto |
|---|---|---|
| A. IA modificó estructura JSON | Prompt del Diseñador no es conservador (fuera de alcance forense) | Sprint 2.9 |
| B. Listeners se borran | Regenerador estructura→JMX SÍ los preserva (raw_xml). Riesgo en **full-refine IA** que regenera desde salida del modelo y omite listeners no re-emitidos. *Confianza media — requiere repro* | HF + endurecer prompt full-refine |
| C. "Edición próximamente" | Fallback de `DetailPanel` (AIScriptEditor.tsx:2540) al seleccionar listener fuera de ejecución. **Pre-existente HF7.B, no es bug 2.6** | HF puntual (UX) |
| D. No hay "+" para escenario | Funcionalidad nunca existió en el editor | Sprint 2.10 |
| E. Ejecución en ceros | Consecuencia de G: JMeter no lee Data_Update.txt → 0 samples (execs 26-28) | HF14 |
| F. Summary "esperando samples" | Consecuencia de E: 0 samples parseados → per_sampler_stats vacío | HF14 (resuelto al arreglar G) |
| G. Solo se copia 1 CSV | `add_csv_dataset` del refine no crea archivo físico ni registro DB; la copia al workdir solo itera `ai_design_data_files` | **HF14 (núcleo)** |
| H. Path absoluto en JMX | UDV `Data` = `/app/uploads/ai_data_files/{design}` (path Docker interno) → no resuelve al abrir el JMX en JMeter desktop | HF14 (opción: zip con CSVs + path relativo) |
| I. Naming JMX descargado | `downloadJmx` usa solo `designName` saneado, sin timestamp/cliente/proyecto | HF14 |

## SIGUIENTE PASO RECOMENDADO

**HF14 (prioridad alta — desbloquea ejecución):** atacar G como núcleo.
1. **G/E/F**: cuando el refine agrega un CSV (`add_csv_dataset`), o bien (a)
   crear un placeholder físico + registro `ai_design_data_files`, o (b) que la
   copia al workdir detecte CSVs del JMX sin registro y avise/cree. Mínimo: que
   smoke/FULL reporten claramente el CSV faltante en `error_message` (hoy status
   queda "completed" con 0 samples, ocultando el fallo).
2. **H**: al descargar el JMX, reescribir UDV `Data` a path relativo y/o empaquetar
   en zip con los CSVs (opción 2). Para ejecución interna, ya se resuelve `${Data}`
   al workdir — el problema H es solo del JMX exportado a desktop.
3. **I**: naming `{cliente}_{proyecto}_{YYYYMMDD_HHMMSS}.jmx`.

**HF puntual:** C (mensaje "Edición próximamente" → texto más claro para listeners,
ej. "Selecciona durante una ejecución para ver datos en vivo").

**Sprints posteriores:** B (endurecer full-refine + repro), A (prompt conservador
— 2.9), D (botón "+" escenario — 2.10).

> Nota: status `completed` con 0 samples es engañoso. Recomendado que el runner
> marque `error`/warning cuando el JTL queda vacío o jmeter.log contiene "must
> exist and be readable" — mejora de observabilidad transversal a E/F/G.
