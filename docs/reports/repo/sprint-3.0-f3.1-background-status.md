# Sprint 3.0 — F3.1: ejecución en background + estado pollable del chunking

**Fecha:** 2026-08-11
**Branch:** `backup-trabajo-local`
**Base:** `49d9100` (descendiente de `9b675e0`, F2.1)
**Tests:** 380 → **411** (todos PASS)

---

## 1. Problema

`POST /generate-chunked` y `POST /retry-failed-chunks` eran **síncronos**: la
request HTTP quedaba abierta durante toda la generación. Medido sobre el HAR de
Pideky (105 entries), eso son **327-412 s**. Ningún browser, proxy reverso ni
balanceador mantiene una request abierta ese tiempo, así que la Fundación 2 era
funcionalmente inalcanzable desde la UI aunque el backend hiciera el trabajo
bien.

El `chunks_plan` persistido que dejó F2 ya soportaba el modelo correcto
(background + polling); faltaba el ciclo de vida.

---

## 2. Cambios

### 2.1 La lógica de negocio no cambió

`process_pending_chunks` sigue siendo la única implementación de la generación
por bloques. La tarea de fondo la reusa **tal cual**. Lo que se agregó alrededor
es exclusivamente ciclo de vida: lanzamiento, guard, estado terminal, polling.

### 2.2 Mecanismo de background elegido: `asyncio.create_task`

Se descartó `BackgroundTasks` de FastAPI por dos razones concretas de este repo:

1. **Ya existe el precedente en el mismo módulo.** `POST /designs/{id}/execute`
   usa `asyncio.create_task` + `_run_full_execution_background` para exactamente
   el mismo problema (trabajo largo, respuesta inmediata, progreso por polling).
   Una segunda mecánica para el mismo caso sería deuda gratuita.
2. **`BackgroundTasks` corre dentro del ciclo de vida de la request.** Se ejecuta
   después de emitir la respuesta pero antes de cerrar las dependencias, con lo
   que la sesión del `Depends(get_db)` seguiría viva y atada a un trabajo de
   400 s. La task suelta corta ese vínculo por completo.

La tarea **abre su propia sesión** (`AsyncSessionLocal`) y **recarga el diseño
por id**: el objeto ORM de la request queda desligado en cuanto el endpoint
responde.

`asyncio` mantiene solo una referencia **débil** a las tasks. Sin protección, una
generación de 400 s puede ser recolectada a mitad de camino y desaparecer. Por
eso las tasks se guardan en un `set` de módulo (`_CHUNK_TASKS`) con
`add_done_callback` para limpiarlas.

### 2.3 Desbloqueo del event loop — **adaptación obligatoria**

`_call_ai` es **síncrono**. Invocado sin ceder el hilo desde una corrutina,
bloquea el event loop entero. Con el endpoint síncrono eso ya pasaba pero era
invisible (la request estaba bloqueada de todos modos). En modo background es
letal: el backend no atendería **nada** durante los ~400 s — incluido el polling
de `/generation-status`, que es justo lo que la feature necesita.

Única línea de `process_pending_chunks` que se tocó:

```python
raw = await asyncio.to_thread(call_ai, messages)   # antes: raw = call_ai(messages)
```

El contrato del callback no cambia (sigue siendo un sync `messages -> str`), así
que los dobles de los tests funcionan igual y `last_finish_reason` se lee después
del `await`.

**Verificado en vivo:** durante una corrida real de **38 min 53 s**,
`/generation-status` respondió en **40-90 ms** en cada uno de los **52 polls**,
sin una sola espera. El event loop nunca se bloqueó.

### 2.4 Guard anti-concurrencia

`generation_status = 'in_progress'` es el **único estado no terminal**. Un
segundo `generate-chunked` o `retry-failed-chunks` sobre el mismo diseño
devuelve **200** con `generation_status='in_progress'` y el avance actual — no
409. Es el contrato de negocio que F2 ya fijó (`mode='single'`,
`generation_status='partial'` viajan en el cuerpo; solo acceso y configuración
usan códigos HTTP). Un 409 obligaría a la UI a tener dos caminos de lectura para
la misma información.

