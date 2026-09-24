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
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, require_role
from app.db.models.client import Client
from app.db.models.time_tracking import (
    Activity, Project, ProjectActivity, ProjectActivityChange, ProjectDeletion,
    ProjectStatusChange, TimeEntry, normalizar,
)
# ETAPA H2b (§5.1): el CONSUMO, en un solo sitio. Con alias porque `estado` es
# además el nombre del filtro del listado y se taparían el uno al otro.
from app.services.horas.desfase import (
    estado as estado_desfase,
    etiqueta as etiqueta_desfase,
    horas_de_desfase,
    porcentaje as porcentaje_consumido,
)
# ETAPA H8 (§3.1): el ESTADO del proyecto. Es la otra columna, y la única
# definición de qué bloquea cada estado y quién puede ponerlo.
from app.services.horas import estados
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import (
    ProjectActivityChangeResponse, ProjectActivityResponse, ProjectActivityUpsert,
    ProjectCreate, ProjectDetailResponse, ProjectResponse, ProjectStatusChangeResponse,
    ProjectStatusUpdate, ProjectUpdate, ProyectoBorrado,
)

router = APIRouter()
logger = logging.getLogger(__name__)

CERO = Decimal("0")


def _campos_estado(status) -> dict:
    """Los cuatro campos del ESTADO de un proyecto (ETAPA H8, §3.1).

    Van juntos en una función porque las tres respuestas de este módulo —el
    listado, el detalle y el cambio de estado— tienen que decir exactamente lo
    mismo, y porque `can_log_hours` y `can_edit_estimates` son la tabla de §3.1
    ya resuelta: **la pantalla los consume, no los deduce**.
    """
    v = estados.normalizar_legado(status)
    return {
        "status": v,
        "status_label": estados.texto(v),
        "can_log_hours": estados.admite_registro(v),
        "can_edit_estimates": estados.admite_estimacion(v),
    }


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

    # ETAPA H3: las actividades que tienen horas registradas pero **no** están
    # estimadas. Pasa con los proyectos que crea la importación (§6.2.4), que
    # nacen sin estimación: sin esto, el detalle enseñaría 0 consumidas de un
    # proyecto que sí tiene horas. Estimadas 0 ⇒ `desfase.py` las deja en rango.
    sueltas = set(consumido) - {a.activity_id for a in actividades}
    if sueltas:
        nombres = {
            a.id: a.name for a in (await db.execute(
                select(Activity).where(Activity.id.in_(sueltas))
            )).scalars().all()
        }
        for aid in sueltas:
            con = consumido[aid]
            total_con += con
            actividades.append(ProjectActivityResponse(
                activity_id=aid, activity_name=nombres.get(aid, ""),
                estimated_hours=CERO, consumed_hours=con, remaining_hours=-con,
                over_estimate=False,
                consumed_pct=porcentaje_consumido(con, CERO),
                overrun_status=estado_desfase(con, CERO),
                overrun_hours=horas_de_desfase(con, CERO),
                overrun_label=etiqueta_desfase(con, CERO),
            ))

    return ProjectDetailResponse(
        id=proyecto.id, client_id=proyecto.client_id,
        client_name=cliente.name if cliente else "",
        name=proyecto.name, description=proyecto.description,
        created_at=proyecto.created_at,
        total_estimated_hours=total_est, total_consumed_hours=total_con,
        activities_count=len(actividades), activities=actividades,
        # ETAPA H2b (§5.1): el consumo del proyecto entero, el mismo que enseña
        # el listado. Sin esto el detalle diría «En rango» de un proyecto que el
        # listado acaba de marcar como desfasado, que es peor que no decir nada.
        consumed_pct=porcentaje_consumido(total_con, total_est),
        # ETAPA H8 (H-D82): el consumo ya NO se tapa con el estado. Un proyecto
        # finalizado sigue diciendo cuánto gastó; en qué punto está lo dice
        # `_campos_estado`, en su propia columna.
        overrun_status=estado_desfase(total_con, total_est),
        overrun_hours=horas_de_desfase(total_con, total_est),
        overrun_label=etiqueta_desfase(total_con, total_est),
        **_campos_estado(proyecto.status),
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
    estado: Optional[str] = Query(
        None, description="ETAPA H8 §3.1: uno de los cinco. Vacío = el filtro por "
                          "defecto"),
    incluir_finalizados: bool = Query(
        False, description="H-D84: trae también los finalizados y los no viables"),
    texto: Optional[str] = Query(None, description="busca en el nombre"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Listado con filtros. Todos los usuarios ven todos los proyectos (§8).

    **Por defecto esconde `finalizado` y `no_viable`** (H-D84): lo que se mira
    todos los días es lo que está en marcha. Pedir un `estado` concreto manda
    sobre eso — si alguien filtra por «finalizado», los quiere ver.

    **ETAPA H8.6: los alias de H-D91 se retiraron.** `incluir_cerrados` y
    `?estado=activo|cerrado` existieron entre H8.2 y H8.3, mientras la pantalla
    todavía mandaba los nombres viejos; hoy la pantalla manda
    `incluir_finalizados` y los cinco estados, así que seguir aceptándolos solo
    servía para que un cliente viejo pareciera funcionar. Ahora
    `?estado=activo` devuelve un **400 que dice cuáles valen**, que es lo que
    hace falta para darse cuenta.
    """
    q = select(Project, Client).join(Client, Client.id == Project.client_id)
    if client_id:
        q = q.where(Project.client_id == client_id)
    if estado:
        if not estados.es_valido(estado):
            raise HTTPException(
                400, "El estado tiene que ser uno de: " + ", ".join(estados.ESTADOS))
        q = q.where(Project.status == estado)
    elif not incluir_finalizados:
        q = q.where(Project.status.in_(estados.visibles_por_defecto()))
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
            description=p.description, created_at=p.created_at,
            total_estimated_hours=est, total_consumed_hours=con,
            activities_count=cuenta.get(p.id, 0),
            # ETAPA H2b (§5.1): campos AÑADIDOS. Lo que ya consumía esta
            # respuesta sigue igual.
            consumed_pct=porcentaje_consumido(con, est),
            overrun_status=estado_desfase(con, est),
            overrun_hours=horas_de_desfase(con, est),
            overrun_label=etiqueta_desfase(con, est),
            **_campos_estado(p.status),
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
        description=data.description, status=estados.POR_DEFECTO,
        created_by=current_user.id,
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


async def _cambiar_estado(db: AsyncSession, proyecto: Project, nuevo: str,
                          actual: User) -> ProjectDetailResponse:
    """El cambio de estado, con su historial (ETAPA H8, H-D83, §3.1).

    Una sola implementación: la usan el endpoint nuevo y los dos atajos viejos.
    Si hubiera dos, una de ellas acabaría olvidándose de escribir el historial.
    """
    if not estados.es_valido(nuevo):
        raise HTTPException(
            400, "El estado tiene que ser uno de: " + ", ".join(estados.ESTADOS))

    anterior = estados.normalizar_legado(proyecto.status)
    if anterior == nuevo:
        raise HTTPException(409, f"El proyecto ya está «{estados.texto(nuevo)}»")

    # §8: los dos estados que CIERRAN el proyecto —esconderlo del listado y
    # bloquear sus estimaciones— son de administrador, como lo era cerrarlo.
    # Los otros tres los cambia cualquiera, como el resto del módulo.
    if estados.exige_admin(nuevo) and actual.role != "admin":
        raise HTTPException(
            403, f"Poner un proyecto en «{estados.texto(nuevo)}» es cosa del administrador")

    proyecto.status = nuevo
    # `closed_at`/`closed_by` siguen contando cuándo se cerró y quién: ahora
    # valen para los DOS estados que cierran, no solo para el antiguo «cerrado».
    if nuevo in estados.SOLO_ADMIN:
        proyecto.closed_at = datetime.utcnow()
        proyecto.closed_by = actual.id
    else:
        proyecto.closed_at = None
        proyecto.closed_by = None

    db.add(ProjectStatusChange(
        id=uuid.uuid4(), project_id=proyecto.id,
        previous_status=anterior, new_status=nuevo, changed_by=actual.id))

    await db.commit()
    await db.refresh(proyecto)
    logger.info(f"Horas: proyecto «{proyecto.name}» pasa de «{anterior}» a «{nuevo}» "
                f"por {actual.username}")
    return await _detalle(db, proyecto)


@router.post("/{project_id}/estado", response_model=ProjectDetailResponse)
async def cambiar_estado(
    project_id: uuid.UUID,
    data: ProjectStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Cambiar el estado del proyecto (H-D83, §3.1).

    Cualquier usuario puede ponerlo en `pendiente`, `en_ejecucion` o `detenido`.
    **`no_viable` y `finalizado` son del administrador** (§8): son los dos que
    cierran el proyecto. El permiso se comprueba contra el estado que se pide,
    no en la dependencia, porque depende del cuerpo de la petición.
    """
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    return await _cambiar_estado(db, proyecto, data.status, current_user)


@router.get("/{project_id}/historial-estado",
            response_model=List[ProjectStatusChangeResponse])
async def historial_estado(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """El historial de estados, lo más reciente primero (H-D83).

    Aparte del de estimaciones y no mezclado con él: aquel va por actividad y
    este no tiene ninguna. La pantalla los enseña juntos (H8.3), que es otra
    cosa que tenerlos en el mismo endpoint.
    """
    if not await db.get(Project, project_id):
        raise HTTPException(404, "Proyecto no encontrado")

    filas = (await db.execute(
        select(ProjectStatusChange, User)
        .outerjoin(User, User.id == ProjectStatusChange.changed_by)
        .where(ProjectStatusChange.project_id == project_id)
        .order_by(ProjectStatusChange.changed_at.desc())
    )).all()

    return [
        ProjectStatusChangeResponse(
            id=c.id,
            previous_status=c.previous_status,
            previous_label=estados.texto(c.previous_status) if c.previous_status else "",
            new_status=c.new_status, new_label=estados.texto(c.new_status),
            changed_by_name=(u.full_name or u.username) if u else "",
            changed_at=c.changed_at,
        )
        for c, u in filas
    ]


# --------------------------------------------------------------------------
# ETAPA H8: los dos atajos de antes. Se quedan **delegando** en el de arriba.
#
# El frontend todavía los llama hasta H8.3, y retirarlos ahora dejaría los
# botones «Cerrar» y «Reabrir» dando 404 sin que nadie lo hubiera pedido. Lo que
# no hacen es duplicar la lógica: pasan por `_cambiar_estado`, así que escriben
# su historial y respetan el permiso igual que el endpoint nuevo.
# --------------------------------------------------------------------------

@router.post("/{project_id}/cerrar", response_model=ProjectDetailResponse)
async def cerrar_proyecto(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """OBSOLETO desde H8 — usar `POST /{id}/estado`. Cerrar es `finalizado`."""
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    return await _cambiar_estado(db, proyecto, estados.FINALIZADO, current_user)


@router.post("/{project_id}/reabrir", response_model=ProjectDetailResponse)
async def reabrir_proyecto(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """OBSOLETO desde H8 — usar `POST /{id}/estado`. Reabrir es `en_ejecucion`."""
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")
    return await _cambiar_estado(db, proyecto, estados.EN_EJECUCION, current_user)


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
    # ETAPA H8 (§3.1): bloquean las estimaciones `no_viable` y `finalizado`.
    # `pendiente` y `detenido` NO: son temporales y se siguen planificando.
    if not estados.admite_estimacion(proyecto.status):
        raise HTTPException(
            409, f"El proyecto está «{estados.texto(proyecto.status)}» "
                 "y no admite cambios en sus estimaciones.")

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
    # ETAPA H8 (§3.1): mismo criterio que al añadir o cambiar una estimación.
    if not estados.admite_estimacion(proyecto.status):
        raise HTTPException(
            409, f"El proyecto está «{estados.texto(proyecto.status)}» "
                 "y no admite cambios en sus estimaciones.")

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


# ===================== BORRAR UN PROYECTO (CARGA REAL, §2) =====================

@router.delete("/{project_id}", response_model=ProyectoBorrado)
async def borrar_proyecto(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Borra un proyecto y lo que cuelga de él. **Solo admin y sin horas.**

    Existe para poder empezar un periodo de cero: hasta ahora el producto sabía
    borrar registros (`/time/borrado`) pero no los proyectos que la importación
    había creado con un nombre equivocado, y esos nombres se quedaban
    compitiendo con los buenos en todas las pantallas.

    Las guardas, en el orden en que se comprueban:

    | Guarda | Por qué |
    |---|---|
    | `require_role(["admin"])` | Igual que cerrar un proyecto (§8, H-D90) |
    | Sin registros de horas | Un proyecto con horas **no se borra por accidente**: se borran antes sus registros, por el endpoint que deja constancia de ello |
    | Una transacción | O se va entero o no se va nada |
    | `project_deletions` | Quién, qué proyecto, de qué cliente y cuándo |

    Lo que se lleva con él —`project_activities`, `project_activity_changes` y
    `project_status_changes`— se va por el `ON DELETE CASCADE` que esas tres
    tablas ya declaran. Sin el proyecto no significan nada: una estimación de 20
    horas para un proyecto que no existe no se puede ni leer ni corregir.

    **No está en la pantalla a propósito.** El botón de borrar un proyecto es
    una decisión aparte, con su confirmación; este endpoint es el que necesita
    la carga.
    """
    proyecto = await db.get(Project, project_id)
    if not proyecto:
        raise HTTPException(404, "Proyecto no encontrado")

    # La guarda que importa. Se dice **cuántos** registros son: «tiene horas» no
    # deja decidir nada, y el número lleva derecho a la pantalla de consulta.
    registros = (await db.execute(
        select(func.count()).select_from(TimeEntry)
        .where(TimeEntry.project_id == project_id)
    )).scalar_one()
    if registros:
        raise HTTPException(
            409,
            f"«{proyecto.name}» tiene {registros} registro(s) de horas y no se "
            "puede borrar. Bórralos antes desde el borrado por periodo: así el "
            "borrado de las horas queda con su propia constancia.")

    cliente = await db.get(Client, proyecto.client_id)
    nombre_cliente = cliente.name if cliente else ""

    # Se cuentan ANTES de borrar: después ya no hay a quién preguntarle.
    async def cuantas(modelo):
        return (await db.execute(
            select(func.count()).select_from(modelo)
            .where(modelo.project_id == project_id)
        )).scalar_one()

    estimaciones = await cuantas(ProjectActivity)
    hist_estimaciones = await cuantas(ProjectActivityChange)
    hist_estados = await cuantas(ProjectStatusChange)

    constancia = ProjectDeletion(
        id=uuid.uuid4(), project_name=proyecto.name, client_name=nombre_cliente,
        status=estados.normalizar_legado(proyecto.status),
        estimaciones_borradas=estimaciones,
        historial_estimaciones=hist_estimaciones,
        historial_estados=hist_estados,
        performed_by=current_user.id)
    db.add(constancia)
    await db.delete(proyecto)
    await db.commit()
    await db.refresh(constancia)

    logger.warning(
        "Horas: BORRADO DE PROYECTO — «%s» (cliente «%s»): %s estimaciones, "
        "%s cambios de estimación, %s cambios de estado, por %s el %s",
        proyecto.name, nombre_cliente, estimaciones, hist_estimaciones,
        hist_estados, current_user.username, constancia.performed_at)

    return ProyectoBorrado(
        id=project_id, name=constancia.project_name,
        client_name=nombre_cliente, status=constancia.status,
        estimaciones_borradas=estimaciones,
        historial_estimaciones_borrado=hist_estimaciones,
        historial_estados_borrado=hist_estados,
        performed_by=(current_user.full_name or current_user.username),
        performed_at=constancia.performed_at,
    )
