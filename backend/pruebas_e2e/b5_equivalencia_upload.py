"""BLOQUE 5 — `/upload` y `/extract-jtl-transactions` dan lo mismo que antes.

    git -C <repo> show <base>:backend/app/api/v1/endpoints/upload.py > backend/pruebas_e2e/_upload_base.py
    docker exec -e GEMINI_API_KEY= -e OPENAI_API_KEY= \
        -e DATABASE_URL=postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_test \
        -e PYTHONPATH=/app/pruebas_e2e jmeter_backend python3 /app/pruebas_e2e/b5_equivalencia_upload.py

El bloque 5 extrajo el cuerpo de `/upload` a `procesar_subida` y las filas del
panel a `panel_transacciones`. Aquí se llama, EN PROCESO, a la versión de antes
(`_upload_base.py`, sacada de git) y a la de ahora con las mismas entradas, sin
IA (claves vacías: todo va al respaldo) y contra la base de PRUEBAS, y se
compara la respuesta campo a campo, salvo id y fechas de alta.
"""
import asyncio
import importlib.util
import io
import os
import sys

sys.path.insert(0, "/app")
from starlette.datastructures import UploadFile   # noqa: E402

import b5_comun as B   # noqa: E402
from b5_comun import ok   # noqa: E402

assert "test" in os.environ.get("DATABASE_URL", ""), "PARADA: DATABASE_URL no apunta a la base de pruebas"
assert not os.environ.get("GEMINI_API_KEY") and not os.environ.get("OPENAI_API_KEY"), "PARADA: hay clave de IA"

spec = importlib.util.spec_from_file_location("upload_base", "/app/pruebas_e2e/_upload_base.py")
viejo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viejo)
from app.api.v1.endpoints import upload as nuevo   # noqa: E402
from app.db.session import AsyncSessionLocal   # noqa: E402
from app.db.models.user import User   # noqa: E402
from sqlalchemy import select   # noqa: E402

DATOS = open(B.JTL_R1, "rb").read()


def archivo():
    return UploadFile(filename="ZZTEST-B5_equivalencia.jtl", file=io.BytesIO(DATOS))


async def main():
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
        print("== /extract-jtl-transactions")
        for rt, av in ((None, None), (500.0, 99.5), (300.0, 50.0)):
            a = await viejo.extract_jtl_transactions([archivo()], rt, av, admin)
            b = await nuevo.extract_jtl_transactions([archivo()], rt, av, admin)
            ok(a == b, f"criterios {rt}/{av}: idéntico ({b['critical_count']} críticas de {b['count']})")

        print("== /upload")
        crit = ('{"concurrency": 5, "response_time": 500, "availability": 99.5, '
                '"critical_transactions": [], "per_transaction": {"1. Auth": {"concurrency": 5, '
                '"response_time": 300, "availability": 99}}}')
        resp = []
        for mod in (viejo, nuevo):
            r = await mod.upload_jtl([archivo()], name="ZZTEST-B5 equivalencia", description="ZZTEST",
                                     test_type="load", client="", project="ZZTEST-B5 equivalencia",
                                     client_id="", acceptance_criteria=crit, metric_unit="TPS",
                                     db=db, current_user=admin)
            resp.append(r)
        fuera = {"id", "created_at", "updated_at", "execution_date"}
        a, b = ({k: v for k, v in r.items() if k not in fuera} for r in resp)
        dif = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        ok(not dif, f"respuesta idéntica salvo id y fechas de alta ({len(a)} campos){' · difieren: ' + str(dif) if dif else ''}")
        ok(b["acceptance_criteria_json"].get("verdict") == "NO APTO", "con su veredicto")
        ok(b["ai_status"]["provider"] == "fallback", "sin IA (respaldo), como se pidió")


asyncio.run(main())
B.fin("B5 equivalencia de /upload")