El guard corre **antes que cualquier otra validación**: con una corrida en curso,
el plan que leeríamos lo está mutando la tarea de fondo en ese mismo instante.

### 2.5 Estado terminal garantizado — sin tareas zombie

`_run_chunked_generation_background` va envuelta en `try/except/finally`. El
`finally` llama a `_ensure_terminal_generation_status`, que:

- abre **una sesión nueva** (si la tarea murió por excepción, la sesión que traía
  puede estar en una transacción abortada y ningún commit de rescate prendería);
- **no pisa un estado ya terminal** — en el camino feliz sale de inmediato;
- si encuentra `in_progress`, escribe el motivo en el primer bloque no terminado
  (el que estaba corriendo) y deja:
  - **`partial`** si hay al menos un bloque completado → recuperable con
    `/retry-failed-chunks`;
  - **`failed`** si no hay ninguno → no hay parcial que reanudar.

### 2.6 Timestamp de inicio

`chunks_plan` es un **array** JSON, no un objeto: no hay dónde colgar un bloque
de metadatos sin cambiarle la forma y romper a todos los consumidores de F2
(`_generable_chunks`, `_chunk_summaries`, el ciclo de `process_pending_chunks`) y
a las filas ya persistidas. El sello va como **una clave más de cada chunk**
(`run_started_at`, ISO-8601 UTC), repetida: cuesta ~30 bytes por bloque y evita
una migración. Se pisa en cada lanzamiento — es diagnóstico, no historial.

Los hijos de un auto-split nacen sin el sello; `_run_started_at(plan)` devuelve
el primero no nulo.

### 2.7 Cobertura de response bodies del HAR (hallazgo F1)

Nueva función `response_body_coverage(entries)` en `har_flow_analyzer.py` — puro
parseo estructural, **cero llamadas al modelo**. Cuenta cuántos entries traen
`response.content.text` no vacío.

- **Persistencia:** `analyze_har_flow` la escribe como clave nueva
  `response_body_coverage` **dentro** de `har_analysis_classification`. Va ahí y
  no en una columna propia porque es un atributo del mismo HAR que describe el
  resto del blob, y así queda invalidada por el mismo `source_sha1` sin lógica
  extra.
- **Fallback on-demand:** para diseños analizados **antes** de F3.1 (que no
  tienen la clave), `/generation-status` la recalcula leyendo el HAR persistido.
  **No re-corre la IA y no escribe nada.** Si el diseño no tiene HAR o el HAR es
  ilegible devuelve `null` sin romper el polling.

### 2.8 `AIScriptDesignDetail`

Se agregaron **solo** `generation_mode` y `generation_status` — lo mínimo para
que la página decida si muestra el panel. El plan completo NO viaja acá: meterlo
obligaría a recargar la conversación y el JMX entero en cada tick del polling.

---

## 3. Contrato de `GET /designs/{design_id}/generation-status`

> Esta sección es la referencia para F3.2. Todo lo que la UI necesita está acá.

**Auth:** cookie `access_token`, roles `admin | analyst`. Es un GET: **no
requiere `X-CSRF-Token`**.

**Códigos:** `404` diseño inexistente · `403` diseño ajeno y no-admin · `200` en
todo lo demás. Un diseño que **nunca** pasó por `/generate-chunked` **no es un
error**: responde 200 con los campos en `null` y `total_chunks: 0` — que es
exactamente lo que la UI necesita para decidir que no muestra el panel.

**Costo:** sin JMX, sin `entry_idxs`, sin conversación. Medido en vivo: **40-90
ms**. Apto para poll cada 3-5 s mientras `generation_status === 'in_progress'`.

### Payload

