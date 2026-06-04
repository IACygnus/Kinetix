"""Tests del jmeter_runner (Sprint 2.5b)."""
import os
import re
import shutil
import tempfile

import pytest

from app.services.engine.jmeter_runner import (
    cleanup_workdir,
    parse_jtl_summary,
    patch_jmx_for_smoke,
    prepare_full_run_jmx,
    run_jmeter,
)


SIMPLE_JMX = '''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test">
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="TG">
        <stringProp name="ThreadGroup.num_threads">100</stringProp>
        <stringProp name="ThreadGroup.ramp_time">60</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController">
          <boolProp name="LoopController.continue_forever">true</boolProp>
          <intProp name="LoopController.loops">-1</intProp>
        </elementProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">300</stringProp>
      </ThreadGroup>
      <hashTree/>
    </hashTree>
  </hashTree>
</jmeterTestPlan>'''


# ============================================================================
# patch_jmx_for_smoke — unit tests
# ============================================================================


def test_patch_jmx_for_smoke_reduce_num_threads():
    patched = patch_jmx_for_smoke(SIMPLE_JMX)
    assert '<stringProp name="ThreadGroup.num_threads">1</stringProp>' in patched
    assert '<stringProp name="ThreadGroup.num_threads">100</stringProp>' not in patched


def test_patch_jmx_for_smoke_loops_uno():
    patched = patch_jmx_for_smoke(SIMPLE_JMX)
    # LoopController.loops debe ser 1 (era -1)
    assert '<intProp name="LoopController.loops">1</intProp>' in patched
    assert '<intProp name="LoopController.loops">-1</intProp>' not in patched
    # continue_forever debe ser false
    assert '<boolProp name="LoopController.continue_forever">false</boolProp>' in patched


def test_patch_jmx_for_smoke_scheduler_false():
    patched = patch_jmx_for_smoke(SIMPLE_JMX)
    assert '<boolProp name="ThreadGroup.scheduler">false</boolProp>' in patched


def test_patch_jmx_invalido_lanza_error():
    with pytest.raises(ValueError):
        patch_jmx_for_smoke("esto no es XML")


def test_patch_jmx_deshabilita_backend_listener():
    jmx_with_bl = SIMPLE_JMX.replace(
        "</TestPlan>",
        '</TestPlan><BackendListener guiclass="BackendListenerGui" '
        'testclass="BackendListener" testname="BL" enabled="true"/>',
    )
    patched = patch_jmx_for_smoke(jmx_with_bl)
    assert "BackendListener" in patched
    bl_attrs = re.findall(r'<BackendListener[^>]*enabled="([^"]+)"', patched)
    assert bl_attrs, "esperaba al menos un BackendListener"
    for v in bl_attrs:
        assert v == "false", f"BackendListener enabled debe ser false, es {v!r}"


# ============================================================================
# Sprint 2.5c.1 — smoke configurable (num_threads / loops / data_dir_resolver)
# ============================================================================


def test_patch_jmx_smoke_num_threads_configurable():
    """num_threads y loops se respetan en el patch."""
    patched = patch_jmx_for_smoke(SIMPLE_JMX, num_threads=5, loops=2)
    assert '<stringProp name="ThreadGroup.num_threads">5</stringProp>' in patched
    # loops puede aparecer como intProp o stringProp (SIMPLE_JMX usa intProp)
    assert (
        '<intProp name="LoopController.loops">2</intProp>' in patched
        or '<stringProp name="LoopController.loops">2</stringProp>' in patched
    )


def test_patch_jmx_smoke_default_sigue_siendo_uno():
    """Sin args explicitos sigue forzando 1 usuario / 1 loop (compat 2.5b)."""
    patched = patch_jmx_for_smoke(SIMPLE_JMX)
    assert '<stringProp name="ThreadGroup.num_threads">1</stringProp>' in patched
    assert '<intProp name="LoopController.loops">1</intProp>' in patched


def test_patch_jmx_smoke_rechaza_num_threads_fuera_de_rango():
    with pytest.raises(ValueError):
        patch_jmx_for_smoke(SIMPLE_JMX, num_threads=25, loops=1)
    with pytest.raises(ValueError):
        patch_jmx_for_smoke(SIMPLE_JMX, num_threads=1, loops=10)


