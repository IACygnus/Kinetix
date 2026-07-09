# Sprint 2.9 — Multi-HAR en el Diseñador IA

> Soporte para adjuntar varios HAR en una conversación del Diseñador IA y
> procesarlos como UN flujo continuo. Origen: caso Bancoomeva (flujo dividido en
> 2 HARs; la UI solo aceptaba 1).
> **Fecha:** 2026-06-17

---

## Bug resuelto

- La UI aceptaba **1 archivo por turno**; el flujo real venía en 2 HARs → la IA
  generaba un script incompleto al no recibir el segundo.

---

## Backend — `backend/app/api/v1/endpoints/script_ai.py` (+139 líneas)

### Endpoint `/generate-from-file` ahora multi-archivo (compat backward)
- Firma: `files: List[UploadFile] = File(default=[])` + `file: Optional[UploadFile]`
  (campo legacy). Se normalizan en una sola lista.
- Tope `_MAX_UPLOAD_FILES = 5`.
- Cada archivo se procesa independientemente (decode + compresión HAR + formato).

### Helpers nuevos
| Helper | Rol |
|---|---|
| `_process_uploaded_file(filename, raw_bytes)` | Pipeline por archivo (extraído del endpoint): decode → HAR compress → `_detect_and_format` → contexto HAR. Devuelve `(kind, ctx, raw, stats)`. |
| `_build_unified_file_context(processed)` | 1 archivo → contenido directo (idéntico a pre-2.9); N → marcadores `=== FLUJO DIVIDIDO EN N ARCHIVOS ===` + instrucción de correlación + numeración cronológica global. |
| `_aggregate_compression_stats(processed)` | Suma original/compressed/entries de todos los HAR para el banner; `files: N`. |

> **Diseño clave:** tras procesar, el endpoint reusa los **mismos nombres de
> variable** (`file_ctx`, `raw_text`, `kind`, `filename`, `compression_stats`)
> con valores multi-aware. Así todo el flujo downstream (2.7b auto-continuación,
> 2.7c selección de prompt, returns) quedó **intacto** y 1 archivo se comporta
> exactamente como antes.

### 🐛 Bug encontrado y corregido durante el sprint
`files: Optional[List[UploadFile]]` provocaba **HTTP 422** ("Input should be a
valid list") al enviar UN solo `files=`: FastAPI solo usa `form.getlist()`
(envolviendo un part único en lista de 1) cuando la anotación es un `List` puro;
el `Optional` lo rompía. **Fix:** `List[UploadFile] = File(default=[])`.
Verificado por curl (ver abajo).

### SYSTEM_PROMPT
Nueva sección **"REGLAS DE MULTI-HAR"** (antes de FORMATO DE RESPUESTA):
procesar varios archivos como un solo flujo, reusar tokens entre archivos, UN
solo JMX, numeración cronológica global, deduplicar empalmes.

---

## Frontend — `frontend/src/pages/AIScriptDesigner.tsx` (+~34 líneas)

- Estado `pendingFile: File | null` → **`pendingFiles: File[]`** (`MAX_FILES = 5`).
- `<input type="file">` con atributo **`multiple`**.
- `handleFileChange` acumula archivos (respeta tope); `removePendingFile(index)`.
- Subida: `form.append('files', f)` por cada archivo (campo `files`).
- **Lista de chips** con tamaño y botón eliminar individual + aviso "💡 la IA
  procesará los N archivos como un solo flujo continuo" cuando hay ≥2.
- `actionLabel`, placeholder, botón disabled y reset de conversación adaptados.

> **`frontend/src/services/api.ts` NO se modificó:** la llamada a
> `/generate-from-file` se construye **inline** en el componente (FormData con
> `aiApi.post`), no vía un método de `api.ts`. El backup se hizo igualmente.

---

## Verificación de compatibilidad backward (curl)

| Caso | Resultado |
|---|---|
| `files=` (1 archivo, campo nuevo) | **HTTP 200** ✅ (tras el fix del 422) |
| `files=` x2 (multi) | **HTTP 200** ✅ |
| `file=` (campo legacy singular) | **HTTP 200** ✅ |

---

## Tests — `backend/tests/test_multi_file_generation.py` (nuevo, 90 líneas, 7 tests)

- `_build_unified_file_context`: 1 archivo directo / N con marcadores / instrucción
  de correlación / 3 archivos (4).
- `_aggregate_compression_stats`: suma + `files` / sin HAR → None (2).
- `SYSTEM_PROMPT` incluye reglas multi-HAR (1).

**Suite: 165 → 172 PASS** (+7), 2 deselected. `tsc --noEmit` EXIT=0.

---

## Validaciones

| Check | Resultado |
|---|---|
| `pytest -m "not slow"` | **172 passed**, 2 deselected |
| Tests nuevos | 7 PASS |
| `npx tsc --noEmit` | **EXIT=0** |
| Backward compat (curl) | `files` single/multi + `file` legacy → todos HTTP 200 |
| Backend reload | `Application startup complete` |
| Docker rebuild | **NO** |
| Backups | `script_ai.py.bak_29_*`, `AIScriptDesigner.tsx.bak_29_*`, `api.ts.bak_29_*` |

---

## Estado: SPRINT 2.8 + 2.9 COMPLETOS

Listo para **VALIDACIÓN VISUAL TOTAL** con dataset real (incluye el flujo
Bancoomeva en 2 HARs). Como siempre: los tests garantizan estructura y compat,
no que el modelo cumpla la correlación cross-HAR — eso lo confirma la validación
visual de Fredy.

### Pendientes para sprints futuros
- Multi-formato mezclado (Postman + HAR) — fuera de alcance de 2.9.
- `set-cookie` en `KEEP_HEADERS` del compressor (detección de auth por cookie),
  pendiente desde 2.8.
