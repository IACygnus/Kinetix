"""Tests del modo background + estado pollable (Sprint 3.0 — F3.1).

Mismo enfoque que F1/F2: sin infraestructura HTTP de test, las funciones de
endpoint se invocan DIRECTAMENTE con un doble de sesion y un usuario falso.

Lo que se ejercita aca es el CICLO DE VIDA, no la generacion en si (esa ya la
cubre ``test_chunked_generation_endpoint.py``):

- el POST devuelve al instante, sin haber llamado a la IA;
- el guard anti-concurrencia rechaza un segundo lanzamiento;
- ningun diseno queda en ``in_progress`` colgado, pase lo que pase;
- ``/generation-status`` sirve el plan completo con linaje y cobertura.

La tarea de fondo se ejecuta en sincronico inyectandole una fabrica de sesion
falsa: es la MISMA funcion que corre en produccion, no una copia de test.
"""
import json
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import script_ai
from app.api.v1.endpoints.script_ai import (
    generate_jmx_chunked,
    get_generation_status,
    retry_failed_chunks,
)
from app.schemas.ai_script_design import AIScriptDesignDetail
from app.services.ai.har_chunk_router import (
    CHUNK_COMPLETED,
    CHUNK_FAILED,
    CHUNK_PENDING,
    CHUNK_SPLIT,
    GENERATION_COMPLETED,
    GENERATION_FAILED,
    GENERATION_IN_PROGRESS,
    GENERATION_PARTIAL,
    MODE_CHUNKED,
    group_entries_into_chunks,
)
from app.services.ai.har_flow_analyzer import response_body_coverage

from tests.test_chunked_generation_endpoint import (
    _AI,
    _FakeDB,
    _FakeSessionFactory,
    _classification,
    _design,
    _har,
    _no_launch,
    _prepared_design,
    _run,
    _run_bg,
    _stub_ai,
    _user,
)


# ---------------------------------------------------------------------------
# El POST vuelve en el acto
# ---------------------------------------------------------------------------


def test_generate_chunked_no_llama_a_la_ia_antes_de_responder(monkeypatch):
    """Lo unico que el endpoint hace es dejar el plan listo y lanzar."""
    _stub_ai(monkeypatch)
    launched = _no_launch(monkeypatch)
    ai = _AI()
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))
    design = _design()
    db = _FakeDB(design)

    resp = _run(generate_jmx_chunked(design.id, db=db, current_user=_user()))

    assert resp.generation_status == GENERATION_IN_PROGRESS
    assert ai.calls == 0
    assert launched == [design.id]
    # El plan quedo persistido antes de responder: la tarea de fondo lo lee de
    # la base, no lo recibe por parametro.
    assert design.generation_mode == MODE_CHUNKED
    assert design.generation_status == GENERATION_IN_PROGRESS
    assert design.chunks_plan


def test_el_lanzamiento_sella_el_timestamp_de_inicio(monkeypatch):
    _stub_ai(monkeypatch)
    _no_launch(monkeypatch)
    design = _design()
    db = _FakeDB(design)

    _run(generate_jmx_chunked(design.id, db=db, current_user=_user()))

    sellos = {c.get("run_started_at") for c in design.chunks_plan}
    assert len(sellos) == 1
    sello = sellos.pop()
    assert sello and sello.endswith("Z")
    datetime.fromisoformat(sello[:-1])  # parseable: no es un string cualquiera


def test_retry_no_llama_a_la_ia_antes_de_responder(monkeypatch):
    _stub_ai(monkeypatch)
    launched = _no_launch(monkeypatch)
    ai = _AI()
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))

    design = _prepared_design()
    design.chunks_plan[0]["status"] = CHUNK_COMPLETED
    design.chunks_plan[1]["status"] = CHUNK_FAILED
    design.generation_status = GENERATION_PARTIAL
    db = _FakeDB(design)

    resp = _run(retry_failed_chunks(design.id, db=db, current_user=_user()))

    assert resp.generation_status == GENERATION_IN_PROGRESS
    assert ai.calls == 0
    assert launched == [design.id]
    assert design.generation_status == GENERATION_IN_PROGRESS


# ---------------------------------------------------------------------------
# Guard anti-concurrencia
# ---------------------------------------------------------------------------


