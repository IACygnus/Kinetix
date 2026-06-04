"""
Aplica un RefineOperationSet a una AIScriptStructure, marcando is_dirty=True
en los elementos modificados para que el regenerador re-construya solo lo
necesario (estrategia edit-preserving del Sprint 2.3a).

Sprint 2.4-HF5.1.
Sprint 2.4-HF5.2: kind-awareness para Thread Groups (standard vs stepping).
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.ai_script_structure import (
    AIScriptStructure,
    CSVDataSetModel,
    ConstantTimerModel,
    HeaderManagerModel,
    HeaderModel,
    HTTPSamplerModel,
    JsonExtractorModel,
    ListenerModel,
    RegexExtractorModel,
    ResponseAssertionModel,
    SamplerBody,
    SamplerChild,
    TGChild,
    UserDefinedVariable,
)
from app.schemas.refine_operations import (
    AddCsvDatasetOp,
    AddListenerOp,
    AddSamplerChildOp,
    AddSamplerOp,
    AddUdvOp,
    DeleteElementOp,
    EnableDisableOp,
    RefineOp,
    UpdateCsvDatasetOp,
    UpdateHttpDefaultsOp,
    UpdateSamplerChildOp,
    UpdateSamplerOp,
    UpdateTestPlanOp,
    UpdateThreadGroupOp,
    UpdateUdvsOp,
)

logger = logging.getLogger(__name__)


class OperationError(ValueError):
    """Raised when an operation cannot be applied (missing target, bad shape, etc.)."""


# Sprint 2.4-HF5.2 — Thread Group kind-awareness.
#
# Cuando la IA pide un campo del esquema "standard" sobre un TG stepping, lo
# redirigimos al equivalente en SteppingConfig (lo unico que el regenerator
# escribira en el XML). Y si pide un campo "stepping" sobre un TG standard,
# fallamos explicitamente para no aplicar un cambio que no se reflejara.

# Standard ThreadGroup field -> SteppingConfig equivalente
STANDARD_TO_STEPPING_FIELD_MAP = {
    "ramp_time": "ramp_up",
    # num_threads NO se redirige — en stepping vive en el ThreadGroup root igual
    # que en standard (el regenerator lo escribe en ambos caminos).
}

# Campos que SOLO existen en standard (loops vive en el LoopController del TG;
# el regenerator stepping si lo escribe, pero `continue_forever` no aplica
# semanticamente en stepping). Los redirigimos a no-op con warning.
STANDARD_ONLY_FIELDS = {"continue_forever"}

# Campos que SOLO existen en SteppingConfig. Si la IA los pide sobre un TG
# standard, lanzamos OperationError porque no hay donde aplicarlos.
STEPPING_ONLY_FIELDS = {
    "initial_delay",
    "start_users_count",
    "start_users_count_burst",
    "start_users_period",
    "ramp_up",
    "flight_time",
    "stop_users_count",
    "stop_users_period",
}


def _normalize_thread_group_fields(
    tg, fields: dict
) -> Tuple[dict, dict, List[str]]:
    """Separa campos segun su destino y el kind del TG.

    Returns:
        top_level_fields: dict de campos que van en el ThreadGroup root
            (num_threads, on_sample_error, name, comments, enabled, loops, etc.)
        stepping_fields: dict de campos que van en tg.stepping (kind=stepping solamente)
        warnings: lista de mensajes informativos (campo redirigido, ignorado, etc.)

    Reglas:
        * Si fields["stepping"] viene como dict, se merge en stepping_fields.
        * TG stepping: redirige `ramp_time` -> `stepping.ramp_up`; ignora
          STANDARD_ONLY_FIELDS con warning; resto va al root.
        * TG standard: si llegan STEPPING_ONLY_FIELDS, lanza OperationError.
    """
    top_level: dict = {}
    stepping: dict = {}
    warnings: List[str] = []

    is_stepping = tg.kind == "stepping"

    for key, value in fields.items():
        # 1) Caso preferido: la IA envia "stepping" como objeto anidado
        if key == "stepping" and isinstance(value, dict):
            for sk, sv in value.items():
                stepping[sk] = sv
            continue

        if is_stepping:
            if key in STEPPING_ONLY_FIELDS:
                stepping[key] = value
            elif key in STANDARD_TO_STEPPING_FIELD_MAP:
                target = STANDARD_TO_STEPPING_FIELD_MAP[key]
                stepping[target] = value
                warnings.append(
                    f"Campo '{key}' redirigido a 'stepping.{target}' (TG es stepping)"
                )
            elif key in STANDARD_ONLY_FIELDS:
                warnings.append(
                    f"Campo '{key}' ignorado: no aplicable a TG stepping"
                )
            else:
                # name, num_threads, on_sample_error, enabled, comments, loops
                top_level[key] = value
        else:
            # TG standard
            if key in STEPPING_ONLY_FIELDS:
                raise OperationError(
                    f"Campo '{key}' es de stepping y el TG '{tg.name}' "
                    f"es standard. Si necesitas convertirlo a stepping, "
                    f"emite fallback_to_full_refine=true."
                )
            top_level[key] = value

    return top_level, stepping, warnings


def apply_operations(
    structure: AIScriptStructure, operations: List[RefineOp]
) -> Tuple[AIScriptStructure, int]:
    """Apply each operation in order. Returns (mutated_structure, applied_count).

    The structure is mutated in place; the same instance is returned for
    callers that prefer chaining.
    """
    applied = 0
    for idx, op in enumerate(operations):
        try:
            _apply_one(structure, op)
            applied += 1
        except OperationError:
            raise
        except Exception as e:
            raise OperationError(
                f"Operacion {idx} ({getattr(op, 'op', type(op).__name__)}): {e}"
            )
    return structure, applied


def _id_matches(model_id, op_id: str) -> bool:
    """Compare a pydantic UUID field with the string id sent by the AI."""
    if model_id is None:
        return False
    return str(model_id) == str(op_id)


def _set_fields(obj, fields: dict) -> None:
    """Set attrs on a pydantic model, ignoring unknown keys; flips is_dirty."""
    for k, v in fields.items():
        if hasattr(obj, k):
            setattr(obj, k, v)
    if hasattr(obj, "is_dirty"):
        obj.is_dirty = True


def _apply_one(structure: AIScriptStructure, op: RefineOp) -> None:
    if isinstance(op, UpdateTestPlanOp):
        _set_fields(structure.test_plan, op.fields)
        return

    if isinstance(op, UpdateThreadGroupOp):
        tg = next(
            (t for t in structure.thread_groups if _id_matches(t.id, op.id)),
            None,
        )
        if not tg:
            raise OperationError(f"Thread Group con id={op.id} no encontrado")

        # Sprint 2.4-HF5.2 — separar campos por destino segun el kind del TG
        # antes de aplicar. Esto cierra el bug silencioso del HF5.1 donde la
        # IA pedia ramp_time sobre un TG stepping y el applier lo seteaba en
        # el modelo, pero el regenerator no lo escribia (el stepping XML usa
        # rampUp / ramp_up via SteppingConfig).
        top_level_fields, stepping_fields, warnings = _normalize_thread_group_fields(
            tg, dict(op.fields)
        )

        for w in warnings:
            logger.info("[refine-applier] TG '%s': %s", tg.name, w)

        # Aplicar campos del root del ThreadGroup
        if top_level_fields:
            _set_fields(tg, top_level_fields)

        # Aplicar campos del stepping (si hay)
        if stepping_fields:
            if tg.stepping is None:
                raise OperationError(
                    f"TG '{tg.name}' (kind={tg.kind}) no tiene config stepping. "
                    f"Campos {list(stepping_fields.keys())} no aplicables."
                )
            for k, v in stepping_fields.items():
                # Soporta tanto el nombre python como el alias XML ("rampUp", etc.)
                set_via_alias = False
                for field_name, field_info in tg.stepping.model_fields.items():
                    if field_info.alias == k:
                        setattr(tg.stepping, field_name, v)
                        set_via_alias = True
                        break
                if not set_via_alias:
                    if hasattr(tg.stepping, k):
                        setattr(tg.stepping, k, v)
                    else:
                        logger.info(
                            "[refine-applier] TG '%s': campo stepping.%s desconocido — ignorado",
                            tg.name, k,
                        )
            # Marcar el TG padre dirty para que el regenerator lo reconstruya
            tg.is_dirty = True
        return

    if isinstance(op, UpdateSamplerOp):
        sampler = _find_sampler(structure, op.id)
        if sampler is None:
            raise OperationError(f"Sampler con id={op.id} no encontrado")
        # Nested body: merge instead of overwriting
        if "body" in op.fields:
            body_updates = op.fields.pop("body")
            if isinstance(body_updates, dict):
                for k, v in body_updates.items():
                    if hasattr(sampler.body, k):
                        setattr(sampler.body, k, v)
        _set_fields(sampler, op.fields)
        return

    if isinstance(op, UpdateSamplerChildOp):
        sampler = _find_sampler(structure, op.sampler_id)
        if sampler is None:
            raise OperationError(
                f"Sampler padre {op.sampler_id} no encontrado"
            )
        for sc in sampler.children:
            child_id = getattr(sc.data, "id", None)
            if _id_matches(child_id, op.child_id):
                _set_fields(sc.data, op.fields)
                # Invalidate parent sampler cache so regenerator rebuilds it
                sampler.is_dirty = True
                return
        raise OperationError(
            f"Child {op.child_id} no encontrado en sampler {op.sampler_id}"
        )

    if isinstance(op, UpdateUdvsOp):
        new_udvs = []
        for u in op.udvs:
            new_udvs.append(
                UserDefinedVariable(
                    name=u.get("name", ""),
                    value=u.get("value", ""),
                    metadata=u.get("metadata", "="),
                )
            )
        structure.user_defined_variables = new_udvs
        return

    if isinstance(op, UpdateCsvDatasetOp):
        ds = next(
            (d for d in structure.csv_data_sets if _id_matches(d.id, op.id)),
            None,
        )
        if not ds:
            raise OperationError(f"CSVDataSet con id={op.id} no encontrado")
        _set_fields(ds, op.fields)
        return

    if isinstance(op, UpdateHttpDefaultsOp):
        if not structure.http_defaults:
            raise OperationError("No hay HttpDefaults para actualizar")
        _set_fields(structure.http_defaults, op.fields)
        return

    if isinstance(op, EnableDisableOp):
        _apply_enable_disable(structure, op)
        return

    # ------------------------------------------------------------------
    # Sprint 2.4-HF7.A — operaciones add/delete
    # ------------------------------------------------------------------

    if isinstance(op, AddSamplerOp):
        _apply_add_sampler(structure, op)
        return

    if isinstance(op, AddSamplerChildOp):
        _apply_add_sampler_child(structure, op)
        return

    if isinstance(op, AddUdvOp):
        _apply_add_udv(structure, op)
        return

    if isinstance(op, AddCsvDatasetOp):
        _apply_add_csv_dataset(structure, op)
        return

    if isinstance(op, DeleteElementOp):
        _apply_delete(structure, op)
        return

    # ------------------------------------------------------------------
    # Sprint 2.4-HF7.B — agregar listener
    # ------------------------------------------------------------------

    if isinstance(op, AddListenerOp):
        _apply_add_listener(structure, op)
        return

    raise OperationError(f"Operacion desconocida: {type(op).__name__}")


def _find_sampler(structure: AIScriptStructure, sampler_id: str):
    """Walk every Thread Group + nested Controllers and return the sampler by id."""

    def walk(children):
        for ch in children:
            if ch.type == "sampler" and ch.sampler is not None:
                if _id_matches(ch.sampler.id, sampler_id):
                    return ch.sampler
            elif ch.type == "controller" and ch.controller is not None:
                nested = getattr(ch.controller, "children", None) or []
                found = walk(nested)
                if found is not None:
                    return found
        return None

    for tg in structure.thread_groups:
        found = walk(tg.children)
        if found is not None:
            return found
    return None


def _apply_enable_disable(
    structure: AIScriptStructure, op: EnableDisableOp
) -> None:
    if op.target_kind == "thread_group":
        tg = next(
            (t for t in structure.thread_groups if _id_matches(t.id, op.id)),
            None,
        )
        if not tg:
            raise OperationError(f"Thread Group id={op.id} no encontrado")
        tg.enabled = op.enabled
        tg.is_dirty = True
        return

    if op.target_kind == "sampler":
        sampler = _find_sampler(structure, op.id or "")
        if sampler is None:
            raise OperationError(f"Sampler id={op.id} no encontrado")
        sampler.enabled = op.enabled
        sampler.is_dirty = True
        return

    if op.target_kind == "sampler_child":
        if not op.sampler_id:
            raise OperationError(
                "set_enabled sobre sampler_child requiere sampler_id"
            )
        sampler = _find_sampler(structure, op.sampler_id)
        if sampler is None:
            raise OperationError(
                f"Sampler padre {op.sampler_id} no encontrado"
            )
        for sc in sampler.children:
            child_id = getattr(sc.data, "id", None)
            if _id_matches(child_id, op.id):
                sc.data.enabled = op.enabled
                if hasattr(sc.data, "is_dirty"):
                    sc.data.is_dirty = True
                sampler.is_dirty = True
                return
        raise OperationError(f"Child {op.id} no encontrado")

    if op.target_kind == "csv_data_set":
        ds = next(
            (d for d in structure.csv_data_sets if _id_matches(d.id, op.id)),
            None,
        )
        if not ds:
            raise OperationError(f"CSV id={op.id} no encontrado")
        ds.enabled = op.enabled
        ds.is_dirty = True
        return

    if op.target_kind == "listener":
        li = next(
            (l for l in structure.listeners if _id_matches(l.id, op.id)),
            None,
        )
        if not li:
            raise OperationError(f"Listener id={op.id} no encontrado")
        li.enabled = op.enabled
        li.is_dirty = True
        return

    if op.target_kind == "cookie_manager":
        if not structure.cookie_manager:
            raise OperationError("No hay CookieManager en el JMX")
        structure.cookie_manager.enabled = op.enabled
        structure.cookie_manager.is_dirty = True
        return

    if op.target_kind == "cache_manager":
        if not structure.cache_manager:
            raise OperationError("No hay CacheManager en el JMX")
        structure.cache_manager.enabled = op.enabled
        structure.cache_manager.is_dirty = True
        return

    raise OperationError(
        f"target_kind {op.target_kind} no soportado en enable/disable"
    )


# ============================================================================
# Sprint 2.4-HF7.A — handlers de creacion (add_*)
# ============================================================================
#
# Los modelos Pydantic generan IDs automaticamente (UUID4) via
# `id: UUID = Field(default_factory=uuid4)`. Por eso al construir un elemento
# nuevo no pasamos `id` — Pydantic lo genera. is_dirty=True fuerza al
# regenerator a re-construir desde campos (no desde raw_xml inexistente).


def _apply_add_sampler(structure: AIScriptStructure, op: AddSamplerOp) -> None:
    tg = next(
        (t for t in structure.thread_groups if _id_matches(t.id, op.thread_group_id)),
        None,
    )
    if not tg:
        raise OperationError(
            f"Thread Group id={op.thread_group_id} no encontrado"
        )

    body_data = op.sampler.get("body", {}) or {}
    body = SamplerBody(
        mode=body_data.get("mode", "none"),
        raw_text=body_data.get("raw_text"),
        form_args=body_data.get("form_args", []) or [],
    )

    new_sampler = HTTPSamplerModel(
        name=op.sampler.get("name", "Nuevo Sampler"),
        enabled=op.sampler.get("enabled", True),
        method=op.sampler.get("method", "GET"),
        domain=op.sampler.get("domain"),
        port=op.sampler.get("port"),
        protocol=op.sampler.get("protocol"),
        path=op.sampler.get("path", "/"),
        follow_redirects=op.sampler.get("follow_redirects", True),
        auto_redirects=op.sampler.get("auto_redirects", False),
        use_keepalive=op.sampler.get("use_keepalive", True),
        content_encoding=op.sampler.get("content_encoding", "UTF-8"),
        body=body,
        children=[],
        is_dirty=True,
    )

    new_child = TGChild(
        type="sampler",
        order=len(tg.children),
        sampler=new_sampler,
        controller=None,
        unsupported=None,
    )

    if op.position is not None and 0 <= op.position <= len(tg.children):
        tg.children.insert(op.position, new_child)
    else:
        tg.children.append(new_child)

    tg.is_dirty = True


def _apply_add_sampler_child(
    structure: AIScriptStructure, op: AddSamplerChildOp
) -> None:
    sampler = _find_sampler(structure, op.sampler_id)
    if sampler is None:
        raise OperationError(f"Sampler id={op.sampler_id} no encontrado")

    data = op.data or {}
    kind = op.child_kind

    child_data: Any
    if kind == "header_manager":
        headers = data.get("headers", []) or []
        child_data = HeaderManagerModel(
            enabled=data.get("enabled", True),
            headers=[
                HeaderModel(name=h.get("name", ""), value=h.get("value", ""))
                for h in headers
            ],
            is_dirty=True,
        )
    elif kind == "response_assertion":
        child_data = ResponseAssertionModel(
            name=data.get("name", "Response Assertion"),
            enabled=data.get("enabled", True),
            test_field=data.get("test_field", "Assertion.response_code"),
            test_type=data.get("test_type", 2),
            test_strings=data.get("test_strings", ["200"]) or ["200"],
            custom_message=data.get("custom_message"),
            assume_success=data.get("assume_success", False),
            is_dirty=True,
        )
    elif kind == "regex_extractor":
        # Schema obliga refname y regex — defaults seguros si vienen vacios
        child_data = RegexExtractorModel(
            name=data.get("name", "Regex Extractor"),
            enabled=data.get("enabled", True),
            refname=data.get("refname", "var"),
            regex=data.get("regex", ""),
            template=data.get("template", "$1$"),
            match_number=str(data.get("match_number", "1")),
            default=data.get("default", "NOT_FOUND"),
            is_dirty=True,
        )
    elif kind == "json_extractor":
        child_data = JsonExtractorModel(
            name=data.get("name", "JSON Extractor"),
            enabled=data.get("enabled", True),
            refname=data.get("refname", "var"),
            json_path=data.get("json_path", "$.id"),
            match_number=str(data.get("match_number", "1")),
            default=data.get("default", "NOT_FOUND"),
            is_dirty=True,
        )
    elif kind == "constant_timer":
        child_data = ConstantTimerModel(
            name=data.get("name", "Constant Timer"),
            enabled=data.get("enabled", True),
            delay_ms=int(data.get("delay_ms", 1000)),
            is_dirty=True,
        )
    else:
        raise OperationError(f"child_kind '{kind}' no soportado")

    new_sc = SamplerChild(type=kind, order=len(sampler.children), data=child_data)
    sampler.children.append(new_sc)
    sampler.is_dirty = True


def _apply_add_udv(structure: AIScriptStructure, op: AddUdvOp) -> None:
    if any(u.name == op.name for u in structure.user_defined_variables):
        raise OperationError(f"UDV con nombre '{op.name}' ya existe")
    structure.user_defined_variables.append(
        UserDefinedVariable(
            name=op.name,
            value=op.value,
            metadata=op.metadata,
        )
    )


def _apply_add_csv_dataset(
    structure: AIScriptStructure, op: AddCsvDatasetOp
) -> None:
    data = op.data or {}
    new_csv = CSVDataSetModel(
        testname=data.get("testname", "CSV Data Set"),
        enabled=data.get("enabled", True),
        filename=data.get("filename", ""),
        file_encoding=data.get("file_encoding"),
        variable_names=data.get("variable_names", []) or [],
        delimiter=data.get("delimiter", ","),
        quoted_data=data.get("quoted_data", False),
        recycle=data.get("recycle", True),
        stop_thread=data.get("stop_thread", False),
        share_mode=data.get("share_mode", "shareMode.all"),
        ignore_first_line=data.get("ignore_first_line", False),
        is_dirty=True,
    )
    structure.csv_data_sets.append(new_csv)


# ============================================================================
# Sprint 2.4-HF7.A — handler de eliminacion
# ============================================================================


def _apply_delete(structure: AIScriptStructure, op: DeleteElementOp) -> None:
    if op.target_kind == "thread_group":
        idx = next(
            (
                i
                for i, t in enumerate(structure.thread_groups)
                if _id_matches(t.id, op.id)
            ),
            -1,
        )
        if idx == -1:
            raise OperationError(f"Thread Group id={op.id} no encontrado")
        del structure.thread_groups[idx]
        return

    if op.target_kind == "sampler":
        for tg in structure.thread_groups:
            idx = next(
                (
                    i
                    for i, ch in enumerate(tg.children)
                    if ch.type == "sampler"
                    and ch.sampler is not None
                    and _id_matches(ch.sampler.id, op.id)
                ),
                -1,
            )
            if idx != -1:
                del tg.children[idx]
                tg.is_dirty = True
                return
        raise OperationError(f"Sampler id={op.id} no encontrado")

    if op.target_kind == "sampler_child":
        if not op.sampler_id:
            raise OperationError(
                "sampler_id requerido para borrar sampler_child"
            )
        sampler = _find_sampler(structure, op.sampler_id)
        if sampler is None:
            raise OperationError(
                f"Sampler padre {op.sampler_id} no encontrado"
            )
        idx = next(
            (
                i
                for i, sc in enumerate(sampler.children)
                if _id_matches(getattr(sc.data, "id", None), op.id)
            ),
            -1,
        )
        if idx == -1:
            raise OperationError(
                f"Child id={op.id} no encontrado en sampler {op.sampler_id}"
            )
        del sampler.children[idx]
        sampler.is_dirty = True
        return

    if op.target_kind == "csv_data_set":
        idx = next(
            (
                i
                for i, d in enumerate(structure.csv_data_sets)
                if _id_matches(d.id, op.id)
            ),
            -1,
        )
        if idx == -1:
            raise OperationError(f"CSV Data Set id={op.id} no encontrado")
        del structure.csv_data_sets[idx]
        return

    if op.target_kind == "listener":
        idx = next(
            (
                i
                for i, l in enumerate(structure.listeners)
                if _id_matches(l.id, op.id)
            ),
            -1,
        )
        if idx == -1:
            raise OperationError(f"Listener id={op.id} no encontrado")
        del structure.listeners[idx]
        return

    if op.target_kind == "udv":
        if not op.udv_name:
            raise OperationError("udv_name requerido para borrar UDV")
        idx = next(
            (
                i
                for i, u in enumerate(structure.user_defined_variables)
                if u.name == op.udv_name
            ),
            -1,
        )
        if idx == -1:
            raise OperationError(f"UDV '{op.udv_name}' no encontrada")
        del structure.user_defined_variables[idx]
        return

    raise OperationError(
        f"target_kind '{op.target_kind}' no soportado para delete"
    )


# ============================================================================
# Sprint 2.4-HF7.B — listeners (5 tipos, raw_xml inicial)
# ============================================================================
#
# Estrategia (via B "raw_xml inicial"):
# El regenerator de listeners es passthrough total: si raw_xml no esta vacio
# lo usa tal cual. Construimos el raw_xml inicial aqui con el guiclass +
# testclass correctos + SaveConfig completo para ResultCollectors, y con
# BackendListener + arguments InfluxDB para el quinto tipo.
#
# Esto cubre los dos casos en los que el regenerador "minimalista" falla:
#  - SaveConfig de ResultCollectors (sin el, JMeter no guarda metricas utiles).
#  - BackendListener no es un ResultCollector — necesita su propia estructura.
#
# Mapeo a ListenerKind del schema (que NO conoce response_time_graph ni
# backend_listener) — para esos dos usamos kind="other" + guiclass nativo,
# el regenerator los respeta porque solo usa raw_xml.

LISTENER_KIND_DEFAULTS = {
    # --- ResultCollectors estandar ---
    "view_results_tree": {
        "guiclass": "ViewResultsFullVisualizer",
        "testclass": "ResultCollector",
        "name_default": "View Results Tree",
        "schema_kind": "view_results_tree",
    },
    "view_results_tree_with_csv": {
        "guiclass": "ViewResultsFullVisualizer",
        "testclass": "ResultCollector",
        "name_default": "View Results Tree (errors + CSV)",
        "schema_kind": "view_results_tree",
        "with_filename": True,
        "default_filename_pattern": "resultados_log_${__time(d-MMM-yyyy)}-${__time(HHmmss)}.csv",
    },
    "summary_report": {
        "guiclass": "SummaryReport",
        "testclass": "ResultCollector",
        "name_default": "Summary Report",
        "schema_kind": "summary_report",
    },
    "aggregate_report": {
        "guiclass": "StatVisualizer",
        "testclass": "ResultCollector",
        "name_default": "Informe Agregado",
        "schema_kind": "aggregate_report",
    },
    "aggregate_report_with_csv": {
        "guiclass": "StatVisualizer",
        "testclass": "ResultCollector",
        "name_default": "Informe Agregado (con CSV)",
        "schema_kind": "aggregate_report",
        "with_filename": True,
        "default_filename_pattern": "resultados_general_${__time(d-MMM-yyyy)}-${__time(HHmmss)}.jtl",
    },
    "response_time_graph": {
        "guiclass": "RespTimeGraphVisualizer",
        "testclass": "ResultCollector",
        "name_default": "Response Time Graph",
        # No esta en ListenerKind del schema — passthrough via "other"
        "schema_kind": "other",
    },
    # --- jp@gc graficas (kg.apc.jmeter.vizualizers.CorrectedResultCollector) ---
    "jpgc_response_times_over_time": {
        "guiclass": "kg.apc.jmeter.vizualizers.ResponseTimesOverTimeGui",
        "testclass": "kg.apc.jmeter.vizualizers.CorrectedResultCollector",
        "name_default": "jp@gc - Response Times Over Time",
        "schema_kind": "kg_apc_response_times_over_time",
        "interval_grouping": 500,
    },
    "jpgc_response_codes_per_second": {
        "guiclass": "kg.apc.jmeter.vizualizers.ResponseCodesPerSecondGui",
        "testclass": "kg.apc.jmeter.vizualizers.CorrectedResultCollector",
        "name_default": "jp@gc - Response Codes per Second",
        "schema_kind": "kg_apc_response_codes_per_second",
        "interval_grouping": 1000,
    },
    "jpgc_transactions_per_second": {
        "guiclass": "kg.apc.jmeter.vizualizers.TransactionsPerSecondGui",
        "testclass": "kg.apc.jmeter.vizualizers.CorrectedResultCollector",
        "name_default": "jp@gc - Transactions per Second",
        "schema_kind": "kg_apc_transactions_per_second",
        "interval_grouping": 1000,
    },
    "jpgc_active_threads_over_time": {
        "guiclass": "kg.apc.jmeter.vizualizers.ThreadsStateOverTimeGui",
        "testclass": "kg.apc.jmeter.vizualizers.CorrectedResultCollector",
        "name_default": "jp@gc - Active Threads Over Time",
        "schema_kind": "kg_apc_active_threads_over_time",
        "interval_grouping": 1000,
    },
    # --- Backend Listener (existente) ---
    "backend_listener": {
        "guiclass": "BackendListenerGui",
        "testclass": "BackendListener",
        "name_default": "Backend Listener (InfluxDB)",
        # BackendListener no es ResultCollector — siempre "other"
        "schema_kind": "other",
    },
}

# Backend Listener defaults — apuntan al InfluxDB del stack Kinetix
# (containers `jmeter_influxdb` con bucket `jmeter`, org `performance`,
# token `jmeter-token-2024-super-secret` definidos en CLAUDE.md).
DEFAULT_BACKEND_LISTENER_IMPL = (
    "org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient"
)
DEFAULT_BACKEND_LISTENER_ARGS = [
    {
        "name": "influxdbMetricsSender",
        "value": "org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender",
    },
    {
        "name": "influxdbUrl",
        "value": "http://influxdb:8086/api/v2/write?org=performance&bucket=jmeter&precision=ms",
    },
    {"name": "application", "value": "${__P(application,Kinetix Test)}"},
    {"name": "measurement", "value": "jmeter"},
    {"name": "summaryOnly", "value": "false"},
    {"name": "samplersRegex", "value": ".*"},
    {"name": "percentiles", "value": "90;95;99"},
    {"name": "testTitle", "value": "Test name"},
    {"name": "eventTags", "value": ""},
    {"name": "TOKEN", "value": "jmeter-token-2024-super-secret"},
]


def _xml_escape(value: str) -> str:
    """Mini XML-escape para los pocos lugares donde inyectamos texto del usuario."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _result_collector_raw_xml(guiclass: str, name: str, filename: str = "") -> str:
    """Construye un <ResultCollector> con SaveConfig completo.

    Los SaveConfig booleans aqui replican los defaults estandar de JMeter
    5.6.3 — todos los metadatos importantes habilitados para que el listener
    sea util en ejecucion real.

    ``filename`` permite los listeners "with_csv" (View Results Tree / Informe
    Agregado que persisten a CSV/JTL). Vacio = listener solo en memoria.
    """
    name_esc = _xml_escape(name)
    filename_esc = _xml_escape(filename)
    return (
        f'<ResultCollector guiclass="{guiclass}" testclass="ResultCollector" '
        f'testname="{name_esc}" enabled="true">\n'
        '  <boolProp name="ResultCollector.error_logging">false</boolProp>\n'
        "  <objProp>\n"
        "    <name>saveConfig</name>\n"
        '    <value class="SampleSaveConfiguration">\n'
        "      <time>true</time>\n"
        "      <latency>true</latency>\n"
        "      <timestamp>true</timestamp>\n"
        "      <success>true</success>\n"
        "      <label>true</label>\n"
        "      <code>true</code>\n"
        "      <message>true</message>\n"
        "      <threadName>true</threadName>\n"
        "      <dataType>true</dataType>\n"
        "      <encoding>false</encoding>\n"
        "      <assertions>true</assertions>\n"
        "      <subresults>true</subresults>\n"
        "      <responseData>false</responseData>\n"
        "      <samplerData>false</samplerData>\n"
        "      <xml>false</xml>\n"
        "      <fieldNames>true</fieldNames>\n"
        "      <responseHeaders>false</responseHeaders>\n"
        "      <requestHeaders>false</requestHeaders>\n"
        "      <responseDataOnError>false</responseDataOnError>\n"
        "      <saveAssertionResultsFailureMessage>true</saveAssertionResultsFailureMessage>\n"
        "      <assertionsResultsToSave>0</assertionsResultsToSave>\n"
        "      <bytes>true</bytes>\n"
        "      <sentBytes>true</sentBytes>\n"
        "      <url>true</url>\n"
        "      <threadCounts>true</threadCounts>\n"
        "      <idleTime>true</idleTime>\n"
        "      <connectTime>true</connectTime>\n"
        "    </value>\n"
        "  </objProp>\n"
        f'  <stringProp name="filename">{filename_esc}</stringProp>\n'
        "</ResultCollector>"
    )


