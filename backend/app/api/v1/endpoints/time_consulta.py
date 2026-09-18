"""Consulta de proyectos del MÓDULO DE HORAS (ETAPA H3.2).

Especificación de horas v1.1 §5: *«Por proyecto: quién ha registrado y cuántas
horas, con el consumido frente a lo estimado… Al ampliar la consulta, la tabla
cambia y muestra los días en que se registraron esas horas.»*

Son dos endpoints y no uno a propósito: la tabla de arriba pide agregados y el
despliegue de una fila pide el detalle de **esa** persona en **ese** proyecto.
Traerlo todo junto significaría cargar cada registro del rango para enseñar, casi
siempre, una sola fila desplegada.

**Las dos cifras de horas no son la misma**, y aquí está el porqué:

    hours_in_range   lo registrado dentro del rango que se consulta
    consumed_hours   todo lo que lleva el proyecto, desde siempre

El desfase de §5.1 se mide **siempre contra el total**. Si se midiera contra el
rango, consultar una semana tranquila dejaría «en rango» un proyecto que la
pantalla de Proyectos marca como desfasado, y tendríamos dos verdades para el
mismo proyecto. Una sola definición, la de `services/horas/desfase.py`.
"""
import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.models.client import Client
from app.db.models.time_tracking import Project, ProjectActivity, TimeEntry
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import (
    ConsultaPersona, ConsultaProyecto, ConsultaResponse, TimeEntryResponse,
)
# Se reusa el resolvedor del registro (H2): es el que ya sabe rellenar cliente,
# proyecto, actividad, quién y la marca de desfase de cada fila. Escribirlo otra
# vez aquí sería la segunda definición de lo mismo.
from app.api.v1.endpoints.time_entries import _responder
from app.services.horas.desfase import (
    DESFASADO,
    estado as estado_desfase,
    etiqueta as etiqueta_desfase,
    horas_de_desfase,
    porcentaje as porcentaje_consumido,
)

router = APIRouter()
logger = logging.getLogger(__name__)
CERO = Decimal("0")


def _dec(v) -> Decimal:
    return Decimal(str(v or 0))


