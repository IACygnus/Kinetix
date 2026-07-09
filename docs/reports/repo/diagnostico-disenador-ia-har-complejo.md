# Diagnóstico Forense — Fallo del Diseñador IA con HAR complejo (erpoci)

> **Modo:** READ-ONLY. No se modificó ningún archivo del proyecto, ni la DB, ni
> git. Único artefacto creado: este reporte.
> **Fecha:** 2026-06-08
> **Diseño analizado:** `aa4840d6-d623-4534-b589-efffdf3a397c`
> **Archivo de referencia:** `erpoci.colcomercio.com.har` (PeopleSoft / ICAJAX)

---

## 1. Estado del diseño erpoci en DB

Tabla real: `ai_script_designs` (no `script_designs`).

| Campo | Valor |
|---|---|
| id | `aa4840d6-d623-4534-b589-efffdf3a397c` |
| name | `(null)` |
| is_draft | `true` |
| updated_at | `2026-06-08 21:12:28+00` |
| **`current_jmx` (longitud)** | **0 bytes (VACÍO)** |
| reference_file_name | `erpoci.colcomercio.com.har` |
| reference_file_content (longitud) | 44 479 bytes (HAR ya comprimido) |
| conversation | 2 mensajes |

Conversación:
- Mensaje 1 — `user`, 173 chars (prompt).
- Mensaje 2 — `assistant`, **28 413 chars**.

El mensaje del assistant **SÍ contiene un JMX**, pero está **truncado**:
- Abre el bloque ` ```xml ` (línea 29) y `<?xml ...` (línea 30).
- Abre `<jmeterTestPlan>` (1 ocurrencia) → **`</jmeterTestPlan>` = 0 (nunca cierra)**.
- Solo el fence de apertura presente; **no hay fence de cierre** ` ``` `.
- Solo llegó al **Sampler 6** (de los ~10 únicos del HAR). 6 comentarios
  `<!-- Sampler N -->`, 11 `HTTPSamplerProxy`.
- El texto se corta literalmente a media línea del body POST de PeopleSoft:
  `...&amp;ICResubmit=0&amp;ICSID=P6kWUi1vdao` ← fin abrupto.

**Conclusión #1:** `current_jmx` quedó VACÍO porque la respuesta de la IA se cortó
a la mitad y el extractor no encontró un bloque JMX cerrado.

---

## 2. Logs del backend

Línea exacta del intento erpoci (`docker logs jmeter_backend`):

```
HAR comprimido erpoci.colcomercio.com.har: 3710563 -> 44479 bytes (98.8% reduccion), entries 61 -> 10
file upload kind=har name=erpoci.colcomercio.com.har size=3710563
OpenAI call model=gpt-4o max_tokens=8192 finish_reason=length
POST /api/v1/script-designer/ai/generate-from-file HTTP/1.1" 200 OK
```

- **`finish_reason=length`** ← evidencia definitiva: el modelo agotó el tope de
  output (`max_tokens=8192`) y la generación se cortó.
- `max_tokens=8192` ← el endpoint `/generate-from-file` usa el cap legacy fijo.
- HTTP 200 OK: el endpoint devolvió el "error" como payload 200 (campo `error`),
  no como excepción.
- Timeouts: ninguno.

---

## 3. Config IA actual

`SELECT ... FROM ai_config WHERE is_active=true`:

| Campo | Valor |
|---|---|
| provider | `openai` |
| model_name | `gpt-4o` |
| daily_requests_used / limit | 0 / 1000 |
| monthly_requests_used / limit | 12 / 20000 |

- Límites lejos de saturarse — **no es problema de cuota**.
- `gpt-4o` permite hasta **16 384** tokens de output (`OPENAI_MAX_TOKENS["gpt-4o"]
  = 16384`), pero la generación **se autolimita a 8192**.
- Context window de entrada de gpt-4o (128K) sobra para el HAR comprimido
  (~11K tokens). El cuello de botella es **el output, no el input**.

---

## 4. HAR processing

`backend/app/services/engine/har_compressor.py`:
- `MAX_BODY_BYTES = 2048` → cada body POST se trunca a 2 KB.
- Filtra assets estáticos (`_is_static_asset`) y tracking (`_is_tracking`).
- Deduplica por `método + URL canónica + hash de body`.
- Resultado erpoci: 3.5 MB → 0.04 MB (98.8 %), 61 → 10 entries.

`backend/app/api/v1/endpoints/script_ai.py`:
- `MAX_FILE_BYTES = 50 MB` (no fue el límite — el HAR crudo pesaba 3.5 MB).
- Tras comprimir, se manda el HAR comprimido **completo** (44 479 bytes ≈
  ~11K tokens) como contexto del prompt.
- La compresión de **entrada funciona bien**. El problema está aguas abajo, en
  el **límite de salida**.