def _corrected_result_collector_raw_xml(
    guiclass: str, name: str, interval: int, filename: str = ""
) -> str:
    """Construye un <kg.apc.jmeter.vizualizers.CorrectedResultCollector> para
    las graficas jp@gc (plugin JMeterPlugins). Replica el SaveConfig estandar
    mas los props especificos de las graficas (interval_grouping, etc.).
    """
    name_esc = _xml_escape(name)
    filename_esc = _xml_escape(filename)
    return (
        f'<kg.apc.jmeter.vizualizers.CorrectedResultCollector guiclass="{guiclass}" '
        f'testclass="kg.apc.jmeter.vizualizers.CorrectedResultCollector" '
        f'testname="{name_esc}" enabled="true">\n'
        '  <boolProp name="ResultCollector.error_logging">false</boolProp>\n'
        "  <objProp>\n"
        "    <name>saveConfig</name>\n"
        '    <value class="SampleSaveConfiguration">\n'
        "      <time>true</time>\n"
        "      <latency>true</latency>\n"
        "      <timestamp>true</timestamp>\n"
        "      <success>true</success>\n"
        "      <label>true</label>\n"
        "      <code>true</code>\n"
        "      <message>true</message>\n"
        "      <threadName>true</threadName>\n"
        "      <dataType>true</dataType>\n"
        "      <encoding>false</encoding>\n"
        "      <assertions>true</assertions>\n"
        "      <subresults>true</subresults>\n"
        "      <responseData>false</responseData>\n"
        "      <samplerData>false</samplerData>\n"
        "      <xml>false</xml>\n"
        "      <fieldNames>true</fieldNames>\n"
        "      <responseHeaders>false</responseHeaders>\n"
        "      <requestHeaders>false</requestHeaders>\n"
        "      <responseDataOnError>false</responseDataOnError>\n"
        "      <saveAssertionResultsFailureMessage>true</saveAssertionResultsFailureMessage>\n"
        "      <assertionsResultsToSave>0</assertionsResultsToSave>\n"
        "      <bytes>true</bytes>\n"
        "      <sentBytes>true</sentBytes>\n"
        "      <url>true</url>\n"
        "      <threadCounts>true</threadCounts>\n"
        "      <idleTime>true</idleTime>\n"
        "      <connectTime>true</connectTime>\n"
        "    </value>\n"
        "  </objProp>\n"
        f'  <stringProp name="filename">{filename_esc}</stringProp>\n'
        f'  <longProp name="interval_grouping">{int(interval)}</longProp>\n'
        '  <boolProp name="graph_aggregated">false</boolProp>\n'
        '  <stringProp name="include_sample_labels"></stringProp>\n'
        '  <stringProp name="exclude_sample_labels"></stringProp>\n'
        '  <stringProp name="start_offset"></stringProp>\n'
        '  <stringProp name="end_offset"></stringProp>\n'
        '  <boolProp name="include_checkbox_state">false</boolProp>\n'
        '  <boolProp name="exclude_checkbox_state">false</boolProp>\n'
        "</kg.apc.jmeter.vizualizers.CorrectedResultCollector>"
    )


