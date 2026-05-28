"""
Regenerador AIScriptStructure → JMX.

Estrategia "edit-preserving":
- Elementos con is_dirty=False: reusan el raw_xml original (preservación 100% fiel).
- Elementos con is_dirty=True: se re-construyen desde los campos del modelo.

Si el modelo no tiene is_dirty (legacy), se asume dirty=True por seguridad.

Para elementos con children (TG, Sampler, Controllers), si is_dirty=False
PERO algún descendiente está dirty, hay que re-construir el wrapper para
reflejar los cambios. Resolución: re-construir.
"""
from typing import Any, List, Optional
from lxml import etree

from app.schemas.ai_script_structure import (
    AIScriptStructure,
    TestPlanModel,
    UserDefinedVariable,
    HttpDefaultsModel,
    CookieManagerModel,
    CacheManagerModel,
    CSVDataSetModel,
    ThreadGroupModel,
    SteppingConfig,
    HTTPSamplerModel,
    SamplerBody,
    FormArgument,
    SamplerChild,
    HeaderManagerModel,
    HeaderModel,
    ResponseAssertionModel,
    RegexExtractorModel,
    JsonExtractorModel,
    XPathExtractorModel,
    BoundaryExtractorModel,
    ConstantTimerModel,
    UniformRandomTimerModel,
    GaussianRandomTimerModel,
    UnsupportedElement,
    GenericControllerModel,
    LoopControllerModel,
    IfControllerModel,
    WhileControllerModel,
    ThroughputControllerModel,
    TGChild,
    ConfigElementModel,
    ListenerModel,
)


# ============================================================================
# Helpers de construcción XML
# ============================================================================

def _string_prop(parent, name: str, value: Any) -> None:
    """Añade un <stringProp name='X'>value</stringProp> al parent."""
    el = etree.SubElement(parent, "stringProp")
    el.set("name", name)
    el.text = str(value) if value is not None else ""


def _bool_prop(parent, name: str, value: bool) -> None:
    el = etree.SubElement(parent, "boolProp")
    el.set("name", name)
    el.text = "true" if value else "false"


def _int_prop(parent, name: str, value: int) -> None:
    el = etree.SubElement(parent, "intProp")
    el.set("name", name)
    el.text = str(value)


def _empty_hash_tree(parent) -> etree.Element:
    """Añade un <hashTree/> vacío al parent y lo retorna."""
    return etree.SubElement(parent, "hashTree")


def _has_dirty_descendant(model: Any) -> bool:
    """
    Recursivamente verifica si algún descendiente del modelo está dirty.
    Si un elemento contenedor (TG, Sampler, Controller) tiene un hijo dirty,
    debe reconstruirse para reflejar el cambio.
    """
    if model is None:
        return False

    children = getattr(model, "children", None)
    if children:
        for child in children:
            # SamplerChild / TGChild son wrappers — el dirty está en .data o en .sampler/.controller
            inner = None
            if hasattr(child, "data"):
                inner = child.data
            elif hasattr(child, "sampler") and child.sampler is not None:
                inner = child.sampler
            elif hasattr(child, "controller") and child.controller is not None:
                inner = child.controller

            if inner is not None:
                if getattr(inner, "is_dirty", False):
                    return True
                if _has_dirty_descendant(inner):
                    return True

    return False


def _should_reuse_raw_xml(model: Any) -> bool:
    """
    Decide si un elemento puede reusar su raw_xml.
    Reusa solo si:
    - is_dirty es False
    - Ningún descendiente está dirty
    - raw_xml existe y no está vacío
    """
    if getattr(model, "is_dirty", True):  # si no tiene is_dirty, asumir dirty
        return False
    if _has_dirty_descendant(model):
        return False
    raw = getattr(model, "raw_xml", None)
    if not raw or len(raw.strip()) == 0:
        return False
    return True


def _inject_raw_xml(parent, raw_xml: str) -> etree.Element:
    """
    Inserta un raw_xml (string) como child del parent, preservando estructura.
    Retorna el elemento inyectado.
    """
    parsed = etree.fromstring(raw_xml.encode("utf-8"))
    parent.append(parsed)
    return parsed


