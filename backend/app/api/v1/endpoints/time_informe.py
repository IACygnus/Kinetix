"""El informe de horas (ETAPA H5, especificación v1.2 §7).

    GET /time/informe        los datos de las diez secciones, en JSON
    GET /time/informe/html   el documento HTML autocontenido (H5.3)
    GET /time/informe/pdf    el mismo documento en PDF (H5.4)
    GET /time/informe/csv    el detalle de registros, para Excel (H-D59)

Los cuatro comparten `construir_informe()`, que es lo que hace que el número del
resumen, el de la tabla y el del CSV sean **el mismo número**. §8: todos ven los
registros de todos, así que el filtro de personas es del usuario, no del permiso.
"""
import logging
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import InformeDatos
from app.services.horas.informe_datos import construir_informe

router = APIRouter()
logger = logging.getLogger(__name__)

# Un rango más largo que esto casi siempre es un error de dedo en el formulario,
# y un informe de varios años no lo lee nadie.
MAX_DIAS = 400


async def _datos(
    db: AsyncSession, desde: date, hasta: date,
    user_id: Optional[List[uuid.UUID]], client_id, project_id, solo_facturables: bool,
) -> InformeDatos:
    if hasta < desde:
        raise HTTPException(400, "El rango está al revés: «hasta» es anterior a «desde»")
    if (hasta - desde).days > MAX_DIAS:
        raise HTTPException(400, f"El rango no puede pasar de {MAX_DIAS} días")
    return await construir_informe(
        db, desde, hasta, user_ids=user_id or None, client_id=client_id,
        project_id=project_id, solo_facturables=solo_facturables,
    )


@router.get("", response_model=InformeDatos)
async def informe(
    desde: date = Query(...),
    hasta: date = Query(...),
    user_id: Optional[List[uuid.UUID]] = Query(None, description="Una, varias o ninguna = todas"),
    client_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    solo_facturables: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Las diez secciones, ya calculadas (H-D52). La plantilla no calcula nada."""
    return await _datos(db, desde, hasta, user_id, client_id, project_id, solo_facturables)
