"""Registro de horas del MÓDULO DE HORAS (ETAPA H2.2).

Especificación de horas v1.0 §1.1, §4 y §8.

Las reglas, y dónde se comprueba cada una:

| Regla | Dónde |
|---|---|
| Registrar por otro: **solo admin** (H-D13) | `_usuario_del_registro` |
| Editar los propios; el admin, todos (H-D19) | `_puede_editar` |
| **Borrar: solo admin** (§8) | `require_role(["admin"])` en el endpoint |
| Proyecto cerrado: ni alta ni edición (H-D20) | `_proyecto_abierto` |
| Sin fecha futura (H-D21) | el schema, con mensaje |
| Pasos de 0,25 (H-D8) | el schema, y la base como última red |
| Exceso: avisa pero **deja guardar** (H-D16) | `_excedidas`, que solo marca |

La jornada y los días incompletos NO se calculan aquí: eso vive en
`services/horas/calendario.py`, una sola vez para los dos endpoints que lo usan.
"""
import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, require_role
from app.db.models.client import Client
from app.db.models.time_tracking import (
    Activity, Holiday, Project, ProjectActivity, TimeEntry, WorkCalendar,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import (
    ActivityAvailabilityResponse, DiaResponse, MonthDayResponse, MonthResponse,
    PendingDayResponse, TimeEntryCreate, TimeEntryResponse, TimeEntryUpdate,
    WeekResponse,
)
from app.services.horas.calendario import (
    construir_dias, dias_pendientes, semana_de,
)

router = APIRouter()
logger = logging.getLogger(__name__)
CERO = Decimal("0")


# ===================== AYUDAS =====================

async def _calendario(db: AsyncSession) -> Dict[int, Decimal]:
    filas = (await db.execute(select(WorkCalendar))).scalars().all()
    return {f.weekday: Decimal(str(f.expected_hours)) for f in filas}


async def _no_laborables(db: AsyncSession, user_id, desde: date, hasta: date) -> Dict[date, tuple]:
    """Festivos nacionales y ausencias de ESA persona, juntos.

    H1 los puso en la misma tabla justamente porque aquí se usan igual: los dos
    hacen que el día no se reclame (§4.2.7).
    """
    filas = (await db.execute(
        select(Holiday).where(
            Holiday.date >= desde, Holiday.date <= hasta,
            ((Holiday.user_id.is_(None)) | (Holiday.user_id == user_id)),
        )
    )).scalars().all()
    salida: Dict[date, tuple] = {}
    for h in filas:
        # Una ausencia propia pesa más que un festivo: si coinciden, se nombra la ausencia.
        if h.date not in salida or h.user_id is not None:
            salida[h.date] = (h.name, h.user_id is not None)
    return salida


async def _usuario_del_registro(db: AsyncSession, pedido, actual: User) -> User:
    """H-D13: registrar por otra persona es exclusivo del admin."""
    if pedido is None or str(pedido) == str(actual.id):
        return actual
    if actual.role != "admin":
        raise HTTPException(403, "Solo el administrador puede registrar horas por otra persona")
    destino = await db.get(User, pedido)
    if not destino:
        raise HTTPException(404, "Usuario no encontrado")
    return destino


def _puede_editar(registro: TimeEntry, actual: User) -> bool:
    """H-D19: los propios; el admin, todos."""
    return actual.role == "admin" or str(registro.user_id) == str(actual.id)


async def _proyecto_abierto(db: AsyncSession, project_id) -> Project:
    """H-D20: un proyecto cerrado no admite registros nuevos ni edición."""
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    if proyecto.status == "cerrado":
        raise HTTPException(
            409, f"El proyecto «{proyecto.name}» está cerrado y no admite registros.")
    return proyecto


async def _actividad_del_proyecto(db: AsyncSession, project_id, activity_id) -> Activity:
    """La actividad tiene que estar EN ese proyecto: §4.1 encadena los selectores."""
    fila = (await db.execute(
        select(ProjectActivity).where(ProjectActivity.project_id == project_id,
                                      ProjectActivity.activity_id == activity_id)
    )).scalar_one_or_none()
    actividad = await db.get(Activity, activity_id)
    if not fila or not actividad:
        raise HTTPException(400, "Esa actividad no está asignada a este proyecto")
    return actividad


async def _excedidas(db: AsyncSession, pares: Set[tuple]) -> Set[tuple]:
    """Qué pares (proyecto, actividad) pasaron de lo estimado (H-D16).

    Solo MARCA. Nunca impide guardar: §4.2.4 dice que se avisa y se permite.
    Dos consultas agregadas para todo el lote, no una por registro.
    """
    if not pares:
        return set()
    proyectos = {p for p, _ in pares}
    estimado = {
        (r[0], r[1]): Decimal(str(r[2]))
        for r in (await db.execute(
            select(ProjectActivity.project_id, ProjectActivity.activity_id,
                   ProjectActivity.estimated_hours)
            .where(ProjectActivity.project_id.in_(proyectos))
        )).all()
    }
    consumido = {
        (r[0], r[1]): Decimal(str(r[2]))
        for r in (await db.execute(
            select(TimeEntry.project_id, TimeEntry.activity_id,
                   func.coalesce(func.sum(TimeEntry.hours), 0))
            .where(TimeEntry.project_id.in_(proyectos))
            .group_by(TimeEntry.project_id, TimeEntry.activity_id)
        )).all()
    }
    return {k for k in pares
            if consumido.get(k, CERO) > estimado.get(k, CERO)}


async def _responder(db: AsyncSession, registros: List[TimeEntry]) -> List[TimeEntryResponse]:
    """Resuelve proyecto, cliente, actividad y usuario de un lote de registros."""
    if not registros:
        return []
    proyectos = {
        p.id: p for p in (await db.execute(
            select(Project).where(Project.id.in_({r.project_id for r in registros}))
        )).scalars().all()
    }
    clientes = {
        c.id: c for c in (await db.execute(
            select(Client).where(Client.id.in_({p.client_id for p in proyectos.values()}))
        )).scalars().all()
    }
    actividades = {
        a.id: a for a in (await db.execute(
            select(Activity).where(Activity.id.in_({r.activity_id for r in registros}))
        )).scalars().all()
    }
    ids_usuario = {r.user_id for r in registros} | {r.created_by for r in registros if r.created_by}
    usuarios = {
        u.id: u for u in (await db.execute(
            select(User).where(User.id.in_(ids_usuario))
        )).scalars().all()
    }
    exceso = await _excedidas(db, {(r.project_id, r.activity_id) for r in registros})

    def nombre(u):
        return (u.full_name or u.username) if u else ""

    salida = []
    for r in registros:
        p = proyectos.get(r.project_id)
        c = clientes.get(p.client_id) if p else None
        salida.append(TimeEntryResponse(
            id=r.id, user_id=r.user_id, user_name=nombre(usuarios.get(r.user_id)),
            created_by=r.created_by, created_by_name=nombre(usuarios.get(r.created_by)),
            date=r.date,
            client_id=c.id if c else None, client_name=c.name if c else "",
            project_id=r.project_id, project_name=p.name if p else "",
            project_status=p.status if p else "activo",
            activity_id=r.activity_id,
            activity_name=actividades[r.activity_id].name if r.activity_id in actividades else "",
            hours=Decimal(str(r.hours)), billable=r.billable, overtime=r.overtime,
            notes=r.notes, source=r.source,
            over_estimate=(r.project_id, r.activity_id) in exceso,
        ))
    return salida


async def _registros(db: AsyncSession, user_id, desde: date, hasta: date) -> List[TimeEntry]:
    return list((await db.execute(
        select(TimeEntry)
        .where(TimeEntry.user_id == user_id,
               TimeEntry.date >= desde, TimeEntry.date <= hasta)
        .order_by(TimeEntry.date, TimeEntry.created_at)
    )).scalars().all())


# ===================== ENDPOINTS =====================

@router.get("/entries", response_model=List[TimeEntryResponse])
async def listar_registros(
    user_id: Optional[uuid.UUID] = Query(None),
    desde: date = Query(...),
    hasta: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Los registros del rango. §8: todos ven los registros de todos."""
    if hasta < desde:
        raise HTTPException(400, "El rango está al revés: «hasta» es anterior a «desde»")
    return await _responder(db, await _registros(db, user_id or current_user.id, desde, hasta))


@router.get("/week", response_model=WeekResponse)
async def ver_semana(
    fecha: Optional[date] = Query(None, description="Cualquier día de la semana"),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """La semana que contiene esa fecha, ya resuelta (H-D14).

    Devuelve por día lo esperado, lo ordinario, lo extra, si es festivo o
    ausencia y si está incompleto: **la pantalla no calcula nada**.
    """
    objetivo = user_id or current_user.id
    usuario = await db.get(User, objetivo) if user_id else current_user
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")

    lunes, domingo = semana_de(fecha or date.today())
    registros = await _registros(db, objetivo, lunes, domingo)
    respuestas = await _responder(db, registros)
    por_id = {r.id: r for r in respuestas}

    horas_por_dia: Dict[date, Dict[str, Decimal]] = {}
    por_dia: Dict[date, List[TimeEntryResponse]] = {}
    for r in registros:
        acc = horas_por_dia.setdefault(r.date, {"ordinarias": CERO, "extra": CERO})
        acc["extra" if r.overtime else "ordinarias"] += Decimal(str(r.hours))
        por_dia.setdefault(r.date, []).append(por_id[r.id])

    dias = construir_dias(lunes, domingo, await _calendario(db), horas_por_dia,
                          await _no_laborables(db, objetivo, lunes, domingo),
                          hoy=date.today())

    return WeekResponse(
        user_id=objetivo, user_name=(usuario.full_name or usuario.username),
        week_start=lunes, week_end=domingo,
        days=[
            DiaResponse(
                date=d.fecha, expected_hours=d.se_reclaman,
                ordinary_hours=d.ordinarias, overtime_hours=d.extra, total_hours=d.total,
                is_holiday=d.es_festivo, is_absence=d.es_ausencia,
                non_working_reason=d.motivo_no_laborable,
                incomplete=d.incompleto, missing_hours=d.faltan,
                entries=por_dia.get(d.fecha, []),
            ) for d in dias
        ],
        total_expected=sum((d.se_reclaman for d in dias), CERO),
        total_ordinary=sum((d.ordinarias for d in dias), CERO),
        total_overtime=sum((d.extra for d in dias), CERO),
    )


@router.get("/month", response_model=MonthResponse)
async def ver_mes(
    anio: Optional[int] = Query(None, ge=2000, le=2100),
    mes: Optional[int] = Query(None, ge=1, le=12),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """El mes entero, casilla a casilla (ETAPA H2b, §4.1).

    Reutiliza `services/horas/calendario.py`, el mismo módulo que resuelve la
    semana y los días pendientes: **la pantalla no calcula nada** y las tres
    vistas no pueden discrepar.
    """
    objetivo = user_id or current_user.id
    usuario = await db.get(User, objetivo) if user_id else current_user
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")

    hoy = date.today()
    a, m = anio or hoy.year, mes or hoy.month
    primero = date(a, m, 1)
    # El último día del mes sin `calendar`: el día 1 del siguiente, menos uno.
    ultimo = (date(a + 1, 1, 1) if m == 12 else date(a, m + 1, 1)) - timedelta(days=1)

    registros = await _registros(db, objetivo, primero, ultimo)
    horas_por_dia: Dict[date, Dict[str, Decimal]] = {}
    cuenta: Dict[date, int] = {}
    for r in registros:
        acc = horas_por_dia.setdefault(r.date, {"ordinarias": CERO, "extra": CERO})
        acc["extra" if r.overtime else "ordinarias"] += Decimal(str(r.hours))
        cuenta[r.date] = cuenta.get(r.date, 0) + 1

    # Qué días tienen algún registro en una actividad desfasada (H-D27).
    exceso = await _excedidas(db, {(r.project_id, r.activity_id) for r in registros})
    con_desfase = {r.date for r in registros if (r.project_id, r.activity_id) in exceso}

    dias = construir_dias(primero, ultimo, await _calendario(db), horas_por_dia,
                          await _no_laborables(db, objetivo, primero, ultimo),
                          hoy=hoy)

    return MonthResponse(
        user_id=objetivo, user_name=(usuario.full_name or usuario.username),
        year=a, month=m, first_day=primero, last_day=ultimo,
        days=[
            MonthDayResponse(
                date=d.fecha, expected_hours=d.se_reclaman,
                ordinary_hours=d.ordinarias, overtime_hours=d.extra, total_hours=d.total,
                is_holiday=d.es_festivo, is_absence=d.es_ausencia,
                non_working_reason=d.motivo_no_laborable,
                incomplete=d.incompleto, missing_hours=d.faltan,
                entries_count=cuenta.get(d.fecha, 0),
                has_over_estimate=d.fecha in con_desfase,
            ) for d in dias
        ],
        total_expected=sum((d.se_reclaman for d in dias), CERO),
        total_ordinary=sum((d.ordinarias for d in dias), CERO),
        total_overtime=sum((d.extra for d in dias), CERO),
        pending_days=len(dias_pendientes(dias, min(ultimo, hoy))),
    )


@router.get("/pending-days", response_model=List[PendingDayResponse])
async def dias_por_completar(
    user_id: Optional[uuid.UUID] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Los días sin registro o por debajo de la jornada (H-D18).

    Por defecto, el mes en curso y el anterior. Nunca lista días futuros: un día
    que no ha llegado no es una deuda.
    """
    objetivo = user_id or current_user.id
    hoy = date.today()
    if hasta is None:
        hasta = hoy
    if desde is None:
        primero = hoy.replace(day=1)
        desde = (primero - timedelta(days=1)).replace(day=1)
    if hasta < desde:
        raise HTTPException(400, "El rango está al revés: «hasta» es anterior a «desde»")

    registros = await _registros(db, objetivo, desde, hasta)
    horas_por_dia: Dict[date, Dict[str, Decimal]] = {}
    for r in registros:
        acc = horas_por_dia.setdefault(r.date, {"ordinarias": CERO, "extra": CERO})
        acc["extra" if r.overtime else "ordinarias"] += Decimal(str(r.hours))

    dias = construir_dias(desde, hasta, await _calendario(db), horas_por_dia,
                          await _no_laborables(db, objetivo, desde, hasta),
                          hoy=hoy)

    return [
        PendingDayResponse(
            date=d.fecha, expected_hours=d.esperadas, ordinary_hours=d.ordinarias,
            missing_hours=d.faltan, week_start=semana_de(d.fecha)[0],
        )
        for d in dias_pendientes(dias, min(hasta, hoy))
    ]


@router.get("/projects/{project_id}/disponibilidad",
            response_model=List[ActivityAvailabilityResponse])
async def disponibilidad(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Estimado, consumido y restante por actividad de un proyecto.

    Alimenta el aviso de exceso (H-D16) sin pedir el detalle entero del proyecto,
    que además trae el historial.
    """
    if not await db.get(Project, project_id):
        raise HTTPException(404, "Proyecto no encontrado")

    filas = (await db.execute(
        select(ProjectActivity, Activity)
        .join(Activity, Activity.id == ProjectActivity.activity_id)
        .where(ProjectActivity.project_id == project_id)
        .order_by(Activity.created_at)
    )).all()
    consumido = {
        a: Decimal(str(h)) for a, h in (await db.execute(
            select(TimeEntry.activity_id, func.coalesce(func.sum(TimeEntry.hours), 0))
            .where(TimeEntry.project_id == project_id)
            .group_by(TimeEntry.activity_id)
        )).all()
    }
    salida = []
    for pa, act in filas:
        est = Decimal(str(pa.estimated_hours))
        con = consumido.get(act.id, CERO)
        salida.append(ActivityAvailabilityResponse(
            activity_id=act.id, activity_name=act.name,
            estimated_hours=est, consumed_hours=con,
            remaining_hours=est - con, over_estimate=con > est,
        ))
    return salida


@router.post("/entries", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
async def crear_registro(
    data: TimeEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Registrar horas. El exceso avisa pero NO impide guardar (§4.2.4)."""
    destino = await _usuario_del_registro(db, data.user_id, current_user)
    await _proyecto_abierto(db, data.project_id)
    await _actividad_del_proyecto(db, data.project_id, data.activity_id)

    registro = TimeEntry(
        id=uuid.uuid4(), user_id=destino.id, created_by=current_user.id,
        date=data.date, project_id=data.project_id, activity_id=data.activity_id,
        hours=data.hours, billable=data.billable, overtime=data.overtime,
        notes=data.notes, source="manual",
    )
    db.add(registro)
    await db.commit()
    await db.refresh(registro)
    logger.info(f"Horas: {data.hours} h de {destino.username} el {data.date} "
                f"registradas por {current_user.username}")
    return (await _responder(db, [registro]))[0]


@router.put("/entries/{entry_id}", response_model=TimeEntryResponse)
async def editar_registro(
    entry_id: uuid.UUID,
    data: TimeEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Editar. Los propios; el admin, todos (H-D19)."""
    registro = await db.get(TimeEntry, entry_id)
    if not registro:
        raise HTTPException(404, "Registro no encontrado")
    if not _puede_editar(registro, current_user):
        raise HTTPException(403, "Solo puedes editar tus propios registros")

    # H-D20 en los dos proyectos: el de origen y el de destino si se mueve.
    await _proyecto_abierto(db, registro.project_id)
    proyecto_id = data.project_id or registro.project_id
    actividad_id = data.activity_id or registro.activity_id
    if data.project_id and str(data.project_id) != str(registro.project_id):
        await _proyecto_abierto(db, data.project_id)
    await _actividad_del_proyecto(db, proyecto_id, actividad_id)

    for campo in ("date", "project_id", "activity_id", "hours",
                  "billable", "overtime", "notes"):
        valor = getattr(data, campo)
        if valor is not None:
            setattr(registro, campo, valor)

    await db.commit()
    await db.refresh(registro)
    return (await _responder(db, [registro]))[0]


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_registro(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Borrar. **Solo admin** (§8), como en el resto de la plataforma."""
    registro = await db.get(TimeEntry, entry_id)
    if not registro:
        raise HTTPException(404, "Registro no encontrado")
    await db.delete(registro)
    await db.commit()
    logger.info(f"Horas: registro {entry_id} borrado por {current_user.username}")
