"""Tests del soporte multi-archivo en /generate-from-file (Sprint 2.9)."""
from app.api.v1.endpoints.script_ai import (
    _aggregate_compression_stats,
    _build_unified_file_context,
)


def test_unified_context_un_solo_archivo_devuelve_contenido_directo():
    """Compat backward: 1 archivo = comportamiento previo (contenido directo)."""
    files = [
        {"index": 1, "filename": "test.har", "kind": "har", "content": "HAR_CONTENT_HERE"},
    ]
    assert _build_unified_file_context(files) == "HAR_CONTENT_HERE"


def test_unified_context_multiples_archivos_incluye_marcadores():
    """Multiples archivos deben tener marcadores claros para la IA."""
    files = [
        {"index": 1, "filename": "login.har", "kind": "har", "content": "HAR_1"},
        {"index": 2, "filename": "ops.har", "kind": "har", "content": "HAR_2"},
    ]
    result = _build_unified_file_context(files)
    assert "=== FLUJO DIVIDIDO EN 2 ARCHIVOS ===" in result
    assert "login.har" in result
    assert "ops.har" in result
    assert "HAR_1" in result
    assert "HAR_2" in result
    assert "UN SOLO FLUJO" in result.upper() or "UN SOLO JMX" in result.upper()


def test_unified_context_instrucciones_correlacion():
    """El contexto debe instruir mantener correlacion entre archivos."""
    files = [
        {"index": 1, "filename": "a.har", "kind": "har", "content": "X"},
        {"index": 2, "filename": "b.har", "kind": "har", "content": "Y"},
    ]
    result = _build_unified_file_context(files)
    assert "correlaci" in result.lower() or "tokens extra" in result.lower()


def test_unified_context_3_archivos_marcador_correcto():
    files = [
        {"index": i, "filename": f"f{i}.har", "kind": "har", "content": f"C{i}"}
        for i in range(1, 4)
    ]
    result = _build_unified_file_context(files)
    assert "=== FLUJO DIVIDIDO EN 3 ARCHIVOS ===" in result
    for i in range(1, 4):
        assert f"f{i}.har" in result
        assert f"C{i}" in result


def test_aggregate_compression_stats_suma_y_marca_archivos():
    """El agregado suma tamanos/entries y reporta cuantos archivos hubo."""
    files = [
        {"compression_stats": {
            "original_size": 1000, "compressed_size": 100,
            "entries_original": 10, "entries_unique": 5,
            "entries_static_filtered": 3, "entries_tracking_filtered": 2,
        }},
        {"compression_stats": {
            "original_size": 3000, "compressed_size": 300,
            "entries_original": 20, "entries_unique": 8,
            "entries_static_filtered": 7, "entries_tracking_filtered": 5,
        }},
    ]
    agg = _aggregate_compression_stats(files)
    assert agg["original_size"] == 4000
    assert agg["compressed_size"] == 400
    assert agg["reduction_ratio"] == 90.0
    assert agg["entries_original"] == 30
    assert agg["entries_unique"] == 13
    assert agg["files"] == 2


def test_aggregate_compression_stats_sin_har_devuelve_none():
    files = [{"compression_stats": None}, {"compression_stats": None}]
    assert _aggregate_compression_stats(files) is None


def test_prompt_base_incluye_reglas_multi_har():
    """SYSTEM_PROMPT debe instruir como manejar multiples archivos."""
    from app.api.v1.endpoints.script_ai import SYSTEM_PROMPT
    p = SYSTEM_PROMPT.lower()
    assert (
        "multi-har" in p
        or "varios archivos" in p
        or "n archivos" in p
        or "flujo dividido" in p
    )
