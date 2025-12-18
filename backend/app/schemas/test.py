"""
Schemas Pydantic para validación de API - Test Executions
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

class TestExecutionBase(BaseModel):
    name: str
    description: Optional[str] = None
    jtl_filename: str

class TestExecutionCreate(TestExecutionBase):
    pass

class TestExecutionResponse(TestExecutionBase):
    id: Any  # Acepta UUID o str
    user_id: Optional[Any] = None  # Acepta UUID o str
    
    # Info del archivo
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Métricas
    total_requests: int
    total_errors: int
    error_rate: float
    avg_response_time: float
    median_response_time: Optional[float] = None
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p90_response_time: float
    p95_response_time: float
    p99_response_time: float
    throughput: float
    
    # Nuevas métricas
    avg_latency: Optional[float] = None
    kb_per_sec_received: Optional[float] = None
    kb_per_sec_sent: Optional[float] = None
    
    # Análisis IA editables
    ai_analysis_summary: Optional[str] = None
    ai_analysis_errors: Optional[str] = None
    ai_analysis_response_times: Optional[str] = None
    ai_analysis_response_time_over_time: Optional[str] = None
    ai_analysis_throughput: Optional[str] = None
    ai_analysis_latency: Optional[str] = None
    ai_analysis_error_rate: Optional[str] = None
    ai_analysis_codes_per_second: Optional[str] = None
    ai_analysis_transactions_per_second: Optional[str] = None
    ai_analysis_active_threads: Optional[str] = None
    ai_recommendations: Optional[str] = None
    ai_conclusions: Optional[str] = None  # ✅ CORREGIDO: Sintaxis Pydantic correcta
    
    # Timestamps
    execution_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class TimelineData(BaseModel):
    timestamp: str
    avg_response_time: float
    request_count: int

class LabelStats(BaseModel):
    label: str
    count: int
    avg_time: float
    min_time: float
    max_time: float
    success_count: int
    kb_received: float = 0.0
    kb_sent: float = 0.0

class TimeSeriesPoint(BaseModel):
    timestamp: str
    value: float
    label: Optional[str] = None
    code: Optional[str] = None

class ChartData(BaseModel):
    timeline: List[TimelineData]
    by_label: List[LabelStats]
    response_codes: Dict[str, int]
    
    # Nuevos datos para gráficos
    response_times_by_label: List[TimeSeriesPoint] = []
    throughput_timeline: List[TimeSeriesPoint] = []
    latency_timeline: List[TimeSeriesPoint] = []
    error_rate_timeline: List[TimeSeriesPoint] = []
    codes_per_second: List[TimeSeriesPoint] = []
    tps_by_label: List[TimeSeriesPoint] = []
    active_threads_timeline: List[TimeSeriesPoint] = []
    # ✅ REMOVIDO: ai_conclusions no pertenece aquí (es metadata de TestExecution)