"""Tests del aplicador de operaciones del refine quirurgico (Sprint 2.4-HF5.1)."""
from pathlib import Path

import pytest

from app.schemas.refine_operations import (
    AddCsvDatasetOp,
    AddListenerOp,
    AddSamplerChildOp,
    AddSamplerOp,
    AddUdvOp,
    DeleteElementOp,
    EnableDisableOp,
    UpdateSamplerOp,
    UpdateThreadGroupOp,
    UpdateUdvsOp,
)
from app.services.engine.jmx_to_structure import parse_jmx_to_structure
from app.services.engine.refine_operations_applier import (
    OperationError,
    apply_operations,
)

SAMPLE_JMX_PATH = Path(__file__).parent / "fixtures" / "Ejercicio_Booking.jmx"


@pytest.fixture
def structure():
    jmx = SAMPLE_JMX_PATH.read_text(encoding="utf-8")
    return parse_jmx_to_structure(jmx)


def test_update_thread_group_ramp_time(structure):
    """HF5.2: ramp_time se aplica al campo ramp_time del modelo SOLO si el TG
    es standard. Sobre stepping se redirige a stepping.ramp_up (ver
    test_update_ramp_time_en_stepping_se_redirige).
    """
    tg = next(t for t in structure.thread_groups if t.kind == "standard")
    op = UpdateThreadGroupOp(id=str(tg.id), fields={"ramp_time": 99})
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    updated = next(t for t in result.thread_groups if str(t.id) == str(tg.id))
    assert updated.ramp_time == 99
    assert updated.is_dirty is True


def test_update_sampler_path(structure):
    sampler = None
    tg_idx = None
    for i, tg in enumerate(structure.thread_groups):
        for ch in tg.children:
            if ch.type == "sampler" and ch.sampler:
                sampler = ch.sampler
                tg_idx = i
                break
        if sampler:
            break
    assert sampler is not None

    op = UpdateSamplerOp(id=str(sampler.id), fields={"path": "/new-path"})
    result, applied = apply_operations(structure, [op])
    assert applied == 1

    updated = next(
        ch.sampler
        for ch in result.thread_groups[tg_idx].children
        if ch.type == "sampler" and ch.sampler and str(ch.sampler.id) == str(sampler.id)
    )
    assert updated.path == "/new-path"
    assert updated.is_dirty is True


def test_update_udvs_reemplaza_lista(structure):
    op = UpdateUdvsOp(
        udvs=[
            {"name": "host", "value": "nuevo.example.com"},
            {"name": "scheme", "value": "https"},
        ]
    )
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    assert len(result.user_defined_variables) == 2
    assert result.user_defined_variables[0].name == "host"
    assert result.user_defined_variables[0].value == "nuevo.example.com"


def test_disable_thread_group(structure):
    tg_id = str(structure.thread_groups[0].id)
    op = EnableDisableOp(target_kind="thread_group", id=tg_id, enabled=False)
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    assert result.thread_groups[0].enabled is False


def test_update_inexistente_lanza_error(structure):
    op = UpdateThreadGroupOp(id="id-que-no-existe", fields={"ramp_time": 99})
    with pytest.raises(OperationError):
        apply_operations(structure, [op])


def test_multiple_operaciones_orden(structure):
    """HF5.2: ramp_time sobre standard TG aplicado dos veces — gana el último."""
    standard_tg = next(t for t in structure.thread_groups if t.kind == "standard")
    tg_id = str(standard_tg.id)
    ops = [
        UpdateThreadGroupOp(id=tg_id, fields={"ramp_time": 10}),
        UpdateThreadGroupOp(id=tg_id, fields={"ramp_time": 20}),
    ]
    result, applied = apply_operations(structure, ops)
    assert applied == 2
    updated = next(t for t in result.thread_groups if str(t.id) == tg_id)
    # last write wins
    assert updated.ramp_time == 20


