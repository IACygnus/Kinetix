# Sprint 3.0 — F2.1: Auto-split de chunks truncados

**Fecha:** 2026-07-28
**Branch:** `backup-trabajo-local`
**Base:** `ac82acb` (docs F2) sobre `81d2cc7` (Fundación 2)
**Estado:** implementado y testeado. Validación en vivo en la sección 7.

---

## 1. Qué resuelve

La Fundación 2 dejó la generación por chunks funcionando, con un límite
documentado: **el chunk 4 de Pideky falla siempre**. Sus 15 requests (llamadas
a S3 con URLs y bodies largos) no entran en los 32K tokens de salida del
modelo, y `finish_reason=length` corta el XML a mitad.

Reintentar ese bloque tal cual es **matemáticamente inútil**: la entrada no
cambia, el techo tampoco. Dos corridas reales de F2 lo demostraron.

F2.1 cambia una sola cosa: cuando un chunk falla **por truncación**, en vez de
cortar el flujo se **parte en dos y se reintentan las mitades en el mismo
ciclo**.

**El contrato de "cortar al primer fallo" sigue intacto para todo lo demás:**
XML mal formado sin truncación, error de red, límite de cuota. La excepción es
exclusivamente la truncación, que es el único fallo donde partir cambia el
resultado.

---

## 2. Cambios por archivo

| Archivo | Δ | Qué |
|---|---:|---|
| `backend/tests/test_chunked_generation_endpoint.py` | +317 | 14 tests de auto-split en la orquestación. |
| `backend/app/api/v1/endpoints/script_ai.py` | +210 | `_try_auto_split`, bucle indexado, conteos. |
| `backend/tests/test_har_chunk_router.py` | +139 | 17 tests de `split_chunk`. |
| `backend/app/services/ai/har_chunk_router.py` | +130 | `split_chunk`, `can_split_chunk`, `next_free_chunk_id`. |

**Total: 4 archivos, 740 inserciones, 56 borrados** (`git diff --cached --stat`).

**Sin migración de base de datos.** El linaje del split (`split_depth`,
`parent_chunk_id`) vive dentro de `chunks_plan`, que ya es JSONB. No hizo falta
ALTER TABLE.

Sin cambios en frontend. Ningún archivo protegido tocado. `/generate`,
`/generate-from-file` y `/refine` no se tocaron.

---

## 3. Memoria de costos: constantes con doble uso

Antes de tocar nada se verificó el alcance real de las constantes de chunking
(`grep` sobre `app/` y `tests/`):

| Constante | Dónde vive | Doble uso |
|---|---|---|
| `_CHUNK_SIZE` | `har_chunk_router.py`, solo como default de `group_entries_into_chunks(chunk_size=…)` | **No** |
| `_MIN_FUNCTIONAL_FOR_CHUNKING` | `har_chunk_router.py`, solo en `should_use_chunked_generation` | **No** |
| `_CHUNK_MAX_TOKENS` | `script_ai.py`, solo en `_build_chunk_call_ai` | **No** |

**`_CHUNK_SIZE` no se modificó.** El split es local al chunk que truncó: bajar
el tamaño global habría encarecido *todas* las generaciones para arreglar un
caso puntual. La constante nueva de este sprint es `_MAX_SPLIT_DEPTH = 2`.

---

## 4. `split_chunk` — lógica pura

```python
split_chunk(chunk, next_chunk_id) -> (hijo_a, hijo_b) | None
```

Garantías, todas cubiertas por tests:

- **Orden del HAR preservado.** `hijo_a` lleva la primera mitad, `hijo_b` la
  segunda, ambas ordenadas. La correlación depende de que un token se extraiga
  antes de usarse; reordenar rompería el plan.
- **La unión de los hijos es exactamente el padre**, sin duplicados. Con un
  número impar (15), la primera mitad es la más chica: 7 + 8.
