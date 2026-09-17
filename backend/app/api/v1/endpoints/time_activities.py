"""Catálogo de actividades del MÓDULO DE HORAS (ETAPA H1.3).

Especificación de horas v1.0 §1.2 y §8.

  - Listar, crear y renombrar: **cualquier usuario autenticado** (§8).
  - Activar / desactivar: cualquier usuario.
  - Borrar: **solo admin**, y solo si la actividad no se usa (H-D4).

La regla que de verdad importa: **una actividad con horas registradas no se borra
nunca**, ni siendo admin. Se desactiva, deja de ofrecerse en los proyectos nuevos
y lo ya registrado se queda como está.
"""
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.security import get_current_active_user, require_role
from app.db.models.time_tracking import (
    Activity, ProjectActivity, TimeEntry, normalizar,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import (
    ActivityCreate, ActivityResponse, ActivityUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = logging.getLogger(__name__)


async def _uso(db: AsyncSession, ids: List[uuid.UUID]) -> dict:
    """Cuántos proyectos usan cada actividad y si tiene horas registradas.

    Dos consultas agregadas para toda la lista, no una por fila: la pantalla las
    pinta todas y no tiene sentido pagar N+1 por un catálogo.
    """
    if not ids:
        return {}
    proyectos = dict((await db.execute(
        select(ProjectActivity.activity_id, func.count())
        .where(ProjectActivity.activity_id.in_(ids))
        .group_by(ProjectActivity.activity_id)
    )).all())
    con_horas = {
        r[0] for r in (await db.execute(
            select(TimeEntry.activity_id)
            .where(TimeEntry.activity_id.in_(ids))
            .group_by(TimeEntry.activity_id)
        )).all()
    }
    return {i: (proyectos.get(i, 0), i in con_horas) for i in ids}


def _respuesta(a: Activity, uso) -> ActivityResponse:
    proyectos, con_horas = uso.get(a.id, (0, False))
    return ActivityResponse(
        id=a.id, name=a.name, is_active=a.is_active, created_at=a.created_at,
        projects_count=proyectos, has_entries=con_horas,
    )


@router.get("", response_model=List[ActivityResponse])
async def listar_actividades(
    solo_activas: bool = Query(False, description="Solo las que se pueden asignar hoy"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """El catálogo entero, con el uso de cada actividad."""
    q = select(Activity)
    if solo_activas:
        q = q.where(Activity.is_active.is_(True))
    filas = (await db.execute(q.order_by(Activity.created_at))).scalars().all()
    uso = await _uso(db, [a.id for a in filas])
    return [_respuesta(a, uso) for a in filas]


@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def crear_actividad(
    data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Crear una actividad. Queda disponible para TODOS los proyectos (H-D3)."""
    nombre = (data.name or "").strip()
    if not nombre:
        raise HTTPException(400, "El nombre de la actividad no puede estar vacío")
    clave = normalizar(nombre)
    if (await db.execute(
        select(Activity).where(Activity.name_normalized == clave)
    )).scalar_one_or_none():
        raise HTTPException(409, f"Ya existe una actividad llamada «{nombre}»")

    actividad = Activity(id=uuid.uuid4(), name=nombre, name_normalized=clave,
                         is_active=True, created_by=current_user.id)
    db.add(actividad)
    await db.commit()
    await db.refresh(actividad)
    logger.info(f"Horas: actividad creada «{nombre}» por {current_user.username}")
    return _respuesta(actividad, {})


@router.put("/{activity_id}", response_model=ActivityResponse)
async def editar_actividad(
    activity_id: uuid.UUID,
    data: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Renombrar y/o activar-desactivar.

    Desactivar es lo que sustituye al borrado cuando la actividad ya se usa
    (H-D4): deja de ofrecerse en los proyectos nuevos y no afecta a lo registrado.
    """
    actividad = await db.get(Activity, activity_id)
    if not actividad:
        raise HTTPException(404, "Actividad no encontrada")

    if data.name is not None:
        nombre = data.name.strip()
        if not nombre:
            raise HTTPException(400, "El nombre de la actividad no puede estar vacío")
        clave = normalizar(nombre)
        choque = (await db.execute(
            select(Activity).where(Activity.name_normalized == clave,
                                   Activity.id != activity_id)
        )).scalar_one_or_none()
        if choque:
            raise HTTPException(409, f"Ya existe una actividad llamada «{nombre}»")
        actividad.name, actividad.name_normalized = nombre, clave

    if data.is_active is not None:
        actividad.is_active = data.is_active

    await db.commit()
    await db.refresh(actividad)
    uso = await _uso(db, [actividad.id])
    return _respuesta(actividad, uso)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_actividad(
    activity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Borrar. Solo admin y solo si no se usa (H-D4, §8).

    Se comprueban las dos cosas por separado para poder decir cuál estorba:
    tener horas registradas es definitivo; estar en un proyecto se puede
    deshacer quitándola de ahí.
    """
    actividad = await db.get(Activity, activity_id)
    if not actividad:
        raise HTTPException(404, "Actividad no encontrada")

    horas = (await db.execute(
        select(func.count()).select_from(TimeEntry)
        .where(TimeEntry.activity_id == activity_id)
    )).scalar_one()
    if horas:
        raise HTTPException(
            409,
            f"«{actividad.name}» tiene {horas} registro(s) de horas y no se puede borrar. "
            "Desactívala: dejará de ofrecerse en los proyectos nuevos y lo ya registrado "
            "se conserva.")

    proyectos = (await db.execute(
        select(func.count()).select_from(ProjectActivity)
        .where(ProjectActivity.activity_id == activity_id)
    )).scalar_one()
    if proyectos:
        raise HTTPException(
            409,
            f"«{actividad.name}» está en {proyectos} proyecto(s). Quítala de ellos "
            "o desactívala.")

    await db.delete(actividad)
    await db.commit()
    logger.info(f"Horas: actividad borrada «{actividad.name}» por {current_user.username}")