def test_update_stepping_anidado(structure):
    stepping_tg = next(
        (t for t in structure.thread_groups if t.kind == "stepping"), None
    )
    if stepping_tg is None:
        pytest.skip("Fixture sin TG stepping")

    op = UpdateThreadGroupOp(
        id=str(stepping_tg.id),
        fields={"stepping": {"start_users_count": 5, "flight_time": 120}},
    )
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    updated = next(
        t for t in result.thread_groups if str(t.id) == str(stepping_tg.id)
    )
    assert updated.stepping.start_users_count == 5
    assert updated.stepping.flight_time == 120


def test_update_sampler_body_merge(structure):
    sampler = None
    for tg in structure.thread_groups:
        for ch in tg.children:
            if ch.type == "sampler" and ch.sampler and ch.sampler.method.upper() in ("POST", "PUT"):
                sampler = ch.sampler
                break
        if sampler:
            break
    if sampler is None:
        pytest.skip("No POST/PUT samplers en el fixture")

    op = UpdateSamplerOp(
        id=str(sampler.id),
        fields={"body": {"raw_text": "{\"updated\": true}"}},
    )
    _, applied = apply_operations(structure, [op])
    assert applied == 1
    # The body sub-object must have been merged, not replaced wholesale
    found = None
    for tg in structure.thread_groups:
        for ch in tg.children:
            if ch.type == "sampler" and ch.sampler and str(ch.sampler.id) == str(sampler.id):
                found = ch.sampler
                break
        if found:
            break
    assert found is not None
    assert found.body.raw_text == "{\"updated\": true}"
    assert found.is_dirty is True


# ============================================================================
# Sprint 2.4-HF5.2 — kind-awareness para Thread Groups
# ============================================================================


def test_update_ramp_time_en_stepping_se_redirige(structure):
    """HF5.2: ramp_time sobre TG stepping debe redirigirse a stepping.ramp_up."""
    stepping_tg = next(
        (t for t in structure.thread_groups if t.kind == "stepping"), None
    )
    if stepping_tg is None:
        pytest.skip("Fixture sin TG stepping")

    op = UpdateThreadGroupOp(id=str(stepping_tg.id), fields={"ramp_time": 99})
    result, applied = apply_operations(structure, [op])
    assert applied == 1

    updated = next(
        t for t in result.thread_groups if str(t.id) == str(stepping_tg.id)
    )
    # El campo CORRECTO (stepping.ramp_up) debe tener el nuevo valor —
    # ese es el que el regenerator escribira en el XML como <stringProp name="rampUp">.
    assert updated.stepping.ramp_up == 99, (
        f"ramp_up esperado=99, real={updated.stepping.ramp_up}"
    )


def test_update_loops_sobre_stepping_no_lanza(structure):
    """HF5.2: loops sobre TG stepping debe aceptarse (el regenerator escribe
    LoopController.loops igual en stepping)."""
    stepping_tg = next(
        (t for t in structure.thread_groups if t.kind == "stepping"), None
    )
    if stepping_tg is None:
        pytest.skip("Fixture sin TG stepping")

    op = UpdateThreadGroupOp(id=str(stepping_tg.id), fields={"loops": 99})
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    updated = next(
        t for t in result.thread_groups if str(t.id) == str(stepping_tg.id)
    )
    assert updated.loops == 99


def test_update_stepping_field_sobre_standard_lanza_error(structure):
    """HF5.2: campo de stepping (ej. start_users_count) sobre TG standard
    debe lanzar OperationError explicito."""
    standard_tg = next(
        (t for t in structure.thread_groups if t.kind == "standard"), None
    )
    if standard_tg is None:
        pytest.skip("Fixture sin TG standard")

    op = UpdateThreadGroupOp(
        id=str(standard_tg.id),
        fields={"start_users_count": 5},
    )
    with pytest.raises(OperationError) as exc:
        apply_operations(structure, [op])
    msg = str(exc.value).lower()
    assert "stepping" in msg or "standard" in msg