def _backend_listener_raw_xml(
    name: str,
    implementation: str,
    arguments: List[Dict[str, str]],
) -> str:
    """Construye un <BackendListener> con argumentos InfluxDB."""
    name_esc = _xml_escape(name)
    impl_esc = _xml_escape(implementation)
    args_xml_lines: List[str] = []
    for a in arguments:
        arg_name = _xml_escape(a.get("name", ""))
        arg_value = _xml_escape(a.get("value", ""))
        args_xml_lines.append(
            f'          <elementProp name="{arg_name}" elementType="Argument">\n'
            f'            <stringProp name="Argument.name">{arg_name}</stringProp>\n'
            f'            <stringProp name="Argument.value">{arg_value}</stringProp>\n'
            f'            <stringProp name="Argument.metadata">=</stringProp>\n'
            f"          </elementProp>"
        )
    args_xml = "\n".join(args_xml_lines)
    return (
        f'<BackendListener guiclass="BackendListenerGui" testclass="BackendListener" '
        f'testname="{name_esc}" enabled="true">\n'
        '  <elementProp name="arguments" elementType="Arguments" guiclass="ArgumentsPanel" '
        'testclass="Arguments" testname="User Defined Variables" enabled="true">\n'
        '    <collectionProp name="Arguments.arguments">\n'
        f"{args_xml}\n"
        "    </collectionProp>\n"
        "  </elementProp>\n"
        f'  <stringProp name="classname">{impl_esc}</stringProp>\n'
        "</BackendListener>"
    )


