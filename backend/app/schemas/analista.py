"""Los cuerpos que acepta el «Analista IA» — BLOQUE 5 (reporte 147).

Todo con `extra="forbid"`: un PATCH que intente tocar las cifras del JTL, las
fases o el resultado de un criterio no se ignora en silencio, se rechaza (422).
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Tipo = Literal["tiempo_respuesta", "disponibilidad_o_error", "concurrencia", "caudal", "volumen", "proceso", "otro"]
Operador = Literal["<", "<=", ">", ">=", "="]


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CriterioEntrada(_Estricto):
    texto: str = Field(..., min_length=1, max_length=500)
    tipo: Tipo = "otro"
    metrica: Optional[str] = Field(None, max_length=40)
    operador: Optional[Operador] = None
    valor: Optional[float] = Field(None, ge=0)
    unidad: Optional[str] = Field(None, max_length=20)
    cantidad: Optional[float] = Field(None, ge=0)
    transaccion: Optional[str] = Field(None, max_length=300)
    cada_transaccion: Optional[bool] = None   # el límite vale para cada una
    # 150: el alcance. Las transacciones nombradas (cada una por separado), o su
    # suma («N entre A y B»), o toda la prueba solo si el analista lo dijo.
    transacciones: Optional[List[str]] = Field(None, max_length=20)
    suma: Optional[bool] = None
    toda_la_prueba: Optional[bool] = None
    metrica_supuesta: Optional[bool] = None   # tiempo sin medida dicha: P90, y se dice
    ventana_valor: Optional[float] = Field(None, ge=0)   # volumen «en 30 minutos»
    ventana_unidad: Optional[Literal["s", "min", "h"]] = None


class CriterioEdicion(_Estricto):
    id: str = Field(..., max_length=20)
    texto: Optional[str] = Field(None, min_length=1, max_length=500)
    tipo: Optional[Tipo] = None
    metrica: Optional[str] = Field(None, max_length=40)
    operador: Optional[Operador] = None
    valor: Optional[float] = Field(None, ge=0)
    unidad: Optional[str] = Field(None, max_length=20)
    cantidad: Optional[float] = Field(None, ge=0)
    transaccion: Optional[str] = Field(None, max_length=300)
    cada_transaccion: Optional[bool] = None
    # 150: el alcance. Las transacciones nombradas (cada una por separado), o su
    # suma («N entre A y B»), o toda la prueba solo si el analista lo dijo.
    transacciones: Optional[List[str]] = Field(None, max_length=20)
    suma: Optional[bool] = None
    toda_la_prueba: Optional[bool] = None
    metrica_supuesta: Optional[bool] = None   # tiempo sin medida dicha: P90, y se dice
    ventana_valor: Optional[float] = Field(None, ge=0)   # volumen «en 30 minutos»
    ventana_unidad: Optional[Literal["s", "min", "h"]] = None
    # Solo para los «lo confirma el analista»: lo que dice él. No es un resultado
    # calculado: esos no se tocan.
    confirmacion: Optional[Literal["cumple", "no_cumple"]] = None


class CambiosCriterios(_Estricto):
    agregar: List[CriterioEntrada] = Field(default_factory=list, max_length=30)
    editar: List[CriterioEdicion] = Field(default_factory=list, max_length=30)
    quitar: List[str] = Field(default_factory=list, max_length=30)
    ninguno_acordado: Optional[bool] = None


class LineaEdicion(_Estricto):
    id: str = Field(..., max_length=20)
    texto: str = Field(..., min_length=1, max_length=500)


class CambiosRelato(_Estricto):
    agregar: List[str] = Field(default_factory=list, max_length=30)
    editar: List[LineaEdicion] = Field(default_factory=list, max_length=30)
    quitar: List[str] = Field(default_factory=list, max_length=30)


class CambiosContexto(_Estricto):
    ambiente: Optional[str] = Field(None, max_length=200)
    version: Optional[str] = Field(None, max_length=200)


class CambiosPendientes(_Estricto):
    descartar: List[str] = Field(default_factory=list, max_length=20)
    reabrir: List[str] = Field(default_factory=list, max_length=20)


class CambiosFicha(_Estricto):
    """PATCH /analista/sesiones/{id}. Todo opcional; lo que no viene no cambia."""
    transacciones: Optional[Dict[str, bool]] = None      # casillas: label -> lleva informe propio
    relato: Optional[CambiosRelato] = None
    criterios: Optional[CambiosCriterios] = None
    contexto: Optional[CambiosContexto] = None
    pendientes: Optional[CambiosPendientes] = None


class DatosPrueba(_Estricto):
    """PUT /analista/sesiones/{id}/prueba: «Cambiar datos de la prueba». Los JTL
    no se cambian aquí: otro JTL es otra conversación."""
    proyecto: str = Field(..., min_length=1, max_length=255)
    tipo: Literal["load", "stress", "endurance", "scalability", "spike", "smoke"]
    client_id: Optional[str] = Field(None, max_length=64)   # "" o null = sin cliente
    unidad: Literal["TPS", "UVC"] = "TPS"


class MensajeEntrada(_Estricto):
    texto: str = Field(..., min_length=1, max_length=2000)
