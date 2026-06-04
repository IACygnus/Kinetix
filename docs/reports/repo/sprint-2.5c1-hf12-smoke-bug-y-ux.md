# HF12 — Hotfix Sprint 2.5c.1

**Fecha:** 2026-06-02
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** ✅ bug crítico arreglado y validado end-to-end con `Data_Create.txt` real (18/18 samplers OK); UX modal implementado; tests 90→91 (+1 slow); tsc EXIT=0.

---

## Problema 1: smoke "0/0 samplers" (BUG CRÍTICO)

### Síntoma
El smoke test devolvía `0/0 samplers OK` y el log de JMeter mostraba
`File ${Data}/Data_Create.txt must exist and be readable` aunque el archivo
existía físicamente.

### Root cause (confirmado en diagnóstico)
El archivo en disco se guarda con su **`stored_filename`** (un UUID, ej.
`bde9ac5b-f29a-4d54-82c9-4fd204ebafa5.csv`), pero el JMX referencia
`${Data}/<original_filename>` (ej. `${Data}/Data_Create.txt`). Aunque
`${Data}` apuntara a `/app/uploads/ai_data_files/{id}` (HF anterior), el
archivo **existía con otro nombre** → FileServer no lo encontraba.

### Fix (Camino 1 — copiar al workdir)
En el endpoint `smoke-test`:
1. Carga los `AIDesignDataFile` del diseño.
2. Crea el workdir temporal (`create_smoke_workdir()`).
3. Copia cada archivo de `uploads/.../{stored_filename}` →
   `{workdir}/{original_filename}` (el nombre que el JMX espera).
4. `data_dir_resolver = {"Data": workdir}` → `${Data}` apunta al workdir local.
5. `run_jmeter(..., workdir=workdir)` (cwd = workdir, JMeter encuentra los CSV).
6. Anexa `[HF12] Data Files: copiados=... omitidos=...` al `jmeter_log_tail`.
7. `cleanup_workdir(workdir)` en `finally` (no toca `/app/uploads`).

El JMX persistido / de descarga mantiene `${Data}/<archivo>` portable; solo el
smoke reescribe la UDV en memoria.

---

## Problema 2: Data File sin variables queda huérfano (UX)

### Síntoma
Subir un Data File sin declarar variables no autocreaba CSV Data Set → archivo
huérfano, no usable por JMeter.

### Fix (Opción A — modal obligatorio)
En `DataFilesPanel`:
- Al seleccionar archivo, si `variableNames` está vacío → abre modal
  **"Variables JMeter requeridas"** (con ejemplo `firstname,lastname`).
- Confirmar (con variables) → sube + autocrea CSV Data Set + refresca árbol.
- Cancelar → no sube; el input se resetea.
- Si el usuario rellena variables ANTES de seleccionar archivo → se salta el
  modal y sube directo.

---

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `backend/app/services/engine/jmeter_runner.py` | +`create_smoke_workdir()` |
| `backend/app/api/v1/endpoints/script_ai.py` | imports (`shutil`, `AIDesignDataFile`, `create_smoke_workdir`); endpoint copia Data Files al workdir, resolver→workdir, run_jmeter(workdir=...), info en log |
| `frontend/src/pages/AIScriptEditor.tsx` | `DataFilesPanel`: estados pendingFile/pendingVariables/showVariablesPrompt, `handleFilePicked`/`doUpload`/`handleConfirmVariables`/`handleCancelUpload`, modal obligatorio |
| `backend/tests/test_jmeter_runner.py` | +`import shutil`, +2 tests (1 fast + 1 slow) |

**Backups:** `.bak_hf12_20260602_155636` en los 4 archivos.

---

## Tests

- `test_run_jmeter_con_csv_dataset_en_workdir` (fast): verifica que `${Data}` se
  reescribe al workdir y que el `filename` del CSV Data Set NO cambia (sigue
  `${Data}/test.csv`).
- `test_run_jmeter_smoke_lee_csv_real_desde_workdir` (slow): JMeter real lee el
  CSV desde el workdir; el log NO contiene `must exist and be readable`.

**Resultado:** `pytest -m "not slow"` → **91 passed, 2 deselected** (antes 90+1).
Slow HF12 → **1 passed in 9.41s**. 0 regresiones.

---

## Validación manual (caso real Data_Create.txt)

Endpoint `POST /script-designer/ai/designs/d9685f4a-.../smoke-test?num_threads=3&loops=1`:

```
login: 200
smoke HTTP: 200
status: success
duration: 8.3s
total=18 ok=18 fail=0
  [OK] 200 '1. Autenticación - Crear Token'  ...
  [OK] 200 '2. Obtener IDs de Reservas'  ...
  [OK] 200 '3. Crear Reserva'  ...
  [OK] 200 '4. Obtener Reserva por ID'  ...
FileServer error present?: False
log: FileServer: Close: /tmp/jmeter_smoke_av35fig3/Data_Create.txt
```

- **HTTP 200**, status **success**.
- **total_samples=18** (3 threads × 6 samplers × 1 loop), **18 OK / 0 fail**
  (antes: 0/0).
- log **NO** contiene `must exist and be readable`; muestra que JMeter resolvió
  `${Data}/Data_Create.txt` al workdir donde se copió el archivo con su nombre
  original.

---

## No-regresión

- `patch_jmx_for_smoke` sin args sigue forzando 1 user / 1 loop.
- Copia de Data Files es best-effort: si un archivo no existe, se omite (queda
  registrado en `skipped_files` / log) sin abortar el smoke.
- `run_jmeter` ya aceptaba `workdir`; no cambió su firma.
- El input de variables en `DataFilesPanel` sigue funcionando como atajo
  (pre-declarar → sin modal).

---

## Estado: LISTO para validación visual de Fredy y luego Sprint 2.5d.

No se hizo rebuild Docker (backend volumen-montado; frontend Vite HMR).