# ============================================================================
# Serializadores específicos
# ============================================================================

def _serialize_test_plan(plan: TestPlanModel) -> etree.Element:
    raw = getattr(plan, "raw_xml", None)
    if _should_reuse_raw_xml(plan) and raw:
        return etree.fromstring(raw.encode("utf-8"))
    return _build_test_plan(plan)


def _build_test_plan(plan: TestPlanModel) -> etree.Element:
    tp = etree.Element("TestPlan")
    tp.set("guiclass", "TestPlanGui")
    tp.set("testclass", "TestPlan")
    tp.set("testname", plan.name or "Test Plan")
    tp.set("enabled", "true")

    _string_prop(tp, "TestPlan.comments", plan.comments or "")
    _bool_prop(tp, "TestPlan.functional_mode", plan.functional_mode)
    _bool_prop(tp, "TestPlan.tearDown_on_shutdown", plan.tearDown_on_shutdown)
    _bool_prop(tp, "TestPlan.serialize_threadgroups", plan.serialize_threadgroups)

    # UDV inline (vacío por convención — los UDV reales van en Arguments hermano)
    udv = etree.SubElement(tp, "elementProp")
    udv.set("name", "TestPlan.user_defined_variables")
    udv.set("elementType", "Arguments")
    udv.set("guiclass", "ArgumentsPanel")
    udv.set("testclass", "Arguments")
    udv.set("testname", "User Defined Variables")
    coll = etree.SubElement(udv, "collectionProp")
    coll.set("name", "Arguments.arguments")

    _string_prop(tp, "TestPlan.user_define_classpath", "")
    return tp


def _serialize_arguments_top_level(udvs: List[UserDefinedVariable]) -> etree.Element:
    """Construye el <Arguments> top-level con todos los UDV."""
    args = etree.Element("Arguments")
    args.set("guiclass", "ArgumentsPanel")
    args.set("testclass", "Arguments")
    args.set("testname", "User Defined Variables")
    args.set("enabled", "true")

    coll = etree.SubElement(args, "collectionProp")
    coll.set("name", "Arguments.arguments")

    for udv in udvs:
        ep = etree.SubElement(coll, "elementProp")
        ep.set("name", udv.name)
        ep.set("elementType", "Argument")
        _string_prop(ep, "Argument.name", udv.name)
        _string_prop(ep, "Argument.value", udv.value)
        _string_prop(ep, "Argument.metadata", udv.metadata or "=")

    return args


def _serialize_http_defaults(hd: HttpDefaultsModel) -> etree.Element:
    raw = getattr(hd, "raw_xml", None)
    if _should_reuse_raw_xml(hd) and raw:
        return etree.fromstring(raw.encode("utf-8"))
    return _build_http_defaults(hd)


def _build_http_defaults(hd: HttpDefaultsModel) -> etree.Element:
    cfg = etree.Element("ConfigTestElement")
    cfg.set("guiclass", "HttpDefaultsGui")
    cfg.set("testclass", "ConfigTestElement")
    cfg.set("testname", "HTTP Request Defaults")
    cfg.set("enabled", "true")

    args = etree.SubElement(cfg, "elementProp")
    args.set("name", "HTTPsampler.Arguments")
    args.set("elementType", "Arguments")
    args.set("guiclass", "HTTPArgumentsPanel")
    args.set("testclass", "Arguments")
    coll = etree.SubElement(args, "collectionProp")
    coll.set("name", "Arguments.arguments")

    _string_prop(cfg, "HTTPSampler.domain", hd.domain or "")
    _string_prop(cfg, "HTTPSampler.port", hd.port or "")
    _string_prop(cfg, "HTTPSampler.protocol", hd.protocol or "")
    _string_prop(cfg, "HTTPSampler.contentEncoding", hd.encoding or "")
    _string_prop(cfg, "HTTPSampler.path", hd.path or "")
    if hd.implementation:
        _string_prop(cfg, "HTTPSampler.implementation", hd.implementation)

    return cfg


