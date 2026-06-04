"""
Servicio que computa el estado en vivo de los listeners de una ejecución JMeter.

Diseño:
- El frontend polea cada 2s a /listeners-state.
- Este servicio mantiene un cache por execution_id con:
  - Offset de bytes ya leídos del JTL (parse incremental).
  - Lista acumulada de samples (con cap de 5000 para View Results Tree).
  - Métricas agregadas por sampler (para Summary/Aggregate).
  - Buckets de tiempo agregados (para gráficas jp@gc).
- Cada call lee SOLO los bytes nuevos del JTL.
- Cuando la ejecución termina, el cache se mantiene hasta que se cierra el drawer
  (TTL de 10 min sin updates → cleanup). El primer poll de una ejecución ya
  terminada parsea el JTL completo una sola vez y luego congela el cache.

Estructura del response:
{
  "execution_id": 123,
  "status": "running" | "completed" | etc.,
  "elapsed_sec": 45.2,
  "total_samples_parsed": 1234,

  "samples_tail": [...],  // últimos 100 samples (para View Results Tree)

  "per_sampler_stats": {  // para Summary Report / Aggregate Report
    "1. Auth": {
      "count": 234, "errors": 2, "min": 50, "max": 480,
      "avg": 145, "median": 130, "p90": 220, "p95": 280, "p99": 380,
      "std_dev": 45.6, "throughput_per_sec": 5.2, "kb_received_per_sec": 12.3,
      "error_pct": 0.85
    },
    "2. GetBooking": { ... }
  },

  "time_buckets": [  // para gráficas jp@gc (interval_grouping desde el listener)
    {
      "bucket_start_sec": 0,
      "bucket_end_sec": 2,
      "per_sampler": {
        "1. Auth": { "count": 5, "avg_response_ms": 145, "throughput": 2.5 }
      },
      "totals": { "count": 12, "avg_response_ms": 152, "throughput": 6.0,
                  "active_threads_max": 3, "codes": {"200": 11, "500": 1} }
    },
    { ... }
  ]
}
"""
import csv
import logging
import os
import time
from collections import defaultdict
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)

# Cap de samples mantenidos en memoria por ejecución (para View Results Tree)
SAMPLES_TAIL_CAP = 100   # solo enviar últimos 100 al frontend
SAMPLES_FULL_CAP = 5000  # cap absoluto en memoria

# Bucket size para gráficas (segundos)
DEFAULT_BUCKET_SIZE_SEC = 2

# TTL del cache desde el último access (segundos)
CACHE_TTL_SEC = 600

# Estados terminales: una vez aquí, el cache se congela tras el primer parse.
_TERMINAL_STATUSES = ("completed", "cancelled", "error")


