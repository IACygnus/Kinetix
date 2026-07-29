# Sprint 3.0 — Fundación 2: Generación de JMX por chunks

**Fecha:** 2026-07-28
**Branch:** `backup-trabajo-local`
**Base:** `04042a9` (docs F1) sobre `31906ba` (Fundación 1)
**Estado:** implementado y testeado. Validación en vivo en la sección 9.

---

## 1. Qué resuelve

La Fundación 1 dejó el HAR clasificado y sus dependencias detectadas. Lo que
seguía sin resolverse es el techo físico del modelo: **un HAR de 100+ requests
no entra en una sola respuesta.**

El techo de salida de `gpt-4.1` son 32K tokens. Eso alcanza para unos 30
samplers completos —con Header Manager, body, Response Assertion y
extractores—. Más allá de eso el modelo corta el XML a mitad de un sampler y el
JMX sale inservible. El síntoma ya estaba diagnosticado en el repo: es
exactamente lo que `_detect_truncation` viene detectando desde HF18a, y el
mensaje que se le muestra al usuario ("reduce el HAR", "pide solo las
transacciones más críticas") es una rendición, no una solución.

Esta fundación cambia el problema: en vez de **una respuesta gigante que puede
truncarse**, son **N respuestas chicas que se ensamblan**.

**Backward compat total.** Un HAR chico, o un diseño sin análisis, sigue por el
flujo de siempre. `/generate`, `/generate-from-file` y `/refine` no se tocaron.

---

## 2. Migración SQL (sin Alembic)

Script versionado en
`backend/migrations/sql/sprint-3.0-fundacion-2-chunking.sql`.

### ADD (aplicado)

```sql
ALTER TABLE ai_script_designs
    ADD COLUMN IF NOT EXISTS generation_mode         VARCHAR(32),
    ADD COLUMN IF NOT EXISTS chunks_plan             JSONB,
    ADD COLUMN IF NOT EXISTS chunks_completed_count  INTEGER,
    ADD COLUMN IF NOT EXISTS generation_status       VARCHAR(32);

COMMENT ON COLUMN ai_script_designs.generation_mode IS
    'Sprint 3.0 F2 — single | chunked. NULL = generado por el flujo clasico.';
COMMENT ON COLUMN ai_script_designs.chunks_plan IS
    'Sprint 3.0 F2 — [{chunk_id, name, entry_idxs[], categories[], status, is_skeleton, failure_reason}]';
COMMENT ON COLUMN ai_script_designs.chunks_completed_count IS
    'Sprint 3.0 F2 — chunks con status=completed; se recalcula desde chunks_plan en cada retry.';
COMMENT ON COLUMN ai_script_designs.generation_status IS
    'Sprint 3.0 F2 — completed | partial | failed';
```

### DROP (rollback completo)

```sql
ALTER TABLE ai_script_designs
    DROP COLUMN IF EXISTS generation_mode,
    DROP COLUMN IF EXISTS chunks_plan,
    DROP COLUMN IF EXISTS chunks_completed_count,
    DROP COLUMN IF EXISTS generation_status;
```

El DROP borra el **plan**, no el JMX: `current_jmx` es una columna aparte y no
se toca. Para re-planificar sin tocar el schema:

```sql
UPDATE ai_script_designs
   SET generation_mode = NULL, chunks_plan = NULL,
       chunks_completed_count = NULL, generation_status = NULL
 WHERE id = '<design_id>';
```

Las cuatro columnas son nullable. Un diseño generado por el flujo clásico las
deja en `NULL` y nada previo se entera.

---

## 3. Cambios por archivo

| Archivo | Δ | Qué |
|---|---:|---|
| `backend/tests/test_chunked_generation_endpoint.py` *(nuevo)* | +514 | 24 tests de orquestación. |
| `backend/app/services/ai/har_chunk_router.py` *(nuevo)* | +492 | Umbral, partición, dependencias por chunk, prompts. |
| `backend/app/api/v1/endpoints/script_ai.py` | +398 | 2 endpoints + `process_pending_chunks`. |
| `backend/tests/test_har_chunk_router.py` *(nuevo)* | +378 | 33 tests del router. |
| `backend/tests/test_jmx_chunk_assembler.py` *(nuevo)* | +328 | 33 tests del ensamblador. |
| `backend/app/services/ai/jmx_chunk_assembler.py` *(nuevo)* | +274 | Cirugía XML incremental. |
| `backend/migrations/sql/…-fundacion-2-chunking.sql` *(nuevo)* | +48 | ADD/DROP. |
| `backend/app/db/models/ai_script_design.py` | +21 −1 | 4 columnas + import de `Integer`. |

**Total: 8 archivos, 2452 inserciones, 1 borrado** (`git diff --cached --stat`).
Sin cambios en frontend. Ningún archivo protegido tocado.

---

## 4. El router — `har_chunk_router.py`

Lógica pura: sin DB, sin red, sin cliente de IA.

### Umbral

`_MIN_FUNCTIONAL_FOR_CHUNKING = 30`, contado sobre entries **funcionales**.

Adopta el criterio de la Fundación 1 tal cual: `FUNCTIONAL_CATEGORIES` excluye
`navigation`. Un HAR con 50 cargas de página y 5 llamadas de API cuenta **5**,
no 55, y no se parte — que es lo correcto: esas navegaciones no generan
samplers pesados. Las navegaciones viajan igual dentro del chunk 1; lo único
que no hacen es empujar la decisión.

`should_use_chunked_generation()` devuelve `(bool, motivo)`, y el motivo es
texto para el usuario que viaja tal cual en la respuesta del endpoint.

### Partición

| Chunk | Categorías | Tamaño | Salida |
|---|---|---|---|
| 1 (esqueleto) | `auth` + `navigation` + `config` | todas juntas | JMX completo y cerrado |
| 2..N | `xhr` + `write` | `_CHUNK_SIZE = 15` | solo samplers + hashTree |

El chunk 1 va primero porque es donde **nacen** los datos que todo lo demás
consume: el login produce el token, el catálogo produce los IDs. Además genera
el andamiaje (Test Plan, UDVs, HTTP Defaults, Cookie/Cache Manager, Thread
Group), así que su salida tiene que ser un JMX válido por sí solo — los
bloques siguientes insertan dentro de él.

Garantías verificadas por tests:

- **Ningún entry se pierde ni se duplica**: la unión de los `entry_idxs` de
  todos los chunks es exactamente el conjunto de idx clasificados.
- **Orden del HAR preservado** dentro de cada chunk (crítico para la
  correlación).
- **IDs incrementales sin huecos**.
- Una categoría desconocida (defensa ante una futura) se suma a transacciones
  en vez de desaparecer.
- Si el HAR no tiene entries de esqueleto, el primer bloque de transacciones
  hace de esqueleto.

### Dependencias por chunk

`get_dependencies_for_chunk()` parte las dependencias globales de la F1 en tres:

- **`produces`** — `source_idx` adentro. Los extractores que este chunk **debe**
  generar.
- **`consumes`** — `target_idx` adentro y `source_idx` afuera. Variables que
  vienen de un bloque anterior; el prompt le dice explícitamente al modelo que
  **no** vuelva a crear el extractor.
- **`internal`** — ambos extremos adentro. Subconjunto de `produces`, expuesto
  aparte porque el prompt lo trata distinto.

`variables_available_from()` arma la lista de variables ya extraídas por los
chunks **completados** anteriores. Sin esa lista el modelo re-inventa el login
en cada bloque.

### Prompts adaptativos

Los conteos salen de los datos, nunca hardcodeados: `REQUESTS DE ESTE BLOQUE
(n)` y `bloque X de Y` se calculan. Hay un test que lo verifica con n = 3, 11 y
26.

El prompt del chunk 1 exige la estructura completa de 8 puntos. El de los
siguientes prohíbe explícitamente la envoltura (`NO generes jmeterTestPlan, ni
TestPlan, ni Thread Group…`) y fija el formato de salida esperado.

---

## 5. El ensamblador — `jmx_chunk_assembler.py`

Lógica XML pura. Contrato, en orden de importancia:

### 1. El JMX previo válido nunca se corrompe

**Toda** falla devuelve `(False, jmx_original_intacto, motivo)`. Los tests
comparan el string devuelto contra el de entrada byte por byte en los cinco
caminos de fallo: fragmento sin XML, fragmento mal formado, fragmento vacío,
JMX base corrupto, JMX sin Thread Group.

### 2. Se valida re-parseando, no confiando

Después de insertar, el resultado se serializa y **se vuelve a parsear**. Si
eso falla, o si perdió el cierre de `jmeterTestPlan`, se descarta y vuelve el
original.

### 3. Prefijo `[Cn]` en el testname

Evita colisiones de nombres entre bloques y permite rastrear qué chunk generó
cada sampler. Es idempotente: un elemento que ya empieza con `[C<n>] ` no se
re-prefija (regex `^\[C\d+\]\s`).

### Detalles de implementación

- **Localización del Thread Group.** En un JMX, `<ThreadGroup/>` y su
  `<hashTree>` son **hermanos**, no padre/hijo. ElementTree no da punteros al
  padre, así que se recorre cada `hashTree` mirando sus hijos de a pares.
  Reconoce las variantes (`SetupThreadGroup`, `PostThreadGroup`, Stepping,
  Concurrency) por sufijo del tag.
- **Punto de inserción.** Después del último par sampler+hashTree, no al final
  del contenedor: así los listeners que suelen cerrar el Thread Group quedan en
  su lugar en vez de terminar en el medio del flujo.
- **Fragmentos multi-raíz.** Un fragmento tiene N elementos de primer nivel
  (sampler, hashTree, sampler, hashTree…), lo que no es XML válido por sí solo;
  se envuelve en una raíz sintética para parsearlo.
- **Declaración XML preservada** vía `ET.tostring(..., xml_declaration=True)`.

---

## 6. Contrato de los endpoints

### `POST /api/v1/script-designer/ai/designs/{design_id}/generate-chunked`

Roles `admin | analyst`.

| Situación | Respuesta |
|---|---|
| Diseño inexistente | **404** |
| No-admin sobre diseño ajeno | **403** |
| `har_analysis_status != 'completed'` | **400** — precondición estructural |
| Límite de uso de IA | **429** |
| Sin API key | **503** |
| HAR bajo el umbral | **200** `mode: "single"` + motivo |
| Un bloque falla | **200** `generation_status: "partial"` |
| OK | **200** `generation_status: "completed"` |

Mapeo alineado con `/analyze-har` de la F1: el **400** es el equivalente del
"este diseño no es un HAR" (precondición estructural), y el **200 con
`mode='single'`** es el equivalente del `status='skipped'` — no es un error,
es la respuesta correcta: el flujo clásico cubre ese caso.

Respuesta:

```json
{
  "design_id": "…", "mode": "chunked",
  "generation_status": "completed", "reason": "…",
  "total_chunks": 7, "chunks_completed": 7, "samplers_total": 96,
  "chunks": [{"chunk_id": 1, "name": "…", "status": "completed",
              "entries": 21, "is_skeleton": true, "failure_reason": null}],
  "error": null
}
```

### `POST /api/v1/script-designer/ai/designs/{design_id}/retry-failed-chunks`

| Situación | Respuesta |
|---|---|
| Sin generación por chunks en curso | **400** |
| Nada pendiente ni fallido | **200** con `reason: "nada que reintentar"` |
| Resto | igual que `generate-chunked` |

Pasa los `failed` a `pending`, **recalcula `chunks_completed_count` contando
el plan** (no confía en el valor guardado, hay un test con el contador
deliberadamente desincronizado en 99) y reanuda. Los chunks ya completados no
se re-generan ni se re-cobran.

### `process_pending_chunks(design, db, call_ai)`

- **Secuencial y no concurrente**: el chunk N necesita variables del N−1.
- **Persiste después de CADA chunk exitoso**: si el proceso se cae en el bloque
  5, los 4 anteriores ya están en la base.
- **Corta al primer fallo**; el resto queda `pending` con el motivo en
  `failure_reason` del que falló.
- **Nunca persiste un JMX inválido.**

---

## 7. Tests

Contados con `pytest`, no estimados:

| Momento | Resultado |
|---|---|
| Baseline (`04042a9`) | **259 passed** en 19.38s |
| Después de Fundación 2 | **349 passed** en 17.36s |
| Delta | **+90** |

- `test_har_chunk_router.py` — **33**: umbral (navigation no cuenta, justo en
  30, 31), partición, ids sin huecos, ningún entry perdido, orden preservado,
  bloque final parcial, categoría desconocida, produces/consumes/internal,
  variables disponibles, prompts adaptativos.
- `test_jmx_chunk_assembler.py` — **33**: inserción simple y múltiple,
  acumulación de 3 chunks, prefijos sin duplicar, listeners al final,
  declaración XML preservada, escapado de `&` (y no re-escapado de entidades
  válidas), y los 6 caminos de fallo comparando el JMX byte por byte.
- `test_chunked_generation_endpoint.py` — **24**: flujo completo, corte al
  primer fallo, persistencia de lo ganado, esqueleto inválido, fragmento
  inválido, truncación reportada explícitamente, no regenerar completados,
  variables del chunk 1 en el prompt del 2, 404/403/400/429/503, `mode=single`,
  retry (recálculo, reanudación, no regenerar esqueleto, nada pendiente).

Ningún test del baseline se modificó.

---

## 8. Adaptaciones respecto al prompt original

1. **`validate_jmx` importado con alias.** `script_ai.py` ya define un endpoint
   llamado `validate_jmx` (`POST /validate`) que ensombrecía el import del
   ensamblador — el símbolo resolvía a la corrutina del endpoint y el resultado
   era un `RuntimeWarning: coroutine was never awaited` con el chunk fallando
   siempre. Lo detectaron los tests antes de cualquier corrida real. Se importa
   como `validate_assembled_jmx`.

2. **`get_dependencies_for_chunk` devuelve 3 claves, no 2.** El prompt pedía
   `{produces, consumes}`; se agregó `internal` (ambos extremos en el mismo
   chunk) porque el prompt del modelo lo trata distinto: ahí el extractor y su
   uso están a la vista en el mismo bloque. `internal` ⊆ `produces`.

3. **Tests de endpoint sin infraestructura HTTP**, igual criterio que la
   Fundación 1: se invocan las funciones directamente con un doble de sesión de
   DB. El repo sigue sin `conftest.py` ni `TestClient`.

4. **`_plan_copy()` en cada persistencia.** SQLAlchemy marca una columna JSONB
   como sucia solo si se le **asigna** un objeto nuevo; mutar la lista en su
   lugar no persistiría el plan. Cada escritura asigna una copia.

5. **El doble de IA responde según el prompt, no según el número de llamada.**
   Detalle de test, pero relevante: así el doble también verifica que el
   orquestador elija el prompt correcto (esqueleto vs bloque).

6. **Dos mejoras no pedidas, ambas nacidas de la corrida real** (sección 9):
   el `failure_reason` enriquecido con `finish_reason=length`, y el escapado de
   `&` sin escapar. Sin la segunda, la validación en vivo se habría quedado en
   `partial` por una causa que no era del diseño sino de una comilla XML.

---

## 9. Validación en vivo

Diseño Pideky `97ccb36f-…`, 105 entries, análisis F1 `completed`, provider
`openai / gpt-4.1` (`max_tokens=32768` por chunk).

### Plan generado (7 chunks)

| Chunk | Contenido | Entries |
|---|---|---:|
| 1 | Esqueleto + `auth` + `navigation` + `config` | 21 |
| 2-6 | Transacciones (`xhr` + `write`) | 15 c/u |
| 7 | Transacciones | 9 |

Suma: 21 + 75 + 9 = **105** — ningún entry perdido, verificado contra la
clasificación.

### Corrida 1 — `generate-chunked`, 412s → `partial` 3/7

| Chunk | Resultado |
|---|---|
| 1 | ✅ 21 samplers, JMX completo y válido |
| 2 | ✅ +15 (30 elementos insertados) |
| 3 | ✅ +15 |
| 4 | ❌ `mismatched tag: line 259, column 50` |
| 5-7 | ⏸ pending — cortó al primer fallo, por diseño |

Log de la llamada del chunk 4: **`finish_reason=length`**. El modelo agotó sus
32K tokens de salida y cortó el XML a mitad. Esos 15 entries son requests a S3
con URLs y bodies largos.

**El JMX no se corrompió**: quedó en 51 samplers, `validate_jmx → (True, 'ok')`,
raíz `jmeterTestPlan`, prefijos `[C2]`/`[C3]` correctos. El invariante central
se cumplió con datos reales, no solo en tests.

### Mejora 1 — la causa real deja de esconderse

`failure_reason` decía `"mismatched tag: line 259, column 50"`: cierto pero
inútil. Ahora, cuando el proveedor reporta `finish_reason=length`, el motivo lo
dice y avisa que reintentar tal cual no va a servir. El `finish_reason` viaja
adjunto al callback (`_call.last_finish_reason`) sin cambiar su contrato
`messages -> str`. 2 tests nuevos.

### Corrida 2 — `retry-failed-chunks`, 301s → `partial` 3/7

`1 failed→pending`, contador recalculado, reanudó desde el 4 sin re-generar los
3 completados… y el chunk 4 **volvió a truncarse**, exactamente como el mensaje
nuevo predecía.

### Corrida 3 — diagnóstico: saltear el 4 para probar 5-7

Se marcó el chunk 4 como `completed` **manualmente vía SQL** para que el flujo
llegara a los bloques siguientes. Resultado: chunk 5 falló, pero con **otro**
error — `not well-formed (invalid token): line 51, column 64`, y **sin**
`finish_reason=length`. O sea: el modelo terminó bien y aun así emitió XML
inválido.

### Mejora 2 — `&` sin escapar

Hipótesis: un `&` crudo dentro de una URL con query string (`?page=1&size=20`),
que en XML debe ser `&amp;`. Se agregó `escape_bare_ampersands()`, que escapa
solo los `&` que no abren una entidad válida (`&amp;`, `&#38;`, `&#x26;`
quedan intactos). No repara nada más: un fragmento realmente roto sigue
fallando, y hay un test que lo verifica.

### Corrida 4 — `retry-failed-chunks`, 209s → **`completed` 7/7**

Hipótesis confirmada empíricamente: el chunk 5 se ensambló sin tocar nada más.
Luego 6 y 7 pasaron limpio.

```json
{"generation_status":"completed","total_chunks":7,"chunks_completed":7,
 "samplers_total":90,"error":null}
```

### JMX final

| Métrica | Valor |
|---|---|
| `validate_jmx` | `(True, 'ok')` |
| Raíz | `jmeterTestPlan` |
| Tamaño | 205.388 bytes |
| `HTTPSamplerProxy` | **90** |
| Distribución | 21 sin prefijo (esqueleto) + `[C2]`15 + `[C3]`15 + `[C5]`15 + `[C6]`15 + `[C7]`9 |
| `JSONPostProcessor` | 18 |
| `HeaderManager` | 203 |
| `ResponseAssertion` | 270 |

90 = 105 − 15, exactamente los entries del chunk 4 que nunca se generó. La
distribución por prefijo coincide con el plan bloque a bloque.

### Estado final de la BD — honesto

El chunk 4 **nunca se generó**. Tras el diagnóstico se restauró su estado real:

```
 chunk |  estado   | entries | motivo
-------+-----------+---------+---------------------------------------
 1     | completed |      21 | -
 2     | completed |      15 | -
 3     | completed |      15 | -
 4     | failed    |      15 | ...finish_reason=length...
 5     | completed |      15 | -
 6     | completed |      15 | -
 7     | completed |       9 | -

 generation_mode | chunks_completed_count | generation_status | jmx_len
 chunked         |                      6 | partial           |  205387
```

### Qué queda demostrado

1. El pipeline completo funciona con datos reales: esqueleto → ensamblado
   incremental → prefijos → extractores → persistencia por bloque → corte al
   fallo → retry reanudable.
2. **El JMX previo nunca se corrompió**, en los 3 fallos reales.
3. `_CHUNK_SIZE = 15` no es universal: sirve para bloques normales y se queda
   corto con requests pesados. Es un número fijo contra un problema variable.

---

## 10. Pendientes / no incluido

- **Sin UI.** Los dos endpoints se invocan con curl. El botón de "reintentar
  bloques fallidos" es de un sprint futuro, como se acordó.
- **`generation_*` y `chunks_plan` no se exponen en `AIScriptDesignDetail`.**
  El schema Pydantic quedó intacto (diff mínimo); se agregan cuando la UI los
  necesite.
- **Ejecución síncrona.** Un HAR de 7 bloques mantiene la request HTTP abierta
  durante toda la generación. Para HARs muy grandes convendría una tarea en
  background con polling de estado — el `chunks_plan` persistido ya soporta
  ese modelo, es solo cambiar quién dispara `process_pending_chunks`.
- **`generate-chunked` sobrescribe `current_jmx`** cuando el chunk esqueleto
  sale bien. Es el comportamiento buscado (se está regenerando el plan), pero
  conviene que la UI lo advierta antes de disparar.
- **Auto-split en truncación.** Es la recomendación concreta que sale de la
  validación: cuando un chunk falla con `finish_reason=length`, partirlo en dos
  y reintentar automáticamente en vez de cortar. El `chunks_plan` persistido ya
  soporta ese modelo — es insertar dos chunks donde había uno. No se implementó
  porque cambia el contrato de "cortar al primer fallo" que definió Fredy.
- **Rebuild de contenedores:** no ejecutado (regla #7). El backend corre con
  `--reload` y tomó los cambios solo.
