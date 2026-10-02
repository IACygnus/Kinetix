"""El «Analista IA» — BLOQUE 5 (reporte 147).

    POST   /analista/sesiones                    crear: JTL (1-5), cliente, proyecto, tipo
    GET    /analista/sesiones                    las mías (admin: todas)
    GET    /analista/sesiones/{id}               la sesión: ficha, mensajes, adjuntos
    PATCH  /analista/sesiones/{id}               lo que el analista toca a mano
    POST   /analista/sesiones/{id}/adjuntos      el CSV/XML de JMeter con el detalle de los errores

Admin y analista. **Cada analista ve solo las suyas**: la de otro responde 404,
como si no existiera. El admin ve todas.

Las cifras del JTL y los resultados de los criterios los calcula el servidor:
el PATCH no los acepta (422) y la IA no los toca.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.upload import UPLOAD_DIR, _get_assigned_client_ids, parsear_archivos
from app.core.security import require_role
from app.db.models.analista import AnalysisAttachment, AnalysisSession
from app.db.models.client import Client
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.analista import CambiosFicha
from app.services.analista import errores as ER
from app.services.analista import ficha as FI

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
        "ficha": s.ficha,
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

    s = AnalysisSession(user_id=usuario.id, client_id=cliente.id if cliente else None,
                        client_name=cliente.name if cliente else None, project=proyecto,
                        test_type=tipo, metric_unit=unidad,
                        jtl=[{"ruta": r, "nombre": n} for r, n in zip(rutas, nombres)],
                        ficha=ficha, mensajes=[], estado="abierta")
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
