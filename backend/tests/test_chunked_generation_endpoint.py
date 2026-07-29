"""Tests de la orquestacion por chunks (Sprint 3.0 — Fundacion 2).

Mismo enfoque que la Fundacion 1: el repo no tiene infraestructura HTTP de
test, asi que las funciones de endpoint se invocan DIRECTAMENTE con un doble
de sesion de DB y un usuario falso. El proveedor de IA se reemplaza por un
``call_ai`` de mentira que devuelve XML fabricado.
"""
import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import script_ai
from app.api.v1.endpoints.script_ai import (
    generate_jmx_chunked,
    process_pending_chunks,
    retry_failed_chunks,
)
from app.services.ai.har_chunk_router import (
    CHUNK_COMPLETED,
    CHUNK_FAILED,
    CHUNK_PENDING,
    GENERATION_COMPLETED,
    GENERATION_PARTIAL,
    MODE_CHUNKED,
    MODE_SINGLE,
    group_entries_into_chunks,
)
from app.services.ai.jmx_chunk_assembler import count_samplers, validate_jmx


# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeDB:
    def __init__(self, obj=None):
        self._obj = obj
        self.commits = 0

    async def execute(self, _stmt):
        return _FakeResult(self._obj)

    async def commit(self):
        self.commits += 1


def _user(role="admin", user_id=None):
    return SimpleNamespace(id=user_id or uuid.uuid4(), role=role)


# --- HAR / clasificacion reales -------------------------------------------


def _har(n):
    return json.dumps({"log": {"entries": [
        {"request": {"method": "GET", "url": f"https://api.x/{i}",
                     "headers": [{"name": "content-type", "value": "application/json"}]},
         "response": {"status": 200}}
        for i in range(n)
    ]}})


def _classification(categories):
    return {
        "version": 1, "source_sha1": "abc", "total_entries": len(categories),
        "analyzed_entries": len(categories),
        "counts": {c: categories.count(c) for c in set(categories)},
        "entries": [
            {"idx": i, "method": "GET", "url": f"https://api.x/{i}",
             "category": c, "reason": "r"}
            for i, c in enumerate(categories)
        ],
        "phase2_error": None,
    }


def _big_classification():
    """2 auth + 1 config + 45 xhr = 46 funcionales (> 30) -> 4 chunks."""
    return _classification(["auth", "auth", "config"] + ["xhr"] * 45)


def _deps():
    return {"version": 1, "analyzed_entries": 46, "dependencies": [{
        "source_idx": 0, "target_idx": 10, "data_name": "AccessToken",
        "locations": ["response.body.AccessToken", "request.header.Authorization"],
        "extractor_hint": "JSON Extractor sobre $.AccessToken", "confidence": "high",
    }]}


def _design(**kw):
    classification = kw.get("classification", _big_classification())
    n = len(classification["entries"]) if classification else 5
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=kw.get("name"),
        user_id=kw.get("owner_id") or uuid.uuid4(),
        reference_file_type="har",
        reference_file_content=kw.get("har", _har(n)),
        har_analysis_status=kw.get("har_status", "completed"),
        har_analysis_classification=classification,
        har_analysis_dependencies=kw.get("dependencies", _deps()),
        current_jmx=kw.get("current_jmx"),
        generation_mode=kw.get("generation_mode"),
        chunks_plan=kw.get("chunks_plan"),
        chunks_completed_count=kw.get("chunks_completed_count"),
        generation_status=kw.get("generation_status"),
    )


# --- IA de mentira ---------------------------------------------------------

_SKELETON_JMX = (
    "<?xml version='1.0' encoding='utf-8'?>"
    '<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3"><hashTree>'
    '<TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Plan" enabled="true"/>'
    "<hashTree>"
    '<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Usuarios" enabled="true"/>'
    '<hashTree><HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" '
    'testname="Login" enabled="true"/><hashTree/></hashTree>'
    "</hashTree></hashTree></jmeterTestPlan>"
)


def _fragment(n, tag="Extra"):
    return "".join(
        f'<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" '
        f'testname="{tag} {i}" enabled="true"/><hashTree/>'
        for i in range(n)
    )


