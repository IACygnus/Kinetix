"""La ingesta del agente — ETAPA O2e (O-D48 a O-D51).

    POST /ingesta/api/v2/write                el agente escribe aqui (Telegraf)
    GET  /ingesta/tokens?client_id=           los tokens de un cliente, sin el token
    POST /ingesta/tokens                      alta: el token sale UNA vez (admin)
    POST /ingesta/tokens/{id}/revocar         revocar (admin)
    GET  /ingesta/token-escritura             ¿hay token de escritura de `infra`?
    PUT  /ingesta/token-escritura             cargarlo (admin)

**Por qué la ruta tiene ese nombre.** Telegraf (`outputs.influxdb_v2`) le añade
él solo `/api/v2/write` a la URL que se le da. Al agente se le pone
`https://kinetix.sqasa.co/api/v1/ingesta` y llega aqui sin tocar nada de él.

**La escritura es la UNICA ruta de la aplicacion que no pide CSRF** (main.py),
porque el agente se identifica con su token y no tiene cookie. La exencion es
por la ruta EXACTA, no por prefijo: las demas rutas de este archivo son de la
pantalla y siguen pidiendolo. `pruebas_e2e/o2e2b_ingesta.py` lo comprueba.

**El token de InfluxDB no sale nunca del servidor.** El agente habla con
Kinetix; Kinetix habla con InfluxDB con el token de escritura de `infra`
(O-D15), que esta cifrado en `monitoring_config` y se lee con SQL tolerante.
"""
import logging
import uuid
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.observabilidad import ESCRIBE, _cifrar, _descifrar
from app.core.security import require_role
from app.db.models.client import Client
from app.db.models.ingest_token import IngestToken
from app.db.models.monitoring import MonitoringConfig
from app.db.models.user import User
from app.db.session import get_db
from app.services.observabilidad import ingesta as I

logger = logging.getLogger(__name__)
router = APIRouter()

ADMIN = require_role(["admin"])

# O-D50: solo el cubo de infraestructura. El de la prueba (`jmeter`) lo escribe
# JMeter con su propio token, y no hay motivo para que un agente llegue alli.
CUBO = "infra"
PRECISIONES = ("ns", "us", "ms", "s")
SQL_COLUMNA = "docs/sql/o2e_infra_write_token.sql"

# Uno por proceso. Aproximado a proposito: ver `ingesta.Limitador`.
_limitador = I.Limitador()


def _error(estado: int, codigo: str, mensaje: str, **cabeceras) -> JSONResponse:
    """Con la forma de los errores de InfluxDB: Telegraf escribe `message` en
    su log, y es lo que lee quien este mirando el servidor del cliente."""
    return JSONResponse(status_code=estado, headers=cabeceras or None,
                        content={"code": codigo, "message": mensaje})


def _constancia(cliente: str, puntos: int, resultado: str, motivo: str = "") -> None:
    """Punto 2 de Fredy: una linea por lote, aceptado o no. Es lo que permite
    decir «este cliente dejo de enviar a las 10:14». Nunca lleva el token."""
    logger.info("ingesta cliente=%r puntos=%d resultado=%s%s", cliente, puntos,
                resultado, f" motivo={motivo!r}" if motivo else "")


async def _leer_cuerpo(request: Request) -> bytes:
    """El cuerpo, sin guardar en memoria mas de 1 MB aunque manden mas.

    `request.body()` lo leeria entero antes de poder medirlo. Se lee a trozos
    y se corta en cuanto pasa del tope — que luego se vuelve a aplicar,
    descomprimido, en `ingesta.descomprimir`.
    """
    largo = request.headers.get("content-length", "")
    if largo.isdigit() and int(largo) > I.TOPE_BYTES:
        raise I.CuerpoDemasiadoGrande(f"Content-Length {largo}")
    trozos, total = [], 0
    async for trozo in request.stream():
        total += len(trozo)
        if total > I.TOPE_BYTES:
            raise I.CuerpoDemasiadoGrande(f"mas de {I.TOPE_BYTES} bytes")
        trozos.append(trozo)
    return b"".join(trozos)


