"""
Tests del regenerador AIScriptStructure → JMX.
Fixture: backend/tests/fixtures/Ejercicio_Booking.jmx
"""
import pytest
from pathlib import Path

from app.services.engine.jmx_to_structure import parse_jmx_to_structure
from app.services.engine.structure_to_jmx import regenerate_jmx_from_structure
from app.schemas.ai_script_structure import AIScriptStructure


SAMPLE_JMX_PATH = Path(__file__).parent / "fixtures" / "Ejercicio_Booking.jmx"


@pytest.fixture(scope="module")
def original_structure() -> AIScriptStructure:
    jmx = SAMPLE_JMX_PATH.read_text(encoding="utf-8")
    return parse_jmx_to_structure(jmx)


# ============================================================================
# Smoke tests del regenerador
# ============================================================================

def test_regenerator_no_lanza_excepcion(original_structure):
    """Regenerar el JMX original debe producir XML válido sin errores."""
    jmx_out = regenerate_jmx_from_structure(original_structure)
    assert jmx_out is not None
    assert len(jmx_out) > 1000
    assert "<jmeterTestPlan" in jmx_out


def test_regenerator_produce_xml_valido(original_structure):
    """El XML generado debe ser parseable por lxml."""
    from lxml import etree
    jmx_out = regenerate_jmx_from_structure(original_structure)
    root = etree.fromstring(jmx_out.encode("utf-8"))
    assert root.tag == "jmeterTestPlan"


# ============================================================================
# Round-trip: parse → regenerate → parse → mismo conteo
# ============================================================================

def test_roundtrip_conserva_thread_groups(original_structure):
    """Parsear, regenerar, re-parsear debe dar el mismo número de TGs."""
    jmx_out = regenerate_jmx_from_structure(original_structure)
    re_parsed = parse_jmx_to_structure(jmx_out)
    assert len(re_parsed.thread_groups) == len(original_structure.thread_groups), \
        f"TGs diferentes: original={len(original_structure.thread_groups)}, re-parsed={len(re_parsed.thread_groups)}"


def test_roundtrip_conserva_samplers(original_structure):
    """Conteo total de samplers debe coincidir tras round-trip."""
    def count_samplers(tgs):
        total = 0
        for tg in tgs:
            for ch in tg.children:
                if ch.type == "sampler":
                    total += 1
                elif ch.type == "controller" and ch.controller:
                    total += sum(1 for c in ch.controller.children if c.type == "sampler")
        return total

    original_count = count_samplers(original_structure.thread_groups)
    jmx_out = regenerate_jmx_from_structure(original_structure)
    re_parsed = parse_jmx_to_structure(jmx_out)
    new_count = count_samplers(re_parsed.thread_groups)

    assert new_count == original_count, f"Samplers: original={original_count}, re-parsed={new_count}"


def test_roundtrip_conserva_csv_data_sets(original_structure):
    jmx_out = regenerate_jmx_from_structure(original_structure)
    re_parsed = parse_jmx_to_structure(jmx_out)
    assert len(re_parsed.csv_data_sets) == len(original_structure.csv_data_sets)


def test_roundtrip_conserva_udvs(original_structure):
    jmx_out = regenerate_jmx_from_structure(original_structure)
    re_parsed = parse_jmx_to_structure(jmx_out)
    original_names = {v.name for v in original_structure.user_defined_variables}
    new_names = {v.name for v in re_parsed.user_defined_variables}
    assert original_names == new_names, f"UDVs perdidas: {original_names - new_names}"


def test_roundtrip_conserva_listeners(original_structure):
    jmx_out = regenerate_jmx_from_structure(original_structure)
    re_parsed = parse_jmx_to_structure(jmx_out)
    assert len(re_parsed.listeners) == len(original_structure.listeners)


