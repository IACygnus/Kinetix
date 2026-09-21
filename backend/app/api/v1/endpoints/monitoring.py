"""
Endpoints de monitoreo (Grafana + InfluxDB) - v2.0 Phase 4
GET  /monitoring/config  - obtener config actual (autenticado)
PUT  /monitoring/config  - actualizar config (admin only)
GET  /monitoring/health  - test de conectividad
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cryptography.fernet import Fernet
from datetime import datetime
from typing import List, Optional
import httpx
import uuid
import base64
import re
import unicodedata
import logging

from app.db.session import get_db
from app.db.models.monitoring import MonitoringConfig
from app.schemas.monitoring import (
    ArgumentoJMeter,
    ConfiguracionJMeter,
    MonitoringConfigRead,
    MonitoringConfigUpdate,
    MonitoringHealthStatus,
)
from app.core.security import get_current_active_user, require_role
from app.core.config import settings
from app.db.models.user import User
from app.db.models.client import Client
from app.db.models.test import TestExecution

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


# ===================================================================
#  ETAPA O1.6 — la configuración de JMeter, generada (O-D4 y O-D5)
# ===================================================================
#
# La pantalla no le pide a nadie que recuerde una URL ni que invente un nombre
# de corrida: se elige cliente y proyecto y aquí sale todo relleno. El nombre de
# la corrida es el de O-D4 y es **la misma etiqueta** con la que el tablero
# filtra, así que no puede haber discrepancia entre lo que se copia y lo que se
# mira.

SENDER_JMETER = "org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender"
LISTENER_JMETER = "org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient"


def _sin_tildes(texto: str) -> str:
    """«Bogotá Región» -> «bogota region». O-D4: ni tildes ni eñes."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def nombre_de_corrida(cliente: str, proyecto: str, cuando: Optional[datetime] = None) -> str:
    """O-D4: `<cliente>-<proyecto>-<aaaammdd-hhmm>`, en minúsculas y sin espacios.

    Va en la etiqueta `application` de InfluxDB, así que todo lo que no sea
    letra o número se vuelve un guion, y los guiones no se amontonan.
    """
    cuando = cuando or datetime.now()
    partes = []
    for trozo in (cliente, proyecto):
        limpio = re.sub(r"[^a-z0-9]+", "-", _sin_tildes(trozo or "").lower())
        partes.append(limpio.strip("-") or "sin-nombre")
    return f"{partes[0]}-{partes[1]}-{cuando.strftime('%Y%m%d-%H%M')}"


def _url_para_el_navegador(url: Optional[str]) -> str:
    """Los nombres de servicio de Docker no los resuelve nadie de fuera.

    Es la misma traducción que hace `MonitoringRealtime.tsx` desde hace tiempo;
    aquí hace falta porque esta URL se la damos a un JMeter que corre **fuera**
    de la red de Docker.
    """
    return (url or "").replace("influxdb:8086", "localhost:8086") \
                      .replace("grafana:3000", "localhost:3000").rstrip("/")


