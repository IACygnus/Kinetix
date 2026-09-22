"""Relé TCP: localhost:5173 (dentro de jmeter_backend) -> jmeter_frontend:5173.

Por que hace falta:
El navegador corre DENTRO de jmeter_backend. Si abriera http://jmeter_frontend:5173,
el origen seria ese host y el backend rechazaria por CORS (solo admite localhost:5173
y 127.0.0.1:5173). Con el rele, el navegador abre http://localhost:5173 -> origen
correcto -> CORS pasa; y http://localhost:8001 ya ES la API en ese mismo contenedor.

No toca configuracion ni contenedores: es un proceso mas dentro del backend.
"""
import asyncio

DESTINO = ("jmeter_frontend", 5173)
ESCUCHA = ("127.0.0.1", 5173)


async def _bombear(lector, escritor):
    try:
        while True:
            datos = await lector.read(65536)
            if not datos:
                break
            escritor.write(datos)
            await escritor.drain()
    except Exception:
        pass
    finally:
        try:
            escritor.close()
        except Exception:
            pass


async def _atender(lector_cliente, escritor_cliente):
    try:
        lector_destino, escritor_destino = await asyncio.open_connection(*DESTINO)
    except Exception:
        escritor_cliente.close()
        return
    await asyncio.gather(
        _bombear(lector_cliente, escritor_destino),
        _bombear(lector_destino, escritor_cliente),
    )


async def main():
    servidor = await asyncio.start_server(_atender, *ESCUCHA)
    print(f"rele escuchando en {ESCUCHA[0]}:{ESCUCHA[1]} -> {DESTINO[0]}:{DESTINO[1]}", flush=True)
    async with servidor:
        await servidor.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
