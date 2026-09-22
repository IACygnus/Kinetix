"""Esquemas de los servidores observados — ETAPA O2c.

La regla que manda aqui es **O-D26: la credencial no se lee nunca**. Por eso hay
dos esquemas de entrada y uno de salida, y el de salida no tiene ni un campo
donde pudiera colarse: lo unico que dice es `tiene_credencial`, si o no.
"""
from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Tipo = Literal["linux", "windows", "postgresql", "otro"]
Modo = Literal["sin_agente", "agente"]

# El puerto de siempre de cada tipo, para que la pantalla lo proponga y nadie
# tenga que acordarse.
PUERTO_POR_TIPO = {"linux": 22, "windows": 5985, "postgresql": 5432, "otro": 22}


class ServidorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    tipo: Tipo = "linux"
    modo: Modo = "sin_agente"
    direccion: str = Field(..., min_length=1, max_length=255)
    puerto: int = Field(default=22, ge=1, le=65535)
    usuario: Optional[str] = Field(default=None, max_length=120)
    activo: bool = True
    notas: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("name", "direccion", "usuario", "notas")
    @classmethod
    def sin_espacios_de_sobra(cls, valor):
        return valor.strip() if isinstance(valor, str) else valor


class ServidorCrear(ServidorBase):
    client_id: UUID
    # Entra una vez y no vuelve a salir. Es la llave privada de SSH o la
    # contrasena del rol de la base, segun el tipo.
    credencial: Optional[str] = None


class ServidorActualizar(BaseModel):
    """Todo opcional: se manda solo lo que cambia.

    `credencial` en `None` significa «no la toques». Para borrarla hay que
    mandar la cadena vacia, que es una decision explicita y no un olvido.
    """
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    tipo: Optional[Tipo] = None
    modo: Optional[Modo] = None
    direccion: Optional[str] = Field(default=None, min_length=1, max_length=255)
    puerto: Optional[int] = Field(default=None, ge=1, le=65535)
    usuario: Optional[str] = Field(default=None, max_length=120)
    activo: Optional[bool] = None
    notas: Optional[str] = Field(default=None, max_length=1000)
    credencial: Optional[str] = None


class ServidorLeer(ServidorBase):
    """Lo que sale a la pantalla. **Aqui no hay credencial, y no puede haberla.**"""
    id: UUID
    client_id: UUID
    cliente_nombre: Optional[str] = None
    tiene_credencial: bool = False
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None

    class Config:
        from_attributes = True


class ComprobacionLectura(BaseModel):
    """Una cosa que se intento leer, y si se pudo."""
    que: str
    ok: bool
    detalle: str = ""


class ResultadoPrueba(BaseModel):
    """O-D24: si se llega, qué se puede leer, y el error REAL cuando falla."""
    ok: bool
    resumen: str
    # El mensaje tal cual lo devolvio el sistema. Sin esto, «no se pudo
    # conectar» obliga a adivinar; con esto se sabe si es la llave, el
    # cortafuegos o el nombre del usuario.
    error: Optional[str] = None
    lecturas: List[ComprobacionLectura] = []
    duracion_ms: int = 0


class ParametroConfiguracion(BaseModel):
    nombre: str
    valor: str
    explicacion: str = ""
    secreto: bool = False


class ConfiguracionServidor(BaseModel):
    """O-D25: lo que hay que poner, segun el modo del servidor."""
    servidor: str
    modo: Modo
    titulo: str
    explicacion: str
    # Para el modo sin agente: los parametros del recolector.
    parametros: List[ParametroConfiguracion] = []
    # Para el modo agente: la orden que hay que ejecutar EN el servidor.
    orden: Optional[str] = None
    # O-D28: quien la ejecuta es una persona, no Kinetix.
    aviso: str = ""
