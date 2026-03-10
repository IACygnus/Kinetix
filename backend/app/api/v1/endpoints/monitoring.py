"""
Endpoints de monitoreo (Grafana + InfluxDB) - v2.0 Phase 4
GET  /monitoring/config  - obtener config actual (autenticado)
PUT  /monitoring/config  - actualizar config (admin only)
GET  /monitoring/health  - test de conectividad
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cryptography.fernet import Fernet
from datetime import datetime
import httpx
import uuid
import base64
import logging

from app.db.session import get_db
from app.db.models.monitoring import MonitoringConfig
from app.schemas.monitoring import MonitoringConfigRead, MonitoringConfigUpdate, MonitoringHealthStatus
from app.core.security import get_current_active_user, require_role
from app.core.config import settings
from app.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


_cached_fernet_key: str = ""


def _get_fernet() -> Fernet:
    """Obtener instancia de Fernet con la clave de configuracion"""
    global _cached_fernet_key
    key = settings.FERNET_KEY
    if not key:
        # Auto-generate a key for this process if none configured
        if not _cached_fernet_key:
            _cached_fernet_key = Fernet.generate_key().decode()
            logger.warning("FERNET_KEY no configurada. Usando clave auto-generada (no persistente entre reinicios).")
        key = _cached_fernet_key
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        raw = key.encode('utf-8')[:32].ljust(32, b'\0')
        valid_key = base64.urlsafe_b64encode(raw)
        return Fernet(valid_key)


def _encrypt_token(plaintext: str) -> str:
    """Encriptar token con Fernet"""
    f = _get_fernet()
    return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')


def _decrypt_token(ciphertext: str) -> str:
    """Desencriptar token con Fernet"""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')


async def _get_or_create_config(db: AsyncSession) -> MonitoringConfig:
    """Obtener o crear la fila unica de configuracion"""
    result = await db.execute(select(MonitoringConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        config = MonitoringConfig(id=uuid.uuid4())
        db.add(config)
        await db.flush()
    return config


@router.get("/config", response_model=MonitoringConfigRead)
async def get_monitoring_config(
    _current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtener configuracion actual de monitoreo"""
    config = await _get_or_create_config(db)
    return MonitoringConfigRead(
        id=config.id,
        grafana_url=config.grafana_url,
        grafana_dashboard_uid=config.grafana_dashboard_uid,
        influxdb_url=config.influxdb_url,
        influxdb_org=config.influxdb_org,
        influxdb_bucket=config.influxdb_bucket,
        has_influxdb_token=bool(config.influxdb_token_encrypted),
        is_configured=config.is_configured,
        updated_at=config.updated_at,
        updated_by=config.updated_by,
    )


@router.put("/config", response_model=MonitoringConfigRead)
async def update_monitoring_config(
    data: MonitoringConfigUpdate,
    current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Actualizar configuracion de monitoreo (admin only)"""
    config = await _get_or_create_config(db)

    if data.grafana_url is not None:
        config.grafana_url = data.grafana_url.rstrip("/")
    if data.grafana_dashboard_uid is not None:
        config.grafana_dashboard_uid = data.grafana_dashboard_uid
    if data.influxdb_url is not None:
        config.influxdb_url = data.influxdb_url.rstrip("/")
    if data.influxdb_org is not None:
        config.influxdb_org = data.influxdb_org
    if data.influxdb_bucket is not None:
        config.influxdb_bucket = data.influxdb_bucket

    # Encriptar token si se proporciona
    if data.influxdb_token is not None:
        if data.influxdb_token.strip():
            config.influxdb_token_encrypted = _encrypt_token(data.influxdb_token)
        else:
            config.influxdb_token_encrypted = None

    # Determinar si esta configurado
    config.is_configured = bool(
        config.grafana_url
        and config.grafana_dashboard_uid
        and config.influxdb_url
        and config.influxdb_org
        and config.influxdb_bucket
        and config.influxdb_token_encrypted
    )

    config.updated_at = datetime.utcnow()
    config.updated_by = current_user.id

    await db.flush()
    logger.info(f"Monitoring config updated by {current_user.username}")

    return MonitoringConfigRead(
        id=config.id,
        grafana_url=config.grafana_url,
        grafana_dashboard_uid=config.grafana_dashboard_uid,
        influxdb_url=config.influxdb_url,
        influxdb_org=config.influxdb_org,
        influxdb_bucket=config.influxdb_bucket,
        has_influxdb_token=bool(config.influxdb_token_encrypted),
        is_configured=config.is_configured,
        updated_at=config.updated_at,
        updated_by=config.updated_by,
    )


@router.get("/health", response_model=MonitoringHealthStatus)
async def check_monitoring_health(
    _current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Verificar conectividad con Grafana e InfluxDB"""
    config = await _get_or_create_config(db)

    result = MonitoringHealthStatus(is_configured=config.is_configured)

    # Test Grafana
    if config.grafana_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{config.grafana_url}/api/health")
                if resp.status_code == 200:
                    result.grafana_status = "ok"
                    result.grafana_message = "Grafana accesible"
                else:
                    result.grafana_status = "error"
                    result.grafana_message = f"HTTP {resp.status_code}"
        except httpx.ConnectError:
            result.grafana_status = "error"
            result.grafana_message = "No se puede conectar a Grafana"
        except Exception as e:
            result.grafana_status = "error"
            result.grafana_message = str(e)[:200]
    else:
        result.grafana_status = "not_configured"
        result.grafana_message = "URL de Grafana no configurada"

    # Test InfluxDB
    if config.influxdb_url and config.influxdb_token_encrypted:
        try:
            token = _decrypt_token(config.influxdb_token_encrypted)
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{config.influxdb_url}/health",
                    headers={"Authorization": f"Token {token}"},
                )
                if resp.status_code == 200:
                    result.influxdb_status = "ok"
                    result.influxdb_message = "InfluxDB accesible"
                else:
                    result.influxdb_status = "error"
                    result.influxdb_message = f"HTTP {resp.status_code}"
        except httpx.ConnectError:
            result.influxdb_status = "error"
            result.influxdb_message = "No se puede conectar a InfluxDB"
        except Exception as e:
            result.influxdb_status = "error"
            result.influxdb_message = str(e)[:200]
    else:
        result.influxdb_status = "not_configured"
        result.influxdb_message = "InfluxDB no configurado o sin token"

    return result