@router.get("", response_model=ConsultaResponse)
async def consultar(
    desde: date = Query(..., description="Primer día del rango"),
    hasta: date = Query(..., description="Último día del rango"),
    client_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    solo_desfasados: bool = Query(False, description="§5.1: ver solo los que se pasaron"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Por proyecto, quién registró y cuántas horas (H-D32).

    §8: todos ven los registros de todos, así que no se filtra por quien
    consulta; el filtro de persona es del usuario, no del permiso.
    """
    if hasta < desde:
        raise HTTPException(400, "El rango está al revés: «hasta» es anterior a «desde»")

    # ---------- 1. Lo registrado en el rango, agrupado por proyecto y persona ----------
    horas_facturables = func.coalesce(
        func.sum(case((TimeEntry.billable, TimeEntry.hours), else_=0)), 0)
    horas_extra = func.coalesce(
        func.sum(case((TimeEntry.overtime, TimeEntry.hours), else_=0)), 0)

    q = (
        select(
            TimeEntry.project_id, TimeEntry.user_id,
            func.coalesce(func.sum(TimeEntry.hours), 0),
            horas_facturables, horas_extra, func.count(TimeEntry.id),
        )
        .join(Project, Project.id == TimeEntry.project_id)
        .where(TimeEntry.date >= desde, TimeEntry.date <= hasta)
        .group_by(TimeEntry.project_id, TimeEntry.user_id)
    )
    if client_id:
        q = q.where(Project.client_id == client_id)
    if project_id:
        q = q.where(TimeEntry.project_id == project_id)
    if user_id:
        q = q.where(TimeEntry.user_id == user_id)

    filas = (await db.execute(q)).all()
    if not filas:
        return ConsultaResponse(desde=desde, hasta=hasta)

    ids_proyecto = {f[0] for f in filas}
    ids_usuario = {f[1] for f in filas}

    # ---------- 2. Los proyectos, sus clientes y su gente ----------
    proyectos = {
        p.id: p for p in (await db.execute(
            select(Project).where(Project.id.in_(ids_proyecto))
        )).scalars().all()
    }
    clientes = {
        c.id: c for c in (await db.execute(
            select(Client).where(Client.id.in_({p.client_id for p in proyectos.values()}))
        )).scalars().all()
    }
    usuarios = {
        u.id: u for u in (await db.execute(
            select(User).where(User.id.in_(ids_usuario))
        )).scalars().all()
    }

    # ---------- 3. Lo estimado y lo consumido DE SIEMPRE, para el desfase ----------
    estimado: Dict[uuid.UUID, Decimal] = {
        r[0]: _dec(r[1]) for r in (await db.execute(
            select(ProjectActivity.project_id,
                   func.coalesce(func.sum(ProjectActivity.estimated_hours), 0))
            .where(ProjectActivity.project_id.in_(ids_proyecto))
            .group_by(ProjectActivity.project_id)
        )).all()
    }
    consumido: Dict[uuid.UUID, Decimal] = {
        r[0]: _dec(r[1]) for r in (await db.execute(
            select(TimeEntry.project_id, func.coalesce(func.sum(TimeEntry.hours), 0))
            .where(TimeEntry.project_id.in_(ids_proyecto))
            .group_by(TimeEntry.project_id)
        )).all()
    }

    # ---------- 4. Armar la respuesta ----------
    por_proyecto: Dict[uuid.UUID, ConsultaProyecto] = {}
    for pid, uid, horas, facturables, extra, cuantos in filas:
        if pid not in por_proyecto:
            p = proyectos.get(pid)
            if not p:
                continue
            c = clientes.get(p.client_id)
            est, con = estimado.get(pid, CERO), consumido.get(pid, CERO)
            por_proyecto[pid] = ConsultaProyecto(
                project_id=pid, project_name=p.name,
                client_id=p.client_id, client_name=c.name if c else "",
                status=p.status,
                estimated_hours=est, consumed_hours=con, remaining_hours=est - con,
                consumed_pct=porcentaje_consumido(con, est),
                overrun_status=estado_desfase(con, est),
                overrun_hours=horas_de_desfase(con, est),
                overrun_label=etiqueta_desfase(con, est),
            )
        bloque = por_proyecto[pid]
        u = usuarios.get(uid)
        bloque.people.append(ConsultaPersona(
            user_id=uid, user_name=(u.full_name or u.username) if u else "",
            hours=_dec(horas), billable_hours=_dec(facturables),
            overtime_hours=_dec(extra), entries_count=int(cuantos),
        ))
        bloque.hours_in_range += _dec(horas)
        bloque.overtime_in_range += _dec(extra)
        bloque.entries_in_range += int(cuantos)

    salida = list(por_proyecto.values())
    for b in salida:
        # Quien más horas puso, primero: es lo que se mira al abrir la consulta.
        b.people.sort(key=lambda x: (-x.hours, x.user_name))

    # §5.1: el filtro de «solo los desfasados» se aplica DESPUÉS de calcular el
    # estado, porque el estado no depende del rango.
    desfasados = sum(1 for b in salida if b.overrun_status == DESFASADO)
    if solo_desfasados:
        salida = [b for b in salida if b.overrun_status == DESFASADO]

    # Los desfasados arriba, y dentro de cada grupo por cliente y proyecto: el
    # que hay que mirar no debería quedar al final de una lista larga.
    orden = {DESFASADO: 0, "por_agotarse": 1, "en_rango": 2}
    salida.sort(key=lambda b: (orden.get(b.overrun_status, 3), b.client_name, b.project_name))

    return ConsultaResponse(
        desde=desde, hasta=hasta, projects=salida,
        total_hours=sum((b.hours_in_range for b in salida), CERO),
        total_overtime=sum((b.overtime_in_range for b in salida), CERO),
        projects_count=len(salida),
        people_count=len({p.user_id for b in salida for p in b.people}),
        overrun_count=desfasados,
    )


@router.get("/dias", response_model=List[TimeEntryResponse])
async def dias_de_la_fila(
    project_id: uuid.UUID = Query(...),
    desde: date = Query(...),
    hasta: date = Query(...),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Los días de esa persona en ese proyecto (H-D33).

    Es lo que se despliega al ampliar una fila: fecha, actividad, horas, si se
    cobra y las observaciones. Sin `user_id` trae los de todo el mundo, que es lo
    que hace falta cuando se despliega el proyecto entero.
    """
    if hasta < desde:
        raise HTTPException(400, "El rango está al revés: «hasta» es anterior a «desde»")

    q = (select(TimeEntry)
         .where(TimeEntry.project_id == project_id,
                TimeEntry.date >= desde, TimeEntry.date <= hasta)
         .order_by(TimeEntry.date, TimeEntry.created_at))
    if user_id:
        q = q.where(TimeEntry.user_id == user_id)

    return await _responder(db, list((await db.execute(q)).scalars().all()))