def _serialize_cookie_manager(cm: CookieManagerModel) -> etree.Element:
    raw = getattr(cm, "raw_xml", None)
    if _should_reuse_raw_xml(cm) and raw:
        return etree.fromstring(raw.encode("utf-8"))
    return _build_cookie_manager(cm)


def _build_cookie_manager(cm: CookieManagerModel) -> etree.Element:
    el = etree.Element("CookieManager")
    el.set("guiclass", "CookiePanel")
    el.set("testclass", "CookieManager")
    el.set("testname", "HTTP Cookie Manager")
    el.set("enabled", "true" if cm.enabled else "false")

    coll = etree.SubElement(el, "collectionProp")
    coll.set("name", "CookieManager.cookies")
    _bool_prop(el, "CookieManager.clearEachIteration", cm.clear_each_iteration)
    if cm.policy:
        _string_prop(el, "CookieManager.policy", cm.policy)

    return el


def _serialize_cache_manager(cm: CacheManagerModel) -> etree.Element:
    raw = getattr(cm, "raw_xml", None)
    if _should_reuse_raw_xml(cm) and raw:
        return etree.fromstring(raw.encode("utf-8"))
    return _build_cache_manager(cm)


def _build_cache_manager(cm: CacheManagerModel) -> etree.Element:
    el = etree.Element("CacheManager")
    el.set("guiclass", "CacheManagerGui")
    el.set("testclass", "CacheManager")
    el.set("testname", "HTTP Cache Manager")
    el.set("enabled", "true" if cm.enabled else "false")

    _bool_prop(el, "clearEachIteration", cm.clear_each_iteration)
    _bool_prop(el, "useExpires", cm.use_expires)

    return el


def _serialize_csv_dataset(ds: CSVDataSetModel) -> etree.Element:
    raw = getattr(ds, "raw_xml", None)
    if _should_reuse_raw_xml(ds) and raw:
        return etree.fromstring(raw.encode("utf-8"))
    return _build_csv_dataset(ds)


def _build_csv_dataset(ds: CSVDataSetModel) -> etree.Element:
    el = etree.Element("CSVDataSet")
    el.set("guiclass", "TestBeanGUI")
    el.set("testclass", "CSVDataSet")
    el.set("testname", ds.testname or "CSV Data Set")
    el.set("enabled", "true" if ds.enabled else "false")

    _string_prop(el, "delimiter", ds.delimiter or ",")
    _string_prop(el, "fileEncoding", ds.file_encoding or "")
    _string_prop(el, "filename", ds.filename or "")
    _bool_prop(el, "ignoreFirstLine", ds.ignore_first_line)
    _bool_prop(el, "quotedData", ds.quoted_data)
    _bool_prop(el, "recycle", ds.recycle)
    _string_prop(el, "shareMode", ds.share_mode or "shareMode.all")
    _bool_prop(el, "stopThread", ds.stop_thread)
    _string_prop(el, "variableNames", ",".join(ds.variable_names))

    return el


def _build_stepping_thread_group(tg: ThreadGroupModel) -> etree.Element:
    """Construye kg.apc.jmeter.threads.SteppingThreadGroup con aliases."""
    el = etree.Element("kg.apc.jmeter.threads.SteppingThreadGroup")
    el.set("guiclass", "kg.apc.jmeter.threads.SteppingThreadGroupGui")
    el.set("testclass", "kg.apc.jmeter.threads.SteppingThreadGroup")
    el.set("testname", tg.name or "Stepping Thread Group")
    el.set("enabled", "true" if tg.enabled else "false")

    _string_prop(el, "ThreadGroup.on_sample_error", tg.on_sample_error)
    _string_prop(el, "ThreadGroup.num_threads", str(tg.num_threads))

    # Stepping props con aliases (nombres XML originales)
    if tg.stepping:
        stepping_dict = tg.stepping.model_dump(by_alias=True)
        for alias_name, value in stepping_dict.items():
            _string_prop(el, alias_name, str(value))

    # main_controller (LoopController)
    main_ctrl = etree.SubElement(el, "elementProp")
    main_ctrl.set("name", "ThreadGroup.main_controller")
    main_ctrl.set("elementType", "LoopController")
    main_ctrl.set("guiclass", "LoopControlPanel")
    main_ctrl.set("testclass", "LoopController")
    main_ctrl.set("testname", "Loop Controller")
    _bool_prop(main_ctrl, "LoopController.continue_forever", tg.continue_forever)
    _string_prop(main_ctrl, "LoopController.loops", str(tg.loops))

    return el


