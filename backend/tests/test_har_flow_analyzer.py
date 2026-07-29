"""Tests del analisis multi-fase del HAR (Sprint 3.0 — Fundacion 1).

El HAR de prueba replica el shape REAL persistido en
``ai_script_designs.reference_file_content``: la salida de ``compress_har``,
que conserva ``{"log": {"entries": [{"request": ..., "response": ...}]}}``.
"""
import json

import pytest

from app.services.ai.har_flow_analyzer import (
    CATEGORIES,
    FUNCTIONAL_CATEGORIES,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    HarAnalysisError,
    _MIN_ENTRIES_FOR_AUTO_ANALYSIS,
    analyze_har_flow,
    build_digests,
    build_phase2_messages,
    entry_digest,
    extract_entries,
    filter_functional,
    parse_ai_json,
    parse_phase1_response,
    parse_phase2_response,
    should_auto_analyze,
    source_fingerprint,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _entry(method="GET", url="https://api.example.com/items", status=200,
           req_body=None, res_body=None, auth=False):
    """Un entry con el shape que produce compress_har."""
    headers = [{"name": "content-type", "value": "application/json"}]
    if auth:
        headers.append({"name": "authorization", "value": "Bearer abc123"})
    entry = {
        "request": {"method": method, "url": url, "headers": headers},
        "response": {"status": status, "statusText": "OK"},
    }
    if req_body:
        entry["request"]["postData"] = {
            "mimeType": "application/json", "text": req_body
        }
    if res_body:
        entry["response"]["content"] = {
            "mimeType": "application/json", "text": res_body
        }
    return entry


def _har(entries):
    return json.dumps({
        "log": {
            "version": "1.2",
            "creator": {"name": "compressed-by-kinetix"},
            "entries": entries,
        }
    })


def _har_n(n):
    """HAR con n entries variados."""
    entries = [_entry(url="https://app.example.com/home", status=200)]
    entries.append(_entry("POST", "https://api.example.com/login",
                          req_body='{"user":"u","pass":"p"}',
                          res_body='{"access_token":"TK"}'))
    while len(entries) < n:
        i = len(entries)
        entries.append(_entry(url=f"https://api.example.com/items/{i}", auth=True))
    return _har(entries[:n])


class _AIStub:
    """call_ai falso: devuelve respuestas en orden y registra las llamadas."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, messages):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("call_ai llamado mas veces de lo esperado")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _phase1_ok(n, category="xhr"):
    return json.dumps({
        "entries": [
            {"idx": i, "category": "navigation" if i == 0 else category,
             "reason": "r"}
            for i in range(n)
        ]
    })


# ---------------------------------------------------------------------------
# Lectura del HAR (shape real)
# ---------------------------------------------------------------------------


def test_extract_entries_lee_shape_real_del_har_comprimido():
    entries = extract_entries(_har_n(5))
    assert len(entries) == 5
    assert entries[1]["request"]["method"] == "POST"
    assert entries[1]["request"]["url"].endswith("/login")


def test_extract_entries_json_invalido_lanza_error_controlado():
    with pytest.raises(HarAnalysisError, match="JSON no parseable"):
        extract_entries("{no es json")


def test_extract_entries_sin_log_lanza_error():
    with pytest.raises(HarAnalysisError, match="falta el objeto 'log'"):
        extract_entries(json.dumps({"entries": []}))


def test_extract_entries_entries_no_lista_lanza_error():
    with pytest.raises(HarAnalysisError, match="no es una lista"):
        extract_entries(json.dumps({"log": {"entries": "nope"}}))


def test_extract_entries_contenido_vacio_lanza_error():
    with pytest.raises(HarAnalysisError):
        extract_entries("")
    with pytest.raises(HarAnalysisError):
        extract_entries(None)


def test_extract_entries_descarta_items_no_dict():
    raw = json.dumps({"log": {"entries": [_entry(), "basura", None]}})
    assert len(extract_entries(raw)) == 1


# ---------------------------------------------------------------------------
# Umbral de auto-analisis
# ---------------------------------------------------------------------------


def test_umbral_de_auto_analisis_es_20():
    assert _MIN_ENTRIES_FOR_AUTO_ANALYSIS == 20


def test_should_auto_analyze_respeta_el_umbral():
    assert not should_auto_analyze([{}] * 19)
    assert should_auto_analyze([{}] * 20)
    assert should_auto_analyze([{}] * 105)


def test_har_pequeno_devuelve_skipped_sin_llamar_a_la_ia():
    ai = _AIStub()  # cualquier llamada seria un fallo
    out = analyze_har_flow(_har_n(10), ai)
    assert out["status"] == STATUS_SKIPPED
    assert out["classification"] is None
    assert out["dependencies"] is None
    assert ai.calls == []


# ---------------------------------------------------------------------------
# Digest de entries
# ---------------------------------------------------------------------------


def test_entry_digest_extrae_campos_utiles():
    d = entry_digest(
        _entry("POST", "https://api.example.com/orders?draft=1", 201,
               req_body='{"sku":1}', res_body='{"id":99}', auth=True),
        7,
    )
    assert d["idx"] == 7
    assert d["method"] == "POST"
    assert d["path"] == "/orders"
    assert d["query"] == "draft=1"
    assert d["status"] == 201
    assert d["has_authorization_header"] is True
    assert d["request_body"] == '{"sku":1}'
    assert d["response_body"] == '{"id":99}'


def test_entry_digest_trunca_bodies_gigantes():
    d = entry_digest(_entry(res_body="x" * 5000), 0)
    assert len(d["response_body"]) < 5000
    assert "chars]" in d["response_body"]


def test_build_digests_indexa_por_posicion_real():
    digests = build_digests(extract_entries(_har_n(25)))
    assert [d["idx"] for d in digests] == list(range(25))


# ---------------------------------------------------------------------------
# Parser de JSON de la IA
# ---------------------------------------------------------------------------


def test_parse_ai_json_acepta_json_limpio():
    assert parse_ai_json('{"a": 1}') == {"a": 1}


def test_parse_ai_json_desenvuelve_markdown():
    raw = 'Claro, aca va:\n```json\n{"entries": [{"idx": 0}]}\n```\nEspero sirva.'
    assert parse_ai_json(raw) == {"entries": [{"idx": 0}]}


def test_parse_ai_json_desenvuelve_fence_sin_lenguaje():
    assert parse_ai_json("```\n[1, 2, 3]\n```") == [1, 2, 3]


def test_parse_ai_json_recorta_texto_alrededor():
    assert parse_ai_json('Resultado: {"ok": true} — fin') == {"ok": True}


def test_parse_ai_json_vacio_lanza_error():
    with pytest.raises(HarAnalysisError, match="vacia"):
        parse_ai_json("")


def test_parse_ai_json_no_parseable_lanza_error():
    with pytest.raises(HarAnalysisError, match="no devolvio JSON parseable"):
        parse_ai_json("no hay ningun json aca, solo prosa")


# ---------------------------------------------------------------------------
# Fase 1 — clasificacion
# ---------------------------------------------------------------------------


def test_phase1_cuenta_por_categoria():
    digests = build_digests(extract_entries(_har_n(4)))
    raw = json.dumps({"entries": [
        {"idx": 0, "category": "navigation", "reason": "html"},
        {"idx": 1, "category": "auth", "reason": "login"},
        {"idx": 2, "category": "write", "reason": "post"},
        {"idx": 3, "category": "config", "reason": "catalogo"},
    ]})
    out = parse_phase1_response(raw, digests)
    assert out["counts"] == {
        "navigation": 1, "xhr": 0, "auth": 1, "write": 1, "config": 1
    }
    assert set(out["counts"]) == set(CATEGORIES)


def test_phase1_categoria_invalida_cae_a_xhr():
    digests = build_digests(extract_entries(_har_n(2)))
    raw = json.dumps({"entries": [
        {"idx": 0, "category": "inventada"},
        {"idx": 1, "category": "AUTH"},
    ]})
    out = parse_phase1_response(raw, digests)
    assert out["entries"][0]["category"] == "xhr"
    assert out["entries"][1]["category"] == "auth"  # normaliza mayusculas


def test_phase1_entry_no_clasificado_cae_a_xhr():
    digests = build_digests(extract_entries(_har_n(3)))
    raw = json.dumps({"entries": [{"idx": 0, "category": "navigation"}]})
    out = parse_phase1_response(raw, digests)
    assert len(out["entries"]) == 3
    assert out["entries"][1]["category"] == "xhr"
    assert "sin clasificar" in out["entries"][1]["reason"]


def test_phase1_acepta_lista_suelta():
    digests = build_digests(extract_entries(_har_n(2)))
    raw = json.dumps([{"idx": 0, "category": "auth"}, {"idx": 1, "category": "write"}])
    out = parse_phase1_response(raw, digests)
    assert out["counts"]["auth"] == 1
    assert out["counts"]["write"] == 1


def test_phase1_sin_ninguna_clasificacion_lanza_error():
    digests = build_digests(extract_entries(_har_n(2)))
    with pytest.raises(HarAnalysisError, match="no clasifico"):
        parse_phase1_response(json.dumps({"entries": []}), digests)


# ---------------------------------------------------------------------------
# Fase 2 — filtrado de categorias + dependencias
# ---------------------------------------------------------------------------


def test_navigation_queda_fuera_de_la_fase_2():
    assert "navigation" not in FUNCTIONAL_CATEGORIES
    digests = build_digests(extract_entries(_har_n(4)))
    classification = {"entries": [
        {"idx": 0, "category": "navigation"},
        {"idx": 1, "category": "auth"},
        {"idx": 2, "category": "xhr"},
        {"idx": 3, "category": "config"},
    ]}
    functional = filter_functional(digests, classification)
    assert [d["idx"] for d in functional] == [1, 2, 3]


def test_fase2_prompt_solo_lleva_los_entries_funcionales():
    digests = build_digests(extract_entries(_har_n(3)))
    classification = {"entries": [
        {"idx": 0, "category": "navigation"},
        {"idx": 1, "category": "auth"},
        {"idx": 2, "category": "write"},
    ]}
    functional = filter_functional(digests, classification)
    messages = build_phase2_messages(functional, {1: "auth", 2: "write"})
    user_content = messages[-1]["content"]
    assert '"idx": 1' in user_content or '"idx":1' in user_content
    assert "/home" not in user_content  # el entry de navigation no viaja


def test_phase2_parsea_dependencias():
    deps = parse_phase2_response(json.dumps({"dependencies": [{
        "source_idx": 1, "target_idx": 4, "data_name": "access_token",
        "locations": ["response.body.access_token", "request.header.Authorization"],
        "extractor_hint": "JSON Extractor $.access_token", "confidence": "high",
    }]}), valid_idx={1, 4})
    assert len(deps) == 1
    assert deps[0]["data_name"] == "access_token"
    assert deps[0]["confidence"] == "high"
    assert len(deps[0]["locations"]) == 2


def test_phase2_descarta_dependencia_hacia_atras():
    deps = parse_phase2_response(json.dumps({"dependencies": [
        {"source_idx": 5, "target_idx": 2, "data_name": "x"},
        {"source_idx": 3, "target_idx": 3, "data_name": "y"},
    ]}), valid_idx={2, 3, 5})
    assert deps == []


def test_phase2_descarta_idx_fuera_del_universo_enviado():
    deps = parse_phase2_response(json.dumps({"dependencies": [
        {"source_idx": 1, "target_idx": 99, "data_name": "x"},
    ]}), valid_idx={1, 2})
    assert deps == []


def test_phase2_normaliza_locations_string_y_confidence():
    deps = parse_phase2_response(json.dumps({"dependencies": [
        {"source_idx": 1, "target_idx": 2, "data_name": "csrf",
         "locations": "response.body.csrf", "confidence": "altisima"},
    ]}), valid_idx={1, 2})
    assert deps[0]["locations"] == ["response.body.csrf"]
    assert deps[0]["confidence"] == "medium"


def test_phase2_lista_vacia_es_resultado_valido():
    assert parse_phase2_response('{"dependencies": []}', valid_idx={1, 2}) == []


# ---------------------------------------------------------------------------
# Orquestacion completa
# ---------------------------------------------------------------------------


def test_flujo_completo_persiste_clasificacion_y_dependencias():
    har = _har_n(25)
    ai = _AIStub(
        _phase1_ok(25, "xhr"),
        json.dumps({"dependencies": [{
            "source_idx": 1, "target_idx": 5, "data_name": "access_token",
            "locations": ["response.body.access_token"],
            "extractor_hint": "JSON Extractor", "confidence": "high",
        }]}),
    )
    out = analyze_har_flow(har, ai)

    assert out["status"] == STATUS_COMPLETED
    assert out["error"] is None
    assert len(ai.calls) == 2  # dos llamadas separadas al modelo
    assert out["classification"]["total_entries"] == 25
    assert out["classification"]["counts"]["navigation"] == 1
    assert out["classification"]["counts"]["xhr"] == 24
    assert out["classification"]["source_sha1"] == source_fingerprint(har)
    assert out["dependencies"]["analyzed_entries"] == 24
    assert len(out["dependencies"]["dependencies"]) == 1


def test_fase2_fallida_retiene_la_fase_1():
    ai = _AIStub(_phase1_ok(25), RuntimeError("502 del proveedor"))
    out = analyze_har_flow(_har_n(25), ai)

    assert out["status"] == STATUS_FAILED
    assert out["classification"] is not None          # Fase 1 se conserva
    assert out["classification"]["counts"]["xhr"] == 24
    assert out["classification"]["phase2_error"] == "502 del proveedor"
    assert out["dependencies"] is None
    assert "Fase 2" in out["error"]


def test_fase2_con_json_basura_retiene_la_fase_1():
    ai = _AIStub(_phase1_ok(25), "lo siento, no puedo ayudarte con eso")
    out = analyze_har_flow(_har_n(25), ai)
    assert out["status"] == STATUS_FAILED
    assert out["classification"]["counts"]["xhr"] == 24
    assert out["dependencies"] is None


def test_fase1_fallida_no_persiste_nada():
    ai = _AIStub(RuntimeError("timeout"))
    out = analyze_har_flow(_har_n(25), ai)
    assert out["status"] == STATUS_FAILED
    assert out["classification"] is None
    assert out["dependencies"] is None
    assert "Fase 1" in out["error"]


def test_har_solo_navigation_completa_con_dependencias_vacias():
    n = 22
    ai = _AIStub(json.dumps({"entries": [
        {"idx": i, "category": "navigation"} for i in range(n)
    ]}))
    out = analyze_har_flow(_har_n(n), ai)
    assert out["status"] == STATUS_COMPLETED
    assert out["dependencies"]["dependencies"] == []
    assert len(ai.calls) == 1  # sin funcionales, no hay segunda llamada


def test_har_ilegible_propaga_error_controlado():
    with pytest.raises(HarAnalysisError):
        analyze_har_flow("{roto", _AIStub())


def test_source_fingerprint_distingue_contenido():
    assert source_fingerprint(_har_n(20)) == source_fingerprint(_har_n(20))
    assert source_fingerprint(_har_n(20)) != source_fingerprint(_har_n(21))
