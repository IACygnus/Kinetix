"""BLOQUE 2.5 — segunda prueba de cache: ¿desde donde se reutiliza un prompt REAL?

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/prueba_cache_25b.py <corrida.json> <n>

Manda la llamada n de la corrida tal cual y, detras, el mismo prompt cortado en
varios puntos (en caracteres) con un final distinto. Solo imprime tokens: el
texto lleva datos de clientes y no sale de aqui. Salida limitada a 32 tokens.
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/pruebas_e2e")

from openai import OpenAI
from app.services.ai import gemini as G
from prueba_cache_25 import _config

COLA = " ".join(f"final{i % 71} distinto{i % 67}" for i in range(300))


def main(ruta, n, cortes):
    conf = asyncio.run(_config())
    modelo = conf["model_name"]
    cli = OpenAI(api_key=conf["api_key"], max_retries=0, timeout=G.CLIENTE_TIMEOUT_S)
    p = json.load(open(ruta, encoding="utf-8"))["detalle"][n - 1]["prompt"]
    for nombre, usuario in [("tal cual", p)] + [(f"cortado en {c} car + cola", p[:c] + "\n" + COLA) for c in cortes]:
        r = G.openai_chat_completion(
            cli, modelo, [{"role": "system", "content": G.SYSTEM_PROMPT}, {"role": "user", "content": usuario}],
            32, **G._openai_reasoning_kwarg(modelo, conf.get("reasoning_effort")))
        u = r.usage
        print(json.dumps({"prueba": nombre, "entrada": u.prompt_tokens,
                          "cache": getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0}), flush=True)
        time.sleep(3)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), [int(x) for x in sys.argv[3:]] or [3744, 4400, 5000])