def _build_standard_thread_group(tg: ThreadGroupModel) -> etree.Element:
    el = etree.Element("ThreadGroup")
    el.set("guiclass", "ThreadGroupGui")
    el.set("testclass", "ThreadGroup")
    el.set("testname", tg.name or "Thread Group")
    el.set("enabled", "true" if tg.enabled else "false")

    _string_prop(el, "ThreadGroup.on_sample_error", tg.on_sample_error)
    _string_prop(el, "ThreadGroup.num_threads", str(tg.num_threads))
    _string_prop(el, "ThreadGroup.ramp_time", str(tg.ramp_time))

    main_ctrl = etree.SubElement(el, "elementProp")
    main_ctrl.set("name", "ThreadGroup.main_controller")
    main_ctrl.set("elementType", "LoopController")
    main_ctrl.set("guiclass", "LoopControlPanel")
    main_ctrl.set("testclass", "LoopController")
    main_ctrl.set("testname", "Loop Controller")
    _bool_prop(main_ctrl, "LoopController.continue_forever", tg.continue_forever)
    _string_prop(main_ctrl, "LoopController.loops", str(tg.loops))

    if tg.scheduler:
        _bool_prop(el, "ThreadGroup.scheduler", True)
        _string_prop(el, "ThreadGroup.duration", str(tg.duration or 0))
        _string_prop(el, "ThreadGroup.delay", str(tg.delay or 0))

    return el


def _serialize_thread_group(tg: ThreadGroupModel) -> etree.Element:
    if _should_reuse_raw_xml(tg):
        return etree.fromstring(tg.raw_xml.encode("utf-8"))
    if tg.kind == "stepping":
        return _build_stepping_thread_group(tg)
    return _build_standard_thread_group(tg)


def _build_header_manager(hm: HeaderManagerModel) -> etree.Element:
    el = etree.Element("HeaderManager")
    el.set("guiclass", "HeaderPanel")
    el.set("testclass", "HeaderManager")
    el.set("testname", "HTTP Header Manager")
    el.set("enabled", "true" if hm.enabled else "false")

    coll = etree.SubElement(el, "collectionProp")
    coll.set("name", "HeaderManager.headers")
    for h in hm.headers:
        ep = etree.SubElement(coll, "elementProp")
        ep.set("name", "")
        ep.set("elementType", "Header")
        _string_prop(ep, "Header.name", h.name)
        _string_prop(ep, "Header.value", h.value)

    return el


def _build_response_assertion(ra: ResponseAssertionModel) -> etree.Element:
    el = etree.Element("ResponseAssertion")
    el.set("guiclass", "AssertionGui")
    el.set("testclass", "ResponseAssertion")
    el.set("testname", ra.name or "Response Assertion")
    el.set("enabled", "true" if ra.enabled else "false")

    coll = etree.SubElement(el, "collectionProp")
    coll.set("name", "Asserion.test_strings")  # JMeter typo histórico
    for s in ra.test_strings:
        sp = etree.SubElement(coll, "stringProp")
        sp.set("name", str(hash(s) % 100000000))  # JMeter usa nombres numéricos arbitrarios
        sp.text = s

    _string_prop(el, "Assertion.custom_message", ra.custom_message or "")
    _string_prop(el, "Assertion.test_field", ra.test_field)
    _bool_prop(el, "Assertion.assume_success", ra.assume_success)
    _int_prop(el, "Assertion.test_type", ra.test_type)

    return el


