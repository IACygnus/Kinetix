"""ETAPA R2 — ¿por que el «despues» no se cachea? Prueba controlada, 2 llamadas.

    docker exec -w /app -e R2_RAIZ=<raiz> jmeter_backend \
        python3 /app/pruebas_e2e/prueba_cache_r2.py <corrida.json> <n_llamada> [<n_llamada_2>]

Manda a OpenAI el mensaje de sistema de la version de <raiz> con el prompt de la
llamada n (1-based) grabado en <corrida.json> por `corrida_r2.py`, y despues el
de la llamada n_2 (por defecto, la misma n: el MISMO texto dos veces). Mismo
modelo y mismos parametros que `_generate`, pero la salida limitada a 64 tokens:
solo interesa `usage.prompt_tokens_details.cached_tokens`.

Solo lectura: la clave sale de una sesion con `default_transaction_read_only=on`.
No usa `_generate`, asi que no toca contadores, circuito ni buzon.
"""
import asyncio
import json
import os
import sys
import time

RAIZ = os.environ.get("R2_RAIZ", "/app")
sys.path.insert(0, RAIZ)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from openai import OpenAI

from app.core.config import settings
from app.services.ai import gemini as G


async def _config():
    motor = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        connect_args={"server_settings": {"default_transaction_read_only": "on"}})
    sesion = async_sessionmaker(motor, class_=AsyncSession, autoflush=False)
    async with sesion() as db:
        conf = await G.load_ai_config_from_db(db)
        await db.rollback()
    await motor.dispose()
    return conf


def main(ruta, n1, n2):
    conf = asyncio.run(_config())
    assert conf.get("provider") == "openai", f"proveedor {conf.get('provider')}: la prueba es de OpenAI"
    modelo = conf["model_name"]
    cli = OpenAI(api_key=conf["api_key"], max_retries=0, timeout=G.CLIENTE_TIMEOUT_S)
    det = json.load(open(ruta, encoding="utf-8"))["detalle"]
    for n in (n1, n2):
        c = det[n - 1]
        t0 = time.time()
        r = G.openai_chat_completion(
            cli, modelo,
            [{"role": "system", "content": G.SYSTEM_PROMPT}, {"role": "user", "content": c["prompt"]}],
            64, temperature=G.GENERATION_CONFIG["temperature"],
            **G._openai_reasoning_kwarg(modelo, conf.get("reasoning_effort")))
        u = r.usage
        print(json.dumps({
            "raiz": RAIZ, "llamada": n, "seccion": c["seccion"], "transaccion": bool(c["transaccion"]),
            "sistema_car": len(G.SYSTEM_PROMPT), "prompt_car": len(c["prompt"]),
            "prompt_tokens": u.prompt_tokens,
            "cached_tokens": getattr(u.prompt_tokens_details, "cached_tokens", None),
            "segundos": round(time.time() - t0, 1),
        }), flush=True)
        time.sleep(2)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], int(a[1]), int(a[2]) if len(a) > 2 else int(a[1]))
