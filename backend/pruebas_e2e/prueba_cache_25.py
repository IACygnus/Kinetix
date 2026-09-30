"""BLOQUE 2.5 — ¿por que las 9 primeras llamadas del informe general no usan la cache?

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/prueba_cache_25.py

Hipotesis (reporte 140): cada peticion deja en la cache UN solo punto, el mayor
1.024·k − 256 tokens que cabe en su prompt (1.792, 2.816, 3.840…), y una peticion
posterior solo lo aprovecha si comparte con ella al menos esa longitud. Si fuera
un modelo de bloques «todo prefijo de 1.024 + 128·n», bastaria compartir el sistema
y el bloque (> 1.792 tokens) para acertar.

Texto sintetico, sin datos de clientes. Un «nonce» nuevo por corrida, justo detras
del sistema, para que nada de corridas anteriores cuente. 4 llamadas con la salida
limitada a 32 tokens y razonamiento bajo.
  B  base: sistema + nonce                         -> tokens del prefijo fijo
  W  escritor: base + relleno A hasta ~3.500 tokens -> guarda E = 1.024·k − 256
  R1 comparte con W unos 500 tokens MENOS que E, y sigue distinto
  R2 comparte con W unos 150 tokens MAS que E, y sigue distinto
Prediccion de la hipotesis: R1 = 0 en cache; R2 = E. Modelo de bloques: R1 >= 1.792.
"""
import asyncio
import json
import sys
import time
import uuid

sys.path.insert(0, "/app")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from openai import OpenAI

from app.core.config import settings
from app.services.ai import gemini as G

A = [f"dato{i % 97} valor{i % 89}" for i in range(4000)]   # relleno A, determinista
Z = [f"otro{i % 83} cosa{i % 79}" for i in range(4000)]    # relleno distinto


async def _config():
    motor = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                                connect_args={"server_settings": {"default_transaction_read_only": "on"}})
    async with async_sessionmaker(motor, class_=AsyncSession)() as db:
        conf = await G.load_ai_config_from_db(db)
        await db.rollback()
    await motor.dispose()
    return conf


def main():
    conf = asyncio.run(_config())
    modelo = conf["model_name"]
    cli = OpenAI(api_key=conf["api_key"], max_retries=0, timeout=G.CLIENTE_TIMEOUT_S)
    nonce = f"PRUEBA DE CACHE {uuid.uuid4().hex}\n"

    def llamar(nombre, usuario):
        r = G.openai_chat_completion(
            cli, modelo, [{"role": "system", "content": G.SYSTEM_PROMPT}, {"role": "user", "content": usuario}],
            32, **G._openai_reasoning_kwarg(modelo, "low"))
        u = r.usage
        out = {"llamada": nombre, "entrada": u.prompt_tokens,
               "cache": getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0}
        print(json.dumps(out), flush=True)
        time.sleep(3)
        return out

    # B con OTRO nonce de la misma longitud: mide el prefijo sin dejar nada que W o R1 reutilicen.
    base = llamar("B", f"PRUEBA DE CACHE {uuid.uuid4().hex}\n" + "ok")["entrada"]
    # Calibracion: tokens por par de palabras del relleno, con W entero.
    W_n = 1300
    w = llamar("W", nonce + " ".join(A[:W_n]))["entrada"]
    por_par = (w - base) / W_n
    e = max(k * 1024 - 256 for k in range(1, 20) if k * 1024 - 256 <= w)
    print(json.dumps({"base": base, "tokens_por_par": round(por_par, 3), "E_predicho": e}), flush=True)

    def pares_hasta(tokens):
        return max(1, int((tokens - base) / por_par))

    n1 = pares_hasta(e - 500)
    r1 = llamar("R1 (comparte ~E-500)", nonce + " ".join(A[:n1] + Z[:700]))
    n2 = pares_hasta(e + 150)
    r2 = llamar("R2 (comparte ~E+150)", nonce + " ".join(A[:n2] + Z[1000:1700]))
    print(json.dumps({"E": e, "R1_comparte_aprox": e - 500, "R1_cache": r1["cache"],
                      "R2_comparte_aprox": e + 150, "R2_cache": r2["cache"],
                      "hipotesis_un_punto": r1["cache"] == 0 and r2["cache"] == e}), flush=True)


if __name__ == "__main__":
    main()
