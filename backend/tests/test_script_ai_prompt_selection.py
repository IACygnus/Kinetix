"""Tests del selector adaptativo de SYSTEM_PROMPT (Sprint 2.7c)."""
from app.api.v1.endpoints.script_ai import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_CONSERVATIVE,
    _LARGE_INPUT_BYTE_THRESHOLD,
    _MANY_TRANSACTIONS_THRESHOLD,
    _detect_large_input,
    _select_system_prompt,
)


def test_detect_large_input_no_file():
    """Sin archivo -> no se considera grande."""
    is_large, reason = _detect_large_input("Crea un script simple", None)
    assert is_large is False
    assert reason == ""


def test_detect_large_input_pequeno():
    """Archivo de 5KB no es grande."""
    is_large, _ = _detect_large_input("test", "x" * 5000)
    assert is_large is False


def test_detect_large_input_por_bytes():
    """Archivo >20KB se considera grande."""
    is_large, reason = _detect_large_input("test", "x" * 25000)
    assert is_large is True
    assert "bytes" in reason


def test_detect_large_input_por_transacciones():
    """HAR con >8 transacciones es grande aunque sea pequeno en bytes."""
    har = "[" + ('"request"' * 10) + "]"  # 10 transacciones, ~100 bytes
    assert len(har.encode("utf-8")) < _LARGE_INPUT_BYTE_THRESHOLD
    is_large, reason = _detect_large_input("test", har)
    assert is_large is True
    assert "transacciones" in reason


def test_detect_large_input_transacciones_en_umbral_no_dispara():
    """Exactamente 8 transacciones no supera el umbral (> estricto)."""
    har = "[" + ('"request"' * _MANY_TRANSACTIONS_THRESHOLD) + "]"
    is_large, _ = _detect_large_input("test", har)
    assert is_large is False


def test_select_prompt_standard_para_input_pequeno():
    """Input pequeno -> prompt estandar."""
    prompt, meta = _select_system_prompt("test prompt", None)
    assert prompt is SYSTEM_PROMPT
    assert meta["prompt_mode"] == "standard"
    assert meta["large_input_reason"] is None


def test_select_prompt_conservative_para_input_grande():
    """Input grande -> prompt conservador."""
    prompt, meta = _select_system_prompt("test", "x" * 30000)
    assert prompt is SYSTEM_PROMPT_CONSERVATIVE
    assert meta["prompt_mode"] == "conservative"
    assert meta["large_input_reason"]


def test_prompt_conservative_menciona_economia():
    """El prompt conservador instruye economia de tokens."""
    assert "ECONOMÍA DE TOKENS" in SYSTEM_PROMPT_CONSERVATIVE
    assert "Bodies grandes" in SYSTEM_PROMPT_CONSERVATIVE
    assert "Headers repetidos" in SYSTEM_PROMPT_CONSERVATIVE


def test_prompt_conservative_pide_jmx_cerrado():
    """El prompt conservador enfatiza JMX completo y cerrado."""
    assert "</jmeterTestPlan>" in SYSTEM_PROMPT_CONSERVATIVE
    assert "COMPLETO" in SYSTEM_PROMPT_CONSERVATIVE.upper()
