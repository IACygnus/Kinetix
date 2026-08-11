# Reporte para Fredy — Sprint 3.0 F3.1

**Ejecución en background + estado pollable del chunking**
**Fecha:** 2026-08-11 · **Branch:** `backup-trabajo-local`

---

## 1. Estado

**Listo para tu validación visual.** Backend completo, tests verdes y corrida
real end-to-end sobre Pideky terminada en `completed` con los 105 samplers.

El problema que resolvimos: `generate-chunked` mantenía la request HTTP abierta
durante toda la generación (medido: 327-412 s en F2, y **38 min** en la corrida
de hoy). Ningún browser aguanta eso. Ahora el POST vuelve en **39 ms** y el
avance se sigue con un endpoint nuevo de polling.

---

## 2. Qué cambió

| # | Cambio |
|---|---|
| 1 | `generate-chunked` y `retry-failed-chunks` responden **inmediato**; el trabajo pasa a una tarea de fondo que abre su propia sesión de DB. |
| 2 | **Guard anti-concurrencia**: un segundo disparo sobre un diseño en curso se rechaza con 200 + `in_progress` (no lanza una segunda tanda de llamadas al modelo). |
| 3 | **Estado terminal garantizado**: `try/except/finally` que nunca deja un diseño colgado en `in_progress`. Con bloques hechos → `partial`; sin ninguno → `failed`. |
| 4 | **`GET /designs/{id}/generation-status`** — endpoint liviano de polling (40-90 ms) con el plan, el linaje del auto-split y la cobertura de bodies. |
| 5 | **Cobertura de response bodies del HAR** calculada en `analyze-har` y persistida en el JSONB; para diseños viejos se recalcula on-demand sin re-correr IA. |
| 6 | `AIScriptDesignDetail` expone `generation_mode` y `generation_status` (solo eso). |

**La lógica de negocio de la generación no se tocó.** La tarea de fondo reusa
`process_pending_chunks` tal cual. Lo que se agregó es ciclo de vida.

**Sin cambios de base de datos.** Ni columnas nuevas ni ALTER TABLE.

---

## 3. Tests

| | Cantidad |
|---|---|
| Baseline (antes) | **380** PASS |
| Después | **411** PASS |
| Netos nuevos | **+31** |

Cifra real, contada con `docker exec jmeter_backend python -m pytest tests/ -q`.

Los 31 nuevos están en `backend/tests/test_f31_background_generation.py` y
cubren: respuesta inmediata, guard anti-concurrencia (4), estado terminal
garantizado ante excepción (6), el endpoint de polling (7), cobertura de bodies
(8) y el schema Detail (3).

Además adapté 8 tests existentes de `test_chunked_generation_endpoint.py` que
asertaban generación síncrona desde el endpoint. **No perdieron cobertura**:
ahora hacen POST → asertan la respuesta inmediata → corren la tarea de fondo con
una fábrica de sesión falsa → asertan el resultado final. Es la misma función que
corre en producción, no una copia de test.

---

## 4. Corrida en vivo — diseño Pideky `97ccb36f-…`

Generación real, con llamadas reales al modelo (gpt-4.1). El JMX se regeneró
desde cero, como acordamos.

### (a) Respuesta inmediata del POST

```
POST /designs/97ccb36f-…/generate-chunked
HTTP 200   tiempo_total = 0.039 s          <-- 39 ms

mode=chunked  status=in_progress  bloques=0/7  samplers=105
reason= El HAR tiene 100 entries funcionales (umbral: mas de 30); se genera por
        bloques. Generacion lanzada en segundo plano; segui el avance en
        GET /designs/{id}/generation-status.
```

Antes esta misma request tardaba **327-412 s**. Ahora vuelve en **39 ms**.

### (b) Polling real durante la corrida

52 consultas a `/generation-status`, **todas entre 40 y 90 ms**, mientras la IA
generaba. Transiciones observadas:

```
[12:28:03]  POST -> in_progress            0/7   samplers=105
[12:34:27]  status=in_progress   bloques=1/7   samplers=21
[12:37:59]  status=in_progress   bloques=2/7   samplers=36
[12:40:37]  status=in_progress   bloques=3/7   samplers=51
[12:59:13]  status=in_progress   bloques=3/8   samplers=51   <- AUTO-SPLIT: total 7->8, aparece 1 'split'
[13:00:15]  status=in_progress   bloques=4/8   samplers=58
[13:01:16]  status=in_progress   bloques=5/8   samplers=66
[13:03:20]  status=in_progress   bloques=6/8   samplers=81
[13:05:23]  status=in_progress   bloques=7/8   samplers=96
[13:06:56]  status=completed     bloques=8/8   samplers=105
```

Dos cosas que se ven acá y valen la pena:

- **El contador avanza de verdad** — no es un estado falso. Y `samplers` baja de
  105 a 21 en el primer bloque porque el esqueleto **reemplaza** el JMX viejo;
  de ahí en adelante sube. Se lo dejé documentado a F3.2 para que no lo muestre
  como una barra monótona.
- **El auto-split de F2.1 volvió a dispararse solo**, y esta vez *se vio en
  vivo*: a las 12:59 el total pasó de 7 a 8 bloques y apareció un `split`. El
  chunk 4 quemó sus 32 768 tokens y cortó el XML a mitad; el sistema lo partió
  en dos mitades (C8 de 7 requests y C9 de 8) y siguió sin intervención.

### (c) Estado final

```
generation_mode   = chunked
generation_status = completed
bloques           = 8/8
samplers_total    = 105
started_at        = 2026-08-11T17:28:03.917534Z
har_body_coverage = {'entries_with_response_body': 56, 'total_entries': 105, 'ratio': 0.5333}

  C1  Chunk 1 - Esqueleto + autenticacion     completed  n=21
  C2  Chunk 2 - Transacciones 1/6             completed  n=15
  C3  Chunk 3 - Transacciones 2/6             completed  n=15
  C4  Chunk 4 - Transacciones 3/6             split      n=15   <- truncó, se partió
  C8    Chunk 8 - mitad 1/2 de C4             completed  n=7    depth=1 parent=4
  C9    Chunk 9 - mitad 2/2 de C4             completed  n=8    depth=1 parent=4
  C5  Chunk 5 - Transacciones 4/6             completed  n=15
  C6  Chunk 6 - Transacciones 5/6             completed  n=15
  C7  Chunk 7 - Transacciones 6/6             completed  n=9
```

Log de cierre de la propia tarea de fondo:

```
chunked gen bg: diseno 97ccb36f-… termino con status=completed (8/8 bloques, 105 samplers)
```

**Duración total: 38 min 53 s** (12:28:03 → 13:06:56).

### (d) Verificación del JMX

```
bytes                          : 239 110
XML BIEN FORMADO               : OK   (root=jmeterTestPlan version=1.2 jmeter=5.6.3)
grep -c HTTPSamplerProxy       : 105
HTTPSamplerProxy (ElementTree) : 105
ThreadGroup                    : 1
ResponseAssertion              : 105
HeaderManager                  : 40
CookieManager                  : 1
JSONPostProcessor (extractores): 2
```

105 samplers, XML válido, parseable por ElementTree.

---

## 5. Cobertura de bodies — el dato que pediste para el aviso de F3.2

`/generation-status` ahora devuelve cuántos requests del HAR traen el body de la
respuesta. Verificado contra los dos diseños reales:

| Diseño | Cobertura | Fuente |
|---|---|---|
| Veritran `f89920fe-…` | **36 / 106** (33,9 %) | calculada on-demand |
| Pideky `97ccb36f-…` | **56 / 105** (53,3 %) | calculada on-demand |

El 36/106 de Veritran **coincide exacto** con el número que la Fundación 1 midió
a mano — o sea, el cálculo automático reproduce el hallazgo sin re-correr IA.

Y se ve la consecuencia en el JMX de hoy: con 53 % de cobertura, la Fase 2
encontró poco que correlacionar y el script salió con **2 extractores para 105
samplers**. Ese es exactamente el aviso que la UI de F3.2 tiene que mostrar antes
de que alguien gaste una generación.

