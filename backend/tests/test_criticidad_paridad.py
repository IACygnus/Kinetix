"""ETAPA 5 (D42) — La regla de criticidad, lado Python.

Corre los casos de `fixtures/criticidad_casos.json` contra la regla REAL del
backend. El mismo archivo lo corre `frontend/src/utils/criticidad.paridad.ts`
contra el puerto en TypeScript: si alguien cambia la regla en un solo lenguaje,
uno de los dos falla.

Aqui no se reimplementa nada: se llama a `compute_per_transaction_verdicts` y al
mismo calculo de senales que usa `POST /extract-jtl-transactions`.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from app.services.ai.gemini import compute_per_transaction_verdicts

CASOS = json.loads(
    (Path(__file__).parent / "fixtures" / "criticidad_casos.json").read_text(encoding="utf-8")
)

ETIQUETA = "T"


def _veredicto(metricas, criterios):
    """Exactamente como lo llama el endpoint: un summary_df de una fila."""
    df = pd.DataFrame([{"label": ETIQUETA, **metricas}])
    return compute_per_transaction_verdicts(df, dict(criterios)).get(
        "verdicts_per_transaction", {}).get(ETIQUETA)


def _es_critica(metricas, criterios):
    """Las tres senales de `extract_jtl_transactions`, en el mismo orden."""
    veredicto = _veredicto(metricas, criterios)
    avg, mx = float(metricas["promedio"]), float(metricas["max"])
    motivos = []
    if veredicto in ("NO APTO", "APTO CON RESERVAS"):
        motivos.append("veredicto")
    if avg > 0 and mx >= 10 * avg:
        motivos.append("pico relativo")
    if mx >= 10000:
        motivos.append("pico absoluto")
    return bool(motivos)


@pytest.mark.parametrize("caso", CASOS["casos"], ids=[c["nombre"] for c in CASOS["casos"]])
def test_veredicto_por_transaccion(caso):
    assert _veredicto(caso["metricas"], caso["criterios"]) == caso["esperado"]


@pytest.mark.parametrize("caso", CASOS["senales"], ids=[c["nombre"] for c in CASOS["senales"]])
def test_senales_de_criticidad(caso):
    assert _es_critica(caso["metricas"], caso["criterios"]) is caso["esperado_critica"]


def test_los_criterios_propios_pisan_a_los_globales():
    """D41: sin criterios propios se evaluan los globales; con ellos, mandan."""
    df = pd.DataFrame([
        {"label": "con_propios", "promedio": 400, "p90": 462, "max": 1013, "tasa_error": 0.0},
        {"label": "sin_propios", "promedio": 400, "p90": 462, "max": 1013, "tasa_error": 0.0},
    ])
    criterios = {
        "response_time": 2000, "availability": 99.5,
        "per_transaction": {"con_propios": {"response_time": 300, "availability": 99.5}},
    }
    v = compute_per_transaction_verdicts(df, criterios)["verdicts_per_transaction"]
    assert v["con_propios"] == "NO APTO"      # 462 > 300
    assert v["sin_propios"] == "APTO"         # 462 holgado contra 2000


def test_la_concurrencia_no_mueve_el_veredicto():
    """D42: el veredicto usa p90 y tasa_error, y nada mas."""
    df = pd.DataFrame([{"label": ETIQUETA, "promedio": 400, "p90": 462,
                        "max": 1013, "tasa_error": 0.0}])
    base = {"response_time": 2000, "availability": 99.5}
    sin_conc = compute_per_transaction_verdicts(df, dict(base))
    con_conc = compute_per_transaction_verdicts(df, {**base, "concurrency": 5000})
    assert sin_conc == con_conc


def test_el_fixture_tiene_los_dos_bloques():
    """Si un bloque se queda vacio, la paridad no probaria nada."""
    assert len(CASOS["casos"]) >= 10
    assert len(CASOS["senales"]) >= 5
