# backend/app/services/engine/metrics_collector.py
"""
MetricsCollector — Agrega métricas de ejecución en tiempo real.

Recibe RequestResults del JTLWriter (a través de hooks) y calcula
estadísticas agregadas: avg, p95, p99, TPS, error rate, etc.

Se usa para:
1. Retornar summary_metrics al finalizar la ejecución
2. Publicar métricas en tiempo real (Sprint 3 — WebSocket)
"""
import time
import statistics
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
from .protocols.base import RequestResult


class MetricsCollector:
    """
    Colector de métricas thread-safe para una ejecución de performance testing.

    Acumula RequestResults y calcula estadísticas agregadas bajo demanda.
    """

    def __init__(self):
        self._results: List[RequestResult] = []
        self._start_time: float = time.monotonic()
        self._end_time: Optional[float] = None

    def record(self, result: RequestResult):
        """Registrar un RequestResult."""
        self._results.append(result)

    def finalize(self):
        """Marcar el fin de la ejecución."""
        self._end_time = time.monotonic()

    def get_summary(self) -> Dict[str, Any]:
        """
        Calcular y retornar las métricas finales resumidas.

        Returns:
            Dict compatible con PerformanceExecution.summary_metrics
        """
        if not self._results:
            return {}

        elapsed_times = [r.elapsed_ms for r in self._results]
        successes = [r for r in self._results if r.success]
        failures = [r for r in self._results if not r.success]

        total_requests = len(self._results)
        total_errors = len(failures)
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

        avg_rt = statistics.mean(elapsed_times) if elapsed_times else 0

        sorted_times = sorted(elapsed_times)
        p95_rt = self._percentile(sorted_times, 95)
        p99_rt = self._percentile(sorted_times, 99)
        max_rt = max(elapsed_times) if elapsed_times else 0
        min_rt = min(elapsed_times) if elapsed_times else 0

        # TPS: total requests / duración total en segundos
        duration_sec = (self._end_time or time.monotonic()) - self._start_time
        avg_tps = total_requests / duration_sec if duration_sec > 0 else 0

        # TPS pico: calcular por ventana de 1 segundo
        peak_tps = self._calculate_peak_tps()

        total_bytes = sum(r.bytes_received for r in self._results)

        return {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate_percent": round(error_rate, 2),
            "avg_response_time_ms": round(avg_rt, 1),
            "p95_response_time_ms": p95_rt,
            "p99_response_time_ms": p99_rt,
            "max_response_time_ms": max_rt,
            "min_response_time_ms": min_rt,
            "avg_tps": round(avg_tps, 2),
            "peak_tps": round(peak_tps, 2),
            "total_bytes": total_bytes,
            "duration_sec": round(duration_sec, 1),
            "successful_requests": len(successes),
        }

    def get_by_label(self) -> Dict[str, Dict[str, Any]]:
        """
        Métricas agrupadas por label (nombre de transacción).
        Útil para el reporte de IA.
        """
        groups: Dict[str, list] = defaultdict(list)
        for r in self._results:
            groups[r.label].append(r)

        summary = {}
        for label, results in groups.items():
            times = [r.elapsed_ms for r in results]
            errors = sum(1 for r in results if not r.success)
            summary[label] = {
                "count": len(results),
                "errors": errors,
                "error_rate_percent": round(errors / len(results) * 100, 2),
                "avg_ms": round(statistics.mean(times), 1),
                "p95_ms": self._percentile(sorted(times), 95),
                "p99_ms": self._percentile(sorted(times), 99),
                "max_ms": max(times),
                "min_ms": min(times),
            }
        return summary

    @staticmethod
    def _percentile(sorted_data: List[int], percentile: int) -> int:
        """Calcular percentil de una lista ya ordenada."""
        if not sorted_data:
            return 0
        idx = int(len(sorted_data) * percentile / 100)
        idx = min(idx, len(sorted_data) - 1)
        return sorted_data[idx]

    def _calculate_peak_tps(self) -> float:
        """Calcular TPS pico usando ventana de 1 segundo."""
        if not self._results:
            return 0.0

        # Agrupar por segundo (usando timestamp_ms)
        seconds: Counter = Counter(r.timestamp_ms // 1000 for r in self._results)
        return max(seconds.values()) if seconds else 0.0

    @property
    def total_requests(self) -> int:
        return len(self._results)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self._results if not r.success)
