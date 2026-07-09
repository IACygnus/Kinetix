"""Tests del manejo de truncacion en /generate y /generate-from-file (Sprint 2.7a).

Cubre:
- _detect_truncation: distingue una respuesta cortada a media XML de una completa.
- _extract_jmx_and_explanation: no extrae JMX cuando falta </jmeterTestPlan>.
- OPENAI_MAX_TOKENS: techos dinamicos por modelo usados ahora en generacion.

No se llaman los endpoints completos (requeririan mocks de DB + auth + OpenAI);
se valida la logica pura portada desde /refine y los valores de max_tokens.
"""
from app.api.v1.endpoints.script_ai import (
    _detect_truncation,
    _extract_jmx_and_explanation,
    _truncation_hint_message,
)
from app.services.ai.gemini import OPENAI_MAX_TOKENS, OPENAI_DEFAULT_MAX_TOKENS


SAMPLE_TRUNCATED_RESPONSE = """```xml
<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan>
  <hashTree>
    <TestPlan testname="Test"/>
    <hashTree>
      <HTTPSamplerProxy testname="1. Sampler 1"/>
      <hashTree/>
      <HTTPSamplerProxy testname="2. Sampler 2"/>
      <hashTree/>
      <HTTPSamplerProxy testname="3. Sampler 3"/>
"""  # truncado: nunca cierra jmeterTestPlan


SAMPLE_COMPLETE_RESPONSE = """Aqui esta el JMX:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan>
  <hashTree>
    <TestPlan testname="Test"/>
    <hashTree/>
  </hashTree>
</jmeterTestPlan>
```
"""


# ---------------------------------------------------------------------------
# _detect_truncation
# ---------------------------------------------------------------------------

# HF18a — el 3er valor de _detect_truncation paso de ser el mensaje al
# truncation_type. El mensaje al usuario ahora lo produce _truncation_hint_message.

def test_detect_truncation_flags_truncated_response():
    # Sin finish_reason (firma Sprint 2.7a original) -> "unknown_no_close".
    is_truncated, partial, ttype = _detect_truncation(SAMPLE_TRUNCATED_RESPONSE)
    assert is_truncated is True
    assert partial == 3
    assert ttype == "unknown_no_close"
    # El hint al usuario sigue siendo util y menciona el conteo de samplers.
    message = _truncation_hint_message(partial)
    assert "truncada" in message.lower()
    assert "3 samplers" in message


def test_detect_truncation_ignores_complete_response():
    is_truncated, partial, ttype = _detect_truncation(SAMPLE_COMPLETE_RESPONSE)
    assert is_truncated is False
    assert partial == 0
    assert ttype == "no_truncation"


def test_detect_truncation_ignores_non_xml_text():
    # Respuesta sin <?xml (la IA charlo en vez de generar) -> no es truncado.
    is_truncated, partial, ttype = _detect_truncation(
        "No pude generar el script porque el prompt es ambiguo."
    )
    assert is_truncated is False
    assert partial == 0
    assert ttype == "no_xml"


def test_detect_truncation_counts_partial_samplers():
    assert SAMPLE_TRUNCATED_RESPONSE.count("<HTTPSamplerProxy") == 3
    _, partial, _ = _detect_truncation(SAMPLE_TRUNCATED_RESPONSE)
    assert partial == 3


# ---------------------------------------------------------------------------
# _extract_jmx_and_explanation interaction
# ---------------------------------------------------------------------------

def test_extract_returns_empty_jmx_on_truncated():
    jmx, _ = _extract_jmx_and_explanation(SAMPLE_TRUNCATED_RESPONSE)
    assert jmx == ""  # sin cierre, no hay bloque extraible -> dispara truncado


def test_extract_returns_jmx_on_complete():
    jmx, _ = _extract_jmx_and_explanation(SAMPLE_COMPLETE_RESPONSE)
    assert jmx.startswith("<?xml")
    assert jmx.endswith("</jmeterTestPlan>")


# ---------------------------------------------------------------------------
# OPENAI_MAX_TOKENS (techo dinamico usado ahora en generacion)
# ---------------------------------------------------------------------------

def test_openai_max_tokens_for_gpt_4o():
    assert OPENAI_MAX_TOKENS["gpt-4o"] == 16384
    assert OPENAI_MAX_TOKENS["gpt-4o-mini"] == 16384
    assert OPENAI_DEFAULT_MAX_TOKENS == 4096


def test_openai_max_tokens_unknown_model_falls_back_to_default():
    val = OPENAI_MAX_TOKENS.get("modelo_inexistente", OPENAI_DEFAULT_MAX_TOKENS)
    assert val == OPENAI_DEFAULT_MAX_TOKENS == 4096


def test_openai_max_tokens_gpt_4o_beats_legacy_8192():
    # El cap legacy de generacion era 8192; gpt-4o ahora resuelve a 16384.
    assert OPENAI_MAX_TOKENS["gpt-4o"] > 8192
