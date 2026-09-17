"""Siembra del MÓDULO DE HORAS (ETAPA H1.2).

Tres cosas que el módulo necesita para arrancar y que no las pone el usuario:

  1. Las cinco actividades iniciales (§1.2, H-D3).
  2. La jornada: lunes a jueves 8,5 y viernes 8,0 (H-D5).
  3. Los festivos de Colombia de 2026 y 2027 (H-D5).

**Idempotente por construcción**: cada siembra comprueba antes de insertar, así
que correrla dos veces no duplica nada. Sigue el molde de `seed_admin_user`
(`main.py:203`), incluida la parte de capturar la excepción: un fallo de siembra
no puede tumbar el arranque del backend.

Los festivos van en una **lista literal por fecha**, no calculados. Es decisión de
Fredy y la razón es buena: un algoritmo de Ley Emiliani se equivoca en silencio y
nadie lo nota hasta que alguien reclama un día; una lista se revisa de un vistazo
y se amplía a mano.
"""
import logging
from datetime import date

from sqlalchemy import select

from app.db.models.time_tracking import (
    Activity, Holiday, WorkCalendar, normalizar,
)

logger = logging.getLogger(__name__)

# §1.2 — el catálogo arranca con estas cinco.
ACTIVIDADES_INICIALES = [
    "Planeación",
    "Diseño y generación de script",
    "Ejecución",
    "Análisis de resultados",
    "Administrativas o gerenciales",
]

# H-D5 — 0 = lunes … 6 = domingo (mismo criterio que `date.weekday()`).
JORNADA = {0: 8.5, 1: 8.5, 2: 8.5, 3: 8.5, 4: 8.0, 5: 0.0, 6: 0.0}

# H-D5 — Festivos de Colombia, por fecha literal. Revisables y ampliables a mano.
FESTIVOS_COLOMBIA = {
    2026: [
        ("2026-01-01", "Año Nuevo"),
        ("2026-01-12", "Día de los Reyes Magos"),
        ("2026-03-23", "Día de San José"),
        ("2026-03-29", "Domingo de Ramos"),
        ("2026-04-02", "Jueves Santo"),
        ("2026-04-03", "Viernes Santo"),
        ("2026-04-05", "Domingo de Resurrección"),
        ("2026-05-01", "Día del Trabajo"),
        ("2026-05-18", "Ascensión del Señor"),
        ("2026-06-08", "Corpus Christi"),
        ("2026-06-15", "Sagrado Corazón de Jesús"),
        ("2026-06-29", "San Pedro y San Pablo"),
        ("2026-07-20", "Día de la Independencia"),
        ("2026-08-07", "Batalla de Boyacá"),
        ("2026-08-17", "La Asunción de la Virgen"),
        ("2026-10-12", "Día de la Raza"),
        ("2026-11-02", "Todos los Santos"),
        ("2026-11-16", "Independencia de Cartagena"),
        ("2026-12-08", "Día de la Inmaculada Concepción"),
        ("2026-12-25", "Navidad"),
    ],
    2027: [
        ("2027-01-01", "Año Nuevo"),
        ("2027-01-11", "Día de los Reyes Magos"),
        ("2027-03-22", "Día de San José"),
        ("2027-03-21", "Domingo de Ramos"),
        ("2027-03-25", "Jueves Santo"),
        ("2027-03-26", "Viernes Santo"),
        ("2027-03-28", "Domingo de Resurrección"),
        ("2027-05-01", "Día del Trabajo"),
        ("2027-05-10", "Ascensión del Señor"),
        ("2027-05-31", "Corpus Christi"),
        ("2027-06-07", "Sagrado Corazón de Jesús"),
        ("2027-07-05", "San Pedro y San Pablo"),
        ("2027-07-20", "Día de la Independencia"),
        ("2027-08-07", "Batalla de Boyacá"),
        ("2027-08-16", "La Asunción de la Virgen"),
        ("2027-10-18", "Día de la Raza"),
        ("2027-11-01", "Todos los Santos"),
        ("2027-11-15", "Independencia de Cartagena"),
        ("2027-12-08", "Día de la Inmaculada Concepción"),
        ("2027-12-25", "Navidad"),
    ],
}


async def _sembrar_actividades(session) -> int:
    """Las cinco iniciales. Se comparan por nombre NORMALIZADO (H-D3)."""
    existentes = {
        a.name_normalized
        for a in (await session.execute(select(Activity))).scalars().all()
    }
    nuevas = 0
    for nombre in ACTIVIDADES_INICIALES:
        clave = normalizar(nombre)
        if clave in existentes:
            continue
        session.add(Activity(name=nombre, name_normalized=clave, is_active=True))
        existentes.add(clave)
        nuevas += 1
    return nuevas


async def _sembrar_jornada(session) -> int:
    """La jornada por día de la semana. Solo inserta los días que falten: si
    alguien cambió las horas de un día a mano, la siembra NO se las pisa."""
    existentes = {
        c.weekday
        for c in (await session.execute(select(WorkCalendar))).scalars().all()
    }
    nuevas = 0
    for dia, horas in JORNADA.items():
        if dia in existentes:
            continue
        session.add(WorkCalendar(weekday=dia, expected_hours=horas))
        nuevas += 1
    return nuevas


async def _sembrar_festivos(session) -> int:
    """Los festivos nacionales de los años de la lista.

    Solo los nacionales (`user_id` nulo). Las ausencias por persona las crea el
    usuario, y esta función no las toca nunca.
    """
    existentes = {
        h.date
        for h in (await session.execute(
            select(Holiday).where(Holiday.user_id.is_(None))
        )).scalars().all()
    }
    nuevos = 0
    for anio, dias in FESTIVOS_COLOMBIA.items():
        for iso, nombre in dias:
            fecha = date.fromisoformat(iso)
            if fecha in existentes:
                continue
            session.add(Holiday(date=fecha, name=nombre, user_id=None, kind="festivo"))
            existentes.add(fecha)
            nuevos += 1
    return nuevos


async def seed_time_tracking():
    """Siembra completa del módulo. Nunca lanza: si algo falla, lo registra y el
    backend arranca igual (mismo criterio que `seed_admin_user`)."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            actividades = await _sembrar_actividades(session)
            jornada = await _sembrar_jornada(session)
            festivos = await _sembrar_festivos(session)
            await session.commit()
            if actividades or jornada or festivos:
                logger.info(
                    f"Horas: siembra — {actividades} actividad(es), "
                    f"{jornada} dia(s) de jornada, {festivos} festivo(s)"
                )
            else:
                logger.info("Horas: siembra ya estaba completa, nada que insertar")
        except Exception as e:
            await session.rollback()
            logger.error(f"Horas: fallo la siembra ({e}); el modulo puede quedar incompleto")
