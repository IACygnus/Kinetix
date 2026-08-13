"""
Endpoints CRUD de Clientes y asignaciones Usuario-Cliente - Admin only - v2.1
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
import io
import uuid
import logging

from app.db.session import get_db
from app.db.models.client import Client, UserClient
from app.db.models.client_logo import ClientLogo
from app.db.models.user import User
from app.core.security import require_role, get_current_active_user
from app.schemas.client import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    UserClientAssign,
    UserClientResponse,
    UserWithClients,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ===================== CLIENTS CRUD =====================

@router.get("", response_model=List[ClientResponse])
async def list_clients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Listar todos los clientes - Cualquier usuario autenticado"""
    result = await db.execute(
        select(Client).order_by(Client.name)
    )
    return await _with_logo_flag(db, result.scalars().all())


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Crear nuevo cliente - Solo admin"""
    # Verificar nombre unico
    result = await db.execute(
        select(Client).where(Client.name == data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe un cliente con ese nombre")

    client = Client(
        id=uuid.uuid4(),
        name=data.name,
        description=data.description,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)

    logger.info(f"Cliente creado: {client.name} por {current_user.username}")
    return client


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Editar cliente - Solo admin"""
    try:
        cid = uuid.UUID(client_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID de cliente invalido")

    result = await db.execute(select(Client).where(Client.id == cid))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Verificar nombre unico si cambia
    if data.name is not None and data.name != client.name:
        existing = await db.execute(
            select(Client).where(Client.name == data.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Ya existe un cliente con ese nombre")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)

    logger.info(f"Cliente actualizado: {client.name} por {current_user.username}")
    (await _with_logo_flag(db, [client]))   # N1.2: no perder has_logo al editar
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Eliminar cliente - Solo admin"""
    try:
        cid = uuid.UUID(client_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID de cliente invalido")

    result = await db.execute(select(Client).where(Client.id == cid))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    await db.delete(client)
    await db.flush()

    logger.info(f"Cliente eliminado: {client.name} por {current_user.username}")


# ===================== USER-CLIENT ASSIGNMENTS =====================

@router.get("/assignments", response_model=List[UserWithClients])
async def list_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Listar usuarios con sus clientes asignados - Solo admin"""
    users_result = await db.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    )
    users = users_result.scalars().all()

    result = []
    for user in users:
        uc_result = await db.execute(
            select(Client).join(UserClient, UserClient.client_id == Client.id).where(
                UserClient.user_id == user.id
            ).order_by(Client.name)
        )
        clients = uc_result.scalars().all()
        result.append(UserWithClients(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            clients=[ClientResponse.model_validate(c) for c in clients],
        ))

    return result


@router.post("/assignments", response_model=UserClientResponse, status_code=status.HTTP_201_CREATED)
async def assign_client_to_user(
    data: UserClientAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Asignar cliente a usuario - Solo admin"""
    # Verificar que existen
    user_result = await db.execute(select(User).where(User.id == data.user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    client_result = await db.execute(select(Client).where(Client.id == data.client_id))
    if not client_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Verificar duplicado
    existing = await db.execute(
        select(UserClient).where(
            UserClient.user_id == data.user_id,
            UserClient.client_id == data.client_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="El usuario ya tiene asignado este cliente")

    assignment = UserClient(
        id=uuid.uuid4(),
        user_id=data.user_id,
        client_id=data.client_id,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)

    logger.info(f"Asignacion creada: user={data.user_id} client={data.client_id} por {current_user.username}")
    return assignment


@router.delete("/assignments/{user_id}/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_client_from_user(
    user_id: str,
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Remover asignacion de cliente a usuario - Solo admin"""
    try:
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(client_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID invalido")

    result = await db.execute(
        select(UserClient).where(
            UserClient.user_id == uid,
            UserClient.client_id == cid,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")

    await db.delete(assignment)
    await db.flush()

    logger.info(f"Asignacion eliminada: user={user_id} client={client_id} por {current_user.username}")


@router.get("/user-clients", response_model=List[ClientResponse])
async def get_my_clients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Obtener clientes asignados al usuario actual"""
    # Admin ve todos los clientes
    if current_user.role == "admin":
        result = await db.execute(
            select(Client).where(Client.is_active == True).order_by(Client.name)
        )
        return result.scalars().all()

    # Otros roles solo ven clientes asignados
    result = await db.execute(
        select(Client).join(UserClient, UserClient.client_id == Client.id).where(
            UserClient.user_id == current_user.id,
            Client.is_active == True,
        ).order_by(Client.name)
    )
    clients = result.scalars().all()
    return await _with_logo_flag(db, clients)


# ===================== CLIENT LOGO (N1.2) =====================

LOGO_ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
LOGO_MAX_UPLOAD = 2 * 1024 * 1024      # 2 MB de subida
LOGO_MAX_SIZE = (400, 160)             # ancho x alto maximos tras normalizar


async def _with_logo_flag(db: AsyncSession, clients):
    """Marca has_logo en cada cliente con UNA consulta y SIN traer los bytes.

    Se consulta solo la columna client_id; `data` (BYTEA) nunca entra en memoria.
    El atributo es transitorio: no es una columna, no se persiste.
    """
    if not clients:
        return clients
    result = await db.execute(select(ClientLogo.client_id))
    with_logo = set(result.scalars().all())
    for c in clients:
        c.has_logo = c.id in with_logo
    return clients


@router.post("/{client_id}/logo")
async def upload_client_logo(
    client_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Sube o reemplaza el logo del cliente - Solo admin."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    if file.content_type not in LOGO_ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: {file.content_type}. Permitidos: PNG, JPG, WebP",
        )

    content = await file.read()
    if len(content) > LOGO_MAX_UPLOAD:
        raise HTTPException(
            status_code=413,
            detail=f"El logo excede el limite de {LOGO_MAX_UPLOAD // (1024 * 1024)}MB",
        )

    # Normalizacion: PNG con transparencia, reducido a LOGO_MAX_SIZE. `thumbnail`
    # respeta la proporcion y NUNCA agranda una imagen mas chica.
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        img.load()                       # una imagen corrupta revienta aca, antes de escribir
        img = img.convert("RGBA")        # conserva/agrega canal alfa
        img.thumbnail(LOGO_MAX_SIZE, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
    except Exception as e:
        logger.warning(f"Logo invalido para cliente {client_id}: {e}")
        raise HTTPException(status_code=400, detail="La imagen no se pudo procesar. Suba un PNG, JPG o WebP valido.")

    result = await db.execute(select(ClientLogo).where(ClientLogo.client_id == client_id))
    logo = result.scalar_one_or_none()
    if logo:
        logo.data = data
        logo.mime_type = "image/png"
        logo.file_size = len(data)
    else:
        db.add(ClientLogo(
            id=uuid.uuid4(), client_id=client_id, data=data,
            mime_type="image/png", file_size=len(data),
        ))
    await db.flush()

    logger.info(f"Logo de '{client.name}' actualizado por {current_user.username} ({len(data)} bytes)")
    return {
        "client_id": str(client_id), "mime_type": "image/png",
        "file_size": len(data), "width": img.width, "height": img.height,
    }


@router.get("/{client_id}/logo")
async def get_client_logo(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Devuelve la imagen del logo - Cualquier usuario autenticado."""
    result = await db.execute(select(ClientLogo).where(ClientLogo.client_id == client_id))
    logo = result.scalar_one_or_none()
    if not logo:
        raise HTTPException(status_code=404, detail="Este cliente no tiene logo")
    return Response(content=logo.data, media_type=logo.mime_type,
                    headers={"Cache-Control": "no-cache"})


@router.delete("/{client_id}/logo")
async def delete_client_logo(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Quita el logo del cliente - Solo admin."""
    result = await db.execute(select(ClientLogo).where(ClientLogo.client_id == client_id))
    logo = result.scalar_one_or_none()
    if not logo:
        raise HTTPException(status_code=404, detail="Este cliente no tiene logo")
    await db.delete(logo)
    await db.flush()
    logger.info(f"Logo del cliente {client_id} eliminado por {current_user.username}")
    return {"deleted": True}
