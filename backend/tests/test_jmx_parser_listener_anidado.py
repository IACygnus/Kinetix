"""
Tests HF20a: el parser reconoce ResultCollector anidado dentro del Thread Group.

Referencia: docs/reports/diagnostico-regresiones-pre-sprint-3.0.md (Regresión 2, B1).
La IA suele emitir los listeners (View Results Tree, Summary Report, ...) DENTRO
del hashTree del Thread Group en vez de top-level. Antes de HF20a esos listeners
caían en el `else` de _parse_tg_children → UnsupportedElement → se renderizaban
como "unmapped" en el árbol. HF20a los mapea a structure.listeners[] con el mismo
shape que el dispatch top-level.

API real: parse_jmx_to_structure(jmx_text) -> AIScriptStructure (modelo Pydantic,
acceso por atributos, NO dict.get()).
"""
from app.services.engine.jmx_to_structure import parse_jmx_to_structure


JMX_LISTENER_ANIDADO = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <TestPlan testname="Test Plan"/>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="TG Main">
        <stringProp name="ThreadGroup.num_threads">1</stringProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="Sampler 1"/>
        <hashTree/>
        <ResultCollector guiclass="ViewResultsFullVisualizer" testclass="ResultCollector" testname="View Results Tree" enabled="true">
          <boolProp name="ResultCollector.error_logging">false</boolProp>
        </ResultCollector>
        <hashTree/>
        <ResultCollector guiclass="SummaryReport" testclass="ResultCollector" testname="Summary Report" enabled="true">
          <boolProp name="ResultCollector.error_logging">false</boolProp>
        </ResultCollector>
        <hashTree/>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>"""


JMX_LISTENER_TOPLEVEL = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <TestPlan testname="Test Plan"/>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="TG Main"/>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="Sampler 1"/>
        <hashTree/>
      </hashTree>
      <ResultCollector guiclass="ViewResultsFullVisualizer" testclass="ResultCollector" testname="VRT Top" enabled="true"/>
      <hashTree/>
    </hashTree>
  </hashTree>
</jmeterTestPlan>"""


def _sampler_children(tg):
    """Helper: devuelve los TGChild de tipo sampler de un thread group."""
    return [ch for ch in tg.children if ch.type == "sampler" and ch.sampler is not None]


def test_listener_anidado_en_tg_se_mapea_correctamente():
    """HF20a: ResultCollector anidado en TG aparece en listeners[], no en unmapped[]."""
    structure = parse_jmx_to_structure(JMX_LISTENER_ANIDADO)

    listener_names = [l.name for l in structure.listeners]
    unmapped_names = [u.name for u in structure.unmapped]

    # Reconoce los 2 listeners anidados
    assert len(structure.listeners) == 2, (
        f"Esperado 2 listeners, obtenido {len(structure.listeners)}: {listener_names}"
    )
    assert "View Results Tree" in listener_names
    assert "Summary Report" in listener_names

    # Ninguno debe quedar en unmapped top-level
    assert "View Results Tree" not in unmapped_names
    assert "Summary Report" not in unmapped_names


def test_listener_anidado_no_deja_unsupported_en_children():
    """HF20a: los listeners anidados no deben renderizar como 'unmapped' en el árbol del TG."""
    structure = parse_jmx_to_structure(JMX_LISTENER_ANIDADO)
    tg = structure.thread_groups[0]
    unsupported_children = [ch for ch in tg.children if ch.type == "unsupported"]
    assert unsupported_children == [], (
        f"No debe haber hijos unsupported en el TG, hay {len(unsupported_children)}"
    )


def test_listener_toplevel_sigue_funcionando():
    """Backward compat (Sprint 2.6): el listener top-level se sigue reconociendo."""
    structure = parse_jmx_to_structure(JMX_LISTENER_TOPLEVEL)
    assert len(structure.listeners) == 1
    assert structure.listeners[0].name == "VRT Top"


def test_listener_anidado_mantiene_atributo_enabled():
    """El campo enabled del ResultCollector anidado debe preservarse."""
    structure = parse_jmx_to_structure(JMX_LISTENER_ANIDADO)
    assert len(structure.listeners) == 2
    for l in structure.listeners:
        assert l.enabled is True


def test_listener_anidado_tiene_kind_mapeado():
    """Los listeners anidados deben mapear su kind vía _LISTENER_KIND_MAP (no 'other')."""
    structure = parse_jmx_to_structure(JMX_LISTENER_ANIDADO)
    kinds = {l.name: l.kind for l in structure.listeners}
    assert kinds.get("View Results Tree") == "view_results_tree"
    assert kinds.get("Summary Report") == "summary_report"


def test_no_regresion_estructura_completa_con_listener_anidado():
    """El JMX con listeners anidados conserva su thread group y sampler intactos."""
    structure = parse_jmx_to_structure(JMX_LISTENER_ANIDADO)

    assert len(structure.thread_groups) == 1
    tg = structure.thread_groups[0]

    samplers = _sampler_children(tg)
    assert len(samplers) == 1
    assert samplers[0].sampler.name == "Sampler 1"
