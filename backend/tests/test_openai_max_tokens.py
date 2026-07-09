"""Tests HF18b: verificar que gpt-4.1 esta registrado con 32K output.

El modelo activo del Disenador IA se escalo de gpt-4o (16K output) a gpt-4.1
(32K output) para resolver cobertura + truncacion con HARs enterprise. Estos
tests fijan (lock) los topes de output por modelo para que un cambio accidental
al dict OPENAI_MAX_TOKENS falle en CI.
"""


def test_openai_max_tokens_gpt_4_1_registrado():
    """gpt-4.1 debe estar en el dict con 32768 (doble de output vs gpt-4o)."""
    from app.services.ai.gemini import OPENAI_MAX_TOKENS
    assert "gpt-4.1" in OPENAI_MAX_TOKENS
    assert OPENAI_MAX_TOKENS["gpt-4.1"] == 32768


def test_openai_max_tokens_gpt_4_1_variantes_32k():
    """HF18b: las variantes gpt-4.1-mini/-nano tambien soportan 32K de output.

    Estaban infra-provisionadas (16384 / 8192): si se cambiara el modelo activo
    a una variante, truncaria sin causa visible. Se fijan en 32768.
    """
    from app.services.ai.gemini import OPENAI_MAX_TOKENS
    for variant in ("gpt-4.1-mini", "gpt-4.1-nano"):
        assert variant in OPENAI_MAX_TOKENS
        assert OPENAI_MAX_TOKENS[variant] == 32768


def test_openai_max_tokens_gpt_4o_mantiene_valor():
    """gpt-4o NO se toca: sigue disponible para rollback con 16384."""
    from app.services.ai.gemini import OPENAI_MAX_TOKENS
    assert OPENAI_MAX_TOKENS["gpt-4o"] == 16384
    assert OPENAI_MAX_TOKENS["gpt-4o-mini"] == 16384


def test_openai_max_tokens_default_no_cambia():
    """El default para modelos desconocidos sigue siendo 4096."""
    from app.services.ai.gemini import OPENAI_DEFAULT_MAX_TOKENS
    assert OPENAI_DEFAULT_MAX_TOKENS == 4096
