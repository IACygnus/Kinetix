"""BLOQUE 2.2 (137 §5.4) — ¿la captura se corta por el tope? UNA llamada real.

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/captura_finish.py <id8>

Toma la primera captura de monitoreo de la ejecucion (base en solo lectura), la
analiza con `analyze_image` —el mismo camino que la pantalla— y NO guarda el
texto: solo imprime el finish_reason, los tokens y la longitud. El texto lleva
datos de clientes y no sale de aqui.
"""
import asyncio
import inspect
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, String
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models.attachment import ExecutionAttachment
from app.services.ai import gemini as G

TEL = []
_orig = G._emit_ai_telemetry
_firma = inspect.signature(_orig)


def _tel(*a, **kw):
    arg = _firma.bind(*a, **kw).arguments
    u = getattr(arg.get("response"), "usage", None)
    TEL.append({"seccion": arg.get("section"), "limite": arg.get("limit"),
                "finish_reason": arg.get("finish_reason"), "outcome": arg.get("outcome"),
                "reasoning_effort": arg.get("reasoning_effort"),
                "entrada": getattr(u, "prompt_tokens", None), "salida": getattr(u, "completion_tokens", None),
                "razonamiento": getattr(getattr(u, "completion_tokens_details", None), "reasoning_tokens", None)})
    return _orig(*a, **kw)


G._emit_ai_telemetry = _tel


async def main(id8):
    motor = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                                connect_args={"server_settings": {"default_transaction_read_only": "on"}})
    async with async_sessionmaker(motor, class_=AsyncSession)() as db:
        att = (await db.execute(select(ExecutionAttachment).where(
            ExecutionAttachment.execution_id.cast(String).like(f"{id8}%"),
            ExecutionAttachment.attachment_type == "monitoring").order_by(ExecutionAttachment.sort_order))).scalars().first()
        conf = await G.load_ai_config_from_db(db)
        datos = dict(fp=att.filepath, tipo=att.file_type or "image/png", cat=att.category or "", tit=att.title or "",
                     desc=att.description or "")
        await db.rollback()
    await motor.dispose()
    an = G.get_gemini_analyzer(provider=conf["provider"], model_name=conf["model_name"], api_key=conf["api_key"],
                               reasoning_effort=conf.get("reasoning_effort") or "")
    import os
    ruta = datos["fp"] if os.path.exists(datos["fp"]) else "/app" + datos["fp"]   # /media vive bajo /app
    img = open(ruta, "rb").read()
    mime = datos["tipo"] if "/" in datos["tipo"] else f"image/{datos['tipo'].lstrip('.') or 'png'}"
    texto = an.analyze_image(img, mime, datos["cat"], datos["tit"], datos["desc"], "monitoring")
    print({"telemetria": TEL, "caracteres": len(texto or ""), "palabras": len((texto or "").split()),
           "parrafos": len([p for p in (texto or "").splitlines() if p.strip()])})


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
