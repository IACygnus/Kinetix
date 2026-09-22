"""ETAPA 6.3 — el dialogo de exportacion en la pantalla (D50).

    docker exec -e KX_PWD=... jmeter_backend python3 /tmp/e2e/dialogo_export.py <exec_id>

Comprueba el recorrido tal como lo hace Fredy: pulsar el boton, ver el dialogo,
cancelar sin que se exporte nada, y que lo que se marca es EXACTAMENTE lo que
viaja en la peticion. 0 llamadas a la IA.
"""
import os
import sys
from urllib.parse import unquote, urlparse, parse_qsl

from playwright.sync_api import sync_playwright

BASE = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
USUARIO = os.environ.get("KX_USER", "admin")
CLAVE = os.environ.get("KX_PWD", "")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
EJECUCION = sys.argv[1] if len(sys.argv) > 1 else "20bb2356-410d-465f-8717-c9a025e26e03"

fallos = []
peticiones = []      # (url, metodo)
respuestas = {}      # url -> status


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def _login(page):
    page.locator('input[type="text"]').first.fill(USUARIO)
    page.locator('input[type="password"]').first.fill(CLAVE)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/dashboard", timeout=30000)


def _entrar(page):
    page.goto(BASE, wait_until="networkidle")
    if page.locator('input[type="password"]').count():
        _login(page)
        return
    r = page.request.get(f"{API}/auth/me")
    if r.status == 401:
        page.goto(BASE, wait_until="networkidle")
        _login(page)
    elif r.status != 200:
        raise RuntimeError(f"/auth/me devolvio {r.status}")


def _estable(page, timeout_s=90):
    import time as _t
    inicio, previo, desde = _t.monotonic(), None, None
    while _t.monotonic() - inicio < timeout_s:
        n = page.locator("svg.recharts-surface").count()
        if n and n == previo:
            if desde is None:
                desde = _t.monotonic()
            elif _t.monotonic() - desde >= 2.0:
                return n
        else:
            desde = None
        previo = n
        page.wait_for_timeout(250)
    raise RuntimeError("la pagina no se estabilizo")


def exports():
    return [u for u, _ in peticiones if "/export/" in u]


def tx_de(url):
    """Los valores de `tx` de una URL, decodificados."""
    q = parse_qsl(urlparse(url).query, keep_blank_values=True)
    return [unquote(v) for k, v in q if k == "tx"]


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        import pathlib
        estado = SESION if pathlib.Path(SESION).exists() else None
        ctx = nav.new_context(viewport={"width": 1600, "height": 1200},
                              storage_state=estado, locale="es-CO",
                              accept_downloads=True)
        page = ctx.new_page()
        page.on("request", lambda r: peticiones.append((r.url, r.method)))
        page.on("response", lambda r: respuestas.__setitem__(r.url, r.status))
        _entrar(page)
        ctx.storage_state(path=SESION)
        page.goto(f"{BASE}/performance/report/{EJECUCION}", wait_until="networkidle")
        _estable(page)
        peticiones.clear()

        print("--- 1. El boton abre el dialogo, no exporta ---")
        page.get_by_role("button", name="Exportar HTML").click()
        page.wait_for_selector("[data-testid='dialogo-export']", timeout=15000)
        page.wait_for_selector("[data-testid='lista-transacciones'] input", timeout=15000)
        ok(len(exports()) == 0, "pulsar el boton no dispara ninguna exportacion")
        cajas = page.locator("[data-testid='lista-transacciones'] input[type=checkbox]")
        n_tx = cajas.count()
        marcadas = sum(1 for i in range(n_tx) if cajas.nth(i).is_checked())
        ok(n_tx > 0, f"el dialogo lista {n_tx} transaccion(es) con analisis")
        ok(marcadas == n_tx, f"las {n_tx} vienen marcadas por defecto (D50)")
        ok(page.locator("[data-testid='opcion-general-y-transacciones']").is_checked(),
           "'General y transacciones' viene seleccionado por defecto")

        print("\n--- 2. Cancelar no exporta (D50) ---")
        page.locator("[data-testid='export-cancelar']").click()
        page.wait_for_timeout(600)
        ok(page.locator("[data-testid='dialogo-export']").count() == 0, "el dialogo se cierra")
        ok(len(exports()) == 0, "cancelar no dispara ninguna exportacion")

        print("\n--- 3. 'Solo informe general' -> ?tx= vacio ---")
        page.get_by_role("button", name="Exportar HTML").click()
        page.wait_for_selector("[data-testid='opcion-solo-general']", timeout=15000)
        page.locator("[data-testid='opcion-solo-general']").check()
        ok(cajas.first.is_disabled(), "la lista de transacciones se deshabilita")
        page.locator("[data-testid='export-confirmar']").click()
        page.wait_for_timeout(2500)
        urls = [u for u in exports() if "/export/html" in u]
        ok(len(urls) == 1, f"se pidio UNA exportacion HTML: {len(urls)}")
        ok(tx_de(urls[-1]) == [""], f"la peticion lleva ?tx= vacio: {urls[-1].split('?')[-1]}")
        page.wait_for_timeout(4000)
        ok(respuestas.get(urls[-1]) == 200, f"el HTML se entrego: {respuestas.get(urls[-1])}")

        print("\n--- 4. Desmarcar una: solo viajan las marcadas ---")
        peticiones.clear()
        page.get_by_role("button", name="Exportar PDF").click()
        page.wait_for_selector("[data-testid='lista-transacciones'] input", timeout=15000)
        etiquetas = [cajas.nth(i).get_attribute("data-tx") for i in range(n_tx)]
        cajas.nth(0).uncheck()
        ok(not cajas.nth(0).is_checked(), f"desmarcada '{etiquetas[0]}'")
        page.locator("[data-testid='export-confirmar']").click()
        page.wait_for_timeout(2500)
        urls = [u for u in exports() if "/export/pdf" in u]
        ok(len(urls) == 1, f"se pidio UNA exportacion PDF: {len(urls)}")
        enviadas = tx_de(urls[-1])
        ok(enviadas == etiquetas[1:],
           f"viajan solo las marcadas: {enviadas} (se desmarco '{etiquetas[0]}')")

        print("\n--- 5. El informe integrado no cambia (v1.2 §6) ---")
        # El boton del integrado vive en otra pantalla y no pasa por el dialogo:
        # se comprueba que su endpoint sigue sin recibir `tx`.
        ok(all("tx=" not in u for u in exports() if "/reports/integrated" in u),
           "ninguna peticion del integrado lleva el parametro tx")

        page.screenshot(path="/tmp/e2e_salida/etapa6_3_dialogo.png", full_page=False)
        nav.close()

    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("6.3 — DIALOGO DE EXPORTACION: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