def _build_regex_extractor(re_model: RegexExtractorModel) -> etree.Element:
    el = etree.Element("RegexExtractor")
    el.set("guiclass", "RegexExtractorGui")
    el.set("testclass", "RegexExtractor")
    el.set("testname", re_model.name or "Regex Extractor")
    el.set("enabled", "true" if re_model.enabled else "false")

    _string_prop(el, "RegexExtractor.useHeaders", re_model.use_headers)
    _string_prop(el, "RegexExtractor.refname", re_model.refname)
    _string_prop(el, "RegexExtractor.regex", re_model.regex)
    _string_prop(el, "RegexExtractor.template", re_model.template)
    _string_prop(el, "RegexExtractor.default", re_model.default)
    _bool_prop(el, "RegexExtractor.default_empty_value", re_model.default_empty_value)
    _string_prop(el, "RegexExtractor.match_number", re_model.match_number)
    if re_model.scope:
        _string_prop(el, "Sample.scope", re_model.scope)

    return el


def _build_json_extractor(je: JsonExtractorModel) -> etree.Element:
    el = etree.Element("JSONPostProcessor")
    el.set("guiclass", "JSONPostProcessorGui")
    el.set("testclass", "JSONPostProcessor")
    el.set("testname", je.name or "JSON Extractor")
    el.set("enabled", "true" if je.enabled else "false")

    _string_prop(el, "JSONPostProcessor.referenceNames", je.refname)
    _string_prop(el, "JSONPostProcessor.jsonPathExprs", je.json_path)
    _string_prop(el, "JSONPostProcessor.match_numbers", je.match_number)
    _string_prop(el, "JSONPostProcessor.defaultValues", je.default)

    return el


def _build_constant_timer(t: ConstantTimerModel) -> etree.Element:
    el = etree.Element("ConstantTimer")
    el.set("guiclass", "ConstantTimerGui")
    el.set("testclass", "ConstantTimer")
    el.set("testname", t.name or "Constant Timer")
    el.set("enabled", "true" if t.enabled else "false")
    _string_prop(el, "ConstantTimer.delay", str(t.delay_ms))
    return el


def _build_uniform_timer(t: UniformRandomTimerModel) -> etree.Element:
    el = etree.Element("UniformRandomTimer")
    el.set("guiclass", "UniformRandomTimerGui")
    el.set("testclass", "UniformRandomTimer")
    el.set("testname", t.name or "Uniform Random Timer")
    el.set("enabled", "true" if t.enabled else "false")
    _string_prop(el, "ConstantTimer.delay", str(t.constant_delay_ms))
    _string_prop(el, "RandomTimer.range", str(t.random_delay_ms))
    return el


# Map de tipo de SamplerChild → builder
_SAMPLER_CHILD_BUILDERS = {
    "header_manager": _build_header_manager,
    "response_assertion": _build_response_assertion,
    "regex_extractor": _build_regex_extractor,
    "json_extractor": _build_json_extractor,
    "constant_timer": _build_constant_timer,
    "uniform_random_timer": _build_uniform_timer,
}


def _serialize_sampler_child(child: SamplerChild) -> etree.Element:
    """Serializa un SamplerChild a XML. Reusa raw_xml si no está dirty."""
    if isinstance(child.data, UnsupportedElement):
        # Siempre reusar raw_xml de unmapped (no se editan)
        return etree.fromstring(child.data.raw_xml.encode("utf-8"))

    if _should_reuse_raw_xml(child.data):
        raw = getattr(child.data, "raw_xml", None)
        if raw:
            return etree.fromstring(raw.encode("utf-8"))

    # Reconstruir desde campos
    builder = _SAMPLER_CHILD_BUILDERS.get(child.type)
    if builder:
        return builder(child.data)

    # Fallback: si no hay builder específico, intentar raw_xml o fallar
    raw = getattr(child.data, "raw_xml", None)
    if raw:
        return etree.fromstring(raw.encode("utf-8"))
    raise ValueError(f"No hay builder ni raw_xml para SamplerChild type={child.type}")


