"""La ingesta del agente: qué se acepta y qué no — ETAPA O2e (O-D49 a O-D51).

Funciones puras, sin base de datos, sin red y sin FastAPI: se prueban sin
levantar nada (`pruebas_e2e/o2e2a_ingesta.py`). La ruta que las usa vive en
`api/v1/endpoints/ingesta.py` y solo decide los codigos HTTP.

Tres piezas:

1. **El token** (O-D49): se genera aqui, se guarda su huella y se compara por
   huella.
2. **El cuerpo** (O-D50, O-D51): se descomprime con tope y se comprueba que
   cada linea sea del cliente del token. Un lote con una sola linea ajena se
   rechaza ENTERO: nada entra mal etiquetado.
3. **El ritmo** (O-D51): 300 peticiones por minuto y token, aproximado.
"""
import hashlib
import math
import secrets
import time
import zlib
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. El token (O-D49)
# ---------------------------------------------------------------------------
# El prefijo delata que es: si aparece pegado en un chat o en un log ajeno,
# se reconoce como un token de ingesta de Kinetix sin tener que adivinar.
PREFIJO_TOKEN = "kxi_"
LARGO_PREFIJO_VISIBLE = 12


def generar_token() -> str:
    """256 bits al azar. Se ensena UNA vez y no se guarda."""
    return PREFIJO_TOKEN + secrets.token_urlsafe(32)


