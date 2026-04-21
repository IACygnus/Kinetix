# backend/app/db/models/script_design.py
"""
Modelo ScriptDesign — Diseño interno de scripts de performance testing.
El script_model JSON almacena requests, variables, extractors y data files.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base


class ScriptDesign(Base):
    __tablename__ = "script_designs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Propietario del script (UUID para coincidir con users.id)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)

    # El modelo interno del script: lista de requests, variables, extractors, data files
    # Estructura JSON:
    # {
    #   "requests": [
    #     {
    #       "id": "uuid",
    #       "order": 0,
    #       "name": "Login",
    #       "protocol": "http",
    #       "method": "POST",
    #       "url": "https://example.com/api/login",
    #       "headers": {"Content-Type": "application/json"},
    #       "body": "{\"user\": \"${username}\", \"pass\": \"${password}\"}",
    #       "body_type": "json",           # json | xml | form | raw
    #       "params": {},
    #       "assertions": [
    #         {"type": "status_code", "value": "200"}
    #       ],
    #       "think_time_ms": 0,
    #       "extractors": [
    #         {
    #           "variable_name": "auth_token",
    #           "extract_from": "body",    # body | header
    #           "regex": "\"token\":\"([^\"]+)\"",
    #           "match_no": 1,
    #           "default_value": ""
    #         }
    #       ]
    #     }
    #   ],
    #   "variables": [
    #     {"name": "username", "value": "", "source": "datafile", "datafile_id": 1}
    #   ],
    #   "protocol": "http"
    # }
    script_model = Column(JSON, nullable=False, default=dict)

    # Tipo de prueba: api | web | both
    script_type = Column(String(20), nullable=True, default="api")

    # Nombre del cliente denormalizado para display rapido
    client_name = Column(String(255), nullable=True)

    # Metodo de origen del script
    origin = Column(String(50), nullable=False, default="manual")
    # Valores: manual | har_import | proxy_capture | wsdl_import | postman | openapi

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    scenarios = relationship("Scenario", back_populates="script", cascade="all, delete-orphan")
    data_files = relationship("DataFile", back_populates="script", cascade="all, delete-orphan")