---

## 6. Adaptaciones (todas reportadas, ninguna cambia el objetivo)

1. **`asyncio.to_thread` en `process_pending_chunks` — obligatoria.**
   `_call_ai` es síncrono. Llamado desde una corrutina sin ceder el hilo,
   bloquea el event loop **entero**. Con el endpoint síncrono eso ya pasaba pero
   era invisible; en background hubiera dejado al backend sin atender nada
   durante 38 minutos — incluido el polling, que es justo lo que la feature
   necesita. Es **una línea** y no cambia el contrato del callback. Sin esto la
   feature no funciona; los 52 polls de 40-90 ms de arriba son la prueba de que
   con esto sí.

2. **Mecanismo de background: `asyncio.create_task`, no `BackgroundTasks`.**
   Porque es el patrón que el mismo módulo ya usa en `/designs/{id}/execute`, y
   porque `BackgroundTasks` corre dentro del ciclo de vida de la request (la
   sesión del `Depends(get_db)` quedaría atada a un trabajo de 38 min).

3. **Timestamp de inicio: como clave de cada chunk, no como bloque de metadatos.**
   `chunks_plan` es un *array* JSON. Colgarle un objeto de metadatos le cambia la
   forma y rompe a todos los consumidores de F2 y a las filas ya guardadas. El
   sello va repetido en cada chunk: ~30 bytes por bloque y cero migración.

4. **Pre-vuelo de la config de IA en la request.** El chequeo de API key / límite
   se sigue haciendo con la sesión de la request para que un 429/503 llegue como
   código HTTP, en vez de morir sin testigos dentro de la tarea de fondo.

---

## 7. Limitaciones y pendientes

1. **`--reload` mata la tarea (solo dev).** Si uvicorn recarga durante una
   generación, la tarea muere y el diseño queda en `in_progress` — el `finally`
   tampoco corre porque el proceso muere. En producción no hay `--reload`
   (`docker-compose.prod.yml` usa `--workers 2`). Si te pasa en dev, se destraba
   con:
   ```sql
   UPDATE ai_script_designs SET generation_status='partial'
   WHERE id='<uuid>' AND generation_status='in_progress';
   ```
   y después `/retry-failed-chunks`, que reanuda sin re-generar ni re-cobrar los
   bloques ya hechos.

2. **El cliente OpenAI no fija `timeout` ni `max_retries`** — usa los defaults
   del SDK (600 s por intento, 3 intentos). Por eso el chunk 4 estuvo 18 minutos
   sin dar señales antes de truncar. **No lo toqué** (regla de memoria de costos:
   los timeouts tienen doble uso y hay que verificar antes). Lo dejo señalado
   como candidato a revisar en un prompt propio.

3. **Falta la UI (F3.2).** El contrato completo del endpoint está documentado en
   `docs/reports/repo/sprint-3.0-f3.1-background-status.md` §3, con 8 notas de
   implementación para que F3.2 no tenga que adivinar nada.

4. **No se tocó** `/generate`, `/generate-from-file`, `/refine` ni ningún archivo
   protegido. **No hice rebuild de contenedores** (regla #7) — el backend tomó los
   cambios por el `--reload` que ya estaba activo.

---

## 8. Archivos

**Modificados** (backups `*.bak_f31_20260811_121858`):

- `backend/app/api/v1/endpoints/script_ai.py`
- `backend/app/services/ai/har_chunk_router.py`
- `backend/app/services/ai/har_flow_analyzer.py`
- `backend/app/schemas/ai_script_design.py`
- `backend/tests/test_chunked_generation_endpoint.py`

**Nuevos:**

- `backend/tests/test_f31_background_generation.py`
- `docs/reports/repo/sprint-3.0-f3.1-background-status.md`
- `docs/reporte-para-fredy-f3.1.md`

---

## 9. Commit y push

- **Commit:** `PENDIENTE_COMMIT_HASH`
- **Push:** `github` / `backup-trabajo-local` — **PENDIENTE_PUSH**
- **`origin` (Azure DevOps / producción): NO se tocó.**
