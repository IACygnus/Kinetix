"""Importación de proyectos, estados y estimaciones (ETAPA H8.5b, H-D94 a H-D107).

    GET  /time/import/proyectos/plantilla   el .xlsx de ejemplo (H-D101)
    POST /time/import/proyectos/preview     analiza y NO escribe nada
    POST /time/import/proyectos/confirm     analiza otra vez y aplica, en una transacción

**Segundo importador. El de registros no se toca** (H-D94): este archivo es
nuevo y de aquel solo se reutiliza el lector, que ya está medido contra archivos
reales.

Por qué existe: hasta ahora los proyectos que creaba la importación de horas
**nacían sin estimaciones** (§6.2.4), así que el desfase no podía funcionar y la
sección 6 del informe se quedaba sin nada que decir. El orden de uso es
**borrar → cargar proyectos → cargar horas**, y este es el paso de en medio.

Las reglas, todas juntas:

| # | Regla |
|---|---|
| H-D96 | Una fila por actividad; el proyecto se crea una vez y se le añaden todas |
| H-D97 | Idempotente: reimportar **actualiza** las horas al valor del archivo, no suma |
| H-D98 | Cliente, proyecto y actividad que falten se crean, comparando normalizado |
| H-D100 | Fila inválida: fuera, con su número y su motivo; el resto entra |
| H-D107 | Los proyectos que no vengan en el archivo **no se tocan** |

Y la de §8 que no está en las decisiones pero manda igual: poner un proyecto en
`no_viable` o `finalizado` es de administrador (H-D90). Una fila que lo pida sin
serlo se descarta con su motivo, en vez de colarse por la puerta de atrás del
importador.
"""
import logging
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.models.client import Client
from app.db.models.time_tracking import (
    Activity, Project, ProjectActivity, ProjectActivityChange, ProjectStatusChange,
    normalizar,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.time_tracking import (
    ActividadNueva, FilaProyectoImportacion, ProyectoCreado, ProyectoImportado,
    ResumenProyectos, VistaPreviaProyectos, validar_paso,
)
# §4 (carga real): **la misma** tabla de sinónimos que usa la importación de
# registros. Las dos preguntan al mismo módulo; si cada una tuviera la suya,
# un archivo de proyectos y uno de horas podrían crear dos actividades
# distintas para el mismo texto y las estimaciones no casarían con el consumo.
from app.services.horas.sinonimos_actividad import traducir as traducir_actividad
from app.services.horas import estados
from app.services.horas.importacion import (
    ArchivoIlegible, FaltanColumnas, MAX_BYTES, filas_del_libro, hojas_del_libro,
    limpiar_texto,
)
from app.services.horas.importacion_proyectos import (
    estados_para_ayuda, leer_estado, leer_horas, mapear_columnas, plantilla_xlsx,
)

router = APIRouter()
logger = logging.getLogger(__name__)
CERO = Decimal("0")

CREA, ACTUALIZA, IGUAL, INVALIDA = "crea", "actualiza", "igual", "invalida"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ===================== EL PLAN =====================

class _Plan:
    """Todo lo que se sabe del archivo antes de tocar la base."""

    def __init__(self):
        self.hoja: str = ""
        self.hojas: List[str] = []
        self.filas: List[FilaProyectoImportacion] = []
        # (cliente_norm, proyecto_norm) -> bloque del proyecto
        self.proyectos: Dict[Tuple[str, str], ProyectoImportado] = {}
        self.clientes_nuevos: Dict[str, str] = {}
        self.actividades_nuevas: Dict[str, str] = {}
        # Lo ya resuelto contra la base.
        self.id_cliente: Dict[str, uuid.UUID] = {}
        self.id_actividad: Dict[str, uuid.UUID] = {}
        self.id_proyecto: Dict[Tuple[str, str], uuid.UUID] = {}
        self.estado_actual: Dict[Tuple[str, str], str] = {}
        # (proyecto, actividad) -> horas estimadas que ya hay.
        self.estimacion_actual: Dict[Tuple[str, str], Decimal] = {}
        # Para detectar la misma actividad dos veces en el archivo.
        self.vistas: Dict[Tuple[str, str, str], int] = {}


async def _analizar(db: AsyncSession, datos: bytes, actual: User) -> _Plan:
    """Lee el archivo y decide qué pasaría con cada fila. **No escribe nada.**"""
    hoja, titulos, filas = filas_del_libro(datos)
    plan = _Plan()
    plan.hoja = hoja
    plan.hojas = hojas_del_libro(datos)
    mapa = mapear_columnas(titulos)      # revienta antes de leer filas

    # ---------- 1. Lo que ya hay en la base ----------
    clientes = {normalizar(c.name): c for c in (await db.execute(select(Client))).scalars()}
    actividades = {normalizar(a.name): a for a in (await db.execute(select(Activity))).scalars()}
    plan.id_cliente = {k: c.id for k, c in clientes.items()}
    plan.id_actividad = {k: a.id for k, a in actividades.items()}

    for p in (await db.execute(select(Project))).scalars():
        cliente = next((c for c in clientes.values() if c.id == p.client_id), None)
        if cliente is None:
            continue
        clave = (normalizar(cliente.name), p.name_normalized)
        plan.id_proyecto[clave] = p.id
        plan.estado_actual[clave] = estados.normalizar_legado(p.status)

    for pa in (await db.execute(select(ProjectActivity))).scalars():
        plan.estimacion_actual[(str(pa.project_id), str(pa.activity_id))] = \
            Decimal(str(pa.estimated_hours))

    def valor(fila, clave):
        pos = mapa.get(clave)
        return fila[pos] if pos is not None and pos < len(fila) else None

    # ---------- 2. Fila a fila ----------
    for numero, fila in filas:
        f = FilaProyectoImportacion(numero=numero)
        f.client_name = limpiar_texto(valor(fila, "cliente"))
        f.project_name = limpiar_texto(valor(fila, "proyecto"))
        del_archivo = limpiar_texto(valor(fila, "actividad"))
        f.activity_name = traducir_actividad(del_archivo)
        if f.activity_name != del_archivo:
            f.activity_original = del_archivo

        faltan = [COL for COL, v in (("Cliente", f.client_name),
                                     ("Proyecto", f.project_name),
                                     ("Actividad", f.activity_name)) if not v]
        if faltan:
            f.accion = INVALIDA
            f.motivo = f"Falta {' y '.join(faltan)}"
            plan.filas.append(f)
            continue

        # Las horas (H-D100): número, mayor que cero y en pasos de 0,25.
        horas = leer_horas(valor(fila, "horas"))
        if horas is None:
            f.accion = INVALIDA
            f.motivo = "Las horas estimadas no se entienden"
            plan.filas.append(f)
            continue
        try:
            horas = validar_paso(horas, "Las horas estimadas")
        except ValueError as e:
            f.accion = INVALIDA
            f.motivo = str(e)
            plan.filas.append(f)
            continue
        f.estimated_hours = horas

        # El estado (H-D95, H-D100).
        estado = leer_estado(valor(fila, "estado"))
        if estado is None:
            f.accion = INVALIDA
            f.motivo = (f"«{limpiar_texto(valor(fila, 'estado'))}» no es un estado. "
                        f"Los que valen: {estados_para_ayuda()}")
            plan.filas.append(f)
            continue
        # §8 / H-D90: cerrar un proyecto es de administrador, también desde un
        # archivo. Si no, el importador sería la puerta de atrás del permiso.
        if estados.exige_admin(estado) and actual.role != "admin":
            f.accion = INVALIDA
            f.motivo = (f"Poner un proyecto en «{estados.texto(estado)}» es cosa del "
                        "administrador")
            plan.filas.append(f)
            continue
        f.status = estado
        f.status_label = estados.texto(estado)

        kc, kp, ka = (normalizar(f.client_name), normalizar(f.project_name),
                      normalizar(f.activity_name))
        clave_proyecto = (kc, kp)

        # La misma actividad dos veces en el mismo proyecto: la segunda fuera.
        # Dejarla pasar haría que el resultado dependiera del orden del archivo.
        repetida = plan.vistas.get((kc, kp, ka))
        if repetida:
            f.accion = INVALIDA
            f.motivo = (f"«{f.activity_name}» ya viene para este proyecto en la "
                        f"fila {repetida}")
            plan.filas.append(f)
            continue
        plan.vistas[(kc, kp, ka)] = numero

        # Qué habría que crear (H-D98).
        if kc not in plan.id_cliente:
            plan.clientes_nuevos.setdefault(kc, f.client_name)
            f.crea_cliente = True
        if ka not in plan.id_actividad:
            plan.actividades_nuevas.setdefault(ka, f.activity_name)
            f.crea_actividad = True

        pid = plan.id_proyecto.get(clave_proyecto)
        f.crea_proyecto = pid is None

        # Qué pasa con la estimación (H-D97).
        if pid is not None and not f.crea_actividad:
            aid = str(plan.id_actividad[ka])
            anterior = plan.estimacion_actual.get((str(pid), aid))
            if anterior is None:
                f.accion = CREA
            elif anterior == horas:
                f.accion = IGUAL
                f.previous_hours = anterior
            else:
                f.accion = ACTUALIZA
                f.previous_hours = anterior
        else:
            f.accion = CREA

        # El bloque del proyecto (H-D96, H-D99).
        bloque = plan.proyectos.get(clave_proyecto)
        if bloque is None:
            anterior = plan.estado_actual.get(clave_proyecto)
            bloque = plan.proyectos[clave_proyecto] = ProyectoImportado(
                client_name=f.client_name, project_name=f.project_name,
                status=estado, status_label=estados.texto(estado),
                es_nuevo=pid is None,
                cambia_de_estado=anterior is not None and anterior != estado,
                status_anterior_label=estados.texto(anterior) if anterior else "",
            )
        bloque.actividades += 1
        bloque.total_hours += horas
        bloque.filas.append(f)
        plan.filas.append(f)

    return plan


def _actividades_nuevas(plan: _Plan,
                        entran: List[FilaProyectoImportacion]) -> List[ActividadNueva]:
    """§4: las que el catálogo no tenía, con sus filas y sus horas ESTIMADAS.

    Mismo aviso que en la importación de registros y por lo mismo: entran igual,
    pero hay que verlas antes de confirmar por si lo que falta es un sinónimo.
    """
    bloques = {
        clave: ActividadNueva(name=nombre)
        for clave, nombre in plan.actividades_nuevas.items()
    }
    for f in entran:
        if not f.crea_actividad:
            continue
        bloque = bloques.get(normalizar(f.activity_name))
        if bloque is None:
            continue
        bloque.filas.append(f.numero)
        bloque.horas += (f.estimated_hours or CERO)
    return sorted(bloques.values(), key=lambda b: b.name.lower())


def _a_vista_previa(plan: _Plan) -> VistaPreviaProyectos:
    bloques = sorted(plan.proyectos.values(),
                     key=lambda b: (b.client_name.lower(), b.project_name.lower()))
    entran = [f for f in plan.filas if f.accion != INVALIDA]
    return VistaPreviaProyectos(
        sheet=plan.hoja, sheets=plan.hojas, total_filas=len(plan.filas),
        proyectos=bloques,
        invalidas=[f for f in plan.filas if f.accion == INVALIDA],
        proyectos_nuevos=sum(1 for b in bloques if b.es_nuevo),
        proyectos_actualizados=sum(1 for b in bloques if not b.es_nuevo),
        estimaciones_nuevas=sum(1 for f in entran if f.accion == CREA),
        estimaciones_actualizadas=sum(1 for f in entran if f.accion == ACTUALIZA),
        estimaciones_iguales=sum(1 for f in entran if f.accion == IGUAL),
        clientes_a_crear=sorted(plan.clientes_nuevos.values()),
        actividades_a_crear=sorted(plan.actividades_nuevas.values()),
        actividades_nuevas=_actividades_nuevas(plan, entran),
        total_horas=sum((f.estimated_hours or CERO for f in entran), CERO),
    )


async def _leer(archivo: UploadFile) -> bytes:
    datos = await archivo.read()
    if not datos:
        raise HTTPException(400, "El archivo está vacío")
    if len(datos) > MAX_BYTES:
        raise HTTPException(400, f"El archivo pesa más de {MAX_BYTES // (1024 * 1024)} MB")
    return datos


# ===================== LOS ENDPOINTS =====================

@router.get("/plantilla")
async def plantilla(current_user: User = Depends(get_current_active_user)):
    """El `.xlsx` de ejemplo (H-D101): cinco columnas y dos filas del MISMO
    proyecto, que es la forma de enseñar que una fila es una actividad."""
    return Response(
        content=plantilla_xlsx(), media_type=XLSX,
        headers={"Content-Disposition":
                 'attachment; filename="plantilla-proyectos-y-estimaciones.xlsx"'})


@router.post("/preview", response_model=VistaPreviaProyectos)
async def vista_previa(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Qué pasaría si se confirmara. **No escribe nada** (H-D99)."""
    datos = await _leer(archivo)
    try:
        plan = await _analizar(db, datos, current_user)
    except (FaltanColumnas, ArchivoIlegible) as e:
        raise HTTPException(400, str(e))
    return _a_vista_previa(plan)


@router.post("/confirm", response_model=ResumenProyectos)
async def confirmar(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Aplica el archivo. **Todo en una transacción** (H-D99).

    Se vuelve a analizar en vez de fiarse de lo que la pantalla enseñó: entre la
    previa y la confirmación la base pudo cambiar, y lo que se escribe tiene que
    decidirse con lo que hay ahora.
    """
    datos = await _leer(archivo)
    try:
        plan = await _analizar(db, datos, current_user)
    except (FaltanColumnas, ArchivoIlegible) as e:
        raise HTTPException(400, str(e))

    creados: List[ProyectoCreado] = []
    clientes_creados: List[str] = []
    actividades_creadas: List[str] = []
    nuevas = actualizadas = iguales = estados_cambiados = 0
    proyectos_tocados = 0

    try:
        # ---------- 1. Clientes y actividades que faltan (H-D98) ----------
        for clave, nombre in plan.clientes_nuevos.items():
            c = Client(name=nombre, is_active=True)
            db.add(c)
            await db.flush()
            plan.id_cliente[clave] = c.id
            clientes_creados.append(nombre)

        for clave, nombre in plan.actividades_nuevas.items():
            a = Activity(id=uuid.uuid4(), name=nombre, name_normalized=clave,
                         is_active=True, created_by=current_user.id)
            db.add(a)
            await db.flush()
            plan.id_actividad[clave] = a.id
            actividades_creadas.append(nombre)

        # ---------- 2. Los proyectos ----------
        for clave, bloque in plan.proyectos.items():
            kc, kp = clave
            pid = plan.id_proyecto.get(clave)
            if pid is None:
                p = Project(id=uuid.uuid4(), client_id=plan.id_cliente[kc],
                            name=bloque.project_name, name_normalized=kp,
                            status=bloque.status, created_by=current_user.id)
                db.add(p)
                await db.flush()
                pid = plan.id_proyecto[clave] = p.id
                # El estado con el que nace también deja rastro: así el historial
                # de un proyecto importado empieza donde empieza el proyecto.
                db.add(ProjectStatusChange(
                    id=uuid.uuid4(), project_id=pid, previous_status=None,
                    new_status=bloque.status, changed_by=current_user.id))
                creados.append(ProyectoCreado(id=pid, name=bloque.project_name,
                                              client_name=bloque.client_name))
            else:
                proyectos_tocados += 1
                if bloque.cambia_de_estado:
                    proyecto = await db.get(Project, pid)
                    anterior = estados.normalizar_legado(proyecto.status)
                    proyecto.status = bloque.status
                    db.add(ProjectStatusChange(
                        id=uuid.uuid4(), project_id=pid, previous_status=anterior,
                        new_status=bloque.status, changed_by=current_user.id))
                    estados_cambiados += 1

            # ---------- 3. Sus estimaciones (H-D96, H-D97) ----------
            for f in bloque.filas:
                aid = plan.id_actividad[normalizar(f.activity_name)]
                fila = (await db.execute(
                    select(ProjectActivity).where(ProjectActivity.project_id == pid,
                                                  ProjectActivity.activity_id == aid)
                )).scalar_one_or_none()
                if fila is None:
                    db.add(ProjectActivity(id=uuid.uuid4(), project_id=pid,
                                           activity_id=aid,
                                           estimated_hours=f.estimated_hours))
                    db.add(ProjectActivityChange(
                        id=uuid.uuid4(), project_id=pid, activity_id=aid,
                        previous_hours=None, new_hours=f.estimated_hours,
                        change_type="alta", changed_by=current_user.id))
                    nuevas += 1
                else:
                    anterior = Decimal(str(fila.estimated_hours))
                    if anterior == f.estimated_hours:
                        # H-D97: reimportar el mismo archivo no cambia nada. Y no
                        # se escribe historial: una fila que dice «de 10 a 10» es
                        # ruido, no rastro (mismo criterio que H-D11).
                        iguales += 1
                        continue
                    fila.estimated_hours = f.estimated_hours
                    db.add(ProjectActivityChange(
                        id=uuid.uuid4(), project_id=pid, activity_id=aid,
                        previous_hours=anterior, new_hours=f.estimated_hours,
                        change_type="cambio", changed_by=current_user.id))
                    actualizadas += 1

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    omitidas = sum(1 for f in plan.filas if f.accion == INVALIDA)
    logger.info(
        "Horas: importados %s proyectos nuevos y %s existentes (%s estimaciones "
        "nuevas, %s actualizadas, %s iguales, %s filas fuera) por %s",
        len(creados), proyectos_tocados, nuevas, actualizadas, iguales, omitidas,
        current_user.username)

    return ResumenProyectos(
        proyectos_creados=creados, proyectos_actualizados=proyectos_tocados,
        estimaciones_creadas=nuevas, estimaciones_actualizadas=actualizadas,
        estimaciones_iguales=iguales, estados_cambiados=estados_cambiados,
        clientes_creados=sorted(clientes_creados),
        actividades_creadas=sorted(actividades_creadas),
        actividades_nuevas=_actividades_nuevas(
            plan, [f for f in plan.filas if f.accion != INVALIDA]),
        omitidas=omitidas,
        total_horas=sum((f.estimated_hours or CERO
                         for f in plan.filas if f.accion != INVALIDA), CERO),
    )
