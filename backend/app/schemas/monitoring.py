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