class _AI:
    """call_ai falso. ``fail_on`` = nro de llamada (1-based) que revienta."""

    def __init__(self, fail_on=None, bad_output_on=None, fragment_size=3):
        self.calls = 0
        self.fail_on = fail_on
        self.bad_output_on = bad_output_on
        self.fragment_size = fragment_size
        self.prompts = []

    def __call__(self, messages):
        self.calls += 1
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        if self.fail_on == self.calls:
            raise RuntimeError("502 del proveedor")
        if self.bad_output_on == self.calls:
            return "lo siento, no puedo generar eso"
        # Responde segun lo que el prompt pide, no segun el numero de llamada:
        # asi el doble tambien verifica que el orquestador elija bien el prompt.
        if "JMX COMPLETO" in prompt:
            return _SKELETON_JMX
        return _fragment(self.fragment_size, tag=f"C{self.calls}")


def _run(coro):
    return asyncio.run(coro)


def _stub_ai(monkeypatch):
    async def _conf(_db):
        return {"provider": "openai", "model_name": "gpt-4o", "api_key": "k"}
    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _conf)


# ---------------------------------------------------------------------------
# process_pending_chunks — el corazon
# ---------------------------------------------------------------------------


def _prepared_design(**kw):
    design = _design(**kw)
    design.chunks_plan = group_entries_into_chunks(
        design.har_analysis_classification, design.har_analysis_dependencies
    )
    design.generation_mode = MODE_CHUNKED
    design.chunks_completed_count = 0
    return design


def test_flujo_completo_genera_todos_los_chunks():
    design = _prepared_design()
    db = _FakeDB(design)
    ai = _AI()

    out = _run(process_pending_chunks(design, db, ai))

    total = len(design.chunks_plan)
    assert out["generation_status"] == GENERATION_COMPLETED
    assert out["error"] is None
    assert ai.calls == total  # una llamada por chunk, ni una mas
    assert all(c["status"] == CHUNK_COMPLETED for c in out["plan"])
    assert design.chunks_completed_count == total
    assert validate_jmx(design.current_jmx)[0] is True
    # 1 del esqueleto + 3 por cada chunk siguiente
    assert count_samplers(design.current_jmx) == 1 + 3 * (total - 1)


def test_corta_al_primer_fallo_y_deja_el_resto_pending():
    design = _prepared_design()
    db = _FakeDB(design)
    ai = _AI(fail_on=3)

    out = _run(process_pending_chunks(design, db, ai))
    plan = out["plan"]

    assert out["generation_status"] == GENERATION_PARTIAL
    assert "502 del proveedor" in out["error"]
    assert [c["status"] for c in plan[:2]] == [CHUNK_COMPLETED, CHUNK_COMPLETED]
    assert plan[2]["status"] == CHUNK_FAILED
    assert "502" in plan[2]["failure_reason"]
    assert all(c["status"] == CHUNK_PENDING for c in plan[3:])
    assert ai.calls == 3  # no siguio intentando


def test_lo_generado_antes_del_fallo_queda_persistido():
    design = _prepared_design()
    db = _FakeDB(design)

    _run(process_pending_chunks(design, db, _AI(fail_on=3)))

    assert design.chunks_completed_count == 2
    assert count_samplers(design.current_jmx) == 1 + 3  # esqueleto + chunk 2
    assert validate_jmx(design.current_jmx)[0] is True
    assert db.commits >= 2  # persistio despues de cada chunk exitoso


def test_esqueleto_invalido_no_persiste_jmx_y_corta():
    design = _prepared_design(current_jmx=None)
    db = _FakeDB(design)

    out = _run(process_pending_chunks(design, db, _AI(bad_output_on=1)))

    assert out["generation_status"] == GENERATION_PARTIAL
    assert design.current_jmx is None  # nada se escribio
    assert out["plan"][0]["status"] == CHUNK_FAILED
    assert "no es un JMX valido" in out["plan"][0]["failure_reason"]


def test_fragmento_invalido_no_corrompe_el_jmx_previo():
    design = _prepared_design()
    db = _FakeDB(design)
    ai = _AI(bad_output_on=2)

    out = _run(process_pending_chunks(design, db, ai))
    jmx_tras_fallo = design.current_jmx

    assert out["generation_status"] == GENERATION_PARTIAL
    assert validate_jmx(jmx_tras_fallo)[0] is True
    assert count_samplers(jmx_tras_fallo) == 1  # solo el esqueleto
    assert out["plan"][1]["status"] == CHUNK_FAILED
    assert "no devolvio XML" in out["plan"][1]["failure_reason"]