def _build_listener_raw_xml(
    kind: str,
    name: str,
    backend_config: Optional[Dict[str, Any]] = None,
    filename: str = "",
) -> str:
    """Despacha la construccion del raw_xml inicial segun el listener_kind."""
    if kind == "backend_listener":
        cfg = backend_config or {}
        impl = cfg.get("implementation", DEFAULT_BACKEND_LISTENER_IMPL)
        args = cfg.get("arguments", DEFAULT_BACKEND_LISTENER_ARGS)
        return _backend_listener_raw_xml(name, impl, args)

    defaults = LISTENER_KIND_DEFAULTS.get(kind)
    if not defaults:
        raise OperationError(f"listener_kind '{kind}' no soportado")

    # Graficas jp@gc → CorrectedResultCollector
    if kind.startswith("jpgc_"):
        return _corrected_result_collector_raw_xml(
            defaults["guiclass"],
            name,
            defaults.get("interval_grouping", 1000),
            filename,
        )

    # ResultCollector estandar (con filename opcional para los "with_csv")
    return _result_collector_raw_xml(defaults["guiclass"], name, filename)


def _resolve_listener_filename(op: AddListenerOp, defaults: Dict[str, Any]) -> str:
    """Resuelve el filename del listener: el de la op si viene, si no el
    default pattern del kind (solo aplica a kinds 'with_filename')."""
    if getattr(op, "filename", None):
        return op.filename  # type: ignore[return-value]
    if defaults.get("with_filename"):
        return defaults.get("default_filename_pattern", "")
    return ""


def _apply_add_listener(
    structure: AIScriptStructure, op: AddListenerOp
) -> None:
    defaults = LISTENER_KIND_DEFAULTS.get(op.listener_kind)
    if not defaults:
        raise OperationError(
            f"listener_kind '{op.listener_kind}' no soportado"
        )

    listener_name = (op.name or defaults["name_default"]).strip()
    if not listener_name:
        listener_name = defaults["name_default"]

    filename = _resolve_listener_filename(op, defaults)

    raw_xml = _build_listener_raw_xml(
        op.listener_kind, listener_name, op.backend_listener_config, filename
    )

    new_listener = ListenerModel(
        kind=defaults["schema_kind"],  # type: ignore[arg-type]
        guiclass=defaults["guiclass"],
        name=listener_name,
        enabled=True,
        filename=filename or None,
        raw_xml=raw_xml,
        # is_dirty=False: el regenerator usa raw_xml directamente.
        is_dirty=False,
    )
    structure.listeners.append(new_listener)


# Optional ya esta importado arriba — solo aseguramos `List` y `Dict` para
# las firmas de los helpers de raw_xml.
# (Los imports `List` y `Dict` ya vienen via typing arriba.)
