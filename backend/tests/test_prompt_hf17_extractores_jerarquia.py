"""Tests HF17: extractores obligatorios + jerarquía de prioridades en prompts."""
import pytest


def test_prompt_conservative_incluye_jerarquia_explicita():
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE
    # Jerarquía P1-P5
    assert "P1" in p and "P2" in p and "P3" in p and "P4" in p and "P5" in p
    assert "JERARQUÍA" in p.upper() or "jerarquia" in p.lower()


def test_prompt_conservative_bodies_es_P1():
    """P1 debe ser sobre bodies (más alta prioridad)."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE
    # Buscar bloque P1 y verificar que menciona bodies
    idx = p.find("P1")
    if idx > 0:
        window = p[idx:idx + 400].lower()
        assert "body" in window or "bodies" in window or "udv vac" in window


def test_prompt_conservative_extractores_es_P2():
    """P2 debe ser sobre extractores/correlación."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE
    idx = p.find("P2")
    if idx > 0:
        window = p[idx:idx + 400].lower()
        assert "extract" in window or "correlac" in window or "token" in window


def test_prompt_conservative_ejemplo_correcto_extractor():
    """Debe incluir ejemplo XML de JSONPostProcessor o RegexExtractor para guiar al modelo."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE
    assert "JSONPostProcessor" in p or "RegexExtractor" in p
    assert "referenceNames" in p or "refname" in p


def test_prompt_conservative_prohibe_bodys_declarados_no_usados():
    """Debe advertir sobre UDV declaradas y no usadas."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE.lower()
    # Debe mencionar el caso "declarado pero no usado"
    assert "no hay" in p or "no referenciad" in p or "no usa" in p or "desperdici" in p


def test_prompt_conservative_checkpoint_incluye_extractores():
    """CHECKPOINT debe verificar existencia de extractores tras auth."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE
    idx = p.upper().find("CHECKPOINT")
    if idx > 0:
        window = p[idx:idx + 1500].lower()
        assert "extractor" in window or "token" in window
        assert "auth" in window


def test_prompt_base_menciona_extractores_criticos():
    """SYSTEM_PROMPT base también debe reforzar extractores post-HF17."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT
    p = SYSTEM_PROMPT.lower()
    assert "extractor" in p
    assert "access_token" in p or "authtoken" in p or "cognito" in p or "bearer" in p


def test_prompt_conservative_menciona_cognito_como_ejemplo():
    """Debe mencionar Cognito como caso concreto (patrón común)."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE
    # Al menos alguno de estos patrones típicos de Cognito
    patrones = ["cognito", "AccessToken", "IdToken", "AuthenticationResult", "RespondToAuthChallenge"]
    matches = sum(1 for pat in patrones if pat in p)
    assert matches >= 1, f"Solo encontró {matches} referencias a patrones de Cognito"


def test_prompt_conservative_numero_minimo_extractores():
    """Debe instruir número mínimo de extractores si hay auth."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE.lower()
    # Debe mencionar "al menos 1", "mínimo" o números
    assert "al menos" in p or "mínimo" in p or "1 extractor" in p


def test_prompt_conservative_regla_prefiere_menos_samplers_con_extractores():
    """Debe instruir preferir menos samplers CON extractores sobre más SIN."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT_CONSERVATIVE
    p = SYSTEM_PROMPT_CONSERVATIVE.lower()
    # Buscar la instrucción de trade-off
    assert ("menos samplers" in p and "extractor" in p) or ("elige" in p and "extractor" in p)
