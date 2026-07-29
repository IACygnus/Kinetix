"""Tests del endpoint POST /designs/{id}/analyze-har (Sprint 3.0 — Fundacion 1).

El repo no tiene infraestructura HTTP de test (no hay conftest.py, TestClient
ni fixtures de DB async): los 208 tests del baseline son unitarios sobre
funciones. Para no montar esa infraestructura completa en esta fundacion, aca
se invoca la funcion del endpoint DIRECTAMENTE con un doble de la sesion de
DB y un usuario falso — las dependencias de FastAPI (``Depends``) se saltan
porque se pasan como argumentos explicitos.
"""
import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import script_ai
from app.api.v1.endpoints.script_ai import analyze_design_har
from app.services.ai.har_flow_analyzer import (
    STATUS_COMPLETED,
    HarAnalysisError,
    source_fingerprint,
)


# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeDB:
    """Sesion async minima: siempre resuelve al objeto que se le dio."""

    def __init__(self, obj):
        self._obj = obj
        self.commits = 0

    async def execute(self, _stmt):
        return _FakeResult(self._obj)

    async def commit(self):
        self.commits += 1


def _user(role="admin", user_id=None):
    return SimpleNamespace(id=user_id or uuid.uuid4(), role=role)


def _design(file_type="har", owner_id=None, content=None, **kwargs):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=owner_id or uuid.uuid4(),
        reference_file_type=file_type,
        reference_file_content=content,
        har_analysis_classification=kwargs.get("classification"),
        har_analysis_dependencies=kwargs.get("dependencies"),
        har_analysis_status=kwargs.get("status"),
    )


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Guardas de acceso y de tipo de archivo
# ---------------------------------------------------------------------------


def test_design_inexistente_devuelve_404():
    db = _FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        _run(analyze_design_har(uuid.uuid4(), force=False, db=db, current_user=_user()))
    assert exc.value.status_code == 404
    assert "no encontrado" in exc.value.detail.lower()


def test_design_sin_har_devuelve_400():
    db = _FakeDB(_design(file_type="postman"))
    with pytest.raises(HTTPException) as exc:
        _run(analyze_design_har(uuid.uuid4(), force=False, db=db, current_user=_user()))
    assert exc.value.status_code == 400
    assert "postman" in exc.value.detail


def test_design_sin_archivo_de_referencia_devuelve_400():
    db = _FakeDB(_design(file_type=None))
    with pytest.raises(HTTPException) as exc:
        _run(analyze_design_har(uuid.uuid4(), force=False, db=db, current_user=_user()))
    assert exc.value.status_code == 400
    assert "ninguno" in exc.value.detail


def test_no_admin_ajeno_al_diseno_devuelve_403():
    db = _FakeDB(_design(owner_id=uuid.uuid4()))
    with pytest.raises(HTTPException) as exc:
        _run(analyze_design_har(
            uuid.uuid4(), force=False, db=db, current_user=_user(role="analyst")
        ))
    assert exc.value.status_code == 403


def test_admin_pasa_la_guarda_de_propiedad():
    """Un admin sobre un diseno ajeno llega hasta la validacion de tipo."""
    db = _FakeDB(_design(file_type="openapi", owner_id=uuid.uuid4()))
    with pytest.raises(HTTPException) as exc:
        _run(analyze_design_har(uuid.uuid4(), force=False, db=db, current_user=_user()))
    assert exc.value.status_code == 400  # 400 (tipo), no 403 (acceso)


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------


def _har_content():
    return json.dumps({"log": {"entries": [
        {"request": {"method": "GET", "url": "https://api.example.com/x"},
         "response": {"status": 200}}
    ]}})


def test_analisis_vigente_se_reutiliza_sin_llamar_a_la_ia():
    content = _har_content()
    design = _design(
        content=content,
        status=STATUS_COMPLETED,
        classification={
            "source_sha1": source_fingerprint(content),
            "total_entries": 105,
            "analyzed_entries": 105,
            "counts": {"navigation": 5, "xhr": 80, "auth": 3, "write": 12, "config": 5},
        },
        dependencies={"dependencies": [{"source_idx": 1, "target_idx": 2}]},
    )
    db = _FakeDB(design)

    # Si no cortara aca, seguiria a load_ai_config_from_db con una DB falsa
    # que no sabe responder esa query — el test fallaria con AttributeError.
    resp = _run(analyze_design_har(design.id, force=False, db=db, current_user=_user()))

    assert resp.reused is True
    assert resp.status == STATUS_COMPLETED
    assert resp.total_entries == 105
    assert resp.counts["write"] == 12
    assert resp.dependencies_found == 1
    assert db.commits == 0  # nada que escribir


def _stub_ai_pipeline(monkeypatch, outcome=None, raises=None):
    """Aisla el endpoint del proveedor de IA real y del analyzer."""
    async def _fake_conf(_db):
        return {"provider": "openai", "model_name": "gpt-4o", "api_key": "k"}

    def _fake_analyze(_content, _call_ai):
        if raises is not None:
            raise raises
        return outcome

    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _fake_conf)
    monkeypatch.setattr(script_ai, "analyze_har_flow", _fake_analyze)