def _build_http_sampler(sampler: HTTPSamplerModel) -> etree.Element:
    el = etree.Element("HTTPSamplerProxy")
    el.set("guiclass", "HttpTestSampleGui")
    el.set("testclass", "HTTPSamplerProxy")
    el.set("testname", sampler.name or "HTTP Request")
    el.set("enabled", "true" if sampler.enabled else "false")

    # Arguments / body
    args = etree.SubElement(el, "elementProp")
    args.set("name", "HTTPsampler.Arguments")
    args.set("elementType", "Arguments")
    args.set("guiclass", "HTTPArgumentsPanel")
    args.set("testclass", "Arguments")
    args.set("testname", "User Defined Variables")
    coll = etree.SubElement(args, "collectionProp")
    coll.set("name", "Arguments.arguments")

    if sampler.body.mode == "raw" and sampler.body.raw_text is not None:
        ep = etree.SubElement(coll, "elementProp")
        ep.set("name", "")
        ep.set("elementType", "HTTPArgument")
        _bool_prop(ep, "HTTPArgument.always_encode", False)
        _string_prop(ep, "Argument.value", sampler.body.raw_text)
        _string_prop(ep, "Argument.metadata", "=")
    elif sampler.body.mode == "form":
        for arg in sampler.body.form_args:
            ep = etree.SubElement(coll, "elementProp")
            ep.set("name", arg.name)
            ep.set("elementType", "HTTPArgument")
            _bool_prop(ep, "HTTPArgument.always_encode", arg.always_encode)
            _string_prop(ep, "Argument.value", arg.value)
            _string_prop(ep, "Argument.metadata", arg.metadata)
            _bool_prop(ep, "HTTPArgument.use_equals", arg.use_equals)
            _string_prop(ep, "Argument.name", arg.name)

    if sampler.domain:
        _string_prop(el, "HTTPSampler.domain", sampler.domain)
    if sampler.port:
        _string_prop(el, "HTTPSampler.port", sampler.port)
    if sampler.protocol:
        _string_prop(el, "HTTPSampler.protocol", sampler.protocol)
    _string_prop(el, "HTTPSampler.contentEncoding", sampler.content_encoding or "")
    _string_prop(el, "HTTPSampler.path", sampler.path or "")
    _string_prop(el, "HTTPSampler.method", sampler.method or "GET")
    _bool_prop(el, "HTTPSampler.follow_redirects", sampler.follow_redirects)
    _bool_prop(el, "HTTPSampler.auto_redirects", sampler.auto_redirects)
    _bool_prop(el, "HTTPSampler.use_keepalive", sampler.use_keepalive)
    _bool_prop(el, "HTTPSampler.postBodyRaw", sampler.body.mode == "raw")

    return el


def _serialize_http_sampler_with_children(sampler: HTTPSamplerModel) -> tuple:
    """
    Retorna (sampler_elem, hash_tree_elem) con los children dentro del hashTree.
    """
    if _should_reuse_raw_xml(sampler):
        sampler_elem = etree.fromstring(sampler.raw_xml.encode("utf-8"))
        # raw_xml NO incluye el hashTree de los children; el hashTree se reconstruye igual
        ht = etree.Element("hashTree")
        for child in sorted(sampler.children, key=lambda c: c.order):
            ht.append(_serialize_sampler_child(child))
            etree.SubElement(ht, "hashTree")  # hashTree vacío del hijo
        return sampler_elem, ht

    sampler_elem = _build_http_sampler(sampler)
    ht = etree.Element("hashTree")
    for child in sorted(sampler.children, key=lambda c: c.order):
        ht.append(_serialize_sampler_child(child))
        etree.SubElement(ht, "hashTree")
    return sampler_elem, ht


# ============================================================================
# Controllers
# ============================================================================

def _build_generic_controller(ctrl: GenericControllerModel) -> etree.Element:
    el = etree.Element("GenericController")
    el.set("guiclass", "LogicControllerGui")
    el.set("testclass", "GenericController")
    el.set("testname", ctrl.name or "Generic Controller")
    el.set("enabled", "true" if ctrl.enabled else "false")
    return el


def _build_loop_controller(ctrl: LoopControllerModel) -> etree.Element:
    el = etree.Element("LoopController")
    el.set("guiclass", "LoopControlPanel")
    el.set("testclass", "LoopController")
    el.set("testname", ctrl.name or "Loop Controller")
    el.set("enabled", "true" if ctrl.enabled else "false")
    _bool_prop(el, "LoopController.continue_forever", ctrl.continue_forever)
    _string_prop(el, "LoopController.loops", str(ctrl.loops))
    return el


