"""ETAPA H1.3 — Reglas de negocio del módulo de horas.

El repo no tiene infraestructura HTTP de test (sin conftest ni TestClient): los
tests son unitarios sobre funciones, y los de endpoint invocan la función
directamente con dobles. Se sigue ese estilo.

Lo que se prueba aquí es lo que NO se puede comprobar con curl sin la contraseña
de otra persona, o lo que conviene tener fijado aunque el servidor no esté
arriba:

  - el 403 de un analyst al cerrar un proyecto (§8) — el caso que la corrida de
    curl dejó sin probar;
  - la normalización de nombres (H-D3, §6.2.3);
  - los pasos de 0,25 y las estimaciones positivas (H-D8);
  - las reglas de `ProjectCreate` (§3).
"""
import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.security import require_role
from app.db.models.time_tracking import normalizar
from app.schemas.time_tracking import (
    ProjectActivityInput, ProjectCreate, validar_paso,
)


def _user(role="admin"):
    return SimpleNamespace(id=uuid.uuid4(), role=role, is_active=True,
                           username=role, full_name=role)


# ==================== §8 — CERRAR ES SOLO DE ADMIN ====================

def test_analyst_no_puede_cerrar_un_proyecto():
    """El caso que la corrida de curl no pudo probar: hace falta la clave de otra
    persona. `require_role` es el guardia real del endpoint, así que se prueba él."""
    guardia = require_role(["admin"])
    with pytest.raises(HTTPException) as e:
        asyncio.run(guardia(current_user=_user("analyst")))
    assert e.value.status_code == 403


def test_viewer_tampoco_puede_cerrar():
    guardia = require_role(["admin"])
    with pytest.raises(HTTPException) as e:
        asyncio.run(guardia(current_user=_user("viewer")))
    assert e.value.status_code == 403


def test_admin_si_puede_cerrar():
    guardia = require_role(["admin"])
    admin = _user("admin")
    assert asyncio.run(guardia(current_user=admin)) is admin


# ==================== H-D3 — NOMBRES NORMALIZADOS ====================

def test_normalizar_quita_tildes():
    assert normalizar("Planeación") == "planeacion"


def test_normalizar_ignora_mayusculas_y_espacios_de_mas():
    assert normalizar("  PLANEACIÓN  ") == normalizar("planeacion")


def test_normalizar_colapsa_espacios_interiores():
    assert normalizar("Analisis   de    resultados") == "analisis de resultados"


def test_normalizar_la_enie_no_es_una_tilde():
    """La eñe es una letra, no una vocal acentuada: 'Diseño' no es 'Diseno'…
    pero la normalización de Unicode la descompone igual. Se fija el
    comportamiento REAL para que nadie lo cambie sin darse cuenta de que el
    catálogo ya tiene filas guardadas con esta forma."""
    assert normalizar("Diseño y generación de script") == "diseno y generacion de script"


def test_normalizar_tolera_vacio():
    assert normalizar("") == ""
    assert normalizar(None) == ""


# ==================== H-D8 — PASOS DE 0,25 ====================

@pytest.mark.parametrize("valor", ["0.25", "0.5", "1", "7.75", "40", "0.75"])
def test_acepta_multiplos_de_un_cuarto(valor):
    assert validar_paso(Decimal(valor)) == Decimal(valor)


@pytest.mark.parametrize("valor", ["0.3", "0.1", "1.2", "7.8", "0.26"])
def test_rechaza_lo_que_no_es_multiplo(valor):
    with pytest.raises(ValueError, match="pasos de 0,25"):
        validar_paso(Decimal(valor))


@pytest.mark.parametrize("valor", ["0", "-1", "-0.25"])
def test_rechaza_cero_y_negativos(valor):
    with pytest.raises(ValueError, match="mayores que cero"):
        validar_paso(Decimal(valor))


def test_el_mensaje_nombra_el_campo():
    with pytest.raises(ValueError, match="Las horas estimadas"):
        validar_paso(Decimal("0.3"), "Las horas estimadas")


# ==================== §3 — REGLAS AL CREAR UN PROYECTO ====================

def _entrada(horas="10"):
    return {"activity_id": str(uuid.uuid4()), "estimated_hours": horas}


def test_proyecto_necesita_al_menos_una_actividad():
    with pytest.raises(ValidationError, match="al menos una actividad"):
        ProjectCreate(client_id=uuid.uuid4(), name="X", activities=[])


def test_proyecto_rechaza_una_actividad_repetida():
    misma = str(uuid.uuid4())
    with pytest.raises(ValidationError, match="repetida"):
        ProjectCreate(client_id=uuid.uuid4(), name="X", activities=[
            {"activity_id": misma, "estimated_hours": "8"},
            {"activity_id": misma, "estimated_hours": "4"},
        ])


def test_proyecto_rechaza_una_estimacion_que_no_es_paso():
    with pytest.raises(ValidationError, match="pasos de 0,25"):
        ProjectCreate(client_id=uuid.uuid4(), name="X",
                      activities=[_entrada("0.3")])


def test_proyecto_rechaza_una_estimacion_cero():
    with pytest.raises(ValidationError, match="mayores que cero"):
        ProjectCreate(client_id=uuid.uuid4(), name="X",
                      activities=[_entrada("0")])


def test_proyecto_valido_se_construye():
    p = ProjectCreate(client_id=uuid.uuid4(), name="Proyecto",
                      activities=[_entrada("40"), _entrada("10.5")])
    assert len(p.activities) == 2
    assert p.activities[1].estimated_hours == Decimal("10.5")


def test_la_estimacion_es_decimal_no_float():
    """Numeric, no Float (decisión de H1.2): 0,1 + 0,2 en float no da 0,3 y la
    comparación consumido/estimado acabaría mintiendo."""
    e = ProjectActivityInput(activity_id=uuid.uuid4(), estimated_hours="0.25")
    assert isinstance(e.estimated_hours, Decimal)
    assert e.estimated_hours * 3 == Decimal("0.75")
