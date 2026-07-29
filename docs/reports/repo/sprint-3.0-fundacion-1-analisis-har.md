# Sprint 3.0 — Fundación 1: Análisis multi-fase del HAR

**Fecha:** 2026-07-28
**Branch:** `backup-trabajo-local`
**Base:** `6b665c7` (docs HF21) sobre `7335f8f` (HF21)
**Estado:** implementado, testeado y validado end-to-end contra la BD real.

---

## 1. Qué resuelve

El AI Script Designer ya convierte un HAR en JMX de un solo tiro: manda el HAR
comprimido entero al modelo y espera que el JMX salga correlacionado. Lo que no
existía era un paso previo que respondiera, de forma explícita y persistida,
dos preguntas distintas:

1. **¿Qué es cada request?** — navegación, XHR de lectura, autenticación,
   escritura de negocio, o catálogo/configuración.
2. **¿Qué dato viaja de un request a otro?** — tokens de sesión, CSRF, IDs de
   recurso creados: la materia prima de los extractores de JMeter.

Esta fundación separa esas dos preguntas en **dos llamadas independientes al
modelo** y persiste el resultado en la fila del diseño, de modo que quede
disponible para las fases siguientes del sprint sin volver a pagar el análisis.

**Nada de esto bloquea el flujo de generación vigente.** `/generate`,
`/generate-from-file` y `/refine` quedaron intactos.

---

## 2. Migración SQL (sin Alembic)

