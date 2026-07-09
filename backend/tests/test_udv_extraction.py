"""
Tests de extracción dual de UDV (HF16).

Bug 2B: el parser detectaba UDV solo en el bloque <Arguments> hermano del
TestPlan (Patrón A). La IA a veces genera el patrón embebido dentro del TestPlan
(<elementProp name="TestPlan.user_defined_variables">, Patrón B), que quedaba sin
detectar → el editor reportaba "N variables sin definir" en falso.

Bug 2A: refuerzo de prompts para que los bodies en UDV lleven valor real, no vacío.
"""
from xml.etree import ElementTree as ET  # noqa: F401  (compat con imports del template)

from app.services.engine.jmx_to_structure import (
    parse_jmx_to_structure,
    _parse_embedded_test_plan_udv,
)


JMX_PATRON_A = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test Plan"/>
    <hashTree>
      <Arguments guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables">
        <collectionProp name="Arguments.arguments">
          <elementProp name="host" elementType="Argument">
            <stringProp name="Argument.name">host</stringProp>
            <stringProp name="Argument.value">api.example.com</stringProp>
          </elementProp>
          <elementProp name="port" elementType="Argument">
            <stringProp name="Argument.name">port</stringProp>
            <stringProp name="Argument.value">443</stringProp>
          </elementProp>
        </collectionProp>
      </Arguments>
      <hashTree/>
    </hashTree>
  </hashTree>
</jmeterTestPlan>"""


# Patrón B: UDV embebido en el slot inline del TestPlan. El comentario referencia
# ${host_main} y ${BODY_SAMPLER_1} para verificar que NO caen en undefined_variables.
JMX_PATRON_B = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test Plan">
      <stringProp name="TestPlan.comments">flujo usa ${host_main} y body ${BODY_SAMPLER_1}</stringProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments">
        <collectionProp name="Arguments.arguments">
          <elementProp name="host_main" elementType="Argument">
            <stringProp name="Argument.name">host_main</stringProp>
            <stringProp name="Argument.value">webfly-b2.example.com</stringProp>
          </elementProp>
          <elementProp name="BODY_SAMPLER_1" elementType="Argument">
            <stringProp name="Argument.name">BODY_SAMPLER_1</stringProp>
            <stringProp name="Argument.value">{"user":"test"}</stringProp>
          </elementProp>
        </collectionProp>
      </elementProp>
    </TestPlan>
    <hashTree/>
  </hashTree>
</jmeterTestPlan>"""


JMX_UDV_VACIO = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test Plan">
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments">
        <collectionProp name="Arguments.arguments">
          <elementProp name="BODY_SAMPLER_1" elementType="Argument">
            <stringProp name="Argument.name">BODY_SAMPLER_1</stringProp>
            <stringProp name="Argument.value"></stringProp>
          </elementProp>
        </collectionProp>
      </elementProp>
    </TestPlan>
    <hashTree/>
  </hashTree>
</jmeterTestPlan>"""


def test_extract_udv_patron_a_arguments_sibling():
    """El patrón moderno con <Arguments> hermano debe extraer variables (regresión)."""
    structure = parse_jmx_to_structure(JMX_PATRON_A)
    vars = structure.user_defined_variables
    assert len(vars) == 2
    assert any(v.name == "host" and v.value == "api.example.com" for v in vars)
    assert any(v.name == "port" and v.value == "443" for v in vars)


def test_extract_udv_patron_b_embedded_en_testplan():
    """El patrón embebido que la IA genera debe extraer variables (HF16 fix Bug 2B)."""
    structure = parse_jmx_to_structure(JMX_PATRON_B)
    vars = structure.user_defined_variables
    assert len(vars) == 2
    assert any(v.name == "host_main" and v.value == "webfly-b2.example.com" for v in vars)
    assert any(v.name == "BODY_SAMPLER_1" for v in vars)


def test_patron_b_no_reporta_falsos_undefined():
    """Vars definidas en el slot embebido y referenciadas NO deben caer en undefined."""
    structure = parse_jmx_to_structure(JMX_PATRON_B)
    undefined = structure.metadata.undefined_variables
    # Ambas están referenciadas en el comentario Y definidas en la UDV embebida.
    assert "host_main" not in undefined
    assert "BODY_SAMPLER_1" not in undefined
    assert undefined == []


def test_extract_udv_detecta_valor_vacio():
    """UDV embebida con Argument.value vacío se detecta como variable con value=''."""
    structure = parse_jmx_to_structure(JMX_UDV_VACIO)
    vars = structure.user_defined_variables
    assert len(vars) == 1
    assert vars[0].name == "BODY_SAMPLER_1"
    assert vars[0].value == ""  # detectado como vacío


def test_helper_embedded_udv_directo():
    """El helper _parse_embedded_test_plan_udv extrae del elementProp inline."""
    from lxml import etree
    root = etree.fromstring(JMX_PATRON_B.encode("utf-8"))
    test_plan_elem = root.find(".//TestPlan")
    vars = _parse_embedded_test_plan_udv(test_plan_elem)
    assert {v.name for v in vars} == {"host_main", "BODY_SAMPLER_1"}
    # Sin slot embebido → lista vacía (no explota).
    root_a = etree.fromstring(JMX_PATRON_A.encode("utf-8"))
    tp_a = root_a.find(".//TestPlan")
    assert _parse_embedded_test_plan_udv(tp_a) == []


def test_prompt_conservative_prohibe_udv_vacia():
    """SYSTEM_PROMPT_CONSERVATIVE debe prohibir UDV con valor vacío (Bug 2A)."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE.lower()
    assert "vac" in p or "placeholder" in p  # "vacío"/"vacia"/"placeholder"
    assert "inejecutable" in p or "prohibido" in p


def test_prompt_base_menciona_bodies_reales():
    """SYSTEM_PROMPT base también debe exigir que los bodies sean reales (Bug 2A)."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT
    p = SYSTEM_PROMPT.lower()
    assert "body" in p or "bodies" in p
    assert "real" in p or "completo" in p
