"""
Tracker en memoria de ejecuciones JMeter FULL en curso (Sprint 2.5d.1).

Mapea ``execution_id`` (int de performance_executions) -> metadata mutable
(pid del subprocess, workdir, jtl_path, status, ultimas metricas, elapsed...).

Necesario para:
- ``GET /performance-executions/{id}/live-metrics`` — leer metricas sin tocar DB
  en cada tick (el frontend hace polling cada 2s).
- ``POST /performance-executions/{id}/stop`` — recuperar el pid y matar el proceso.

Es un singleton in-process. Si el backend reinicia, las ejecuciones en curso se
pierden del tracker (el status final igual se persiste en DB al terminar el task).
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any, Dict, Optional


class ExecutionTracker:
    def __init__(self) -> None:
        self._registry: Dict[int, Dict[str, Any]] = {}
        self._lock = Lock()

    def register(self, execution_id: int, metadata: Dict[str, Any]) -> None:
        with self._lock:
            self._registry[execution_id] = {
                **metadata,
                "registered_at": time.time(),
            }

    def get(self, execution_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._registry.get(execution_id)
            return dict(data) if data is not None else None

    def update(self, execution_id: int, **kwargs: Any) -> None:
        with self._lock:
            if execution_id in self._registry:
                self._registry[execution_id].update(kwargs)

    def unregister(self, execution_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._registry.pop(execution_id, None)

    def all_running(self) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            return {
                k: dict(v)
                for k, v in self._registry.items()
                if v.get("status") in ("running", "starting", "stopping")
            }


# Singleton compartido por endpoints y background tasks.
execution_tracker = ExecutionTracker()