@router.get("/proyectos", response_model=List[str])
async def proyectos_del_cliente(
    client_id: uuid.UUID,
    _current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Los proyectos con los que ya se ha probado ese cliente.

    Son sugerencias para no teclear: el proyecto se puede escribir libre.
    """
    filas = await db.execute(
        select(TestExecution.project)
        .where(TestExecution.client_id == client_id, TestExecution.project.isnot(None))
        .distinct()
    )
    return sorted({(p or "").strip() for p in filas.scalars().all() if (p or "").strip()})


async def _configuracion_jmeter(
    db: AsyncSession, client_id: uuid.UUID, proyecto: str,
) -> ConfiguracionJMeter:
    config = await _get_or_create_config(db)

    cliente = (await db.execute(
        select(Client).where(Client.id == client_id))).scalar_one_or_none()
    if cliente is None:
        raise HTTPException(404, "No existe ese cliente")
    if not (proyecto or "").strip():
        raise HTTPException(400, "Falta el proyecto")

    token = ""
    if config.influxdb_token_encrypted:
        try:
            token = _decrypt_token(config.influxdb_token_encrypted)
        except Exception:
            # Un token que no se descifra es un token que no sirve, y decirlo
            # aquí ahorra media hora de mirar por qué no llegan los puntos.
            logger.warning("El token de InfluxDB guardado no se puede descifrar")
            token = ""

    application = nombre_de_corrida(cliente.name, proyecto)
    base = _url_para_el_navegador(config.influxdb_url) or "http://localhost:8086"
    org = config.influxdb_org or "performance"
    cubo = config.influxdb_bucket or "jmeter"

    argumentos = [
        ArgumentoJMeter(
            nombre="influxdbMetricsSender", valor=SENDER_JMETER,
            explicacion="El que envía por HTTP. Viene con JMeter."),
        ArgumentoJMeter(
            nombre="influxdbUrl",
            valor=f"{base}/api/v2/write?org={org}&bucket={cubo}",
            explicacion="La dirección de escritura, con su organización y su cubo."),
        ArgumentoJMeter(
            nombre="influxdbToken", valor=token, secreto=True,
            explicacion="Token de solo escritura y solo para este cubo: no sirve para leer nada."),
        ArgumentoJMeter(
            nombre="application", valor=application,
            explicacion="El nombre de esta corrida. Es por lo que filtra el tablero."),
        ArgumentoJMeter(
            nombre="measurement", valor="jmeter",
            explicacion="No se cambia: el tablero busca por este nombre."),
        ArgumentoJMeter(
            nombre="summaryOnly", valor="false",
            explicacion="En «false» para ver transacción por transacción, no solo el total."),
        ArgumentoJMeter(
            nombre="samplersRegex", valor=".*",
            explicacion="Qué peticiones se envían. «.*» son todas."),
        ArgumentoJMeter(
            nombre="percentiles", valor="90;95;99",
            explicacion="Los percentiles que JMeter calcula y publica."),
        ArgumentoJMeter(
            nombre="testTitle", valor=application,
            explicacion="El título de la prueba. Se deja igual que la corrida."),
        ArgumentoJMeter(
            nombre="eventTags", valor="",
            explicacion="Etiquetas extra. Se puede dejar vacío."),
    ]

    tablero = _url_para_el_navegador(config.grafana_url) or "http://localhost:3000"
    uid = config.grafana_dashboard_uid or "jmeter-performance"

    aviso = ""
    if not token:
        aviso = ("No hay un token de InfluxDB utilizable. Pídele a un administrador "
                 "que lo cargue en la configuración de monitoreo.")

    return ConfiguracionJMeter(
        application=application,
        clase_listener=LISTENER_JMETER,
        argumentos=argumentos,
        url_tablero=f"{tablero}/d/{uid}?orgId=1&var-application={application}",
        aviso=aviso,
    )


@router.get("/jmeter-config", response_model=ConfiguracionJMeter)
async def configuracion_para_jmeter(
    client_id: uuid.UUID,
    proyecto: str,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Los valores exactos del Backend Listener para esta corrida (O-D5)."""
    return await _configuracion_jmeter(db, client_id, proyecto)


@router.get("/jmeter-fragmento")
async def fragmento_jmx(
    client_id: uuid.UUID,
    proyecto: str,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """El mismo Backend Listener ya escrito en XML, para pegar en un `.jmx`.

    Es texto armado a mano: no hace falta ninguna biblioteca nueva. Se pega
    **dentro** del Thread Group, junto a los demás elementos.
    """
    cfg = await _configuracion_jmeter(db, client_id, proyecto)

    def _xml(texto: str) -> str:
        return (texto.replace("&", "&amp;").replace("<", "&lt;")
                     .replace(">", "&gt;").replace('"', "&quot;"))

    lineas = [
        "<!-- Backend Listener generado por Kinetix Pro -->",
        f"<!-- Corrida: {cfg.application} -->",
        '<BackendListener guiclass="BackendListenerGui" testclass="BackendListener"'
        ' testname="InfluxDB de Kinetix" enabled="true">',
        '  <elementProp name="arguments" elementType="Arguments"'
        ' guiclass="ArgumentsPanel" testclass="Arguments" enabled="true">',
        '    <collectionProp name="Arguments.arguments">',
    ]
    for arg in cfg.argumentos:
        lineas += [
            f'      <elementProp name="{_xml(arg.nombre)}" elementType="Argument">',
            f'        <stringProp name="Argument.name">{_xml(arg.nombre)}</stringProp>',
            f'        <stringProp name="Argument.value">{_xml(arg.valor)}</stringProp>',
            "      </elementProp>",
        ]
    lineas += [
        "    </collectionProp>",
        "  </elementProp>",
        f'  <stringProp name="classname">{_xml(cfg.clase_listener)}</stringProp>',
        "</BackendListener>",
        "<hashTree/>",
        "",
    ]
    return Response(
        content="\n".join(lineas),
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="backend-listener-{cfg.application}.jmx"'},
    )