def _build_if_controller(ctrl: IfControllerModel) -> etree.Element:
    el = etree.Element("IfController")
    el.set("guiclass", "IfControllerPanel")
    el.set("testclass", "IfController")
    el.set("testname", ctrl.name or "If Controller")
    el.set("enabled", "true" if ctrl.enabled else "false")
    _string_prop(el, "IfController.condition", ctrl.condition)
    _bool_prop(el, "IfController.evaluateAll", ctrl.evaluate_all)
    _bool_prop(el, "IfController.useExpression", ctrl.use_expression)
    return el


def _build_while_controller(ctrl: WhileControllerModel) -> etree.Element:
    el = etree.Element("WhileController")
    el.set("guiclass", "WhileControllerGui")
    el.set("testclass", "WhileController")
    el.set("testname", ctrl.name or "While Controller")
    el.set("enabled", "true" if ctrl.enabled else "false")
    _string_prop(el, "WhileController.condition", ctrl.condition)
    return el


def _build_throughput_controller(ctrl: ThroughputControllerModel) -> etree.Element:
    el = etree.Element("ThroughputController")
    el.set("guiclass", "ThroughputControllerGui")
    el.set("testclass", "ThroughputController")
    el.set("testname", ctrl.name or "Throughput Controller")
    el.set("enabled", "true" if ctrl.enabled else "false")
    _int_prop(el, "ThroughputController.style", ctrl.style)
    _bool_prop(el, "ThroughputController.perThread", ctrl.per_thread)

    max_thr = etree.SubElement(el, "intProp")
    max_thr.set("name", "ThroughputController.maxThroughput")
    max_thr.text = "1"

    percent = etree.SubElement(el, "FloatProperty")
    name = etree.SubElement(percent, "name")
    name.text = "ThroughputController.percentThroughput"
    value = etree.SubElement(percent, "value")
    value.text = ctrl.percent_throughput

    return el


_CONTROLLER_BUILDERS = {
    "generic_controller": _build_generic_controller,
    "loop_controller": _build_loop_controller,
    "if_controller": _build_if_controller,
    "while_controller": _build_while_controller,
    "throughput_controller": _build_throughput_controller,
}


def _serialize_controller_with_children(ctrl) -> tuple:
    """Retorna (controller_elem, hash_tree_with_children)."""
    builder = _CONTROLLER_BUILDERS.get(ctrl.kind)
    if not builder:
        raise ValueError(f"Controller no soportado: {ctrl.kind}")

    ctrl_elem = builder(ctrl)
    ht = etree.Element("hashTree")
    for child in sorted(ctrl.children, key=lambda c: c.order):
        _append_tg_child(ht, child)
    return ctrl_elem, ht


# ============================================================================
# TG children: samplers + controllers + unsupported
# ============================================================================

def _append_tg_child(parent_ht: etree.Element, child: TGChild) -> None:
    """Añade un TGChild al hashTree parent."""
    if child.type == "sampler" and child.sampler:
        sampler_elem, sampler_ht = _serialize_http_sampler_with_children(child.sampler)
        parent_ht.append(sampler_elem)
        parent_ht.append(sampler_ht)
    elif child.type == "controller" and child.controller:
        ctrl_elem, ctrl_ht = _serialize_controller_with_children(child.controller)
        parent_ht.append(ctrl_elem)
        parent_ht.append(ctrl_ht)
    elif child.type == "unsupported" and child.unsupported:
        # Unsupported: siempre reusar raw_xml
        parent_ht.append(etree.fromstring(child.unsupported.raw_xml.encode("utf-8")))
        etree.SubElement(parent_ht, "hashTree")
    else:
        raise ValueError(f"TGChild inválido: type={child.type}")


# ============================================================================
# Listeners y config_elements top-level
# ============================================================================

