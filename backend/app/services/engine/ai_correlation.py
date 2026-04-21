# backend/app/services/engine/ai_correlation.py
"""
AI Correlation Service — Usa Gemini para detectar valores dinámicos en scripts.

Analiza el script_model y detecta patrones típicos de correlación:
- Session IDs, JWTs, CSRF tokens, ViewState, correlation IDs
- Sugiere variable_name, regex, extract_from y request donde aplicarlo

También implementa "Debug Script" que detecta recursos estáticos
que podrían haberse colado en el script (JS, CSS, analytics, etc.)
"""
import asyncio
import json
import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Prompt para correlación — few-shot con ejemplos reales
CORRELATION_PROMPT_TEMPLATE = """Eres un experto en performance testing con JMeter y correlación de variables dinámicas.

Analiza el siguiente script de performance testing y detecta todos los valores dinámicos que deben ser parametrizados mediante extractores de variables (correlación).

**Patrones a buscar:**
- Tokens de autenticación (JWT, Bearer, session tokens, API keys)
- CSRF tokens (X-CSRF-Token, _csrf, csrfToken, __RequestVerificationToken)
- Session IDs (JSESSIONID, PHPSESSID, ASP.NET_SessionId, sessionId)
- ViewState y valores de formularios ASP.NET
- Correlation IDs / Request IDs generados por el servidor
- Cualquier valor en el body o headers de response que aparezca en requests posteriores

**Script a analizar:**
{script_json}

**Responde ÚNICAMENTE con un JSON válido** con esta estructura exacta (sin texto adicional, sin markdown, sin backticks):
{{
  "correlations": [
    {{
      "variable_name": "auth_token",
      "description": "JWT de autenticación retornado en el login",
      "extract_from_request": 0,
      "extract_from": "body",
      "regex": "\"token\":\"([^\"]+)\"",
      "match_no": 1,
      "default_value": "",
      "used_in_requests": [1, 2, 3],
      "header_name": ""
    }}
  ],
  "analysis_summary": "Breve descripción de lo que encontró"
}}

Si no detectas correlaciones necesarias, retorna: {{"correlations": [], "analysis_summary": "No se detectaron valores dinámicos que requieran correlación."}}"""


# Prompt para debug — detectar recursos estáticos y duplicados
DEBUG_PROMPT_TEMPLATE = """Eres un experto en performance testing. Analiza el siguiente script y detecta problemas de calidad.

**Busca:**
1. Recursos estáticos que no deben estar en un load test: JS, CSS, imágenes, fuentes, analytics
2. Requests duplicados (misma URL y método)
3. Requests a dominios de terceros irrelevantes (CDNs, analytics, tracking)

**Script a analizar:**
{script_json}

**Responde ÚNICAMENTE con un JSON válido** (sin texto adicional, sin markdown, sin backticks):
{{
  "requests_to_remove": [0, 3, 5],
  "reasons": {{
    "0": "Recurso estático: archivo CSS",
    "3": "Tracker de analytics: Google Analytics",
    "5": "Duplicado del request 1"
  }},
  "analysis_summary": "Se detectaron N requests innecesarios"
}}

Si el script está bien, retorna: {{"requests_to_remove": [], "reasons": {{}}, "analysis_summary": "El script no contiene recursos estáticos ni duplicados."}}"""


class AICorrelationService:
    """
    Servicio de correlación inteligente usando Gemini.
    Llama directamente a la API de Gemini para prompts arbitrarios
    (el GeminiAnalyzer existente es para análisis de reportes, no prompts libres).
    """

    def __init__(self):
        self._available = False
        self._api_key = ""
        try:
            from app.core.config import settings
            self._api_key = settings.GEMINI_API_KEY or ""
            self._model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
            self._available = bool(self._api_key)
            if not self._available:
                logger.warning("AICorrelationService: GEMINI_API_KEY not configured")
        except Exception as e:
            logger.warning(f"AICorrelationService init error: {e}")

    async def correlate(self, script_model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analizar el script con Gemini y sugerir extractores de correlación.

        Returns:
            {"correlations": [...], "analysis_summary": "..."}
        """
        if not self._available:
            return {"correlations": [], "analysis_summary": "AI service not available", "error": "GEMINI_API_KEY not configured"}

        simplified = self._simplify_for_correlation(script_model)
        script_json = json.dumps(simplified, indent=2, ensure_ascii=False)
        prompt = CORRELATION_PROMPT_TEMPLATE.format(script_json=script_json)

        try:
            response_text = await self._call_gemini(prompt)
            result = self._parse_json_response(response_text)

            if "correlations" not in result:
                result["correlations"] = []
            if "analysis_summary" not in result:
                result["analysis_summary"] = "Analysis complete"

            logger.info(f"AI Correlation: found {len(result['correlations'])} correlations")
            return result

        except Exception as e:
            logger.error(f"AI Correlation error: {e}")
            return {
                "correlations": [],
                "analysis_summary": f"Error during analysis: {str(e)}",
                "error": str(e)
            }

    async def debug_script(self, script_model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analizar el script con Gemini y detectar requests a eliminar.

        Returns:
            {"requests_to_remove": [...], "reasons": {...}, "analysis_summary": "..."}
        """
        if not self._available:
            return {"requests_to_remove": [], "reasons": {}, "analysis_summary": "AI service not available", "error": "GEMINI_API_KEY not configured"}

        simplified = self._simplify_for_debug(script_model)
        script_json = json.dumps(simplified, indent=2, ensure_ascii=False)
        prompt = DEBUG_PROMPT_TEMPLATE.format(script_json=script_json)

        try:
            response_text = await self._call_gemini(prompt)
            result = self._parse_json_response(response_text)

            if "requests_to_remove" not in result:
                result["requests_to_remove"] = []
            if "reasons" not in result:
                result["reasons"] = {}
            if "analysis_summary" not in result:
                result["analysis_summary"] = "Analysis complete"

            logger.info(f"AI Debug: {len(result['requests_to_remove'])} requests to remove")
            return result

        except Exception as e:
            logger.error(f"AI Debug error: {e}")
            return {
                "requests_to_remove": [],
                "reasons": {},
                "analysis_summary": f"Error during analysis: {str(e)}",
                "error": str(e)
            }

    async def _call_gemini(self, prompt: str) -> str:
        """Llamar a la API de Gemini directamente (async con httpx)."""
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _parse_json_response(self, text: str) -> dict:
        """Parsear la respuesta JSON de Gemini, limpiando markdown si es necesario."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
            text = text.strip()
        return json.loads(text)

    def _simplify_for_correlation(self, script_model: Dict[str, Any]) -> list:
        """Simplificar el script para el prompt de correlación — solo datos relevantes."""
        simplified = []
        for req in script_model.get("requests", []):
            simplified.append({
                "order": req.get("order", 0),
                "name": req.get("name", ""),
                "method": req.get("method", ""),
                "url": req.get("url", ""),
                "headers": req.get("headers", {}),
                "body": (req.get("body", "") or "")[:500],
                "existing_extractors": [e.get("variable_name") for e in req.get("extractors", [])],
            })
        return simplified

    def _simplify_for_debug(self, script_model: Dict[str, Any]) -> list:
        """Simplificar el script para el prompt de debug — solo URL y método."""
        simplified = []
        for req in script_model.get("requests", []):
            simplified.append({
                "order": req.get("order", 0),
                "name": req.get("name", ""),
                "method": req.get("method", ""),
                "url": req.get("url", ""),
            })
        return simplified