def test_update_stepping_objeto_anidado_funciona(structure):
    """HF5.2: enviar 'stepping' como objeto anidado debe funcionar (formato preferido)."""
    stepping_tg = next(
        (t for t in structure.thread_groups if t.kind == "stepping"), None
    )
    if stepping_tg is None:
        pytest.skip("Fixture sin TG stepping")

    op = UpdateThreadGroupOp(
        id=str(stepping_tg.id),
        fields={"stepping": {"ramp_up": 88, "flight_time": 240}},
    )
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    updated = next(
        t for t in result.thread_groups if str(t.id) == str(stepping_tg.id)
    )
    assert updated.stepping.ramp_up == 88
    assert updated.stepping.flight_time == 240


def test_update_num_threads_funciona_en_ambos_kinds(structure):
    """HF5.2: num_threads va al root del ThreadGroup tanto en standard como stepping."""
    for tg in structure.thread_groups:
        op = UpdateThreadGroupOp(id=str(tg.id), fields={"num_threads": 77})
        result, applied = apply_operations(structure, [op])
        updated = next(
            t for t in result.thread_groups if str(t.id) == str(tg.id)
        )
        assert updated.num_threads == 77, (
            f"num_threads no se aplico en TG kind={tg.kind}"
        )


# ============================================================================
# Sprint 2.4-HF7.A — operaciones de creacion (add_*) y eliminacion (delete_element)
# ============================================================================


def _find_first_sampler(structure):
    for tg in structure.thread_groups:
        for ch in tg.children:
            if ch.type == "sampler" and ch.sampler is not None:
                return tg, ch.sampler
    return None, None


def test_add_sampler_a_tg_existente(structure):
    tg = structure.thread_groups[0]
    initial = sum(1 for ch in tg.children if ch.type == "sampler")

    op = AddSamplerOp(
        thread_group_id=str(tg.id),
        sampler={"name": "Test Nuevo", "method": "POST", "path": "/api/test"},
    )
    result, applied = apply_operations(structure, [op])
    assert applied == 1

    tg_updated = next(t for t in result.thread_groups if str(t.id) == str(tg.id))
    new_count = sum(1 for ch in tg_updated.children if ch.type == "sampler")
    assert new_count == initial + 1

    new_sampler = next(
        ch.sampler
        for ch in tg_updated.children
        if ch.type == "sampler" and ch.sampler and ch.sampler.name == "Test Nuevo"
    )
    assert new_sampler.method == "POST"
    assert new_sampler.path == "/api/test"
    assert new_sampler.is_dirty is True
    assert new_sampler.id is not None


def test_add_sampler_child_header_manager(structure):
    tg, sampler = _find_first_sampler(structure)
    assert sampler is not None

    initial = len(sampler.children)
    op = AddSamplerChildOp(
        sampler_id=str(sampler.id),
        child_kind="header_manager",
        data={"headers": [{"name": "X-Test", "value": "1"}]},
    )
    result, applied = apply_operations(structure, [op])
    assert applied == 1

    found_sampler = None
    for t in result.thread_groups:
        for ch in t.children:
            if ch.type == "sampler" and ch.sampler and str(ch.sampler.id) == str(sampler.id):
                found_sampler = ch.sampler
                break
        if found_sampler:
            break
    assert found_sampler is not None
    assert len(found_sampler.children) == initial + 1
    last_child = found_sampler.children[-1]
    assert last_child.type == "header_manager"


def test_add_udv(structure):
    initial = len(structure.user_defined_variables)
    op = AddUdvOp(name="new_var", value="nuevo_valor")
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    assert len(result.user_defined_variables) == initial + 1
    assert any(u.name == "new_var" for u in result.user_defined_variables)


def test_add_udv_duplicado_lanza_error(structure):
    if not structure.user_defined_variables:
        apply_operations(structure, [AddUdvOp(name="primera", value="v")])
    existing_name = structure.user_defined_variables[0].name
    with pytest.raises(OperationError):
        apply_operations(structure, [AddUdvOp(name=existing_name, value="x")])


