"""
Schemas Pydantic para validacion de API - Test Executions v2.0
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class TestExecutionBase(BaseModel):
    name: str
    description: Optional[str] = None
    jtl_filename: str


class TestExecutionCreate(TestExecutionBase):
    pass


class TestExecutionResponse(TestExecutionBase):
    id: Any
    user_id: Optional[Any] = None

    # v2.0 metadata
    client: Optional[str] = None
    client_id: Optional[Any] = None
    project: Optional[str] = None
    test_type: str = "load"
    jtl_filenames: Optional[List[str]] = None
    acceptance_criteria_json: Optional[Dict[str, Any]] = None

    # Info del archivo
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Metricas
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

    # Metricas adicionales
    avg_latency: Optional[float] = None
    kb_per_sec_received: Optional[float] = None
    kb_per_sec_sent: Optional[float] = None

    # Redirecciones v2.0
    total_redirects: int = 0
    redirect_labels: Optional[List[str]] = None

    # Analisis IA editables
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
    ai_analysis_redirects: Optional[str] = None
    ai_recommendations: Optional[str] = None
    ai_conclusions: Optional[str] = None

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
    error_count: int = 0
    error_rate: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    throughput: float = 0.0
    kb_received: float = 0.0
    kb_sent: float = 0.0
    is_redirect: bool = False


class TimeSeriesPoint(BaseModel):
    timestamp: str
    value: float
    label: Optional[str] = None
    code: Optional[str] = None


class ChartData(BaseModel):
    timeline: List[TimelineData]
    by_label: List[LabelStats]
    by_label_redirects: List[LabelStats] = []
    response_codes: Dict[str, int]

    # Datos para graficos
    response_times_by_label: List[TimeSeriesPoint] = []
    throughput_timeline: List[TimeSeriesPoint] = []
    latency_timeline: List[TimeSeriesPoint] = []
    error_rate_timeline: List[TimeSeriesPoint] = []
    codes_per_second: List[TimeSeriesPoint] = []
    tps_by_label: List[TimeSeriesPoint] = []
    active_threads_timeline: List[TimeSeriesPoint] = []

    # Totales v2.0
    total_main_samples: int = 0
    total_all_samples: int = 0
    has_redirects: bool = False


class ValidationResult(BaseModel):
    compatible: bool
    errors: List[str] = []
    warnings: List[str] = []
    summary: Optional[Dict[str, Any]] = None
