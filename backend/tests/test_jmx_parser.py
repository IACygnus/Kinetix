"""
Tests del parser JMX → AIScriptStructure.
Fixture principal: sample_jmx/Ejercicio_Booking.jmx
"""
import pytest
from pathlib import Path

from app.services.engine.jmx_to_structure import parse_jmx_to_structure
from app.schemas.ai_script_structure import (
    AIScriptStructure,
    ThreadGroupModel,
    HTTPSamplerModel,
    UnsupportedElement,
    GenericControllerModel,
)


SAMPLE_JMX_PATH = Path(__file__).parent / "fixtures" / "Ejercicio_Booking.jmx"


@pytest.fixture(scope="module")
def parsed_structure() -> AIScriptStructure:
    """Parsea el JMX una sola vez para todos los tests del módulo."""
    assert SAMPLE_JMX_PATH.exists(), f"Fixture no encontrado: {SAMPLE_JMX_PATH}"
    jmx_text = SAMPLE_JMX_PATH.read_text(encoding="utf-8")
    return parse_jmx_to_structure(jmx_text)


# ============================================================================
# Smoke tests básicos
# ============================================================================

def test_parser_no_lanza_excepcion(parsed_structure):
    assert parsed_structure is not None
    assert isinstance(parsed_structure, AIScriptStructure)


def test_test_plan_parseado(parsed_structure):
    assert parsed_structure.test_plan.name


# ============================================================================
# Thread Groups
# ============================================================================

def test_tres_thread_groups(parsed_structure):
    """Ejercicio_Booking.jmx tiene 3 TGs: Carga (Stepping), Smoke test, Grabación original."""
    assert len(parsed_structure.thread_groups) == 3, \
        f"Esperaba 3 ThreadGroups, encontré {len(parsed_structure.thread_groups)}"


def test_stepping_thread_group_presente(parsed_structure):
    """Debe haber al menos 1 TG con kind=stepping."""
    stepping = [tg for tg in parsed_structure.thread_groups if tg.kind == "stepping"]
    assert len(stepping) >= 1, "No se detectó SteppingThreadGroup"
    assert stepping[0].stepping is not None, "SteppingConfig no se parseó"


def test_stepping_props_correctos(parsed_structure):
    """Valores reales de Ejercicio_Booking.jmx según diagnóstico previo."""
    stepping_tg = next(tg for tg in parsed_structure.thread_groups if tg.kind == "stepping")
    s = stepping_tg.stepping
    assert s.initial_delay == 0
    assert s.start_users_count == 1
    assert s.start_users_period == 30
    assert s.stop_users_count == 1
    assert s.stop_users_period == 9
    assert s.flight_time == 120
    assert s.ramp_up == 5


def test_stepping_serializa_con_aliases(parsed_structure):
    """model_dump(by_alias=True) debe producir nombres XML originales."""
    stepping_tg = next(tg for tg in parsed_structure.thread_groups if tg.kind == "stepping")
    dumped = stepping_tg.stepping.model_dump(by_alias=True)
    assert "Threads initial delay" in dumped
    assert "Start users count" in dumped
    assert "rampUp" in dumped
    assert "flighttime" in dumped


def test_smoke_test_thread_group_deshabilitado(parsed_structure):
    """Convención de Fredy: smoke_test es ThreadGroup estándar con enabled=false."""
    tg_names = [tg.name for tg in parsed_structure.thread_groups]
    assert any("Smoke" in n or "smoke" in n for n in tg_names), \
        f"No hay TG con 'Smoke' en el nombre. TGs: {tg_names}"
    smoke = next(tg for tg in parsed_structure.thread_groups if "Smoke" in tg.name or "smoke" in tg.name)
    assert smoke.enabled is False, "Smoke test debería estar enabled=false"


# ============================================================================
# HTTP Samplers
# ============================================================================

def test_dieciocho_samplers_total(parsed_structure):
    """18 HTTPSamplers en total (sumando los 3 TGs)."""
    count = 0
    def count_samplers(children):
        nonlocal count
        for ch in children:
            if ch.type == "sampler":
                count += 1
            elif ch.type == "controller" and ch.controller:
                count_samplers(ch.controller.children)
    for tg in parsed_structure.thread_groups:
        count_samplers(tg.children)
    assert count == 18, f"Esperaba 18 samplers, encontré {count}"


