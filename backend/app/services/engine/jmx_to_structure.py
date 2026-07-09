"""
Parser JMX → AIScriptStructure.

Convierte un JMX (string XML) a la representación intermedia editable
definida en app.schemas.ai_script_structure.

NO persiste nada en DB — el modelo se deriva on-demand desde current_jmx.

Basado en análisis de sample_jmx/Ejercicio_Booking.jmx (Sprint 2.0).
Soporta:
- Standard ThreadGroup + kg.apc SteppingThreadGroup.
- HTTPSampler con body raw y form-encoded.
- HeaderManager, ResponseAssertion (con tolerancia al typo "Asserion"),
  RegexExtractor, JsonExtractor, XPathExtractor, BoundaryExtractor.
- Constant/Uniform/Gaussian timers.
- Controllers: Generic, Loop, If, While, Throughput.
- Config elements: CookieManager, CacheManager + otros como passthrough.
- Listeners estándar + kg.apc.* family.
- Elementos no soportados → unmapped[] con raw_xml.
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
from datetime import datetime

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
    StructureMetadata,
)


# ============================================================================
# Helpers de lectura de props XML
# ============================================================================

def _string_prop(elem, name: str, default: str = "") -> str:
    """Lee un <stringProp name='X'> hijo directo. Tolera typo 'Asserion'."""
    # Buscar el nombre exacto y la variante con typo
    for prop_name in (name, name.replace("Assertion.", "Asserion.")):
        node = elem.find(f"./stringProp[@name='{prop_name}']")
        if node is not None:
            return (node.text or "").strip()
    return default


def _int_prop(elem, name: str, default: int = 0) -> int:
    """Lee un <intProp> o <stringProp> numérico."""
    for tag in ("intProp", "stringProp"):
        node = elem.find(f"./{tag}[@name='{name}']")
        if node is not None and node.text:
            try:
                return int(node.text.strip())
            except ValueError:
                continue
    return default


def _bool_prop(elem, name: str, default: bool = False) -> bool:
    """Lee un <boolProp>."""
    node = elem.find(f"./boolProp[@name='{name}']")
    if node is None:
        return default
    text = (node.text or "").strip().lower()
    return text == "true"


def _enabled_attr(elem) -> bool:
    """Lee el atributo enabled del elemento. Default true si no está presente."""
    val = elem.get("enabled", "true").lower()
    return val != "false"


def _testname_attr(elem) -> str:
    return elem.get("testname", "")


def _guiclass_attr(elem) -> str:
    return elem.get("guiclass", "")


def _testclass_attr(elem) -> str:
    return elem.get("testclass", "")


def _raw_xml(elem) -> str:
    """Serializa el elemento de vuelta a XML (para passthrough)."""
    return etree.tostring(elem, encoding="unicode", pretty_print=False)


# ============================================================================
# Walker de hashTree (par <X/><hashTree>...</hashTree>)
# ============================================================================

def _walk_hashtree_children(hash_tree_elem) -> List[Tuple[Any, Any]]:
    """
    Recorre un <hashTree> y devuelve pares (element, child_hashTree).
    JMeter alterna: [Element1, HashTree1, Element2, HashTree2, ...].
    El HashTree puede estar vacío (no tiene hijos).

    NOTA (Sprint 2.1.1): se filtran Comments y Processing Instructions de lxml,
    que tienen tag no-string (cyfunction). Los JMX generados por la IA suelen
    incluir <!-- comentarios --> que rompen el parsing posterior.
    """
    if hash_tree_elem is None:
        return []
    # Filtrar nodos non-Element (Comments, Processing Instructions, etc.)
    # lxml: Comments tienen elem.tag = <cyfunction Comment>, no string.
    children = [c for c in hash_tree_elem if isinstance(c.tag, str)]
    pairs = []
    i = 0
    while i < len(children):
        elem = children[i]
        if elem.tag == "hashTree":
            i += 1
            continue
        # Sigue un hashTree si existe
        next_ht = children[i + 1] if (i + 1 < len(children) and children[i + 1].tag == "hashTree") else None
        pairs.append((elem, next_ht))
        i += 2 if next_ht is not None else 1
    return pairs


# ============================================================================
# Parsers específicos
# ============================================================================

def _parse_test_plan(elem) -> TestPlanModel:
    return TestPlanModel(
        name=_testname_attr(elem) or "Test Plan",
        functional_mode=_bool_prop(elem, "TestPlan.functional_mode"),
        serialize_threadgroups=_bool_prop(elem, "TestPlan.serialize_threadgroups"),
        tearDown_on_shutdown=_bool_prop(elem, "TestPlan.tearDown_on_shutdown", True),
        comments=_string_prop(elem, "TestPlan.comments") or None,
    )


def _parse_arguments_collection(elem) -> List[UserDefinedVariable]:
    """
    Lee un <collectionProp name='Arguments.arguments'> con elementProps Argument.
    Usado para User Defined Variables top-level y HTTPArguments en samplers.
    """
    result = []
    coll = elem.find(".//collectionProp[@name='Arguments.arguments']")
    if coll is None:
        return result
    for arg in coll.findall("./elementProp"):
        name = _string_prop(arg, "Argument.name")
        value = _string_prop(arg, "Argument.value")
        meta = _string_prop(arg, "Argument.metadata", "=")
        if name:
            result.append(UserDefinedVariable(name=name, value=value, metadata=meta))
    return result


def _parse_embedded_test_plan_udv(test_plan_elem) -> List[UserDefinedVariable]:
    """
    HF16: extrae UDV del slot inline del TestPlan (Patrón B):

        <TestPlan ...>
          <elementProp name="TestPlan.user_defined_variables" elementType="Arguments">
            <collectionProp name="Arguments.arguments"> ... </collectionProp>
          </elementProp>
        </TestPlan>

    La IA a veces genera este patrón embebido en vez del bloque <Arguments>
    hermano del TestPlan (Patrón A). Antes de HF16 estas variables no se
    detectaban → el editor reportaba "N variables sin definir" en falso.
    """
    embedded = test_plan_elem.find(
        "./elementProp[@name='TestPlan.user_defined_variables']"
    )
    if embedded is None:
        return []
    return _parse_arguments_collection(embedded)


def _parse_http_defaults(elem) -> HttpDefaultsModel:
    return HttpDefaultsModel(
        domain=_string_prop(elem, "HTTPSampler.domain") or None,
        protocol=_string_prop(elem, "HTTPSampler.protocol") or None,
        port=_string_prop(elem, "HTTPSampler.port") or None,
        path=_string_prop(elem, "HTTPSampler.path") or None,
        implementation=_string_prop(elem, "HTTPSampler.implementation") or None,
        encoding=_string_prop(elem, "HTTPSampler.contentEncoding") or None,
    )


def _parse_cookie_manager(elem) -> CookieManagerModel:
    return CookieManagerModel(
        enabled=_enabled_attr(elem),
        clear_each_iteration=_bool_prop(elem, "CookieManager.clearEachIteration"),
        policy=_string_prop(elem, "CookieManager.policy") or None,
    )


def _parse_cache_manager(elem) -> CacheManagerModel:
    return CacheManagerModel(
        enabled=_enabled_attr(elem),
        clear_each_iteration=_bool_prop(elem, "clearEachIteration"),
        use_expires=_bool_prop(elem, "useExpires", True),
    )


def _parse_csv_dataset(elem) -> CSVDataSetModel:
    variable_names_raw = _string_prop(elem, "variableNames")
    variable_names = [v.strip() for v in variable_names_raw.split(",") if v.strip()]
    return CSVDataSetModel(
        testname=_testname_attr(elem) or "CSV Data Set",
        enabled=_enabled_attr(elem),
        filename=_string_prop(elem, "filename"),
        variable_names=variable_names,
        delimiter=_string_prop(elem, "delimiter", ","),
        ignore_first_line=_bool_prop(elem, "ignoreFirstLine"),
        quoted_data=_bool_prop(elem, "quotedData"),
        recycle=_bool_prop(elem, "recycle", True),
        share_mode=_string_prop(elem, "shareMode", "shareMode.all"),
        stop_thread=_bool_prop(elem, "stopThread"),
        file_encoding=_string_prop(elem, "fileEncoding") or None,
    )


def _parse_stepping_config(elem) -> SteppingConfig:
    """Lee los 8 stringProps del kg.apc SteppingThreadGroup con sus nombres EXACTOS."""
    return SteppingConfig(**{
        "Threads initial delay": _int_prop(elem, "Threads initial delay", 0),
        "Start users count": _int_prop(elem, "Start users count", 1),
        "Start users count burst": _int_prop(elem, "Start users count burst", 0),
        "Start users period": _int_prop(elem, "Start users period", 30),
        "Stop users count": _int_prop(elem, "Stop users count", 1),
        "Stop users period": _int_prop(elem, "Stop users period", 5),
        "rampUp": _int_prop(elem, "rampUp", 5),
        "flighttime": _int_prop(elem, "flighttime", 60),
    })


def _parse_thread_group(elem, hash_tree, http_defaults: Optional[HttpDefaultsModel]) -> ThreadGroupModel:
    guiclass = _guiclass_attr(elem)
    testclass = _testclass_attr(elem)

    if "SteppingThreadGroup" in guiclass or "SteppingThreadGroup" in testclass:
        kind = "stepping"
        stepping = _parse_stepping_config(elem)
    else:
        kind = "standard"
        stepping = None

    # main_controller para loops
    main_ctrl = elem.find("./elementProp[@name='ThreadGroup.main_controller']")
    loops = 1
    continue_forever = False
    if main_ctrl is not None:
        loops = _int_prop(main_ctrl, "LoopController.loops", 1)
        continue_forever = _bool_prop(main_ctrl, "LoopController.continue_forever")

    children = _parse_tg_children(hash_tree, http_defaults)

    return ThreadGroupModel(
        kind=kind,
        name=_testname_attr(elem) or "Thread Group",
        enabled=_enabled_attr(elem),
        comments=_string_prop(elem, "TestPlan.comments") or None,
        on_sample_error=_string_prop(elem, "ThreadGroup.on_sample_error", "continue"),
        num_threads=_int_prop(elem, "ThreadGroup.num_threads", 1),
        ramp_time=_int_prop(elem, "ThreadGroup.ramp_time", 1),
        duration=_int_prop(elem, "ThreadGroup.duration") or None,
        delay=_int_prop(elem, "ThreadGroup.delay") or None,
        scheduler=_bool_prop(elem, "ThreadGroup.scheduler"),
        loops=loops,
        continue_forever=continue_forever,
        stepping=stepping,
        children=children,
        raw_xml=_raw_xml(elem),
    )


def _parse_header_manager(elem) -> HeaderManagerModel:
    headers = []
    coll = elem.find(".//collectionProp[@name='HeaderManager.headers']")
    if coll is not None:
        for h in coll.findall("./elementProp"):
            name = _string_prop(h, "Header.name")
            value = _string_prop(h, "Header.value")
            if name:
                headers.append(HeaderModel(name=name, value=value))
    return HeaderManagerModel(
        enabled=_enabled_attr(elem),
        headers=headers,
    )


def _derive_pattern_match_and_negate(test_type: int) -> Tuple[str, bool]:
    """
    Bitmask JMeter Assertion.test_type:
    1 = matches (regex), 2 = contains, 4 = not, 8 = equals, 16 = substring.
    """
    negate = bool(test_type & 4)
    if test_type & 1:
        pattern = "matches"
    elif test_type & 8:
        pattern = "equals"
    elif test_type & 16:
        pattern = "substring"
    else:
        pattern = "contains"
    return pattern, negate


def _parse_response_assertion(elem) -> ResponseAssertionModel:
    test_type = _int_prop(elem, "Assertion.test_type", 2)
    # Test strings — collectionProp con stringProps; tolerar typo "Asserion"
    strings = []
    for coll_name in ("Assertion.test_strings", "Asserion.test_strings"):
        coll = elem.find(f".//collectionProp[@name='{coll_name}']")
        if coll is not None:
            for s in coll.findall("./stringProp"):
                if s.text:
                    strings.append(s.text.strip())
            break

    pattern, negate = _derive_pattern_match_and_negate(test_type)

    return ResponseAssertionModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "Response Assertion",
        test_field=_string_prop(elem, "Assertion.test_field", "Assertion.response_data"),
        test_type=test_type,
        test_strings=strings,
        custom_message=_string_prop(elem, "Assertion.custom_message") or None,
        assume_success=_bool_prop(elem, "Assertion.assume_success"),
        negate=negate,
        pattern_match=pattern,
    )


def _parse_regex_extractor(elem) -> RegexExtractorModel:
    use_headers = _string_prop(elem, "RegexExtractor.useHeaders", "false")
    extract_from_map = {
        "false": "body", "true": "header", "URL": "url",
        "code": "code", "message": "message",
    }
    extract_from = extract_from_map.get(use_headers, "body")
    return RegexExtractorModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "Regex Extractor",
        refname=_string_prop(elem, "RegexExtractor.refname"),
        regex=_string_prop(elem, "RegexExtractor.regex"),
        template=_string_prop(elem, "RegexExtractor.template", "$1$"),
        match_number=_string_prop(elem, "RegexExtractor.match_number", "1"),
        default=_string_prop(elem, "RegexExtractor.default"),
        default_empty_value=_bool_prop(elem, "RegexExtractor.default_empty_value"),
        use_headers=use_headers,
        extract_from=extract_from,
    )


def _parse_json_extractor(elem) -> JsonExtractorModel:
    return JsonExtractorModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "JSON Extractor",
        refname=_string_prop(elem, "JSONPostProcessor.referenceNames"),
        json_path=_string_prop(elem, "JSONPostProcessor.jsonPathExprs"),
        match_number=_string_prop(elem, "JSONPostProcessor.match_numbers", "1"),
        default=_string_prop(elem, "JSONPostProcessor.defaultValues"),
    )


def _parse_constant_timer(elem) -> ConstantTimerModel:
    return ConstantTimerModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "Constant Timer",
        delay_ms=_int_prop(elem, "ConstantTimer.delay", 0),
    )


def _parse_uniform_timer(elem) -> UniformRandomTimerModel:
    return UniformRandomTimerModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "Uniform Random Timer",
        constant_delay_ms=_int_prop(elem, "ConstantTimer.delay", 0),
        random_delay_ms=_int_prop(elem, "RandomTimer.range", 100),
    )


def _parse_sampler_body(elem) -> SamplerBody:
    """Detecta body mode: raw (postBodyRaw=true) o form (args)."""
    post_body_raw = _bool_prop(elem, "HTTPSampler.postBodyRaw")
    coll = elem.find(".//collectionProp[@name='Arguments.arguments']")

    if post_body_raw and coll is not None:
        # Body raw: el value del primer Argument contiene el JSON/XML
        first_arg = coll.find("./elementProp")
        if first_arg is not None:
            raw_text = _string_prop(first_arg, "Argument.value")
            return SamplerBody(mode="raw", raw_text=raw_text, form_args=[], body_type="auto")
        return SamplerBody(mode="none", raw_text=None, form_args=[], body_type="auto")

    if coll is not None and len(coll.findall("./elementProp")) > 0:
        # Form-encoded
        args = []
        for arg in coll.findall("./elementProp"):
            args.append(FormArgument(
                name=_string_prop(arg, "Argument.name"),
                value=_string_prop(arg, "Argument.value"),
                always_encode=_bool_prop(arg, "HTTPArgument.always_encode"),
                use_equals=_bool_prop(arg, "HTTPArgument.use_equals", True),
                metadata=_string_prop(arg, "Argument.metadata", "="),
            ))
        if args:
            return SamplerBody(mode="form", raw_text=None, form_args=args, body_type="form")
    return SamplerBody(mode="none", raw_text=None, form_args=[], body_type="auto")


def _rescue_malformed_body(hash_tree) -> Optional[SamplerBody]:
    """
    HF1: rescate de body raw mal ubicado por el SYSTEM_PROMPT de la IA.

    Algunos JMX generados por la IA colocan el body fuera del sampler:
    <HTTPSamplerProxy>
      <boolProp name="HTTPSampler.postBodyRaw">false</boolProp>   <- aquí falso
    </HTTPSamplerProxy>
    <hashTree>
      <HeaderManager>...</HeaderManager>
      <hashTree/>
      <stringProp name="HTTPSampler.postBodyRaw">true</stringProp>   <- suelto
      <hashTree/>
      <elementProp name="HTTPsampler.Arguments">                    <- suelto, body real
        <collectionProp>
          <elementProp name="body" elementType="HTTPArgument">
            <stringProp name="Argument.value">{JSON}</stringProp>
            ...

    Esta función busca esos artefactos sueltos en el hash_tree (hijos directos)
    y, si encuentra ambos, devuelve un SamplerBody con mode=raw poblado.
    Si no encuentra, devuelve None.
    """
    if hash_tree is None:
        return None

    has_post_body_raw_flag = False
    orphan_args = None

    for child in hash_tree:
        if not isinstance(child.tag, str):
            continue
        if child.tag == "stringProp" and child.get("name") == "HTTPSampler.postBodyRaw":
            text = (child.text or "").strip().lower()
            if text == "true":
                has_post_body_raw_flag = True
        elif child.tag == "elementProp" and child.get("name") == "HTTPsampler.Arguments":
            orphan_args = child

    if not has_post_body_raw_flag or orphan_args is None:
        return None

    # Extraer el primer Argument.value de la collection
    coll = orphan_args.find(".//collectionProp[@name='Arguments.arguments']")
    if coll is None:
        return None
    first_arg = coll.find("./elementProp")
    if first_arg is None:
        return None
    raw_text = _string_prop(first_arg, "Argument.value")
    if not raw_text:
        return None

    return SamplerBody(mode="raw", raw_text=raw_text, form_args=[], body_type="auto")


def _parse_http_sampler(elem, hash_tree) -> HTTPSamplerModel:
    body = _parse_sampler_body(elem)

    # HF1: si el hash_tree tiene los artefactos sueltos del SYSTEM_PROMPT IA
    # malformado (postBodyRaw=true suelto + HTTPsampler.Arguments suelto con
    # body real), rescatarlos. Prevalecen sobre lo que diga el sampler porque
    # en este JMX malformado el body real SIEMPRE está fuera del sampler.
    rescued_body = _rescue_malformed_body(hash_tree)
    if rescued_body is not None:
        body = rescued_body

    # Si rescatamos body, filtrar los artefactos del hash_tree para que no
    # aparezcan como children "unsupported" en el editor.
    skip_orphan_body = rescued_body is not None
    children = _parse_sampler_children(hash_tree, parent_sampler_id=None, skip_orphan_body=skip_orphan_body)

    sampler = HTTPSamplerModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "HTTP Request",
        method=_string_prop(elem, "HTTPSampler.method", "GET"),
        protocol=_string_prop(elem, "HTTPSampler.protocol") or None,
        domain=_string_prop(elem, "HTTPSampler.domain") or None,
        port=_string_prop(elem, "HTTPSampler.port") or None,
        path=_string_prop(elem, "HTTPSampler.path"),
        content_encoding=_string_prop(elem, "HTTPSampler.contentEncoding", "UTF-8"),
        follow_redirects=_bool_prop(elem, "HTTPSampler.follow_redirects", True),
        use_keepalive=_bool_prop(elem, "HTTPSampler.use_keepalive", True),
        auto_redirects=_bool_prop(elem, "HTTPSampler.auto_redirects"),
        body=body,
        children=children,
        raw_xml=_raw_xml(elem),
    )

    # Propagar parent_sampler_id a UnsupportedElement children
    for ch in sampler.children:
        if isinstance(ch.data, UnsupportedElement):
            ch.data.parent_sampler_id = sampler.id

    return sampler


# ============================================================================
# Parser de children de un Sampler (HeaderManager, Assertions, Extractors, Timers)
# ============================================================================

_SAMPLER_CHILD_PARSERS = {
    "HeaderPanel": ("header_manager", _parse_header_manager),
    "AssertionGui": ("response_assertion", _parse_response_assertion),
    "RegexExtractorGui": ("regex_extractor", _parse_regex_extractor),
    "JSONPostProcessorGui": ("json_extractor", _parse_json_extractor),
    "ConstantTimerGui": ("constant_timer", _parse_constant_timer),
    "UniformRandomTimerGui": ("uniform_random_timer", _parse_uniform_timer),
}


def _parse_sampler_children(hash_tree, parent_sampler_id, skip_orphan_body: bool = False) -> List[SamplerChild]:
    """
    Parsea los children del hashTree de un sampler.

    skip_orphan_body=True: oculta los artefactos sueltos del JMX malformado de la IA
    (stringProp postBodyRaw + elementProp HTTPsampler.Arguments) ya rescatados
    por _rescue_malformed_body. Sin esta flag aparecerían como "unsupported".
    """
    if hash_tree is None:
        return []
    result = []
    order = 0
    for elem, _ in _walk_hashtree_children(hash_tree):
        # HF1: filtrar artefactos del JMX malformado IA cuando ya fueron rescatados
        if skip_orphan_body:
            if elem.tag == "stringProp" and elem.get("name") == "HTTPSampler.postBodyRaw":
                continue
            if elem.tag == "elementProp" and elem.get("name") == "HTTPsampler.Arguments":
                continue

        guiclass = _guiclass_attr(elem)
        if guiclass in _SAMPLER_CHILD_PARSERS:
            child_type, parser_fn = _SAMPLER_CHILD_PARSERS[guiclass]
            data = parser_fn(elem)
            result.append(SamplerChild(type=child_type, order=order, data=data))
        else:
            # Unsupported child del sampler
            unsupp = UnsupportedElement(
                kind=guiclass or elem.tag,
                name=_testname_attr(elem) or None,
                reason=f"Elemento '{guiclass or elem.tag}' no editable visualmente en este editor",
                severity="warning",
                raw_xml=_raw_xml(elem),
                parent_sampler_id=parent_sampler_id,
            )
            result.append(SamplerChild(type="unsupported", order=order, data=unsupp))
        order += 1
    return result


# ============================================================================
# Parser de Controllers
# ============================================================================

def _parse_generic_controller(elem, hash_tree, http_defaults) -> GenericControllerModel:
    return GenericControllerModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "Generic Controller",
        children=_parse_tg_children(hash_tree, http_defaults),
    )


def _parse_loop_controller(elem, hash_tree, http_defaults) -> LoopControllerModel:
    return LoopControllerModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "Loop Controller",
        loops=_int_prop(elem, "LoopController.loops", 1),
        continue_forever=_bool_prop(elem, "LoopController.continue_forever"),
        children=_parse_tg_children(hash_tree, http_defaults),
    )


def _parse_if_controller(elem, hash_tree, http_defaults) -> IfControllerModel:
    return IfControllerModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "If Controller",
        condition=_string_prop(elem, "IfController.condition"),
        use_expression=_bool_prop(elem, "IfController.useExpression", True),
        evaluate_all=_bool_prop(elem, "IfController.evaluateAll"),
        children=_parse_tg_children(hash_tree, http_defaults),
    )


def _parse_while_controller(elem, hash_tree, http_defaults) -> WhileControllerModel:
    return WhileControllerModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "While Controller",
        condition=_string_prop(elem, "WhileController.condition"),
        children=_parse_tg_children(hash_tree, http_defaults),
    )


def _parse_throughput_controller(elem, hash_tree, http_defaults) -> ThroughputControllerModel:
    return ThroughputControllerModel(
        enabled=_enabled_attr(elem),
        name=_testname_attr(elem) or "Throughput Controller",
        style=_int_prop(elem, "ThroughputController.style", 0),
        percent_throughput=_string_prop(elem, "ThroughputController.percentThroughput", "100.0"),
        per_thread=_bool_prop(elem, "ThroughputController.perThread"),
        children=_parse_tg_children(hash_tree, http_defaults),
    )


_CONTROLLER_PARSERS = {
    "GenericController": _parse_generic_controller,
    "LogicControllerGui": _parse_generic_controller,
    "LoopControlPanel": _parse_loop_controller,
    "IfControllerPanel": _parse_if_controller,
    "WhileControllerGui": _parse_while_controller,
    "ThroughputControllerGui": _parse_throughput_controller,
    # RecordController (RecordingController gui): se trata como GenericController
    # para preservar samplers anidados en el round-trip. Sin esto, los 6 samplers
    # generados por el Recorder de JMeter se perderían si el TG anfitrión está
    # disabled (que es el caso típico tras una grabación).
    "RecordController": _parse_generic_controller,
}


# ============================================================================
# Parser de children de un Thread Group / Controller (mezcla samplers/controllers)
# ============================================================================

def _parse_tg_children(hash_tree, http_defaults: Optional[HttpDefaultsModel]) -> List[TGChild]:
    """Recorre el hashTree de un ThreadGroup o Controller. Mezcla samplers, controllers y unsupported."""
    if hash_tree is None:
        return []
    result = []
    order = 0
    for elem, child_ht in _walk_hashtree_children(hash_tree):
        guiclass = _guiclass_attr(elem)
        testclass = _testclass_attr(elem)

        if "HTTPSampler" in testclass or "HttpTestSampleGui" in guiclass:
            sampler = _parse_http_sampler(elem, child_ht)
            result.append(TGChild(type="sampler", order=order, sampler=sampler))
        elif guiclass in _CONTROLLER_PARSERS:
            parser_fn = _CONTROLLER_PARSERS[guiclass]
            ctrl = parser_fn(elem, child_ht, http_defaults)
            result.append(TGChild(type="controller", order=order, controller=ctrl))
        else:
            # Unsupported dentro del thread group / controller
            unsupp = UnsupportedElement(
                kind=guiclass or elem.tag,
                name=_testname_attr(elem) or None,
                reason=f"Elemento '{guiclass or elem.tag}' no soportado dentro de Thread Group",
                severity="info",
                raw_xml=_raw_xml(elem),
            )
            result.append(TGChild(type="unsupported", order=order, unsupported=unsupp))
        order += 1
    return result


# ============================================================================
# Parser de Listeners (top-level)
# ============================================================================

_LISTENER_KIND_MAP = {
    "ViewResultsFullVisualizer": "view_results_tree",
    "SummaryReport": "summary_report",
    "StatVisualizer": "aggregate_report",
    "GraphVisualizer": "graph_results",
    "kg.apc.jmeter.vizualizers.ResponseTimesOverTimeGui": "kg_apc_response_times_over_time",
    "kg.apc.jmeter.vizualizers.ResponseCodesPerSecondGui": "kg_apc_response_codes_per_second",
    "kg.apc.jmeter.vizualizers.TransactionsPerSecondGui": "kg_apc_transactions_per_second",
    "kg.apc.jmeter.vizualizers.ThreadsStateOverTimeGui": "kg_apc_active_threads_over_time",
    "kg.apc.jmeter.vizualizers.HitsPerSecondGui": "kg_apc_hits_per_second",
}


def _parse_listener(elem) -> ListenerModel:
    guiclass = _guiclass_attr(elem)
    kind = _LISTENER_KIND_MAP.get(guiclass, "other")
    return ListenerModel(
        kind=kind,
        guiclass=guiclass,
        name=_testname_attr(elem) or "Listener",
        enabled=_enabled_attr(elem),
        filename=_string_prop(elem, "filename") or None,
        raw_xml=_raw_xml(elem),
    )


# ============================================================================
# Metadata: variables referenced / defined / undefined
# ============================================================================

_VAR_REF_RE = re.compile(r'\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}')


def _compute_metadata(structure: AIScriptStructure, jmx_text: str, warnings: List[str]) -> StructureMetadata:
    referenced = set(_VAR_REF_RE.findall(jmx_text))

    defined = set()
    # UDV
    for v in structure.user_defined_variables:
        defined.add(v.name)
    # CSV columns
    for ds in structure.csv_data_sets:
        defined.update(ds.variable_names)
    # Extractor refnames (recorrer thread groups)
    def collect_extractors(children):
        for ch in children:
            if ch.type == "sampler" and ch.sampler:
                for sc in ch.sampler.children:
                    if isinstance(sc.data, (RegexExtractorModel, JsonExtractorModel, XPathExtractorModel, BoundaryExtractorModel)):
                        if sc.data.refname:
                            defined.add(sc.data.refname)
            elif ch.type == "controller" and ch.controller:
                collect_extractors(ch.controller.children)

    for tg in structure.thread_groups:
        collect_extractors(tg.children)

    undefined = sorted(referenced - defined)
    unmapped_count = len(structure.unmapped)
    # Contar unmapped dentro de samplers también
    for tg in structure.thread_groups:
        for ch in tg.children:
            if ch.type == "sampler" and ch.sampler:
                for sc in ch.sampler.children:
                    if isinstance(sc.data, UnsupportedElement):
                        unmapped_count += 1

    return StructureMetadata(
        jmx_version="5.6.3",
        parsed_at=datetime.utcnow(),
        referenced_variables=sorted(referenced),
        defined_variables=sorted(defined),
        undefined_variables=undefined,
        has_unmapped=unmapped_count > 0,
        unmapped_count=unmapped_count,
        parse_warnings=warnings,
    )


# ============================================================================
# Orquestador principal
# ============================================================================

def parse_jmx_to_structure(jmx_text: str) -> AIScriptStructure:
    """
    Parsea un JMX completo (string XML) a AIScriptStructure.

    Args:
        jmx_text: contenido raw del JMX.

    Returns:
        AIScriptStructure con todo lo soportado parseado + unmapped[] para el resto.

    Raises:
        ValueError: si el XML está mal formado.
    """
    warnings = []

    try:
        # lxml es más tolerante con CDATA que xml.etree
        parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
        root = etree.fromstring(jmx_text.encode("utf-8"), parser)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"JMX XML mal formado: {e}")

    # Estructura JMeter: <jmeterTestPlan><hashTree><TestPlan/><hashTree>...</hashTree></hashTree></jmeterTestPlan>
    outer_ht = root.find("./hashTree")
    if outer_ht is None:
        raise ValueError("JMX sin hashTree raíz")

    # Primer elemento del hashTree raíz es el TestPlan
    pairs = _walk_hashtree_children(outer_ht)
    if not pairs:
        warnings.append("JMX vacío: sin TestPlan encontrado")
        return AIScriptStructure(metadata=_compute_metadata(AIScriptStructure(), jmx_text, warnings))

    test_plan_elem, test_plan_ht = pairs[0]
    test_plan = _parse_test_plan(test_plan_elem)

    # HF16: UDV embebido en el slot inline del TestPlan (Patrón B). Se fusiona más
    # abajo con el Patrón A (bloque <Arguments> hermano) sin duplicar por nombre.
    embedded_udv = _parse_embedded_test_plan_udv(test_plan_elem)

    # Recorrer hijos del TestPlan
    structure_data: Dict[str, Any] = {
        "test_plan": test_plan,
        "user_defined_variables": [],
        "http_defaults": None,
        "cookie_manager": None,
        "cache_manager": None,
        "csv_data_sets": [],
        "thread_groups": [],
        "config_elements": [],
        "listeners": [],
        "unmapped": [],
    }

    http_defaults: Optional[HttpDefaultsModel] = None

    for elem, child_ht in _walk_hashtree_children(test_plan_ht):
        guiclass = _guiclass_attr(elem)
        testclass = _testclass_attr(elem)
        testname = _testname_attr(elem)

        # User Defined Variables top-level (Arguments con testclass=Arguments)
        if "Arguments" in testclass and "ArgumentsPanel" in guiclass and "User Defined Variables" in testname:
            structure_data["user_defined_variables"].extend(_parse_arguments_collection(elem))
        elif "Arguments" in testclass and "User Defined Variables" in testname:
            structure_data["user_defined_variables"].extend(_parse_arguments_collection(elem))

        # HTTP Request Defaults
        elif "HttpDefaultsGui" in guiclass or "ConfigTestElement" in testclass and "HTTPSamplerProxy" not in testclass:
            if "Http" in guiclass or "HTTPSampler" in _string_prop(elem, ""):
                http_defaults = _parse_http_defaults(elem)
                structure_data["http_defaults"] = http_defaults

        # Cookie Manager
        elif "CookiePanel" in guiclass or "CookieManager" in testclass:
            structure_data["cookie_manager"] = _parse_cookie_manager(elem)

        # Cache Manager
        elif "CacheManagerGui" in guiclass or "CacheManager" in testclass:
            structure_data["cache_manager"] = _parse_cache_manager(elem)

        # CSV Data Set
        elif "CSVDataSet" in testclass or "TestBeanGUI" in guiclass and "CSV" in testname:
            structure_data["csv_data_sets"].append(_parse_csv_dataset(elem))

        # Thread Groups (estándar + stepping)
        elif "ThreadGroup" in testclass or "ThreadGroupGui" in guiclass or "SteppingThreadGroup" in guiclass:
            tg = _parse_thread_group(elem, child_ht, http_defaults)
            structure_data["thread_groups"].append(tg)

        # Listeners (ResultCollector)
        elif "ResultCollector" in testclass:
            structure_data["listeners"].append(_parse_listener(elem))

        # Resto → unmapped top-level
        else:
            structure_data["unmapped"].append(UnsupportedElement(
                kind=guiclass or testclass or elem.tag,
                name=testname or None,
                reason=f"Elemento top-level '{guiclass or testclass}' no soportado",
                severity="info" if "Recording" in guiclass or "Proxy" in guiclass else "warning",
                raw_xml=_raw_xml(elem),
            ))

    # HF16: fusionar UDV del Patrón B (embebido) sin duplicar las del Patrón A
    # (bloque <Arguments> hermano, ya recolectadas en el loop). El Patrón A gana
    # en caso de colisión de nombre por ser el bloque canónico.
    existing_udv_names = {v.name for v in structure_data["user_defined_variables"]}
    for v in embedded_udv:
        if v.name not in existing_udv_names:
            structure_data["user_defined_variables"].append(v)
            existing_udv_names.add(v.name)

    structure = AIScriptStructure(**structure_data)
    structure.metadata = _compute_metadata(structure, jmx_text, warnings)
    return structure