```jsonc
{
  "design_id": "97ccb36f-511f-4d48-8331-c7d4d7bc8335",

  // single | chunked | null (nunca generado)
  "generation_mode": "chunked",

  // null | in_progress | completed | partial | failed
  "generation_status": "in_progress",

  // Bloques con status 'completed'. Se cuenta desde el plan, nunca de la columna.
  "chunks_completed_count": 3,

  // Bloques GENERABLES. Semantica F2.1: los 'split' NO cuentan (sus entries ya
  // viven en los hijos). Por eso `chunks_completed_count === total_chunks`
  // significa terminado, y `chunks.length` puede ser MAYOR que `total_chunks`.
  "total_chunks": 7,

  // HTTPSamplerProxy acumulados en el JMX. Ojo: al generarse el esqueleto el
  // JMX se REEMPLAZA, asi que este numero puede BAJAR al inicio de una
  // regeneracion (105 -> 21 -> 36 -> ...). No asumir monotonia.
  "samplers_total": 51,

  // ISO-8601 UTC del ultimo lanzamiento. null en planes previos a F3.1.
  "generation_started_at": "2026-08-11T17:28:03.917534Z",

  "chunks": [
    {
      "chunk_id": 1,
      "name": "Chunk 1 - Esqueleto + autenticacion",
      "status": "completed",          // pending | completed | failed | split
      "n_entries": 21,                // conteo; los entry_idxs NO viajan
      "is_skeleton": true,            // el bloque que crea el jmeterTestPlan
      "split_depth": 0,               // 0 = original; 1-2 = hijo de auto-split
      "parent_chunk_id": null,        // != null => es hijo de un split
      "failure_reason": null          // truncado a 400 chars
    }
  ],

  // null si el diseno no tiene HAR o el HAR es ilegible. NO es un error.
  "har_body_coverage": {
    "entries_with_response_body": 56,
    "total_entries": 105,
    "ratio": 0.5333                   // 0.0 - 1.0; 0.0 si total_entries == 0
  }
}
```

### Notas para F3.2

1. **Cuándo mostrar el panel.** `generation_mode === 'chunked'`. Con `'single'` o
   `null` el diseño usa el flujo clásico de una sola llamada.
2. **Cuándo pollear.** Solo mientras `generation_status === 'in_progress'`. Los
   otros cuatro estados son terminales — al llegar a uno, cortar el intervalo.
3. **Barra de progreso.** `chunks_completed_count / total_chunks`. No usar
   `chunks.length` como denominador: incluye los padres `split`.
4. **Linaje del auto-split.** Un bloque con `status: 'split'` es solo rastro
   histórico: se partió porque el modelo truncó, y sus entries están en los dos
   hijos que le siguen en el array (`parent_chunk_id` apunta a él). Renderizarlo
   indentado o colapsado, nunca como un bloque pendiente.
5. **`samplers_total` puede bajar.** Ver el comentario en el payload. Si la UI
   muestra ese número, no presentarlo como progreso monótono.
6. **Aviso "HAR sin bodies".** Si `har_body_coverage.ratio` es bajo, la Fase 2
   del análisis tuvo poco de dónde inferir correlaciones y el JMX va a traer
   pocos extractores. `null` significa "no se pudo calcular" — no mostrar aviso,
   no mostrar 0%.
7. **Botón de reintento.** Habilitarlo solo con `generation_status === 'partial'`
   (o `'failed'`). Con `'in_progress'` el POST devuelve 200 sin lanzar nada.
8. **Rechazo por concurrencia.** Un `generate-chunked` / `retry-failed-chunks`
   sobre un diseño en curso devuelve **200** (no 409) con
   `generation_status: 'in_progress'` y un `reason` explicativo. La UI debe
   detectar el estado, no el código HTTP.

### Contrato de los POST (cambió)

`POST /generate-chunked` y `POST /retry-failed-chunks` devuelven ahora **de
inmediato** (medido: **39 ms**) con `generation_status: 'in_progress'`,
`chunks_completed` con el avance previo y el plan recién armado en `chunks`. El
`ChunkedGenerationResponse` no cambió de forma; cambió *cuándo* llega.

Se mantienen tal cual: `404`/`403` de acceso, `400` de precondición (sin análisis
de HAR / sin generación por chunks), `429`/`503` de configuración de IA, y el
`200 mode='single'` cuando el HAR no llega al umbral.

