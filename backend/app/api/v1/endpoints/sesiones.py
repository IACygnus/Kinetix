"""Las sesiones de monitoreo — ETAPA O2d.

    GET    /observabilidad/sesiones                 el listado (O-D36)
    POST   /observabilidad/sesiones                 crear (O-D37, paso 1)
    GET    /observabilidad/sesiones/{id}            una sesion
    PUT    /observabilidad/sesiones/{id}            editarla o cerrarla
    DELETE /observabilidad/sesiones/{id}            borrarla
    GET    /observabilidad/sesiones/{id}/jmeter     los valores, para copiarlos
    POST   /observabilidad/sesiones/{id}/jmx        subir un .jmx y recibirlo
                                                    con el listener puesto (O-D45)
    GET    /observabilidad/sesiones/{id}/metricas   lo que se pinta (O-D38, O-D39)

**La razon de ser de todo esto** es que hasta O2c una corrida era una cadena que
alguien tenia que copiar antes de cambiar de pestana. Aqui se guarda: sales,
vuelves, y sigue con sus metricas (O-D35, O-D40).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.observabilidad import _descifrar, _token_de_lectura
# O-D4: el nombre de la corrida tiene UNA sola definición, la de O1. Si una
# sesión lo generara por su cuenta, lo que JMeter escribe y lo que el recolector
# etiqueta podrían discrepar, y entonces no se cruzan.
from app.api.v1.endpoints.monitoring import nombre_de_corrida
from app.core.security import get_current_active_user, require_role
from app.db.models.client import Client
from app.db.models.monitoring import MonitoringConfig
from app.db.models.monitoring_session import MonitoringSession, sesion_servidores
from app.db.models.observed_server import ObservedServer
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.monitoring_session import (
    ConexionJMeter, GraficaServidor, MetricasDeServidor, MetricasDeSesion,
    SerieMetrica, ServidorDeSesion, SesionActualizar, SesionCrear, SesionLeer,
)
from app.services.observabilidad.jmx_listener import (
    JmxInvalido, insertar, mensaje,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ESCRIBE = require_role(["admin", "analyst"])

# Qué se pinta de cada tipo de servidor (O-D38). Cada entrada es:
#   (título, explicación, unidad, medida, [(campo, etiqueta), ...], transformación)
#
# La transformación es lo que convierte el número crudo en el que se enseña:
# `usage_idle` al revés es «CPU en uso», que es lo que la gente busca.
GRAFICAS_LINUX = [
    ("CPU", "Cuánto trabaja el procesador del servidor. Es lo primero que se "
            "mira cuando una prueba va lenta.", "%", "cpu",
     [("usage_idle", "CPU en uso")], "invertir"),
    ("Memoria", "Memoria en uso sobre el total.", "%", "mem",
     [("used_percent", "Memoria en uso")], None),
    ("Disco", "Espacio ocupado en los sistemas de ficheros del servidor.",
     "%", "disk", [("used_percent", "Disco en uso")], None),
    ("Red", "Bytes por segundo que entran y salen del servidor.", "B/s", "net",
     [("bytes_recv", "Entrada"), ("bytes_sent", "Salida")], "por_segundo"),
]

GRAFICAS_POSTGRES = [
    ("Conexiones", "Sesiones abiertas contra la base. Si se dispara, la "
                   "aplicación está abriendo más de las que cierra.", "",
     "postgresql", [("numbackends", "Conexiones")], None),
    ("Transacciones por segundo", "Confirmadas y revertidas. Las revertidas "
                                  "subiendo suelen ser errores.", "/s",
     "postgresql", [("xact_commit", "Confirmadas"),
                    ("xact_rollback", "Revertidas")], "por_segundo"),
]


# ---------------------------------------------------------------------------
async def _cargar(db: AsyncSession, sesion_id: uuid.UUID) -> MonitoringSession:
    fila = (await db.execute(
        select(MonitoringSession).where(MonitoringSession.id == sesion_id)
    )).scalar_one_or_none()
    if fila is None:
        raise HTTPException(404, "No existe esa sesión")
    return fila


async def _servidores_de(db: AsyncSession, sesion_id: uuid.UUID
                         ) -> List[ObservedServer]:
    return list((await db.execute(
        select(ObservedServer)
        .join(sesion_servidores,
              sesion_servidores.c.server_id == ObservedServer.id)
        .where(sesion_servidores.c.session_id == sesion_id)
        .order_by(ObservedServer.name)
    )).scalars().all())


async def _a_lectura(db: AsyncSession, sesion: MonitoringSession) -> SesionLeer:
    nombre_cliente = (await db.execute(
        select(Client.name).where(Client.id == sesion.client_id)
    )).scalar_one_or_none()
    servidores = await _servidores_de(db, sesion.id)
    return SesionLeer(
        id=sesion.id, nombre=sesion.nombre, client_id=sesion.client_id,
        cliente_nombre=nombre_cliente, proyecto=sesion.proyecto,
        corrida=sesion.corrida, estado=sesion.estado, notas=sesion.notas,
        servidores=[ServidorDeSesion(
            id=s.id, name=s.name, tipo=s.tipo, modo=s.modo,
            direccion=s.direccion) for s in servidores],
        creada_en=sesion.creada_en, empezo_en=sesion.empezo_en,
        termino_en=sesion.termino_en,
    )


async def _fijar_servidores(db: AsyncSession, sesion_id: uuid.UUID,
                            ids: List[uuid.UUID]) -> None:
    await db.execute(delete(sesion_servidores).where(
        sesion_servidores.c.session_id == sesion_id))
    for server_id in dict.fromkeys(ids):   # sin repetidos, en su orden
        existe = (await db.execute(select(ObservedServer.id).where(
            ObservedServer.id == server_id))).scalar_one_or_none()
        if existe is None:
            raise HTTPException(404, f"No existe el servidor {server_id}")
        await db.execute(insert(sesion_servidores).values(
            session_id=sesion_id, server_id=server_id))


async def _corrida_libre(db: AsyncSession, cliente: str, proyecto: str) -> str:
    """El nombre de corrida de O-D4, y si ya está cogido, uno que no lo esté.

    `nombre_de_corrida()` tiene resolución de MINUTO
    (`<cliente>-<proyecto>-<aaaammdd-hhmm>`), así que dos sesiones del mismo
    cliente y proyecto creadas en el mismo minuto salían con la misma cadena y
    chocaban contra el índice único: **500 Internal Server Error**. Pasa de
    verdad —creas una sesión, ves que le pusiste mal el nombre y creas otra— y
    era un error feo para algo tan normal.

    No se cambia el formato de O-D4: es la definición única que comparten el
    Backend Listener y el recolector. Se le añade un sufijo solo cuando hace
    falta, que es casi nunca.
    """
    base = nombre_de_corrida(cliente, proyecto)
    candidata = base
    for intento in range(2, 60):
        existe = (await db.execute(select(MonitoringSession.id).where(
            MonitoringSession.corrida == candidata))).scalar_one_or_none()
        if existe is None:
            return candidata
        candidata = f"{base}-{intento}"
    # Sesenta sesiones del mismo cliente y proyecto en el mismo minuto no es un
    # caso de uso: es alguien dándole a un botón en bucle.
    raise HTTPException(
        409, "Demasiadas sesiones de este proyecto en el mismo minuto. "
             "Espera unos segundos y vuelve a intentarlo.")


# ---------------------------------------------------------------------------
# El listado y el CRUD
# ---------------------------------------------------------------------------
@router.get("/sesiones", response_model=List[SesionLeer])
async def listar_sesiones(
    client_id: Optional[uuid.UUID] = None,
    _usuario: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    consulta = select(MonitoringSession)
    if client_id:
        consulta = consulta.where(MonitoringSession.client_id == client_id)
    filas = (await db.execute(
        consulta.order_by(MonitoringSession.creada_en.desc()))).scalars().all()
    return [await _a_lectura(db, s) for s in filas]


@router.post("/sesiones", response_model=SesionLeer, status_code=201)
async def crear_sesion(
    datos: SesionCrear,
    usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    cliente = (await db.execute(
        select(Client).where(Client.id == datos.client_id))).scalar_one_or_none()
    if cliente is None:
        raise HTTPException(404, "No existe ese cliente")

    repetida = (await db.execute(select(MonitoringSession).where(
        MonitoringSession.client_id == datos.client_id,
        MonitoringSession.nombre == datos.nombre))).scalar_one_or_none()
    if repetida is not None:
        raise HTTPException(
            409, f"«{cliente.name}» ya tiene una sesión llamada «{datos.nombre}»")

    sesion = MonitoringSession(
        id=uuid.uuid4(), nombre=datos.nombre, client_id=datos.client_id,
        proyecto=datos.proyecto, notas=datos.notas,
        corrida=await _corrida_libre(db, cliente.name, datos.proyecto),
        estado="preparada", creada_por=usuario.id,
    )
    db.add(sesion)
    await db.flush()
    await _fijar_servidores(db, sesion.id, datos.servidores)
    await db.commit()
    await db.refresh(sesion)
    return await _a_lectura(db, sesion)


@router.get("/sesiones/{sesion_id}", response_model=SesionLeer)
async def ver_sesion(
    sesion_id: uuid.UUID,
    _usuario: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await _a_lectura(db, await _cargar(db, sesion_id))


@router.put("/sesiones/{sesion_id}", response_model=SesionLeer)
async def actualizar_sesion(
    sesion_id: uuid.UUID,
    datos: SesionActualizar,
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    sesion = await _cargar(db, sesion_id)
    cambios = datos.model_dump(exclude_unset=True)

    servidores = cambios.pop("servidores", None)
    if servidores is not None:
        await _fijar_servidores(db, sesion.id, servidores)

    if cambios.get("estado") == "terminada" and sesion.termino_en is None:
        sesion.termino_en = datetime.utcnow()

    for campo, valor in cambios.items():
        setattr(sesion, campo, valor)
    await db.commit()
    await db.refresh(sesion)
    return await _a_lectura(db, sesion)


@router.delete("/sesiones/{sesion_id}", status_code=204)
async def borrar_sesion(
    sesion_id: uuid.UUID,
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    """Borra la SESIÓN. Las métricas siguen en InfluxDB: no se toca ni un punto."""
    sesion = await _cargar(db, sesion_id)
    await db.delete(sesion)
    await db.commit()


# ---------------------------------------------------------------------------
# O-D45 — conectar JMeter
# ---------------------------------------------------------------------------
async def _datos_de_escritura(db: AsyncSession) -> Tuple[str, str, str]:
    """(url de escritura, token, aviso) — lo que necesita el Backend Listener."""
    config = (await db.execute(
        select(MonitoringConfig).limit(1))).scalar_one_or_none()
    if config is None:
        return "", "", ("No hay configuración de monitoreo todavía. "
                        "Cárgala en Monitoreo → Configuración.")
    base = (config.influxdb_url or "http://influxdb:8086").rstrip("/")
    org = config.influxdb_org or "performance"
    cubo = config.influxdb_bucket or "jmeter"
    url = f"{base}/api/v2/write?org={org}&bucket={cubo}"

    token = ""
    if config.influxdb_token_encrypted:
        try:
            token = _descifrar(config.influxdb_token_encrypted)
        except Exception:
            return url, "", ("El token de InfluxDB guardado no se puede "
                             "descifrar. Vuelve a cargarlo.")
    if not token:
        return url, "", ("No hay token de escritura de InfluxDB. Sin él, el "
                         "JMeter no podrá enviar sus métricas.")
    return url, token, ""


@router.get("/sesiones/{sesion_id}/jmeter", response_model=ConexionJMeter)
async def conexion_jmeter(
    sesion_id: uuid.UUID,
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    """Los valores, para quien prefiera copiarlos a mano (la opción avanzada)."""
    sesion = await _cargar(db, sesion_id)
    url, token, aviso = await _datos_de_escritura(db)
    return ConexionJMeter(
        url=url, token=token, corrida=sesion.corrida, aviso=aviso,
        parametros=[
            {"nombre": "influxdbUrl", "valor": url,
             "explicacion": "A dónde manda JMeter sus métricas."},
            {"nombre": "influxdbToken", "valor": token,
             "explicacion": "Token de solo escritura: no sirve para leer nada."},
            {"nombre": "application", "valor": sesion.corrida,
             "explicacion": "El nombre de esta sesión. Es por lo que se cruzan "
                            "la prueba y los servidores."},
            {"nombre": "measurement", "valor": "jmeter",
             "explicacion": "No se cambia."},
            {"nombre": "summaryOnly", "valor": "false",
             "explicacion": "En «false» para ver transacción por transacción."},
        ],
    )


@router.post("/sesiones/{sesion_id}/jmx")
async def poner_listener(
    sesion_id: uuid.UUID,
    archivo: UploadFile = File(...),
    _usuario: User = Depends(ESCRIBE),
    db: AsyncSession = Depends(get_db),
):
    """Sube un `.jmx` y te lo devuelve con el Backend Listener puesto (O-D45).

    El original no se toca (O-D46): lo que baja es una copia.
    """
    sesion = await _cargar(db, sesion_id)
    url, token, aviso = await _datos_de_escritura(db)
    if not token:
        raise HTTPException(400, aviso)

    contenido = await archivo.read()
    if len(contenido) > 20 * 1024 * 1024:
        raise HTTPException(400, "El archivo pasa de 20 MB. ¿Es un .jmx?")

    try:
        nuevo, informe = insertar(contenido, url, token, sesion.corrida)
    except JmxInvalido as exc:
        raise HTTPException(400, str(exc))

    base = (archivo.filename or "plan.jmx").rsplit(".", 1)[0]
    return StreamingResponse(
        iter([nuevo]), media_type="application/xml; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="{base}-{sesion.corrida}.jmx"',
            # La pantalla lee esto para decir qué pasó sin abrir el archivo.
            # Una cabecera HTTP solo admite ASCII, así que las tildes viajan
            # transliteradas; el texto se entiende igual.
            "X-Kinetix-Mensaje": mensaje(informe).encode("ascii", "replace").decode(),
            "X-Kinetix-Reemplazado": "1" if informe["reemplazado"] else "0",
            # Que el navegador pueda LEERLAS lo decide `expose_headers` del
            # CORSMiddleware, en main.py. Ponerlas aquí no basta.
        })


# ---------------------------------------------------------------------------
# O-D38 y O-D39 — las métricas que se pintan DENTRO de Kinetix
# ---------------------------------------------------------------------------
async def _flux(db: AsyncSession, consulta: str) -> Tuple[Optional[str], str]:
    """Lanza una consulta con el token de LECTURA. Devuelve (csv, aviso)."""
    config = (await db.execute(
        select(MonitoringConfig).limit(1))).scalar_one_or_none()
    if config is None or not config.influxdb_url:
        return None, "No hay configuración de monitoreo."

    token = await _token_de_lectura(db)
    if not token:
        return None, (
            "Falta el token de solo lectura del depósito de infraestructura. "
            "Sin él no se pueden dibujar las gráficas de los servidores. "
            "Cárgalo aquí arriba: el token de monitoreo que ya hay es de solo "
            "escritura a propósito y no puede leer.")

    try:
        async with httpx.AsyncClient(timeout=40.0) as cliente:
            respuesta = await cliente.post(
                f"{config.influxdb_url.rstrip('/')}/api/v2/query",
                params={"org": config.influxdb_org or "performance"},
                headers={"Authorization": f"Token {token}",
                         "Content-Type": "application/vnd.flux",
                         "Accept": "application/csv"},
                content=consulta)
    except Exception as exc:
        return None, f"No se pudo consultar InfluxDB: {type(exc).__name__}"

    if respuesta.status_code >= 400:
        return None, (f"InfluxDB respondió {respuesta.status_code}. Si es 401 o "
                      f"404, el token de lectura no alcanza ese depósito.")
    return respuesta.text, ""


def _series(csv: str, columna_serie: str) -> Dict[str, List[List[float]]]:
    """Agrupa el CSV de InfluxDB en {etiqueta: [[ms, valor], ...]}.

    InfluxDB emite una cabecera NUEVA cada vez que cambia el esquema, no solo
    una al principio; darlo por hecho desplaza las columnas (lección de O2c).
    """
    salida: Dict[str, List[List[float]]] = {}
    cabecera: List[str] = []
    for linea in csv.splitlines():
        if not linea.strip() or linea.startswith("#"):
            continue
        trozos = linea.split(",")
        if len(trozos) > 1 and trozos[1] == "result":
            cabecera = trozos
            continue
        if not cabecera:
            continue
        fila = dict(zip(cabecera, trozos))
        marca, valor = fila.get("_time"), fila.get("_value")
        etiqueta = fila.get(columna_serie) or fila.get("_field") or "valor"
        if not marca or valor in (None, ""):
            continue
        try:
            momento = datetime.fromisoformat(marca.replace("Z", "+00:00"))
            salida.setdefault(etiqueta, []).append(
                [momento.timestamp() * 1000.0, float(valor)])
        except ValueError:
            continue
    for puntos in salida.values():
        puntos.sort(key=lambda par: par[0])
    return salida


def _ventana(cada: int) -> str:
    """Cada cuánto agrupar, para no mandarle 5.000 puntos a una gráfica."""
    return f"{max(cada, 5)}s"


@router.get("/sesiones/{sesion_id}/metricas", response_model=MetricasDeSesion)
async def metricas_de_la_sesion(
    sesion_id: uuid.UUID,
    minutos: int = Query(default=60, ge=1, le=1440),
    _usuario: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """O-D38 y O-D39: la prueba arriba, la infraestructura abajo, mismo tiempo.

    Para una sesión terminada el rango sale de sus propias fechas (O-D40): así
    se abre meses después y enseña lo que pasó, no una pantalla vacía.
    """
    sesion = await _cargar(db, sesion_id)
    servidores = await _servidores_de(db, sesion.id)

    if sesion.estado == "terminada" and sesion.termino_en:
        # Dos minutos de margen a cada lado: el antes y el después son la mitad
        # de la historia. Si nunca llegó a empezar, se toma desde que se creó.
        inicio = (sesion.empezo_en or sesion.creada_en
                  or sesion.termino_en) - timedelta(minutes=2)
        fin = sesion.termino_en + timedelta(minutes=2)
        desde = inicio.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        hasta = fin.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        desde, hasta = f"-{minutos}m", "now()"

    paso = max(5, (minutos * 60) // 240)   # ~240 puntos por serie, como mucho
    ventana = _ventana(paso)
    aviso = ""
    hay_datos = False

    # ---------- Arriba: la prueba ----------
    prueba: List[GraficaServidor] = []
    csv, fallo = await _flux(db, f'''
from(bucket: "jmeter")
  |> range(start: {desde}, stop: {hasta})
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["application"] == "{sesion.corrida}")
  |> filter(fn: (r) => r["_field"] == "avg" and r["statut"] == "all")
  |> aggregateWindow(every: {ventana}, fn: mean, createEmpty: false)
  |> keep(columns: ["_time", "_value", "transaction"])
''')
    if fallo:
        aviso = fallo
    elif csv:
        series = _series(csv, "transaction")
        if series:
            hay_datos = True
            prueba.append(GraficaServidor(
                titulo="Tiempo de respuesta",
                explicacion="Lo que tardó cada transacción de tu prueba.",
                unidad="ms",
                series=[SerieMetrica(etiqueta=e, unidad="ms", puntos=p)
                        for e, p in sorted(series.items())]))

    csv, _ = await _flux(db, f'''
from(bucket: "jmeter")
  |> range(start: {desde}, stop: {hasta})
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["application"] == "{sesion.corrida}")
  |> filter(fn: (r) => r["_field"] == "count" and r["statut"] == "all")
  |> aggregateWindow(every: {ventana}, fn: sum, createEmpty: false)
  |> keep(columns: ["_time", "_value", "transaction"])
''')
    if csv:
        series = _series(csv, "transaction")
        if series:
            hay_datos = True
            prueba.append(GraficaServidor(
                titulo="Peticiones", explicacion="Cuántas se lanzaron.",
                unidad="", series=[SerieMetrica(etiqueta=e, puntos=p)
                                   for e, p in sorted(series.items())]))

    # ---------- Abajo: la infraestructura ----------
    infraestructura: List[MetricasDeServidor] = []
    for servidor in servidores:
        definiciones = (GRAFICAS_POSTGRES if servidor.tipo == "postgresql"
                        else GRAFICAS_LINUX)
        graficas: List[GraficaServidor] = []

        for titulo, explica, unidad, medida, campos, transformacion in definiciones:
            condicion = " or ".join(
                f'r["_field"] == "{campo}"' for campo, _ in campos)
            extra = ""
            if transformacion == "por_segundo":
                # Son contadores desde que arrancó la máquina: lo que interesa
                # es cuánto suben por segundo, no su valor absoluto.
                extra = "  |> toFloat()\n  |> derivative(unit: 1s, nonNegative: true)\n"
            filtro_host = f'  |> filter(fn: (r) => r["host"] == "{servidor.name}")\n'

            # **Se cruza por SERVIDOR y VENTANA DE TIEMPO, no por la etiqueta
            # `corrida`.** Y es una corrección, no un descuido:
            #
            # La etiqueta la pone el recolector, y ponérsela exige ir a
            # reconfigurarlo antes de cada prueba (en el laboratorio,
            # `scripts/lab_corrida.sh`). Nadie se acuerda de hacer eso desde una
            # pantalla, y en casa de un cliente Kinetix no tiene ningún canal
            # para tocarle el recolector. Filtrando por `corrida` la mitad de
            # abajo salía SIEMPRE vacía — que es exactamente la queja que abrió
            # esta etapa.
            #
            # Las métricas de infraestructura son continuas: el servidor existe
            # antes y después de la prueba. Una sesión es una VENTANA sobre
            # ellas. La etiqueta se sigue escribiendo y el tablero de Grafana la
            # sigue usando; aquí no hace falta.
            csv, fallo = await _flux(db, f'''
from(bucket: "infra")
  |> range(start: {desde}, stop: {hasta})
  |> filter(fn: (r) => r["_measurement"] == "{medida}")
{filtro_host}  |> filter(fn: (r) => {condicion})
{extra}  |> aggregateWindow(every: {ventana}, fn: mean, createEmpty: false)
  |> keep(columns: ["_time", "_value", "_field"])
''')
            if fallo:
                aviso = aviso or fallo
                continue
            if not csv:
                continue
            series = _series(csv, "_field")
            if not series:
                continue

            nombres = dict(campos)
            lineas = []
            for campo, puntos in series.items():
                if transformacion == "invertir":
                    puntos = [[t, 100.0 - v] for t, v in puntos]
                lineas.append(SerieMetrica(
                    etiqueta=nombres.get(campo, campo), unidad=unidad,
                    puntos=puntos))
            if lineas:
                hay_datos = True
                graficas.append(GraficaServidor(
                    titulo=titulo, explicacion=explica, unidad=unidad,
                    series=sorted(lineas, key=lambda s: s.etiqueta)))

        infraestructura.append(MetricasDeServidor(
            servidor=servidor.name, tipo=servidor.tipo, graficas=graficas))

    # Los avisos se dicen por separado, porque son cosas distintas: puede haber
    # servidores y no haber prueba todavía, que es lo normal nada más crearla.
    if not aviso:
        if not servidores:
            aviso = ("Esta sesión no tiene ningún servidor marcado, así que "
                     "solo puede enseñar las métricas de la prueba. Edítala "
                     "para añadirlos.")
        elif not prueba:
            aviso = ("Todavía no ha llegado ninguna métrica de tu prueba. "
                     "Lanza el .jmx que descargaste y aparecerán arriba en unos "
                     "segundos. Lo de abajo son tus servidores, que se miden "
                     "todo el tiempo.")
        elif not any(s.graficas for s in infraestructura):
            aviso = ("Llegan las métricas de la prueba pero no las de los "
                     "servidores. Comprueba en Servidores que su conexión "
                     "funciona, y que el nombre del servidor aquí es el mismo "
                     "con el que el recolector los publica.")

    # La sesión se marca sola: en cuanto llega su primera métrica, está en curso.
    if hay_datos and sesion.estado == "preparada":
        sesion.estado = "en_curso"
        sesion.empezo_en = sesion.empezo_en or datetime.utcnow()
        await db.commit()

    return MetricasDeSesion(
        corrida=sesion.corrida, desde=desde, hasta=hasta,
        prueba=prueba, infraestructura=infraestructura,
        aviso=aviso, hay_datos=hay_datos,
    )