def test_generate_chunked_rechaza_un_segundo_lanzamiento(monkeypatch):
    """200 con el estado actual, no 409 ni una segunda tanda de llamadas."""
    _stub_ai(monkeypatch)
    launched = _no_launch(monkeypatch)
    design = _prepared_design()
    design.generation_status = GENERATION_IN_PROGRESS
    design.chunks_plan[0]["status"] = CHUNK_COMPLETED
    db = _FakeDB(design)

    resp = _run(generate_jmx_chunked(design.id, db=db, current_user=_user()))

    assert resp.generation_status == GENERATION_IN_PROGRESS
    assert launched == []  # NO se lanzo una segunda tarea
    assert "en curso" in resp.reason
    assert "generation-status" in resp.reason
    # Devuelve el avance real, para que la UI pueda seguir dibujando.
    assert resp.chunks_completed == 1
    assert resp.total_chunks == len(design.chunks_plan)


def test_retry_rechaza_un_segundo_lanzamiento(monkeypatch):
    _stub_ai(monkeypatch)
    launched = _no_launch(monkeypatch)
    design = _prepared_design()
    design.generation_status = GENERATION_IN_PROGRESS
    db = _FakeDB(design)

    resp = _run(retry_failed_chunks(design.id, db=db, current_user=_user()))

    assert resp.generation_status == GENERATION_IN_PROGRESS
    assert launched == []


def test_el_guard_no_pisa_el_plan_de_la_corrida_en_curso(monkeypatch):
    """Un segundo POST no puede resetear los bloques que ya se generaron."""
    _stub_ai(monkeypatch)
    _no_launch(monkeypatch)
    design = _prepared_design()
    design.generation_status = GENERATION_IN_PROGRESS
    for c in design.chunks_plan[:2]:
        c["status"] = CHUNK_COMPLETED
    plan_antes = [dict(c) for c in design.chunks_plan]
    db = _FakeDB(design)

    _run(generate_jmx_chunked(design.id, db=db, current_user=_user()))

    assert design.chunks_plan == plan_antes
    assert db.commits == 0  # ni siquiera toco la base


def test_el_guard_corre_antes_que_la_validacion_de_analisis(monkeypatch):
    """Con una corrida en curso no se evalua nada mas: el plan lo esta mutando
    la tarea de fondo en este mismo instante."""
    _stub_ai(monkeypatch)
    _no_launch(monkeypatch)
    design = _prepared_design(har_status="skipped")  # daria 400 si se evaluara
    design.generation_status = GENERATION_IN_PROGRESS
    db = _FakeDB(design)

    resp = _run(generate_jmx_chunked(design.id, db=db, current_user=_user()))

    assert resp.generation_status == GENERATION_IN_PROGRESS


# ---------------------------------------------------------------------------
# Estado terminal garantizado — sin tareas zombie
# ---------------------------------------------------------------------------


def test_una_excepcion_en_la_tarea_deja_estado_failed(monkeypatch):
    """Sin ningun bloque generado no hay parcial que reanudar: failed."""
    async def _explota(_db):
        raise RuntimeError("la base se cayo a mitad")
    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _explota)

    design = _prepared_design()
    design.generation_status = GENERATION_IN_PROGRESS
    db = _FakeDB(design)

    _run_bg(design, db)  # no levanta: la tarea de fondo se traga todo

    assert design.generation_status == GENERATION_FAILED
    assert design.generation_status != GENERATION_IN_PROGRESS


def test_una_excepcion_con_bloques_hechos_deja_estado_partial(monkeypatch):
    """Con trabajo ya persistido el estado es partial: /retry lo reanuda."""
    async def _explota(_db):
        raise RuntimeError("timeout del proveedor")
    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _explota)

    design = _prepared_design()
    design.generation_status = GENERATION_IN_PROGRESS
    design.chunks_plan[0]["status"] = CHUNK_COMPLETED
    design.chunks_plan[1]["status"] = CHUNK_COMPLETED
    db = _FakeDB(design)

    _run_bg(design, db)

    assert design.generation_status == GENERATION_PARTIAL
    assert design.chunks_completed_count == 2