def _serialize_listener(li: ListenerModel) -> etree.Element:
    # Listeners: siempre reusar raw_xml si existe (passthrough total)
    if li.raw_xml:
        return etree.fromstring(li.raw_xml.encode("utf-8"))
    # Fallback mínimo si no hay raw_xml
    el = etree.Element("ResultCollector")
    el.set("guiclass", li.guiclass or "ViewResultsFullVisualizer")
    el.set("testclass", "ResultCollector")
    el.set("testname", li.name or "Listener")
    el.set("enabled", "true" if li.enabled else "false")
    if li.filename:
        _string_prop(el, "filename", li.filename)
    return el


def _serialize_config_element(ce: ConfigElementModel) -> etree.Element:
    if ce.raw_xml:
        return etree.fromstring(ce.raw_xml.encode("utf-8"))
    raise ValueError(f"ConfigElement sin raw_xml: {ce.kind}")


def _serialize_unmapped(u: UnsupportedElement) -> etree.Element:
    return etree.fromstring(u.raw_xml.encode("utf-8"))


# ============================================================================
# Orquestador principal
# ============================================================================

def regenerate_jmx_from_structure(structure: AIScriptStructure) -> str:
    """
    Regenera un JMX completo desde AIScriptStructure.

    Estrategia edit-preserving:
    - Elementos con is_dirty=False y raw_xml → reusar raw_xml.
    - Elementos con is_dirty=True o sin raw_xml → re-construir.
    """
    root = etree.Element("jmeterTestPlan")
    root.set("version", "1.2")
    root.set("properties", "5.0")
    root.set("jmeter", structure.metadata.jmx_version or "5.6.3")

    outer_ht = etree.SubElement(root, "hashTree")

    # TestPlan
    test_plan_elem = _serialize_test_plan(structure.test_plan)
    outer_ht.append(test_plan_elem)
    test_plan_ht = etree.SubElement(outer_ht, "hashTree")

    # UDV top-level (Arguments)
    if structure.user_defined_variables:
        udv_elem = _serialize_arguments_top_level(structure.user_defined_variables)
        test_plan_ht.append(udv_elem)
        etree.SubElement(test_plan_ht, "hashTree")

    # HTTP Defaults
    if structure.http_defaults:
        hd_elem = _serialize_http_defaults(structure.http_defaults)
        test_plan_ht.append(hd_elem)
        etree.SubElement(test_plan_ht, "hashTree")

    # Cookie Manager
    if structure.cookie_manager:
        cm_elem = _serialize_cookie_manager(structure.cookie_manager)
        test_plan_ht.append(cm_elem)
        etree.SubElement(test_plan_ht, "hashTree")

    # Cache Manager
    if structure.cache_manager:
        ca_elem = _serialize_cache_manager(structure.cache_manager)
        test_plan_ht.append(ca_elem)
        etree.SubElement(test_plan_ht, "hashTree")

    # CSV Data Sets
    for ds in structure.csv_data_sets:
        ds_elem = _serialize_csv_dataset(ds)
        test_plan_ht.append(ds_elem)
        etree.SubElement(test_plan_ht, "hashTree")

    # Thread Groups con sus children
    for tg in structure.thread_groups:
        tg_elem = _serialize_thread_group(tg)
        test_plan_ht.append(tg_elem)
        tg_ht = etree.SubElement(test_plan_ht, "hashTree")
        for child in sorted(tg.children, key=lambda c: c.order):
            _append_tg_child(tg_ht, child)

    # Config elements adicionales (no cookie/cache)
    for ce in structure.config_elements:
        ce_elem = _serialize_config_element(ce)
        test_plan_ht.append(ce_elem)
        etree.SubElement(test_plan_ht, "hashTree")

    # Listeners
    for li in structure.listeners:
        li_elem = _serialize_listener(li)
        test_plan_ht.append(li_elem)
        etree.SubElement(test_plan_ht, "hashTree")

    # Unmapped top-level (Recording, Proxy, etc.)
    for u in structure.unmapped:
        u_elem = _serialize_unmapped(u)
        test_plan_ht.append(u_elem)
        etree.SubElement(test_plan_ht, "hashTree")

    # Serializar a string XML con declaración
    xml_bytes = etree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )
    return xml_bytes.decode("utf-8")