def test_add_csv_dataset(structure):
    initial = len(structure.csv_data_sets)
    op = AddCsvDatasetOp(
        data={
            "testname": "Datos de prueba",
            "filename": "test.csv",
            "variable_names": ["col1", "col2"],
        }
    )
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    assert len(result.csv_data_sets) == initial + 1
    new = result.csv_data_sets[-1]
    assert new.filename == "test.csv"
    assert new.variable_names == ["col1", "col2"]


def test_delete_sampler(structure):
    tg, sampler = _find_first_sampler(structure)
    assert sampler is not None
    sampler_id = str(sampler.id)
    tg_id = str(tg.id)

    op = DeleteElementOp(target_kind="sampler", id=sampler_id)
    result, applied = apply_operations(structure, [op])
    assert applied == 1

    tg_updated = next(t for t in result.thread_groups if str(t.id) == tg_id)
    remaining_ids = [
        str(ch.sampler.id) for ch in tg_updated.children
        if ch.type == "sampler" and ch.sampler
    ]
    assert sampler_id not in remaining_ids


def test_delete_udv(structure):
    apply_operations(structure, [AddUdvOp(name="to_delete", value="x")])
    op = DeleteElementOp(target_kind="udv", udv_name="to_delete")
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    assert not any(u.name == "to_delete" for u in result.user_defined_variables)


def test_delete_inexistente_lanza_error(structure):
    op = DeleteElementOp(target_kind="sampler", id="id_que_no_existe")
    with pytest.raises(OperationError):
        apply_operations(structure, [op])


# ============================================================================
# Sprint 2.4-HF7.B — add_listener (5 tipos, raw_xml inicial)
# ============================================================================


def test_add_listener_view_results_tree(structure):
    initial = len(structure.listeners)
    op = AddListenerOp(listener_kind="view_results_tree")
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    assert len(result.listeners) == initial + 1
    new_listener = result.listeners[-1]
    assert new_listener.name == "View Results Tree"
    assert new_listener.guiclass == "ViewResultsFullVisualizer"
    assert "ViewResultsFullVisualizer" in new_listener.raw_xml
    assert "<ResultCollector" in new_listener.raw_xml


def test_add_listener_summary_report_con_nombre_custom(structure):
    op = AddListenerOp(listener_kind="summary_report", name="Mi Resumen")
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    new_listener = result.listeners[-1]
    assert new_listener.name == "Mi Resumen"
    assert new_listener.guiclass == "SummaryReport"
    assert 'testname="Mi Resumen"' in new_listener.raw_xml


def test_add_backend_listener_default_config(structure):
    op = AddListenerOp(listener_kind="backend_listener")
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    new_listener = result.listeners[-1]
    assert new_listener.guiclass == "BackendListenerGui"
    assert new_listener.kind == "other"  # BackendListener no es ResultCollector
    # Defaults apuntan al InfluxDB del stack Kinetix
    assert "InfluxdbBackendListenerClient" in new_listener.raw_xml
    assert "http://influxdb:8086" in new_listener.raw_xml
    assert "<BackendListener" in new_listener.raw_xml


def test_add_listener_round_trip_summary_report(structure):
    """Round-trip: agregar listener → regenerate → re-parse mantiene el listener."""
    from app.services.engine.jmx_to_structure import parse_jmx_to_structure
    from app.services.engine.structure_to_jmx import regenerate_jmx_from_structure

    initial = len(structure.listeners)
    op = AddListenerOp(listener_kind="summary_report", name="Test Summary HF7B")
    structure_after, applied = apply_operations(structure, [op])
    assert applied == 1

    new_jmx = regenerate_jmx_from_structure(structure_after)
    assert "Test Summary HF7B" in new_jmx
    assert "SummaryReport" in new_jmx

    re_parsed = parse_jmx_to_structure(new_jmx)
    assert len(re_parsed.listeners) == initial + 1
    found = next(
        (l for l in re_parsed.listeners if l.name == "Test Summary HF7B"), None
    )
    assert found is not None
    assert found.kind == "summary_report"


