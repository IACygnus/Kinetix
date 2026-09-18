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
from app.services.horas.informe import (
    CLAVES, csv_detalle, documento_html, documento_pdf_html, nombre_archivo,
)
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


def _elegidas(secciones: Optional[List[str]], por_defecto: List[str]) -> List[str]:
    """Las secciones pedidas, filtradas contra las que existen.

    Una clave inventada se ignora en vez de reventar: el informe sigue saliendo,
    que es lo que quiere quien lo pidió.
    """
    if not secciones:
        return por_defecto
    validas = [s for s in secciones if s in CLAVES]
    return validas or por_defecto


@router.get("/html")
async def informe_html(
    desde: date = Query(...),
    hasta: date = Query(...),
    user_id: Optional[List[uuid.UUID]] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    solo_facturables: bool = Query(False),
    seccion: Optional[List[str]] = Query(None, description="Qué secciones entran (H-D53)"),
    descargar: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """El documento HTML, autocontenido e interactivo (H-D55).

    Sin `descargar` va `inline`, que es lo que necesita el `iframe` de la vista
    previa (H-D57): lo que se ve ahí es **este mismo documento**, no una maqueta
    aparte que acabaría mintiendo.
    """
    d = await _datos(db, desde, hasta, user_id, client_id, project_id, solo_facturables)
    html = documento_html(d, _elegidas(seccion, list(CLAVES)))
    disp = "attachment" if descargar else "inline"
    return Response(
        content=html, media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'{disp}; filename="{nombre_archivo(d, "html")}"'},
    )


@router.get("/pdf")
async def informe_pdf(
    desde: date = Query(...),
    hasta: date = Query(...),
    user_id: Optional[List[uuid.UUID]] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    solo_facturables: bool = Query(False),
    seccion: Optional[List[str]] = Query(None),
    descargar: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """El mismo documento, en PDF, **todo en vertical** (H-D69).

    Por defecto **sin el detalle de registros** (H-D58): trescientas filas en
    papel no se leen. Su casilla lo permite cuando hace falta.
    """
    d = await _datos(db, desde, hasta, user_id, client_id, project_id, solo_facturables)
    por_defecto = [c for c in CLAVES if c != "detalle"]
    html = documento_pdf_html(d, _elegidas(seccion, por_defecto))
    try:
        from weasyprint import HTML as WeasyHTML
        # Se renderiza y luego se escribe, en dos pasos, para poder contar las
        # páginas: la vista previa las necesita y preguntárselo al PDF ya escrito
        # no se puede, porque WeasyPrint guarda sus objetos comprimidos.
        doc = WeasyHTML(string=html).render()
        paginas = len(doc.pages)
        pdf = doc.write_pdf()
    except Exception:
        logger.exception("Informe de horas: fallo al render del PDF")
        raise HTTPException(500, "No se pudo generar el PDF del informe.")
    disp = "attachment" if descargar else "inline"
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'{disp}; filename="{nombre_archivo(d, "pdf")}"',
                 "X-Total-Paginas": str(paginas)},
    )


@router.get("/csv")
async def informe_csv(
    desde: date = Query(...),
    hasta: date = Query(...),
    user_id: Optional[List[uuid.UUID]] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    solo_facturables: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """El detalle de registros del filtro aplicado, para Excel (H-D59)."""
    d = await _datos(db, desde, hasta, user_id, client_id, project_id, solo_facturables)
    return Response(
        content=csv_detalle(d), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="{nombre_archivo(d, "csv")}"'},
    )