def test_la_excepcion_queda_escrita_en_el_bloque_en_curso(monkeypatch):
    async def _explota(_db):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _explota)

    design = _prepared_design()
    design.generation_status = GENERATION_IN_PROGRESS
    design.chunks_plan[0]["status"] = CHUNK_COMPLETED
    db = _FakeDB(design)

    _run_bg(design, db)

    # El motivo va al PRIMER bloque no terminado, que es el que estaba corriendo.
    fallado = design.chunks_plan[1]
    assert fallado["status"] == CHUNK_FAILED
    assert "kaboom" in fallado["failure_reason"]
    assert "tarea de fondo aborto" in fallado["failure_reason"]
    # Los ya completados no se tocan.
    assert design.chunks_plan[0]["status"] == CHUNK_COMPLETED


def test_el_camino_feliz_no_es_pisado_por_la_red_de_seguridad(monkeypatch):
    """El `finally` corre SIEMPRE; no debe degradar un completed a partial."""
    _stub_ai(monkeypatch)
    ai = _AI()
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))
    design = _prepared_design()
    design.generation_status = GENERATION_IN_PROGRESS
    db = _FakeDB(design)

    _run_bg(design, db)

    assert design.generation_status == GENERATION_COMPLETED


def test_un_diseno_borrado_a_mitad_no_rompe_la_tarea(monkeypatch):
    _stub_ai(monkeypatch)
    design = _prepared_design()
    db = _FakeDB(None)  # el SELECT ya no lo encuentra

    _run_bg(design, db)  # no levanta

    assert db.commits == 0


def test_la_tarea_de_fondo_abre_su_propia_sesion(monkeypatch):
    """No reusa la de la request: cuando corre, esa ya se cerro."""
    _stub_ai(monkeypatch)
    ai = _AI()
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))
    design = _prepared_design()
    db = _FakeDB(design)

    class _ContadaFactory(_FakeSessionFactory):
        aperturas = 0

        async def __aenter__(self):
            type(self).aperturas += 1
            return await super().__aenter__()

    _run(script_ai._run_chunked_generation_background(
        design.id, session_factory=_ContadaFactory(db)
    ))

    # Una para el trabajo + una para la red de seguridad del `finally`, que
    # SIEMPRE abre sesion nueva: la de la tarea puede venir con la transaccion
    # abortada y ahi ningun commit de rescate prenderia.
    assert _ContadaFactory.aperturas == 2


# ---------------------------------------------------------------------------
# GET /generation-status
# ---------------------------------------------------------------------------


def _status(design):
    return _run(get_generation_status(
        design.id, db=_FakeDB(design), current_user=_user()
    ))


def test_generation_status_sirve_el_plan_completo():
    design = _prepared_design()
    design.chunks_plan[0]["status"] = CHUNK_COMPLETED
    design.chunks_plan[1]["status"] = CHUNK_FAILED
    design.chunks_plan[1]["failure_reason"] = "502 del proveedor"
    design.generation_status = GENERATION_PARTIAL

    resp = _status(design)

    assert resp.generation_mode == MODE_CHUNKED
    assert resp.generation_status == GENERATION_PARTIAL
    assert resp.chunks_completed_count == 1
    assert resp.total_chunks == len(design.chunks_plan)
    assert len(resp.chunks) == len(design.chunks_plan)
    assert resp.chunks[0].status == CHUNK_COMPLETED
    assert resp.chunks[1].failure_reason == "502 del proveedor"
    assert resp.chunks[0].n_entries > 0
    assert resp.chunks[0].is_skeleton is True