El **pre-vuelo de la configuración de IA** (`_build_chunk_call_ai`) se sigue
haciendo en la request, con su sesión: así un 429/503 le llega al usuario como
código HTTP en vez de morir sin testigos dentro de la tarea de fondo.

---

## 4. Limitación conocida: `--reload` mata la tarea

En desarrollo uvicorn corre con `--reload`. **Un reload durante una generación
mata la tarea de fondo en curso.** El diseño queda con
`generation_status='in_progress'` sin nadie procesándolo, porque el `finally`
tampoco llega a ejecutarse: el proceso muere.

- **Impacto:** solo dev. `docker-compose.prod.yml` corre `--workers 2` **sin
  `--reload`**.
- **Recuperación:** el estado colgado no es irreversible pero el guard
  anti-concurrencia lo va a rechazar. Se destraba con un UPDATE manual:
  ```sql
  UPDATE ai_script_designs SET generation_status='partial'
  WHERE id='<uuid>' AND generation_status='in_progress';
  ```
  y después `/retry-failed-chunks`, que reanuda desde el primer pendiente sin
  re-generar ni re-cobrar los bloques ya completados.
- **Nota de multi-worker:** con `--workers 2` la task vive en el worker que
  atendió el POST. El polling puede caer en el otro worker — no es problema,
  porque **todo el estado está en la base**, no en memoria del proceso.

---

## 5. Archivos tocados

| Archivo | Cambio |
|---|---|
| `backend/app/api/v1/endpoints/script_ai.py` | background runner, guard, estado terminal, `/generation-status`, `to_thread` |
| `backend/app/services/ai/har_chunk_router.py` | `GENERATION_IN_PROGRESS` |
| `backend/app/services/ai/har_flow_analyzer.py` | `response_body_coverage()` + persistencia en la clasificación |
| `backend/app/schemas/ai_script_design.py` | `generation_mode` + `generation_status` en `AIScriptDesignDetail` |
| `backend/tests/test_chunked_generation_endpoint.py` | 8 tests adaptados al contrato de background |
| `backend/tests/test_f31_background_generation.py` | **nuevo** — 31 tests |

Backups: `*.bak_f31_20260811_121858`.

**No se tocó:** `/generate`, `/generate-from-file`, `/refine`, ni ningún archivo
protegido. **Sin cambios de schema en DB** — ni columnas nuevas ni ALTER TABLE.

---

## 6. Tests

**380 → 411** (`docker exec jmeter_backend python -m pytest tests/ -q`).

Los 31 nuevos cubren:

- **POST inmediato** (3): no llama a la IA antes de responder, sella el
  timestamp, el plan queda persistido antes del lanzamiento.
- **Guard anti-concurrencia** (4): rechaza el segundo `generate` y el segundo
  `retry`, no pisa el plan en curso, corre antes que la validación de análisis.
- **Estado terminal** (6): excepción sin bloques → `failed`; con bloques →
  `partial`; el motivo queda escrito en el bloque en curso; el camino feliz no
  es degradado por la red de seguridad; diseño borrado a mitad no rompe nada; la
  tarea abre su propia sesión (2 aperturas: trabajo + rescate).
- **`/generation-status`** (7): plan completo, linaje de split, diseño nunca
  generado, truncado de motivos largos, ausencia de JMX/`entry_idxs`, timestamp,
  404/403.
- **Cobertura de bodies** (8): conteo, bodies vacíos/ausentes, lectura
  persistida, fallback on-demand sin escribir, `null` sin HAR, HAR ilegible que
  no tumba el polling, división por cero, persistencia en `analyze_har_flow`.
- **`AIScriptDesignDetail`** (3): expone los dos campos, `null` en diseños
  clásicos, sigue sin exponer el plan.

Los 8 tests adaptados en `test_chunked_generation_endpoint.py` no perdieron
cobertura: ahora hacen POST → asertan la respuesta inmediata → corren
`_run_chunked_generation_background` con una fábrica de sesión falsa → asertan
el resultado final. Es la **misma función** que corre en producción, no una copia
de test.

---

## 7. Validación en vivo

Ver `docs/reporte-para-fredy-f3.1.md`, sección "Corrida en vivo".