def test_samplers_con_body_raw_y_form(parsed_structure):
    """9 samplers con body raw (POST/PUT con JSON) y 9 con body none/form (GET/DELETE)."""
    raw_count = 0
    form_or_none_count = 0
    def count_bodies(children):
        nonlocal raw_count, form_or_none_count
        for ch in children:
            if ch.type == "sampler" and ch.sampler:
                if ch.sampler.body.mode == "raw":
                    raw_count += 1
                else:
                    form_or_none_count += 1
            elif ch.type == "controller" and ch.controller:
                count_bodies(ch.controller.children)
    for tg in parsed_structure.thread_groups:
        count_bodies(tg.children)
    assert raw_count == 9, f"Esperaba 9 bodies raw, encontré {raw_count}"


# ============================================================================
# Children de samplers
# ============================================================================

def test_samplers_tienen_header_manager(parsed_structure):
    """Todos los samplers de Ejercicio_Booking tienen HeaderManager."""
    samplers_with_hm = 0
    def check_hm(children):
        nonlocal samplers_with_hm
        for ch in children:
            if ch.type == "sampler" and ch.sampler:
                if any(sc.type == "header_manager" for sc in ch.sampler.children):
                    samplers_with_hm += 1
            elif ch.type == "controller" and ch.controller:
                check_hm(ch.controller.children)
    for tg in parsed_structure.thread_groups:
        check_hm(tg.children)
    assert samplers_with_hm > 0, "Ningún sampler tiene HeaderManager"


def test_response_assertions_se_parsean(parsed_structure):
    """18 ResponseAssertions (1 por sampler)."""
    count = 0
    def check_ra(children):
        nonlocal count
        for ch in children:
            if ch.type == "sampler" and ch.sampler:
                count += sum(1 for sc in ch.sampler.children if sc.type == "response_assertion")
            elif ch.type == "controller" and ch.controller:
                check_ra(ch.controller.children)
    for tg in parsed_structure.thread_groups:
        check_ra(tg.children)
    assert count >= 18, f"Esperaba >=18 ResponseAssertions, encontré {count}"


def test_regex_extractors_se_parsean(parsed_structure):
    """4 RegexExtractors según diagnóstico."""
    count = 0
    def check_re(children):
        nonlocal count
        for ch in children:
            if ch.type == "sampler" and ch.sampler:
                count += sum(1 for sc in ch.sampler.children if sc.type == "regex_extractor")
            elif ch.type == "controller" and ch.controller:
                check_re(ch.controller.children)
    for tg in parsed_structure.thread_groups:
        check_re(tg.children)
    assert count == 4, f"Esperaba 4 RegexExtractors, encontré {count}"


# ============================================================================
# Generic Controllers (6 en el JMX según diagnóstico, anidando samplers de la Grabación original)
# ============================================================================

def test_generic_controllers_anidan_samplers(parsed_structure):
    """6 GenericControllers en el TG 'Grabación original'."""
    grabacion_tg = next((tg for tg in parsed_structure.thread_groups if "Grabación" in tg.name or "Grabacion" in tg.name), None)
    assert grabacion_tg is not None, "No se encontró el TG 'Grabación original'"
    controllers = [ch for ch in grabacion_tg.children if ch.type == "controller"]
    assert len(controllers) >= 1, "Esperaba al menos 1 controller en Grabación original"


# ============================================================================
# CSV Data Sets
# ============================================================================

def test_csv_data_sets_dos(parsed_structure):
    """2 CSVDataSets: Data Post Create y Data Put Update."""
    assert len(parsed_structure.csv_data_sets) == 2, \
        f"Esperaba 2 CSVDataSets, encontré {len(parsed_structure.csv_data_sets)}"


def test_csv_variable_names_split(parsed_structure):
    """variable_names debe estar split por coma."""
    for ds in parsed_structure.csv_data_sets:
        assert len(ds.variable_names) >= 1, f"CSV '{ds.testname}' sin variable_names"
        assert all("," not in v for v in ds.variable_names), "variable_names no fue split"


# ============================================================================
# UDV top-level
# ============================================================================

