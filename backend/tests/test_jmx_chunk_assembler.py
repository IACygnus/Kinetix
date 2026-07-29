"""Tests del ensamblador incremental de JMX (Sprint 3.0 — Fundacion 2).

El invariante que mas importa: **un fragmento malo nunca puede corromper el
JMX acumulado**. Varios tests verifican explicitamente que el string devuelto
en el camino de fallo es identico al de entrada.
"""
import xml.etree.ElementTree as ET

import pytest

from app.services.ai.jmx_chunk_assembler import (
    assemble_chunk_into_jmx,
    count_samplers,
    escape_bare_ampersands,
    extract_fragment_xml,
    find_thread_group_hashtree,
    prefix_testname,
    sanitize_generated_jmx,
    validate_jmx,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _jmx(samplers=1, listener=False, thread_group=True):
    """JMX minimo con la estructura real de JMeter 5.6.3."""
    body = ""
    for i in range(samplers):
        body += (
            f'<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" '
            f'testname="Request {i}" enabled="true">'
            f'<stringProp name="HTTPSampler.path">/x{i}</stringProp>'
            f"</HTTPSamplerProxy><hashTree/>"
        )
    if listener:
        body += (
            '<ResultCollector guiclass="ViewResultsFullVisualizer" '
            'testclass="ResultCollector" testname="Ver Resultados" enabled="true"/>'
            "<hashTree/>"
        )

    tg = (
        '<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" '
        'testname="Usuarios" enabled="true">'
        '<stringProp name="ThreadGroup.num_threads">10</stringProp>'
        f"</ThreadGroup><hashTree>{body}</hashTree>"
        if thread_group
        else ""
    )

    return (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">'
        "<hashTree>"
        '<TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Plan" enabled="true"/>'
        f"<hashTree>{tg}</hashTree>"
        "</hashTree></jmeterTestPlan>"
    )


def _fragment(n=1, start=100):
    out = ""
    for i in range(start, start + n):
        out += (
            f'<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" '
            f'testname="Nuevo {i}" enabled="true">'
            f'<stringProp name="HTTPSampler.path">/nuevo{i}</stringProp>'
            f"</HTTPSamplerProxy><hashTree/>"
        )
    return out


# ---------------------------------------------------------------------------
# Extraccion del fragmento
# ---------------------------------------------------------------------------


def test_extract_fragment_acepta_xml_limpio():
    assert extract_fragment_xml("<a/>") == "<a/>"


def test_extract_fragment_desenvuelve_markdown():
    assert extract_fragment_xml("```xml\n<a/>\n```") == "<a/>"
    assert extract_fragment_xml("```\n<a/>\n```") == "<a/>"


def test_extract_fragment_recorta_prosa_alrededor():
    assert extract_fragment_xml("Aca van:\n<a/>\nEso es todo.") == "<a/>"


def test_escapa_ampersands_crudos_de_urls():
    """El fallo mas comun del modelo: query string sin escapar."""
    assert escape_bare_ampersands("a=1&b=2") == "a=1&amp;b=2"
    assert escape_bare_ampersands("x&y&z") == "x&amp;y&amp;z"


def test_no_re_escapa_entidades_validas():
    for ya_valido in ("&amp;", "&lt;", "&gt;", "&quot;", "&#38;", "&#x26;"):
        assert escape_bare_ampersands(ya_valido) == ya_valido
    assert escape_bare_ampersands("a=1&amp;b=2&c=3") == "a=1&amp;b=2&amp;c=3"


def test_fragmento_con_ampersand_crudo_se_ensambla():
    """Antes del saneo esto reventaba con 'not well-formed (invalid token)'."""
    frag = (
        '<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" '
        'testname="Busqueda" enabled="true">'
        '<stringProp name="HTTPSampler.path">/api/items?page=1&size=20&sort=asc</stringProp>'
        "</HTTPSamplerProxy><hashTree/>"
    )
    ok, jmx, reason = assemble_chunk_into_jmx(_jmx(samplers=1), frag, 4)

    assert ok is True, reason
    assert count_samplers(jmx) == 2
    assert "page=1&amp;size=20&amp;sort=asc" in jmx
    assert validate_jmx(jmx)[0] is True


def test_el_saneo_no_rescata_un_fragmento_realmente_roto():
    base = _jmx()
    ok, jmx, reason = assemble_chunk_into_jmx(base, "<a><b></a>", 2)
    assert ok is False
    assert jmx == base


def test_sanitize_generated_jmx_aplica_el_mismo_criterio():
    assert sanitize_generated_jmx("<a p='x&y'/>") == "<a p='x&amp;y'/>"
    assert sanitize_generated_jmx(None) == ""


def test_extract_fragment_vacio_o_sin_xml():
    assert extract_fragment_xml("") == ""
    assert extract_fragment_xml(None) == ""
    assert extract_fragment_xml("no hay xml aca") == ""


# ---------------------------------------------------------------------------
# Localizacion del Thread Group
# ---------------------------------------------------------------------------


def test_encuentra_el_hashtree_del_thread_group():
    root = ET.fromstring(_jmx(samplers=2))
    container = find_thread_group_hashtree(root)
    assert container.tag == "hashTree"
    assert len(container.findall("HTTPSamplerProxy")) == 2


def test_reconoce_variantes_de_thread_group():
    jmx = _jmx().replace("ThreadGroup", "SetupThreadGroup")
    root = ET.fromstring(jmx)
    assert find_thread_group_hashtree(root) is not None


# ---------------------------------------------------------------------------
# Prefijos
# ---------------------------------------------------------------------------


def test_prefija_el_testname():
    elem = ET.fromstring('<HTTPSamplerProxy testname="Login"/>')
    prefix_testname(elem, 3)
    assert elem.get("testname") == "[C3] Login"


def test_no_re_prefija_un_elemento_ya_prefijado():
    elem = ET.fromstring('<HTTPSamplerProxy testname="[C2] Login"/>')
    prefix_testname(elem, 5)
    assert elem.get("testname") == "[C2] Login"  # intacto


def test_elemento_sin_testname_no_revienta():
    elem = ET.fromstring("<hashTree/>")
    prefix_testname(elem, 1)
    assert elem.get("testname") is None


# ---------------------------------------------------------------------------
# Ensamblado — camino feliz
# ---------------------------------------------------------------------------


def test_ensambla_un_sampler_en_el_thread_group():
    base = _jmx(samplers=1)
    ok, jmx, reason = assemble_chunk_into_jmx(base, _fragment(1), 2)

    assert ok is True
    assert count_samplers(jmx) == 2
    assert "[C2] Nuevo 100" in jmx
    assert validate_jmx(jmx)[0] is True


def test_ensambla_multiples_samplers_de_un_solo_fragmento():
    ok, jmx, _ = assemble_chunk_into_jmx(_jmx(samplers=2), _fragment(5), 3)
    assert ok is True
    assert count_samplers(jmx) == 7
    for i in range(100, 105):
        assert f"[C3] Nuevo {i}" in jmx


def test_los_samplers_nuevos_quedan_dentro_del_thread_group():
    ok, jmx, _ = assemble_chunk_into_jmx(_jmx(samplers=1), _fragment(2), 2)
    container = find_thread_group_hashtree(ET.fromstring(jmx))
    nombres = [e.get("testname") for e in container.findall("HTTPSamplerProxy")]
    assert nombres == ["Request 0", "[C2] Nuevo 100", "[C2] Nuevo 101"]


def test_ensamblados_sucesivos_acumulan():
    jmx = _jmx(samplers=1)
    for chunk_id, start in ((2, 100), (3, 200), (4, 300)):
        ok, jmx, _ = assemble_chunk_into_jmx(jmx, _fragment(2, start), chunk_id)
        assert ok is True
    assert count_samplers(jmx) == 7
    assert "[C2] Nuevo 100" in jmx and "[C3] Nuevo 200" in jmx and "[C4] Nuevo 300" in jmx


def test_preserva_la_declaracion_xml():
    ok, jmx, _ = assemble_chunk_into_jmx(_jmx(), _fragment(1), 2)
    assert jmx.startswith("<?xml")
    assert "encoding='utf-8'" in jmx or 'encoding="utf-8"' in jmx


def test_inserta_antes_de_los_listeners_del_final():
    ok, jmx, _ = assemble_chunk_into_jmx(_jmx(samplers=1, listener=True), _fragment(1), 2)
    container = find_thread_group_hashtree(ET.fromstring(jmx))
    tags = [e.tag for e in container]
    assert tags.index("HTTPSamplerProxy") < tags.index("ResultCollector")
    assert tags[-2:] == ["ResultCollector", "hashTree"]


def test_fragmento_con_fences_se_ensambla_igual():
    ok, jmx, _ = assemble_chunk_into_jmx(_jmx(), f"```xml\n{_fragment(1)}\n```", 2)
    assert ok is True
    assert count_samplers(jmx) == 2


# ---------------------------------------------------------------------------
# Ensamblado — el JMX previo NUNCA se corrompe
# ---------------------------------------------------------------------------


def test_fragmento_xml_invalido_devuelve_el_jmx_intacto():
    base = _jmx(samplers=3)
    ok, jmx, reason = assemble_chunk_into_jmx(base, "<HTTPSamplerProxy><sin cerrar", 2)

    assert ok is False
    assert jmx == base  # byte por byte
    assert "no es XML valido" in reason
    assert count_samplers(jmx) == 3


def test_fragmento_sin_xml_devuelve_el_jmx_intacto():
    base = _jmx(samplers=2)
    ok, jmx, reason = assemble_chunk_into_jmx(base, "Lo siento, no puedo generar eso", 2)
    assert ok is False
    assert jmx == base
    assert "no devolvio XML" in reason


def test_fragmento_vacio_devuelve_el_jmx_intacto():
    base = _jmx()
    for vacio in ("", None, "   "):
        ok, jmx, reason = assemble_chunk_into_jmx(base, vacio, 2)
        assert ok is False
        assert jmx == base


def test_jmx_base_corrupto_no_se_intenta_reparar():
    roto = "<jmeterTestPlan><hashTree>sin cerrar"
    ok, jmx, reason = assemble_chunk_into_jmx(roto, _fragment(1), 2)
    assert ok is False
    assert jmx == roto
    assert "no es XML valido" in reason


def test_sin_thread_group_falla_sin_tocar_nada():
    base = _jmx(thread_group=False)
    ok, jmx, reason = assemble_chunk_into_jmx(base, _fragment(1), 2)
    assert ok is False
    assert jmx == base
    assert "Thread Group" in reason


def test_sin_jmx_base_falla():
    ok, jmx, reason = assemble_chunk_into_jmx("", _fragment(1), 2)
    assert ok is False
    assert "No hay JMX base" in reason


# ---------------------------------------------------------------------------
# Validacion y conteo
# ---------------------------------------------------------------------------


def test_validate_jmx_acepta_un_plan_correcto():
    ok, reason = validate_jmx(_jmx(samplers=2))
    assert ok is True
    assert reason == "ok"


def test_validate_jmx_rechaza_xml_roto():
    assert validate_jmx("<jmeterTestPlan><sin cerrar")[0] is False


def test_validate_jmx_rechaza_raiz_equivocada():
    ok, reason = validate_jmx("<otraCosa><ThreadGroup/><hashTree/></otraCosa>")
    assert ok is False
    assert "jmeterTestPlan" in reason


def test_validate_jmx_rechaza_plan_sin_thread_group():
    ok, reason = validate_jmx(_jmx(thread_group=False))
    assert ok is False
    assert "Thread Group" in reason


def test_validate_jmx_rechaza_vacio():
    assert validate_jmx("")[0] is False
    assert validate_jmx(None)[0] is False


def test_count_samplers():
    assert count_samplers(_jmx(samplers=0)) == 0
    assert count_samplers(_jmx(samplers=4)) == 4
    assert count_samplers(None) == 0
