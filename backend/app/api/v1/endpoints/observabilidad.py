"""Los servidores que se miran durante una prueba — ETAPA O2c.

    GET    /observabilidad/servidores?client_id=     la lista
    POST   /observabilidad/servidores                alta
    GET    /observabilidad/servidores/{id}           detalle
    PUT    /observabilidad/servidores/{id}           edicion
    DELETE /observabilidad/servidores/{id}           baja
    POST   /observabilidad/servidores/{id}/probar    ¿se llega? ¿qué se lee?
    GET    /observabilidad/servidores/{id}/configuracion   qué hay que poner
    GET    /observabilidad/servidores/de-corrida?client_id=  los de esta prueba

**O-D26 manda sobre todo lo demas:** la credencial entra una vez y no vuelve a
salir. Ningun endpoint de aqui la devuelve, ni entera ni en trozos. Lo unico que
se dice es si la hay.
"""
import asyncio
import base64
import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime
from typing import List, Optional

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_active_user, require_role
from app.db.models.client import Client
from app.db.models.monitoring import MonitoringConfig
from app.db.models.observed_server import ObservedServer
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.observed_server import (
    ComprobacionLectura, ConfiguracionServidor, ParametroConfiguracion,
    ResultadoPrueba, ServidorActualizar, ServidorCrear, ServidorLeer,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ESCRIBE = require_role(["admin", "analyst"])

# La version del agente que instala O2b. Una sola definicion: si cambia alli,
# cambia aqui, y la orden que se le da a un cliente no queda desfasada.
VERSION_AGENTE = "1.29.5"


# ---------------------------------------------------------------------------
# Fernet — el mismo patron que `monitoring.py` y `ai_config.py`
# ---------------------------------------------------------------------------
_clave_en_memoria: str = ""


def _fernet() -> Fernet:
    global _clave_en_memoria
    clave = settings.FERNET_KEY
    if not clave:
        if not _clave_en_memoria:
            _clave_en_memoria = Fernet.generate_key().decode()
            logger.warning(
                "FERNET_KEY no configurada. Clave auto-generada, NO persistente "
                "entre reinicios: las credenciales guardadas dejaran de "
                "descifrarse al reiniciar.")
        clave = _clave_en_memoria
    try:
        return Fernet(clave.encode() if isinstance(clave, str) else clave)
    except Exception:
        crudo = clave.encode("utf-8")[:32].ljust(32, b"\0")
        return Fernet(base64.urlsafe_b64encode(crudo))


def _cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode("utf-8")).decode("utf-8")


def _descifrar(texto: str) -> str:
    return _fernet().decrypt(texto.encode("utf-8")).decode("utf-8")


# ---------------------------------------------------------------------------
def _a_lectura(servidor: ObservedServer, cliente_nombre: Optional[str] = None
               ) -> ServidorLeer:
    """El unico camino por el que un servidor sale de aqui.

    Se construye campo a campo a proposito: con `from_attributes` sobre el
    modelo, anadir una columna nueva la publicaria sin que nadie lo decidiera, y
    una de esas columnas es la credencial.
    """
    return ServidorLeer(
        id=servidor.id,
        client_id=servidor.client_id,
        cliente_nombre=cliente_nombre,
        name=servidor.name,
        tipo=servidor.tipo,
        modo=servidor.modo,
        direccion=servidor.direccion,
        puerto=servidor.puerto,
        usuario=servidor.usuario,
        activo=servidor.activo,
        notas=servidor.notas,
        tiene_credencial=bool(servidor.credencial_cifrada),
        creado_en=servidor.creado_en,
        actualizado_en=servidor.actualizado_en,
    )


async def _buscar(db: AsyncSession, servidor_id: uuid.UUID) -> ObservedServer:
    fila = (await db.execute(
        select(ObservedServer).where(ObservedServer.id == servidor_id)
    )).scalar_one_or_none()
    if fila is None:
        raise HTTPException(404, "No existe ese servidor")
    return fila