def test_generation_status_expone_el_linaje_del_split():
    design = _prepared_design()
    design.chunks_plan = [
        {"chunk_id": 1, "name": "C1", "entry_idxs": [0], "categories": ["auth"],
         "status": CHUNK_COMPLETED, "is_skeleton": True, "failure_reason": None,
         "split_depth": 0, "parent_chunk_id": None},
        {"chunk_id": 2, "name": "C2", "entry_idxs": [1, 2, 3, 4], "categories": ["xhr"],
         "status": CHUNK_SPLIT, "is_skeleton": False, "failure_reason": "trunco",
         "split_depth": 0, "parent_chunk_id": None},
        {"chunk_id": 3, "name": "C3", "entry_idxs": [1, 2], "categories": ["xhr"],
         "status": CHUNK_COMPLETED, "is_skeleton": False, "failure_reason": None,
         "split_depth": 1, "parent_chunk_id": 2},
        {"chunk_id": 4, "name": "C4", "entry_idxs": [3, 4], "categories": ["xhr"],
         "status": CHUNK_PENDING, "is_skeleton": False, "failure_reason": None,
         "split_depth": 1, "parent_chunk_id": 2},
    ]

    resp = _status(design)

    hijos = [c for c in resp.chunks if c.parent_chunk_id == 2]
    assert len(hijos) == 2
    assert all(h.split_depth == 1 for h in hijos)
    assert len(resp.chunks) == 4          # el padre sigue visible como linaje
    assert resp.total_chunks == 3         # ...pero no cuenta como generable
    assert resp.chunks_completed_count == 2


def test_generation_status_de_un_diseno_nunca_generado_no_es_error():
    """La UI necesita este 200 para decidir que NO muestra el panel."""
    design = _design()  # sin generation_mode ni chunks_plan

    resp = _status(design)

    assert resp.generation_mode is None
    assert resp.generation_status is None
    assert resp.total_chunks == 0
    assert resp.chunks_completed_count == 0
    assert resp.chunks == []
    assert resp.generation_started_at is None


def test_generation_status_trunca_motivos_de_fallo_largos():
    """Es un endpoint de poll: el XML cortado del modelo no viaja cada 3s."""
    design = _prepared_design()
    design.chunks_plan[0]["status"] = CHUNK_FAILED
    design.chunks_plan[0]["failure_reason"] = "x" * 5000

    resp = _status(design)

    assert len(resp.chunks[0].failure_reason) < 600
    assert "truncado" in resp.chunks[0].failure_reason


def test_generation_status_no_devuelve_el_jmx_ni_los_entry_idxs():
    design = _prepared_design()
    design.current_jmx = "<jmeterTestPlan>" + "<HTTPSamplerProxy/>" * 40

    resp = _status(design)

    campos = resp.model_dump()
    assert "current_jmx" not in campos
    assert all("entry_idxs" not in c for c in campos["chunks"])
    assert resp.samplers_total == 40  # el conteo si, que es barato


def test_generation_status_devuelve_el_timestamp_de_inicio():
    design = _prepared_design()
    for c in design.chunks_plan:
        c["run_started_at"] = "2026-08-11T10:00:00Z"

    assert _status(design).generation_started_at == "2026-08-11T10:00:00Z"


