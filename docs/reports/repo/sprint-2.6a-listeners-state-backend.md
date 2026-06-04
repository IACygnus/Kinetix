# Sprint 2.6a — Backend listeners-state

## Objetivo
Backend del polling de JTL en vivo para los listeners en vivo. Servicio que
parsea el JTL en streaming (incremental) cada vez que el frontend polea (~2s),
con cache por `execution_id`, y endpoint que devuelve el estado agregado de los
listeners para que los renderers de 2.6c-g lo consuman.

## Arquitectura

`backend/app/services/engine/listeners_state_service.py` (módulo nuevo):

- **`ListenersStateCache`** — singleton thread-safe (`Lock`). Cache por
  `execution_id` con: `byte_offset` (parse incremental), `header`, `all_samples`
  (cap 5000), agregados `per_sampler` y `time_buckets`, `last_access` (TTL 600s).
- **`_parse_incremental(jtl_path, byte_offset, header)`** — lee SOLO los bytes
  nuevos desde el último offset. Maneja líneas parciales (archivo en escritura):
  corta en el último `\n` y no cruza la línea incompleta.
- **`compute_listeners_state(...)`** — función pública. Parsea si la ejecución
  sigue activa, o si el cache está recién inicializado (primer poll de una
  ejecución ya terminada → parsea el JTL completo una vez y luego congela).
- **`cleanup_execution_cache(execution_id)`** — libera el cache (al cerrar drawer).
- Helpers: `_percentile`, `_stddev`, `_update_per_sampler_stats`,
  `_update_time_buckets`, `_build_per_sampler_response`, `_build_time_buckets_response`.

### Correcciones respecto al diseño inicial
Durante la implementación se detectaron y corrigieron 2 defectos del borrador:

1. **`f.tell()` tras iterar `csv.reader` lanza `OSError`** ("telling position
   disabled by next() call"): el offset nunca avanzaba → cada poll **duplicaba**
   todos los samples. Reescrito con lectura binaria (`open(rb)` + `seek` + `read`)
   y corte byte-exacto por el último `\n`. Offset siempre consistente y sin
   duplicados (verificado con `test_parse_incremental_no_repite_samples` y
   `test_parse_incremental_lee_solo_lo_nuevo`).
2. **Ejecución terminada nunca poleada en vivo**: con la lógica literal el cache
   quedaba vacío (skip total) y una ejecución `completed` devolvía 0 samples.
   Añadido `freshly_initialized`: el primer poll de una ejecución terminada
   parsea el JTL completo una vez; pólizas posteriores quedan congeladas.

## Endpoints nuevos

`backend/app/api/v1/endpoints/performance_executions.py`:

- `GET  /performance-executions/{id}/listeners-state`
  Tracker en memoria primero (ejecución en curso) → fallback a DB (terminada).
  Auth `admin|analyst` + chequeo de ownership en la rama DB.
- `DELETE /performance-executions/{id}/listeners-state-cache`
  Libera el cache (frontend lo llama al cerrar el drawer — Opción R híbrida).

## Estructura del response

```json
{
  "execution_id": 25,
  "status": "completed",
  "elapsed_sec": 45.2,
  "total_samples_parsed": 60,
  "bucket_size_sec": 2,
  "samples_tail": [ /* últimos 100 samples crudos para View Results Tree */ ],
  "per_sampler_stats": {
    "1. Auth": {
      "count": 10, "errors": 0, "min": ..., "max": ..., "avg": 422.2,
      "median": ..., "p90": ..., "p95": 669, "p99": ..., "std_dev": ...,
      "throughput_per_sec": 0.67, "kb_received_per_sec": ...,
      "kb_sent_per_sec": ..., "error_pct": 0.0
    }
  },
  "time_buckets": [
    { "bucket_start_sec": 0, "bucket_end_sec": 2,
      "per_sampler": { "1. Auth": {"count": 5, "avg_response_ms": 145, "throughput": 2.5} },
      "totals": { "count": 12, "avg_response_ms": 152, "throughput": 6.0,
                  "active_threads_max": 3, "codes": {"200": 11, "500": 1} } }
  ]
}
```

## Tests

`backend/tests/test_listeners_state_service.py` (10 nuevos, +2 sobre los 8
planeados para cubrir el parse incremental real y el primer-poll terminal):

- parseo de JTL, métricas por sampler, no-duplicación, lectura incremental
  (solo lo nuevo), time buckets, status terminal congela / primer-poll parsea,
  cleanup de cache, `_percentile`, `_stddev`.

**Resultado:** `100 → 110 PASS` (+10), 2 deselected (slow). Sin regresiones.

## Validación

- Tests: **110 passed, 2 deselected** (`pytest -m "not slow"`).
- Endpoints registrados (2): `GET .../listeners-state`, `DELETE .../listeners-state-cache`.
- Curl `GET /listeners-state` sobre ejecución completada #25:
  `total_samples=60`, 5 samplers en `per_sampler_stats`, 6 `time_buckets`,
  60 en `samples_tail`. Ejemplo: `{count:10, errors:0, avg:422.2, p95:669, error_pct:0.0}`.
- Curl `DELETE /listeners-state-cache`: HTTP 200 `{"cache_cleared": true}`.

## Backup
`performance_executions.py.bak_26a_20260603_125826`.

## Fuera de alcance (confirmado)
Frontend (2.6b), renderers específicos (2.6c-g), smoke test (solo FULL).

## Estado: LISTO para Sprint 2.6b (frontend routing).
```