"""Esquemas de las sesiones de monitoreo — ETAPA O2d."""
from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

Estado = Literal["preparada", "en_curso", "terminada"]


class SesionCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    client_id: UUID
    proyecto: str = Field(..., min_length=1, max_length=200)
    # Los servidores que se miran. Pueden ser cero —una sesion sin servidores
    # sigue enseñando las metricas de la prueba—, pero entonces la pantalla lo
    # dice, para que nadie se quede esperando graficas que no van a venir.
    servidores: List[UUID] = []
    notas: Optional[str] = None


class SesionActualizar(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=200)
    proyecto: Optional[str] = Field(default=None, min_length=1, max_length=200)
    servidores: Optional[List[UUID]] = None
    estado: Optional[Estado] = None
    notas: Optional[str] = None


class ServidorDeSesion(BaseModel):
    id: UUID
    name: str
    tipo: str
    modo: str
    direccion: str


class SesionLeer(BaseModel):
    id: UUID
    nombre: str
    client_id: UUID
    cliente_nombre: Optional[str] = None
    proyecto: str
    corrida: str
    estado: Estado
    notas: Optional[str] = None
    servidores: List[ServidorDeSesion] = []
    creada_en: Optional[datetime] = None
    empezo_en: Optional[datetime] = None
    termino_en: Optional[datetime] = None


class ConexionJMeter(BaseModel):
    """Lo que hace falta para que JMeter mande sus metricas a esta sesion.

    Es lo mismo que Kinetix le mete al `.jmx` (O-D45); se devuelve aparte para
    la opcion avanzada, la de copiarlos a mano.
    """
    url: str
    token: str
    corrida: str
    parametros: List[Dict[str, str]] = []
    # Si falta el token de escritura, hay que decirlo aqui y no dejar que
    # alguien descargue un .jmx que no va a enviar nada.
    aviso: str = ""


class SerieMetrica(BaseModel):
    """Una linea de una grafica."""
    etiqueta: str
    unidad: str = ""
    puntos: List[List[float]] = []   # [[milisegundos, valor], ...]


class GraficaServidor(BaseModel):
    titulo: str
    explicacion: str = ""
    unidad: str = ""
    series: List[SerieMetrica] = []


class MetricasDeServidor(BaseModel):
    servidor: str
    tipo: str
    graficas: List[GraficaServidor] = []


class MetricasDeSesion(BaseModel):
    """O-D39: arriba la prueba, abajo la infraestructura, mismo eje de tiempo."""
    corrida: str
    desde: str
    hasta: str
    prueba: List[GraficaServidor] = []
    infraestructura: List[MetricasDeServidor] = []
    # El motivo EXACTO cuando no hay nada que pintar. Una grafica vacia sin
    # explicacion es el peor resultado posible: parece que el producto no va.
    aviso: str = ""
    hay_datos: bool = False