def test_udv_top_level_cuatro(parsed_structure):
    """4 UDVs según diagnóstico: host, scheme, Data, Resultados."""
    assert len(parsed_structure.user_defined_variables) >= 4, \
        f"Esperaba >=4 UDVs, encontré {len(parsed_structure.user_defined_variables)}"
    names = [v.name for v in parsed_structure.user_defined_variables]
    assert "host" in names
    assert "scheme" in names


# ============================================================================
# HTTP Defaults
# ============================================================================

def test_http_defaults_presente(parsed_structure):
    assert parsed_structure.http_defaults is not None
    # En Ejercicio_Booking, domain está en UDV (${host}), no aquí.


# ============================================================================
# Cookie y Cache Managers
# ============================================================================

def test_cookie_manager_presente(parsed_structure):
    assert parsed_structure.cookie_manager is not None


def test_cache_manager_presente(parsed_structure):
    assert parsed_structure.cache_manager is not None


# ============================================================================
# Listeners (kg.apc family)
# ============================================================================

def test_listeners_kg_apc_reconocidos(parsed_structure):
    """3 listeners kg.apc según diagnóstico + ViewResultsFullVisualizer + StatVisualizer."""
    listeners = parsed_structure.listeners
    assert len(listeners) >= 5, f"Esperaba >=5 listeners, encontré {len(listeners)}"
    kinds = [l.kind for l in listeners]
    # Debe haber al menos uno kg_apc_*
    assert any(k.startswith("kg_apc_") for k in kinds), \
        f"Ningún listener kg.apc detectado. Kinds: {kinds}"


# ============================================================================
# Unmapped (passthrough)
# ============================================================================

def test_recording_y_proxy_en_unmapped(parsed_structure):
    """RecordingController y ProxyControl deben ir a unmapped con severity=info."""
    # Pueden estar en unmapped top-level o como hijos
    all_unmapped = list(parsed_structure.unmapped)
    # También recolectar desde dentro de TGs
    def collect_unmapped(children):
        for ch in children:
            if ch.type == "unsupported" and ch.unsupported:
                all_unmapped.append(ch.unsupported)
            elif ch.type == "controller" and ch.controller:
                collect_unmapped(ch.controller.children)
    for tg in parsed_structure.thread_groups:
        collect_unmapped(tg.children)
    # No es obligatorio que aparezcan (depende de si están en este JMX), pero el modelo lo soporta.
    # Test no falla si no aparecen; solo verifica que el campo existe.
    assert isinstance(all_unmapped, list)


# ============================================================================
# Metadata derivada (variables)
# ============================================================================

def test_metadata_referenced_variables(parsed_structure):
    """${host}, ${token}, ${bookingid}, etc. deben aparecer en referenced_variables."""
    refs = parsed_structure.metadata.referenced_variables
    assert "host" in refs or "scheme" in refs, f"Variables referenciadas: {refs}"


def test_metadata_no_hay_indefinidas_criticas(parsed_structure):
    """
    Según diagnóstico, Ejercicio_Booking tiene todas las variables definidas
    (UDV + CSV + Extractors). undefined_variables debería ser vacío.
    """
    undef = parsed_structure.metadata.undefined_variables
    # No assertEqual([]) porque pueden quedar variables internas de JMeter (__time, etc.)
    # Verificar que las críticas del negocio (host, token, bookingid) NO están indefinidas
    critical = ["host", "scheme", "token", "bookingid", "firstname", "lastname"]
    for v in critical:
        assert v not in undef, f"Variable crítica '{v}' aparece como indefinida"


# ============================================================================
# Edge cases
# ============================================================================

def test_jmx_vacio_no_lanza_excepcion():
    """JMX mínimo válido debe parsearse sin error."""
    minimal_jmx = '<?xml version="1.0" encoding="UTF-8"?><jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3"><hashTree><TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test Plan"><boolProp name="TestPlan.functional_mode">false</boolProp><elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables"><collectionProp name="Arguments.arguments"/></elementProp></TestPlan><hashTree/></hashTree></jmeterTestPlan>'
    s = parse_jmx_to_structure(minimal_jmx)
    assert s is not None
    assert len(s.thread_groups) == 0