def test_generation_status_404_y_403():
    with pytest.raises(HTTPException) as exc:
        _run(get_generation_status(
            uuid.uuid4(), db=_FakeDB(None), current_user=_user()
        ))
    assert exc.value.status_code == 404

    ajeno = _design(owner_id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        _run(get_generation_status(
            ajeno.id, db=_FakeDB(ajeno), current_user=_user(role="analyst")
        ))
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Cobertura de response bodies del HAR (hallazgo F1)
# ---------------------------------------------------------------------------


def _har_con_bodies(total, con_body):
    entries = []
    for i in range(total):
        entry = {
            "request": {"method": "GET", "url": f"https://api.x/{i}", "headers": []},
            "response": {"status": 200, "content": {}},
        }
        if i < con_body:
            entry["response"]["content"] = {"text": '{"ok":true}'}
        entries.append(entry)
    return json.dumps({"log": {"entries": entries}})


def test_response_body_coverage_cuenta_solo_bodies_con_contenido():
    har = json.loads(_har_con_bodies(10, 4))
    assert response_body_coverage(har["log"]["entries"]) == {
        "entries_with_response_body": 4, "total_entries": 10,
    }


def test_response_body_coverage_ignora_bodies_vacios_o_ausentes():
    entries = [
        {"response": {"content": {"text": "   "}}},   # solo espacios
        {"response": {"content": {"text": ""}}},      # vacio
        {"response": {"content": {}}},                # sin text
        {"response": {}},                             # sin content
        {},                                           # sin response
        {"response": {"content": {"text": "{}"}}},    # este si cuenta
    ]
    assert response_body_coverage(entries)["entries_with_response_body"] == 1


def test_generation_status_lee_la_cobertura_persistida():
    """Camino normal: la clave la dejo /analyze-har, sin re-correr nada."""
    design = _prepared_design()
    design.har_analysis_classification["response_body_coverage"] = {
        "entries_with_response_body": 36, "total_entries": 106,
    }

    cov = _status(design).har_body_coverage

    assert cov.entries_with_response_body == 36
    assert cov.total_entries == 106
    assert cov.ratio == pytest.approx(0.3396, abs=1e-4)


def test_generation_status_calcula_la_cobertura_on_demand_si_falta():
    """Disenos analizados ANTES de F3.1: se recalcula del HAR, sin tocar la IA."""
    design = _prepared_design(classification=_classification(["xhr"] * 6))
    design.reference_file_content = _har_con_bodies(6, 2)
    assert "response_body_coverage" not in design.har_analysis_classification

    cov = _status(design).har_body_coverage

    assert cov.entries_with_response_body == 2
    assert cov.total_entries == 6
    # El fallback NO escribe: es solo lectura.
    assert "response_body_coverage" not in design.har_analysis_classification


def test_generation_status_devuelve_cobertura_none_si_no_hay_har():
    design = _prepared_design()
    design.har_analysis_classification = None
    design.reference_file_content = None

    assert _status(design).har_body_coverage is None


def test_una_cobertura_ilegible_no_tumba_el_polling():
    design = _prepared_design()
    design.reference_file_content = "{esto no es json"

    resp = _status(design)

    assert resp.har_body_coverage is None
    assert resp.total_chunks > 0  # el resto del payload llego intacto


def test_cobertura_de_un_har_vacio_no_divide_por_cero():
    design = _prepared_design()
    design.har_analysis_classification = {
        "response_body_coverage": {"entries_with_response_body": 0, "total_entries": 0}
    }

    assert _status(design).har_body_coverage.ratio == 0.0


def test_analyze_har_persiste_la_cobertura_en_la_clasificacion(monkeypatch):
    """La clave nueva viaja dentro del JSONB de clasificacion, no en una columna."""
    from app.services.ai import har_flow_analyzer as hfa

    def _fake_ai(messages):
        if "correlacion" in messages[0]["content"]:
            return '{"dependencies":[]}'
        return json.dumps({"entries": [
            {"idx": i, "category": "xhr", "reason": "r"} for i in range(25)
        ]})

    outcome = hfa.analyze_har_flow(_har_con_bodies(25, 9), _fake_ai)

    cov = outcome["classification"]["response_body_coverage"]
    assert cov == {"entries_with_response_body": 9, "total_entries": 25}


# ---------------------------------------------------------------------------
# AIScriptDesignDetail
# ---------------------------------------------------------------------------


def _detail_row(**kw):
    return SimpleNamespace(
        id=uuid.uuid4(), session_id=uuid.uuid4(), name="D", client_id=uuid.uuid4(),
        user_id=uuid.uuid4(), is_draft=True, conversation=[], current_jmx=None,
        reference_file_name=None, reference_file_content=None,
        reference_file_type="har",
        generation_mode=kw.get("generation_mode"),
        generation_status=kw.get("generation_status"),
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )


def test_detail_expone_generation_mode_y_status():
    detail = AIScriptDesignDetail.model_validate(_detail_row(
        generation_mode=MODE_CHUNKED, generation_status=GENERATION_IN_PROGRESS
    ))

    assert detail.generation_mode == MODE_CHUNKED
    assert detail.generation_status == GENERATION_IN_PROGRESS


def test_detail_de_un_diseno_clasico_deja_los_campos_en_none():
    """Un diseno que nunca paso por chunking no rompe la validacion."""
    detail = AIScriptDesignDetail.model_validate(_detail_row())

    assert detail.generation_mode is None
    assert detail.generation_status is None


def test_detail_sigue_sin_exponer_el_plan_de_chunks():
    """El plan es del endpoint de polling; el detalle solo dice si mostrar panel."""
    campos = AIScriptDesignDetail.model_validate(_detail_row()).model_dump()

    assert "chunks_plan" not in campos
    assert "chunks_completed_count" not in campos
