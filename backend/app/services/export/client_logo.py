"""
N1.4 — Resolucion del logo del cliente para los informes exportados.

Vive en services/export porque sus unicos consumidores son los generadores de
reportes (N1.5 HTML integrado, N1.6 PDF, N1.7 HTML individual).

Los informes pintan `execution.client`, que es un campo de TEXTO legacy, no el
FK. Por eso la resolucion es en dos pasos: primero el FK (cubre las ejecuciones
modernas) y, si no hay, coincidencia por nombre como red de seguridad.
"""
import base64
import logging

from sqlalchemy import select, func

from app.db.models.client import Client
from app.db.models.client_logo import ClientLogo

logger = logging.getLogger(__name__)


async def get_client_logo_b64(db, execution) -> str | None:
    """Devuelve 'data:image/png;base64,...' del logo del cliente, o None.

    NUNCA lanza: si algo falla (DB, bytes corruptos, ejecucion sin atributos)
    devuelve None y lo deja en el log. Un logo roto no puede tumbar un export.
    """
    try:
        logo = None

        client_id = getattr(execution, "client_id", None)
        if client_id:
            result = await db.execute(
                select(ClientLogo).where(ClientLogo.client_id == client_id)
            )
            logo = result.scalar_one_or_none()

        if logo is None:
            # Sin FK (o cliente sin logo): probar por nombre, sin distinguir
            # mayusculas ni espacios sobrantes.
            name = (getattr(execution, "client", "") or "").strip()
            if name:
                result = await db.execute(
                    select(ClientLogo)
                    .join(Client, Client.id == ClientLogo.client_id)
                    .where(func.lower(func.trim(Client.name)) == name.lower())
                )
                logo = result.scalars().first()

        if logo is None or not logo.data:
            return None

        encoded = base64.b64encode(logo.data).decode()
        return f"data:{logo.mime_type or 'image/png'};base64,{encoded}"

    except Exception as e:
        logger.warning("No se pudo resolver el logo del cliente: %s", e)
        return None
