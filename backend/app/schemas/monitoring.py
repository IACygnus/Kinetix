"""
Schemas de monitoreo (Grafana + InfluxDB) - v2.0 Phase 4
"""
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class MonitoringConfigRead(BaseModel):
    """Response schema - token is never exposed"""
    id: UUID
    grafana_url: Optional[str] = None
    grafana_dashboard_uid: Optional[str] = None
    influxdb_url: Optional[str] = None
    influxdb_org: Optional[str] = None
    influxdb_bucket: Optional[str] = None
    has_influxdb_token: bool = False  # indica si hay token configurado, sin exponer el valor
    is_configured: bool = False
    updated_at: Optional[datetime] = None
    updated_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class MonitoringConfigUpdate(BaseModel):
    """Update schema - admin only"""
    grafana_url: Optional[str] = None
    grafana_dashboard_uid: Optional[str] = None
    influxdb_url: Optional[str] = None
    influxdb_org: Optional[str] = None
    influxdb_bucket: Optional[str] = None
    influxdb_token: Optional[str] = None  # plaintext, sera encriptado en backend


class MonitoringHealthStatus(BaseModel):
    """Health check response"""
    grafana_status: str = "unknown"  # ok, error, not_configured
    grafana_message: str = ""
    influxdb_status: str = "unknown"
    influxdb_message: str = ""
    is_configured: bool = False


# ===================== ETAPA O1.6 — la configuración para JMeter =====================


class ArgumentoJMeter(BaseModel):
    """Un parámetro del `InfluxdbBackendListenerClient`, listo para copiar.

    `secreto` marca los que no conviene enseñar en una captura de pantalla; la
    pantalla los tapa hasta que se piden.
    """
    nombre: str
    valor: str
    explicacion: str = ""
    secreto: bool = False


class ConfiguracionJMeter(BaseModel):
    """Lo que hay que poner en el Backend Listener de una corrida (O-D5).

    `application` es el nombre de la corrida de O-D4 y es la misma etiqueta con
    la que el tablero de Grafana filtra (O-D6): por eso viaja aparte, además de
    venir dentro de `argumentos`.
    """
    application: str
    clase_listener: str
    argumentos: list[ArgumentoJMeter]
    url_tablero: str
    aviso: str = ""