def huella(token: str) -> str:
    """Lo que se guarda en `ingest_tokens.huella` y por donde se busca."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def prefijo_visible(token: str) -> str:
    """Lo que la pantalla puede mostrar para distinguir dos tokens."""
    return token[:LARGO_PREFIJO_VISIBLE]


# ---------------------------------------------------------------------------
# 2. El cuerpo
# ---------------------------------------------------------------------------
# O-D51. 1 MB es lo que nginx deja pasar por defecto (`client_max_body_size`),
# asi que subirlo aqui no serviria de nada sin tocar el servidor. Un lote de
# 2.000 puntos del agente ronda los 200-300 KB sin comprimir.
TOPE_BYTES = 1024 * 1024


class CuerpoDemasiadoGrande(Exception):
    """Se contesta con 413 — NO con 400. Ver `descomprimir`."""


class CuerpoInvalido(Exception):
    """Se contesta con 400: el lote no se puede leer."""


def descomprimir(cuerpo: bytes, content_encoding: Optional[str],
                 tope: int = TOPE_BYTES) -> bytes:
    """El cuerpo tal como lo va a leer InfluxDB, sin pasar de `tope`.

    **Telegraf comprime con gzip por defecto** (`content_encoding = "gzip"` en
    `outputs.influxdb_v2`), asi que casi todo lo que llega viene comprimido.

    **El tope se aplica DESPUES de descomprimir, no al cuerpo recibido.** Medir
    solo lo que llega por la red parece suficiente y no lo es: unos pocos KB de
    gzip pueden expandirse a cientos de MB (una «bomba» de compresion), y
    descomprimirlos enteros para medirlos despues ya es el dano. Por eso se
    descomprime con `max_length`: nunca se saca de la memoria mas de `tope`+1
    bytes, pase lo que pase dentro del gzip.

    **Pasarse del tope es 413, no 400.** Telegraf, ante un 413, parte el lote
    en dos y reenvia cada mitad; ante cualquier otro 4xx salvo el 429, tira el
    lote y esas metricas se pierden. Un lote grande no es un lote malo: solo
    hay que mandarlo en trozos, y el 413 es la forma de pedirlo.
    """
    if len(cuerpo) > tope:
        raise CuerpoDemasiadoGrande(
            f"el cuerpo recibido ocupa {len(cuerpo)} bytes y el tope es {tope}")

    codificacion = (content_encoding or "").strip().lower()
    if codificacion in ("", "identity"):
        return cuerpo
    if codificacion != "gzip":
        raise CuerpoInvalido(
            f"Content-Encoding «{content_encoding}» no se acepta: solo gzip o "
            "ninguno")

    # 16 + MAX_WBITS = formato gzip (cabecera y cola), no zlib a secas.
    descompresor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        salida = descompresor.decompress(cuerpo, tope + 1)
    except zlib.error as exc:
        raise CuerpoInvalido(f"el gzip no se puede leer: {exc}") from exc
    if len(salida) > tope or descompresor.unconsumed_tail:
        raise CuerpoDemasiadoGrande(
            f"descomprimido pasa de {tope} bytes")
    if not descompresor.eof:
        raise CuerpoInvalido("el gzip esta cortado")
    return salida


def _cabeza(linea: str) -> str:
    """La medida y las etiquetas: todo hasta el primer espacio sin escapar."""
    i = 0
    while i < len(linea):
        c = linea[i]
        if c == "\\":
            i += 2
            continue
        if c == " ":
            return linea[:i]
        i += 1
    return linea


def _partir(texto: str, separador: str, maximo: int = -1):
    """Parte por `separador` cuando NO va escapado con barra invertida."""
    trozos, actual, i = [], [], 0
    while i < len(texto):
        c = texto[i]
        if c == "\\" and i + 1 < len(texto):
            actual.append(texto[i:i + 2])
            i += 2
            continue
        if c == separador and (maximo < 0 or len(trozos) < maximo):
            trozos.append("".join(actual))
            actual = []
        else:
            actual.append(c)
        i += 1
    trozos.append("".join(actual))
    return trozos


def _desescapar(valor: str) -> str:
    """En etiquetas, el protocolo de linea escapa coma, igual y espacio.

    De una sola pasada: una barra delante de otra cosa se queda como esta
    (Telegraf no escapa la barra), asi que `C:\\` sigue siendo `C:\\`.
    """
    salida, i = [], 0
    while i < len(valor):
        if valor[i] == "\\" and i + 1 < len(valor) and valor[i + 1] in ", =":
            salida.append(valor[i + 1])
            i += 2
        else:
            salida.append(valor[i])
            i += 1
    return "".join(salida)


def cliente_de_linea(linea: str) -> Optional[str]:
    """El valor de la etiqueta `cliente`, ya sin escapes. None si no la lleva.

    Protocolo de linea: `medida[,clave=valor...] campos [marca]`. Las
    etiquetas acaban en el primer espacio sin escapar; el nombre del cliente
    puede llevar espacios y comas («Banco X, S.A.»), y Telegraf los escapa.
    """
    etiquetas = _partir(_cabeza(linea), ",")[1:]   # la primera es la medida
    for par in etiquetas:
        clave_valor = _partir(par, "=", maximo=1)
        if len(clave_valor) == 2 and _desescapar(clave_valor[0]) == "cliente":
            return _desescapar(clave_valor[1])
    return None


@dataclass
class ResultadoLote:
    puntos: int = 0
    # Solo las lineas que NO son del cliente del token; None = sin etiqueta.
    ajenas: Counter = field(default_factory=Counter)

    @property
    def aceptado(self) -> bool:
        return self.puntos > 0 and not self.ajenas

    def motivo(self, cliente: str) -> str:
        """El texto del 400: cuantas lineas y con qué cliente venian.

        Es lo que el analista necesita para saber qué instalacion esta mal
        configurada, sin tener que ir a mirar el lote.
        """
        if self.puntos == 0:
            return "El lote no trae ninguna linea."
        total = sum(self.ajenas.values())
        partes = []
        for valor, n in sorted(self.ajenas.items(),
                               key=lambda kv: (-kv[1], kv[0] or "")):
            linea = "linea" if n == 1 else "lineas"
            if valor is None:
                partes.append(f"{n} {linea} sin la etiqueta cliente")
            else:
                partes.append(f"{n} {linea} con cliente=«{valor}»")
        return (f"Lote rechazado entero: {total} de {self.puntos} lineas no son "
                f"del cliente «{cliente}» ({'; '.join(partes)}). No se ha "
                "escrito nada.")


def revisar_lote(texto: str, cliente: str) -> ResultadoLote:
    """¿Es todo el lote de `cliente`? Cuenta los puntos y las lineas ajenas.

    La comparacion es EXACTA con el nombre del cliente en Kinetix, que es lo
    que pone la orden de instalacion en `--cliente`. Si el cliente se renombra
    en Kinetix, sus agentes empiezan a ser rechazados: es lo correcto, porque
    sus metricas ya no se encontrarian por el nombre nuevo.
    """
    resultado = ResultadoLote()
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        resultado.puntos += 1
        valor = cliente_de_linea(linea)
        if valor != cliente:
            resultado.ajenas[valor] += 1
    return resultado


# ---------------------------------------------------------------------------
# 3. El ritmo (O-D51)
# ---------------------------------------------------------------------------
# Un agente envia cada 5 s: 12 peticiones por minuto. 300 son exactamente 25
# agentes, asi que el techo comodo con un mismo token son unos 20 servidores:
# los reintentos de Telegraf y el desfase entre agentes necesitan holgura. Mas
# alla de eso no es un cliente con muchos servidores, es un abuso — o hace
# falta un segundo token para ese cliente.
PETICIONES_POR_MINUTO = 300
VENTANA_S = 60.0


class Limitador:
    """Ventana deslizante de 60 s por token. **Aproximado, y es a proposito.**

    Vive en la memoria de cada proceso. En produccion corren dos workers
    (`--workers 2`), asi que el tope real puede llegar al doble. El objetivo es
    frenar un abuso, no contar exacto (Fredy, O-D51): guardarlo en Postgres
    costaria una escritura por lote para ganar una precision que no se usa.
    """

    def __init__(self, tope: int = PETICIONES_POR_MINUTO,
                 ventana_s: float = VENTANA_S, reloj=time.monotonic):
        self.tope = tope
        self.ventana_s = ventana_s
        self._reloj = reloj
        self._marcas: Dict[str, Deque[float]] = {}

    def admitir(self, clave: str) -> Tuple[bool, int]:
        """(se admite, segundos del `Retry-After` si no)."""
        ahora = self._reloj()
        marcas = self._marcas.setdefault(clave, deque())
        while marcas and marcas[0] <= ahora - self.ventana_s:
            marcas.popleft()
        if len(marcas) >= self.tope:
            # Hasta que salga de la ventana la mas vieja; nunca menos de 1 s,
            # que es lo minimo que se puede escribir en la cabecera.
            espera = math.ceil(marcas[0] + self.ventana_s - ahora)
            return False, max(1, espera)
        marcas.append(ahora)
        self._limpiar(ahora)
        return True, 0

    def _limpiar(self, ahora: float) -> None:
        """Que un token que ya no escribe no ocupe memoria para siempre."""
        if len(self._marcas) < 1000:
            return
        for clave in [c for c, m in self._marcas.items()
                      if not m or m[-1] <= ahora - self.ventana_s]:
            del self._marcas[clave]