def test_los_chunks_completados_no_se_regeneran():
    design = _prepared_design()
    design.chunks_plan[0]["status"] = CHUNK_COMPLETED
    design.chunks_plan[1]["status"] = CHUNK_COMPLETED
    design.current_jmx = _SKELETON_JMX
    db = _FakeDB(design)
    ai = _AI()

    out = _run(process_pending_chunks(design, db, ai))

    assert ai.calls == len(design.chunks_plan) - 2
    assert out["generation_status"] == GENERATION_COMPLETED


def test_el_prompt_del_chunk_2_recibe_las_variables_del_chunk_1():
    design = _prepared_design()
    db = _FakeDB(design)
    ai = _AI()

    _run(process_pending_chunks(design, db, ai))

    # El idx 0 (auth) esta en el chunk 1 y produce AccessToken.
    assert "AccessToken" in ai.prompts[1]
    assert "NO generes jmeterTestPlan" in ai.prompts[1]


def test_fallo_por_truncado_del_modelo_lo_dice_explicito():
    """finish_reason=length no puede quedar disfrazado de 'XML mal formado'."""
    design = _prepared_design()
    db = _FakeDB(design)
    ai = _AI(bad_output_on=2)
    ai.last_finish_reason = "length"

    out = _run(process_pending_chunks(design, db, ai))
    motivo = out["plan"][1]["failure_reason"]

    assert "finish_reason=length" in motivo
    assert "limite de tokens" in motivo
    assert "bloque mas chico" in motivo


def test_fallo_sin_truncado_no_inventa_la_causa():
    design = _prepared_design()
    db = _FakeDB(design)
    ai = _AI(bad_output_on=2)
    ai.last_finish_reason = "stop"

    out = _run(process_pending_chunks(design, db, ai))
    assert "finish_reason" not in out["plan"][1]["failure_reason"]


def test_har_ilegible_devuelve_partial_sin_llamar_a_la_ia():
    design = _prepared_design(har="{roto")
    db = _FakeDB(design)
    ai = _AI()

    out = _run(process_pending_chunks(design, db, ai))

    assert out["generation_status"] == GENERATION_PARTIAL
    assert ai.calls == 0
    assert out["error"]


# ---------------------------------------------------------------------------
# generate-chunked — guardas y contrato
# ---------------------------------------------------------------------------


def test_design_inexistente_devuelve_404():
    db = _FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        _run(generate_jmx_chunked(uuid.uuid4(), db=db, current_user=_user()))
    assert exc.value.status_code == 404


def test_no_admin_ajeno_devuelve_403():
    db = _FakeDB(_design(owner_id=uuid.uuid4()))
    with pytest.raises(HTTPException) as exc:
        _run(generate_jmx_chunked(uuid.uuid4(), db=db, current_user=_user(role="analyst")))
    assert exc.value.status_code == 403


def test_sin_analisis_completado_devuelve_400():
    db = _FakeDB(_design(har_status="skipped"))
    with pytest.raises(HTTPException) as exc:
        _run(generate_jmx_chunked(uuid.uuid4(), db=db, current_user=_user()))
    assert exc.value.status_code == 400
    assert "analyze-har" in exc.value.detail


def test_har_chico_responde_single_no_error(monkeypatch):
    """Debajo del umbral no es un fallo: el flujo clasico es la via correcta."""
    _stub_ai(monkeypatch)
    design = _design(classification=_classification(["xhr"] * 10))
    db = _FakeDB(design)

    resp = _run(generate_jmx_chunked(design.id, db=db, current_user=_user()))

    assert resp.mode == MODE_SINGLE
    assert resp.total_chunks == 0
    assert "10 entries funcionales" in resp.reason
    assert design.generation_mode == MODE_SINGLE


def test_generate_chunked_arma_el_plan_y_genera(monkeypatch):
    _stub_ai(monkeypatch)
    ai = _AI()
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))
    design = _design()
    db = _FakeDB(design)

    resp = _run(generate_jmx_chunked(design.id, db=db, current_user=_user()))

    assert resp.mode == MODE_CHUNKED
    assert resp.generation_status == GENERATION_COMPLETED
    assert resp.total_chunks == resp.chunks_completed == len(design.chunks_plan)
    assert resp.samplers_total == count_samplers(design.current_jmx)
    assert resp.error is None
    assert len(resp.chunks) == resp.total_chunks
    assert resp.chunks[0].is_skeleton is True


def test_generate_chunked_reporta_partial_al_fallar(monkeypatch):
    _stub_ai(monkeypatch)
    ai = _AI(fail_on=2)
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))
    design = _design()
    db = _FakeDB(design)

    resp = _run(generate_jmx_chunked(design.id, db=db, current_user=_user()))

    assert resp.generation_status == GENERATION_PARTIAL
    assert resp.chunks_completed == 1
    assert resp.error
    assert resp.chunks[1].status == CHUNK_FAILED
    assert resp.chunks[1].failure_reason


