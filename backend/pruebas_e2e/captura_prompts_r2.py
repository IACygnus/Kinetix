"""BLOQUE 2.1 — los prompts que recibiria cada seccion de Nova, SIN llamar a la IA.

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/captura_prompts_r2.py <salida.json>

Corre el pipeline general y el de una transaccion con `_generate` sustituido por
un stub (como r2_series.py) y guarda {seccion: prompt}. Sirve para comparar el
bloque de datos antes y despues de un cambio sin gastar llamadas. La salida
LLEVA DATOS DE CLIENTES: va a /tmp o al scratchpad, nunca a docs/.
"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")

from app.services.ai import gemini as G
from app.services.ai import transaction_report as TR
from app.services.ai.analysis_pipeline import run_ai_and_verdict
from app.services.jtl.jtl_parser import JTLParser
from app.services.jtl.transaction_series import build_transaction_series
from app.api.v1.endpoints.upload import METRIC_KEYS

JTL = "/app/uploads/20260925_142338_resultados_general_carga_22-09-2026_200455.jtl"
TX = "1. ConsultaContratosCliente-HU5344"
PROMPTS = {}


def _stub(self, prompt, section_name="?", *a, **kw):
    PROMPTS[section_name] = prompt
    return f"[texto de {section_name}]"


async def _colector(*a, **kw):
    return None


class _SinBase:
    async def execute(self, *a, **kw):
        raise RuntimeError("sin base")


G.GeminiAnalyzer._generate = _stub
TR._upsert = _colector


async def main(salida):
    p = JTLParser(JTL)
    _, metrics = p.parse()
    await run_ai_and_verdict(p, metrics, "load", {"concurrency": 4, "response_time": 2000, "availability": 99.5},
                             "TPS", _SinBase())
    fila = {str(r["label"]): r for _, r in p.get_summary_table_data().iterrows()}[TX]
    kw = {}
    try:
        from app.services.ai import fases as F
        import inspect
        if "fases" in inspect.signature(TR.generate_transaction_report).parameters:
            kw["fases"] = F.calcular(p.df_main)
    except ImportError:
        pass
    await TR.generate_transaction_report(
        db=_SinBase(), execution_id=None, label=TX, metrics={k: fila[k] for k in METRIC_KEYS},
        series=build_transaction_series(p.df_main, TX), analyzer=G.GeminiAnalyzer.__new__(G.GeminiAnalyzer),
        df_tx=p.df_main[p.df_main["label"] == TX], **kw)
    json.dump(PROMPTS, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{salida}: {len(PROMPTS)} prompts")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
