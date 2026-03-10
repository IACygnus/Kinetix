"""
Modelo de configuracion de monitoreo (Grafana + InfluxDB) - v2.0 Phase 4
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.db.base_class import Base


class MonitoringConfig(Base):
    __tablename__ = "monitoring_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Grafana
    grafana_url = Column(String(500), nullable=True, default="http://grafana:3000")
    grafana_dashboard_uid = Column(String(100), nullable=True, default="jmeter-realtime")

    # InfluxDB
    influxdb_url = Column(String(500), nullable=True, default="http://influxdb:8086")
    influxdb_org = Column(String(255), nullable=True, default="jmeter-org")
    influxdb_bucket = Column(String(255), nullable=True, default="jmeter")
    influxdb_token_encrypted = Column(Text, nullable=True)  # Fernet-encrypted token

    # Estado
    is_configured = Column(Boolean, default=False)

    # Audit
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
