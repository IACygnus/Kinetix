"""Los datos del informe de horas (ETAPA H5.2, especificación v1.2 §7).

**Una sola pasada por la base y una sola fuente por cifra.** Las diez secciones
salen de aquí ya calculadas; la plantilla —HTML o PDF— pinta y no suma nada.

Dos decisiones que sostienen todo lo demás:

1. **Se reutilizan las definiciones que ya existen.** La jornada y el día
   incompleto salen de `calendario.py`; el estado de desfase, de `desfase.py`. Si
   el informe las volviera a escribir, acabaría diciendo que un día está completo
   mientras el calendario lo pinta en ámbar, y nadie sabría cuál de los dos
   miente.

2. **Un solo endpoint, no seis.** Seis llamadas desde la pantalla darían seis
   momentos distintos de la base: el resumen de las 10:00 y el detalle de las
   10:01 no cuadran, y cuadrar es justo lo que se le pide a un informe.

El filtro de `solo_facturables` **no se aplica a la jornada esperada**: lo que a
una persona le tocaba trabajar no depende de qué se le cobra a quién.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.client import Client
from app.db.models.time_tracking import (
    Activity, Holiday, Project, ProjectActivity, TimeEntry, WorkCalendar,
)
from app.db.models.user import User
from app.schemas.time_tracking import (
    ConsultaProyecto, InformeCapacidad, InformeDatos, InformeFacturacion,
    InformeFilaDiaria, InformeFiltros, InformeMapaPersona, InformePendiente,
    InformePersona, InformeReparto, InformeResumen,
)
from app.services.horas.calendario import construir_dias, dias_del_rango
from app.services.horas.desfase import (
    estado as estado_desfase, etiqueta as etiqueta_desfase, horas_de_desfase,
    porcentaje as porcentaje_consumido,
)

CERO = Decimal("0")

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _dec(v) -> Decimal:
    return Decimal(str(v or 0))


def _pct(parte: Decimal, total: Decimal) -> Decimal:
    """Un porcentaje que nunca divide por cero."""
    return (parte / total * 100) if total > 0 else CERO


def describir_periodo(desde: date, hasta: date) -> str:
    """El periodo, en español y como lo diría una persona.

    Un mes entero se llama por su nombre; un rango cualquiera se dice con sus dos
    extremos. Es lo que va en el encabezado y en el nombre del archivo (H-D61).
    """
    ultimo_del_mes = (date(desde.year + 1, 1, 1) if desde.month == 12
                      else date(desde.year, desde.month + 1, 1)).toordinal() - 1
    if desde.day == 1 and hasta.toordinal() == ultimo_del_mes and desde.month == hasta.month:
        return f"{MESES[desde.month - 1]} de {desde.year}"
    if desde == hasta:
        return f"{desde.day} de {MESES[desde.month - 1]} de {desde.year}"
    if desde.month == hasta.month and desde.year == hasta.year:
        return f"del {desde.day} al {hasta.day} de {MESES[desde.month - 1]} de {desde.year}"
    return (f"del {desde.day} de {MESES[desde.month - 1]} "
            f"al {hasta.day} de {MESES[hasta.month - 1]} de {hasta.year}")


async def construir_informe(
    db: AsyncSession,
    desde: date,
    hasta: date,
    user_ids: Optional[Sequence[uuid.UUID]] = None,
    client_id: Optional[uuid.UUID] = None,
    project_id: Optional[uuid.UUID] = None,
    solo_facturables: bool = False,
    dirigido_a: str = "",
    tope_detalle: int = 5000,
) -> InformeDatos:
    """Las diez secciones de §7.2, en una sola pasada."""
    dias = dias_del_rango(desde, hasta)

    # ---------- 1. Los registros del periodo, con sus filtros ----------
    q = (select(TimeEntry, Project, Client, Activity, User)
         .join(Project, Project.id == TimeEntry.project_id)
         .join(Client, Client.id == Project.client_id)
         .join(Activity, Activity.id == TimeEntry.activity_id)
         .join(User, User.id == TimeEntry.user_id)
         .where(TimeEntry.date >= desde, TimeEntry.date <= hasta))
    if user_ids:
        q = q.where(TimeEntry.user_id.in_(list(user_ids)))
    if client_id:
        q = q.where(Project.client_id == client_id)
    if project_id:
        q = q.where(TimeEntry.project_id == project_id)
    if solo_facturables:
        q = q.where(TimeEntry.billable.is_(True))

    filas = (await db.execute(q.order_by(TimeEntry.date, User.username))).all()

    # ---------- 2. Quién entra en el informe ----------
    # Si se pidieron personas, salen TODAS las pedidas aunque no tengan horas: un
    # informe de ocupación tiene que poder enseñar a quien no registró nada.
    if user_ids:
        usuarios = {
            u.id: u for u in (await db.execute(
                select(User).where(User.id.in_(list(user_ids)))
            )).scalars().all()
        }
    else:
        usuarios = {u.id: u for _, _, _, _, u in filas}
    for _, _, _, _, u in filas:
        usuarios.setdefault(u.id, u)

    def nombre(u: User) -> str:
        return u.full_name or u.username

    # ---------- 3. La jornada esperada, de `calendario.py` ----------
    calendario = {
        f.weekday: _dec(f.expected_hours)
        for f in (await db.execute(select(WorkCalendar))).scalars().all()
    }
    festivos = (await db.execute(
        select(Holiday).where(Holiday.date >= desde, Holiday.date <= hasta)
    )).scalars().all()
    hoy = date.today()

    # ---------- 3b. La capacidad base del periodo (H-D75) ----------
    # Solo festivos NACIONALES: la capacidad base es la que ofrece el calendario,
    # no la que queda despues de las vacaciones de cada cual. Y es del periodo
    # ENTERO, no «hasta hoy»: responde a cuanto cabe en estas fechas.
    nacionales = {f.date: (f.name, False) for f in festivos if f.user_id is None}
    dias_base = construir_dias(desde, hasta, calendario, {}, nacionales)
    habiles = [d for d in dias_base if d.se_reclaman > 0]
    horas_analista = sum((d.se_reclaman for d in habiles), CERO)

    # ---------- 4. Acumuladores ----------
    por_persona: Dict[uuid.UUID, Dict[str, Decimal]] = {}
    por_persona_dia: Dict[uuid.UUID, Dict[date, Dict[str, Decimal]]] = {}
    por_cliente: Dict[str, Decimal] = {}
    por_actividad: Dict[str, Decimal] = {}
    facturacion: Dict[str, Dict[str, Decimal]] = {}
    lineas_diarias: Dict[Tuple[str, str, str], Dict[date, Decimal]] = {}
    total = ordinarias = extra = facturables = CERO
    proyectos_vistos = set()

    for r, p, c, a, u in filas:
        h = _dec(r.hours)
        total += h
        if r.overtime:
            extra += h
        else:
            ordinarias += h
        if r.billable:
            facturables += h
        proyectos_vistos.add(p.id)

        acc = por_persona.setdefault(u.id, {"total": CERO, "ord": CERO, "extra": CERO,
                                            "fact": CERO})
        acc["total"] += h
        acc["extra" if r.overtime else "ord"] += h
        if r.billable:
            acc["fact"] += h

        dia_acc = por_persona_dia.setdefault(u.id, {}).setdefault(
            r.date, {"ordinarias": CERO, "extra": CERO})
        dia_acc["extra" if r.overtime else "ordinarias"] += h

        por_cliente[c.name] = por_cliente.get(c.name, CERO) + h
        por_actividad[a.name] = por_actividad.get(a.name, CERO) + h

        fac = facturacion.setdefault(c.name, {"si": CERO, "no": CERO})
        fac["si" if r.billable else "no"] += h

        clave = (c.name, p.name, a.name)
        lineas_diarias.setdefault(clave, {})
        lineas_diarias[clave][r.date] = lineas_diarias[clave].get(r.date, CERO) + h

    # ---------- 5. Secciones 2, 7 y 8: lo que necesita el calendario ----------
    personas: List[InformePersona] = []
    mapa: List[InformeMapaPersona] = []
    pendientes: List[InformePendiente] = []
    esperadas_totales = CERO
    pendientes_totales = 0

    for uid, u in sorted(usuarios.items(), key=lambda kv: nombre(kv[1]).lower()):
        # Mismo criterio que `_no_laborables` de H2, y a propósito: una ausencia
        # propia pesa más que un festivo nacional, y lo que marca «ausencia» es
        # tener `user_id`, no la columna `kind`. Dos reglas distintas aquí harían
        # que el informe y el calendario pintaran días distintos.
        no_laborables: Dict[date, tuple] = {}
        for f in festivos:
            if f.user_id is not None and str(f.user_id) != str(uid):
                continue
            if f.date not in no_laborables or f.user_id is not None:
                no_laborables[f.date] = (f.name, f.user_id is not None)
        resueltos = construir_dias(desde, hasta, calendario,
                                   por_persona_dia.get(uid, {}), no_laborables, hoy=hoy)
        # **La jornada esperada llega hasta hoy, no hasta el final del periodo.**
        # `dias_pendientes` ya trabajaba así desde H2b, y contar los días que aún
        # no han llegado haría que el informe del mes en curso enseñara una
        # ocupación del 2 % el día 2 — y que la ocupación y los días pendientes
        # se midieran con reglas distintas, que es peor todavía.
        esperadas = sum((d.se_reclaman for d in resueltos if not d.futuro), CERO)
        esperadas_totales += esperadas

        acc = por_persona.get(uid, {"total": CERO, "ord": CERO, "extra": CERO, "fact": CERO})
        sin_registrar = [d for d in resueltos if d.incompleto]
        pendientes_totales += len(sin_registrar)

        personas.append(InformePersona(
            user_id=uid, user_name=nombre(u),
            expected_hours=esperadas, total_hours=acc["total"],
            ordinary_hours=acc["ord"], overtime_hours=acc["extra"],
            billable_hours=acc["fact"],
            occupancy_pct=_pct(acc["ord"], esperadas),
            pending_days=len(sin_registrar),
        ))

        mapa.append(InformeMapaPersona(
            user_id=uid, user_name=nombre(u),
            por_dia=[d.total for d in resueltos],
            estados=[_estado_casilla(d) for d in resueltos],
            total_hours=sum((d.total for d in resueltos), CERO),
        ))

        for d in sin_registrar:
            pendientes.append(InformePendiente(
                user_name=nombre(u), date=d.fecha,
                expected_hours=d.se_reclaman, ordinary_hours=d.ordinarias,
                missing_hours=d.faltan,
            ))

    pendientes.sort(key=lambda x: (x.date, x.user_name))

    # ---------- 6. Sección 6: consumido frente a estimado ----------
    proyectos: List[ConsultaProyecto] = []
    if proyectos_vistos:
        estimado = {
            r[0]: _dec(r[1]) for r in (await db.execute(
                select(ProjectActivity.project_id,
                       func.coalesce(func.sum(ProjectActivity.estimated_hours), 0))
                .where(ProjectActivity.project_id.in_(proyectos_vistos))
                .group_by(ProjectActivity.project_id)
            )).all()
        }
        # Lo consumido de SIEMPRE, no lo del rango: es contra lo que se mide el
        # desfase, igual que en la consulta de §5.
        consumido = {
            r[0]: _dec(r[1]) for r in (await db.execute(
                select(TimeEntry.project_id, func.coalesce(func.sum(TimeEntry.hours), 0))
                .where(TimeEntry.project_id.in_(proyectos_vistos))
                .group_by(TimeEntry.project_id)
            )).all()
        }
        en_rango: Dict[uuid.UUID, Dict[str, Decimal]] = {}
        datos_proyecto: Dict[uuid.UUID, Tuple[Project, Client]] = {}
        for r, p, c, _a, _u in filas:
            datos_proyecto[p.id] = (p, c)
            acc = en_rango.setdefault(p.id, {"h": CERO, "extra": CERO, "n": CERO})
            acc["h"] += _dec(r.hours)
            if r.overtime:
                acc["extra"] += _dec(r.hours)
            acc["n"] += 1

        for pid, (p, c) in datos_proyecto.items():
            est, con = estimado.get(pid, CERO), consumido.get(pid, CERO)
            acc = en_rango[pid]
            proyectos.append(ConsultaProyecto(
                project_id=pid, project_name=p.name,
                client_id=p.client_id, client_name=c.name, status=p.status,
                estimated_hours=est, consumed_hours=con, remaining_hours=est - con,
                consumed_pct=porcentaje_consumido(con, est),
                overrun_status=estado_desfase(con, est, p.status == "cerrado"),
                overrun_hours=horas_de_desfase(con, est),
                overrun_label=etiqueta_desfase(con, est, p.status == "cerrado"),
                hours_in_range=acc["h"], overtime_in_range=acc["extra"],
                entries_in_range=int(acc["n"]), people=[],
            ))
        orden = {"desfasado": 0, "por_agotarse": 1, "en_rango": 2}
        proyectos.sort(key=lambda b: (orden.get(b.overrun_status, 3),
                                      b.client_name, b.project_name))

    # ---------- 7. Secciones 3, 4, 5 y 9 ----------
    facturacion_lista = sorted(
        (InformeFacturacion(
            client_name=nombre_cliente, billable_hours=v["si"], non_billable_hours=v["no"],
            total_hours=v["si"] + v["no"], billable_pct=_pct(v["si"], v["si"] + v["no"]),
        ) for nombre_cliente, v in facturacion.items()),
        key=lambda x: -x.total_hours)

    reparto_cliente = sorted(
        (InformeReparto(name=k, hours=v, pct=_pct(v, total)) for k, v in por_cliente.items()),
        key=lambda x: -x.hours)
    reparto_actividad = sorted(
        (InformeReparto(name=k, hours=v, pct=_pct(v, total)) for k, v in por_actividad.items()),
        key=lambda x: -x.hours)

    diarias = sorted(
        (InformeFilaDiaria(
            client_name=cl, project_name=pr, activity_name=ac,
            por_dia=[celdas.get(d, CERO) for d in dias],
            total_hours=sum(celdas.values(), CERO),
        ) for (cl, pr, ac), celdas in lineas_diarias.items()),
        key=lambda x: (x.client_name, x.project_name, x.activity_name))

    # ---------- 8. Sección 10: el detalle ----------
    from app.api.v1.endpoints.time_entries import _responder   # noqa: E402  (evita ciclo)
    registros = [r for r, _p, _c, _a, _u in filas]
    detalle = await _responder(db, registros[:tope_detalle])

    return InformeDatos(
        filtros=InformeFiltros(
            desde=desde, hasta=hasta, periodo=describir_periodo(desde, hasta),
            personas=[p.user_name for p in personas],
            alcance=(personas[0].user_name if len(personas) == 1 else "Equipo"),
            solo_facturables=solo_facturables,
            dirigido_a=dirigido_a,
        ),
        dias=dias,
        capacidad=InformeCapacidad(
            working_days=len(habiles),
            hours_per_analyst=horas_analista,
            people_count=len(personas),
            total_hours=horas_analista * len(personas),
        ),
        resumen=InformeResumen(
            total_hours=total, ordinary_hours=ordinarias, overtime_hours=extra,
            billable_hours=facturables, billable_pct=_pct(facturables, total),
            pending_days=pendientes_totales,
            expected_hours=esperadas_totales,
            people_count=len(personas), projects_count=len(proyectos),
            entries_count=len(registros),
        ),
        personas=personas,
        facturacion=facturacion_lista,
        por_cliente=reparto_cliente,
        por_actividad=reparto_actividad,
        proyectos=proyectos,
        mapa=mapa,
        pendientes=pendientes,
        diarias=diarias,
        detalle=detalle,
        detalle_total=len(registros),
        generado=datetime.now(),
    )


def _estado_casilla(d) -> str:
    """El estado de una casilla del mapa (sección 7), con el mismo orden que el
    calendario de §4.1: primero lo que no se reclama."""
    if d.es_festivo:
        return "festivo"
    if d.es_ausencia:
        return "ausencia"
    if d.esperadas <= 0:
        return "finde"
    # `incompleto` va ANTES que `trabajado`: un día con 4 de 8,5 tiene horas y
    # aun así hay que verlo en ámbar, que es de lo que sirve el mapa.
    if d.incompleto:
        return "incompleto"
    if d.total > 0:
        return "trabajado"
    return "vacio"