def test_roundtrip_conserva_stepping_config(original_structure):
    """Los nombres XML del stepping deben preservarse tras round-trip."""
    stepping_tg = next((tg for tg in original_structure.thread_groups if tg.kind == "stepping"), None)
    assert stepping_tg is not None
    original_stepping = stepping_tg.stepping

    jmx_out = regenerate_jmx_from_structure(original_structure)

    # Verificar que el XML contiene los nombres con espacios
    assert 'name="Start users count"' in jmx_out
    assert 'name="rampUp"' in jmx_out
    assert 'name="flighttime"' in jmx_out

    re_parsed = parse_jmx_to_structure(jmx_out)
    new_stepping_tg = next(tg for tg in re_parsed.thread_groups if tg.kind == "stepping")
    assert new_stepping_tg.stepping.start_users_count == original_stepping.start_users_count
    assert new_stepping_tg.stepping.ramp_up == original_stepping.ramp_up
    assert new_stepping_tg.stepping.flight_time == original_stepping.flight_time


# ============================================================================
# Edit-preserving: editar un campo y verificar que solo eso cambia
# ============================================================================

def test_edit_sampler_url_se_refleja_en_regen(original_structure):
    """Editar la URL de un sampler debe reflejarse en el JMX regenerado."""
    # Tomar el primer sampler del primer TG
    tg = original_structure.thread_groups[0]
    sampler = None
    for ch in tg.children:
        if ch.type == "sampler" and ch.sampler:
            sampler = ch.sampler
            break
    assert sampler is not None

    # Editar path y marcar dirty
    original_path = sampler.path
    sampler.path = "/new-edited-path"
    sampler.is_dirty = True

    jmx_out = regenerate_jmx_from_structure(original_structure)
    assert "/new-edited-path" in jmx_out, "El path editado no aparece en el regenerado"

    # Restaurar para no afectar otros tests
    sampler.path = original_path
    sampler.is_dirty = False


def test_no_dirty_reusa_raw_xml(original_structure):
    """Si is_dirty=False, debe reusar el raw_xml del sampler."""
    tg = original_structure.thread_groups[0]
    sampler = next(ch.sampler for ch in tg.children if ch.type == "sampler" and ch.sampler)

    # Modificar el modelo PERO mantener is_dirty=False (caso edge)
    sampler.is_dirty = False
    sampler.path = "/this-should-NOT-appear"  # no dirty → se ignora

    jmx_out = regenerate_jmx_from_structure(original_structure)
    # El path editado NO debe aparecer porque is_dirty=False y se reusa raw_xml
    # (el raw_xml original tiene la path original)
    assert "/this-should-NOT-appear" not in jmx_out, "raw_xml no se reusó"


def test_dirty_descendiente_invalida_cache_padre(original_structure):
    """
    Si un sampler tiene is_dirty=False pero su HeaderManager hijo está dirty,
    el sampler debe re-construirse para reflejar el cambio.
    """
    tg = original_structure.thread_groups[0]
    sampler = next(ch.sampler for ch in tg.children if ch.type == "sampler" and ch.sampler)

    # Encontrar HeaderManager hijo
    hm_child = next((c for c in sampler.children if c.type == "header_manager"), None)
    if hm_child is None:
        pytest.skip("Sampler sin HeaderManager para probar")

    # Editar header y marcar HIJO dirty pero PADRE limpio
    if hm_child.data.headers:
        hm_child.data.headers[0].value = "NEW-CUSTOM-VALUE"
        hm_child.data.is_dirty = True
        sampler.is_dirty = False  # padre limpio

    jmx_out = regenerate_jmx_from_structure(original_structure)
    assert "NEW-CUSTOM-VALUE" in jmx_out, "Cambio en hijo dirty no se reflejó"


# ============================================================================
# Edge cases
# ============================================================================

def test_structure_vacia_no_lanza(original_structure):
    """Una AIScriptStructure vacía debe regenerar XML mínimo válido."""
    s = AIScriptStructure()
    jmx_out = regenerate_jmx_from_structure(s)
    assert "<jmeterTestPlan" in jmx_out
    assert "<TestPlan" in jmx_out


def test_jmx_regenerado_es_valido_para_re_parse(original_structure):
    """El XML regenerado debe ser parseable sin errores por el propio parser."""
    jmx_out = regenerate_jmx_from_structure(original_structure)
    re_parsed = parse_jmx_to_structure(jmx_out)
    assert re_parsed is not None
    assert re_parsed.test_plan is not None