_OK_OUTCOME = {
    "status": STATUS_COMPLETED,
    "classification": {
        "source_sha1": "nuevo", "total_entries": 30, "analyzed_entries": 30,
        "counts": {"navigation": 2, "xhr": 20, "auth": 3, "write": 4, "config": 1},
        "phase2_error": None,
    },
    "dependencies": {"analyzed_entries": 28, "dependencies": [
        {"source_idx": 1, "target_idx": 4}, {"source_idx": 4, "target_idx": 9},
    ]},
    "error": None,
}


def test_har_cambiado_invalida_el_analisis_previo(monkeypatch):
    """Mismo status 'completed' pero otro HAR: el hash no coincide, re-analiza."""
    _stub_ai_pipeline(monkeypatch, outcome=_OK_OUTCOME)
    design = _design(
        content=_har_content(),
        status=STATUS_COMPLETED,
        classification={"source_sha1": "hash-de-otro-har", "counts": {}},
    )
    db = _FakeDB(design)
    resp = _run(analyze_design_har(design.id, force=False, db=db, current_user=_user()))

    assert resp.reused is False
    assert resp.total_entries == 30
    assert db.commits == 1


def test_status_failed_no_se_reutiliza(monkeypatch):
    _stub_ai_pipeline(monkeypatch, outcome=_OK_OUTCOME)
    content = _har_content()
    design = _design(
        content=content,
        status="failed",
        classification={"source_sha1": source_fingerprint(content), "counts": {}},
    )
    db = _FakeDB(design)
    resp = _run(analyze_design_har(design.id, force=False, db=db, current_user=_user()))
    assert resp.reused is False
    assert resp.status == STATUS_COMPLETED


def test_force_ignora_el_analisis_vigente(monkeypatch):
    _stub_ai_pipeline(monkeypatch, outcome=_OK_OUTCOME)
    content = _har_content()
    design = _design(
        content=content,
        status=STATUS_COMPLETED,
        classification={"source_sha1": source_fingerprint(content), "counts": {}},
    )
    db = _FakeDB(design)
    resp = _run(analyze_design_har(design.id, force=True, db=db, current_user=_user()))
    assert resp.reused is False
    assert db.commits == 1


def test_analisis_ok_persiste_las_tres_columnas(monkeypatch):
    _stub_ai_pipeline(monkeypatch, outcome=_OK_OUTCOME)
    design = _design(content=_har_content())
    db = _FakeDB(design)
    resp = _run(analyze_design_har(design.id, force=False, db=db, current_user=_user()))

    assert design.har_analysis_status == STATUS_COMPLETED
    assert design.har_analysis_classification["counts"]["write"] == 4
    assert len(design.har_analysis_dependencies["dependencies"]) == 2
    assert resp.dependencies_found == 2
    assert resp.counts["xhr"] == 20
    assert db.commits == 1


def test_fase2_fallida_persiste_failed_sin_pisar_la_fase_1(monkeypatch):
    """status='failed' + clasificacion retenida + dependencias intactas."""
    _stub_ai_pipeline(monkeypatch, outcome={
        "status": "failed",
        "classification": {"source_sha1": "x", "total_entries": 30,
                           "counts": {"xhr": 30}, "phase2_error": "502"},
        "dependencies": None,
        "error": "Fase 2 (dependencias) fallo: 502",
    })
    design = _design(content=_har_content())
    db = _FakeDB(design)
    resp = _run(analyze_design_har(design.id, force=False, db=db, current_user=_user()))

    assert resp.status == "failed"
    assert "Fase 2" in resp.error
    assert design.har_analysis_status == "failed"
    assert design.har_analysis_classification["phase2_error"] == "502"
    assert design.har_analysis_dependencies is None


def test_har_ilegible_devuelve_200_con_failed_no_500(monkeypatch):
    """Un HAR roto no puede tumbar el fire-and-forget del frontend."""
    _stub_ai_pipeline(monkeypatch, raises=HarAnalysisError("HAR invalido"))
    design = _design(content="{roto")
    db = _FakeDB(design)
    resp = _run(analyze_design_har(design.id, force=False, db=db, current_user=_user()))

    assert resp.status == "failed"
    assert "HAR invalido" in resp.error
    assert design.har_analysis_status == "failed"
    assert db.commits == 1


def test_sin_api_key_devuelve_503(monkeypatch):
    async def _no_key(_db):
        return {"provider": "openai", "model_name": "gpt-4o", "api_key": ""}

    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _no_key)
    db = _FakeDB(_design(content=_har_content()))
    with pytest.raises(HTTPException) as exc:
        _run(analyze_design_har(uuid.uuid4(), force=False, db=db, current_user=_user()))
    assert exc.value.status_code == 503


def test_limite_de_uso_de_ia_devuelve_429(monkeypatch):
    async def _limited(_db):
        return {"provider": "openai", "api_key": "k", "limit_reached": "diario"}

    monkeypatch.setattr(script_ai, "load_ai_config_from_db", _limited)
    db = _FakeDB(_design(content=_har_content()))
    with pytest.raises(HTTPException) as exc:
        _run(analyze_design_har(uuid.uuid4(), force=False, db=db, current_user=_user()))
    assert exc.value.status_code == 429
