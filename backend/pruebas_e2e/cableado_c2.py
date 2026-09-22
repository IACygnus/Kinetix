"""Prueba de cableado (C2): cada caja de analisis guarda en SU canal.

Lo que demuestra, sobre la pantalla real y sin tocar la base a mano:

  1. Editar la caja de "Latency Over Time" DENTRO del bloque de una transaccion
     escribe en transaction_chart_analyses (seccion chart_latency de ESE label)
     y NO toca el campo general ai_analysis_latency de la ejecucion.
  2. Editar la caja de "Latency Over Time" del informe GENERAL escribe en
     ai_analysis_latency y NO toca ninguna fila por transaccion.

Deja las dos cajas como estaban: guarda el texto original y lo devuelve al final,
pase lo que pase.

Uso (dentro de jmeter_backend, con el rele 5173 arriba):
    python3 /tmp/e2e/cableado_c2.py [execution_id]
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
USUARIO = os.environ.get("KX_USER", "admin")
CLAVE = os.environ.get("KX_PWD", "")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
EJECUCION = sys.argv[1] if len(sys.argv) > 1 else "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8"

GRAFICA = "Latency Over Time"      # existe en los dos alcances
CAMPO_GENERAL = "ai_analysis_latency"
SECCION_TX = "chart_latency"
ESPERA_GUARDADO_MS = 4000          # debounce 1,8 s + margen

fallos = []


def comprobar(ok, texto):
    print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
    if not ok:
        fallos.append(texto)


def _login(page):
    page.locator('input[type="text"]').first.fill(USUARIO)
    page.locator('input[type="password"]').first.fill(CLAVE)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/dashboard", timeout=30000)


def _entrar(page):
    """Un solo login si hace falta. El limitador cuenta tambien los correctos."""
    page.goto(BASE, wait_until="networkidle")
    if page.locator('input[type="password"]').count():
        _login(page)
        return
    r = page.request.get(f"{API}/auth/me")
    if r.status == 401:
        page.goto(BASE, wait_until="networkidle")
        if not page.locator('input[type="password"]').count():
            raise RuntimeError("401 en /auth/me y no aparece el formulario")
        _login(page)
    elif r.status != 200:
        raise RuntimeError(f"/auth/me devolvio {r.status}; se aborta sin reintentar")


def _general(page):
    return page.request.get(f"{API}/executions/{EJECUCION}").json()


def _tx(page, label):
    r = page.request.get(f"{API}/executions/{EJECUCION}/transaction-report",
                         params={"label": label})
    filas = r.json().get("sections", [])
    return {f["section"]: (f.get("ai_analysis") or "") for f in filas}


def _escribir(caja, texto):
    caja.click()
    caja.fill(texto)
    caja.blur()


def main():
    marca = f"[cableado {int(time.time())}]"
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1600, "height": 1200},
                              storage_state=SESION if os.path.exists(SESION) else None)
        page = ctx.new_page()
        _entrar(page)
        ctx.storage_state(path=SESION)

        page.goto(f"{BASE}/performance/report/{EJECUCION}", wait_until="networkidle")
        page.wait_for_selector("svg.recharts-surface", timeout=60000)
        page.wait_for_timeout(4000)      # las transacciones cargan en serie

        # El titulo de cada bloque por transaccion es el nombre exacto (D16).
        titulos = page.locator("span.text-2xl.font-bold")
        if not titulos.count():
            raise RuntimeError("no hay bloques por transaccion en esta ejecucion")
        label = titulos.first.inner_text().strip()
        print(f"transaccion de prueba: {label}")

        bloque = titulos.first.locator("xpath=ancestor::div[contains(@class,'border-2')][1]")
        caja_tx = bloque.locator("h3", has_text=GRAFICA).first.locator("xpath=following::textarea[1]")
        caja_gen = page.locator("h3", has_text=GRAFICA).first.locator("xpath=following::textarea[1]")
        comprobar(caja_tx.count() == 1, f"la caja de {GRAFICA} existe dentro del bloque de {label}")
        comprobar(caja_gen.count() == 1, f"la caja de {GRAFICA} existe en el informe general")

        gen0 = _general(page).get(CAMPO_GENERAL) or ""
        tx0 = _tx(page, label)
        original_tx = tx0.get(SECCION_TX, "")
        print(f"estado inicial: general {len(gen0)} chars · {SECCION_TX} de {label} {len(original_tx)} chars")

        try:
            # ---- 1. alcance transaccion ----
            _escribir(caja_tx, f"{original_tx}\n{marca} TX")
            page.wait_for_timeout(ESPERA_GUARDADO_MS)
            tx1 = _tx(page, label)
            gen1 = _general(page).get(CAMPO_GENERAL) or ""
            comprobar(marca in tx1.get(SECCION_TX, ""),
                      f"editar dentro del bloque escribe en transaction_chart_analyses/{SECCION_TX} de {label}")
            comprobar(marca not in gen1,
                      f"esa edicion NO toca el campo general {CAMPO_GENERAL}")
            otras = {s: t for s, t in tx1.items() if s != SECCION_TX and marca in t}
            comprobar(not otras, "esa edicion NO toca las demas secciones de la transaccion")

            # ---- 2. alcance general ----
            _escribir(caja_gen, f"{gen0}\n{marca} GEN")
            page.wait_for_timeout(ESPERA_GUARDADO_MS)
            gen2 = _general(page).get(CAMPO_GENERAL) or ""
            tx2 = _tx(page, label)
            comprobar(f"{marca} GEN" in gen2,
                      f"editar en el informe general escribe en {CAMPO_GENERAL}")
            comprobar(f"{marca} GEN" not in tx2.get(SECCION_TX, ""),
                      "esa edicion NO toca la fila por transaccion")
        finally:
            # ---- restitucion ----
            _escribir(caja_tx, original_tx)
            page.wait_for_timeout(ESPERA_GUARDADO_MS)
            _escribir(caja_gen, gen0)
            page.wait_for_timeout(ESPERA_GUARDADO_MS)
            tx3 = _tx(page, label).get(SECCION_TX, "")
            gen3 = _general(page).get(CAMPO_GENERAL) or ""
            comprobar(tx3 == original_tx, "el texto de la transaccion queda como estaba")
            comprobar(gen3 == gen0, "el texto general queda como estaba")
            nav.close()

    print(f"\n=== {'CABLEADO CORRECTO' if not fallos else f'{len(fallos)} FALLOS'} ===")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
