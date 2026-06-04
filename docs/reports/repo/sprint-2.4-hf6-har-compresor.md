# Sprint 2.4-HF6 — Compresor HAR + límite 50 MB

**Fecha:** 2026-05-29
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** Aplicado y validado (sintético, sin gasto de cuota IA)

---

## 1. Resumen

Permite subir HARs reales de hasta **50 MB** (antes 5 MB) al diseñador IA. Antes de mandar el HAR a la IA el backend lo **comprime automáticamente** filtrando assets estáticos, requests de tracking, headers de ruido y duplicados — típicamente reduciendo el tamaño un **98–99%**.

El usuario ve un banner en el chat con el resumen de la compresión: `📊 HAR comprimido: 45.0 MB → 0.43 MB (99.0% reducción) · 2840 requests → 187 únicos · filtrados 1240 assets, 380 tracking`.

---

## 2. Archivos creados / modificados

| Archivo | Tipo | Líneas |
|---|---|---|
| `backend/app/services/engine/har_compressor.py` | NUEVO | 274 |
| `backend/app/api/v1/endpoints/script_ai.py` | MOD | +63 / -7 |
| `frontend/src/services/api.ts` | MOD | +4 / -1 |
| `frontend/src/pages/AIScriptDesigner.tsx` | MOD | +35 / -7 |
| `backend/tests/test_har_compressor.py` | NUEVO | 152 |

**Backups creados:**
- `backend/app/api/v1/endpoints/script_ai.py.bak_hf6_20260529_200845`
- `frontend/src/pages/AIScriptDesigner.tsx.bak_hf6_20260529_200845`
- `frontend/src/services/api.ts.bak_hf6_20260529_200845`

---

## 3. Estrategia de compresión

| Paso | Acción | Reduce |
|---|---|---|
| 1 | Filtrar entries cuyo path termina en extensión de asset (`.css`, `.js`, `.png`, `.woff2`, etc.) | 30–50% en SPAs típicas |
| 2 | Filtrar URLs de tracking (`google-analytics.com`, `googletagmanager.com`, `hotjar.com`, `segment.io`, `mixpanel.com`, ...) | 5–20% |
| 3 | Deduplicar por fingerprint = `método + URL canónica + body_hash`. URL canónica = scheme+host+path sin query string. | 60–95% |
| 4 | Truncar bodies > 2 KB con marca `...truncado (N bytes total)...` | Variable |
| 5 | Filtrar headers de ruido (`Cookie`, `User-Agent`, `sec-*`, `accept-*`, `cache-control`, `referer`, `origin`, `if-*`, etc.). Mantiene `Content-Type`, `Authorization`, `x-api-key`, `x-auth-token`, `x-csrf-token`. | Variable |
| 6 | Marcar entries duplicados con `_duplicate_count: N` para que la IA sepa la frecuencia real. | (metadata) |

El compresor mantiene el HAR como JSON válido del schema HAR 1.2 — la IA lo procesa como un HAR normal pero mucho más pequeño.

---

## 4. Flujo end-to-end

```
Frontend (upload .har file)
    │ aiApi.post('/generate-from-file', formData)  [timeout 10 min]
    ▼
Backend POST /api/v1/script-designer/ai/generate-from-file
    │
    ├─ raw_bytes = await file.read()  (hasta 50 MB)
    ├─ raw_text = raw_bytes.decode('utf-8', errors='replace')
    │
    ├─ _is_har_file(filename, raw_text) ?
    │     ├─ Sí → compress_har(raw_text) → (compressed_text, stats)
    │     │      raw_text = compressed_text   # 99% más pequeño
    │     │      kind = 'har', file_ctx = "HAR COMPRIMIDO..."
    │     └─ No → _detect_and_format() → kind='postman'/'openapi'/'text'
    │
    ├─ _call_ai(messages, ai_conf)   # IA recibe el HAR comprimido
    │
    └─ return FileGenerateResponse(
           ..., compression_stats=stats   # se devuelven al frontend
       )

Frontend recibe la respuesta
    │
    └─ Si data.compression_stats → antepone banner al mensaje del assistant:
       "📊 HAR comprimido: X MB → Y MB (Z% reducción) · N requests → M únicos · ..."
```

---

## 5. Validaciones

### 5.1. Tests backend