def test_sin_api_key_devuelve_503(monkeypatch):
    async def _no_key(_db):
        return {"provider": "openai", "api_key": ""}
    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _no_key)
    db = _FakeDB(_design())
    with pytest.raises(HTTPException) as exc:
        _run(generate_jmx_chunked(uuid.uuid4(), db=db, current_user=_user()))
    assert exc.value.status_code == 503


def test_limite_de_ia_devuelve_429(monkeypatch):
    async def _limited(_db):
        return {"provider": "openai", "api_key": "k", "limit_reached": "diario"}
    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _limited)
    db = _FakeDB(_design())
    with pytest.raises(HTTPException) as exc:
        _run(generate_jmx_chunked(uuid.uuid4(), db=db, current_user=_user()))
    assert exc.value.status_code == 429


# ---------------------------------------------------------------------------
# retry-failed-chunks
# ---------------------------------------------------------------------------


def _partial_design():
    """Diseno que quedo partial: chunk 1 OK, chunk 2 failed, resto pending."""
    design = _prepared_design()
    design.chunks_plan[0]["status"] = CHUNK_COMPLETED
    design.chunks_plan[1]["status"] = CHUNK_FAILED
    design.chunks_plan[1]["failure_reason"] = "502 del proveedor"
    design.current_jmx = _SKELETON_JMX
    design.chunks_completed_count = 99  # contador desincronizado a proposito
    design.generation_status = GENERATION_PARTIAL
    return design


def test_retry_recalcula_el_contador_desde_el_plan(monkeypatch):
    _stub_ai(monkeypatch)
    ai = _AI()
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))
    design = _partial_design()
    db = _FakeDB(design)

    resp = _run(retry_failed_chunks(design.id, db=db, current_user=_user()))

    # El 99 se descarta: el contador sale de contar los chunks completados.
    assert design.chunks_completed_count == len(design.chunks_plan)
    assert resp.chunks_completed == len(design.chunks_plan)


def test_retry_reanuda_y_completa(monkeypatch):
    _stub_ai(monkeypatch)
    ai = _AI()
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))
    design = _partial_design()
    total = len(design.chunks_plan)
    db = _FakeDB(design)

    resp = _run(retry_failed_chunks(design.id, db=db, current_user=_user()))

    assert resp.generation_status == GENERATION_COMPLETED
    assert all(c.status == CHUNK_COMPLETED for c in resp.chunks)
    assert ai.calls == total - 1  # el chunk 1 no se re-genero
    assert "1 bloque(s) fallido(s)" in resp.reason


def test_retry_no_regenera_el_esqueleto_completado(monkeypatch):
    _stub_ai(monkeypatch)
    ai = _AI()
    monkeypatch.setattr(script_ai, "_call_ai", lambda m, c, **kw: (ai(m), "stop"))
    design = _partial_design()
    db = _FakeDB(design)

    _run(retry_failed_chunks(design.id, db=db, current_user=_user()))

    # La primera llamada del retry ya es de un bloque, no del esqueleto.
    assert "NO generes jmeterTestPlan" in ai.prompts[0]


def test_retry_sin_nada_pendiente_no_llama_a_la_ia(monkeypatch):
    _stub_ai(monkeypatch)
    design = _prepared_design()
    for c in design.chunks_plan:
        c["status"] = CHUNK_COMPLETED
    design.current_jmx = _SKELETON_JMX
    design.generation_status = GENERATION_COMPLETED
    db = _FakeDB(design)

    resp = _run(retry_failed_chunks(design.id, db=db, current_user=_user()))

    assert resp.generation_status == GENERATION_COMPLETED
    assert "nada que reintentar" in resp.reason


def test_retry_sin_generacion_por_chunks_devuelve_400():
    db = _FakeDB(_design())  # generation_mode = None
    with pytest.raises(HTTPException) as exc:
        _run(retry_failed_chunks(uuid.uuid4(), db=db, current_user=_user()))
    assert exc.value.status_code == 400
    assert "generate-chunked" in exc.value.detail


def test_retry_design_inexistente_devuelve_404():
    db = _FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        _run(retry_failed_chunks(uuid.uuid4(), db=db, current_user=_user()))
    assert exc.value.status_code == 404