> Nota PeopleSoft: cada transacción ICAJAX trae bodies `x-www-form-urlencoded`
> enormes (decenas de parámetros `IC*`). Aun truncados a 2 KB c/u, 10 samplers
> con esos bodies + boilerplate JMX exceden de sobra 8192 tokens de salida.

---

## 5. Auto-save

`frontend/src/pages/AIScriptDesigner.tsx`:
- Tras CADA turno (líneas 583-590) se llama `performAutoSave(...)`
  **incondicionalmente**, exitoso o no.
- `current_jmx: data.jmx_content || currentJmx || null` → con extracción fallida,
  `data.jmx_content = ""` → cae a `currentJmx` ("") → persiste vacío/null.
- **No hay validación XML antes del upsert.** Se persiste:
  - la conversación (incluido el assistant de 28 413 chars truncado),
  - `current_jmx` VACÍO.
- Eso explica el "Guardado hace 20s": auto-save de un borrador con JMX vacío.

**Conclusión #5:** No hay corrupción de DB — sólo un draft con conversación
guardada y JMX vacío. Pero **el JMX parcial generado (6 samplers) se pierde**:
queda enterrado en el texto del assistant y nunca se ofrece al usuario.

---

## 6. Detector de error

`backend/app/api/v1/endpoints/script_ai.py`:
- Extractor: `_extract_jmx_and_explanation` (líneas 620-635) con dos regex:
  - `_JMX_FENCE_RE` = ` ```(xml|jmx)? (<?xml ... </jmeterTestPlan>) ``` `
  - `_JMX_BARE_RE` = `(<?xml ... </jmeterTestPlan>)`
- **Ambos exigen `</jmeterTestPlan>` de cierre.** Con output truncado no
  matchean → retorna `("", explanation)`.
- Mensaje disparado en `/generate-from-file` (líneas 1370-1381):
  `"La IA no devolvio un bloque JMX. Reformula tu prompt o revisa el archivo."`
- **Recupera JMX parcial:** NO. Se descarta.
- **Diagnóstico engañoso:** sugiere "reformula tu prompt", cuando la causa real
  es truncación por límite de tokens.
- Asimetría notable: `/refine` SÍ detecta el caso truncado (líneas 1462-1474:
  `"<?xml" in raw_text and "</jmeterTestPlan>" not in raw_text` → mensaje
  específico "respuesta truncada, usa modelo con mayor capacidad"). **`/generate`
  y `/generate-from-file` NO tienen esa detección.**

---

## 7. Tamaño prompt vs límite modelo

| Métrica | Valor estimado |
|---|---|
| HAR comprimido (input) | 44 479 bytes ≈ **~11K tokens** |
| System prompt (`SYSTEM_PROMPT`) | ~9 600 chars ≈ **~2.6K tokens** |
| Input total | ~14K tokens (cabe sobradamente en los 128K de gpt-4o) |
| Output generado antes de cortar | 28 413 chars ≈ **~7.5K tokens** |
| **Tope de output configurado** | **8192 tokens** ← se alcanzó (`finish_reason=length`) |
| Output necesario (10 samplers PeopleSoft completos) | estimado **15K-25K tokens** |

**El input cabe; el output NO.** El JMX completo para 10 transacciones PeopleSoft
con bodies grandes excede 8192 tokens, y el cap de generación está fijo en 8192
aunque gpt-4o soporta 16384 (y gpt-4.1 hasta 32768).

---

## 8. System prompt

`SYSTEM_PROMPT` (líneas 106-343, ~9.6K chars):
- **Cubre HARs grandes:** NO. No hay instrucciones para HAR ni para limitar el
  tamaño de salida / priorizar transacciones.
- **Cubre PeopleSoft / apps empresariales con bodies ICAJAX gigantes:** NO.
- Sí exige "JMX COMPLETO" con 10 secciones obligatorias, assertions y header
  manager en CADA sampler → **empuja al modelo a producir MÁS output**, lo que
  agrava la truncación con HARs grandes.
- Sí instruye devolver el JMX dentro de ` ```xml ... ``` ` (formato de respuesta,
  sección final).

---

## CAUSA RAÍZ DEL FALLO ERPOCI

**Truncación de la salida del modelo por el tope fijo de `max_tokens=8192` en el
endpoint `/generate-from-file`.**

Cadena causal:
1. HAR PeopleSoft con 10 transacciones de bodies `urlencoded` grandes (ICAJAX).
2. El SYSTEM_PROMPT exige un JMX completo y verboso (header manager + assertion +
   extractor por sampler) → output objetivo ~15-25K tokens.
3. `/generate-from-file` llama `_call_ai(messages, ai_conf)` **sin
   `max_tokens_override`** → cae al `else` (línea 1094) → `effective_max_tokens =
   8192`. (Confirmado en logs: `finish_reason=length`.)
