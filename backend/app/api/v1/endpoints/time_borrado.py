"""Borrado de los registros de un periodo (ETAPA H8.5, §4.3, H-D88/H-D89).

    GET  /time/borrado/preview?desde=&hasta=   analiza y NO escribe nada
    POST /time/borrado/confirm                 borra, en una transacción

Existe para poder **volver a cargar un periodo desde cero** cuando la
importación trajo algo mal. Es la operación más peligrosa del módulo, así que
todo aquí está puesto para que no pueda ocurrir por accidente:

| Condición | Dónde |
|---|---|
| Solo administrador | `require_role(["admin"])` en los dos endpoints |
| Vista previa que no escribe | La previa es un `GET`: no abre transacción de escritura |
| Confirmación tecleada | `_frase(desde, hasta)`, comparada normalizada |
| La copia la hace una persona | `copia_hecha` obligatorio; **Kinetix no ejecuta `pg_dump`** |
| Todo o nada | Un solo `DELETE` dentro de la transacción de la petición |
| Queda constancia | `time_entry_purges` **y** el log |

**Solo se borran registros de horas.** Proyectos, clientes, actividades, sus
estimaciones y su historial no se tocan: ni aparecen en este archivo más que
para contarlos y decir que siguen ahí.

Reglas 28 a 33: nacieron de una pérdida de datos real. Este endpoint es la única
forma que tiene el producto de borrar en bloque, y por eso deja rastro.
"""
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_role
from app.db.models.client import Client
from app.db.models.time_tracking import (
    Activity, Project, ProjectActivity, TimeEntry, TimeEntryPurge, normalizar,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import (
    BorradoConfirm, BorradoPersona, BorradoPreview, BorradoResumen,
)
# El periodo se escribe con la MISMA función que el informe (H-D61). Si aquí
# hubiera otra, la frase que hay que teclear y la que se lee en el informe
# podrían acabar diciendo cosas distintas del mismo rango.
from app.services.horas.informe_datos import describir_periodo

router = APIRouter()
logger = logging.getLogger(__name__)
CERO = Decimal("0")


def _rango(desde: date, hasta: date) -> None:
    if hasta < desde:
        raise HTTPException(400, "El rango está al revés: «hasta» es anterior a «desde»")


def _frase(desde: date, hasta: date) -> str:
    """Lo que hay que teclear para confirmar: el periodo, en español."""
    return describir_periodo(desde, hasta)


def _comando_copia() -> str:
    """El `pg_dump` ya escrito (H-D89).

    **Kinetix no lo ejecuta.** No puede —el backend es otro contenedor, no trae
    el binario y no ve la carpeta del anfitrión— y tampoco debe: el mismo
    criterio que con los `docker compose build`, el sistema no toca lo que es de
    Fredy, le da el comando.
    """
    hoy = datetime.now().strftime("%Y%m%d")
    return ("docker exec jmeter_postgres pg_dump -U jmeter_user -d jmeter_analyzer_db "
            f"> C:/proyectos/Kinetix_pruebas/backup_antes_de_borrar_{hoy}.sql")


async def _lo_que_sobrevive(db: AsyncSession) -> str:
    """§4.3, con esas palabras y con las cuentas de ahora.

    Se cuentan de verdad, no se afirman: si algún día este endpoint empezara a
    borrar de más, esta frase sería lo primero en delatarlo.
    """
    async def cuantos(modelo):
        return (await db.execute(select(func.count()).select_from(modelo))).scalar_one()

    def plural(n: int, uno: str, varios: str) -> str:
        return f"{n} {uno}" if n == 1 else f"{n} {varios}"

    proyectos = await cuantos(Project)
    actividades = await cuantos(Activity)
    estimaciones = await cuantos(ProjectActivity)
    clientes = await cuantos(Client)
    return ("Se borran SOLO registros de horas. No se toca nada más: "
            f"{plural(proyectos, 'proyecto', 'proyectos')} con "
            f"{plural(estimaciones, 'su estimación', 'sus estimaciones')} y su "
            f"historial, {plural(actividades, 'actividad', 'actividades')} y "
            f"{plural(clientes, 'cliente', 'clientes')} siguen exactamente igual "
            "después del borrado.")


async def _resumen_del_rango(db: AsyncSession, desde: date, hasta: date):
    """Lo que hay en el rango, agrupado. **Solo lee.**"""
    total, horas = (await db.execute(
        select(func.count(TimeEntry.id), func.coalesce(func.sum(TimeEntry.hours), 0))
        .where(TimeEntry.date >= desde, TimeEntry.date <= hasta)
    )).one()

    filas = (await db.execute(
        select(User, func.count(TimeEntry.id), func.coalesce(func.sum(TimeEntry.hours), 0))
        .join(User, User.id == TimeEntry.user_id)
        .where(TimeEntry.date >= desde, TimeEntry.date <= hasta)
        .group_by(User.id)
    )).all()
    por_persona = sorted(
        (BorradoPersona(user_name=(u.full_name or u.username), entries=int(n),
                        hours=Decimal(str(h)))
         for u, n, h in filas),
        key=lambda b: b.user_name.lower())

    importados = (await db.execute(
        select(func.count(TimeEntry.id))
        .where(TimeEntry.date >= desde, TimeEntry.date <= hasta,
               TimeEntry.source == "import")
    )).scalar_one()

    return int(total), Decimal(str(horas)), por_persona, int(importados)


@router.get("/preview", response_model=BorradoPreview)
async def vista_previa(
    desde: date = Query(..., description="Primer día que se borraría"),
    hasta: date = Query(..., description="Último día que se borraría"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Qué pasaría si se confirmara. **No escribe nada** (§4.3).

    Es un `GET` a propósito: así no hay ninguna ruta por la que este endpoint
    pueda modificar la base, ni equivocándose.
    """
    _rango(desde, hasta)
    total, horas, por_persona, importados = await _resumen_del_rango(db, desde, hasta)
    return BorradoPreview(
        desde=desde, hasta=hasta, periodo=describir_periodo(desde, hasta),
        total_entries=total, total_hours=horas, por_persona=por_persona,
        de_importacion=importados, manuales=total - importados,
        frase_de_confirmacion=_frase(desde, hasta),
        comando_copia=_comando_copia(),
        lo_que_no_se_borra=await _lo_que_sobrevive(db),
    )


@router.post("/confirm", response_model=BorradoResumen)
async def confirmar(
    data: BorradoConfirm,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Borra los registros del rango. Las tres condiciones, en orden."""
    _rango(data.desde, data.hasta)

    # 1. La copia. Primero, porque es la que no tiene vuelta atrás si falta.
    if not data.copia_hecha:
        raise HTTPException(
            400, "Antes de borrar hay que hacer la copia de seguridad y marcar "
                 "la casilla que lo confirma. El comando está en la vista previa.")

    # 2. La frase. Normalizada: «Septiembre de 2026» vale, «septiembre 2026» no.
    esperada = _frase(data.desde, data.hasta)
    if normalizar(data.confirmacion or "") != normalizar(esperada):
        raise HTTPException(
            400, f"Para confirmar hay que escribir el periodo exactamente: «{esperada}»")

    # 3. Y que haya algo que borrar, para no dejar constancia de un borrado vacío.
    total, horas, _, _ = await _resumen_del_rango(db, data.desde, data.hasta)
    if total == 0:
        raise HTTPException(404, f"No hay registros en {esperada}: no se borra nada.")

    # Una sola sentencia, dentro de la transacción de la petición: o se borran
    # todos los del rango o no se borra ninguno.
    await db.execute(
        delete(TimeEntry).where(TimeEntry.date >= data.desde, TimeEntry.date <= data.hasta))

    purga = TimeEntryPurge(
        id=uuid.uuid4(), desde=data.desde, hasta=data.hasta,
        entries_deleted=total, hours_deleted=horas,
        confirmation_text=(data.confirmacion or "")[:200],
        performed_by=current_user.id)
    db.add(purga)
    await db.commit()
    await db.refresh(purga)

    logger.warning(
        "Horas: BORRADO DE PERIODO — %s (%s a %s): %s registros, %s h, "
        "por %s el %s", esperada, data.desde, data.hasta, total, horas,
        current_user.username, purga.performed_at)

    return BorradoResumen(
        desde=data.desde, hasta=data.hasta, periodo=esperada,
        entries_deleted=total, hours_deleted=horas,
        performed_by=(current_user.full_name or current_user.username),
        performed_at=purga.performed_at,
        lo_que_no_se_borro=await _lo_que_sobrevive(db),
    )
