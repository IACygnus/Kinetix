"""Tests del SYSTEM_PROMPT mejorado para flujos enterprise (Sprint 2.8).

Verifican que ambos prompts (estandar y conservador) instruyan correlacion de
tokens, multi-dominio (UDV por dominio) y cobertura completa del flujo — los
3 bugs del caso Bancoomeva (docs/reports/comparativa-jmx-bancoomeva.md).
"""
from app.api.v1.endpoints.script_ai import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_CONSERVATIVE,
)


def test_prompt_base_incluye_reglas_correlacion():
    """SYSTEM_PROMPT debe instruir crear extractores para tokens."""
    p = SYSTEM_PROMPT.lower()
    assert "extractor" in p or "extract" in p
    assert "token" in p
    assert "bearer" in p or "authorization" in p


def test_prompt_base_incluye_reglas_multi_dominio():
    """SYSTEM_PROMPT debe instruir UDV por dominio."""
    p = SYSTEM_PROMPT
    assert "host_" in p or "UDV" in p
    assert "dominio" in p.lower()


def test_prompt_base_incluye_cobertura_completa():
    """SYSTEM_PROMPT debe instruir incluir TODOS los requests funcionales."""
    p = SYSTEM_PROMPT.lower()
    assert "todos" in p or "completo" in p
    assert "logout" in p or "cerrar" in p or "cerrarsesion" in p


def test_prompt_conservative_mantiene_correlacion():
    """El prompt conservador NO debe sacrificar correlacion de tokens."""
    p = SYSTEM_PROMPT_CONSERVATIVE.lower()
    assert "extractor" in p or "extract" in p
    assert "token" in p


def test_prompt_conservative_mantiene_multi_dominio():
    """El prompt conservador NO debe sacrificar multi-dominio."""
    p = SYSTEM_PROMPT_CONSERVATIVE
    assert "host_" in p.lower() or "udv" in p.lower()


def test_prompt_base_da_ejemplo_regex_extractor():
    """SYSTEM_PROMPT debe incluir ejemplo XML de extractor para guiar al modelo."""
    p = SYSTEM_PROMPT
    assert "RegexExtractor" in p
    assert "refname" in p


def test_prompt_base_lista_patrones_token_comunes():
    """SYSTEM_PROMPT debe mencionar patrones tipicos: access_token, authToken, sessionId."""
    p = SYSTEM_PROMPT.lower()
    patterns = ["access_token", "authtoken", "sessionid", "csrf", "jwt"]
    matches = sum(1 for pat in patterns if pat in p)
    assert matches >= 2, f"Solo encontro {matches} patrones de token mencionados"


def test_prompt_base_lista_subdominios_funcionales():
    """SYSTEM_PROMPT debe sugerir nombres descriptivos para subdominios."""
    p = SYSTEM_PROMPT
    subdomains = ["host_auth", "host_user", "host_products", "host_pagos", "host_main"]
    matches = sum(1 for sd in subdomains if sd in p)
    assert matches >= 2, f"Solo encontro {matches} ejemplos de subdominios"
