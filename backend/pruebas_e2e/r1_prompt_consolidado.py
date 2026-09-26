"""ETAPA R1.2 — el prompt del consolidado de un integrado, SIN llamar a la IA.

    DATABASE_URL=postgresql://...@postgres:5432/jmeter_analyzer_test \\
        python3 /app/pruebas_e2e/r1_prompt_consolidado.py <report_id>

Llama en proceso a `generate_consolidated_analysis` con un sustituto de la IA que
guarda el prompt y devuelve un texto fijo. Imprime cada prompt en una linea
`PROMPT <json>`. Lo usa r1_seleccion.py.

Se para si la base no es de pruebas: el endpoint GUARDA el consolidado.
"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, text  # noqa: E402

import app.services.ai.gemini as G  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.models.integrated_report import IntegratedReport  # noqa: E402
from app.api.v1.endpoints.integrated_report import (  # noqa: E402
    ConsolidatedRequest, SectionInput, generate_consolidated_analysis)

RID = sys.argv[1]
prompts = []


class SinIA:
    """Sustituto: no hay ni una peticion a ningun proveedor."""
    def _generate(self, prompt, **kw):
        prompts.append(prompt)
        return "===CONCLUSIONES_CONSOLIDADAS===\nZZTEST.\n===RECOMENDACIONES_CONSOLIDADAS===\nZZTEST."


G.get_gemini_analyzer = lambda **kw: SinIA()


async def main():
    async with AsyncSessionLocal() as db:
        base = (await db.execute(text("select current_database()"))).scalar()
        if "test" not in base:
            sys.exit(f"PARADA: '{base}' no es la base de pruebas")
        rep = await db.get(IntegratedReport, __import__("uuid").UUID(RID))
        u = (await db.execute(select(User).where(User.username == "admin"))).scalars().first()
        secs = [SectionInput(**{k: s.get(k) for k in ("order", "type", "source_id", "source_name", "seleccion")})
                for s in rep.sections]
        await generate_consolidated_analysis(ConsolidatedRequest(sections=secs, report_id=RID), db=db, current_user=u)
    for p in prompts:
        print("PROMPT " + json.dumps(p, ensure_ascii=False))
    print(f"llamadas a la IA: 0 (prompts capturados: {len(prompts)})")


asyncio.run(main())
