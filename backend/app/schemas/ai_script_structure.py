"""
Schemas Pydantic para AIScriptStructure.

Representación intermedia editable de un JMX. NO se persiste en DB:
se deriva on-demand del current_jmx con el parser del Sprint 2.1.

Modelo basado en análisis real de sample_jmx/Ejercicio_Booking.jmx.

Sprint 2.3a: campo `is_dirty: bool = False` añadido a 24 modelos para
habilitar la estrategia edit-preserving del regenerador
(`structure_to_jmx.regenerate_jmx_from_structure`).
"""
from typing import List, Optional, Literal, Union, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Configuración base — habilita aliases con espacios (ej. "Start users count")
# ============================================================================

class JMXBase(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,         # acepta tanto field name como alias
        extra='allow',                  # passthrough de campos no contemplados
    )


# ============================================================================
# Test Plan (raíz)
# ============================================================================

class TestPlanModel(JMXBase):
    name: str = "Test Plan"
    functional_mode: bool = False
    serialize_threadgroups: bool = False
    tearDown_on_shutdown: bool = True
    comments: Optional[str] = None
    is_dirty: bool = False


# ============================================================================
# Variables top-level (Arguments / UserDefinedVariables)
# ============================================================================

class UserDefinedVariable(JMXBase):
    name: str
    value: str
    metadata: str = "="
    description: Optional[str] = None
    is_dirty: bool = False


# ============================================================================
# HTTP Defaults
# ============================================================================

class HttpDefaultsModel(JMXBase):
    domain: Optional[str] = None
    protocol: Optional[str] = None
    port: Optional[str] = None
    path: Optional[str] = None
    implementation: Optional[str] = None
    encoding: Optional[str] = None
    is_dirty: bool = False


# ============================================================================
# Cookie / Cache Manager
# ============================================================================

class CookieManagerModel(JMXBase):
    enabled: bool = True
    clear_each_iteration: bool = False
    policy: Optional[str] = None
    is_dirty: bool = False


class CacheManagerModel(JMXBase):
    enabled: bool = True
    clear_each_iteration: bool = False
    use_expires: bool = True
    is_dirty: bool = False


# ============================================================================
# CSV Data Sets
# ============================================================================

class CSVDataSetModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    testname: str
    enabled: bool = True
    filename: str
    variable_names: List[str] = []
    delimiter: str = ","
    ignore_first_line: bool = False
    quoted_data: bool = False
    recycle: bool = True
    share_mode: Literal["shareMode.all", "shareMode.group", "shareMode.thread"] = "shareMode.all"
    stop_thread: bool = False
    file_encoding: Optional[str] = None
    is_dirty: bool = False


# ============================================================================
# Stepping Thread Group config (subobjeto opcional)
# Nombres con espacios via alias — preserva fidelidad del XML kg.apc
# ============================================================================

class SteppingConfig(JMXBase):
    initial_delay: int = Field(default=0, alias="Threads initial delay")
    start_users_count: int = Field(default=1, alias="Start users count")
    start_users_count_burst: int = Field(default=0, alias="Start users count burst")
    start_users_period: int = Field(default=30, alias="Start users period")
    stop_users_count: int = Field(default=1, alias="Stop users count")
    stop_users_period: int = Field(default=5, alias="Stop users period")
    ramp_up: int = Field(default=5, alias="rampUp")
    flight_time: int = Field(default=60, alias="flighttime")


# ============================================================================
# Sampler children — modelos discriminados por 'type'
# ============================================================================

class HeaderModel(JMXBase):
    name: str
    value: str


class HeaderManagerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    headers: List[HeaderModel] = []
    is_dirty: bool = False


class ResponseAssertionModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    name: str = "Response Assertion"
    test_field: str = "Assertion.response_data"  # response_data | response_code | response_headers | response_message
    test_type: int = 2                            # bitmask: 1=matches, 2=contains, 4=not, 8=equals, 16=substring
    test_strings: List[str] = []
    custom_message: Optional[str] = None
    assume_success: bool = False
    # Flags derivados (computed) — NO se serializan al JMX, son para UI:
    negate: bool = False                          # set true si bit 4 está activo en test_type
    pattern_match: Literal["contains", "matches", "equals", "substring"] = "contains"
    is_dirty: bool = False


class RegexExtractorModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    name: str = "Regex Extractor"
    refname: str
    regex: str
    template: str = "$1$"
    match_number: str = "1"
    default: str = ""
    default_empty_value: bool = False
    use_headers: Literal["false", "true", "URL", "code", "message"] = "false"
    scope: Optional[Literal["all", "parent", "children"]] = None
    extract_from: Literal["body", "header", "url", "code", "message"] = "body"  # derivado de use_headers
    is_dirty: bool = False


class JsonExtractorModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    name: str = "JSON Extractor"
    refname: str
    json_path: str
    match_number: str = "1"
    default: str = ""
    is_dirty: bool = False


class XPathExtractorModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    name: str = "XPath Extractor"
    refname: str
    xpath: str
    default: str = ""
    is_dirty: bool = False


class BoundaryExtractorModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    name: str = "Boundary Extractor"
    refname: str
    left_boundary: str
    right_boundary: str
    match_number: str = "1"
    default: str = ""
    is_dirty: bool = False


class ConstantTimerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    name: str = "Constant Timer"
    delay_ms: int = 0
    is_dirty: bool = False


class UniformRandomTimerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    name: str = "Uniform Random Timer"
    constant_delay_ms: int = 0
    random_delay_ms: int = 100
    is_dirty: bool = False


class GaussianRandomTimerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    enabled: bool = True
    name: str = "Gaussian Random Timer"
    constant_delay_ms: int = 0
    deviation_ms: int = 100
    is_dirty: bool = False


# ============================================================================
# HTTP Sampler body
# ============================================================================

class FormArgument(JMXBase):
    name: str
    value: str
    always_encode: bool = False
    use_equals: bool = True
    metadata: str = "="


class SamplerBody(JMXBase):
    mode: Literal["raw", "form", "none"] = "none"
    raw_text: Optional[str] = None
    form_args: List[FormArgument] = []
    body_type: Literal["json", "xml", "form", "raw", "auto"] = "auto"  # heurística según Content-Type


# ============================================================================
# Sampler child wrapper (discriminado por 'type')
# ============================================================================

SamplerChildType = Literal[
    "header_manager",
    "response_assertion",
    "regex_extractor",
    "json_extractor",
    "xpath_extractor",
    "boundary_extractor",
    "constant_timer",
    "uniform_random_timer",
    "gaussian_random_timer",
    "unsupported",
]


class UnsupportedElement(JMXBase):
    """Passthrough para elementos no soportados — preserva raw_xml + warning."""
    id: UUID = Field(default_factory=uuid4)
    type: Literal["unsupported"] = "unsupported"
    kind: str                                    # ej. "JSR223PreProcessor"
    name: Optional[str] = None
    reason: str                                  # ej. "PreProcessor JSR223 no editable visualmente"
    severity: Literal["warning", "info"] = "warning"
    raw_xml: str                                 # bloque XML original para round-trip
    parent_sampler_id: Optional[UUID] = None


class SamplerChild(JMXBase):
    """
    Wrapper discriminado por 'type'. El campo 'data' contiene el modelo concreto.
    Esto permite preservar el ORDEN de los children, que JMeter usa
    semánticamente (ej. extractor antes que assertion = el assertion
    puede usar la variable extraída).
    """
    type: SamplerChildType
    order: int                                   # posición en el hashTree
    data: Union[
        HeaderManagerModel,
        ResponseAssertionModel,
        RegexExtractorModel,
        JsonExtractorModel,
        XPathExtractorModel,
        BoundaryExtractorModel,
        ConstantTimerModel,
        UniformRandomTimerModel,
        GaussianRandomTimerModel,
        UnsupportedElement,
    ]


# ============================================================================
# HTTP Sampler
# ============================================================================

class HTTPSamplerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["sampler"] = "sampler"
    enabled: bool = True
    name: str
    method: str = "GET"                          # GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS
    protocol: Optional[str] = None
    domain: Optional[str] = None
    port: Optional[str] = None
    path: str = ""
    content_encoding: str = "UTF-8"
    follow_redirects: bool = True
    use_keepalive: bool = True
    auto_redirects: bool = False
    body: SamplerBody = Field(default_factory=SamplerBody)
    children: List[SamplerChild] = []            # orden preservado
    raw_xml: str = ""                            # backup completo del sampler para round-trip
    is_dirty: bool = False


# ============================================================================
# Controllers (Top 5 — GenericController, LoopController, IfController,
# WhileController, ThroughputController). ForEach queda v2.
# ============================================================================

ControllerType = Literal[
    "generic_controller",
    "loop_controller",
    "if_controller",
    "while_controller",
    "throughput_controller",
]


class GenericControllerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["controller"] = "controller"
    kind: Literal["generic_controller"] = "generic_controller"
    enabled: bool = True
    name: str
    children: List["TGChild"] = []
    is_dirty: bool = False


class LoopControllerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["controller"] = "controller"
    kind: Literal["loop_controller"] = "loop_controller"
    enabled: bool = True
    name: str
    loops: int = 1
    continue_forever: bool = False
    children: List["TGChild"] = []
    is_dirty: bool = False


class IfControllerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["controller"] = "controller"
    kind: Literal["if_controller"] = "if_controller"
    enabled: bool = True
    name: str
    condition: str
    use_expression: bool = True
    evaluate_all: bool = False
    children: List["TGChild"] = []
    is_dirty: bool = False


class WhileControllerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["controller"] = "controller"
    kind: Literal["while_controller"] = "while_controller"
    enabled: bool = True
    name: str
    condition: str
    children: List["TGChild"] = []
    is_dirty: bool = False


class ThroughputControllerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["controller"] = "controller"
    kind: Literal["throughput_controller"] = "throughput_controller"
    enabled: bool = True
    name: str
    style: int = 0                               # 0=percent, 1=total
    percent_throughput: str = "100.0"
    per_thread: bool = False
    children: List["TGChild"] = []
    is_dirty: bool = False


# Union de Controllers
ControllerUnion = Union[
    GenericControllerModel,
    LoopControllerModel,
    IfControllerModel,
    WhileControllerModel,
    ThroughputControllerModel,
]


# ============================================================================
# Thread Group child — discriminado por 'type'
# ============================================================================

class TGChild(JMXBase):
    """
    Hijo de Thread Group o Controller. Puede ser sampler, controller anidado,
    o elemento no soportado. Discriminado por 'type'.
    """
    type: Literal["sampler", "controller", "unsupported"]
    order: int
    sampler: Optional[HTTPSamplerModel] = None
    controller: Optional[ControllerUnion] = None
    unsupported: Optional[UnsupportedElement] = None


# Forward refs para self-referencing controllers
GenericControllerModel.model_rebuild()
LoopControllerModel.model_rebuild()
IfControllerModel.model_rebuild()
WhileControllerModel.model_rebuild()
ThroughputControllerModel.model_rebuild()


# ============================================================================
# Thread Group
# ============================================================================

class ThreadGroupModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    kind: Literal["standard", "stepping", "concurrency", "ultimate"] = "standard"
    name: str = "Thread Group"
    enabled: bool = True                         # crítico: smoke vs carga se distingue por enabled
    comments: Optional[str] = None
    on_sample_error: Literal[
        "continue", "startnextloop", "stopthread", "stoptest", "stoptestnow"
    ] = "continue"
    num_threads: int = 1
    ramp_time: int = 1
    duration: Optional[int] = None
    delay: Optional[int] = None
    scheduler: bool = False
    loops: int = 1
    continue_forever: bool = False
    stepping: Optional[SteppingConfig] = None    # solo si kind == "stepping"
    children: List[TGChild] = []                 # samplers + controllers en orden
    raw_xml: str = ""                            # backup completo
    is_dirty: bool = False


# ============================================================================
# Config elements (top-level: CookieManager, CacheManager, AuthManager, etc.)
# ============================================================================

ConfigElementKind = Literal[
    "cookie_manager",
    "cache_manager",
    "auth_manager",
    "dns_cache_manager",
    "keystore_config",
    "other",
]


class ConfigElementModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    kind: ConfigElementKind
    name: str
    enabled: bool = True
    properties: Dict[str, Any] = {}
    raw_xml: str = ""
    is_dirty: bool = False


# ============================================================================
# Listeners (incluye kg.apc family + estándar)
# ============================================================================

ListenerKind = Literal[
    "view_results_tree",
    "summary_report",
    "aggregate_report",
    "graph_results",
    "kg_apc_response_times_over_time",
    "kg_apc_response_codes_per_second",
    "kg_apc_transactions_per_second",
    "kg_apc_active_threads_over_time",
    "kg_apc_hits_per_second",
    "other",
]


class ListenerModel(JMXBase):
    id: UUID = Field(default_factory=uuid4)
    kind: ListenerKind
    guiclass: str                                # guiclass original ("ViewResultsFullVisualizer" etc.)
    name: str
    enabled: bool = True
    filename: Optional[str] = None
    raw_xml: str = ""                            # passthrough — save_config props internas
    is_dirty: bool = False


# ============================================================================
# Metadata derivada (calculada por el parser)
# ============================================================================

class StructureMetadata(JMXBase):
    jmx_version: str = "5.6.3"
    parsed_at: datetime = Field(default_factory=datetime.utcnow)
    referenced_variables: List[str] = []         # ${var} encontradas en cualquier sampler
    defined_variables: List[str] = []            # union de UDV + CSV columns + extractor refnames
    undefined_variables: List[str] = []          # referenced - defined → warning crítico
    has_unmapped: bool = False
    unmapped_count: int = 0
    parse_warnings: List[str] = []               # warnings no fatales del parser


# ============================================================================
# Modelo raíz: AIScriptStructure
# ============================================================================

class AIScriptStructure(JMXBase):
    """
    Representación intermedia editable de un JMX completo.
    Se deriva on-demand desde current_jmx (no se persiste en DB).
    """
    test_plan: TestPlanModel = Field(default_factory=TestPlanModel)
    user_defined_variables: List[UserDefinedVariable] = []
    http_defaults: Optional[HttpDefaultsModel] = None
    cookie_manager: Optional[CookieManagerModel] = None
    cache_manager: Optional[CacheManagerModel] = None
    csv_data_sets: List[CSVDataSetModel] = []
    thread_groups: List[ThreadGroupModel] = []
    config_elements: List[ConfigElementModel] = []   # otros que no caben en cookie/cache
    listeners: List[ListenerModel] = []
    unmapped: List[UnsupportedElement] = []          # elementos top-level no soportados
    metadata: StructureMetadata = Field(default_factory=StructureMetadata)