def test_add_backend_listener_round_trip(structure):
    """Backend Listener: round-trip preserva la config InfluxDB."""
    from app.services.engine.jmx_to_structure import parse_jmx_to_structure
    from app.services.engine.structure_to_jmx import regenerate_jmx_from_structure

    op = AddListenerOp(listener_kind="backend_listener", name="Backend HF7B")
    structure_after, applied = apply_operations(structure, [op])
    assert applied == 1

    new_jmx = regenerate_jmx_from_structure(structure_after)
    assert "Backend HF7B" in new_jmx
    assert "InfluxdbBackendListenerClient" in new_jmx
    assert "http://influxdb:8086" in new_jmx

    # El parser solo reconoce ResultCollector como listener; el Backend
    # Listener cae en `unmapped` con su raw_xml intacto. Verificamos eso.
    re_parsed = parse_jmx_to_structure(new_jmx)
    backend_in_unmapped = any(
        u.kind == "BackendListener" or "BackendListener" in (u.raw_xml or "")
        for u in re_parsed.unmapped
    )
    assert backend_in_unmapped, (
        "Backend Listener debe quedar en unmapped (no es ResultCollector) "
        "con su raw_xml preservado"
    )


# ============================================================================
# Sprint 2.5c.1 (HF7.B.1) — listeners ampliados a 11 tipos (jp@gc + with_csv)
# ============================================================================


def test_add_listener_jpgc_response_times(structure):
    op = AddListenerOp(listener_kind="jpgc_response_times_over_time", name="RTOT")
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    new_listener = result.listeners[-1]
    assert new_listener.name == "RTOT"
    assert new_listener.kind == "kg_apc_response_times_over_time"
    assert "ResponseTimesOverTimeGui" in new_listener.raw_xml
    assert "CorrectedResultCollector" in new_listener.raw_xml
    assert 'name="interval_grouping">500' in new_listener.raw_xml


def test_add_listener_jpgc_transactions_per_second(structure):
    op = AddListenerOp(listener_kind="jpgc_transactions_per_second")
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    new_listener = result.listeners[-1]
    assert new_listener.kind == "kg_apc_transactions_per_second"
    assert "TransactionsPerSecondGui" in new_listener.raw_xml


def test_add_listener_with_csv_filename_custom(structure):
    op = AddListenerOp(
        listener_kind="aggregate_report_with_csv",
        name="Agg con CSV",
        filename="${Resultados}/test.jtl",
    )
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    new_listener = result.listeners[-1]
    assert new_listener.guiclass == "StatVisualizer"
    assert "${Resultados}/test.jtl" in new_listener.raw_xml


def test_add_listener_with_csv_default_pattern(structure):
    """Sin filename explicito, los kinds with_csv usan su patron default."""
    op = AddListenerOp(listener_kind="view_results_tree_with_csv")
    result, applied = apply_operations(structure, [op])
    assert applied == 1
    new_listener = result.listeners[-1]
    assert "resultados_log_" in new_listener.raw_xml


def test_add_listener_jpgc_round_trip(structure):
    """Round-trip de los 4 listeners jp@gc: regenerate preserva los guiclasses."""
    from app.services.engine.structure_to_jmx import regenerate_jmx_from_structure

    ops = [
        AddListenerOp(listener_kind="jpgc_response_times_over_time"),
        AddListenerOp(listener_kind="jpgc_response_codes_per_second"),
        AddListenerOp(listener_kind="jpgc_transactions_per_second"),
        AddListenerOp(listener_kind="jpgc_active_threads_over_time"),
    ]
    result, applied = apply_operations(structure, ops)
    assert applied == 4

    new_jmx = regenerate_jmx_from_structure(result)
    for gui in (
        "ResponseTimesOverTimeGui",
        "ResponseCodesPerSecondGui",
        "TransactionsPerSecondGui",
        "ThreadsStateOverTimeGui",
    ):
        assert gui in new_jmx, f"Falta {gui} en el JMX regenerado"
    assert "CorrectedResultCollector" in new_jmx
