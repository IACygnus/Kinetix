"""
Endpoints de configuracion de IA
GET  /ai-config           - obtener config activa (key enmascarada)
POST /ai-config           - crear o actualizar config
POST /ai-config/test      - probar conexion con el proveedor
GET  /ai-config/models    - listar modelos por provider
POST /ai-config/reset-usage - resetear contadores (solo admin)
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cryptography.fernet import Fernet
from datetime import datetime, date, timedelta
import uuid
import logging
import base64

from app.db.session import get_db
from app.db.models.ai_config import AIConfig
from app.schemas.ai_config import (
    AIConfigRead, AIConfigCreate, AIProviderInfo, AITestResult, LiveModelsResponse,
)
from app.core.security import require_role
from app.core.config import settings
from app.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Modelos disponibles por proveedor
PROVIDERS = {
    "gemini": AIProviderInfo(
        id="gemini",
        name="Google Gemini",
        models=["gemini-3.1-flash-lite-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"],
    ),
    "openai": AIProviderInfo(
        id="openai",
        name="OpenAI",
        models=["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
    ),
}

_cached_fernet_key: str = ""

# ---- Live models cache (TTL 5 min) ----
_models_cache: dict = {}  # key: "provider:key_prefix" → value: (models_list, cached_at)
_MODELS_CACHE_TTL = timedelta(minutes=5)


def _invalidate_models_cache(provider: str = None):
    """Invalidate cached models. If provider=None, clear all."""
    global _models_cache
    if provider is None:
        _models_cache.clear()
    else:
        keys_to_remove = [k for k in _models_cache if k.startswith(f"{provider}:")]
        for k in keys_to_remove:
            del _models_cache[k]


def _fetch_models_from_provider(provider: str, api_key: str) -> list:
    """Call provider API to list available models. Raises on failure."""
    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        models_response = client.models.list()
        chat_prefixes = ("gpt-", "o1", "o3", "o4")
        filtered = [
            m.id for m in models_response.data
            if m.id.startswith(chat_prefixes)
            and not any(x in m.id for x in ("embedding", "audio", "tts", "whisper", "image", "dall"))
        ]
        return sorted(filtered, reverse=True)

    elif provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key, transport="rest")
        models_response = genai.list_models()
        filtered = [
            m.name.replace("models/", "")
            for m in models_response
            if "generateContent" in (m.supported_generation_methods or [])
        ]
        return sorted(filtered, reverse=True)

    else:
        raise ValueError(f"Provider no soportado: {provider}")


def _get_fernet() -> Fernet:
    """Obtener instancia de Fernet (misma logica que monitoring)"""
    global _cached_fernet_key
    key = settings.FERNET_KEY
    if not key:
        if not _cached_fernet_key:
            _cached_fernet_key = Fernet.generate_key().decode()
            logger.warning("FERNET_KEY no configurada. Clave auto-generada.")
        key = _cached_fernet_key
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        raw = key.encode('utf-8')[:32].ljust(32, b'\0')
        valid_key = base64.urlsafe_b64encode(raw)
        return Fernet(valid_key)


def _encrypt_key(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')


def _decrypt_key(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')


def _mask_key(encrypted: str | None) -> str:
    """Retorna **** si hay key guardada, vacio si no.
    Never decrypts — avoids errors when FERNET_KEY changes."""
    if not encrypted:
        return ""
    return "****"


def _is_new_plaintext_key(value: str | None) -> bool:
    """True if the value is a real new API key (not a masked placeholder)."""
    if not value or not value.strip():
        return False
    stripped = value.strip()
    # Placeholders the frontend might send back
    if stripped == "****" or stripped.startswith("•"):
        return False
    # Too short to be a real API key
    if len(stripped) < 10:
        return False
    return True


def _auto_reset_counters(config: AIConfig) -> None:
    """Resetea contadores si cambio el dia o el mes"""
    today = date.today()

    if config.last_reset_daily is None or config.last_reset_daily < today:
        config.daily_requests_used = 0
        config.last_reset_daily = today

    first_of_month = today.replace(day=1)
    if config.last_reset_monthly is None or config.last_reset_monthly < first_of_month:
        config.monthly_requests_used = 0
        config.last_reset_monthly = first_of_month


async def _get_or_create_config(db: AsyncSession) -> AIConfig:
    """Obtener o crear la fila unica de configuracion de IA"""
    result = await db.execute(select(AIConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        config = AIConfig(
            id=uuid.uuid4(),
            provider="gemini",
            model_name=settings.GEMINI_MODEL or "gemini-2.5-flash",
            is_active=True,
            daily_request_limit=1000,
            monthly_request_limit=20000,
            daily_requests_used=0,
            monthly_requests_used=0,
            last_reset_daily=date.today(),
            last_reset_monthly=date.today(),
        )
        if settings.GEMINI_API_KEY:
            config.api_key_encrypted = _encrypt_key(settings.GEMINI_API_KEY)
        db.add(config)
        await db.flush()
        logger.info("AI config created from env vars")
    else:
        _auto_reset_counters(config)
    return config


def _config_to_read(config: AIConfig) -> AIConfigRead:
    """Convierte modelo DB a schema de lectura"""
    return AIConfigRead(
        id=config.id,
        provider=config.provider or "gemini",
        model_name=config.model_name or "gemini-2.5-flash",
        api_key_masked=_mask_key(config.api_key_encrypted),
        is_active=config.is_active if config.is_active is not None else True,
        daily_request_limit=config.daily_request_limit or 1000,
        monthly_request_limit=config.monthly_request_limit or 20000,
        daily_requests_used=config.daily_requests_used or 0,
        monthly_requests_used=config.monthly_requests_used or 0,
        last_reset_daily=config.last_reset_daily,
        last_reset_monthly=config.last_reset_monthly,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


# ===================== ENDPOINTS =====================


@router.get("", response_model=AIConfigRead)
async def get_ai_config(
    _current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Obtener configuracion activa de IA (key enmascarada)"""
    config = await _get_or_create_config(db)
    return _config_to_read(config)


