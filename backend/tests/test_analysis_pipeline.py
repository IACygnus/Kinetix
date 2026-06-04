"""Tests del pipeline publico de analisis IA (Sprint 2.5d.2).

El proyecto no usa pytest-asyncio, asi que las corrutinas se ejecutan con
asyncio.run(). Las llamadas a Gemini se mockean (los metodos analyze_* son
SINCRONOS en el codigo real). time.sleep se neutraliza para que el test no
tarde ~11s por los delays entre secciones.
"""
import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.analysis_pipeline import run_jtl_analysis_pipeline
from app.db.models.test import TestExecution as ExecModel


SAMPLE_JTL_CSV = """timeStamp,elapsed,label,responseCode,responseMessage,threadName,success,bytes,sentBytes,grpThreads,allThreads,Latency,IdleTime,Connect
1700000000000,150,sampler1,200,OK,Thread-1,true,1024,512,1,1,100,0,50
1700000001000,200,sampler2,200,OK,Thread-1,true,2048,256,1,1,150,0,40
1700000002000,300,sampler1,500,KO,Thread-1,false,512,128,1,1,250,0,30
"""


def _mock_analyzer():
    """Analyzer con todos los analyze_* SINCRONOS devolviendo cadena vacia."""
    analyzer = MagicMock()
    analyzer.analyze_summary_table.return_value = ""
    analyzer.analyze_errors.return_value = ""
    analyzer.analyze_chart.return_value = ""
    analyzer.analyze_redirects.return_value = ""
    analyzer.generate_conclusions.return_value = ""
    analyzer.generate_recommendations.return_value = ""
    return analyzer


def test_pipeline_parsea_jtl_y_popula_metricas_basicas():
    """El pipeline parsea el JTL y popula los campos basicos de TestExecution."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jtl", delete=False) as f:
        f.write(SAMPLE_JTL_CSV)
        jtl_path = f.name

    try:
        test_exec = ExecModel(
            user_id="00000000-0000-0000-0000-000000000000",
            name="Test",
            client="cli",
            project="proj",
            test_type="load",
            jtl_filename=os.path.basename(jtl_path),
        )

        with patch("app.services.ai.analysis_pipeline.get_gemini_analyzer") as mock_get, \
             patch("app.services.ai.analysis_pipeline.load_ai_config_from_db",
                   new=AsyncMock(return_value={
                       "provider": "gemini", "model_name": "m", "api_key": "k",
                   })), \
             patch("app.services.ai.analysis_pipeline.time.sleep", MagicMock()):
            mock_get.return_value = _mock_analyzer()
            mock_db = AsyncMock()
            result = asyncio.run(run_jtl_analysis_pipeline(
                test_execution=test_exec,
                jtl_path=jtl_path,
                db=mock_db,
            ))

        assert result.total_requests == 3
        assert result.total_errors == 1
        assert result.error_rate is not None and result.error_rate > 0
        assert result.avg_response_time is not None and result.avg_response_time > 0
        # Sin acceptance criteria => no verdict.
        assert result.acceptance_criteria_json is None
    finally:
        os.unlink(jtl_path)


def test_pipeline_jtl_inexistente_lanza_error():
    """Si el JTL no existe, el parser falla y el pipeline propaga la excepcion."""
    test_exec = ExecModel(
        user_id="00000000-0000-0000-0000-000000000000",
        name="Test",
        client="cli",
        project="proj",
        test_type="load",
        jtl_filename="missing.jtl",
    )
    mock_db = AsyncMock()
    with pytest.raises(Exception):
        asyncio.run(run_jtl_analysis_pipeline(
            test_execution=test_exec,
            jtl_path="/path/que/no/existe.jtl",
            db=mock_db,
        ))