- **IDs nuevos, nunca reciclados** (ver sección 5).
- **`split_depth` incrementa** y **`parent_chunk_id`** apunta al padre.
- **Si el padre era el esqueleto**, `hijo_a` hereda ese rol —sigue teniendo que
  generar el JMX completo— y `hijo_b` pasa a ser un bloque normal que se
  ensambla dentro de lo que generó su hermano.

### Guardas (anti-loop y anti-costo)

`can_split_chunk(chunk) -> (bool, motivo)` devuelve el motivo en texto para
persona, porque termina en el `failure_reason` que lee el usuario.

| Guarda | Condición | Mensaje |
|---|---|---|
| Tamaño mínimo | `len(entry_idxs) < 2` | "un entry individual excede la capacidad de salida del modelo y requiere revisión manual" |
| Profundidad | `split_depth >= 2` | "ya se partió 2 veces (máximo 2) y sigue truncando; requiere revisión manual" |

`_MAX_SPLIT_DEPTH = 2` da la cadena 15 → ~8 → ~4. Más profundidad no arregla el
problema de fondo (un request individual demasiado pesado) y multiplica el
costo en llamadas.

**Cuál guarda se dispara primero depende del tamaño del bloque**: con bloques
chicos se llega antes al mínimo de 2 entries que al tope de profundidad. Hay un
test para cada camino.

---

## 5. Identidad de chunks — restricción dura

Los prefijos `[Cn]` ya están escritos en los `testname` del JMX persistido de
los chunks completados. **Renumerar rompería esa trazabilidad en silencio**, y
el JMX no se puede "des-prefijar" sin reescribirlo.

Por eso:

- Los hijos reciben `chunk_id` **nuevos**: `next_free_chunk_id(plan)` =
  `max(chunk_id) + 1`. Nunca se recicla el ID del padre ni se corren los demás.
- El padre **queda en el plan** con `status='split'` como rastro de linaje. No
  se genera, no se cuenta, y su `failure_reason` documenta en qué bloques se
  partió.
- Los hijos se insertan **justo después del padre** en el plan, no al final:
  así el orden del HAR —y por lo tanto el orden de los samplers en el JMX— no
  se altera.

**Consecuencia: `chunk_id` deja de coincidir con la posición en el plan.** El
ID es identidad; la posición es orden. Son cosas distintas y ahora se ve.

### Conteos coherentes

| Métrica | Fórmula |
|---|---|
| `chunks_completed` / `chunks_completed_count` | `count(status == 'completed')` |
| `total_chunks` | `count(status != 'split')` — los padres partidos no son bloques generables |
| `pending` (retry) | `count(status not in ('completed', 'split'))` |

Sin excluir los `split` del total, una generación completa se vería como
`partial` para siempre; y sin excluirlos de `pending`, el retry entraría en un
ciclo sin trabajo que hacer.

La lista `chunks` de la respuesta **sí** incluye a los padres partidos: el
linaje queda visible aunque no cuente.

---

## 6. Integración en `process_pending_chunks`

### Bucle indexado

El `for chunk in plan` se reemplazó por un `while` con índice explícito. Un
split inserta los hijos **dentro** de la lista mientras se la recorre, y
iterar una lista que crece por el medio con un `for` es una fuente clásica de
saltos silenciosos.

Tras un split, el bucle **no incrementa el índice**: la guarda de arriba salta
al padre (ahora `split`) y aterriza en el primer hijo. Las mitades se procesan
en el mismo ciclo, en orden.

### Detección de truncación

`_is_truncation_failure(reason, call_ai)` mira dos fuentes:

1. `call_ai.last_finish_reason == "length"` — la señal directa del proveedor.
2. `"finish_reason=length" in reason` — el marcador que `_enrich_failure_reason`
   ya escribía en F2, útil cuando el motivo viaja desde un plan persistido.

### Bug corregido: `last_finish_reason` colgado

En F2 el callback seteaba `last_finish_reason` **después** de llamar al
proveedor. Si `_call_ai` levantaba una excepción, quedaba el valor de la
llamada anterior — y un error de red posterior a una truncación se habría
diagnosticado como truncación, disparando un split inútil.

