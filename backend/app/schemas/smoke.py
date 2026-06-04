"""Schemas Pydantic para el smoke test (Sprint 2.5b)."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SmokeSamplerResult(BaseModel):
    """Resultado por sampler tras un smoke test."""

    label: str
    success: bool
    response_code: str
    response_message: str = ""
    elapsed_ms: int = 0
    failure_message: Optional[str] = None


class SmokeTestResult(BaseModel):
    """Resumen completo del smoke test devuelto al frontend.

    status:
        - "success": todos los samplers pasaron.
        - "partial": algunos pasaron y otros fallaron.
        - "failed":  ningun sampler paso (o el JTL quedo vacio).
        - "error":   JMeter no llego ni a ejecutar (timeout, FileNotFoundError, etc.).
    """

    status: Literal["success", "partial", "failed", "error"]
    duration_sec: float = Field(..., description="Tiempo total de ejecucion incluyendo arranque de JMeter")
    total_samples: int = 0
    successful_samples: int = 0
    failed_samples: int = 0
    samplers: List[SmokeSamplerResult] = []
    jmeter_log_tail: Optional[str] = Field(
        None, description="Ultimas ~3 KB del jmeter.log para diagnosticar fallos"
    )
    error_message: Optional[str] = None