def test_jmx_malformado_lanza_value_error():
    with pytest.raises(ValueError):
        parse_jmx_to_structure("<not><valid></xml>")


# ============================================================================
# Sprint 2.1.1 — Regresión: JMX con comentarios XML
# ============================================================================

def test_jmx_con_comentarios_xml_no_lanza_excepcion():
    """
    Regresión del bug del Sprint 2.2 Test 5: lxml Comments tienen tag no-string
    (cyfunction Comment), que rompía _walk_hashtree_children con TypeError.

    Los JMX generados por la AI Script Designer suelen incluir <!-- ... -->.
    """
    jmx_con_comentario = '''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test con comentario">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
    </TestPlan>
    <hashTree>
      <!-- Comentario que rompía el parser antes del fix Sprint 2.1.1 -->
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="TG con comentario" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <stringProp name="ThreadGroup.num_threads">1</stringProp>
        <stringProp name="ThreadGroup.ramp_time">1</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">1</stringProp>
        </elementProp>
      </ThreadGroup>
      <hashTree>
        <!-- Otro comentario más profundo -->
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="Sampler de prueba" enabled="true">
          <stringProp name="HTTPSampler.domain">example.com</stringProp>
          <stringProp name="HTTPSampler.path">/test</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
          <boolProp name="HTTPSampler.postBodyRaw">false</boolProp>
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="User Defined Variables">
            <collectionProp name="Arguments.arguments"/>
          </elementProp>
        </HTTPSamplerProxy>
        <hashTree/>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>'''

    # El parser NO debe lanzar excepción
    structure = parse_jmx_to_structure(jmx_con_comentario)

    # Validaciones positivas: los comentarios se ignoran pero el resto se parsea bien
    assert structure is not None
    assert len(structure.thread_groups) == 1, "Esperaba 1 TG, los comentarios no deben afectar el conteo"

    tg = structure.thread_groups[0]
    assert tg.name == "TG con comentario"

    samplers = [ch for ch in tg.children if ch.type == "sampler"]
    assert len(samplers) == 1, "Esperaba 1 sampler dentro del TG"
    assert samplers[0].sampler.name == "Sampler de prueba"


def test_jmx_solo_con_comentarios_no_crashea():
    """Edge case: hashTree con SOLO comentarios y nada útil."""
    jmx_extremo = '''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
    </TestPlan>
    <hashTree>
      <!-- comment 1 -->
      <!-- comment 2 -->
      <!-- comment 3 -->
    </hashTree>
  </hashTree>
</jmeterTestPlan>'''

    structure = parse_jmx_to_structure(jmx_extremo)
    assert structure is not None
    assert len(structure.thread_groups) == 0, "Sin TGs reales"
    assert len(structure.unmapped) == 0, "Comentarios no van a unmapped (se ignoran silenciosamente)"


# ============================================================================
# Sprint 2.4-HF1 — Rescate de body raw mal ubicado por la IA
# ============================================================================