def test_patch_jmx_data_dir_resolver_reescribe_udv():
    """Si se pasa data_dir_resolver, la UDV 'Data' se reescribe con el path real."""
    jmx_with_data_udv = SIMPLE_JMX.replace(
        '<collectionProp name="Arguments.arguments"/>',
        '<collectionProp name="Arguments.arguments">'
        '<elementProp name="Data" elementType="Argument">'
        '<stringProp name="Argument.name">Data</stringProp>'
        '<stringProp name="Argument.value">C:/path/original</stringProp>'
        '<stringProp name="Argument.metadata">=</stringProp>'
        '</elementProp>'
        '</collectionProp>',
        1,  # solo el primero
    )
    patched = patch_jmx_for_smoke(
        jmx_with_data_udv,
        data_dir_resolver={"Data": "/app/uploads/ai_data_files/abc-123"},
    )
    assert "/app/uploads/ai_data_files/abc-123" in patched
    assert "C:/path/original" not in patched


# ============================================================================
# Sprint 2.5c.1-HF12 — bug "0/0 samplers": CSV Data Set + ${Data} en workdir
# ============================================================================


JMX_WITH_CSV = '''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Test">
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments">
        <collectionProp name="Arguments.arguments">
          <elementProp name="Data" elementType="Argument">
            <stringProp name="Argument.name">Data</stringProp>
            <stringProp name="Argument.value">/will-be-replaced</stringProp>
            <stringProp name="Argument.metadata">=</stringProp>
          </elementProp>
        </collectionProp>
      </elementProp>
    </TestPlan>
    <hashTree>
      <CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="Data Set">
        <stringProp name="delimiter">,</stringProp>
        <stringProp name="fileEncoding"></stringProp>
        <stringProp name="filename">${Data}/test.csv</stringProp>
        <boolProp name="ignoreFirstLine">false</boolProp>
        <boolProp name="quotedData">false</boolProp>
        <boolProp name="recycle">true</boolProp>
        <stringProp name="shareMode">shareMode.all</stringProp>
        <boolProp name="stopThread">false</boolProp>
        <stringProp name="variableNames">col1,col2</stringProp>
      </CSVDataSet>
      <hashTree/>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="TG">
        <stringProp name="ThreadGroup.num_threads">1</stringProp>
        <stringProp name="ThreadGroup.ramp_time">1</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <intProp name="LoopController.loops">1</intProp>
        </elementProp>
      </ThreadGroup>
      <hashTree/>
    </hashTree>
  </hashTree>
</jmeterTestPlan>'''


def test_run_jmeter_con_csv_dataset_en_workdir():
    """HF12: ${Data} se reescribe al workdir y el filename del CSV no cambia."""
    workdir = tempfile.mkdtemp(prefix="test_hf12_")
    try:
        csv_path = os.path.join(workdir, "test.csv")
        with open(csv_path, "w") as f:
            f.write("hello,world\nfoo,bar\n")

        patched = patch_jmx_for_smoke(
            JMX_WITH_CSV,
            num_threads=1,
            loops=1,
            data_dir_resolver={"Data": workdir},
        )
        # La UDV Data se reescribió al workdir
        assert workdir in patched, "data_dir_resolver no reescribió la UDV Data"
        assert "/will-be-replaced" not in patched, "El valor original sigue presente"
        # El filename del CSV Data Set sigue usando ${Data} (portable)
        assert "${Data}/test.csv" in patched, "filename del CSV no debería cambiar"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@pytest.mark.slow
def test_run_jmeter_smoke_lee_csv_real_desde_workdir():
    """HF12 slow: JMeter real lee el CSV desde el workdir sin 'must exist and be readable'."""
    workdir = tempfile.mkdtemp(prefix="test_hf12_slow_")
    try:
        csv_path = os.path.join(workdir, "test.csv")
        with open(csv_path, "w") as f:
            f.write("v1,v2\nv3,v4\n")

        patched = patch_jmx_for_smoke(
            JMX_WITH_CSV, num_threads=1, loops=1, data_dir_resolver={"Data": workdir}
        )
        result = run_jmeter(patched, timeout_sec=60, workdir=workdir)

        assert result.error_message is None, f"JMeter no arrancó: {result.error_message}"
        assert result.exit_code == 0, f"JMeter falló: {result.stderr_tail}"

        # CRÍTICO: el log NO debe contener el error de FileServer
        if result.jmeter_log_path and os.path.exists(result.jmeter_log_path):
            with open(result.jmeter_log_path) as f:
                log = f.read()
            assert "must exist and be readable" not in log, (
                f"BUG HF12 NO ARREGLADO: FileServer sigue fallando. Log:\n{log[-1500:]}"
            )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ============================================================================
