"""
Schema de operaciones estructuradas para el refine quirurgico (Sprint 2.4-HF5.1).

La IA devuelve un RefineOperationSet en JSON. El backend lo aplica a la
AIScriptStructure y regenera el JMX. Esto evita que la IA escupa el JMX completo
y se trunque con scripts grandes (problema observado en HF5 con gpt-4o sobre
JMX de ~95KB).

Si el cambio solicitado requiere agregar o borrar elementos (no soportado en MVP),
la IA puede devolver fallback_to_full_refine=true para que el backend
automaticamente caiga al endpoint /refine clasico del HF5.
"""
from typing import Optional, Dict, Any, List, Literal, Union

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------------
# Operaciones soportadas en MVP (solo updates + enable/disable)
# ----------------------------------------------------------------------------


class UpdateTestPlanOp(BaseModel):
    op: Literal["update_test_plan"] = "update_test_plan"
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Campos a actualizar: name, comments, functional_mode, serialize_threadgroups",
    )


class UpdateThreadGroupOp(BaseModel):
    op: Literal["update_thread_group"] = "update_thread_group"
    id: str = Field(..., description="ID del thread group")
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "num_threads, ramp_time, loops, continue_forever, on_sample_error, "
            "name, enabled, comments, stepping (objeto anidado)"
        ),
    )


class UpdateSamplerOp(BaseModel):
    op: Literal["update_sampler"] = "update_sampler"
    id: str = Field(..., description="ID del sampler")
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "name, method, domain, port, protocol, path, follow_redirects, "
            "auto_redirects, use_keepalive, content_encoding, "
            "body (objeto anidado: mode, raw_text, form_args, body_type)"
        ),
    )


class UpdateSamplerChildOp(BaseModel):
    op: Literal["update_sampler_child"] = "update_sampler_child"
    sampler_id: str
    child_id: str
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Campos del child especifico (depende del tipo: header, assertion, extractor, timer)",
    )


class UpdateUdvsOp(BaseModel):
    """Reemplaza completamente la lista de UDVs."""

    op: Literal["update_udvs"] = "update_udvs"
    udvs: List[Dict[str, str]] = Field(
        ..., description="Lista completa de UDVs: [{name, value, metadata?}]"
    )


class UpdateCsvDatasetOp(BaseModel):
    op: Literal["update_csv_dataset"] = "update_csv_dataset"
    id: str
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "testname, filename, variable_names (lista), delimiter, "
            "file_encoding, share_mode, ignore_first_line, recycle, "
            "stop_thread, quoted_data"
        ),
    )


class UpdateHttpDefaultsOp(BaseModel):
    op: Literal["update_http_defaults"] = "update_http_defaults"
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="protocol, domain, port, encoding, path, implementation",
    )


class EnableDisableOp(BaseModel):
    """Activar/desactivar cualquier elemento por id."""

    op: Literal["set_enabled"] = "set_enabled"
    target_kind: Literal[
        "thread_group",
        "sampler",
        "sampler_child",
        "csv_data_set",
        "listener",
        "config_element",
        "cookie_manager",
        "cache_manager",
    ]
    id: Optional[str] = Field(
        None,
        description="ID del elemento (no necesario para cookie/cache que son singleton)",
    )
    sampler_id: Optional[str] = Field(
        None, description="Si target_kind=sampler_child, id del sampler padre"
    )
    enabled: bool


# ============================================================================
# Operaciones de creacion (Sprint 2.4-HF7.A)
# ============================================================================


class AddSamplerOp(BaseModel):
    """Agrega un HTTPSampler nuevo a un Thread Group existente."""

    op: Literal["add_sampler"] = "add_sampler"
    thread_group_id: str = Field(
        ..., description="ID del TG destino"
    )
    sampler: Dict[str, Any] = Field(
        ...,
        description=(
            "Campos del sampler: name, method, domain, port, protocol, path, "
            "follow_redirects, auto_redirects, use_keepalive, body (anidado), "
            "content_encoding, enabled"
        ),
    )
    position: Optional[int] = Field(
        None, description="Indice donde insertar dentro de tg.children. None = al final"
    )


class AddSamplerChildOp(BaseModel):
    """Agrega un HeaderManager, Assertion, Extractor o Timer a un sampler."""

    op: Literal["add_sampler_child"] = "add_sampler_child"
    sampler_id: str
    child_kind: Literal[
        "header_manager",
        "response_assertion",
        "regex_extractor",
        "json_extractor",
        "constant_timer",
    ]
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Campos iniciales del child (depende del kind). Defaults razonables si vacio.",
    )


class AddUdvOp(BaseModel):
    """Agrega una variable nueva a la lista global de UDVs."""

    op: Literal["add_udv"] = "add_udv"
    name: str
    value: str = ""
    metadata: str = "="


class AddCsvDatasetOp(BaseModel):
    """Agrega un CSV Data Set nuevo a la estructura."""

    op: Literal["add_csv_dataset"] = "add_csv_dataset"
    data: Dict[str, Any] = Field(
        ...,
        description=(
            "testname, filename, variable_names (lista), delimiter, file_encoding, "
            "share_mode, ignore_first_line, recycle, stop_thread, quoted_data, enabled"
        ),
    )


# ============================================================================
# Operacion de eliminacion (Sprint 2.4-HF7.A)
# ============================================================================