async def _destino(db: AsyncSession):
    """(url, org, token) de InfluxDB para `infra`, o None si no hay token.

    Los tres de la MISMA fila: si hubiera dos configuraciones, no se mezcla la
    URL de una con el token de otra. SQL a mano por el mismo motivo que el
    token de lectura de O2c: hasta que se aplique el ALTER, la columna no
    existe, y declararla en el modelo romperia la pantalla de monitoreo.
    """
    try:
        fila = (await db.execute(text(
            "SELECT influxdb_url, influxdb_org, influxdb_infra_write_token_encrypted "
            "FROM monitoring_config "
            "WHERE influxdb_infra_write_token_encrypted IS NOT NULL LIMIT 1"
        ))).first()
    except Exception:
        await db.rollback()
        return None
    if not fila or not fila[0]:
        return None
    try:
        return fila[0].rstrip("/"), fila[1] or "performance", _descifrar(fila[2])
    except Exception:
        logger.warning("El token de escritura de «infra» no se puede descifrar")
        return None


# ---------------------------------------------------------------------------
# La escritura — lo que llama el agente
# ---------------------------------------------------------------------------
@router.post("/api/v2/write", include_in_schema=False)
async def escribir(
    request: Request,
    bucket: str = Query(""),
    precision: str = Query("ns"),
    db: AsyncSession = Depends(get_db),
):
    # 1. Quién es. Telegraf manda `Authorization: Token <token>`.
    esquema, _, token = request.headers.get("authorization", "").partition(" ")
    token = token.strip()
    if esquema.lower() not in ("token", "bearer") or not token:
        return _error(401, "unauthorized", "Falta el token de ingesta")
    fila = (await db.execute(
        select(IngestToken, Client.name)
        .join(Client, Client.id == IngestToken.client_id)
        .where(IngestToken.huella == I.huella(token))
    )).first()
    if fila is None:
        _constancia("?", 0, "rechazado_401", "token desconocido")
        return _error(401, "unauthorized", "Token de ingesta desconocido")
    registro, cliente = fila
    if registro.revocado_en is not None:
        _constancia(cliente, 0, "rechazado_401",
                    f"token {registro.prefijo} revocado")
        return _error(401, "unauthorized",
                      f"Este token se revoco el {registro.revocado_en:%Y-%m-%d %H:%M} UTC")

    # 2. El ritmo (O-D51). Telegraf respeta el Retry-After y reintenta.
    admitido, espera = _limitador.admitir(registro.huella)
    if not admitido:
        _constancia(cliente, 0, "rechazado_429", f"reintentar en {espera} s")
        return _error(429, "too many requests",
                      f"Mas de {I.PETICIONES_POR_MINUTO} escrituras por minuto "
                      f"con este token. Reintente en {espera} s.",
                      **{"Retry-After": str(espera)})

    # 3. A dónde. Solo `infra` (O-D50).
    if bucket != CUBO:
        _constancia(cliente, 0, "rechazado_400", f"cubo {bucket!r}")
        return _error(400, "invalid",
                      f"Solo se acepta el cubo «{CUBO}», no «{bucket}»")
    if precision not in PRECISIONES:
        _constancia(cliente, 0, "rechazado_400", f"precision {precision!r}")
        return _error(400, "invalid", f"Precision «{precision}» no valida")

    # 4. El cuerpo: tope, gzip y 413 (O-D51; ver `ingesta.descomprimir`).
    try:
        cuerpo = I.descomprimir(await _leer_cuerpo(request),
                                request.headers.get("content-encoding"))
        texto = cuerpo.decode("utf-8")
    except I.CuerpoDemasiadoGrande as exc:
        _constancia(cliente, 0, "rechazado_413", str(exc))
        return _error(413, "request too large",
                      f"El lote pasa de {I.TOPE_BYTES} bytes descomprimido: "
                      "partalo en lotes mas pequenos")
    except (I.CuerpoInvalido, UnicodeDecodeError) as exc:
        _constancia(cliente, 0, "rechazado_400", str(exc))
        return _error(400, "invalid", f"El lote no se puede leer: {exc}")

    # 5. Que todo sea de este cliente (O-D50). Una linea ajena y no entra nada.
    lote = I.revisar_lote(texto, cliente)
    if not lote.aceptado:
        motivo = lote.motivo(cliente)
        _constancia(cliente, lote.puntos, "rechazado_400", motivo)
        return _error(400, "invalid", motivo)

    # 6. A InfluxDB, con el token que no sale del servidor. Se reenvia lo que
    #    se acaba de revisar, descomprimido: exactamente eso, no el original.
    destino = await _destino(db)
    if destino is None:
        # 503 y no 4xx: Telegraf guarda el lote y reintenta. Mientras un admin
        # carga el token no se pierde nada.
        _constancia(cliente, lote.puntos, "rechazado_503",
                    "sin token de escritura de infra")
        return _error(503, "unavailable",
                      "Kinetix no tiene configurado el token de escritura del "
                      "cubo «infra». Se reintentara.")
    url, org, token_influx = destino
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.post(
                f"{url}/api/v2/write",
                params={"org": org, "bucket": CUBO, "precision": precision},
                headers={"Authorization": f"Token {token_influx}",
                         "Content-Type": "text/plain; charset=utf-8"},
                content=cuerpo)
    except httpx.HTTPError as exc:
        _constancia(cliente, lote.puntos, "rechazado_503",
                    f"InfluxDB no responde: {type(exc).__name__}")
        return _error(503, "unavailable", "InfluxDB no responde. Se reintentara.")

    if r.status_code >= 500:
        _constancia(cliente, lote.puntos, "rechazado_503",
                    f"InfluxDB {r.status_code}")
        return _error(503, "unavailable",
                      f"InfluxDB respondio {r.status_code}. Se reintentara.")
    if r.status_code >= 300:
        # Un 4xx de InfluxDB es del lote (un tipo de campo en conflicto, una
        # linea mal formada): se le devuelve tal cual al agente. Un 401/403
        # seria NUESTRO token de `infra`, no el del agente: 503, para que no
        # tire lotes buenos mientras se arregla.
        if r.status_code in (401, 403):
            _constancia(cliente, lote.puntos, "rechazado_503",
                        f"InfluxDB rechaza el token de infra ({r.status_code})")
            return _error(503, "unavailable",
                          "Kinetix no puede escribir en «infra». Se reintentara.")
        _constancia(cliente, lote.puntos, f"rechazado_{r.status_code}",
                    r.text[:300])
        return Response(status_code=r.status_code, content=r.content,
                        media_type=r.headers.get("content-type", "application/json"))

    await db.execute(update(IngestToken).where(IngestToken.id == registro.id)
                     .values(ultimo_uso=datetime.utcnow()))
    await db.commit()
    _constancia(cliente, lote.puntos, "aceptado")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Los tokens — lo que usa la pantalla (con cookie y CSRF, como todo lo demas)
