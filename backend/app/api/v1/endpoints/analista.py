"""El «Analista IA» — BLOQUE 5 (reporte 147).

    POST   /analista/sesiones                    crear: JTL (1-5), cliente, proyecto, tipo
    GET    /analista/sesiones                    las mías (admin: todas)
    GET    /analista/sesiones/{id}               la sesión: ficha, mensajes, adjuntos
    PATCH  /analista/sesiones/{id}               lo que el analista toca a mano
    POST   /analista/sesiones/{id}/adjuntos      el CSV/XML de JMeter con el detalle de los errores
    POST   /analista/sesiones/{id}/mensajes      un turno del chat (una llamada a la IA)
    POST   /analista/sesiones/{id}/generar       el informe, por el mismo camino que /upload

Admin y analista. **Cada analista ve solo las suyas**: la de otro responde 404,
como si no existiera. El admin ve todas.

Las cifras del JTL y los resultados de los criterios los calcula el servidor:
el PATCH no los acepta (422) y la IA no los toca.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.upload import (UPLOAD_DIR, _get_assigned_client_ids, parsear_archivos,
                                         procesar_subida)
from app.core.security import require_role
from app.db.models.analista import AnalysisAttachment, AnalysisSession
from app.db.models.client import Client
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.analista import CambiosFicha, MensajeEntrada
from app.services.ai import contexto_prompt
from app.services.analista import chat as CH
from app.services.analista import errores as ER
from app.services.analista import ficha as FI
from app.services.analista import prompt as PA

logger = logging.getLogger(__name__)
router = APIRouter()

ROL = require_role(["admin", "analyst"])
TIPOS_PRUEBA = {"load", "stress", "endurance", "scalability", "spike", "smoke"}
UNIDADES = {"TPS", "UVC"}
MAX_JTL = 5


# ------------------------------------------------------------------ ayudas

async def _sesion(db: AsyncSession, usuario: User, sid: str) -> AnalysisSession:
    try:
        clave = uuid.UUID(sid)
    except ValueError:
        raise HTTPException(404, "La sesión no existe")
    s = await db.get(AnalysisSession, clave)
    if s is None or (usuario.role != "admin" and s.user_id != usuario.id):
        raise HTTPException(404, "La sesión no existe")
    return s


async def _adjuntos(db: AsyncSession, sid) -> List[AnalysisAttachment]:
    r = await db.execute(select(AnalysisAttachment).where(AnalysisAttachment.session_id == sid)
                         .order_by(AnalysisAttachment.created_at))
    return list(r.scalars())


def _adjunto_lectura(a: AnalysisAttachment) -> Dict[str, Any]:
    """Nunca la ruta ni el contenido del archivo: solo su resumen, ya enmascarado."""
    return {"id": str(a.id), "nombre": a.nombre, "formato": a.formato, "tamano": a.tamano,
            "execution_id": str(a.execution_id) if a.execution_id else None,
            "creado": a.created_at.isoformat(timespec="seconds"), "resumen": a.resumen}


async def _lectura(db: AsyncSession, s: AnalysisSession) -> Dict[str, Any]:
    return {
        "id": str(s.id),
        "estado": s.estado,
        "cliente": s.client_name,
        "cliente_id": str(s.client_id) if s.client_id else None,
        "proyecto": s.project,
        "tipo": s.test_type,
        "unidad": s.metric_unit,
        "jtl": [j["nombre"] for j in (s.jtl or [])],
        # Lo que empieza por «_» es de uso interno (el bloque de la ejecución
        # que recibe el chat): no es contrato de la pantalla.
        "ficha": {k: v for k, v in (s.ficha or {}).items() if not k.startswith("_")},
        "mensajes": s.mensajes or [],
        "adjuntos": [_adjunto_lectura(a) for a in await _adjuntos(db, s.id)],
        "execution_id": str(s.execution_id) if s.execution_id else None,
        "creada": s.created_at.isoformat(timespec="seconds"),
        "actualizada": s.updated_at.isoformat(timespec="seconds") if s.updated_at else None,
    }


def _cargador(s: AnalysisSession):
    """Lee el JTL otra vez, solo si un criterio de proceso lo necesita."""
    def cargar():
        rutas = [j["ruta"] for j in s.jtl]
        nombres = [j["nombre"] for j in s.jtl]
        _df, _m, parser = parsear_archivos(rutas, nombres)
        return parser.df_main if getattr(parser, "df_main", None) is not None and len(parser.df_main) else parser.df
    return cargar


def _abierta(s: AnalysisSession) -> None:
    if s.estado != "abierta":
        raise HTTPException(409, "La sesión ya se generó (o se está generando): la ficha no se puede cambiar")


# ------------------------------------------------------------------ crear

@router.post("/sesiones", status_code=201)
async def crear_sesion(
    files: List[UploadFile] = File(...),
    proyecto: str = Form(..., min_length=1, max_length=255),
    tipo: str = Form("load"),
    client_id: str = Form(""),
    unidad: str = Form("TPS"),
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(ROL),
):
    """La ventana inicial: la prueba y sus JTL. **Sin criterios**: esos se
    conversan después. Devuelve la sesión con la ficha ya armada."""
    if not files or len(files) > MAX_JTL:
        raise HTTPException(400, f"Hace falta entre 1 y {MAX_JTL} archivos JTL")
    if tipo not in TIPOS_PRUEBA:
        raise HTTPException(400, f"Tipo de prueba inválido. Opciones: {sorted(TIPOS_PRUEBA)}")
    if unidad not in UNIDADES:
        raise HTTPException(400, "La unidad es TPS o UVC")
    for f in files:
        if not f.filename or not f.filename.endswith((".jtl", ".csv", ".xml")):
            raise HTTPException(400, f"Solo archivos .jtl, .csv o .xml: {f.filename}")
    proyecto = proyecto.strip()
    if not proyecto:
        raise HTTPException(400, "El proyecto es obligatorio")

    cliente = None
    if client_id:
        try:
            cliente = await db.get(Client, uuid.UUID(client_id))
        except ValueError:
            cliente = None
        if cliente is None:
            raise HTTPException(400, "El cliente no existe")
        if usuario.role != "admin" and cliente.id not in await _get_assigned_client_ids(db, usuario):
            raise HTTPException(403, "Ese cliente no está asignado a tu usuario")

    # Los JTL se guardan con el MISMO nombre que usa /upload (`<ts>[_i]_<nombre>`):
    # el informe y sus gráficas encuentran el archivo por su nombre original.
    UPLOAD_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rutas, nombres = [], []
    try:
        for i, f in enumerate(files):
            nombre = Path(f.filename).name
            ruta = UPLOAD_DIR / f"{ts}{f'_{i}' if len(files) > 1 else ''}_{nombre}"
            async with aiofiles.open(ruta, "wb") as out:
                await out.write(await f.read())
            rutas.append(str(ruta))
            nombres.append(nombre)
        try:
            _df, metrics, parser = await asyncio.to_thread(parsear_archivos, rutas, nombres)
            ficha = await asyncio.to_thread(
                FI.construir, parser, metrics, cliente=cliente.name if cliente else None,
                cliente_id=str(cliente.id) if cliente else None, proyecto=proyecto, tipo=tipo,
                unidad=unidad, jtl=nombres)
            # D: el bloque de la ejecución que recibe el chat, sin datos del
            # analista (esos van en la ficha). Se calcula una vez: el JTL no cambia.
            ficha["_bloque"] = (await asyncio.to_thread(
                contexto_prompt.contexto_de_parser, parser, tipo, unidad,
                {"analista": {"estado_criterios": "sin_declarar"}}, metrics))[0]
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Analista: no se pudo leer el JTL ({type(e).__name__})")
            raise HTTPException(400, f"No se pudo leer el JTL: {e}")
        FI.recalcular(ficha)
    except Exception:
        for r in rutas:
            Path(r).unlink(missing_ok=True)
        raise

    # D.10: el primer mensaje. Con IA, lo escribe ella; sin IA, uno fijo equivalente.
    primero = await CH.primer_mensaje(ficha, ficha["_bloque"], await llamador(db))
    s = AnalysisSession(user_id=usuario.id, client_id=cliente.id if cliente else None,
                        client_name=cliente.name if cliente else None, project=proyecto,
                        test_type=tipo, metric_unit=unidad,
                        jtl=[{"ruta": r, "nombre": n} for r, n in zip(rutas, nombres)],
                        ficha=ficha, mensajes=[primero], estado="abierta")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    logger.info(f"Analista: sesion {s.id} creada ({len(rutas)} JTL)")
    return await _lectura(db, s)


# ------------------------------------------------------------------ leer

@router.get("/sesiones")
async def listar_sesiones(db: AsyncSession = Depends(get_db), usuario: User = Depends(ROL)):
    q = select(AnalysisSession).order_by(AnalysisSession.updated_at.desc()).limit(200)
    if usuario.role != "admin":
        q = q.where(AnalysisSession.user_id == usuario.id)
    filas = (await db.execute(q)).scalars().all()
    return [{"id": str(s.id), "estado": s.estado, "cliente": s.client_name, "proyecto": s.project,
             "tipo": s.test_type, "criterios": (s.ficha or {}).get("criterios", {}).get("estado"),
             "listo": (s.ficha or {}).get("listo"),
             "execution_id": str(s.execution_id) if s.execution_id else None,
             "creada": s.created_at.isoformat(timespec="seconds"),
             "actualizada": s.updated_at.isoformat(timespec="seconds") if s.updated_at else None}
            for s in filas]


@router.get("/sesiones/{sid}")
async def leer_sesion(sid: str, db: AsyncSession = Depends(get_db), usuario: User = Depends(ROL)):
    return await _lectura(db, await _sesion(db, usuario, sid))


# ------------------------------------------------------------------ PATCH

@router.patch("/sesiones/{sid}")
async def cambiar_ficha(sid: str, cambios: CambiosFicha, db: AsyncSession = Depends(get_db),
                        usuario: User = Depends(ROL)):
    """Casillas, relato, criterios, ambiente y versión, pendientes. Las cifras y
    los resultados no: el esquema los rechaza con 422."""
    s = await _sesion(db, usuario, sid)
    _abierta(s)
    ficha = copy.deepcopy(s.ficha)
    try:
        tocados = FI.aplicar_patch(ficha, cambios.model_dump(exclude_unset=True))
    except FI.CambioInvalido as e:
        raise HTTPException(422, str(e))
    await asyncio.to_thread(FI.recalcular, ficha, _cargador(s), tocados)
    s.ficha = ficha
    s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(s)
    return await _lectura(db, s)


# ------------------------------------------------------------------ adjuntos (B)

async def asociar_adjuntos(db: AsyncSession, session_id, execution_id) -> int:
    """B.8: al generar, los adjuntos quedan enlazados a la ejecución como
    evidencia (`analysis_attachments.execution_id`). La pantalla de Evidencias
    todavía no los pinta: el enlace queda en el modelo."""
    adjuntos = await _adjuntos(db, session_id)
    for a in adjuntos:
        a.execution_id = execution_id
    return len(adjuntos)


MAX_ADJUNTOS = 5


@router.post("/sesiones/{sid}/adjuntos", status_code=201)
async def adjuntar_errores(sid: str, archivo: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                           usuario: User = Depends(ROL)):
    """El CSV o XML de JMeter con el detalle de los errores. Devuelve la sesión
    con su resumen, ya enmascarado. Ni el contenido ni los ejemplos van al log."""
    s = await _sesion(db, usuario, sid)
    _abierta(s)
    nombre = Path(archivo.filename or "").name
    formato = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if formato not in ("csv", "xml"):
        raise HTTPException(415, "Solo se admiten archivos .csv o .xml de JMeter")
    if len(await _adjuntos(db, s.id)) >= MAX_ADJUNTOS:
        raise HTTPException(409, f"Una sesión admite como máximo {MAX_ADJUNTOS} archivos de errores")
    partes, total = [], 0
    while True:
        trozo = await archivo.read(1024 * 1024)
        if not trozo:
            break
        total += len(trozo)
        if total > ER.TOPE_BYTES:
            raise HTTPException(413, f"El archivo pasa del tope de {ER.TOPE_BYTES // (1024 * 1024)} MB")
        partes.append(trozo)
    datos = b"".join(partes)
    fallos_jtl = {p["label"]: p["fallos"] for p in (s.ficha.get("fallos") or {}).get("por_transaccion") or []}
    try:
        resumen = await asyncio.to_thread(ER.resumir, datos, formato, fallos_jtl)
    except ER.ArchivoInvalido as e:
        raise HTTPException(400, f"No se pudo leer el archivo de errores: {e}")

    aid = uuid.uuid4()
    carpeta = UPLOAD_DIR / "analista" / str(s.id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{aid}.{formato}"
    async with aiofiles.open(ruta, "wb") as out:
        await out.write(datos)
    a = AnalysisAttachment(id=aid, session_id=s.id, nombre=nombre[:255], formato=formato, ruta=str(ruta),
                           tamano=total, resumen=resumen)
    db.add(a)
    ficha = copy.deepcopy(s.ficha)
    ficha["errores_detalle"]["adjuntos"].append(ER.resumen_corto(str(aid), nombre, resumen))
    FI.recalcular(ficha)
    s.ficha = ficha
    s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(s)
    logger.info(f"Analista: adjunto {aid} en la sesion {s.id} ({formato}, {total} bytes, "
                f"{resumen['errores']} errores, cuadra={resumen['cruce']['cuadra']})")
    return await _lectura(db, s)


# ------------------------------------------------------------------ la IA (D)

async def llamador(db: AsyncSession) -> CH.Llamar:
    """La función que habla con la IA configurada, o una que contesta «no hay
    IA» sin llamar a nadie. Las suites la sustituyen (`llamador = …`)."""
    from app.services.ai import origen
    from app.services.ai.gemini import get_gemini_analyzer, load_ai_config_from_db, update_ai_usage_in_db
    try:
        conf = await load_ai_config_from_db(db)
    except Exception:
        conf = {}
    if not conf or conf.get("limit_reached") or not conf.get("api_key"):
        motivo = (f"se alcanzó el límite {conf['limit_reached']} de la IA" if conf.get("limit_reached")
                  else "la IA no está configurada")

        async def sin_ia(prompt: str, sistema: str, sanear: bool) -> Tuple[Optional[str], str]:
            return None, motivo
        return sin_ia

    async def con_ia(prompt: str, sistema: str, sanear: bool) -> Tuple[Optional[str], str]:
        try:
            an = get_gemini_analyzer(provider=conf.get("provider", ""), model_name=conf.get("model_name", ""),
                                     api_key=conf.get("api_key", ""),
                                     reasoning_effort=conf.get("reasoning_effort") or "")
        except Exception as e:
            return None, f"no se pudo preparar la IA ({type(e).__name__})"
        texto, fallo = await origen.llamar(an._generate, prompt, section_name="analista_chat",
                                           max_retries=2, sistema=sistema, sanear=sanear)
        try:
            await update_ai_usage_in_db(db)
            await db.commit()
        except Exception:
            await db.rollback()
        if not texto:
            tipo = (fallo or {}).get("tipo") or "error"
            return None, origen.MOTIVOS.get(tipo, tipo)
        return texto, ""
    return con_ia


# ------------------------------------------------------------------ límites (D.13)

MAX_MENSAJES_ANALISTA = 30          # por sesión
RITMO_MENSAJES = 6                  # por usuario…
RITMO_VENTANA_S = 60.0              # …en este tiempo
_ritmo: Dict[str, deque] = defaultdict(deque)


def _comprobar_ritmo(usuario: User) -> None:
    """Por proceso: con varios workers, cada uno lleva su cuenta (reporte 147)."""
    ahora = time.monotonic()
    cola = _ritmo[str(usuario.id)]
    while cola and ahora - cola[0] > RITMO_VENTANA_S:
        cola.popleft()
    if len(cola) >= RITMO_MENSAJES:
        raise HTTPException(429, f"Demasiados mensajes seguidos: espera un poco (máximo {RITMO_MENSAJES} "
                                 f"por minuto)")
    cola.append(ahora)


# ------------------------------------------------------------------ mensajes (D.11)

@router.post("/sesiones/{sid}/mensajes")
async def enviar_mensaje(sid: str, entrada: MensajeEntrada, db: AsyncSession = Depends(get_db),
                         usuario: User = Depends(ROL)):
    """Un turno del chat. El mensaje del analista se guarda ANTES de llamar a la
    IA: si la IA falla, el mensaje queda y la ficha no cambia."""
    s = await _sesion(db, usuario, sid)
    _abierta(s)
    texto = entrada.texto.strip()
    if not texto:
        raise HTTPException(422, "El mensaje está vacío")
    mensajes = list(s.mensajes or [])
    if sum(1 for m in mensajes if m["rol"] == "analista") >= MAX_MENSAJES_ANALISTA:
        raise HTTPException(429, f"Esta sesión ya tiene {MAX_MENSAJES_ANALISTA} mensajes: completa la ficha a "
                                 f"mano o genera el informe")
    _comprobar_ritmo(usuario)

    mensajes.append(CH.mensaje("analista", texto, mensajes))
    s.mensajes = mensajes
    s.updated_at = datetime.utcnow()
    await db.commit()

    ficha, mensajes, bien = await CH.turno(copy.deepcopy(s.ficha), mensajes, texto, s.ficha.get("_bloque", ""),
                                           await llamador(db), _cargador(s))
    s = await _sesion(db, usuario, sid)
    s.ficha, s.mensajes, s.updated_at = ficha, mensajes, datetime.utcnow()
    await db.commit()
    await db.refresh(s)
    logger.info(f"Analista: turno en la sesion {s.id} ({'ok' if bien else 'sin cambios: la IA fallo'})")
    salida = await _lectura(db, s)
    salida["turno"] = {"ok": bien}
    return salida


# ------------------------------------------------------------------ generar (D.12)

@router.post("/sesiones/{sid}/generar")
async def generar(sid: str, db: AsyncSession = Depends(get_db), usuario: User = Depends(ROL)):
    """Con los criterios sin declarar NO genera: 409 `faltan_criterios` y un
    mensaje en el chat que los pide. Con criterios, o con «no se acordó
    ninguno», genera por el MISMO camino que /upload (`procesar_subida`)."""
    s = await _sesion(db, usuario, sid)
    _abierta(s)
    if s.ficha["criterios"]["estado"] == "sin_declarar":
        mensajes = list(s.mensajes or [])
        mensajes.append(CH.mensaje("ia", CH.PIDE_CRITERIOS, mensajes, origen="fijo"))
        s.mensajes, s.updated_at = mensajes, datetime.utcnow()
        await db.commit()
        await db.refresh(s)
        return JSONResponse(status_code=409, content={
            "resultado": "faltan_criterios", "mensaje": CH.PIDE_CRITERIOS, "sesion": await _lectura(db, s)})

    # Una generación a la vez: el paso a «generando» es atómico.
    paso = await db.execute(update(AnalysisSession)
                            .where(AnalysisSession.id == s.id, AnalysisSession.estado == "abierta")
                            .values(estado="generando", updated_at=datetime.utcnow()))
    await db.commit()
    if paso.rowcount != 1:
        raise HTTPException(409, "La sesión ya se está generando")

    s = await _sesion(db, usuario, sid)
    resumenes = [a.resumen for a in await _adjuntos(db, s.id)]
    criterios = PA.criterios_para_generar(s.ficha, resumenes, str(s.id))
    dueno = await db.get(User, s.user_id)
    try:
        respuesta = await procesar_subida(
            [j["ruta"] for j in s.jtl], [j["nombre"] for j in s.jtl], name=s.project,
            description=f"Cliente: {s.client_name}" if s.client_name else "", test_type=s.test_type,
            client=s.client_name or "", project=s.project, client_id=str(s.client_id) if s.client_id else "",
            acceptance_criteria_dict=criterios, metric_unit=s.metric_unit, db=db, current_user=dueno)
    except Exception as e:
        await db.rollback()
        await db.execute(update(AnalysisSession).where(AnalysisSession.id == s.id)
                         .values(estado="abierta", updated_at=datetime.utcnow()))
        await db.commit()
        logger.exception(f"Analista: no se pudo generar la sesion {s.id}")
        detalle = e.detail if isinstance(e, HTTPException) else str(e)
        raise HTTPException(500, f"No se pudo generar el informe: {detalle}")

    eid = uuid.UUID(respuesta["id"])
    s = await _sesion(db, usuario, sid)
    s.execution_id, s.estado, s.updated_at = eid, "generada", datetime.utcnow()
    n = await asociar_adjuntos(db, s.id, eid)
    await db.commit()
    await db.refresh(s)
    logger.info(f"Analista: sesion {s.id} generada -> ejecucion {eid} ({n} adjunto(s) asociados)")
    return {"resultado": "generado", "execution_id": str(eid), "ai_status": respuesta.get("ai_status"),
            "auto_transaction_reports": respuesta.get("auto_transaction_reports", []),
            "sesion": await _lectura(db, s)}