@router.post("", response_model=AIConfigRead)
async def create_or_update_ai_config(
    data: AIConfigCreate,
    _current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Crear o actualizar configuracion de IA"""
    config = await _get_or_create_config(db)

    if data.provider is not None:
        if data.provider not in PROVIDERS:
            raise HTTPException(400, f"Proveedor invalido. Opciones: {list(PROVIDERS.keys())}")
        config.provider = data.provider

    if data.model_name is not None:
        # B6: NO se valida contra PROVIDERS. Esa lista es fija y envejece sola:
        # el desplegable se llena con la lista viva del proveedor (95 modelos),
        # asi que validar contra 4 rechazaba casi todo — incluido el modelo ya
        # configurado. PROVIDERS queda solo como fallback del desplegable cuando
        # models/live no responde. La verificacion real del modelo es el boton
        # "Probar conexion" (POST /ai-config/test), que consulta al proveedor.
        model_name = (data.model_name or "").strip()
        if not model_name:
            raise HTTPException(400, "El nombre del modelo no puede estar vacio.")
        config.model_name = model_name

    # API key handling: only encrypt if it's a real new plaintext key.
    # If it's "****", "•...", or empty → keep the existing encrypted key in DB.
    if data.api_key is not None:
        if _is_new_plaintext_key(data.api_key):
            # New plaintext key from user → encrypt and store
            config.api_key_encrypted = _encrypt_key(data.api_key.strip())
            logger.info("AI config: new API key encrypted and stored")
        elif not data.api_key.strip():
            # Explicitly cleared → remove key
            config.api_key_encrypted = None
            logger.info("AI config: API key cleared")
        # else: placeholder like "****" → do nothing, keep existing key

    if data.is_active is not None:
        config.is_active = data.is_active

    if data.daily_request_limit is not None:
        config.daily_request_limit = max(1, data.daily_request_limit)

    if data.monthly_request_limit is not None:
        config.monthly_request_limit = max(1, data.monthly_request_limit)

    config.updated_at = datetime.utcnow()
    await db.flush()

    # Invalidate live models cache so next fetch uses new key/provider
    _invalidate_models_cache(provider=config.provider)

    logger.info(f"AI config updated by {_current_user.username}: provider={config.provider}, model={config.model_name}")
    return _config_to_read(config)


@router.get("/models", response_model=list[AIProviderInfo])
async def list_models(
    _current_user: User = Depends(require_role(["admin"])),
):
    """Listar proveedores con sus modelos disponibles (hardcoded)"""
    return list(PROVIDERS.values())


@router.get("/models/live", response_model=LiveModelsResponse)
async def list_models_live(
    provider: str = "gemini",
    _current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List models from provider API in real-time. Falls back to hardcoded list on failure.
    Cache TTL: 5 minutes. Invalidated on config save."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Provider invalido: {provider}. Opciones: {list(PROVIDERS.keys())}")

    # Read DB config to get the stored (encrypted) API key
    config = await _get_or_create_config(db)

    if not config.api_key_encrypted:
        return LiveModelsResponse(
            provider=provider,
            models=PROVIDERS[provider].models,
            is_live=False,
            message="No hay API key configurada. Mostrando modelos genericos.",
        )

    # Decrypt
    try:
        api_key = _decrypt_key(config.api_key_encrypted)
    except Exception:
        return LiveModelsResponse(
            provider=provider,
            models=PROVIDERS[provider].models,
            is_live=False,
            message="No se pudo desencriptar la API key. Mostrando modelos genericos.",
        )

    # Check cache
    cache_key = f"{provider}:{api_key[:8]}"
    if cache_key in _models_cache:
        cached_models, cached_at = _models_cache[cache_key]
        if datetime.utcnow() - cached_at < _MODELS_CACHE_TTL:
            return LiveModelsResponse(provider=provider, models=cached_models, is_live=True)

    # Call provider API
    try:
        models = _fetch_models_from_provider(provider, api_key)
        if not models:
            models = PROVIDERS[provider].models
        _models_cache[cache_key] = (models, datetime.utcnow())
        logger.info(f"Live models fetched: provider={provider}, count={len(models)}")
        return LiveModelsResponse(provider=provider, models=models, is_live=True)
    except Exception as e:
        error_msg = str(e).lower()
        if "rate" in error_msg or "limit" in error_msg or "quota" in error_msg:
            msg = "Rate limit excedido. Mostrando modelos genericos."
        elif "auth" in error_msg or "401" in error_msg or "key" in error_msg:
            msg = "API key invalida. Mostrando modelos genericos."
        elif "timeout" in error_msg or "connect" in error_msg:
            msg = "No se pudo conectar al provider. Mostrando modelos genericos."
        else:
            msg = f"Error consultando provider: {str(e)[:100]}. Mostrando modelos genericos."
        logger.warning(f"Live models fetch failed: provider={provider}, error={str(e)[:120]}")
        return LiveModelsResponse(
            provider=provider,
            models=PROVIDERS[provider].models,
            is_live=False,
            message=msg,
        )


@router.post("/test", response_model=AITestResult)
async def test_ai_connection(
    payload: Optional[dict] = None,
    _current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Probar conexion con el proveedor de IA.
    Accepts optional payload with provider/model_name/api_key to test
    before saving. Falls back to stored DB config."""
    config = await _get_or_create_config(db)

    # Use payload values if provided, otherwise DB config
    provider = (payload or {}).get("provider") or config.provider or "gemini"
    model = (payload or {}).get("model_name") or config.model_name or "gemini-2.5-flash"

    # Determine API key: payload > DB > error
    payload_key = (payload or {}).get("api_key", "")
    if _is_new_plaintext_key(payload_key):
        # New key from payload — use directly without decrypting
        api_key = payload_key.strip()
    elif config.api_key_encrypted:
        try:
            api_key = _decrypt_key(config.api_key_encrypted)
        except Exception as e:
            logger.error(f"Cannot decrypt stored API key: {e}")
            return AITestResult(
                status="error",
                message=(
                    "No se puede desencriptar la API key almacenada. "
                    "Esto ocurre cuando cambia FERNET_KEY entre reinicios. "
                    "Solucion: ingrese la API key nuevamente y presione Guardar."
                ),
                provider=provider,
                model=model,
            )
    else:
        return AITestResult(
            status="error",
            message="No hay API key configurada. Guarde una API key primero.",
            provider=provider,
            model=model,
        )

    # Log key prefix for debugging (never log full key)
    logger.info(f"AI test: provider={provider}, model={model}, key_prefix={api_key[:10]}...")

    if provider == "gemini":
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key, transport="rest")
            m = genai.GenerativeModel(model)
            response = m.generate_content("Responde solo: OK")
            if response and response.text:
                return AITestResult(
                    status="ok",
                    message=f"Conexion exitosa. Respuesta: {response.text.strip()[:50]}",
                    provider=provider,
                    model=model,
                )
            return AITestResult(status="error", message="Sin respuesta del modelo", provider=provider, model=model)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "resource" in error_str.lower():
                return AITestResult(
                    status="error",
                    message=(
                        f"Error 429: La cuota de la API esta agotada. "
                        f"Key usada (prefijo): {api_key[:10]}... "
                        f"Verifique su plan en https://aistudio.google.com/apikey "
                        f"o cambie la API key. Detalle: {error_str[:120]}"
                    ),
                    provider=provider,
                    model=model,
                )
            return AITestResult(status="error", message=f"Key prefix: {api_key[:10]}... Error: {error_str[:180]}", provider=provider, model=model)

    elif provider == "openai":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Responde solo: OK"}],
                max_tokens=10,
            )
            text = response.choices[0].message.content if response.choices else ""
            return AITestResult(
                status="ok",
                message=f"Conexion exitosa. Respuesta: {(text or '').strip()[:50]}",
                provider=provider,
                model=model,
            )
        except Exception as e:
            return AITestResult(status="error", message=str(e)[:200], provider=provider, model=model)

    return AITestResult(status="error", message=f"Proveedor no soportado: {provider}", provider=provider, model=model)


@router.post("/reset-usage")
async def reset_ai_usage(
    _current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Resetear contadores de uso (solo admin)"""
    config = await _get_or_create_config(db)
    config.daily_requests_used = 0
    config.monthly_requests_used = 0
    config.last_reset_daily = date.today()
    config.last_reset_monthly = date.today()
    config.updated_at = datetime.utcnow()
    await db.flush()
    logger.info(f"AI usage counters reset by {_current_user.username}")
    return {"message": "Contadores reseteados exitosamente"}
