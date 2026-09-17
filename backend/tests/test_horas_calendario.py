"""ETAPA H2.2 — El calendario y las reglas del registro de horas.

Dos cosas que la corrida por HTTP no puede probar bien:

  - los **403** de H-D13 y §8 (registrar por otro y borrar siendo analyst), que
    exigirían la contraseña de otra persona;
  - los **bordes del calendario** (un festivo en viernes, un día con solo horas
    extra, un día futuro), que por HTTP dependerían de qué día se corra la prueba.

Aquí se prueban las funciones directamente, así que el resultado no cambia según
el día ni según quién ejecute.
"""
import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints.time_entries import _puede_editar, _usuario_del_registro
from app.core.security import require_role
from app.schemas.time_tracking import TimeEntryCreate, TimeEntryUpdate
from app.services.horas.calendario import (
    DiaDelCalendario, construir_dias, dias_pendientes, jornada_de, semana_de,
)

JORNADA = {0: D("8.5"), 1: D("8.5"), 2: D("8.5"), 3: D("8.5"), 4: D("8"), 5: D("0"), 6: D("0")}
LUNES = date(2026, 9, 14)   # un lunes de verdad


def _user(role="analyst", uid=None):
    return SimpleNamespace(id=uid or uuid.uuid4(), role=role, is_active=True,
                           username=role, full_name=role)


# ==================== LA JORNADA ====================

def test_la_jornada_de_lunes_a_jueves_es_ocho_y_media():
    for i in range(4):
        assert jornada_de(LUNES + timedelta(days=i), JORNADA) == D("8.5")


def test_el_viernes_son_ocho():
    assert jornada_de(LUNES + timedelta(days=4), JORNADA) == D("8")


def test_el_fin_de_semana_no_se_espera_nada():
    assert jornada_de(LUNES + timedelta(days=5), JORNADA) == D("0")
    assert jornada_de(LUNES + timedelta(days=6), JORNADA) == D("0")


def test_la_semana_empieza_en_lunes_sea_cual_sea_el_dia():
    for i in range(7):
        assert semana_de(LUNES + timedelta(days=i))[0] == LUNES


# ==================== LAS TRES REGLAS DE §4.2.6 y §4.2.7 ====================

def _dia(ordinarias="0", extra="0", esperadas="8.5", festivo=False, ausencia=False):
    return DiaDelCalendario(
        fecha=LUNES, esperadas=D(esperadas), ordinarias=D(ordinarias),
        extra=D(extra), es_festivo=festivo, es_ausencia=ausencia)


def test_por_debajo_de_la_jornada_esta_incompleto():
    d = _dia(ordinarias="4")
    assert d.incompleto is True
    assert d.faltan == D("4.5")


def test_completo_no_falta_nada():
    d = _dia(ordinarias="8.5")
    assert d.incompleto is False
    assert d.faltan == D("0")


def test_un_dia_con_horas_extra_nunca_esta_incompleto():
    """H-D17. Aunque las ordinarias no lleguen a la jornada."""
    d = _dia(ordinarias="2", extra="3")
    assert d.incompleto is False
    assert d.faltan == D("0")


def test_un_festivo_no_se_reclama():
    assert _dia(ordinarias="0", festivo=True).incompleto is False


def test_una_ausencia_tampoco_se_reclama():
    assert _dia(ordinarias="0", ausencia=True).incompleto is False


def test_el_fin_de_semana_no_se_reclama():
    assert _dia(ordinarias="0", esperadas="0").incompleto is False


def test_pasarse_de_la_jornada_no_es_incompleto():
    assert _dia(ordinarias="12").incompleto is False


# ==================== LA SEMANA ENTERA ====================

def test_una_semana_con_festivo_extras_y_un_dia_flojo():
    dias = construir_dias(
        LUNES, LUNES + timedelta(days=6), JORNADA,
        {
            LUNES: {"ordinarias": D("8.5")},                        # completo
            LUNES + timedelta(days=1): {"ordinarias": D("4")},      # faltan 4,5
            LUNES + timedelta(days=2): {"extra": D("3")},           # solo extras
        },
        {LUNES + timedelta(days=3): ("Fiesta", False)},             # festivo el jueves
    )
    assert len(dias) == 7
    assert [d.incompleto for d in dias] == [False, True, False, False, True, False, False]
    #                                        lun    mar   mié    jue*   vie    sáb    dom
    assert dias[1].faltan == D("4.5")
    assert dias[3].es_festivo is True
    assert dias[4].faltan == D("8")     # el viernes, sin registrar


