"""
Modelos para almacenar ejecuciones de tests JMeter - VERSIÓN COMPLETA
"""
from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.db.base_class import Base

class TestExecution(Base):
    __tablename__ = "test_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    jtl_filename = Column(String(255), nullable=False)
    
    # Info del archivo
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Métricas agregadas
    total_requests = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)
    avg_response_time = Column(Float, default=0.0)
    median_response_time = Column(Float, default=0.0)
    min_response_time = Column(Float, default=0.0)
    max_response_time = Column(Float, default=0.0)
    p50_response_time = Column(Float, default=0.0)
    p90_response_time = Column(Float, default=0.0)
    p95_response_time = Column(Float, default=0.0)
    p99_response_time = Column(Float, default=0.0)
    throughput = Column(Float, default=0.0)  # requests/sec
    
    # Nuevas métricas
    avg_latency = Column(Float, default=0.0)
    kb_per_sec_received = Column(Float, default=0.0)
    kb_per_sec_sent = Column(Float, default=0.0)
    
    # Análisis IA - Editables
    ai_analysis_summary = Column(Text, nullable=True)  # Análisis del Reporte Resumen
    ai_analysis_errors = Column(Text, nullable=True)   # Análisis de Errores
    ai_analysis_response_times = Column(Text, nullable=True)  # Response Times por Transacción
    ai_analysis_response_time_over_time = Column(Text, nullable=True)  # Response Time Over Time
    ai_analysis_throughput = Column(Text, nullable=True)  # Throughput Over Time
    ai_analysis_latency = Column(Text, nullable=True)  # Latency Over Time
    ai_analysis_error_rate = Column(Text, nullable=True)  # Error Rate Over Time
    ai_analysis_codes_per_second = Column(Text, nullable=True)  # Response Codes per Second
    ai_analysis_transactions_per_second = Column(Text, nullable=True)  # Transactions per Second
    ai_analysis_active_threads = Column(Text, nullable=True)  # Active Threads Over Time
    ai_recommendations = Column(Text, nullable=True)  # Recomendaciones generales
    
    # Timestamps
    execution_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TestResult(Base):
    __tablename__ = "test_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Datos del JTL - TODOS los campos
    timestamp = Column(DateTime, nullable=False)
    elapsed_time = Column(Integer, nullable=False)  # timeStamp -> elapsed
    label = Column(String(255), nullable=False)
    response_code = Column(String(10), nullable=False)
    response_message = Column(String(255), nullable=True)
    thread_name = Column(String(100), nullable=True)
    data_type = Column(String(50), nullable=True)
    success = Column(Boolean, default=True)
    failure_message = Column(Text, nullable=True)
    bytes_received = Column(Integer, default=0)  # bytes
    bytes_sent = Column(Integer, default=0)  # sentBytes
    grp_threads = Column(Integer, default=0)  # grpThreads
    all_threads = Column(Integer, default=0)  # allThreads
    url = Column(Text, nullable=True)
    latency = Column(Integer, default=0)
    idle_time = Column(Integer, default=0)
    connect_time = Column(Integer, default=0)  # Connect