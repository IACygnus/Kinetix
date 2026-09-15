# Reporte para Fredy — F2.1: Auto-split de chunks truncados

**Fecha:** 2026-07-28 · **Branch:** `backup-trabajo-local`
**Commit:** `9b675e0` · **Push:** ✅ solo a `github` (`ac82acb..9b675e0`). **`origin` (Azure/producción) NO se tocó.**

---

## 1. Estado

**Funcionó.** El HAR de Pideky pasó de **90/105 samplers** a **105/105**, con
`generation_status = completed` y XML válido, **sin intervención manual**.

El chunk 4 —el que fallaba siempre y que en F2 te documenté como el límite
duro— truncó otra vez, pero esta vez el sistema lo partió solo en dos bloques
de 7 y 8 requests, los generó y siguió.

Antes de escribir código verifiqué el contexto contra el repo: HEAD
descendiente de `81d2cc7`, baseline 349, y cómo viaja hoy la señal de
truncación. Todo coincidía.

---

## 2. Qué cambió, en una frase

Cuando un chunk falla **por truncación**, en vez de cortar el flujo se parte en
dos y se reintentan las mitades en el mismo ciclo.

**Para cualquier otro fallo, el contrato que definiste sigue igual**: XML mal
formado sin truncación, error de red o límite de cuota siguen cortando al
primer fallo. La excepción es solo la truncación, porque es el único caso donde
partir cambia el resultado — reintentar sin partir es matemáticamente inútil,
y en F2 lo comprobamos dos veces.

---

## 3. Cambios (4 archivos, 740 inserciones, 56 borrados)

| Archivo | Δ |
|---|---:|
| `backend/tests/test_chunked_generation_endpoint.py` | +317 |
| `backend/app/api/v1/endpoints/script_ai.py` | +210 |
| `backend/tests/test_har_chunk_router.py` | +139 |
| `backend/app/services/ai/har_chunk_router.py` | +130 |

**Sin migración de base de datos**: el linaje del split (`split_depth`,
`parent_chunk_id`) entra en el `chunks_plan`, que ya era JSONB.

Sin cambios en frontend. Ningún archivo protegido tocado. `/generate`,
`/generate-from-file` y `/refine` intactos. Backups
`.bak_f21_20260728_215644`.

### Memoria de costos — lo verifiqué antes de tocar

`grep` sobre `app/` y `tests/`: **`_CHUNK_SIZE` no tiene doble uso** (vive solo
como default de `group_entries_into_chunks`), igual que
`_MIN_FUNCTIONAL_FOR_CHUNKING` y `_CHUNK_MAX_TOKENS`.

**No lo modifiqué.** El split es local al bloque que truncó: bajar el tamaño
global habría encarecido *todas* las generaciones para arreglar un caso
puntual. La única constante nueva es `_MAX_SPLIT_DEPTH = 2`.

---

## 4. Tests — cifras reales contadas con pytest

| Momento | Resultado |
|---|---|
| Baseline (`ac82acb`) | **349 passed** / 19.03s |
| Después | **380 passed** / 17.41s |
| **Delta** | **+31** |

17 de `split_chunk` · 14 de la orquestación. Ningún test del baseline se rompió;
**uno se reescribió** (explicado en la sección 7).

### Los tests encontraron dos bugs reales míos

1. **`_try_auto_split` escribía el `failure_reason` y el caller lo pisaba** una
   línea después. Efecto: un bloque de 1 solo request que truncaba mostraba el
   mensaje genérico en vez de "requiere revisión manual". Lo cambié para que
   devuelva el motivo en vez de mutarlo.
2. **`last_finish_reason` quedaba colgado** de la llamada anterior si el
   proveedor levantaba excepción. Efecto: un error de red posterior a una
   truncación se habría diagnosticado como truncación y disparado un split
   inútil. Ahora se limpia *antes* de llamar.

---

## 5. La corrida en vivo, paso a paso

Punto de partida (lo que dejó F2): `partial`, 6/7 bloques, 90 samplers, chunk 4
`failed`.

```
retry chunks: 1 failed->pending, 1 pendientes en total
chunk 4 trunco -> auto-split en C8 (7) + C9 (8), nivel 1
chunk 8 insertado — 14 elementos, 7 samplers nuevos   -> 97 acumulados
chunk 9 insertado — 16 elementos, 8 samplers nuevos   -> 105 acumulados
```

Total: **327 segundos**, 3 llamadas al modelo (el intento del 4 + las dos
mitades).

### El plan final, con el linaje visible

```
 chunk |  estado   | entries | nivel | padre
-------+-----------+---------+-------+-------
 1     | completed |      21 | 0     | -
 2     | completed |      15 | 0     | -
 3     | completed |      15 | 0     | -
 4     | split     |      15 | 0     | -     <- el padre queda como rastro
 8     | completed |       7 | 1     | 4     <- hijo
 9     | completed |       8 | 1     | 4     <- hijo
 5     | completed |      15 | 0     | -     <- ID original intacto
 6     | completed |      15 | 0     | -
 7     | completed |       9 | 0     | -

 generation_mode | chunks_completed_count | generation_status | jmx_len
 chunked         |                      8 | completed         |  233489
```

Fijate en tres cosas:

- **C5, C6 y C7 conservan sus IDs.** Nada se renumeró — era la restricción
  dura, porque los prefijos `[Cn]` ya están escritos en los `testname` del JMX
  y renumerar los rompería en silencio.
