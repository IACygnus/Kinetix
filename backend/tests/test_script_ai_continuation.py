"""Tests del flujo de auto-continuacion de JMX parcial (Sprint 2.7b).

Cubren los helpers puros del ensamblador y la construccion del prompt de
continuacion. La orquestacion completa (_try_continue_truncated_generation)
depende de _call_ai (OpenAI/Gemini real), por lo que su happy-path se valida
indirectamente a traves de los helpers que ensambla.
"""
from app.api.v1.endpoints.script_ai import (
    _assemble_continued_jmx,
    _build_continuation_messages,
    _extract_continuation_xml,
    _extract_partial_xml,
)


PARTIAL_TRUNCATED = """```xml
<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan>
  <hashTree>
    <TestPlan testname="Test"/>
    <hashTree>
      <HTTPSamplerProxy testname="1. Sampler 1">
        <stringProp name="HTTPSampler.path">/api/v1/users</stringProp>
"""  # cortado a media estructura


CONTINUATION_RESPONSE = """```xml
      </HTTPSamplerProxy>
      <hashTree/>
      <HTTPSamplerProxy testname="2. Sampler 2"/>
      <hashTree/>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
````
"""


# ---------------------------------------------------------------------------
# _extract_partial_xml
# ---------------------------------------------------------------------------

def test_extract_partial_xml_with_fence():
    result = _extract_partial_xml(PARTIAL_TRUNCATED)
    assert "<?xml" in result
    assert "<jmeterTestPlan>" in result


def test_extract_partial_xml_no_xml_returns_empty():
    assert _extract_partial_xml("Just plain text without XML") == ""


def test_extract_partial_xml_drops_leading_fence():
    # El fence ```xml de apertura no debe quedar dentro del XML extraido.
    result = _extract_partial_xml(PARTIAL_TRUNCATED)
    assert not result.startswith("```")


# ---------------------------------------------------------------------------
# _extract_continuation_xml
# ---------------------------------------------------------------------------

def test_extract_continuation_xml_with_fence():
    result = _extract_continuation_xml(CONTINUATION_RESPONSE)
    assert "</jmeterTestPlan>" in result
    assert "```" not in result  # fence removido


def test_extract_continuation_xml_no_fence():
    raw = "<hashTree/></jmeterTestPlan>"
    assert _extract_continuation_xml(raw) == raw


# ---------------------------------------------------------------------------
# _assemble_continued_jmx
# ---------------------------------------------------------------------------

def test_assemble_produces_closed_jmx():
    partial = _extract_partial_xml(PARTIAL_TRUNCATED)
    continuation = _extract_continuation_xml(CONTINUATION_RESPONSE)
    assembled = _assemble_continued_jmx(partial, continuation)
    assert "<?xml" in assembled
    assert "</jmeterTestPlan>" in assembled
    assert assembled.count("<jmeterTestPlan>") == 1  # una sola apertura


# ---------------------------------------------------------------------------
# _build_continuation_messages
# ---------------------------------------------------------------------------

def test_build_continuation_messages_structure():
    messages = _build_continuation_messages(
        original_prompt="Crea un script para mi API",
        file_content=None,
        partial_xml="<?xml ... <HTTPSamplerProxy testname='1. Auth'/>",
        samplers_done=1,
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "NO repitas" in messages[0]["content"]
    assert "1 samplers parciales" in messages[1]["content"]
    assert "Crea un script para mi API" in messages[1]["content"]


def test_build_continuation_messages_tail_limit():
    huge_partial = "<?xml ...\n" + ("X" * 5000)
    messages = _build_continuation_messages(
        original_prompt="test",
        file_content=None,
        partial_xml=huge_partial,
        samplers_done=0,
    )
    user_content = messages[1]["content"]
    # Solo el tail (<= 2000 chars) entra, no el partial completo.
    assert len(user_content) < 5000 + 2000


def test_build_continuation_messages_mentions_file_without_inlining_it():
    # Con archivo, se menciona su tamano pero NO se reinyecta su contenido.
    big_file = "REFERENCE-" + ("Y" * 10000)
    messages = _build_continuation_messages(
        original_prompt="test",
        file_content=big_file,
        partial_xml="<?xml ...",
        samplers_done=2,
    )
    user_content = messages[1]["content"]
    assert "Archivo de referencia ya analizado" in user_content
    assert "YYYY" not in user_content  # el contenido del archivo no se reinyecta