class DeleteElementOp(BaseModel):
    """Elimina cualquier elemento del arbol por id (o por nombre para UDVs)."""

    op: Literal["delete_element"] = "delete_element"
    target_kind: Literal[
        "thread_group",
        "sampler",
        "sampler_child",
        "csv_data_set",
        "listener",
        "udv",
    ]
    id: Optional[str] = Field(
        None, description="ID del elemento (no requerido para UDV — usa udv_name)"
    )
    sampler_id: Optional[str] = Field(
        None,
        description="Si target_kind=sampler_child, id del sampler padre",
    )
    udv_name: Optional[str] = Field(
        None,
        description="Si target_kind=udv, nombre de la variable a borrar",
    )


# ============================================================================
# Sprint 2.4-HF7.B — agregar listener al test plan
# ============================================================================


class AddListenerOp(BaseModel):
    """Agrega un Listener al test plan.

    Tipos soportados (cada uno con su guiclass JMeter correspondiente y un
    raw_xml inicial razonable que incluye SaveConfig completo para los
    ResultCollector y el InfluxDB-compatible Backend Listener apuntando al
    stack Kinetix por defecto):

    - view_results_tree            → ResultCollector + ViewResultsFullVisualizer
    - view_results_tree_with_csv   → ResultCollector + ViewResultsFullVisualizer (persiste CSV)
    - summary_report               → ResultCollector + SummaryReport
    - aggregate_report             → ResultCollector + StatVisualizer
    - aggregate_report_with_csv    → ResultCollector + StatVisualizer (persiste JTL)
    - response_time_graph          → ResultCollector + RespTimeGraphVisualizer
    - jpgc_response_times_over_time   → CorrectedResultCollector + ResponseTimesOverTimeGui
    - jpgc_response_codes_per_second  → CorrectedResultCollector + ResponseCodesPerSecondGui
    - jpgc_transactions_per_second    → CorrectedResultCollector + TransactionsPerSecondGui
    - jpgc_active_threads_over_time   → CorrectedResultCollector + ThreadsStateOverTimeGui
    - backend_listener             → BackendListener (InfluxDB → Grafana)
    """

    op: Literal["add_listener"] = "add_listener"
    listener_kind: Literal[
        "view_results_tree",
        "view_results_tree_with_csv",
        "summary_report",
        "aggregate_report",
        "aggregate_report_with_csv",
        "response_time_graph",
        "jpgc_response_times_over_time",
        "jpgc_response_codes_per_second",
        "jpgc_transactions_per_second",
        "jpgc_active_threads_over_time",
        "backend_listener",
    ]
    name: Optional[str] = Field(
        None,
        description=(
            "Nombre del listener. Si None, se usa el default del kind "
            "(ej. 'View Results Tree')."
        ),
    )
    filename: Optional[str] = Field(
        None,
        description=(
            "Path del archivo de resultados (CSV/JTL) para listeners "
            "with_filename. Si None, los kinds '*_with_csv' usan su patron "
            "default; los demas quedan solo en memoria."
        ),
    )
    backend_listener_config: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Solo para backend_listener: "
            "{ 'implementation': 'org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient', "
            "'arguments': [{'name': 'influxdbUrl', 'value': '...'}] }. "
            "Si None, se usan los defaults apuntando al InfluxDB del stack Kinetix."
        ),
    )


# Union discriminada por el campo "op"
RefineOp = Union[
    UpdateTestPlanOp,
    UpdateThreadGroupOp,
    UpdateSamplerOp,
    UpdateSamplerChildOp,
    UpdateUdvsOp,
    UpdateCsvDatasetOp,
    UpdateHttpDefaultsOp,
    EnableDisableOp,
    # Sprint 2.4-HF7.A
    AddSamplerOp,
    AddSamplerChildOp,
    AddUdvOp,
    AddCsvDatasetOp,
    DeleteElementOp,
    # Sprint 2.4-HF7.B
    AddListenerOp,
]


# ----------------------------------------------------------------------------
# Respuesta de la IA
# ----------------------------------------------------------------------------


class RefineOperationSet(BaseModel):
    """Conjunto de operaciones que la IA devuelve."""

    operations: List[RefineOp] = Field(
        default_factory=list, description="Operaciones a aplicar en orden"
    )
    explanation: str = Field(
        "", description="Explicacion humana de lo que se cambio"
    )
    fallback_to_full_refine: bool = Field(
        False,
        description=(
            "Si true, el cambio requiere add/delete no soportado por el MVP "
            "— el backend usa /refine antiguo"
        ),
    )
    fallback_reason: Optional[str] = Field(
        None, description="Por que pide fallback"
    )


# ----------------------------------------------------------------------------
# Request/Response del endpoint
# ----------------------------------------------------------------------------


class RefineSurgicalRequest(BaseModel):
    current_jmx: str = Field(..., min_length=10)
    prompt: str = Field(..., min_length=1, description="Instruccion del usuario")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    file_content: Optional[str] = Field(
        None, description="Archivo de referencia opcional"
    )


class RefineSurgicalResponse(BaseModel):
    jmx_content: str = Field(
        ..., description="JMX resultante (igual o modificado)"
    )
    is_valid: bool = True
    explanation: str = ""
    operations_applied: int = 0
    fallback_used: bool = Field(
        False, description="True si se cayo al refine clasico"
    )
    fallback_reason: Optional[str] = None
    error: Optional[str] = None
