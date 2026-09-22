"""Relé TCP: localhost:3000 (dentro de jmeter_backend) -> jmeter_grafana:3000.

Hermano de `rele_5173.py`, y por el mismo motivo. La pantalla de Monitoreo en
vivo embebe el tablero en `http://localhost:3000/d/...`, porque esa es la URL
que vale desde el navegador de Fredy. El navegador de las pruebas corre DENTRO
de `jmeter_backend`, donde el 3000 no es de nadie: sin este relé el iframe sale
vacío y la prueba no comprueba nada.

No toca configuración ni contenedores: es un proceso más dentro del backend.
"""
import asyncio

DESTINO = ("jmeter_grafana", 3000)
ESCUCHA = ("127.0.0.1", 3000)


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