Ahora se limpia **antes** de llamar. Hay un test
(`test_error_de_red_no_se_confunde_con_truncacion`).

### Corrección en `variables_available_from`

El corte era por `chunk_id`; tras un split los hijos tienen IDs altos pero van
**antes** en el plan, así que comparar IDs escondía variables ya extraídas a
los bloques posteriores. Ahora el corte es **por posición en el plan**.

---

## 7. Validación en vivo

Diseño Pideky `97ccb36f-…`, provider `openai / gpt-4.1`.
**Estado de partida (dejado por F2):** `partial`, 6/7 bloques, **90 samplers**,
chunk 4 `failed` por `finish_reason=length` tras dos reintentos inútiles.

### Corrida: `POST /retry-failed-chunks` — 327s

Secuencia real, de los logs:

```
retry chunks: diseno 97ccb36f-… — 1 failed->pending, 1 pendientes en total
chunked gen: chunk 4 trunco -> auto-split en C8 (7) + C9 (8), nivel 1
jmx assembler: chunk 8 insertado — 14 elementos, 7 samplers nuevos
chunked gen: chunk 8 OK (7/8 bloques) — 97 samplers acumulados
jmx assembler: chunk 9 insertado — 16 elementos, 8 samplers nuevos
chunked gen: chunk 9 OK (8/8 bloques) — 105 samplers acumulados
```

El chunk 4 volvió a truncar —como estaba previsto— pero esta vez **no cortó el
flujo**: se partió en dos y las mitades se generaron en el mismo ciclo.

### Respuesta

```json
{"generation_status":"completed","total_chunks":8,"chunks_completed":8,
 "samplers_total":105,"error":null}
```

### Plan final con linaje

```
 chunk |  estado   | entries | nivel | padre
-------+-----------+---------+-------+-------
 1     | completed |      21 | 0     | -
 2     | completed |      15 | 0     | -
 3     | completed |      15 | 0     | -
 4     | split     |      15 | 0     | -     <- padre partido, no se cuenta
 8     | completed |       7 | 1     | 4     <- hijo, insertado tras el padre
 9     | completed |       8 | 1     | 4     <- hijo
 5     | completed |      15 | 0     | -     <- ID original intacto
 6     | completed |      15 | 0     | -
 7     | completed |       9 | 0     | -

 generation_mode | chunks_completed_count | generation_status | jmx_len
 chunked         |                      8 | completed         |  233489
```

Se ve todo lo que exigía el contrato:

- Los hijos **C8 y C9** tienen IDs nuevos (por encima del máximo original, 7).
- **C5, C6 y C7 conservan sus IDs**: nada se renumeró.
- Los hijos están **justo después del padre**, así que el orden del HAR se
  mantiene y los samplers salen en secuencia.
- `7 + 8 = 15`: la unión de los hijos es exactamente el padre.
- `chunks_completed_count = 8` sobre 8 bloques generables — el padre `split`
  no infla el total ni bloquea el `completed`.

El `failure_reason` del padre quedó como documentación del episodio:

> *"…el modelo agoto su limite de tokens de salida y corto el XML a mitad
> (finish_reason=length). … Se partio automaticamente en los bloques C8 (7
> requests) y C9 (8 requests)."*

### JMX final

| Métrica | Antes (F2) | Después (F2.1) |
|---|---:|---:|
| `validate_jmx` | `(True, 'ok')` | **`(True, 'ok')`** |
| Tamaño | 205.387 bytes | **233.489 bytes** |
| `HTTPSamplerProxy` | 90 | **105** |
| Cobertura del HAR | 90/105 | **105/105** |

Distribución por bloque: 21 sin prefijo (esqueleto) + `[C2]`15 + `[C3]`15 +
`[C5]`15 + `[C6]`15 + `[C7]`9 + `[C8]`7 + `[C9]`8 = **105**.
18 `JSONPostProcessor` (extractores) conservados.

