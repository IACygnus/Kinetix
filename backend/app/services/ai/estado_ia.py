"""
F1 (aviso de respaldo) — ¿sirve la IA AHORA? Sin generar nada.

Lo pidio Fredy despues de pasar dos dias generando informes con una clave
invalidada: «si la clave no sirve, prefiero enterarme ahi y parar, no generar
un informe entero para descubrirlo al final». La pantalla de subida lo consulta
ANTES de subir.

Como se comprueba, sin gastar una llamada de generacion:
  - OpenAI: `models.retrieve(<modelo>)`. Valida la clave Y que el modelo exista
    para esa clave. No cuesta tokens.
  - Gemini: `get_model(models/<modelo>)`, con transport="rest" (regla 12).

Lo que NO puede ver: un cupo agotado. El proveedor solo lo dice al generar. Se
devuelve en `limite` para que la pantalla no prometa mas de lo que sabe.

Cache de 60 s por (proveedor, modelo, prefijo de clave): la pantalla puede
preguntar cada vez que se abre sin llamar cada vez al proveedor. Guardar la
configuracion la vacia (`olvidar()`).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.services.ai.origen import MOTIVOS

logger = logging.getLogger(__name__)

CACHE_S = 60
TIMEOUT_S = 10.0
LIMITE = ("Esta comprobación no gasta llamadas: confirma que la clave y el modelo existen. "
          "Un cupo agotado solo se ve al generar.")

_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def olvidar() -> None:
    _cache.clear()


def _resultado(ok: bool, provider: Optional[str], model: Optional[str],
               tipo: Optional[str] = None, detalle: str = "") -> Dict[str, Any]:
    return {
        "ok": ok, "provider": provider, "model": model,
        "motivo_tipo": None if ok else tipo,
        "motivo_frase": None if ok else MOTIVOS.get(tipo or "error"),
        "detalle": None if ok else (detalle or "")[:400],
        "comprobado_en": datetime.utcnow().isoformat(),
        "limite": LIMITE,
    }


def _tipo_openai(err) -> str:
    try:
        import openai
    except Exception:   # pragma: no cover
        return "error"
    if isinstance(err, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return "clave"
    if isinstance(err, openai.NotFoundError):
        return "modelo"
    if isinstance(err, openai.RateLimitError):
        cuerpo = getattr(err, "body", None)
        codigo = cuerpo.get("code") if isinstance(cuerpo, dict) else None
        return "cupo" if codigo == "insufficient_quota" else "limite_proveedor"
    if isinstance(err, (openai.APIConnectionError, openai.APITimeoutError)):
        return "transitorio"
    estado = getattr(err, "status_code", None)
    if isinstance(estado, int) and estado >= 500:
        return "transitorio"
    return "error"


def _tipo_gemini(err) -> str:
    nombre = type(err).__name__
    texto = str(err)
    if nombre in ("PermissionDenied", "Unauthenticated") or "API key not valid" in texto or "API_KEY_INVALID" in texto:
        return "clave"
    if nombre == "NotFound":
        return "modelo"
    if nombre == "ResourceExhausted":
        return "limite_proveedor"
    if nombre in ("ServiceUnavailable", "DeadlineExceeded", "InternalServerError"):
        return "transitorio"
    return "error"


def comprobar(conf: Dict[str, Any], forzar: bool = False) -> Dict[str, Any]:
    """`conf` es lo que devuelve `load_ai_config_from_db`. SINCRONO: va a un hilo."""
    if not conf:
        return _resultado(False, None, None, "sin_configuracion",
                          "No hay configuración de IA activa, o su clave no se puede leer.")
    provider, model = conf.get("provider"), conf.get("model_name")
    if conf.get("limit_reached"):
        return _resultado(False, provider, model, "limite_kinetix",
                          f"Límite {conf['limit_reached']} de Kinetix alcanzado.")
    clave = conf.get("api_key") or ""
    if not clave:
        return _resultado(False, provider, model, "sin_configuracion", "La configuración no tiene clave.")

    llave = f"{provider}:{model}:{clave[:12]}"
    if not forzar and llave in _cache and time.monotonic() - _cache[llave][0] < CACHE_S:
        return {**_cache[llave][1], "cache": True}

    try:
        if provider == "openai":
            from openai import OpenAI
            OpenAI(api_key=clave, max_retries=0, timeout=TIMEOUT_S).models.retrieve(model)
        elif provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=clave, transport="rest")   # regla 12
            genai.get_model(f"models/{model}", request_options={"timeout": TIMEOUT_S})
        else:
            return _resultado(False, provider, model, "error", f"Proveedor no soportado: {provider}")
        res = _resultado(True, provider, model)
    except Exception as e:
        tipo = _tipo_openai(e) if provider == "openai" else _tipo_gemini(e)
        logger.warning(f"F1: la IA no esta disponible ({provider} {model}): {tipo} — {str(e)[:200]}")
        res = _resultado(False, provider, model, tipo, f"{model}: {e}")

    _cache[llave] = (time.monotonic(), res)
    return {**res, "cache": False}