```
pytest tests/ -q
63 passed in 1.60s
```

- 27 `test_jmx_parser.py` (sin cambios).
- 15 `test_jmx_regenerator.py` (sin cambios).
- 13 `test_refine_operations.py` (sin cambios).
- **8 nuevos `test_har_compressor.py`**:
  - `test_detecta_assets_estaticos` ✅
  - `test_detecta_tracking` ✅
  - `test_filtra_headers_de_ruido` ✅
  - `test_canonical_url_remueve_query_dinamico` ✅
  - `test_fingerprint_detecta_duplicados` ✅
  - `test_compress_har_basico` ✅ (verifica filtros + dedup + headers + `_duplicate_count`)
  - `test_compress_har_invalido_lanza_error` ✅
  - `test_compress_har_trunca_bodies_grandes` ✅

### 5.2. TypeScript check

```
npx tsc --noEmit → EXIT=0
```

### 5.3. Detección de HAR (función `_is_har_file`)

| Entrada | Esperado | Real |
|---|---|---|
| `captura.har` + `{}` | `True` (por extensión) | ✅ True |
| `captura.json` + HAR real | `True` (por contenido) | ✅ True |
| `coleccion.json` + Postman | `False` | ✅ False |
| filename vacío + body vacío | `False` | ✅ False |

### 5.4. Prueba sintética con HAR de 1.83 MB y 2 000 entries

Generado con seed fijo (`random.seed(42)`) — 5/7 reales, 1/5 asset estático, 1/7 tracking. URLs con query string aleatorio para forzar dedup canónico:

```
HAR sintético:   1.83 MB, 2000 entries
Comprimido:      0.0083 MB
Reducción:       99.5%
Entries:         2000 → 10 únicos
Static filtered: 400
Tracking filtered: 228
```

**Implicación para HAR real de 45 MB tipo Croydonistas:** se espera comprimir a ~0.2-0.5 MB antes de enviar a la IA, cabiendo holgadamente en el context window de cualquier modelo (incluso gpt-3.5-turbo).

---

## 6. Cambios de constantes

| Constante | Antes | Después |
|---|---|---|
| `backend MAX_FILE_BYTES` | 5 MB (HF3) | **50 MB** |
| `frontend MAX_UPLOAD_BYTES` | 5 MB | **50 MB** |
| `frontend api.ts api.timeout` | 300 s | **600 s** |
| `frontend AIScriptDesigner.tsx aiApi.timeout` | 300 s (HF5) | **600 s** |
| `MAX_BODY_BYTES` (truncamiento dentro del compresor) | — | **2 048 bytes** |
| Indicador UI "Máx. 5 MB" | — | **"Máx. 50 MB · HAR comprimido automáticamente"** |

---

## 7. Cómo validar visualmente

1. Iniciar el frontend (`http://localhost:5173`) y entrar al **Diseñador IA**.
2. Adjuntar un HAR real >5 MB (ej. exportado desde DevTools de Chrome).
3. Enviar el mensaje sin texto adicional (o con instrucción ligera).
4. En el chat aparece el banner:
   `📊 HAR comprimido: X MB → Y MB (Z% reducción) · N requests → M únicos · filtrados A assets, B tracking`
5. Confirmar que el JMX generado refleja las transacciones únicas (no los assets).

---

## 8. Garantías de no-regresión

- Postman / OpenAPI / texto siguen funcionando — `_is_har_file` devuelve `False` para esos casos y el flujo cae a `_detect_and_format` igual que antes.
- `compression_stats` es `Optional`, los call sites del frontend que no son HAR reciben `null` y siguen el flujo normal.
- 55/55 tests pre-HF6 siguen verdes (no se tocó ningún test existente).
- `tsc --noEmit` → EXIT=0.

---

## 9. Estado

**LISTO para HF7 (paridad JMeter) o validación visual de Fredy en navegador.**

No se hizo `docker compose build` ni `up`. Backend recargó vía `--reload` de uvicorn dev.

### Próximas mejoras sugeridas (no bloquean HF6)

- Hacer las listas de extensiones / patrones de tracking configurables vía env vars.
- Soportar HAR comprimido con gzip (`.har.gz`) directamente sin que el usuario tenga que descomprimirlo.
- Telemetría: log de `compression_stats` para medir la efectividad en HARs reales en producción.