# run_jmeter — integracion (subprocess real)
# ============================================================================


@pytest.mark.slow
def test_run_jmeter_smoke_jmx_trivial():
    """Corre JMeter real sobre el JMX trivial. Tarda ~5-10 s."""
    patched = patch_jmx_for_smoke(SIMPLE_JMX)
    workdir = tempfile.mkdtemp(prefix="test_jmeter_")
    try:
        result = run_jmeter(patched, timeout_sec=60, workdir=workdir)
        assert result.error_message is None, (
            f"JMeter no arranco: {result.error_message}"
        )
        assert result.exit_code == 0, (
            f"JMeter exit_code={result.exit_code}, stderr={result.stderr_tail}"
        )
        assert result.jtl_path is not None
        assert result.jmeter_log_path is not None
        assert os.path.exists(result.jtl_path)
        # smoke debe ser rapido (< 30 s incluso con arranque de JVM)
        assert result.duration_sec < 30, (
            f"smoke tardo {result.duration_sec:.1f}s — demasiado lento"
        )
    finally:
        cleanup_workdir(workdir)


# ============================================================================
# Sprint 2.5d.1 — prepare_full_run_jmx (ejecucion FULL, no smoke)
# ============================================================================


def test_prepare_full_run_habilita_backend_listener():
    """A diferencia del smoke, FULL habilita el Backend Listener (-> InfluxDB)."""
    jmx_with_disabled_bl = SIMPLE_JMX.replace(
        "</TestPlan>",
        '</TestPlan><BackendListener guiclass="BackendListenerGui" '
        'testclass="BackendListener" testname="BL" enabled="false"/>',
    )
    prepared = prepare_full_run_jmx(jmx_with_disabled_bl)
    bl_attrs = re.findall(r'<BackendListener[^>]*enabled="([^"]+)"', prepared)
    assert bl_attrs, "esperaba al menos un BackendListener"
    for v in bl_attrs:
        assert v == "true", f"BackendListener enabled debe ser true, es {v!r}"


def test_prepare_full_run_no_modifica_num_threads():
    """FULL NO debe reducir num_threads (respeta el Thread Group tal cual)."""
    prepared = prepare_full_run_jmx(SIMPLE_JMX)
    # SIMPLE_JMX tiene num_threads=100; debe permanecer.
    assert '<stringProp name="ThreadGroup.num_threads">100</stringProp>' in prepared


def test_prepare_full_run_jmx_invalido_lanza_error():
    with pytest.raises(ValueError):
        prepare_full_run_jmx("esto no es XML")


def test_prepare_full_run_reescribe_data_resolver():
    prepared = prepare_full_run_jmx(
        JMX_WITH_CSV,
        data_dir_resolver={"Data": "/app/uploads/jtl_results/42"},
    )
    assert "/app/uploads/jtl_results/42" in prepared
    assert "/will-be-replaced" not in prepared


# ============================================================================
# Sprint 2.5d.1 — parse_jtl_summary (metricas live desde el JTL)
# ============================================================================


def test_parse_jtl_summary_vacio():
    summary = parse_jtl_summary("/tmp/jtl-que-no-existe-2_5d1.jtl")
    assert summary["total_samples"] == 0
    assert summary["error_rate_pct"] == 0.0


def test_parse_jtl_summary_calcula_metricas():
    csv_content = (
        "timeStamp,elapsed,label,responseCode,success\n"
        "1234567890000,150,sampler1,200,true\n"
        "1234567891000,200,sampler2,200,true\n"
        "1234567892000,300,sampler3,500,false\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jtl", delete=False
    ) as f:
        f.write(csv_content)
        jtl_path = f.name
    try:
        summary = parse_jtl_summary(jtl_path)
        assert summary["total_samples"] == 3
        assert summary["successful_samples"] == 2
        assert summary["failed_samples"] == 1
        assert summary["error_rate_pct"] > 0
        assert summary["avg_response_ms"] > 0
    finally:
        os.unlink(jtl_path)


# ============================================================================
# Sprint 2.5d.1 — ExecutionTracker
# ============================================================================


def test_execution_tracker_register_and_get():
    from app.services.engine.execution_tracker import ExecutionTracker

    t = ExecutionTracker()
    t.register(1, {"status": "running"})
    assert t.get(1)["status"] == "running"
    t.update(1, status="completed")
    assert t.get(1)["status"] == "completed"
    assert t.get(999) is None
    t.unregister(1)
    assert t.get(1) is None