def test_los_pendientes_no_incluyen_el_futuro():
    """Un día que todavía no ha llegado no es una deuda: abrir el panel un lunes
    no puede listar el resto de la semana."""
    dias = construir_dias(LUNES, LUNES + timedelta(days=6), JORNADA, {}, {})
    # Con "hoy" el martes, solo lunes y martes pueden estar pendientes.
    pendientes = dias_pendientes(dias, LUNES + timedelta(days=1))
    assert [d.fecha for d in pendientes] == [LUNES, LUNES + timedelta(days=1)]


def test_los_pendientes_saltan_festivos_y_fines_de_semana():
    dias = construir_dias(
        LUNES, LUNES + timedelta(days=6), JORNADA, {},
        {LUNES: ("Fiesta", False)},
    )
    fechas = [d.fecha for d in dias_pendientes(dias, LUNES + timedelta(days=6))]
    assert LUNES not in fechas                       # festivo
    assert LUNES + timedelta(days=5) not in fechas   # sábado
    assert LUNES + timedelta(days=6) not in fechas   # domingo
    assert len(fechas) == 4                          # martes a viernes


# ==================== H-D13 y §8: LOS PERMISOS ====================

def test_un_analyst_no_puede_registrar_por_otro():
    with pytest.raises(HTTPException) as e:
        asyncio.run(_usuario_del_registro(None, uuid.uuid4(), _user("analyst")))
    assert e.value.status_code == 403


def test_registrarse_a_uno_mismo_no_necesita_ser_admin():
    yo = _user("analyst")
    assert asyncio.run(_usuario_del_registro(None, yo.id, yo)) is yo
    assert asyncio.run(_usuario_del_registro(None, None, yo)) is yo


def test_borrar_es_solo_de_admin():
    guardia = require_role(["admin"])
    with pytest.raises(HTTPException) as e:
        asyncio.run(guardia(current_user=_user("analyst")))
    assert e.value.status_code == 403


def test_cada_cual_edita_los_suyos():
    mio = uuid.uuid4()
    yo = _user("analyst", mio)
    assert _puede_editar(SimpleNamespace(user_id=mio), yo) is True
    assert _puede_editar(SimpleNamespace(user_id=uuid.uuid4()), yo) is False


def test_el_admin_edita_los_de_todos():
    admin = _user("admin")
    assert _puede_editar(SimpleNamespace(user_id=uuid.uuid4()), admin) is True


# ==================== H-D21 y H-D8: EL SCHEMA ====================

def _alta(**kw):
    base = {"date": date.today(), "project_id": uuid.uuid4(),
            "activity_id": uuid.uuid4(), "hours": "8", "billable": True}
    base.update(kw)
    return TimeEntryCreate(**base)


def test_hoy_se_puede_registrar():
    assert _alta().date == date.today()


def test_ayer_tambien_sin_limite_hacia_atras():
    hace_un_ano = date.today() - timedelta(days=365)
    assert _alta(date=hace_un_ano).date == hace_un_ano


def test_manana_no():
    with pytest.raises(ValidationError, match="fecha futura"):
        _alta(date=date.today() + timedelta(days=1))


@pytest.mark.parametrize("h", ["0.3", "1.1", "0"])
def test_las_horas_van_en_pasos_de_un_cuarto(h):
    with pytest.raises(ValidationError):
        _alta(hours=h)


def test_editar_tampoco_admite_fecha_futura():
    with pytest.raises(ValidationError, match="fecha futura"):
        TimeEntryUpdate(date=date.today() + timedelta(days=1))


def test_editar_sin_tocar_la_fecha_es_valido():
    assert TimeEntryUpdate(hours="4").date is None


def test_facturable_es_obligatorio_al_crear():
    with pytest.raises(ValidationError):
        TimeEntryCreate(date=date.today(), project_id=uuid.uuid4(),
                        activity_id=uuid.uuid4(), hours="8")


def test_extra_y_observaciones_son_opcionales():
    e = _alta()
    assert e.overtime is False and e.notes is None