class ListenersStateCache:
    """Cache thread-safe por execution_id."""

    def __init__(self):
        self._cache: Dict[int, Dict[str, Any]] = {}
        self._lock = Lock()

    def get_or_init(self, execution_id: int, jtl_path: str, start_time: float) -> Dict[str, Any]:
        with self._lock:
            if execution_id not in self._cache:
                self._cache[execution_id] = {
                    "jtl_path": jtl_path,
                    "start_time": start_time,
                    "byte_offset": 0,
                    "header": None,  # se setea en el primer parse
                    "all_samples": [],  # lista de dicts (parsed rows)
                    "per_sampler": defaultdict(lambda: {
                        "elapsed_list": [],
                        "errors": 0,
                        "bytes_received": 0,
                        "bytes_sent": 0,
                    }),
                    "time_buckets": defaultdict(lambda: {
                        "samples_by_sampler": defaultdict(list),
                        "active_threads_max": 0,
                        "codes": defaultdict(int),
                    }),
                    "last_access": time.time(),
                }
            self._cache[execution_id]["last_access"] = time.time()
            return self._cache[execution_id]

    def get(self, execution_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._cache.get(execution_id)
            if entry:
                entry["last_access"] = time.time()
            return entry

    def cleanup_stale(self):
        """Elimina entradas con TTL expirado."""
        now = time.time()
        with self._lock:
            stale = [eid for eid, e in self._cache.items() if now - e["last_access"] > CACHE_TTL_SEC]
            for eid in stale:
                del self._cache[eid]

    def invalidate(self, execution_id: int):
        with self._lock:
            self._cache.pop(execution_id, None)


# Singleton
listeners_cache = ListenersStateCache()


def _parse_incremental(
    jtl_path: str,
    byte_offset: int,
    header: Optional[List[str]],
) -> Tuple[List[Dict[str, Any]], int, Optional[List[str]]]:
    """
    Lee solo los bytes nuevos del JTL desde byte_offset.

    Usa lectura binaria + corte por el último '\\n' para:
    - Evitar el OSError de ``f.tell()`` tras iterar ``csv.reader`` sobre un file
      object (Python deshabilita tell() después de usar el iterador del archivo).
    - Manejar líneas parciales: si el archivo está en escritura, la última línea
      sin '\\n' se deja sin consumir y el offset NO la cruza (se reintenta luego).

    Retorna: (samples nuevos como dicts, nuevo offset en bytes, header conocido).
    """
    if not os.path.exists(jtl_path):
        return [], byte_offset, header

    new_samples: List[Dict[str, Any]] = []

    try:
        with open(jtl_path, "rb") as f:
            f.seek(byte_offset)
            chunk = f.read()

        if not chunk:
            return [], byte_offset, header

        # Cortar en el último '\n' para no parsear una línea parcial (offset byte-exacto).
        if chunk.endswith(b"\n"):
            complete = chunk
        else:
            last_nl = chunk.rfind(b"\n")
            if last_nl == -1:
                # Ninguna línea completa todavía.
                return [], byte_offset, header
            complete = chunk[: last_nl + 1]

        consumed_bytes = len(complete)
        text = complete.decode("utf-8", errors="replace")
        lines = text.splitlines()

        # Primera lectura: la primera línea es el header.
        if byte_offset == 0 and header is None and lines:
            header = lines[0].strip().split(",")
            lines = lines[1:]

        # Header desconocido pero ya pasamos el inicio: leerlo del archivo.
        if header is None:
            try:
                with open(jtl_path, "r", encoding="utf-8", errors="replace") as hf:
                    first = hf.readline()
                    if first:
                        header = first.strip().split(",")
            except Exception:
                header = None

        if header:
            reader = csv.DictReader(lines, fieldnames=header)
            for row in reader:
                ts = row.get("timeStamp")
                if ts and ts != "timeStamp":
                    new_samples.append(row)

        return new_samples, byte_offset + consumed_bytes, header
    except Exception as e:
        logger.warning("Error parseando JTL incremental (%s): %s", jtl_path, e)
        return [], byte_offset, header


def _update_per_sampler_stats(entry: Dict[str, Any], samples: List[Dict[str, Any]]):
    """Actualiza las stats agregadas por sampler con los samples nuevos."""
    for s in samples:
        label = s.get("label", "")
        try:
            elapsed = int(s.get("elapsed", 0) or 0)
        except (ValueError, TypeError):
            elapsed = 0
        success = (s.get("success", "") or "").lower() == "true"
        try:
            bytes_recv = int(s.get("bytes", 0) or 0)
            bytes_sent = int(s.get("sentBytes", 0) or 0)
        except (ValueError, TypeError):
            bytes_recv = 0
            bytes_sent = 0

        bucket = entry["per_sampler"][label]
        bucket["elapsed_list"].append(elapsed)
        if not success:
            bucket["errors"] += 1
        bucket["bytes_received"] += bytes_recv
        bucket["bytes_sent"] += bytes_sent


def _update_time_buckets(
    entry: Dict[str, Any],
    samples: List[Dict[str, Any]],
    bucket_size_sec: int = DEFAULT_BUCKET_SIZE_SEC,
):
    """
    Actualiza los buckets de tiempo (para gráficas).
    Cada bucket = un intervalo de bucket_size_sec segundos desde el inicio.
    """
    start_ms = int(entry["start_time"] * 1000)

    for s in samples:
        try:
            ts = int(s.get("timeStamp", 0) or 0)
        except (ValueError, TypeError):
            continue

        if ts < start_ms:
            continue

        elapsed_since_start = (ts - start_ms) / 1000.0
        bucket_idx = int(elapsed_since_start // bucket_size_sec)

        bucket = entry["time_buckets"][bucket_idx]
        label = s.get("label", "")
        try:
            elapsed = int(s.get("elapsed", 0) or 0)
            all_threads = int(s.get("allThreads", 0) or 0)
        except (ValueError, TypeError):
            elapsed = 0
            all_threads = 0

        bucket["samples_by_sampler"][label].append(elapsed)
        bucket["active_threads_max"] = max(bucket["active_threads_max"], all_threads)

        code = s.get("responseCode", "")
        bucket["codes"][code] += 1


def _percentile(values: List[int], p: float) -> int:
    """Calcula el percentil p (0-100) de una lista de valores."""
    if not values:
        return 0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return int(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def _stddev(values: List[int]) -> float:
    """Desviación estándar poblacional simple."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return round(variance ** 0.5, 2)


def _build_per_sampler_response(entry: Dict[str, Any], elapsed_sec: float) -> Dict[str, Any]:
    """Construye el dict per_sampler_stats para la respuesta."""
    result = {}
    for label, data in entry["per_sampler"].items():
        elapsed_list = data["elapsed_list"]
        count = len(elapsed_list)
        if count == 0:
            continue
        result[label] = {
            "count": count,
            "errors": data["errors"],
            "min": min(elapsed_list),
            "max": max(elapsed_list),
            "avg": round(sum(elapsed_list) / count, 1),
            "median": _percentile(elapsed_list, 50),
            "p90": _percentile(elapsed_list, 90),
            "p95": _percentile(elapsed_list, 95),
            "p99": _percentile(elapsed_list, 99),
            "std_dev": _stddev(elapsed_list),
            "throughput_per_sec": round(count / elapsed_sec, 2) if elapsed_sec > 0 else 0.0,
            "kb_received_per_sec": round((data["bytes_received"] / 1024) / elapsed_sec, 2) if elapsed_sec > 0 else 0.0,
            "kb_sent_per_sec": round((data["bytes_sent"] / 1024) / elapsed_sec, 2) if elapsed_sec > 0 else 0.0,
            "error_pct": round((data["errors"] / count) * 100, 2),
        }
    return result


def _build_time_buckets_response(
    entry: Dict[str, Any],
    bucket_size_sec: int = DEFAULT_BUCKET_SIZE_SEC,
) -> List[Dict[str, Any]]:
    """Construye la lista de buckets de tiempo para gráficas."""
    if not entry["time_buckets"]:
        return []

    buckets_list = []
    for idx in sorted(entry["time_buckets"].keys()):
        bucket = entry["time_buckets"][idx]
        per_sampler = {}
        total_count = 0
        total_elapsed_sum = 0
        for label, elapsed_list in bucket["samples_by_sampler"].items():
            count = len(elapsed_list)
            if count == 0:
                continue
            avg = sum(elapsed_list) / count
            per_sampler[label] = {
                "count": count,
                "avg_response_ms": round(avg, 1),
                "throughput": round(count / bucket_size_sec, 2),
            }
            total_count += count
            total_elapsed_sum += sum(elapsed_list)

        buckets_list.append({
            "bucket_start_sec": idx * bucket_size_sec,
            "bucket_end_sec": (idx + 1) * bucket_size_sec,
            "per_sampler": per_sampler,
            "totals": {
                "count": total_count,
                "avg_response_ms": round(total_elapsed_sum / total_count, 1) if total_count > 0 else 0,
                "throughput": round(total_count / bucket_size_sec, 2),
                "active_threads_max": bucket["active_threads_max"],
                "codes": dict(bucket["codes"]),
            },
        })

    return buckets_list


def compute_listeners_state(
    execution_id: int,
    jtl_path: str,
    start_time: float,
    elapsed_sec: float,
    status: str,
) -> Dict[str, Any]:
    """
    Función pública: computa o actualiza el estado de listeners para una ejecución.

    Args:
        execution_id: id de PerformanceExecution.
        jtl_path: ruta absoluta al JTL.
        start_time: epoch seconds del inicio de la ejecución.
        elapsed_sec: segundos transcurridos.
        status: estado de la ejecución (running/completed/etc.).

    Returns:
        Dict con el estado completo para el frontend (ver docstring del módulo).
    """
    entry = listeners_cache.get_or_init(execution_id, jtl_path, start_time)

    # Parsear si la ejecución sigue activa, O si el cache está recién inicializado
    # (primer poll de una ejecución ya terminada → parsear el JTL completo una vez).
    is_terminal = status in _TERMINAL_STATUSES
    freshly_initialized = entry["byte_offset"] == 0 and not entry["all_samples"]

    if (not is_terminal) or freshly_initialized:
        new_samples, new_offset, header = _parse_incremental(
            jtl_path, entry["byte_offset"], entry["header"]
        )

        if header and entry["header"] is None:
            entry["header"] = header

        if new_samples:
            # Agregar a all_samples respetando el cap.
            entry["all_samples"].extend(new_samples)
            if len(entry["all_samples"]) > SAMPLES_FULL_CAP:
                entry["all_samples"] = entry["all_samples"][-SAMPLES_FULL_CAP:]

            _update_per_sampler_stats(entry, new_samples)
            _update_time_buckets(entry, new_samples)

        entry["byte_offset"] = new_offset

    # Tail de samples para View Results Tree.
    samples_tail = entry["all_samples"][-SAMPLES_TAIL_CAP:]

    return {
        "execution_id": execution_id,
        "status": status,
        "elapsed_sec": elapsed_sec,
        "total_samples_parsed": len(entry["all_samples"]),
        "samples_tail": samples_tail,
        "per_sampler_stats": _build_per_sampler_response(entry, elapsed_sec),
        "time_buckets": _build_time_buckets_response(entry),
        "bucket_size_sec": DEFAULT_BUCKET_SIZE_SEC,
    }


def cleanup_execution_cache(execution_id: int):
    """Limpia el cache de una ejecución (al cerrar el drawer del frontend)."""
    listeners_cache.invalidate(execution_id)
