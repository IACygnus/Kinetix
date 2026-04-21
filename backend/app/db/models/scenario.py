# backend/app/db/models/scenario.py
"""
Modelo Scenario — Configuracion de escenarios de prueba de performance.
Cada escenario define el tipo de prueba (load, stress, spike, soak, custom)
y la configuracion del Stepping Thread Group.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)

    script_id = Column(Integer, ForeignKey("script_designs.id"), nullable=False)

    # Tipo de prueba
    test_type = Column(String(50), nullable=False, default="load")
    # Valores: load | stress | spike | soak | custom

    # Configuracion del Stepping Thread Group (nuestro motor propio)
    # {
    #   "initial_users": 1,
    #   "step_users": 5,            # usuarios que se agregan por paso
    #   "step_duration_sec": 30,    # duracion de cada paso
    #   "hold_duration_sec": 600,   # tiempo en carga maxima
    #   "max_users": 50,
    #   "ramp_down_sec": 60,
    #   "total_duration_sec": 1800,
    #   "think_time_ms": 1000,      # tiempo de espera entre requests por usuario
    #   "iterations": 0             # 0 = infinito hasta que termine el tiempo
    # }
    thread_group_config = Column(JSON, nullable=False, default=dict)

    # Criterios de aceptacion opcionales para este escenario
    # {
    #   "max_avg_response_time_ms": 2000,
    #   "max_p95_response_time_ms": 5000,
    #   "max_error_rate_percent": 1.0,
    #   "min_tps": 10.0
    # }
    acceptance_criteria = Column(JSON, nullable=True, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    script = relationship("ScriptDesign", back_populates="scenarios")
    executions = relationship("PerformanceExecution", back_populates="scenario", cascade="all, delete-orphan")
