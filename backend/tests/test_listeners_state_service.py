"""Tests del servicio de listeners state (Sprint 2.6a)."""
import os
import tempfile

import pytest

from app.services.engine.listeners_state_service import (
    compute_listeners_state,
    cleanup_execution_cache,
    listeners_cache,
    _percentile,
    _stddev,
)


SAMPLE_JTL = """timeStamp,elapsed,label,responseCode,responseMessage,threadName,success,bytes,sentBytes,grpThreads,allThreads,Latency
1700000000000,150,sampler1,200,OK,Thread-1,true,1024,512,1,1,100
1700000000500,200,sampler2,200,OK,Thread-1,true,2048,256,1,1,150
1700000001000,300,sampler1,500,KO,Thread-1,false,512,128,1,2,250
1700000001500,180,sampler1,200,OK,Thread-2,true,1024,512,1,2,130
1700000002000,250,sampler2,200,OK,Thread-2,true,2048,256,1,2,200
"""


@pytest.fixture
def jtl_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jtl', delete=False) as f:
        f.write(SAMPLE_JTL)
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(autouse=True)
def clean_cache():
    """Limpia el cache entre tests para evitar leaks."""
    listeners_cache._cache.clear()
    yield
    listeners_cache._cache.clear()


def test_compute_listeners_state_parsea_jtl(jtl_file):
    start_time = 1700000000.0
    state = compute_listeners_state(
        execution_id=1,
        jtl_path=jtl_file,
        start_time=start_time,
        elapsed_sec=3,
        status="running",
    )

    assert state["execution_id"] == 1
    assert state["total_samples_parsed"] == 5
    assert "sampler1" in state["per_sampler_stats"]
    assert "sampler2" in state["per_sampler_stats"]


def test_per_sampler_stats_calcula_metricas(jtl_file):
    start_time = 1700000000.0
    state = compute_listeners_state(
        execution_id=2,
        jtl_path=jtl_file,
        start_time=start_time,
        elapsed_sec=3,
        status="running",
    )

    s1 = state["per_sampler_stats"]["sampler1"]
    assert s1["count"] == 3
    assert s1["errors"] == 1
    assert s1["min"] == 150
    assert s1["max"] == 300
    assert s1["error_pct"] > 0


def test_parse_incremental_no_repite_samples(jtl_file):
    """Llamadas sucesivas no deben duplicar samples."""
    start_time = 1700000000.0
    state1 = compute_listeners_state(1, jtl_file, start_time, 1, "running")
    state2 = compute_listeners_state(1, jtl_file, start_time, 2, "running")

    assert state1["total_samples_parsed"] == state2["total_samples_parsed"] == 5


def test_parse_incremental_lee_solo_lo_nuevo(jtl_file):
    """Tras un primer parse, agregar lineas y reparsear suma solo lo nuevo."""
    start_time = 1700000000.0
    state1 = compute_listeners_state(7, jtl_file, start_time, 1, "running")
    assert state1["total_samples_parsed"] == 5

    with open(jtl_file, "a") as f:
        f.write("1700000003000,400,sampler3,200,OK,Thread-3,true,512,128,1,1,300\n")

    state2 = compute_listeners_state(7, jtl_file, start_time, 2, "running")
    assert state2["total_samples_parsed"] == 6
    assert "sampler3" in state2["per_sampler_stats"]


def test_time_buckets_agrupan_correctamente(jtl_file):
    start_time = 1700000000.0
    state = compute_listeners_state(
        execution_id=3,
        jtl_path=jtl_file,
        start_time=start_time,
        elapsed_sec=3,
        status="running",
    )

    assert len(state["time_buckets"]) >= 1
    assert state["bucket_size_sec"] == 2


def test_status_terminal_no_parsea_mas(jtl_file):
    """Si la ejecucion ya fue parseada, status terminal congela el cache."""
    start_time = 1700000000.0
    # Primer call con running (parsea 5).
    compute_listeners_state(4, jtl_file, start_time, 1, "running")

    # Modificar el archivo (agregar linea).
    with open(jtl_file, "a") as f:
        f.write("1700000003000,400,sampler3,200,OK,Thread-3,true,512,128,1,1,300\n")

    # Call con completed → cache ya inicializado → no parsea lo nuevo.
    state = compute_listeners_state(4, jtl_file, start_time, 5, "completed")

    assert state["total_samples_parsed"] == 5


def test_status_terminal_primer_poll_parsea_completo(jtl_file):
    """Primer poll de una ejecucion ya terminada parsea el JTL completo una vez."""
    start_time = 1700000000.0
    state = compute_listeners_state(
        execution_id=8,
        jtl_path=jtl_file,
        start_time=start_time,
        elapsed_sec=3,
        status="completed",
    )
    assert state["total_samples_parsed"] == 5
    assert "sampler1" in state["per_sampler_stats"]


def test_cleanup_cache_libera_memoria(jtl_file):
    start_time = 1700000000.0
    compute_listeners_state(99, jtl_file, start_time, 1, "running")

    assert listeners_cache.get(99) is not None
    cleanup_execution_cache(99)
    assert listeners_cache.get(99) is None


def test_percentile_basico():
    values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert _percentile(values, 50) == 55 or _percentile(values, 50) == 50
    assert _percentile(values, 90) >= 90
    assert _percentile(values, 99) >= 99


def test_stddev_lista_vacia():
    assert _stddev([]) == 0.0
    assert _stddev([100]) == 0.0