4. El modelo se corta en el Sampler 6, a media línea del body, sin cerrar
   `</jmeterTestPlan>` ni el fence ` ``` `.
5. `_extract_jmx_and_explanation` exige `</jmeterTestPlan>` → no matchea →
   `jmx=""`.
6. El endpoint devuelve `error="La IA no devolvio un bloque JMX..."` (diagnóstico
   engañoso; el problema no es el prompt sino el truncado).
7. El frontend auto-guarda igualmente el draft con `current_jmx` vacío
   ("Guardado hace 20s"), descartando los 6 samplers ya generados.

**No es** problema de cuota, ni de timeout, ni de tamaño de input, ni del
compresor HAR. Es **exclusivamente el límite de output de generación** + la falta
de manejo del caso truncado en el path de generación.

---

## COMPONENTES A ENDURECER PARA ESCALAR A CUALQUIER CLIENTE

Ordenados por prioridad:

1. **`_call_ai` / `/generate-from-file` / `/generate` — max_tokens de generación.**
   Problema: cap fijo 8192, ignora el techo real del modelo. Fix: usar
   `OPENAI_MAX_TOKENS.get(model, ...)` (16384 para gpt-4o, 32768 para gpt-4.1)
   igual que ya hace `/refine`. Es el fix de mayor impacto y menor riesgo.

2. **Detección de truncado en el path de generación.** Problema: solo `/refine`
   distingue "truncado" de "sin JMX". Fix: portar la lógica
   `"<?xml" in raw and "</jmeterTestPlan>" not in raw` a `/generate-from-file` y
   `/generate`, con mensaje accionable ("HAR muy grande, sube el modelo o pide
   menos transacciones").

3. **Recuperación / cierre del JMX parcial.** Problema: 6 samplers válidos se
   tiran a la basura. Fix (opcional, mayor esfuerzo): si el output trae N
   samplers pero está truncado, ofrecer auto-continuación (segundo turno
   "continúa el JMX desde donde quedó") o cerrar el XML parcial y avisar.

4. **SYSTEM_PROMPT consciente del tamaño.** Problema: empuja verbosidad ilimitada.
   Fix: para HARs grandes, instruir priorizar las N transacciones de negocio,
   agrupar duplicados y evitar repetición innecesaria de bodies.

5. **Auto-save con guarda de validez.** Problema: persiste drafts con JMX vacío
   sin avisar. Fix: marcar el draft como "generación incompleta" o no sobrescribir
   un `current_jmx` previo válido con uno vacío.

6. **Estrategia para HARs muy grandes (futuro).** Para apps con >15-20
   transacciones únicas, una sola llamada nunca cabrá en el output. Fix
   arquitectónico: generación por lotes (samplers en tandas) y ensamblado backend,
   o pipeline HAR→estructura→JMX local (similar al refine quirúrgico ya existente).

---

## PLAN DE FIXES PROPUESTO

### Sprint inmediato — HF15 (Endurecimiento Diseñador IA: truncación)

Alcance: **1 archivo backend**, quirúrgico.

- **Fix A — Subir max_tokens de generación** (`script_ai.py`, `_call_ai` y/o los
  dos endpoints de generación). Reemplazar el `effective_max_tokens = 8192` por
  el techo del modelo (`OPENAI_MAX_TOKENS.get(model, OPENAI_DEFAULT_MAX_TOKENS)`),
  reutilizando el patrón de `/refine`. ~5-15 líneas.
- **Fix B — Detección de truncado en generación.** Portar el bloque
  `truncated_xml` de `/refine` a `/generate-from-file` y `/generate`, con mensaje
  específico. ~15-20 líneas.

Total estimado: ~20-35 líneas, 1 archivo (`script_ai.py`). Sin tocar DB, sin
tocar frontend en esta tanda. Validación: re-subir el HAR erpoci y verificar
`finish_reason=stop` + `</jmeterTestPlan>` presente.

### Sprint posterior — HF16+ (robustez y UX)

- Fix #3 (recuperación de JMX parcial / auto-continuación).
- Fix #4 (SYSTEM_PROMPT consciente de tamaño para HAR/PeopleSoft).
- Fix #5 (auto-save con guarda de validez) — `AIScriptDesigner.tsx`.
- Fix #6 (generación por lotes para HARs > ~15 transacciones) — cambio
  arquitectónico, planificar aparte.

---

## CONFIRMACIÓN

- **Nada fue modificado.** Solo lecturas: `docker ps`, `psql` con `SELECT`/`\d`,
  `docker logs`, `grep`, `Read`. Sin ALTER/UPDATE/DELETE, sin git add/commit/push,
  sin edición de archivos del proyecto.
- Único artefacto creado: **este reporte** (`docs/reports/diagnostico-disenador-ia-har-complejo.md`).
