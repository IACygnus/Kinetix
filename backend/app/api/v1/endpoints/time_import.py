"""Importación del archivo de horas (ETAPA H3.4, especificación §6).

Dos endpoints y **un solo análisis**:

    POST /time/import/preview   analiza y NO escribe nada
    POST /time/import/confirm   analiza otra vez y aplica, en una transacción

Los dos llaman a `_analizar()`. Es el punto entero de la vista previa: si la
previa se calculara con un código y la escritura con otro, acabarían diciendo
cosas distintas y la previa dejaría de servir para decidir —que es para lo único
que existe (§6.2.5)—.

Las reglas del archivo (títulos, fechas, horas, sí/no, observaciones) viven en
`services/horas/importacion.py`; aquí está lo que necesita la base de datos:
qué existe ya, qué hay que crear y qué se actualiza.
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.models.client import Client
from app.db.models.time_tracking import (
    Activity, Project, ProjectActivity, TimeEntry, normalizar,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import (
    ActividadNueva, FilaImportacion, ProyectoAImportar, ProyectoCreado,
    ProyectoNoEnEjecucion, ResumenImportacion, VistaPreviaImportacion, validar_paso,
)
# §4 (carga real): la definición única de qué texto del Excel es cuál de las
# ocho actividades. La comparten los DOS importadores; aquí no se copia nada.
from app.services.horas.sinonimos_actividad import traducir as traducir_actividad
# ETAPA H8 (§6.2.8): la excepción de la importación vive aquí, no en `estados`.
from app.services.horas import estados
from app.services.horas.desfase import (
    DESFASADO, estado as estado_desfase, etiqueta as etiqueta_desfase, horas_de_desfase,
)
from app.services.horas.importacion import (
    ArchivoIlegible, FaltanColumnas, MAX_BYTES,
    filas_del_libro, hojas_del_libro, leer_fecha, leer_horas, leer_id, leer_si_no,
    limpiar_texto, mapear_columnas,
)

router = APIRouter()
logger = logging.getLogger(__name__)
CERO = Decimal("0")

NUEVA, ACTUALIZA, INVALIDA = "nueva", "actualiza", "invalida"


# ===================== EL PLAN =====================

@dataclass
class _Plan:
    """Todo lo que se sabe del archivo antes de tocar la base."""
    hoja: str = ""
    hojas: List[str] = field(default_factory=list)
    filas: List[FilaImportacion] = field(default_factory=list)
    # Nombre normalizado -> nombre tal como viene en el archivo.
    clientes_nuevos: Dict[str, str] = field(default_factory=dict)
    actividades_nuevas: Dict[str, str] = field(default_factory=dict)
    proyectos_nuevos: Dict[Tuple[str, str], Tuple[str, str]] = field(default_factory=dict)
    # Lo ya resuelto contra la base, por nombre normalizado.
    id_cliente: Dict[str, uuid.UUID] = field(default_factory=dict)
    id_actividad: Dict[str, uuid.UUID] = field(default_factory=dict)
    id_proyecto: Dict[Tuple[str, str], uuid.UUID] = field(default_factory=dict)
    # external_id -> el registro que se va a actualizar.
    existentes: Dict[str, TimeEntry] = field(default_factory=dict)


async def _analizar(db: AsyncSession, datos: bytes, destino: User) -> _Plan:
    """Lee el archivo y decide qué pasaría con cada fila. **No escribe nada.**"""
    hoja, titulos, filas = filas_del_libro(datos)
    plan = _Plan(hoja=hoja, hojas=hojas_del_libro(datos))
    mapa = mapear_columnas(titulos)          # H-D42: revienta antes de leer filas

    def celda(valores, clave):
        i = mapa.get(clave)
        return valores[i] if i is not None and i < len(valores) else None

    # ---------- 1. Lo que ya existe, de una sola consulta por tabla ----------
    clientes = {normalizar(c.name): c for c in (await db.execute(select(Client))).scalars().all()}
    actividades = {normalizar(a.name): a for a in (await db.execute(select(Activity))).scalars().all()}
    proyectos = {
        (str(p.client_id), p.name_normalized): p
        for p in (await db.execute(select(Project))).scalars().all()
    }
    plan.id_cliente = {k: c.id for k, c in clientes.items()}
    plan.id_actividad = {k: a.id for k, a in actividades.items()}

    ids_archivo = {
        leer_id(celda(v, "external_id")) for _, v in filas
        if leer_id(celda(v, "external_id"))
    }
    if ids_archivo:
        plan.existentes = {
            r.external_id: r for r in (await db.execute(
                select(TimeEntry).where(TimeEntry.external_id.in_(ids_archivo))
            )).scalars().all()
        }

    # Lo consumido hoy por (proyecto, actividad) y lo estimado, para H-D38.
    consumido: Dict[Tuple[str, str], Decimal] = {
        (str(p), str(a)): Decimal(str(h)) for p, a, h in (await db.execute(
            select(TimeEntry.project_id, TimeEntry.activity_id,
                   func.coalesce(func.sum(TimeEntry.hours), 0))
            .group_by(TimeEntry.project_id, TimeEntry.activity_id)
        )).all()
    }
    estimado: Dict[Tuple[str, str], Decimal] = {
        (str(p), str(a)): Decimal(str(h)) for p, a, h in (await db.execute(
            select(ProjectActivity.project_id, ProjectActivity.activity_id,
                   ProjectActivity.estimated_hours)
        )).all()
    }

    # ---------- 2. Fila a fila ----------
    hoy = date.today()
    vistos: Dict[str, int] = {}          # external_id -> nº de fila que ya lo usó
    for numero, valores in filas:
        f = FilaImportacion(
            numero=numero,
            external_id=leer_id(celda(valores, "external_id")),
            client_name=limpiar_texto(celda(valores, "cliente")),
            project_name=limpiar_texto(celda(valores, "proyecto")),
            notes=limpiar_texto(celda(valores, "notas")),
            billable=leer_si_no(celda(valores, "facturable")),
            overtime=leer_si_no(celda(valores, "extra")),
        )
        # §4: la actividad pasa por la tabla de sinónimos ANTES de compararse
        # con el catálogo. Sin esto, «Diseño y generación de script» y «Diseño y
        # configuración» crearían dos actividades distintas que ya no se pueden
        # sumar. Se guarda lo que decía el archivo cuando la tabla lo cambió.
        del_archivo = limpiar_texto(celda(valores, "actividad"))
        f.activity_name = traducir_actividad(del_archivo)
        if f.activity_name != del_archivo:
            f.activity_original = del_archivo

        f.date = leer_fecha(celda(valores, "fecha"))
        f.hours = leer_horas(celda(valores, "horas"))

        motivo = _motivo_invalida(f, hoy, vistos)
        if motivo:
            f.accion, f.motivo = INVALIDA, motivo
            plan.filas.append(f)
            continue
        if f.external_id:
            vistos[f.external_id] = numero

        # ---------- 3. Qué hay que crear (H-D36, H-D48) ----------
        kc, ka = normalizar(f.client_name), normalizar(f.activity_name)
        cliente = clientes.get(kc)
        if not cliente:
            plan.clientes_nuevos.setdefault(kc, f.client_name)
            f.crea_cliente = True
        if not actividades.get(ka):
            plan.actividades_nuevas.setdefault(ka, f.activity_name)
            f.crea_actividad = True

        kp = normalizar(f.project_name)
        clave_proyecto = (str(cliente.id) if cliente else f"nuevo:{kc}", kp)
        proyecto = proyectos.get(clave_proyecto) if cliente else None
        if not proyecto:
            plan.proyectos_nuevos.setdefault(clave_proyecto, (f.client_name, f.project_name))
            f.crea_proyecto = True
        else:
            plan.id_proyecto[clave_proyecto] = proyecto.id
            # ETAPA H8 (§6.2.8): **la excepción**. La importación entra en
            # cualquier estado menos `no_viable`. Un Excel trae horas de hace
            # semanas y el proyecto pudo cambiar de estado desde entonces;
            # rechazarlas obligaría a reabrir el proyecto, importar y volver a
            # cerrarlo. La previa avisa de las que caen fuera de ejecución.
            f.project_status = estados.normalizar_legado(proyecto.status)
            f.project_status_label = estados.texto(proyecto.status)
            if not estados.admite_importacion(proyecto.status):
                f.accion = INVALIDA
                f.motivo = (f"El proyecto «{f.project_name}» está "
                            f"«{f.project_status_label}»")
                plan.filas.append(f)
                continue

        f.accion = ACTUALIZA if f.external_id in plan.existentes else NUEVA
        if f.accion == ACTUALIZA:
            previo = plan.existentes[f.external_id]
            f.cambia_de_persona = str(previo.user_id) != str(destino.id)

        # ---------- 4. Cómo queda el desfase si entra (H-D38) ----------
        if proyecto and not f.crea_actividad:
            clave = (str(proyecto.id), str(actividades[ka].id))
            est = estimado.get(clave, CERO)
            acumulado = consumido.get(clave, CERO) + (f.hours or CERO)
            if f.accion == ACTUALIZA:
                # Lo que esa fila ya aportaba no se cuenta dos veces.
                acumulado -= Decimal(str(plan.existentes[f.external_id].hours))
            consumido[clave] = acumulado
            f.overrun_status = estado_desfase(acumulado, est)
            f.overrun_hours = horas_de_desfase(acumulado, est)
            f.overrun_label = etiqueta_desfase(acumulado, est)

        plan.filas.append(f)

    return plan


def _motivo_invalida(f: FilaImportacion, hoy: date, vistos: Dict[str, int]) -> str:
    """Por qué NO se importa esta fila (H-D40). Cadena vacía = sí se importa."""
    if not f.client_name or not f.project_name or not f.activity_name:
        faltan = [n for n, v in (("Cliente", f.client_name), ("Proyecto", f.project_name),
                                 ("Tarea", f.activity_name)) if not v]
        return "Falta " + " y ".join(f"«{n}»" for n in faltan)
    if f.date is None:
        return "La fecha no se entiende (se espera dd/mm/aaaa)"
    if f.date > hoy:
        # Mismo criterio que H-D21 en el registro a mano: no se adelantan horas
        # que todavía no se han trabajado.
        return "La fecha es futura"
    if f.hours is None:
        return "Las horas no se entienden"
    try:
        validar_paso(f.hours)
    except ValueError as e:
        return str(e)
    if f.external_id and f.external_id in vistos:
        # Si entraran las dos, el índice único de `external_id` tumbaría la
        # transacción entera y no entraría nada (H-D41).
        return f"El Id «{f.external_id}» ya venía en la fila {vistos[f.external_id]}"
    return ""


# ===================== LOS ENDPOINTS =====================

async def _destinatario(db: AsyncSession, pedido: Optional[str], actual: User) -> User:
    """H-D39: importar por otra persona es exclusivo del admin."""
    if not pedido or str(pedido) == str(actual.id):
        return actual
    if actual.role != "admin":
        raise HTTPException(403, "Solo el administrador puede importar horas por otra persona")
    destino = await db.get(User, uuid.UUID(str(pedido)))
    if not destino:
        raise HTTPException(404, "Usuario no encontrado")
    return destino


async def _leer(archivo: UploadFile) -> bytes:
    datos = await archivo.read()
    if not datos:
        raise HTTPException(400, "El archivo llegó vacío")
    if len(datos) > MAX_BYTES:
        raise HTTPException(413, f"El archivo pesa más de {MAX_BYTES // (1024 * 1024)} MB")
    return datos


def _fuera_de_ejecucion(entran: List[FilaImportacion]) -> List[ProyectoNoEnEjecucion]:
    """ETAPA H8 (§6.2.8): el aviso de la vista previa.

    Dice **cuántas filas y en qué proyectos**, no solo que las hay: con el
    total a secas no se puede decidir si confirmar. Se cuenta sobre las filas
    que van a entrar de verdad —una fila inválida por otro motivo no cuenta— y
    los proyectos que la importación va a **crear** tampoco aparecen aquí,
    porque nacen en ejecución.
    """
    por_proyecto: Dict[tuple, ProyectoNoEnEjecucion] = {}
    for f in entran:
        if f.project_status == estados.EN_EJECUCION:
            continue
        clave = (f.client_name, f.project_name)
        bloque = por_proyecto.get(clave)
        if bloque is None:
            bloque = por_proyecto[clave] = ProyectoNoEnEjecucion(
                project_name=f.project_name, client_name=f.client_name,
                status=f.project_status, status_label=f.project_status_label)
        bloque.filas += 1
        bloque.horas += (f.hours or CERO)
    return sorted(por_proyecto.values(), key=lambda b: (b.client_name, b.project_name))


def _actividades_nuevas(plan: _Plan, entran: List[FilaImportacion]) -> List[ActividadNueva]:
    """§4: las actividades que el catálogo no tenía, con sus filas y sus horas.

    **No es un error y no bloquea nada**: entran igual. Es el aviso que permite
    decidir antes de confirmar si lo que falta es un sinónimo en
    `services/horas/sinonimos_actividad.py` o si de verdad es una actividad
    nueva. Una desconocida con 40 horas en 12 filas casi nunca es nueva: es una
    variante de escritura de una de las ocho.

    Se listan **todas** las que se van a crear, también si ninguna fila válida
    las usa al final (filas 0, horas 0): que se cree una actividad que nadie usa
    también hay que verlo.
    """
    bloques = {
        clave: ActividadNueva(name=nombre)
        for clave, nombre in plan.actividades_nuevas.items()
    }
    for f in entran:
        if not f.crea_actividad:
            continue
        bloque = bloques.get(normalizar(f.activity_name))
        if bloque is None:
            continue
        bloque.filas.append(f.numero)
        bloque.horas += (f.hours or CERO)
    return sorted(bloques.values(), key=lambda b: b.name.lower())


def _a_vista_previa(plan: _Plan, destino: User) -> VistaPreviaImportacion:
    entran = [f for f in plan.filas if f.accion != INVALIDA]
    fuera = _fuera_de_ejecucion(entran)
    return VistaPreviaImportacion(
        sheet=plan.hoja, sheets=plan.hojas,
        user_id=destino.id, user_name=(destino.full_name or destino.username),
        total_filas=len(plan.filas),
        nuevas=[f for f in plan.filas if f.accion == NUEVA],
        actualizadas=[f for f in plan.filas if f.accion == ACTUALIZA],
        invalidas=[f for f in plan.filas if f.accion == INVALIDA],
        desfasadas=[f for f in entran if f.overrun_status == DESFASADO],
        clientes_a_crear=sorted(plan.clientes_nuevos.values()),
        actividades_a_crear=sorted(plan.actividades_nuevas.values()),
        actividades_nuevas=_actividades_nuevas(plan, entran),
        proyectos_a_crear=[ProyectoAImportar(client_name=c, project_name=p)
                           for c, p in sorted(plan.proyectos_nuevos.values())],
        total_horas=sum((f.hours or CERO for f in entran), CERO),
        proyectos_no_en_ejecucion=fuera,
        filas_no_en_ejecucion=sum(b.filas for b in fuera),
    )


@router.post("/preview", response_model=VistaPreviaImportacion)
async def vista_previa(
    archivo: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Qué pasaría si se confirmara. **No escribe nada** (§6.2.5)."""
    destino = await _destinatario(db, user_id, current_user)
    datos = await _leer(archivo)
    try:
        plan = await _analizar(db, datos, destino)
    except FaltanColumnas as e:
        raise HTTPException(400, str(e))
    except ArchivoIlegible as e:
        raise HTTPException(400, str(e))
    return _a_vista_previa(plan, destino)