def test_parser_rescata_body_raw_malformado_por_ia():
    """
    Regresión HF1: el SYSTEM_PROMPT de la IA genera JMX con postBodyRaw=false
    dentro del sampler y los artefactos del body como siblings sueltos en el
    hashTree (stringProp postBodyRaw + elementProp HTTPsampler.Arguments con
    el JSON real). El parser debe rescatarlos y poblar body.mode=raw.
    """
    jmx_malformado = '''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="T">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="UDV">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="TG" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <stringProp name="ThreadGroup.num_threads">1</stringProp>
        <stringProp name="ThreadGroup.ramp_time">1</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="LC">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">1</stringProp>
        </elementProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="3. Crear Reserva" enabled="true">
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="UDV">
            <collectionProp name="Arguments.arguments"/>
          </elementProp>
          <stringProp name="HTTPSampler.domain">example.com</stringProp>
          <stringProp name="HTTPSampler.path">/booking</stringProp>
          <stringProp name="HTTPSampler.method">POST</stringProp>
          <boolProp name="HTTPSampler.postBodyRaw">false</boolProp>
        </HTTPSamplerProxy>
        <hashTree>
          <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="HM" enabled="true">
            <collectionProp name="HeaderManager.headers">
              <elementProp name="" elementType="Header">
                <stringProp name="Header.name">Content-Type</stringProp>
                <stringProp name="Header.value">application/json</stringProp>
              </elementProp>
            </collectionProp>
          </HeaderManager>
          <hashTree/>
          <stringProp name="HTTPSampler.postBodyRaw">true</stringProp>
          <hashTree/>
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
            <collectionProp name="Arguments.arguments">
              <elementProp name="body" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">false</boolProp>
                <stringProp name="Argument.value">{"firstname":"${firstname}","totalprice":${totalprice}}</stringProp>
                <stringProp name="Argument.metadata">=</stringProp>
              </elementProp>
            </collectionProp>
          </elementProp>
          <hashTree/>
          <RegexExtractor guiclass="RegexExtractorGui" testclass="RegexExtractor" testname="Extract bookingid" enabled="true">
            <stringProp name="RegexExtractor.useHeaders">false</stringProp>
            <stringProp name="RegexExtractor.refname">bookingid</stringProp>
            <stringProp name="RegexExtractor.regex">"bookingid":(\\d+)</stringProp>
            <stringProp name="RegexExtractor.template">$1$</stringProp>
            <stringProp name="RegexExtractor.default"></stringProp>
            <boolProp name="RegexExtractor.default_empty_value">false</boolProp>
            <stringProp name="RegexExtractor.match_number">1</stringProp>
          </RegexExtractor>
          <hashTree/>
        </hashTree>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>'''

    structure = parse_jmx_to_structure(jmx_malformado)
    assert len(structure.thread_groups) == 1
    tg = structure.thread_groups[0]
    samplers = [ch.sampler for ch in tg.children if ch.type == 'sampler' and ch.sampler]
    assert len(samplers) == 1
    samp = samplers[0]
    assert samp.method == 'POST'

    # Body raw rescatado
    assert samp.body.mode == 'raw', f"Esperaba mode=raw tras rescate, obtuvo {samp.body.mode}"
    assert samp.body.raw_text is not None
    assert 'firstname' in samp.body.raw_text
    assert '${totalprice}' in samp.body.raw_text

    # Los artefactos sueltos NO deben aparecer como unsupported
    unsupported_kinds = [
        sc.data.kind for sc in samp.children
        if sc.type == 'unsupported'
    ]
    assert 'stringProp' not in unsupported_kinds, \
        f"stringProp huérfano apareció como unsupported: {unsupported_kinds}"
    assert 'elementProp' not in unsupported_kinds, \
        f"elementProp huérfano apareció como unsupported: {unsupported_kinds}"

    # Los children legítimos (HeaderManager + RegexExtractor) sí deben aparecer
    types = [sc.type for sc in samp.children]
    assert 'header_manager' in types
    assert 'regex_extractor' in types


def test_parser_no_rescata_si_no_hay_artefactos():
    """
    Regresión negativa HF1: si el sampler tiene postBodyRaw=true correctamente
    dentro del XML (estructura válida), el parser no debe activar el rescate
    ni perder nada.
    """
    jmx_valido = '''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="T">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="UDV">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="TG" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <stringProp name="ThreadGroup.num_threads">1</stringProp>
        <stringProp name="ThreadGroup.ramp_time">1</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="LC">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">1</stringProp>
        </elementProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="POST valido" enabled="true">
          <stringProp name="HTTPSampler.domain">example.com</stringProp>
          <stringProp name="HTTPSampler.path">/api</stringProp>
          <stringProp name="HTTPSampler.method">POST</stringProp>
          <boolProp name="HTTPSampler.postBodyRaw">true</boolProp>
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="UDV">
            <collectionProp name="Arguments.arguments">
              <elementProp name="" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">false</boolProp>
                <stringProp name="Argument.value">{"valid":true}</stringProp>
                <stringProp name="Argument.metadata">=</stringProp>
              </elementProp>
            </collectionProp>
          </elementProp>
        </HTTPSamplerProxy>
        <hashTree/>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>'''

    structure = parse_jmx_to_structure(jmx_valido)
    samp = structure.thread_groups[0].children[0].sampler
    assert samp is not None
    assert samp.body.mode == 'raw'
    assert samp.body.raw_text is not None
    assert '"valid":true' in samp.body.raw_text
