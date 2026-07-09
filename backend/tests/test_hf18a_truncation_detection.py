"""Tests HF18a: deteccion extendida de truncacion.

Sprint 2.7b solo detectaba truncacion por finish_reason="length". gpt-4o
presenta un failure mode conocido: con prompts densos y HARs grandes devuelve
finish_reason="stop" (dice que termino) pero corta el JMX antes de
</jmeterTestPlan>. HF18a extiende _detect_truncation para reconocer ese caso
("stop_mentiroso") y disparar la misma auto-continuacion del Sprint 2.7b.
"""
from app.api.v1.endpoints.script_ai import _detect_truncation


JMX_INCOMPLETO = """```xml
<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <TestPlan testname="Test"/>
    <hashTree>
      <HTTPSamplerProxy testname="1. Sampler 1"/>
      <hashTree/>
      <HTTPSamplerProxy testname="2. Sampler 2"/>
      <hashTree/>
      <HTTPSamplerProxy testname="3. Sampler 3">
"""  # cortado a media tag, sin </jmeterTestPlan>


JMX_COMPLETO = """```xml
<?xml version="1.0"?>
<jmeterTestPlan>
  <hashTree>
    <TestPlan/>
    <hashTree>
      <HTTPSamplerProxy testname="1. Sampler"/>
      <hashTree/>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
```
"""


def test_detect_truncation_length_activa_continuacion():
    """Caso clasico Sprint 2.7a: finish_reason=length + XML sin cerrar."""
    is_trunc, samplers, ttype = _detect_truncation(JMX_INCOMPLETO, finish_reason="length")
    assert is_trunc is True
    assert samplers == 3
    assert ttype == "length"


def test_detect_truncation_stop_mentiroso_HF18a():
    """Caso nuevo HF18a: finish_reason=stop pero XML sin cerrar."""
    is_trunc, samplers, ttype = _detect_truncation(JMX_INCOMPLETO, finish_reason="stop")
    assert is_trunc is True
    assert samplers == 3
    assert ttype == "stop_mentiroso"


def test_detect_truncation_completo_stop_no_activa():
    """finish_reason=stop + XML bien cerrado = no truncacion."""
    is_trunc, samplers, ttype = _detect_truncation(JMX_COMPLETO, finish_reason="stop")
    assert is_trunc is False
    assert ttype == "no_truncation"


def test_detect_truncation_completo_length_no_activa():
    """Edge case: finish_reason=length pero XML SI cierra bien = no truncacion."""
    is_trunc, samplers, ttype = _detect_truncation(JMX_COMPLETO, finish_reason="length")
    assert is_trunc is False


def test_detect_truncation_sin_xml_no_activa():
    """Response sin XML alguno no es truncacion."""
    is_trunc, samplers, ttype = _detect_truncation("just plain text response", finish_reason="stop")
    assert is_trunc is False
    assert ttype == "no_xml"


def test_detect_truncation_finish_reason_desconocido():
    """finish_reason desconocido + XML sin cerrar = tratado como truncado (defensivo)."""
    is_trunc, samplers, ttype = _detect_truncation(JMX_INCOMPLETO, finish_reason=None)
    assert is_trunc is True
    assert ttype == "unknown_no_close"


def test_detect_truncation_compat_signature_sin_finish_reason():
    """Backward compat: llamadas sin finish_reason siguen funcionando (Sprint 2.7a)."""
    is_trunc, samplers, ttype = _detect_truncation(JMX_INCOMPLETO)
    assert is_trunc is True  # detecta por XML sin cerrar aunque no sepa finish_reason