async def _nombre_cliente(db: AsyncSession, client_id: uuid.UUID) -> Optional[str]:
    return (await db.execute(
        select(Client.name).where(Client.id == client_id))).scalar_one_or_none()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@router.get("/servidores", response_model=List[ServidorLeer])
async def listar_servidores(
    client_id: Optional[uuid.UUID] = None,
    solo_activos: bool = False,
    _usuario: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    consulta = select(ObservedServer, Client.name).join(
        Client, Client.id == ObservedServer.client_id)
    if client_id:
        consulta = consulta.where(ObservedServer.client_id == client_id)
    if solo_activos:
        consulta = consulta.where(ObservedServer.activo.is_(True))
    filas = (await db.execute(consulta.order_by(Client.name, ObservedServer.name))).all()
    return [_a_lectura(servidor, nombre) for servidor, nombre in filas]


@router.get("/servidores/de-corrida", response_model=List[ServidorLeer])
async def servidores_de_la_corrida(
    client_id: uuid.UUID = Query(...),
    _usuario: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """O-D27: los servidores ACTIVOS de ese cliente.

    La corrida de O1 ya lleva cliente, asi que al lanzar una prueba estos son
    los que quedan ligados a ella. No hay que elegirlos otra vez.
    """
    filas = (await db.execute(
        select(ObservedServer, Client.name)
        .join(Client, Client.id == ObservedServer.client_id)
        .where(ObservedServer.client_id == client_id,
               ObservedServer.activo.is_(True))
        .order_by(ObservedServer.name)
    )).all()
    return [_a_lectura(servidor, nombre) for servidor, nombre in filas]


@router.post("/servidores", response_model=ServidorLeer, status_code=201)
async def crear_servidor(
    datos: ServidorCrear,
    usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    cliente = (await db.execute(
        select(Client).where(Client.id == datos.client_id))).scalar_one_or_none()
    if cliente is None:
        raise HTTPException(404, "No existe ese cliente")

    repetido = (await db.execute(
        select(ObservedServer).where(
            ObservedServer.client_id == datos.client_id,
            ObservedServer.name == datos.name)
    )).scalar_one_or_none()
    if repetido is not None:
        raise HTTPException(
            409, f"«{cliente.name}» ya tiene un servidor llamado «{datos.name}»")

    servidor = ObservedServer(
        id=uuid.uuid4(),
        client_id=datos.client_id,
        name=datos.name, tipo=datos.tipo, modo=datos.modo,
        direccion=datos.direccion, puerto=datos.puerto, usuario=datos.usuario,
        activo=datos.activo, notas=datos.notas,
        credencial_cifrada=_cifrar(datos.credencial) if datos.credencial else None,
        creado_por=usuario.id,
    )
    db.add(servidor)
    await db.commit()
    await db.refresh(servidor)
    return _a_lectura(servidor, cliente.name)


@router.get("/servidores/{servidor_id}", response_model=ServidorLeer)
async def ver_servidor(
    servidor_id: uuid.UUID,
    _usuario: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    servidor = await _buscar(db, servidor_id)
    return _a_lectura(servidor, await _nombre_cliente(db, servidor.client_id))


@router.put("/servidores/{servidor_id}", response_model=ServidorLeer)
async def actualizar_servidor(
    servidor_id: uuid.UUID,
    datos: ServidorActualizar,
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    servidor = await _buscar(db, servidor_id)
    cambios = datos.model_dump(exclude_unset=True)

    nuevo_nombre = cambios.get("name")
    if nuevo_nombre and nuevo_nombre != servidor.name:
        repetido = (await db.execute(
            select(ObservedServer).where(
                ObservedServer.client_id == servidor.client_id,
                ObservedServer.name == nuevo_nombre,
                ObservedServer.id != servidor.id)
        )).scalar_one_or_none()
        if repetido is not None:
            raise HTTPException(409, f"Ya hay un servidor llamado «{nuevo_nombre}»")

    # La credencial es el unico campo con reglas propias (O-D26):
    #   ausente        -> no se toca
    #   cadena vacia   -> se borra, y es una decision explicita
    #   con contenido  -> se sustituye
    if "credencial" in cambios:
        valor = cambios.pop("credencial")
        if valor is None:
            pass
        elif valor == "":
            servidor.credencial_cifrada = None
        else:
            servidor.credencial_cifrada = _cifrar(valor)

    for campo, valor in cambios.items():
        setattr(servidor, campo, valor)

    await db.commit()
    await db.refresh(servidor)
    return _a_lectura(servidor, await _nombre_cliente(db, servidor.client_id))


@router.delete("/servidores/{servidor_id}", status_code=204)
async def borrar_servidor(
    servidor_id: uuid.UUID,
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    servidor = await _buscar(db, servidor_id)
    await db.delete(servidor)
    await db.commit()


# ---------------------------------------------------------------------------
# O-D24 — la prueba de conexion
# ---------------------------------------------------------------------------
async def _saludo_tcp(host: str, puerto: int, espera: float = 6.0):
    """Abre el puerto y lee lo primero que diga. Devuelve (ok, texto, error)."""
    try:
        lector, escritor = await asyncio.wait_for(
            asyncio.open_connection(host, puerto), timeout=espera)
    except Exception as exc:
        return False, "", f"{type(exc).__name__}: {exc}"
    try:
        crudo = await asyncio.wait_for(lector.read(255), timeout=espera)
        return True, crudo.decode("utf-8", "replace").strip(), None
    except asyncio.TimeoutError:
        # Se llego al puerto pero nadie saluda. Para SSH es raro; para otros
        # protocolos es lo normal, asi que no es un fallo por si solo.
        return True, "", None
    except Exception as exc:
        return True, "", f"{type(exc).__name__}: {exc}"
    finally:
        escritor.close()
        try:
            await escritor.wait_closed()
        except Exception:
            pass


async def _token_de_lectura(db: AsyncSession) -> Optional[str]:
    """El token de solo lectura del cubo `infra` (O-D33), si ya esta la columna.

    **Se lee con SQL a mano, y a proposito.** La columna se anade con un
    `ALTER TABLE` (regla 10) que ejecuta Fredy cuando le viene bien. Si se
    declarara en el modelo, SQLAlchemy la pediria en CADA consulta de
    `monitoring_config` y, hasta que el ALTER estuviera aplicado, reventaria la
    pantalla de monitoreo entera — que es exactamente lo que paso en la Etapa 2
    con `ai_config.reasoning_effort` y que `CLAUDE.md` guarda como aviso.
    """
    try:
        fila = (await db.execute(text(
            "SELECT influxdb_read_token_encrypted FROM monitoring_config "
            "WHERE influxdb_read_token_encrypted IS NOT NULL LIMIT 1"
        ))).scalar_one_or_none()
    except Exception:
        # La columna todavia no existe. No es un error: es el estado normal
        # antes de aplicar docs/sql/o2c_influxdb_read_token.sql.
        await db.rollback()
        return None
    if not fila:
        return None
    try:
        return _descifrar(fila)
    except Exception:
        logger.warning("El token de lectura de InfluxDB no se puede descifrar")
        return None


async def _hay_metricas(servidor: ObservedServer, db: AsyncSession):
    """¿Estan llegando metricas de este servidor al cubo `infra`?

    Es la comprobacion que de verdad cierra el circulo: si llegan, es que la
    credencial sirve, que el servidor deja leer lo que hay que leer y que el
    camino hasta la base funciona. Un inicio de sesion de prueba solo diria lo
    primero.
    """
    config = (await db.execute(select(MonitoringConfig).limit(1))).scalar_one_or_none()
    if config is None or not config.influxdb_url:
        return None, "no hay configuracion de monitoreo"

    # O-D33: se lee con el token de LECTURA. El de escritura no sirve —y eso
    # esta bien: es de solo escritura a proposito (O-D2)—.
    token = await _token_de_lectura(db)
    if not token:
        return None, (
            "falta el token de solo lectura del cubo «infra» (O-D33). "
            "Aplique docs/sql/o2c_influxdb_read_token.sql y cargue el token "
            "en la configuracion de monitoreo.")

    # O-D34: ademas de QUE medidas llegan, CUANDO llego la ultima.
    #
    # El `_value` se pasa a texto antes de juntar las tablas: unas medidas
    # guardan enteros y otras flotantes, y Flux se niega a agruparlas
    # («schema collision: cannot group integer and float types together»).
    # Aqui el valor no importa —solo la fecha y el nombre—, asi que se
    # uniforma y se sigue.
    consulta = (
        'from(bucket: "infra")\n'
        '  |> range(start: -24h)\n'
        f'  |> filter(fn: (r) => r["host"] == "{servidor.name}")\n'
        '  |> last()\n'
        '  |> map(fn: (r) => ({ _time: r._time, _measurement: r._measurement }))\n'
        '  |> group(columns: ["_measurement"])\n'
        '  |> max(column: "_time")\n'
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as cliente:
            respuesta = await cliente.post(
                f"{config.influxdb_url.rstrip('/')}/api/v2/query",
                params={"org": config.influxdb_org or "performance"},
                headers={"Authorization": f"Token {token}",
                         "Content-Type": "application/vnd.flux",
                         "Accept": "application/csv"},
                content=consulta)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    if respuesta.status_code in (401, 403, 404):
        return None, (
            f"el token de lectura no sirve para el cubo «infra» "
            f"(InfluxDB respondio {respuesta.status_code}). Compruebe que se "
            f"creo con --read-bucket sobre ese cubo.")
    try:
        respuesta.raise_for_status()
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    # La respuesta trae, por cada medida, su ultimo punto. Las dos columnas que
    # interesan son `_time` y `_measurement`, y vienen al final de cada fila.
    # Se parte por la cabecera y se zipea, sin suponer nada de como empieza la
    # fila: segun la consulta, la columna `result` sale vacia (`,,0,...`) o con
    # nombre (`,_result,0,...`), y dar por hecho lo primero hacia que el
    # programa no viera ni una fila de una respuesta perfectamente valida.
    medidas, ultimo = {}, None
    cabecera = []
    for linea in respuesta.text.splitlines():
        if not linea.strip() or linea.startswith("#"):
            continue
        trozos = linea.split(",")
        # InfluxDB emite una cabecera NUEVA cada vez que cambia el esquema del
        # resultado, no solo una al principio. Tomando la primera y tratando
        # las demas como datos, las columnas salian desplazadas en uno y la
        # fecha aparecia en la lista de medidas.
        if len(trozos) > 1 and trozos[1] == "result":
            cabecera = trozos
            continue
        if not cabecera:
            continue
        fila = dict(zip(cabecera, trozos))
        medida = (fila.get("_measurement") or "").strip()
        cuando = (fila.get("_time") or "").strip()
        if medida:
            medidas[medida] = cuando
            if cuando and (ultimo is None or cuando > ultimo):
                ultimo = cuando
    return {"medidas": sorted(medidas), "ultima": ultimo}, None


def _hace_cuanto(marca: Optional[str]) -> str:
    """«hace 4 segundos», para que nadie tenga que restar fechas de cabeza."""
    if not marca:
        return "sin fecha"
    try:
        cuando = datetime.fromisoformat(marca.replace("Z", "+00:00"))
    except ValueError:
        return marca
    segundos = int((datetime.now(cuando.tzinfo) - cuando).total_seconds())
    if segundos < 0:
        return "ahora mismo"
    if segundos < 90:
        return f"hace {segundos} segundos"
    if segundos < 5400:
        return f"hace {segundos // 60} minutos"
    if segundos < 172800:
        return f"hace {segundos // 3600} horas"
    return f"hace {segundos // 86400} dias"


async def _probar_ssh(servidor: ObservedServer) -> ComprobacionLectura:
    """O-D32: ¿sirve la credencial? Los tres casos, distinguidos.

    Hace falta `openssh-client` en la imagen del backend. Mientras no este, se
    dice que no se ha comprobado — que es distinto de decir que esta bien.
    """
    if not shutil.which("ssh"):
        return ComprobacionLectura(
            que="la credencial (sin comprobar)", ok=False,
            detalle="este Kinetix no trae cliente de SSH, asi que no se ha "
                    "podido comprobar la credencial. Reconstruya el backend "
                    "con openssh-client (O-D32).")
    if not servidor.credencial_cifrada:
        return ComprobacionLectura(
            que="la credencial (sin comprobar)", ok=False,
            detalle="no hay credencial guardada para este servidor")
    try:
        llave = _descifrar(servidor.credencial_cifrada)
    except Exception as exc:
        return ComprobacionLectura(
            que="la credencial", ok=False,
            detalle=f"la credencial guardada no se puede descifrar: {exc}")

    # La llave se escribe en un fichero privado y se borra al terminar: `ssh`
    # rechaza una llave que puedan leer otros, y ademas no tiene por que quedar
    # en disco ni un segundo de mas.
    carpeta = tempfile.mkdtemp(prefix="kx_ssh_")
    ruta = os.path.join(carpeta, "llave")
    try:
        with open(ruta, "w") as fichero:
            fichero.write(llave if llave.endswith("\n") else llave + "\n")
        os.chmod(ruta, 0o600)

        proceso = await asyncio.create_subprocess_exec(
            # Sin `-q`: es justo la opcion que silencia «Permission denied
            # (publickey)», y sin ese mensaje lo unico que queda es «codigo
            # 255», que no le dice nada a nadie.
            "ssh", "-n",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=8",
            "-o", "NumberOfPasswordPrompts=0",
            "-i", ruta,
            "-p", str(servidor.puerto),
            f"{servidor.usuario or 'kinetix_lector'}@{servidor.direccion}",
            # Lo mismo que lee el recolector, para comprobar de una vez que la
            # credencial sirve Y que el servidor deja leer lo que hace falta.
            "head -1 /proc/stat; nproc",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        salida, fallo = await asyncio.wait_for(proceso.communicate(), timeout=20)
    except asyncio.TimeoutError:
        return ComprobacionLectura(
            que="la credencial", ok=False,
            detalle="el servidor no respondio a tiempo (20 s)")
    except Exception as exc:
        return ComprobacionLectura(
            que="la credencial", ok=False, detalle=f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)

    texto = (salida or b"").decode("utf-8", "replace").strip()
    motivo = (fallo or b"").decode("utf-8", "replace").strip()
    if proceso.returncode == 0 and texto.startswith("cpu"):
        nucleos = texto.splitlines()[-1].strip()
        return ComprobacionLectura(
            que="la credencial sirve y /proc se lee", ok=True,
            detalle=f"sesion abierta como «{servidor.usuario}»; "
                    f"el servidor dice tener {nucleos} nucleos")
    return ComprobacionLectura(
        que="la credencial", ok=False,
        detalle=motivo.splitlines()[-1] if motivo else
                f"ssh termino con codigo {proceso.returncode}")


async def _probar_postgresql(servidor: ObservedServer) -> List[ComprobacionLectura]:
    """Se conecta de verdad y comprueba lo que O-D12 promete que se lee."""
    import asyncpg

    if not servidor.credencial_cifrada:
        return [ComprobacionLectura(
            que="conexion", ok=False,
            detalle="no hay credencial guardada para este servidor")]
    try:
        clave = _descifrar(servidor.credencial_cifrada)
    except Exception as exc:
        return [ComprobacionLectura(
            que="conexion", ok=False,
            detalle=f"la credencial guardada no se puede descifrar: {exc}")]

    base = (servidor.notas or "").strip() or "postgres"
    conexion = None
    lecturas: List[ComprobacionLectura] = []
    try:
        conexion = await asyncio.wait_for(asyncpg.connect(
            host=servidor.direccion, port=servidor.puerto,
            user=servidor.usuario or "kinetix_lector",
            password=clave, database=base, timeout=10), timeout=15)
        lecturas.append(ComprobacionLectura(
            que="conexion", ok=True,
            detalle=f"conectado a «{base}» como «{servidor.usuario}»"))
    except Exception as exc:
        return [ComprobacionLectura(
            que="conexion", ok=False, detalle=f"{type(exc).__name__}: {exc}")]

    try:
        for que, sql in (
            ("pg_stat_database (conexiones y transacciones)",
             "select count(*) from pg_stat_database"),
            ("pg_stat_activity (estado de las sesiones)",
             "select count(*) from pg_stat_activity"),
            ("pg_locks (bloqueos)", "select count(*) from pg_locks"),
            ("pg_stat_statements (consultas lentas)",
             "select count(*) from pg_stat_statements"),
        ):
            try:
                cuantos = await conexion.fetchval(sql)
                lecturas.append(ComprobacionLectura(
                    que=que, ok=True, detalle=f"{cuantos} filas visibles"))
            except Exception as exc:
                lecturas.append(ComprobacionLectura(
                    que=que, ok=False, detalle=f"{type(exc).__name__}: {exc}"))

        # Y lo que NO tiene que poder leer. Que falle aqui es lo correcto, y se
        # enseña asi para que el cliente lo vea.
        try:
            await conexion.fetchval("select count(*) from pg_class limit 1")
            catalogo = True
        except Exception:
            catalogo = False
        lecturas.append(ComprobacionLectura(
            que="acceso al catalogo (informativo)", ok=True,
            detalle="si" if catalogo else "no"))
    finally:
        await conexion.close()
    return lecturas


@router.post("/servidores/{servidor_id}/probar", response_model=ResultadoPrueba)
async def probar_servidor(
    servidor_id: uuid.UUID,
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    """O-D24: si se llega, qué se puede leer, y el error REAL cuando falla."""
    servidor = await _buscar(db, servidor_id)
    empezo = time.monotonic()
    lecturas: List[ComprobacionLectura] = []
    error: Optional[str] = None

    if servidor.tipo == "postgresql":
        lecturas = await _probar_postgresql(servidor)
        ok = bool(lecturas) and lecturas[0].ok
        if not ok:
            error = lecturas[0].detalle
        resumen = ("Se conecta a la base y se leen sus estadisticas"
                   if ok else "No se pudo conectar a la base")

    elif servidor.tipo == "windows":
        ok = False
        resumen = "Windows todavia no se puede probar desde Kinetix"
        error = ("El modo Windows esta declarado pero no implementado: haria "
                 "falta WinRM. Ver el reporte de la etapa O2c.")

    else:  # linux y otro
        alcanzable, saludo, fallo = await _saludo_tcp(
            servidor.direccion, servidor.puerto)
        lecturas.append(ComprobacionLectura(
            que=f"el puerto {servidor.puerto} responde", ok=alcanzable,
            detalle=saludo or (fallo or "abierto, sin saludo")))
        if not alcanzable:
            error = fallo
        if saludo.startswith("SSH-"):
            lecturas.append(ComprobacionLectura(
                que="habla SSH", ok=True, detalle=saludo))

        # La credencial NO se comprueba iniciando sesion: el backend de Kinetix
        # no lleva cliente de SSH. Anadir `openssh-client` a su imagen es una
        # dependencia nueva, y eso lo decide Fredy, no yo.
        #
        # Lo que se intenta en su lugar dice mas, cuando se puede: si estan
        # llegando metricas de este servidor, la credencial sirve, el servidor
        # deja leer y el camino hasta la base funciona. Hoy hace falta un token
        # de lectura que no existe todavia; ver `_hay_metricas`.
        if alcanzable:
            lecturas.append(await _probar_ssh(servidor))

        datos, fallo_metricas = await _hay_metricas(servidor, db)
        if datos is None:
            lecturas.append(ComprobacionLectura(
                que="llegan metricas de este servidor", ok=False,
                detalle=f"no se pudo comprobar: {fallo_metricas}"))
        elif datos["medidas"]:
            lecturas.append(ComprobacionLectura(
                que="llegan metricas de este servidor", ok=True,
                detalle=(f"la ultima, {_hace_cuanto(datos['ultima'])}. "
                         f"Medidas: {', '.join(datos['medidas'])}")))
        else:
            lecturas.append(ComprobacionLectura(
                que="llegan metricas de este servidor", ok=False,
                detalle="ninguna en las ultimas 24 horas. Si acaba de darlo de "
                        "alta es lo normal: falta configurar el recolector o "
                        "instalar el agente."))

        # El veredicto lo manda la credencial SOLO cuando se ha podido
        # comprobar. «Sin comprobar» no es «no sirve», y decir lo segundo
        # mandaria a alguien a buscar un fallo que a lo mejor no existe: por
        # eso se busca la etiqueta exacta del caso rechazado, no un prefijo.
        credencial = next((l for l in lecturas if l.que == "la credencial"), None)
        if credencial is not None and not credencial.ok:
            ok = False
            resumen = "Se llega al servidor, pero la credencial no sirve"
            error = credencial.detalle
        else:
            ok = alcanzable
            resumen = ("Se llega al servidor" if alcanzable
                       else "No se llega al servidor")

    return ResultadoPrueba(
        ok=ok, resumen=resumen, error=error, lecturas=lecturas,
        duracion_ms=int((time.monotonic() - empezo) * 1000),
    )


# ---------------------------------------------------------------------------
# O-D33 — el token de solo lectura
# ---------------------------------------------------------------------------
@router.get("/token-lectura")
async def estado_del_token_de_lectura(
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    """Si esta la columna y si hay token. **Nunca el token.**"""
    try:
        await db.execute(text(
            "SELECT influxdb_read_token_encrypted FROM monitoring_config LIMIT 1"))
        columna = True
    except Exception:
        await db.rollback()
        columna = False
    return {
        "columna_aplicada": columna,
        "hay_token": bool(await _token_de_lectura(db)) if columna else False,
        "sql": "docs/sql/o2c_influxdb_read_token.sql",
    }


@router.put("/token-lectura", status_code=204)
async def guardar_token_de_lectura(
    cuerpo: dict,
    _usuario: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Carga el token de solo lectura del cubo `infra` (O-D33). Solo admin.

    Igual que al leerlo, se escribe con SQL a mano para no obligar a que la
    columna exista en el modelo: hasta que Fredy aplique el ALTER, el resto de
    la pantalla de monitoreo tiene que seguir funcionando.
    """
    token = (cuerpo or {}).get("token") or ""
    if not token.strip():
        raise HTTPException(400, "Falta el token")

    config = (await db.execute(select(MonitoringConfig).limit(1))).scalar_one_or_none()
    if config is None:
        raise HTTPException(
            400, "No hay configuracion de monitoreo todavia: guardela primero")
    try:
        await db.execute(
            text("UPDATE monitoring_config SET influxdb_read_token_encrypted = :t "
                 "WHERE id = :i"),
            {"t": _cifrar(token.strip()), "i": config.id})
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            400, "No se pudo guardar. Si la columna no existe todavia, aplique "
                 "docs/sql/o2c_influxdb_read_token.sql. Detalle: "
                 f"{type(exc).__name__}")


# ---------------------------------------------------------------------------
# O-D25 — el generador de configuracion
# ---------------------------------------------------------------------------
@router.get("/servidores/{servidor_id}/configuracion",
            response_model=ConfiguracionServidor)
async def configuracion_del_servidor(
    servidor_id: uuid.UUID,
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    """Lo que hay que poner para que este servidor se empiece a medir.

    Si es sin agente, los parametros del recolector. Si es con agente, la orden
    de instalacion ya rellena — que **la ejecuta una persona** con acceso al
    servidor, no Kinetix (O-D28).
    """
    servidor = await _buscar(db, servidor_id)
    config = (await db.execute(select(MonitoringConfig).limit(1))).scalar_one_or_none()

    destino = (config.influxdb_url if config else "") or "http://influxdb:8086"
    org = (config.influxdb_org if config else "") or "performance"
    cubo = "infra"

    aviso_od28 = (
        "Kinetix genera esta configuracion; NO la ejecuta. La aplica una "
        "persona con acceso al servidor. Kinetix no guarda, ni pide, "
        "credenciales de administrador de nadie.")

    if servidor.modo == "agente":
        orden = "\n".join([
            "# 1. Deje el token en un fichero, para que no quede en la linea",
            "#    de ordenes, donde lo veria cualquiera con `ps`.",
            "printf '%s' '<EL TOKEN DE ESCRITURA>' > /tmp/kx_token",
            "chmod 600 /tmp/kx_token",
            "",
            "# 2. Instale el agente.",
            "sudo bash instalar_agente.sh \\",
            f"     --url {destino} \\",
            "     --token-fichero /tmp/kx_token \\",
            f"     --org {org} \\",
            f"     --cubo {cubo} \\",
            f"     --cliente '{await _nombre_cliente(db, servidor.client_id) or ''}' \\",
            f"     --host {servidor.name}",
            "",
            "# 3. Borre el fichero del token.",
            "rm -f /tmp/kx_token",
        ])
        return ConfiguracionServidor(
            servidor=servidor.name, modo="agente",
            titulo=f"Instalar el agente en «{servidor.name}»",
            explicacion=(
                f"Telegraf {VERSION_AGENTE} como servicio, con un usuario sin "
                "privilegios. Mide una vez por segundo. Los requisitos y lo que "
                "consume estan en docs/observabilidad/requisitos-con-agente.md — "
                "lea su seccion 6 antes de planificar con esto."),
            orden=orden, aviso=aviso_od28,
        )

    parametros = [
        ParametroConfiguracion(
            nombre="KX_OBJETIVOS", valor=servidor.direccion,
            explicacion="A qué servidor se conecta el recolector."),
        ParametroConfiguracion(
            nombre="KX_SSH_USUARIO", valor=servidor.usuario or "kinetix_lector",
            explicacion="El usuario de solo lectura. Sin shell de administracion "
                        "y sin sudo."),
        ParametroConfiguracion(
            nombre="KX_SSH_PUERTO", valor=str(servidor.puerto),
            explicacion="El puerto de SSH del servidor."),
        ParametroConfiguracion(
            nombre="KX_CLIENTE",
            valor=await _nombre_cliente(db, servidor.client_id) or "",
            explicacion="La etiqueta `cliente` que llevara cada metrica."),
        ParametroConfiguracion(
            nombre="KX_INFLUX_URL", valor=destino,
            explicacion="A dónde escribe el recolector."),
        ParametroConfiguracion(
            nombre="KX_INFLUX_ORG", valor=org,
            explicacion="La organizacion de InfluxDB."),
        ParametroConfiguracion(
            nombre="KX_INFLUX_BUCKET", valor=cubo,
            explicacion="El cubo de infraestructura, separado del de la prueba."),
    ]
    if servidor.tipo == "postgresql":
        parametros = [
            ParametroConfiguracion(
                nombre="KX_PG_DSN",
                valor=(f"postgres://{servidor.usuario or 'kinetix_lector'}:"
                       f"<LA CONTRASENA>@{servidor.direccion}:{servidor.puerto}/"
                       f"{(servidor.notas or 'postgres').strip()}?sslmode=disable"),
                explicacion="La conexion de solo lectura. La contrasena la pone "
                            "quien aplica la configuracion: Kinetix no la "
                            "escribe aqui (O-D26).",
                secreto=True),
        ] + parametros[3:]

    return ConfiguracionServidor(
        servidor=servidor.name, modo="sin_agente",
        titulo=f"Configurar el recolector para «{servidor.name}»",
        explicacion=(
            "No se instala nada en el servidor. El recolector entra por SSH con "
            "un usuario de solo lectura, o se conecta a la base con un rol con "
            "`pg_monitor`. Lo que se le pide al cliente esta en "
            "docs/observabilidad/requisitos-sin-agente.md."),
        parametros=parametros, aviso=aviso_od28,
    )
