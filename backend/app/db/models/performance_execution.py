# backend/app/db/models/performance_execution.py
"""
Modelo PerformanceExecution — Registro de ejecuciones del motor propio.
Almacena estado, metricas resumidas, rutas de archivos JTL/JMX y snapshot del escenario.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base


class PerformanceExecution(Base):
    __tablename__ = "performance_executions"

    id = Column(Integer, primary_key=True, index=True)

    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Estado de la ejecucion
    status = Column(String(50), nullable=False, default="pending")
    # Valores: pending | starting | running | stopping | completed | error | cancelled

    # Rutas de archivos generados
    jtl_file_path = Column(String(500), nullable=True)   # Ruta al .jtl de resultados
    jmx_file_path = Column(String(500), nullable=True)   # Ruta al .jmx exportado (opcional)

    # Nombre del archivo para descarga: NombreCliente_NombreProyecto_FechaHora
    output_filename = Column(String(255), nullable=True)

    # Metricas finales resumidas (se completan al finalizar)
    # {
    #   "total_requests": 1500,
    #   "total_errors": 12,
    #   "error_rate_percent": 0.8,
    #   "avg_response_time_ms": 245,
    #   "p95_response_time_ms": 890,
    #   "p99_response_time_ms": 1200,
    #   "max_response_time_ms": 2100,
    #   "min_response_time_ms": 45,
    #   "avg_tps": 8.5,
    #   "peak_tps": 12.3,
    #   "total_bytes": 4500000,
    #   "duration_sec": 180
    # }
    summary_metrics = Column(JSON, nullable=True, default=dict)

    # Metadata del escenario ejecutado (snapshot al momento de ejecucion)
    # Incluye: test_type, thread_group_config, acceptance_criteria
    scenario_snapshot = Column(JSON, nullable=True, default=dict)

    # Mensaje de error si status == "error"
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    scenario = relationship("Scenario", back_populates="executions")