El proyecto no usa Alembic (regla #10 de `CLAUDE.md`): `Base.metadata.create_all`
solo **crea tablas nuevas**, nunca agrega columnas a tablas existentes. Las tres
columnas se aplicaron con `ALTER TABLE` manual.

Script versionado en
`backend/migrations/sql/sprint-3.0-fundacion-1-har-analysis.sql`.

### ADD (aplicado)

```sql
ALTER TABLE ai_script_designs
    ADD COLUMN IF NOT EXISTS har_analysis_classification JSONB,
    ADD COLUMN IF NOT EXISTS har_analysis_dependencies   JSONB,
    ADD COLUMN IF NOT EXISTS har_analysis_status         VARCHAR(32);

COMMENT ON COLUMN ai_script_designs.har_analysis_classification IS
    'Sprint 3.0 F1 — Fase 1: {version, source_sha1, total_entries, counts, entries[], phase2_error}';
COMMENT ON COLUMN ai_script_designs.har_analysis_dependencies IS
    'Sprint 3.0 F1 — Fase 2: {version, analyzed_entries, dependencies[{source_idx, target_idx, data_name, locations, extractor_hint, confidence}]}';
COMMENT ON COLUMN ai_script_designs.har_analysis_status IS
    'Sprint 3.0 F1 — completed | skipped | failed (failed retiene Fase 1)';
```

### DROP (rollback completo)

```sql
ALTER TABLE ai_script_designs
    DROP COLUMN IF EXISTS har_analysis_classification,
    DROP COLUMN IF EXISTS har_analysis_dependencies,
    DROP COLUMN IF EXISTS har_analysis_status;
```

### Reset sin perder el schema

Si lo único que se quiere es re-correr el análisis, no hace falta el DROP:

```sql
UPDATE ai_script_designs
   SET har_analysis_classification = NULL,
       har_analysis_dependencies   = NULL,
       har_analysis_status         = NULL
 WHERE reference_file_type = 'har';
```

…o llamar al endpoint con `?force=true`.

### Aplicación

```bash
docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
  < backend/migrations/sql/sprint-3.0-fundacion-1-har-analysis.sql
```

Las tres columnas son **nullable**: los 9 diseños HAR ya existentes quedaron en
`NULL` y ningún código previo se entera. No hay backfill.

Verificación post-aplicación:

```
         column_name         |     data_type     | is_nullable
-----------------------------+-------------------+-------------
 har_analysis_classification | jsonb             | YES
 har_analysis_dependencies   | jsonb             | YES
 har_analysis_status         | character varying | YES
```

---

## 3. Cambios por archivo

| Archivo | Δ | Qué |
|---|---:|---|
| `backend/app/services/ai/har_flow_analyzer.py` | +557 | **Nuevo.** Módulo del análisis. |
| `backend/tests/test_har_flow_analyzer.py` | +436 | **Nuevo.** 37 tests del analyzer. |
| `backend/tests/test_analyze_har_endpoint.py` | +297 | **Nuevo.** 14 tests del endpoint. |
| `backend/app/api/v1/endpoints/script_ai.py` | +137 | Endpoint `analyze-har` + imports. |
| `backend/migrations/sql/…-har-analysis.sql` | +47 | **Nuevo.** ADD/DROP documentado. |
| `backend/app/db/models/ai_script_design.py` | +19 | 3 columnas, estilo `Column()`. |
| `frontend/src/services/api.ts` | +7 | Cliente `analyzeHar`. |
| `frontend/src/pages/AIScriptDesigner.tsx` | +6 | Disparo fire-and-forget. |

**Total: 8 archivos, 1506 inserciones, 0 borrados** (`git diff --cached --stat`).
Ningún archivo protegido fue tocado.

---

## 4. El analyzer — `backend/app/services/ai/har_flow_analyzer.py`

### Lectura del HAR

`extract_entries()` lee
`json.loads(reference_file_content)["log"]["entries"]`. Ese contenido es la
salida de `compress_har()` (assets estáticos, tracking y duplicados ya
filtrados), que conserva el shape original del HAR. Verificado contra la BD:
los 9 diseños HAR responden a `jsonb_array_length(…->'log'->'entries')` con
valores entre 10 y 106.

Cualquier defecto de forma (JSON roto, sin `log`, `entries` no-lista, contenido
vacío) levanta `HarAnalysisError`, nunca un `KeyError` suelto.

### Fase 1 — clasificación

Categorías: `navigation` · `xhr` · `auth` · `write` · `config`.
El prompt exige **solo JSON** y define desempates explícitos
(`auth` gana sobre `write`; `config` gana sobre `xhr`).

`parse_phase1_response()` normaliza la salida contra los digests enviados:

- Categoría inventada por el modelo → `xhr`.
- Entry que el modelo se saltó → `xhr` con `reason` = "sin clasificar por la IA".
- Acepta `{"entries": […]}` o la lista suelta.
- Si no clasificó **nada** → `HarAnalysisError`.

El resultado siempre cubre el 100% de los entries: la Fase 2 nunca opera sobre
un universo incompleto.

### Fase 2 — dependencias

Corre **solo sobre entries funcionales** —
`FUNCTIONAL_CATEGORIES = (auth, write, xhr, config)`. `navigation` queda fuera:
son cargas de página HTML que rara vez producen el dato que otro request
consume.

Cada dependencia lleva `source_idx`, `target_idx`, `data_name`, `locations[]`,
`extractor_hint` y `confidence`. `parse_phase2_response()` descarta lo que el
modelo alucina:

- `source_idx >= target_idx` (un dato no puede consumirse antes de producirse).
- `idx` que no estaba en el universo enviado.
- `locations` como string suelto → se normaliza a lista.
- `confidence` fuera de `high|medium|low` → `medium`.

### Umbral de auto-análisis

`_MIN_ENTRIES_FOR_AUTO_ANALYSIS = 20`. Por debajo, `status='skipped'` y **cero
llamadas al modelo**: una grabación de 8 requests se entiende leyéndola.

### Parser de respuestas

`parse_ai_json()` tolera lo que los modelos hacen aunque el prompt lo prohíba:
fences ```` ```json ````, fences sin lenguaje, prosa antes y/o después. Como
último recurso recorta desde el primer `{`/`[` hasta su cierre exterior. Sin
JSON parseable → `HarAnalysisError`.

### Fase 2 falla → Fase 1 se retiene

Contrato explícito: si la segunda llamada revienta (excepción del proveedor,
JSON basura, timeout), la clasificación **se conserva**, el motivo queda en
`classification.phase2_error`, `har_analysis_dependencies` queda `NULL` y el
status es `failed`.

### Orquestación

Síncrona, sin cliente de IA propio: el caller inyecta
`call_ai(messages) -> str`. El endpoint envuelve ahí el `_call_ai` de
`script_ai.py` (que ya resuelve OpenAI vs Gemini). Consecuencia práctica: **el
módulo se testea entero sin red y sin API key**.

---

## 5. El endpoint

`POST /api/v1/script-designer/ai/designs/{design_id}/analyze-har`
Roles `admin | analyst`. Query param opcional `force=true`.

Design-aware a propósito: `/generate-from-file` y `/refine` son stateless y no
tienen dónde persistir el resultado.

| Situación | Respuesta |
|---|---|
| Diseño inexistente | **404** |
| No-admin sobre diseño ajeno | **403** |
| `reference_file_type != 'har'` | **400** (nombra el tipo real) |
| Límite de uso de IA alcanzado | **429** |
| Sin API key configurada | **503** |
| Análisis vigente del mismo HAR | **200** `reused: true`, sin llamar a la IA |
| HAR ilegible / análisis fallido | **200** `status: "failed"` + `error` |
| OK | **200** con conteos y nº de dependencias |

El caso fallido devuelve **200, no 500**, a propósito: un fire-and-forget del
frontend no puede explotarle en la cara al usuario por un HAR raro.

### Idempotencia

El auto-save dispara `upsert` en **cada turno** de la conversación. Sin guarda,
un fire-and-forget gastaría 2 llamadas al modelo por turno.

La guarda usa el **SHA1 del HAR guardado dentro del JSON de clasificación**
(`classification.source_sha1`), no una cuarta columna. Si el HAR cambia, el hash
no coincide y el análisis se rehace solo. `?force=true` lo fuerza siempre.

---

## 6. Wiring frontend

Mínimo, **13 líneas** en total (presupuesto: ~15):

- `api.ts` (+7): método `analyzeHar(id)`.
- `AIScriptDesigner.tsx` (+6): tras el upsert exitoso, si
  `reference_file_type === 'har'` y hay contenido, dispara
  `void aiScriptDesignsAPI.analyzeHar(saved.id).catch(() => undefined)`.

Es seguro por construcción: fire-and-forget con `.catch` mudo, sobre un endpoint
idempotente que además nunca devuelve 5xx por fallas del análisis.

`npx tsc --noEmit` limpio.

---

## 7. Tests

Contados con `pytest`, no estimados:

| Momento | Resultado |
|---|---|
| Baseline (`6b665c7`) | **208 passed** en 35.70s |
| Después de Fundación 1 | **259 passed** en 38.46s |
| Delta | **+51** |

- `test_har_flow_analyzer.py` — **37 tests**: shape real del HAR (incluye los 4
  modos de HAR inválido), umbral 20, digests, parser JSON (4 formas de
  envoltura), Fase 1 (conteos, categoría inválida, entry no clasificado, lista
  suelta), filtrado de `navigation` en Fase 2, descarte de dependencias
  imposibles, flujo completo, Fase 2 fallida reteniendo Fase 1, Fase 1 fallida,
  HAR ilegible, fingerprint.
- `test_analyze_har_endpoint.py` — **14 tests**: 404, 400 (con tipo y sin
  archivo), 403, admin sobre diseño ajeno, reuso idempotente, invalidación por
  HAR cambiado, `failed` no se reusa, `force`, persistencia de las 3 columnas,
  Fase 2 fallida, HAR ilegible → 200 no 500, 503 sin API key, 429 por límite.

Ningún test del baseline se modificó.

---

## 8. Validación en vivo (curl + SELECT)

Contra la BD real, con `openai / gpt-4.1` como provider activo.

**Umbral (10 entries):**

```json
{"design_id":"aa4840d6-…","status":"skipped","error":"HAR con 10 entries funcionales; el analisis automatico requiere al menos 20."}
```

**Análisis real (106 entries — Veritran):**

```json
{"status":"completed","total_entries":106,"analyzed_entries":106,
 "counts":{"navigation":7,"xhr":2,"auth":4,"write":9,"config":84},
 "dependencies_found":0}
```

**Análisis real (105 entries — Pideky):**

```json
{"status":"completed","total_entries":105,
 "counts":{"navigation":5,"xhr":82,"auth":5,"write":2,"config":11},
 "dependencies_found":4}
```

Dependencias detectadas en Pideky (persistidas):

```
 src | tgt |    dato     | conf |                 extractor
-----+-----+-------------+------+-------------------------------------------
 6   | 11  | AccessToken | high | JSON Extractor sobre $.AuthenticationResult.AccessToken
 91  | 97  | orderPideky | high | JSON Extractor sobre $.orders[0].orderPideky …
 91  | 99  | orderPideky | high | JSON Extractor sobre $.orders[0].orderPideky …
 91  | 101 | orderPideky | high | JSON Extractor sobre $.orders[0].orderPideky …
```

Son correlaciones reales y accionables: el `AccessToken` de Cognito y el ID de
orden que tres requests posteriores consumen.

**Estado persistido:**

```
                  id                  |  status   |                       counts                        | clasificados | fase2_entries | deps
--------------------------------------+-----------+-----------------------------------------------------+--------------+---------------+------
 aa4840d6-… (10 entries)              | skipped   |                                                     |              |               |
 f89920fe-… (106 entries)             | completed | {"xhr":2,"auth":4,"write":9,"config":84,"nav":7}    |          106 |            99 |    0
 97ccb36f-… (105 entries)             | completed | {"xhr":82,"auth":5,"write":2,"config":11,"nav":5}   |          105 |            99 |    4
```

**Idempotencia:** segunda llamada al mismo diseño → `"reused": true`, sin gasto
de IA.

**Errores:** `404` en UUID inexistente; `400` en un diseño Postman
(`"…este es 'postman'"`).

---

## 9. Hallazgo: 0 dependencias no siempre es un falso negativo

El HAR de 106 entries devolvió 0 dependencias. La causa está en los datos, no en
el análisis: **solo 36 de sus 106 entries traen `response.content.text`**.
`compress_har()` conserva el body de respuesta únicamente cuando el `mimeType`
contiene `json`/`xml`/`text`; en el resto, el valor producido simplemente no
está en el archivo, así que ningún modelo puede correlacionarlo.

Consecuencia para las fases siguientes: la cobertura de la Fase 2 depende de la
**calidad de la grabación**. Un HAR exportado sin cuerpos de respuesta acota
estructuralmente lo que se puede correlacionar. Vale la pena reflejar eso en la
UI antes que dejar creer que "no hay dependencias".

---

## 10. Adaptaciones respecto al prompt original

1. **Tests del endpoint sin infraestructura HTTP.** El repo no tiene
   `conftest.py`, `TestClient` ni fixtures de DB async — los 208 tests del
   baseline son unitarios sobre funciones. Montar esa infraestructura era un
   cambio estructural fuera del alcance de la fundación. Los tests invocan la
   función del endpoint **directamente**, con un doble de sesión de DB y un
   usuario falso; las `Depends` de FastAPI se saltan al pasarlas como
   argumentos. Mismos asserts (404/400/403/429/503), cero infraestructura nueva.

2. **Idempotencia por hash, no una cuarta columna.** El disparo automático desde
   el auto-save exigía una guarda o gastaba 2 llamadas al modelo por turno. El
   SHA1 del HAR vive **dentro** de `har_analysis_classification`, respetando el
   límite de 3 columnas.

3. **`status='partial'` descartado.** Se evaluó, pero el contrato acordado es
   `failed` reteniendo la Fase 1. Se implementó tal cual: `completed` |
   `skipped` | `failed`.

4. **`_call_ai` se invoca directo, sin threadpool.** Es síncrono y bloquea el
   event loop, igual que en los otros 5 puntos donde el módulo ya lo llama
   (líneas 1192, 1844, 2161, 2308, 2558). Cambiar esa convención es una decisión
   transversal, no de esta fundación.

---

## 11. Pendientes / no incluido

- **UI del análisis.** No hay panel que muestre clasificación ni dependencias:
  esta fundación solo produce y persiste el dato. Lo consumen las fases
  siguientes del sprint.
- **Los `har_analysis_*` no se exponen en `AIScriptDesignDetail`.** El schema
  Pydantic quedó intacto a propósito (diff mínimo); habrá que agregarlos cuando
  la UI los necesite.
- **Tope de 200 entries por llamada** (`_MAX_ENTRIES_PER_CALL`). Ningún HAR de
  la BD se acerca (máximo real: 106), pero un HAR mayor se analizaría parcial.
  `classification.analyzed_entries` deja constancia cuando eso pasa.
- **Rebuild de contenedores:** no ejecutado (regla #7 — el ciclo Docker lo
  controla Fredy). El backend corre con `--reload` y tomó los cambios solo; el
  frontend no se rebuildeó.
