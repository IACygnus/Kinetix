# backend/app/services/engine/protocols/base.py
"""
Interfaz abstracta para Protocol Handlers del motor de SQA Kinetix Pro.

Cada protocolo soportado (HTTP, WebSocket, gRPC, etc.) implementa esta interfaz.
El VirtualUser solo interactua con ProtocolHandler — nunca con implementaciones directas.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class RequestConfig:
    """Configuracion de un request individual extraida del Script Model."""
    id: str
    name: str                              # Nombre de la transaccion (label en JTL)
    protocol: str                          # "http", "websocket", "grpc"
    method: str                            # GET, POST, PUT, DELETE, etc.
    url: str                               # URL con variables ya sustituidas
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None             # Body con variables ya sustituidas
    body_type: str = "json"                # json | xml | form | raw
    params: Dict[str, str] = field(default_factory=dict)
    think_time_ms: int = 0                 # Tiempo de espera despues del request
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    extractors: List[Dict[str, Any]] = field(default_factory=list)
    # Cada extractor: {variable_name, extract_from, regex, match_no, default_value}


@dataclass
class RequestResult:
    """Resultado de ejecutar un RequestConfig. Alimenta al JTLWriter."""
    # Campos estandar del formato JTL de JMeter
    timestamp_ms: int           # epoch milliseconds al inicio del request
    elapsed_ms: int             # tiempo total del request en ms
    label: str                  # nombre de la transaccion
    response_code: str          # "200", "404", "Connection refused", etc.
    response_message: str       # "OK", "Not Found", etc.
    thread_name: str            # "Thread-1-VU-1" etc.
    data_type: str = "text"     # tipo de dato de respuesta
    success: bool = True        # True si assertion paso y no hubo error de red
    failure_message: str = ""   # mensaje si success=False
    bytes_received: int = 0     # bytes del response
    sent_bytes: int = 0
    grp_threads: int = 0        # threads activos en este grupo
    all_threads: int = 0        # threads activos totales
    url: str = ""               # URL final (puede diferir si hay redirect)
    latency_ms: int = 0         # tiempo hasta primer byte
    idle_time_ms: int = 0
    connect_ms: int = 0         # tiempo de establecer conexion TCP

    # No va al JTL — datos internos para correlacion
    response_body: str = ""
    response_headers: Dict[str, str] = field(default_factory=dict)
    extracted_variables: Dict[str, str] = field(default_factory=dict)


class ProtocolHandler(ABC):
    """
    Interfaz base para todos los protocol handlers del motor.

    Implementaciones actuales: HTTPHandler
    Futuras: WebSocketHandler, GRPCHandler, MobileProxyHandler
    """

    @abstractmethod
    async def execute(self, request: RequestConfig, thread_name: str, all_threads: int) -> RequestResult:
        """
        Ejecutar un request y retornar el resultado.

        Args:
            request: Configuracion del request con URL y variables ya sustituidas
            thread_name: Identificador del usuario virtual (para JTL)
            all_threads: Total de usuarios activos en este momento

        Returns:
            RequestResult con todos los datos para el JTL y para extraccion de variables

        Nota: Este metodo NUNCA debe lanzar excepcion.
              Los errores de red deben capturarse y retornarse como RequestResult con success=False.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Liberar recursos (conexiones, sesiones, etc.)"""
        pass

    @property
    @abstractmethod
    def protocol_name(self) -> str:
        """Nombre del protocolo: 'http', 'websocket', 'grpc'"""
        pass
