"""
Modelos para almacenar ejecuciones de tests JMeter - v2.0
Agrega: test_type, client, project, jtl_filenames, acceptance_criteria_json, redirect support
"""
from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.db.base_class import Base


class TestExecution(Base):
    __tablename__ = "test_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)

    # Metadata v2.0
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    client = Column(String(255), nullable=True)  # Legacy text field
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)
    project = Column(String(255), nullable=True)
    test_type = Column(String(50), nullable=False, default="load")
    jtl_filename = Column(String(255), nullable=False)
    jtl_filenames = Column(JSON, nullable=True)  # Array de nombres de archivos JTL
    acceptance_criteria_json = Column(JSON, nullable=True)  # {concurrency, response_time, availability}

    # Info del archivo
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Metricas agregadas
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
    throughput = Column(Float, default=0.0)

    # Metricas adicionales
    avg_latency = Column(Float, default=0.0)
    kb_per_sec_received = Column(Float, default=0.0)
    kb_per_sec_sent = Column(Float, default=0.0)

    # Redirecciones v2.0
    total_redirects = Column(Integer, default=0)
    redirect_labels = Column(JSON, nullable=True)  # Lista de labels identificados como redirect

    # Analisis IA - Editables
    ai_analysis_summary = Column(Text, nullable=True)
    ai_analysis_errors = Column(Text, nullable=True)
    ai_analysis_response_times = Column(Text, nullable=True)
    ai_analysis_response_time_over_time = Column(Text, nullable=True)
    ai_analysis_throughput = Column(Text, nullable=True)
    ai_analysis_latency = Column(Text, nullable=True)
    ai_analysis_error_rate = Column(Text, nullable=True)
    ai_analysis_codes_per_second = Column(Text, nullable=True)
    ai_analysis_transactions_per_second = Column(Text, nullable=True)
    ai_analysis_active_threads = Column(Text, nullable=True)
    ai_analysis_redirects = Column(Text, nullable=True)  # v2.0: analisis de redirecciones
    ai_recommendations = Column(Text, nullable=True)
    ai_conclusions = Column(Text, nullable=True)

    # KNX-17: Capacity analysis (JSON string)
    capacity_analysis_json = Column(Text, nullable=True)

    # P4: Metric unit (TPS or UVC)
    metric_unit = Column(String(10), nullable=True, default="TPS")

    # Timestamps
    execution_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), nullable=False)

    # Datos del JTL
    timestamp = Column(DateTime, nullable=False)
    elapsed_time = Column(Integer, nullable=False)
    label = Column(String(255), nullable=False)
    response_code = Column(String(10), nullable=False)
    response_message = Column(String(255), nullable=True)
    thread_name = Column(String(100), nullable=True)
    data_type = Column(String(50), nullable=True)
    success = Column(Boolean, default=True)
    failure_message = Column(Text, nullable=True)
    bytes_received = Column(Integer, default=0)
    bytes_sent = Column(Integer, default=0)
    grp_threads = Column(Integer, default=0)
    all_threads = Column(Integer, default=0)
    url = Column(Text, nullable=True)
    latency = Column(Integer, default=0)
    idle_time = Column(Integer, default=0)
    connect_time = Column(Integer, default=0)