- **Los hijos van justo después del padre**, no al final: el orden del HAR se
  mantiene y los samplers salen en secuencia.
- **`7 + 8 = 15`**: los hijos cubren exactamente al padre, sin perder ni
  duplicar requests.

El motivo del padre quedó como documentación de lo que pasó:

> *"…el modelo agoto su limite de tokens de salida y corto el XML a mitad
> (finish_reason=length). … Se partio automaticamente en los bloques C8 (7
> requests) y C9 (8 requests)."*

### El JMX

| Métrica | Antes (F2) | Después (F2.1) |
|---|---:|---:|
| XML válido | sí | **sí** |
| Tamaño | 205.387 bytes | **233.489 bytes** |
| Samplers | 90 | **105** |
| Cobertura del HAR | 90/105 | **105/105** |

No hizo falta el segundo nivel de split: las mitades de 7 y 8 requests entraron
holgadas.

---

## 6. Las guardas que pediste

| Guarda | Qué hace |
|---|---|
| **Tamaño mínimo** | Un bloque de 1 request no se parte. Si trunca, queda `failed` con: *"un entry individual excede la capacidad de salida del modelo y requiere revisión manual"*. |
| **Profundidad máxima** | `_MAX_SPLIT_DEPTH = 2` → cadena 15 → ~8 → ~4. Si a ese nivel sigue truncando, `failed` con *"ya se partió 2 veces y sigue truncando"*. |
| **Linaje** | `split_depth` y `parent_chunk_id` en cada hijo; el padre queda en el plan con `status='split'`. |

Cuál se dispara primero depende del tamaño del bloque: con bloques chicos se
llega antes al mínimo de 2 requests que al tope de profundidad. Hay un test
para cada camino, y uno que confirma que **no se generan chunks de nivel 3**.

**Los conteos siguen coherentes:** el padre `split` no cuenta como bloque
generable (si no, una generación completa se vería `partial` para siempre) ni
como pendiente (si no, el retry entraría en un ciclo sin trabajo).

---

## 7. Adaptaciones respecto al prompt

1. **`split_chunk` recibe un segundo parámetro `next_chunk_id`.** El prompt lo
   pedía como `split_chunk(chunk)`, pero asignar IDs libres exige conocer el
   plan, y meter el plan adentro la ataría al estado. El ID libre lo calcula
   `next_free_chunk_id(plan)` —también pura y testeada aparte— y se inyecta.
2. **Agregué `can_split_chunk(chunk) -> (bool, motivo)`.** `split_chunk`
   devuelve `None` en los dos casos no divisibles; sin este helper el
   orquestador no podría distinguir "es de 1 request" de "ya se partió 2 veces"
   para el mensaje.
3. **`_try_auto_split` devuelve `(absorbido, motivo)`**, no solo un bool — el
   bug #1 de la sección 4.
4. **`total_chunks` cambió de semántica**: era `len(plan)`, ahora cuenta solo
   bloques generables.
5. **Un test de F2 se reescribió, no se borró.**
   `test_fallo_por_truncado_del_modelo_lo_dice_explicito` verificaba que una
   truncación dejara el mensaje explícito en un chunk `failed`. Bajo F2.1 una
   truncación divisible ya no falla —se parte—, así que ahora usa un bloque que
   alcanzó el tope de profundidad. La intención se conserva, y el camino nuevo
   lo cubre `test_el_motivo_del_padre_documenta_el_split`.
6. **Sin migración SQL:** no hizo falta, el linaje entra en el JSONB existente.

---

## 8. Commit y pendientes

**Commit:** `9b675e0` — *"Sprint 3.0 F2.1: auto-split de chunks truncados"*
**Push:** ✅ `github/backup-trabajo-local` (`ac82acb..9b675e0`).
**`origin` (Azure DevOps / producción): NO se tocó.**

Reporte técnico: `docs/reports/repo/sprint-3.0-f2.1-auto-split.md`.

**Pendientes:**

- **Sin UI.** El auto-split es transparente por API, pero el plan con linaje
  solo se ve por endpoint o SQL.
- **`_MAX_SPLIT_DEPTH` es global**, no configurable por diseño ni por request.
- **Un request individual demasiado pesado sigue sin solución automática.** La
  guarda lo detecta y lo dice claro, pero requiere que alguien acorte ese
  request o cambie a un modelo con mayor límite de salida.
- **Ejecución síncrona:** la request HTTP queda abierta toda la generación (327s
  en esta corrida). Sigue siendo el pendiente de F2.
- **Rebuild de contenedores: NO ejecutado** (regla #7). El backend corre con
  `--reload` y tomó los cambios solo.

---

## 9. Cómo reproducirlo

```bash
# Con un diseño que quedó partial por truncación:
curl -s -b cookies.txt -X POST \
  "http://localhost:8001/api/v1/script-designer/ai/designs/<DESIGN_ID>/retry-failed-chunks" \
  -H "X-CSRF-Token: <CSRF>"
```

```sql
-- El plan con el linaje del split
SELECT (c->>'chunk_id') AS chunk, (c->>'status') AS estado,
       jsonb_array_length(c->'entry_idxs') AS entries,
       coalesce(c->>'split_depth','0') AS nivel,
       coalesce(c->>'parent_chunk_id','-') AS padre
  FROM ai_script_designs x, jsonb_array_elements(x.chunks_plan) c
 WHERE x.id = '<DESIGN_ID>';
```