**Los 15 samplers que faltaban se recuperaron sin intervención manual**, que
era exactamente el objetivo del mini-sprint. No hizo falta el segundo nivel de
split: las mitades de 7 y 8 requests entraron holgadas.

---

## 7.b Tests

Contados con `pytest`, no estimados:

| Momento | Resultado |
|---|---|
| Baseline (`ac82acb`) | **349 passed** en 19.03s |
| Después de F2.1 | **380 passed** en 17.41s |
| Delta | **+31** |

- `test_har_chunk_router.py` — **+17**: mitades ordenadas, unión == padre sin
  duplicados, impares (15 → 7+8), IDs nuevos consecutivos, profundidad,
  linaje, esqueleto heredado solo por el primer hijo, `None` con 1 entry y con
  0, tope de profundidad, cadena 15→8→4 sin pérdida, `next_free_chunk_id`,
  variables disponibles con hijos intercalados.
- `test_chunked_generation_endpoint.py` — **+14**: split y mitades en el mismo
  ciclo, inserción justo después del padre, cobertura exacta del padre, IDs sin
  colisión, el padre no cuenta como pendiente ni completado, motivo
  documentado, split en cadena a nivel 2, tope de profundidad, bloque de 1
  entry sin loop, **fallo no-truncación conserva el corte clásico**, error de
  red no confundido con truncación, retry sobre plan con splits, retry que no
  reintenta un padre partido, linaje expuesto en la respuesta.

Ningún test del baseline se rompió; uno se reescribió (ver adaptación 5).

---

## 8. Adaptaciones respecto al prompt

1. **`split_chunk` recibe un segundo parámetro `next_chunk_id`.** El prompt lo
   especificaba como `split_chunk(chunk)`, pero asignar IDs libres exige
   conocer el plan, y meter el plan dentro de la función la ataría al estado.
   El ID libre se calcula con `next_free_chunk_id(plan)` —también pura y
   testeada aparte— y se inyecta. La función sigue siendo pura.

2. **Se agregó `can_split_chunk(chunk) -> (bool, motivo)`.** `split_chunk`
   devuelve `None` en ambos casos no divisibles; sin este helper el
   orquestador no podría distinguir "es de 1 entry" de "ya se partió 2 veces"
   para el mensaje al usuario.

3. **`_try_auto_split` devuelve `(absorbido, motivo)` en vez de solo un bool.**
   La primera versión escribía el `failure_reason` ampliado dentro del helper y
   el caller lo pisaba una línea después. Lo detectaron los tests
   (`test_un_chunk_de_un_entry_que_trunca_no_entra_en_loop`).

4. **`total_chunks` cambió de semántica**: era `len(plan)`, ahora es
   `count(status != 'split')`. Sin eso una generación completa con split se
   reportaría eternamente como incompleta.

5. **Un test de F2 se reescribió**, no se borró:
   `test_fallo_por_truncado_del_modelo_lo_dice_explicito` verificaba que una
   truncación dejara el mensaje explícito en un chunk `failed`. Bajo F2.1 una
   truncación divisible ya no falla —se parte—, así que ahora usa un chunk que
   alcanzó el tope de profundidad. La intención original se conserva; el nuevo
   `test_el_motivo_del_padre_documenta_el_split` cubre el otro camino.

6. **Sin migración SQL.** El prompt no pedía columnas nuevas y no hicieron
   falta: el linaje entra en el JSONB existente.

---

## 9. Pendientes

- **Sin UI.** El auto-split es transparente para quien llama al endpoint, pero
  el plan con linaje solo se ve por API o SQL.
- **La profundidad máxima es global** (`_MAX_SPLIT_DEPTH = 2`), no configurable
  por diseño ni por request.
- **Un request individual demasiado pesado sigue sin solución automática.** La
  guarda lo detecta y lo dice claro, pero requiere intervención: acortar el
  body/URL de ese request o usar un modelo con mayor límite de salida.
- **Rebuild de contenedores:** no ejecutado (regla #7). El backend corre con
  `--reload` y tomó los cambios solo.