# ---------------------------------------------------------------------------
class TokenLeer(BaseModel):
    """Lo que se ve de un token. **No hay campo para el token**: ni aqui ni en
    ningun otro sitio despues del alta."""
    id: uuid.UUID
    client_id: uuid.UUID
    prefijo: str
    creado_en: datetime
    ultimo_uso: Optional[datetime] = None
    revocado_en: Optional[datetime] = None


class TokenCreado(TokenLeer):
    token: str
    aviso: str


class TokenCrear(BaseModel):
    client_id: uuid.UUID


def _a_lectura(t: IngestToken) -> TokenLeer:
    # Campo a campo, como `_a_lectura` de observabilidad.py (O-D26): con
    # `from_attributes`, una columna nueva saldria sin que nadie lo decidiera.
    return TokenLeer(id=t.id, client_id=t.client_id, prefijo=t.prefijo,
                     creado_en=t.creado_en, ultimo_uso=t.ultimo_uso,
                     revocado_en=t.revocado_en)


@router.get("/tokens", response_model=List[TokenLeer])
async def listar_tokens(
    client_id: uuid.UUID,
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    filas = (await db.execute(
        select(IngestToken).where(IngestToken.client_id == client_id)
        .order_by(IngestToken.creado_en.desc()))).scalars().all()
    return [_a_lectura(t) for t in filas]


@router.post("/tokens", response_model=TokenCreado, status_code=201)
async def crear_token(
    cuerpo: TokenCrear,
    usuario: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    """El token sale en ESTA respuesta y en ninguna otra (O-D49)."""
    cliente = await db.get(Client, cuerpo.client_id)
    if cliente is None:
        raise HTTPException(404, "Cliente no encontrado")
    token = I.generar_token()
    registro = IngestToken(client_id=cliente.id, huella=I.huella(token),
                           prefijo=I.prefijo_visible(token),
                           creado_en=datetime.utcnow(), creado_por=usuario.id)
    db.add(registro)
    await db.commit()
    await db.refresh(registro)
    logger.info("ingesta token %s creado para cliente=%r por %s",
                registro.prefijo, cliente.name, usuario.username)
    return TokenCreado(
        **_a_lectura(registro).model_dump(), token=token,
        aviso=("Este token se muestra una sola vez. Kinetix guarda solo su "
               "huella y no puede volver a ensenarlo. Copielo ahora; si se "
               "pierde, revoquelo y cree otro."))


@router.post("/tokens/{token_id}/revocar", response_model=TokenLeer)
async def revocar_token(
    token_id: uuid.UUID,
    usuario: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    """Desde este momento no entra nada con él. La fila se queda: es la
    constancia de que existio y de hasta cuando valio."""
    registro = await db.get(IngestToken, token_id)
    if registro is None:
        raise HTTPException(404, "Token no encontrado")
    if registro.revocado_en is None:
        registro.revocado_en = datetime.utcnow()
        registro.revocado_por = usuario.id
        await db.commit()
        await db.refresh(registro)
        logger.info("ingesta token %s revocado por %s", registro.prefijo,
                    usuario.username)
    return _a_lectura(registro)


# ---------------------------------------------------------------------------
# El token de escritura de `infra` — con el que Kinetix escribe en InfluxDB
# ---------------------------------------------------------------------------
@router.get("/token-escritura")
async def estado_del_token_de_escritura(
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    """Si esta la columna y si hay token. **Nunca el token.**"""
    try:
        await db.execute(text(
            "SELECT influxdb_infra_write_token_encrypted FROM monitoring_config LIMIT 1"))
        columna = True
    except Exception:
        await db.rollback()
        columna = False
    return {"columna_aplicada": columna,
            "hay_token": bool(await _destino(db)) if columna else False,
            "sql": SQL_COLUMNA}


@router.put("/token-escritura", status_code=204)
async def guardar_token_de_escritura(
    cuerpo: dict,
    _usuario: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    """Carga el token de escritura del cubo `infra` (O-D15). Solo admin."""
    token = ((cuerpo or {}).get("token") or "").strip()
    if not token:
        raise HTTPException(400, "Falta el token")
    config = (await db.execute(select(MonitoringConfig).limit(1))).scalar_one_or_none()
    if config is None:
        raise HTTPException(
            400, "No hay configuracion de monitoreo todavia: guardela primero")
    try:
        await db.execute(
            text("UPDATE monitoring_config "
                 "SET influxdb_infra_write_token_encrypted = :t WHERE id = :i"),
            {"t": _cifrar(token), "i": config.id})
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            400, f"No se pudo guardar. Si la columna no existe todavia, aplique "
                 f"{SQL_COLUMNA}. Detalle: {type(exc).__name__}")
