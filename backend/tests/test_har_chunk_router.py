"""Tests del router de chunks (Sprint 3.0 — Fundacion 2).

Los fixtures replican el shape REAL que persiste la Fundacion 1:
``har_analysis_classification`` con ``entries[{idx, method, url, category,
reason}]`` y ``har_analysis_dependencies`` con
``dependencies[{source_idx, target_idx, data_name, locations, extractor_hint,
confidence}]``.
"""
import json

import pytest

from app.services.ai.har_chunk_router import (
    _CHUNK_SIZE,
    _MAX_SPLIT_DEPTH,
    _MIN_FUNCTIONAL_FOR_CHUNKING,
    CHUNK_COMPLETED,
    CHUNK_PENDING,
    build_first_chunk_prompt,
    build_next_chunk_prompt,
    can_split_chunk,
    count_functional_entries,
    digests_for_chunk,
    get_dependencies_for_chunk,
    group_entries_into_chunks,
    next_free_chunk_id,
    should_use_chunked_generation,
    split_chunk,
    variables_available_from,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _classification(categories):
    """categories: lista de categorias, una por idx."""
    return {
        "version": 1,
        "source_sha1": "abc",
        "total_entries": len(categories),
        "analyzed_entries": len(categories),
        "counts": {c: categories.count(c) for c in set(categories)},
        "entries": [
            {"idx": i, "method": "GET", "url": f"https://api.x/{i}",
             "category": c, "reason": "r"}
            for i, c in enumerate(categories)
        ],
        "phase2_error": None,
    }


def _mix(navigation=0, auth=0, config=0, xhr=0, write=0):
    """Categorias intercaladas para que los idx NO queden agrupados por tipo."""
    buckets = (
        ["navigation"] * navigation + ["auth"] * auth + ["config"] * config
        + ["xhr"] * xhr + ["write"] * write
    )
    # intercala: navigation, auth, config, xhr, write, navigation, ...
    out = []
    pools = {
        "navigation": ["navigation"] * navigation,
        "auth": ["auth"] * auth,
        "config": ["config"] * config,
        "xhr": ["xhr"] * xhr,
        "write": ["write"] * write,
    }
    while any(pools.values()):
        for key in ("navigation", "auth", "config", "xhr", "write"):
            if pools[key]:
                out.append(pools[key].pop())
    assert len(out) == len(buckets)
    return out


def _deps(*triples):
    """triples: (source_idx, target_idx, data_name)."""
    return {
        "version": 1,
        "analyzed_entries": 10,
        "dependencies": [
            {
                "source_idx": s, "target_idx": t, "data_name": n,
                "locations": [f"response.body.{n}", "request.header.Authorization"],
                "extractor_hint": f"JSON Extractor sobre $.{n}",
                "confidence": "high",
            }
            for s, t, n in triples
        ],
    }


def _har_entries(n):
    return [
        {"request": {"method": "GET", "url": f"https://api.x/{i}",
                     "headers": [{"name": "content-type", "value": "application/json"}]},
         "response": {"status": 200}}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Umbral
# ---------------------------------------------------------------------------


def test_umbral_de_chunking_es_mayor_a_30():
    assert _MIN_FUNCTIONAL_FOR_CHUNKING == 30


def test_navigation_no_cuenta_para_el_umbral():
    """Criterio de F1: FUNCTIONAL_CATEGORIES excluye navigation."""
    c = _classification(_mix(navigation=50, xhr=5))
    assert count_functional_entries(c) == 5
    use, reason = should_use_chunked_generation(c)
    assert use is False
    assert "5 entries funcionales" in reason


def test_justo_en_el_umbral_no_chunkea():
    c = _classification(_mix(xhr=30))
    assert count_functional_entries(c) == 30
    assert should_use_chunked_generation(c)[0] is False


def test_uno_mas_que_el_umbral_si_chunkea():
    c = _classification(_mix(xhr=31))
    use, reason = should_use_chunked_generation(c)
    assert use is True
    assert "31 entries funcionales" in reason


def test_sin_clasificacion_no_chunkea_y_avisa():
    for bad in (None, {}, {"entries": []}, "nope"):
        use, reason = should_use_chunked_generation(bad)
        assert use is False
        assert "analyze-har" in reason


def test_todas_las_categorias_funcionales_suman():
    c = _classification(_mix(auth=10, write=10, xhr=10, config=10, navigation=99))
    assert count_functional_entries(c) == 40


# ---------------------------------------------------------------------------
# Agrupacion
# ---------------------------------------------------------------------------


def test_primer_chunk_es_auth_navigation_config_y_es_esqueleto():
    c = _classification(_mix(navigation=3, auth=2, config=4, xhr=40))
    plan = group_entries_into_chunks(c, None)
    first = plan[0]
    assert first["chunk_id"] == 1
    assert first["is_skeleton"] is True
    assert set(first["categories"]) == {"auth", "navigation", "config"}
    assert len(first["entry_idxs"]) == 3 + 2 + 4
    cats = {e["idx"]: e["category"] for e in c["entries"]}
    assert all(cats[i] in ("auth", "navigation", "config") for i in first["entry_idxs"])


def test_chunks_siguientes_son_xhr_y_write_de_a_15():
    c = _classification(_mix(auth=2, xhr=40, write=5))
    plan = group_entries_into_chunks(c, None)
    rest = plan[1:]
    assert len(rest) == 3  # 45 entries / 15
    assert [len(ch["entry_idxs"]) for ch in rest] == [15, 15, 15]
    assert all(ch["is_skeleton"] is False for ch in rest)
    assert all(set(ch["categories"]) == {"xhr", "write"} for ch in rest)


def test_chunk_size_por_defecto_es_15():
    assert _CHUNK_SIZE == 15


def test_ids_incrementales_sin_huecos():
    c = _classification(_mix(auth=3, xhr=50))
    plan = group_entries_into_chunks(c, None)
    assert [ch["chunk_id"] for ch in plan] == list(range(1, len(plan) + 1))


def test_ningun_entry_se_pierde_ni_se_duplica():
    c = _classification(_mix(navigation=7, auth=4, config=6, xhr=48, write=9))
    plan = group_entries_into_chunks(c, None)
    todos = [i for ch in plan for i in ch["entry_idxs"]]
    assert sorted(todos) == list(range(len(c["entries"])))
    assert len(todos) == len(set(todos))  # sin duplicados


def test_entries_conservan_el_orden_del_har_dentro_del_chunk():
    c = _classification(_mix(auth=2, xhr=30))
    plan = group_entries_into_chunks(c, None)
    for ch in plan:
        assert ch["entry_idxs"] == sorted(ch["entry_idxs"])


def test_ultimo_bloque_puede_ser_parcial():
    c = _classification(_mix(auth=1, xhr=17))
    plan = group_entries_into_chunks(c, None)
    assert [len(ch["entry_idxs"]) for ch in plan] == [1, 15, 2]


def test_sin_entries_de_esqueleto_el_primer_bloque_hace_de_esqueleto():
    c = _classification(_mix(xhr=20))
    plan = group_entries_into_chunks(c, None)
    assert plan[0]["chunk_id"] == 1
    assert plan[0]["is_skeleton"] is True
    assert set(plan[0]["categories"]) == {"xhr", "write"}


def test_todos_los_chunks_arrancan_pending():
    plan = group_entries_into_chunks(_classification(_mix(auth=2, xhr=30)), None)
    assert all(ch["status"] == CHUNK_PENDING for ch in plan)
    assert all(ch["failure_reason"] is None for ch in plan)


def test_categoria_desconocida_no_se_pierde():
    c = _classification(["auth", "xhr", "categoria_del_futuro", "write"])
    plan = group_entries_into_chunks(c, None)
    todos = [i for ch in plan for i in ch["entry_idxs"]]
    assert 2 in todos


def test_chunk_size_configurable():
    c = _classification(_mix(auth=1, xhr=20))
    plan = group_entries_into_chunks(c, None, chunk_size=5)
    assert [len(ch["entry_idxs"]) for ch in plan] == [1, 5, 5, 5, 5]


# ---------------------------------------------------------------------------
# Auto-split (Sprint 3.0 F2.1)
# ---------------------------------------------------------------------------


def _chunk(idxs, chunk_id=4, depth=0, skeleton=False, name=None):
    return {
        "chunk_id": chunk_id,
        "name": name or f"Chunk {chunk_id} - Transacciones 3/6",
        "entry_idxs": list(idxs),
        "categories": ["xhr", "write"],
        "status": CHUNK_PENDING,
        "is_skeleton": skeleton,
        "failure_reason": None,
        "split_depth": depth,
        "parent_chunk_id": None,
    }


def test_profundidad_maxima_de_split_es_2():
    assert _MAX_SPLIT_DEPTH == 2


def test_next_free_chunk_id_es_el_siguiente_entero():
    plan = group_entries_into_chunks(_classification(_mix(auth=2, xhr=30)), None)
    assert next_free_chunk_id(plan) == len(plan) + 1
    assert next_free_chunk_id([]) == 1


def test_split_parte_por_la_mitad_preservando_el_orden():
    a, b = split_chunk(_chunk(range(10, 25)), next_chunk_id=8)
    assert a["entry_idxs"] == list(range(10, 17))   # 7
    assert b["entry_idxs"] == list(range(17, 25))   # 8
    assert a["entry_idxs"] == sorted(a["entry_idxs"])
    assert b["entry_idxs"] == sorted(b["entry_idxs"])


def test_la_union_de_los_hijos_es_exactamente_el_padre():
    padre = _chunk([3, 1, 9, 7, 5])  # desordenado a proposito
    a, b = split_chunk(padre, next_chunk_id=8)
    union = a["entry_idxs"] + b["entry_idxs"]
    assert sorted(union) == sorted(padre["entry_idxs"])
    assert len(union) == len(set(union))  # sin duplicados


def test_split_de_un_par_da_mitades_iguales():
    a, b = split_chunk(_chunk(range(8)), next_chunk_id=20)
    assert len(a["entry_idxs"]) == len(b["entry_idxs"]) == 4


def test_los_hijos_reciben_ids_nuevos_consecutivos():
    a, b = split_chunk(_chunk(range(6), chunk_id=4), next_chunk_id=12)
    assert (a["chunk_id"], b["chunk_id"]) == (12, 13)
    assert a["parent_chunk_id"] == b["parent_chunk_id"] == 4


def test_los_hijos_incrementan_la_profundidad():
    a, b = split_chunk(_chunk(range(8), depth=0), next_chunk_id=9)
    assert a["split_depth"] == b["split_depth"] == 1
    nieto_a, nieto_b = split_chunk(a, next_chunk_id=11)
    assert nieto_a["split_depth"] == nieto_b["split_depth"] == 2


def test_los_hijos_arrancan_pending_y_sin_motivo_de_fallo():
    for hijo in split_chunk(_chunk(range(6)), next_chunk_id=8):
        assert hijo["status"] == CHUNK_PENDING
        assert hijo["failure_reason"] is None


def test_el_nombre_del_hijo_referencia_al_padre():
    a, b = split_chunk(_chunk(range(6), chunk_id=4), next_chunk_id=8)
    assert "mitad 1/2 de C4" in a["name"]
    assert "mitad 2/2 de C4" in b["name"]
    assert "Transacciones 3/6" in a["name"]


def test_solo_el_primer_hijo_hereda_el_rol_de_esqueleto():
    a, b = split_chunk(_chunk(range(6), skeleton=True), next_chunk_id=8)
    assert a["is_skeleton"] is True   # sigue teniendo que generar el JMX
    assert b["is_skeleton"] is False  # se ensambla dentro de lo que genero A


def test_un_chunk_de_un_solo_entry_no_se_parte():
    assert split_chunk(_chunk([7]), next_chunk_id=8) is None
    ok, motivo = can_split_chunk(_chunk([7]))
    assert ok is False
    assert "un solo request" in motivo
    assert "revision manual" in motivo


def test_un_chunk_vacio_no_se_parte():
    assert split_chunk(_chunk([]), next_chunk_id=8) is None


def test_no_se_parte_mas_alla_de_la_profundidad_maxima():
    hondo = _chunk(range(4), depth=_MAX_SPLIT_DEPTH)
    assert split_chunk(hondo, next_chunk_id=8) is None
    ok, motivo = can_split_chunk(hondo)
    assert ok is False
    assert f"se partio {_MAX_SPLIT_DEPTH} veces" in motivo


def test_a_profundidad_uno_todavia_se_puede_partir():
    assert can_split_chunk(_chunk(range(8), depth=1))[0] is True
    assert split_chunk(_chunk(range(8), depth=1), next_chunk_id=8) is not None


def test_cadena_completa_15_a_8_a_4_no_pierde_entries():
    padre = _chunk(range(15))
    a, b = split_chunk(padre, 8)
    a1, a2 = split_chunk(a, 10)
    todos = a1["entry_idxs"] + a2["entry_idxs"] + b["entry_idxs"]
    assert sorted(todos) == list(range(15))
    assert len(todos) == len(set(todos))


def test_los_chunks_frescos_traen_linaje_vacio():
    plan = group_entries_into_chunks(_classification(_mix(auth=2, xhr=30)), None)
    assert all(c["split_depth"] == 0 for c in plan)
    assert all(c["parent_chunk_id"] is None for c in plan)


def test_variables_disponibles_con_hijos_de_split_intercalados():
    """Los hijos tienen IDs altos pero van antes en el plan: cuenta la posicion."""
    plan = [
        {"chunk_id": 1, "entry_idxs": [0], "status": CHUNK_COMPLETED},
        {"chunk_id": 8, "entry_idxs": [1], "status": CHUNK_COMPLETED},   # hijo
        {"chunk_id": 9, "entry_idxs": [2], "status": CHUNK_COMPLETED},   # hijo
        {"chunk_id": 5, "entry_idxs": [3], "status": CHUNK_PENDING},
    ]
    deps = _deps((1, 3, "token_del_hijo"))
    disponibles = variables_available_from(plan, deps, up_to_chunk_id=5)
    assert [v["data_name"] for v in disponibles] == ["token_del_hijo"]


# ---------------------------------------------------------------------------
# Dependencias por chunk
# ---------------------------------------------------------------------------


def test_produces_son_las_que_nacen_en_el_chunk():
    chunk = {"entry_idxs": [1, 2, 3]}
    out = get_dependencies_for_chunk(chunk, _deps((1, 9, "token"), (5, 9, "otro")))
    assert [d["data_name"] for d in out["produces"]] == ["token"]
    assert out["consumes"] == []


def test_consumes_son_las_que_vienen_de_afuera():
    chunk = {"entry_idxs": [8, 9]}
    out = get_dependencies_for_chunk(chunk, _deps((1, 9, "token")))
    assert [d["data_name"] for d in out["consumes"]] == ["token"]
    assert out["produces"] == []


def test_dependencia_interna_cuenta_como_produces_y_como_internal():
    chunk = {"entry_idxs": [1, 2, 3]}
    out = get_dependencies_for_chunk(chunk, _deps((1, 3, "csrf")))
    assert [d["data_name"] for d in out["produces"]] == ["csrf"]
    assert [d["data_name"] for d in out["internal"]] == ["csrf"]
    assert out["consumes"] == []


def test_dependencia_ajena_al_chunk_se_ignora():
    chunk = {"entry_idxs": [1, 2]}
    out = get_dependencies_for_chunk(chunk, _deps((7, 8, "nada")))
    assert out == {"produces": [], "consumes": [], "internal": []}


def test_sin_dependencias_devuelve_estructura_vacia():
    for bad in (None, {}, {"dependencies": None}, {"dependencies": "x"}):
        out = get_dependencies_for_chunk({"entry_idxs": [1]}, bad)
        assert out == {"produces": [], "consumes": [], "internal": []}


def test_variables_disponibles_solo_de_chunks_completados():
    plan = [
        {"chunk_id": 1, "entry_idxs": [0, 1], "status": CHUNK_COMPLETED},
        {"chunk_id": 2, "entry_idxs": [2, 3], "status": CHUNK_PENDING},
        {"chunk_id": 3, "entry_idxs": [4, 5], "status": CHUNK_PENDING},
    ]
    deps = _deps((1, 4, "token"), (2, 5, "order_id"))
    disponibles = variables_available_from(plan, deps, up_to_chunk_id=3)
    assert [v["data_name"] for v in disponibles] == ["token"]  # el chunk 2 no corrio


def test_variables_disponibles_deduplicadas():
    plan = [{"chunk_id": 1, "entry_idxs": [1], "status": CHUNK_COMPLETED}]
    deps = _deps((1, 5, "token"), (1, 7, "token"), (1, 9, "otro"))
    disponibles = variables_available_from(plan, deps, up_to_chunk_id=2)
    assert [v["data_name"] for v in disponibles] == ["token", "otro"]


def test_variables_disponibles_vacio_sin_chunks_completados():
    plan = [{"chunk_id": 1, "entry_idxs": [1], "status": CHUNK_PENDING}]
    assert variables_available_from(plan, _deps((1, 5, "t")), 2) == []


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------


def test_digests_del_chunk_reusan_entry_digest_de_f1():
    entries = _har_entries(10)
    c = _classification(["xhr"] * 10)
    digests = digests_for_chunk(entries, {"entry_idxs": [2, 5]}, c)
    assert [d["idx"] for d in digests] == [2, 5]
    assert digests[0]["url"].endswith("/2")
    assert digests[0]["category"] == "xhr"


def test_digests_ignoran_idx_fuera_de_rango():
    digests = digests_for_chunk(_har_entries(3), {"entry_idxs": [0, 99, -1]}, None)
    assert [d["idx"] for d in digests] == [0]


# ---------------------------------------------------------------------------
# Prompts (adaptativos, nada hardcodeado)
# ---------------------------------------------------------------------------


def test_prompt_del_primer_chunk_pide_jmx_completo_y_cuenta_real():
    digests = digests_for_chunk(_har_entries(7), {"entry_idxs": list(range(7))}, None)
    deps = get_dependencies_for_chunk({"entry_idxs": list(range(7))}, _deps((1, 20, "token")))
    messages = build_first_chunk_prompt(
        {"chunk_id": 1}, digests, deps, plan_name="Mi Plan", total_chunks=4
    )
    user = messages[-1]["content"]
    assert "bloque 1 de 4" in user
    assert "REQUESTS DE ESTE BLOQUE (7)" in user
    assert "Mi Plan" in user
    assert "Thread Group" in user
    assert "${token}" in user  # extractor obligatorio derivado de la dependencia


def test_prompt_del_primer_chunk_no_hardcodea_el_conteo():
    for n in (3, 11, 26):
        digests = digests_for_chunk(_har_entries(n), {"entry_idxs": list(range(n))}, None)
        user = build_first_chunk_prompt(
            {"chunk_id": 1}, digests, {"produces": [], "consumes": [], "internal": []}
        )[-1]["content"]
        assert f"REQUESTS DE ESTE BLOQUE ({n})" in user


def test_prompt_de_chunk_siguiente_prohibe_la_envoltura():
    digests = digests_for_chunk(_har_entries(5), {"entry_idxs": [0, 1, 2]}, None)
    user = build_next_chunk_prompt(
        {"chunk_id": 3}, digests,
        {"produces": [], "consumes": [], "internal": []},
        [{"data_name": "token", "extractor_hint": "JSON Extractor"}],
        total_chunks=6,
    )[-1]["content"]
    assert "bloque 3 de 6" in user
    assert "NO generes jmeterTestPlan" in user
    assert "${token}" in user
    assert "REQUESTS DE ESTE BLOQUE (3)" in user


def test_prompt_de_chunk_siguiente_sin_variables_previas_lo_dice():
    digests = digests_for_chunk(_har_entries(2), {"entry_idxs": [0]}, None)
    user = build_next_chunk_prompt(
        {"chunk_id": 2}, digests,
        {"produces": [], "consumes": [], "internal": []}, [],
    )[-1]["content"]
    assert "No hay variables extraidas por bloques anteriores" in user


def test_prompt_lista_variables_a_consumir_de_chunks_previos():
    digests = digests_for_chunk(_har_entries(12), {"entry_idxs": [10, 11]}, None)
    deps = get_dependencies_for_chunk({"entry_idxs": [10, 11]}, _deps((1, 11, "AccessToken")))
    user = build_next_chunk_prompt({"chunk_id": 2}, digests, deps, [])[-1]["content"]
    assert "VARIABLES QUE YA EXISTEN" in user
    assert "AccessToken" in user
    assert "NO vuelvas a crear el extractor" in user


def test_prompts_traen_system_de_jmeter():
    digests = digests_for_chunk(_har_entries(2), {"entry_idxs": [0]}, None)
    empty = {"produces": [], "consumes": [], "internal": []}
    for messages in (
        build_first_chunk_prompt({"chunk_id": 1}, digests, empty),
        build_next_chunk_prompt({"chunk_id": 2}, digests, empty, []),
    ):
        assert messages[0]["role"] == "system"
        assert "JMeter" in messages[0]["content"]
        assert messages[-1]["role"] == "user"