@router.post("/confirm", response_model=ResumenImportacion)
async def confirmar(
    archivo: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Aplica la importación **en una transacción** (H-D41).

    O entra todo lo válido o no entra nada: media importación es un mes a medio
    cargar que nadie sabría auditar.
    """
    destino = await _destinatario(db, user_id, current_user)
    datos = await _leer(archivo)
    try:
        plan = await _analizar(db, datos, destino)
    except FaltanColumnas as e:
        raise HTTPException(400, str(e))
    except ArchivoIlegible as e:
        raise HTTPException(400, str(e))

    ahora = datetime.utcnow()
    creados = actualizados = 0
    clientes_creados: List[str] = []
    actividades_creadas: List[str] = []
    proyectos_creados: List[ProyectoCreado] = []

    try:
        # ---------- 1. Clientes, actividades y proyectos que faltan (H-D36) ----------
        for clave, nombre in plan.clientes_nuevos.items():
            c = Client(name=nombre, is_active=True)
            db.add(c)
            await db.flush()
            plan.id_cliente[clave] = c.id
            clientes_creados.append(nombre)

        for clave, nombre in plan.actividades_nuevas.items():
            a = Activity(name=nombre, name_normalized=clave, is_active=True,
                         created_by=current_user.id)
            db.add(a)
            await db.flush()
            plan.id_actividad[clave] = a.id
            actividades_creadas.append(nombre)

        for clave, (nombre_cliente, nombre_proyecto) in plan.proyectos_nuevos.items():
            client_id = plan.id_cliente[normalizar(nombre_cliente)]
            # H-D37: **sin horas estimadas**. No se le inventa ninguna: se crea
            # el proyecto y el resumen ofrece el enlace para ponérselas.
            p = Project(client_id=client_id, name=nombre_proyecto,
                        name_normalized=normalizar(nombre_proyecto),
                        status=estados.POR_DEFECTO, created_by=current_user.id)
            db.add(p)
            await db.flush()
            plan.id_proyecto[clave] = p.id
            proyectos_creados.append(ProyectoCreado(
                id=p.id, name=nombre_proyecto, client_name=nombre_cliente))

        # ---------- 2. Los registros ----------
        for f in plan.filas:
            if f.accion == INVALIDA:
                continue
            kc, ka, kp = (normalizar(f.client_name), normalizar(f.activity_name),
                          normalizar(f.project_name))
            client_id = plan.id_cliente[kc]
            project_id = (plan.id_proyecto.get((str(client_id), kp))
                          or plan.id_proyecto[(f"nuevo:{kc}", kp)])
            activity_id = plan.id_actividad[ka]

            if f.accion == ACTUALIZA:
                r = plan.existentes[f.external_id]
                # El dueño se actualiza a propósito: si la primera importación se
                # hizo con la persona equivocada, reimportar con la correcta es la
                # única forma de arreglarlo desde la pantalla.
                r.user_id = destino.id
                r.date, r.project_id, r.activity_id = f.date, project_id, activity_id
                r.hours, r.billable, r.overtime = f.hours, f.billable, f.overtime
                r.notes = f.notes or None
                r.source, r.updated_at = "import", ahora
                actualizados += 1
            else:
                db.add(TimeEntry(
                    external_id=f.external_id or None,
                    user_id=destino.id, created_by=current_user.id,
                    date=f.date, project_id=project_id, activity_id=activity_id,
                    hours=f.hours, billable=f.billable, overtime=f.overtime,
                    notes=f.notes or None, source="import",
                ))
                creados += 1

        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Importación de horas: se deshizo la transacción entera")
        raise HTTPException(
            500, "No se pudo completar la importación. No se guardó ninguna fila.")

    return ResumenImportacion(
        creados=creados, actualizados=actualizados,
        omitidos=sum(1 for f in plan.filas if f.accion == INVALIDA),
        total_horas=sum((f.hours or CERO for f in plan.filas if f.accion != INVALIDA), CERO),
        clientes_creados=sorted(clientes_creados),
        actividades_creadas=sorted(actividades_creadas),
        # §4: el mismo bloque que enseñó la previa, repetido aquí para que siga
        # a la vista después de confirmar. Se calcula del plan, que no se tocó.
        actividades_nuevas=_actividades_nuevas(
            plan, [f for f in plan.filas if f.accion != INVALIDA]),
        proyectos_creados=proyectos_creados,
        user_id=destino.id, user_name=(destino.full_name or destino.username),
    )
