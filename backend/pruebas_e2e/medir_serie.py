"""Mide la carga EN SERIE de los bloques por transaccion y el bloqueo del event loop.

Reproduce lo que hace la pantalla tras el ajuste de 2.6: pide
/transaction-charts de cada transaccion una tras otra. Mientras tanto, una sonda
independiente golpea /auth/me cada 100 ms y se queda con el PEOR tiempo: ese
numero es el que dice si el proceso quedo sordo mientras parseaba el JTL.

Uso (dentro de jmeter_backend):
    python3 /tmp/e2e/medir_serie.py <execution_id> [execution_id...]

Las cookies salen de la sesion de Playwright (/tmp/e2e_sesion.json): no gasta
cupo del limitador de /auth/login.
"""
import asyncio
import json
import os
import sys
import time

import httpx

API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
MODO = os.environ.get("KX_MODO", "serie")      # serie (hoy) o paralelo (antes)


def _cookies():
    try:
        datos = json.load(open(SESION))
    except Exception:
        return {}
    return {c["name"]: c["value"] for c in datos.get("cookies", [])}


def _guardar_cookies(cli):
    """Refresca el fichero de sesion que comparte con Playwright."""
    try:
        datos = json.load(open(SESION))
    except Exception:
        datos = {"cookies": [], "origins": []}
    # Por el tarro, no por .items(): si quedo una cookie vieja con el mismo nombre
    # httpx levanta CookieConflict. El dict se queda con la ultima, que es la nueva.
    vals = {}
    for c in cli.cookies.jar:
        vals[c.name] = c.value
    # OJO con httpOnly: csrf_token TIENE que ser legible por JS — el interceptor de
    # axios lo saca de document.cookie para mandar la cabecera X-CSRF-Token. Si se
    # guarda como httpOnly, el navegador lo oculta, la cabecera viaja vacia y toda
    # mutacion responde 403 (que el navegador ademas reporta como error de CORS,
    # porque la respuesta del middleware no lleva Access-Control-Allow-Origin).
    datos["cookies"] = [{"name": k, "value": v, "domain": "localhost", "path": "/",
                         "expires": -1, "httpOnly": k == "access_token",
                         "secure": False, "sameSite": "Lax"} for k, v in vals.items()]
    json.dump(datos, open(SESION, "w"))


async def _asegurar_sesion(cli):
    """UN solo login si la sesion guardada ya no vale, nunca un bucle: el
    limitador de /auth/login cuenta tambien los logins correctos (5 por 15 min
    y por IP), asi que reintentar gasta cupo en vez de arreglar nada."""
    r = await cli.get(f"{API}/auth/me")
    if r.status_code == 200:
        return
    if r.status_code != 401:
        raise RuntimeError(f"/auth/me devolvio {r.status_code}; se aborta sin reintentar")
    print("  sesion caducada: un unico login")
    cli.cookies.clear()          # fuera la caducada antes de recibir la nueva
    r = await cli.post(f"{API}/auth/login",
                       data={"username": os.environ.get("KX_USER", "admin"),
                             "password": os.environ["KX_PWD"]})
    if r.status_code != 200:
        raise RuntimeError(f"login {r.status_code}: {r.text[:200]}")
    _guardar_cookies(cli)


async def _sonda(cli, parar, medidas):
    """Latido cada 100 ms contra /auth/me. Solo mide; no cambia nada."""
    while not parar.is_set():
        t0 = time.perf_counter()
        try:
            r = await cli.get(f"{API}/auth/me")
            ms = (time.perf_counter() - t0) * 1000
            medidas.append((ms, r.status_code))
        except Exception as e:
            medidas.append(((time.perf_counter() - t0) * 1000, str(e)[:40]))
        await asyncio.sleep(0.1)


async def medir(eid):
    async with httpx.AsyncClient(cookies=_cookies(), timeout=600.0) as cli:
        await _asegurar_sesion(cli)
        r = await cli.get(f"{API}/executions/{eid}/transaction-analyses")
        r.raise_for_status()
        d = r.json()
        labels = list(dict.fromkeys(
            [t["label"] for t in (d.get("transaction_analyses") or [])]
            + (d.get("report_labels") or [])))
        print(f"\n=== {eid} — {len(labels)} transaccion(es): {', '.join(labels) or 'ninguna'}")
        if not labels:
            return

        parar = asyncio.Event()
        medidas = []
        sonda = asyncio.create_task(_sonda(cli, parar, medidas))
        await asyncio.sleep(0.5)          # unos latidos de referencia en reposo

        async def _una(l):
            t0 = time.perf_counter()
            rr = await cli.get(f"{API}/executions/{eid}/transaction-charts",
                               params={"label": l})
            ms = (time.perf_counter() - t0) * 1000
            servidor = rr.json().get("elapsed_ms") if rr.status_code == 200 else "-"
            print(f"  {l[:46]:<46} {rr.status_code}  {ms:8.0f} ms  (servidor {servidor} ms)")

        t_total = time.perf_counter()
        if MODO == "paralelo":
            # Lo que hacia la pantalla ANTES del ajuste: todas a la vez.
            await asyncio.gather(*[_una(l) for l in labels])
        else:
            for l in labels:
                await _una(l)
        total = (time.perf_counter() - t_total) * 1000

        await asyncio.sleep(0.3)
        parar.set()
        await sonda

        lat = [m for m, _ in medidas]
        lat_ord = sorted(lat)
        p95 = lat_ord[int(len(lat_ord) * 0.95) - 1] if lat_ord else 0
        print(f"  {'TOTAL (' + MODO + ')':<46}      {total:8.0f} ms")
        print(f"  sonda /auth/me: {len(lat)} latidos · maximo {max(lat):.0f} ms · "
              f"p95 {p95:.0f} ms · mediana {lat_ord[len(lat_ord)//2]:.0f} ms")
        malos = [c for _, c in medidas if c != 200]
        if malos:
            print(f"  AVISO: {len(malos)} latidos no-200: {set(map(str, malos))}")
        print(f"  {'sonda por debajo de 100 ms':<46} {'PASA' if max(lat) < 100 else 'FALLA'}")


async def main():
    for eid in sys.argv[1:]:
        await medir(eid)


if __name__ == "__main__":
    asyncio.run(main())
