"""Proyectos del MÓDULO DE HORAS (ETAPA H1.3).

Especificación de horas v1.0 §3 y §8.

  - Crear, listar, ver y editar: **cualquier usuario** (§3: "cualquier usuario
    puede crear un proyecto").
  - Cerrar y reabrir: **solo admin** (§8).
  - Cada cambio de estimación escribe su historial, siempre (H-D11).
  - Una actividad con horas registradas no se puede quitar del proyecto (H-D12).

El detalle devuelve ya `consumed_hours` y `remaining_hours` por actividad, en 0
mientras no exista el registro de horas: **el contrato se fija ahora para que H2
y H3 no tengan que cambiarlo**.
"""
import logging
import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, require_role
from app.db.models.client import Client
from app.db.models.time_tracking import (
    Activity, Project, ProjectActivity, ProjectActivityChange, TimeEntry, normalizar,
)
# ETAPA H2b (§5.1): el estado de desfase, en un solo sitio. Con alias porque
# `estado` es además el nombre del filtro del listado (activo/cerrado) y se
# taparían el uno al otro.
from app.services.horas.desfase import (
    estado as estado_desfase,
    etiqueta as etiqueta_desfase,
    horas_de_desfase,
    porcentaje as porcentaje_consumido,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import (
    ProjectActivityChangeResponse, ProjectActivityResponse, ProjectActivityUpsert,
    ProjectCreate, ProjectDetailResponse, ProjectResponse, ProjectUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)

CERO = Decimal("0")


async def _consumido(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """Horas registradas por actividad en un proyecto.

    Hoy `time_entries` está vacía y esto devuelve {}: el registro llega en H2.
    La consulta ya está escrita para que el contrato de la respuesta no cambie
    cuando haya datos.
    """
    filas = (await db.execute(
        select(TimeEntry.activity_id, func.coalesce(func.sum(TimeEntry.hours), 0))
        .where(TimeEntry.project_id == project_id)
        .group_by(TimeEntry.activity_id)
    )).all()
    return {a: Decimal(str(h)) for a, h in filas}


async def _detalle(db: AsyncSession, proyecto: Project) -> ProjectDetailResponse:
    cliente = await db.get(Client, proyecto.client_id)
    filas = (await db.execute(
        select(ProjectActivity, Activity)
        .join(Activity, Activity.id == ProjectActivity.activity_id)
        .where(ProjectActivity.project_id == proyecto.id)
        .order_by(Activity.created_at)
    )).all()
    consumido = await _consumido(db, proyecto.id)

    actividades, total_est, total_con = [], CERO, CERO
    for pa, act in filas:
        est = Decimal(str(pa.estimated_hours))
        con = consumido.get(act.id, CERO)
        total_est += est
        total_con += con
        actividades.append(ProjectActivityResponse(
            activity_id=act.id, activity_name=act.name,
            estimated_hours=est, consumed_hours=con,
            remaining_hours=est - con,
            over_estimate=con > est,
            # ETAPA H2b (§5.1): el mismo estado por actividad.
            consumed_pct=porcentaje_consumido(con, est),
            overrun_status=estado_desfase(con, est),
            overrun_hours=horas_de_desfase(con, est),
            overrun_label=etiqueta_desfase(con, est),
        ))

    return ProjectDetailResponse(
        id=proyecto.id, client_id=proyecto.client_id,
        client_name=cliente.name if cliente else "",
        name=proyecto.name, description=proyecto.description, status=proyecto.status,
        created_at=proyecto.created_at,
        total_estimated_hours=total_est, total_consumed_hours=total_con,
        activities_count=len(actividades), activities=actividades,
        # ETAPA H2b (§5.1): el estado del proyecto entero, el mismo que enseña el
        # listado. Sin esto el detalle diría «En rango» de un proyecto que el
        # listado acaba de marcar como desfasado, que es peor que no decir nada.
        consumed_pct=porcentaje_consumido(total_con, total_est),
        overrun_status=estado_desfase(total_con, total_est),
        overrun_hours=horas_de_desfase(total_con, total_est),
        overrun_label=etiqueta_desfase(total_con, total_est),
    )


async def _nombre_libre(db: AsyncSession, client_id, nombre: str, excluir=None):
    """§3: el nombre es único POR CLIENTE, comparado normalizado."""
    clave = normalizar(nombre)
    q = select(Project).where(Project.client_id == client_id,
                              Project.name_normalized == clave)
    if excluir:
        q = q.where(Project.id != excluir)
    if (await db.execute(q)).scalar_one_or_none():
        raise HTTPException(409, f"Ese cliente ya tiene un proyecto llamado «{nombre}»")
    return clave


@router.get("", response_model=List[ProjectResponse])
async def listar_proyectos(
    client_id: Optional[uuid.UUID] = Query(None),
    estado: Optional[str] = Query(None, description="activo | cerrado"),
    texto: Optional[str] = Query(None, description="busca en el nombre"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Listado con filtros. Todos los usuarios ven todos los proyectos (§8)."""
    q = select(Project, Client).join(Client, Client.id == Project.client_id)
    if client_id:
        q = q.where(Project.client_id == client_id)
    if estado:
        if estado not in ("activo", "cerrado"):
            raise HTTPException(400, "El estado tiene que ser «activo» o «cerrado»")
        q = q.where(Project.status == estado)
    if texto and texto.strip():
        q = q.where(Project.name_normalized.contains(normalizar(texto)))

    filas = (await db.execute(q.order_by(Client.name, Project.name))).all()
    if not filas:
        return []

    ids = [p.id for p, _ in filas]
    estimado = dict((await db.execute(
        select(ProjectActivity.project_id, func.coalesce(func.sum(ProjectActivity.estimated_hours), 0))
        .where(ProjectActivity.project_id.in_(ids))
        .group_by(ProjectActivity.project_id)
    )).all())
    cuenta = dict((await db.execute(
        select(ProjectActivity.project_id, func.count())
        .where(ProjectActivity.project_id.in_(ids))
        .group_by(ProjectActivity.project_id)
    )).all())
    consumido = dict((await db.execute(
        select(TimeEntry.project_id, func.coalesce(func.sum(TimeEntry.hours), 0))
        .where(TimeEntry.project_id.in_(ids))
        .group_by(TimeEntry.project_id)
    )).all())

    salida = []
    for p, c in filas:
        est = Decimal(str(estimado.get(p.id, 0)))
        con = Decimal(str(consumido.get(p.id, 0)))
        salida.append(ProjectResponse(
            id=p.id, client_id=p.client_id, client_name=c.name, name=p.name,
            description=p.description, status=p.status, created_at=p.created_at,
            total_estimated_hours=est, total_consumed_hours=con,
            activities_count=cuenta.get(p.id, 0),
            # ETAPA H2b (§5.1): campos AÑADIDOS. Lo que ya consumía esta
            # respuesta sigue igual.
            consumed_pct=porcentaje_consumido(con, est),
            overrun_status=estado_desfase(con, est),
            overrun_hours=horas_de_desfase(con, est),
            overrun_label=etiqueta_desfase(con, est),
        ))
    return salida


@router.post("", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
async def crear_proyecto(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Crear un proyecto con su estimación inicial (§3, H-D6).

    Obligatorio: cliente, nombre y al menos una actividad con horas. Lo de "al
    menos una" lo valida el schema; aquí se comprueba lo que necesita la base.
    """
    cliente = await db.get(Client, data.client_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    nombre = (data.name or "").strip()
    if not nombre:
        raise HTTPException(400, "El nombre del proyecto no puede estar vacío")
    clave = await _nombre_libre(db, data.client_id, nombre)

    ids = [a.activity_id for a in data.activities]
    encontradas = {
        a.id: a for a in (await db.execute(
            select(Activity).where(Activity.id.in_(ids))
        )).scalars().all()
    }
    faltan = [str(i) for i in ids if i not in encontradas]
    if faltan:
        raise HTTPException(404, f"Actividad no encontrada: {', '.join(faltan)}")
    inactivas = [encontradas[i].name for i in ids if not encontradas[i].is_active]
    if inactivas:
        raise HTTPException(
            400, f"No se pueden asignar actividades desactivadas: {', '.join(inactivas)}")

    proyecto = Project(
        id=uuid.uuid4(), client_id=data.client_id, name=nombre, name_normalized=clave,
        description=data.description, status="activo", created_by=current_user.id,
    )
    db.add(proyecto)
    await db.flush()

    for a in data.activities:
        db.add(ProjectActivity(id=uuid.uuid4(), project_id=proyecto.id,
                               activity_id=a.activity_id,
                               estimated_hours=a.estimated_hours))
        # H-D11: hasta el alta deja rastro.
        db.add(ProjectActivityChange(
            id=uuid.uuid4(), project_id=proyecto.id, activity_id=a.activity_id,
            previous_hours=None, new_hours=a.estimated_hours,
            change_type="alta", changed_by=current_user.id))

    await db.commit()
    await db.refresh(proyecto)
    logger.info(f"Horas: proyecto «{nombre}» creado por {current_user.username} "
                f"con {len(data.activities)} actividad(es)")
    return await _detalle(db, proyecto)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def ver_proyecto(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    return await _detalle(db, proyecto)


@router.put("/{project_id}", response_model=ProjectDetailResponse)
async def editar_proyecto(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Renombrar o cambiar la descripción. Las actividades van por su endpoint."""
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")

    if data.name is not None:
        nombre = data.name.strip()
        if not nombre:
            raise HTTPException(400, "El nombre del proyecto no puede estar vacío")
        proyecto.name_normalized = await _nombre_libre(
            db, proyecto.client_id, nombre, excluir=project_id)
        proyecto.name = nombre
    if data.description is not None:
        proyecto.description = data.description

    await db.commit()
    await db.refresh(proyecto)
    return await _detalle(db, proyecto)


@router.post("/{project_id}/cerrar", response_model=ProjectDetailResponse)
async def cerrar_proyecto(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Cerrar. Solo admin (§8). Un proyecto cerrado no admite registros nuevos
    pero se sigue consultando (§3)."""
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    if proyecto.status == "cerrado":
        raise HTTPException(409, "El proyecto ya está cerrado")
    from datetime import datetime
    proyecto.status = "cerrado"
    proyecto.closed_at = datetime.utcnow()
    proyecto.closed_by = current_user.id
    await db.commit()
    await db.refresh(proyecto)
    logger.info(f"Horas: proyecto «{proyecto.name}» cerrado por {current_user.username}")
    return await _detalle(db, proyecto)


@router.post("/{project_id}/reabrir", response_model=ProjectDetailResponse)
async def reabrir_proyecto(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Reabrir. Solo admin, por simetría con cerrar."""
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    if proyecto.status == "activo":
        raise HTTPException(409, "El proyecto ya está activo")
    proyecto.status = "activo"
    proyecto.closed_at = None
    proyecto.closed_by = None
    await db.commit()
    await db.refresh(proyecto)
    return await _detalle(db, proyecto)


@router.put("/{project_id}/actividades", response_model=ProjectDetailResponse)
async def upsert_actividad(
    project_id: uuid.UUID,
    data: ProjectActivityUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Añadir una actividad al proyecto o cambiar su estimación.

    H-D11: **siempre** escribe en el historial, con el valor anterior y el nuevo.
    Si la estimación no cambia, no se escribe nada — una fila que dice "de 10 a
    10" es ruido, no rastro.
    """
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    if proyecto.status == "cerrado":
        raise HTTPException(409, "El proyecto está cerrado: no admite cambios")

    actividad = await db.get(Activity, data.activity_id)
    if not actividad:
        raise HTTPException(404, "Actividad no encontrada")

    fila = (await db.execute(
        select(ProjectActivity).where(ProjectActivity.project_id == project_id,
                                      ProjectActivity.activity_id == data.activity_id)
    )).scalar_one_or_none()

    if fila is None:
        if not actividad.is_active:
            raise HTTPException(400, f"«{actividad.name}» está desactivada")
        db.add(ProjectActivity(id=uuid.uuid4(), project_id=project_id,
                               activity_id=data.activity_id,
                               estimated_hours=data.estimated_hours))
        db.add(ProjectActivityChange(
            id=uuid.uuid4(), project_id=project_id, activity_id=data.activity_id,
            previous_hours=None, new_hours=data.estimated_hours,
            change_type="alta", changed_by=current_user.id))
    else:
        anterior = Decimal(str(fila.estimated_hours))
        if anterior != data.estimated_hours:
            fila.estimated_hours = data.estimated_hours
            db.add(ProjectActivityChange(
                id=uuid.uuid4(), project_id=project_id, activity_id=data.activity_id,
                previous_hours=anterior, new_hours=data.estimated_hours,
                change_type="cambio", changed_by=current_user.id))

    await db.commit()
    await db.refresh(proyecto)
    return await _detalle(db, proyecto)


@router.delete("/{project_id}/actividades/{activity_id}", response_model=ProjectDetailResponse)
async def quitar_actividad(
    project_id: uuid.UUID,
    activity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Quitar una actividad del proyecto. Solo si no tiene horas (H-D12)."""
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    if proyecto.status == "cerrado":
        raise HTTPException(409, "El proyecto está cerrado: no admite cambios")

    fila = (await db.execute(
        select(ProjectActivity).where(ProjectActivity.project_id == project_id,
                                      ProjectActivity.activity_id == activity_id)
    )).scalar_one_or_none()
    if not fila:
        raise HTTPException(404, "Esa actividad no está en el proyecto")

    horas = (await db.execute(
        select(func.count()).select_from(TimeEntry)
        .where(TimeEntry.project_id == project_id,
               TimeEntry.activity_id == activity_id)
    )).scalar_one()
    if horas:
        raise HTTPException(
            409, f"Esa actividad tiene {horas} registro(s) de horas en este proyecto "
                 "y no se puede quitar.")

    anterior = Decimal(str(fila.estimated_hours))
    await db.delete(fila)
    db.add(ProjectActivityChange(
        id=uuid.uuid4(), project_id=project_id, activity_id=activity_id,
        previous_hours=anterior, new_hours=None,
        change_type="baja", changed_by=current_user.id))
    await db.commit()
    await db.refresh(proyecto)
    return await _detalle(db, proyecto)


@router.get("/{project_id}/historial", response_model=List[ProjectActivityChangeResponse])
async def historial(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """El historial de estimaciones del proyecto, lo más reciente primero (H-D11)."""
    if not await db.get(Project, project_id):
        raise HTTPException(404, "Proyecto no encontrado")

    filas = (await db.execute(
        select(ProjectActivityChange, Activity, User)
        .join(Activity, Activity.id == ProjectActivityChange.activity_id)
        .outerjoin(User, User.id == ProjectActivityChange.changed_by)
        .where(ProjectActivityChange.project_id == project_id)
        .order_by(ProjectActivityChange.changed_at.desc())
    )).all()

    return [
        ProjectActivityChangeResponse(
            id=c.id, activity_id=c.activity_id, activity_name=a.name,
            previous_hours=c.previous_hours, new_hours=c.new_hours,
            change_type=c.change_type,
            changed_by_name=(u.full_name or u.username) if u else "",
            changed_at=c.changed_at,
        )
        for c, a, u in filas
    ]
