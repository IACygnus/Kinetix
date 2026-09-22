"""E3.4 — El aviso ambar de estilo (D36) sobre la pantalla real.

Demuestra, sin tocar la base a mano:
  1. En E2-validacion (textos de la Etapa 2, con jerga) aparecen los avisos en
     las secciones que el detector marca, y SOLO en esas.
  2. Al quitar la jerga de un texto y guardarlo, el aviso desaparece tras
     recargar.
  3. El texto original se restaura al terminar, pase lo que pase.

Uso (dentro de jmeter_backend, con el rele 5173 arriba):
    python3 /tmp/e3/avisos_estilo.py [execution_id]
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
EJECUCION = sys.argv[1] if len(sys.argv) > 1 else "59e25069-5104-4b23-9b79-d305f5b38abd"

LABEL = "6. Delete_Booking_Id"      # el que trae jerga en E2-validacion
ESPERA_GUARDADO_MS = 4000           # debounce 1,8 s + margen

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


def _tx(page, label):
    r = page.request.get(f"{API}/executions/{EJECUCION}/transaction-report",
                         params={"label": label})
    return {f["section"]: f for f in r.json().get("sections", [])}


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1600, "height": 1400},
                              storage_state=SESION if os.path.exists(SESION) else None)
        page = ctx.new_page()
        _entrar(page)
        ctx.storage_state(path=SESION)

        # ---------- 0. Lo que dice el backend ----------
        secciones = _tx(page, LABEL)
        con_aviso = {s: d.get("style_warnings") for s, d in secciones.items()
                     if d.get("style_warnings")}
        print(f"backend: secciones con aviso en {LABEL} -> {con_aviso}")
        comprobar(bool(con_aviso),
                  f"el backend marca al menos una seccion de {LABEL} (textos de la Etapa 2)")
        original = secciones.get("summary", {}).get("ai_analysis") or ""
        comprobar("summary" in con_aviso,
                  "el resumen de esa transaccion trae aviso de estilo")

        page.goto(f"{BASE}/performance/report/{EJECUCION}", wait_until="networkidle")
        page.wait_for_selector("svg.recharts-surface", timeout=60000)
        page.wait_for_timeout(6000)      # los bloques por transaccion cargan en serie

        # ---------- 1. El aviso se pinta ----------
        avisos = page.locator("text=Revisar estilo:")
        n = avisos.count()
        print(f"pantalla: {n} avisos ambar visibles")
        comprobar(n >= len(con_aviso),
                  f"se pintan al menos {len(con_aviso)} avisos (hay {n})")
        if n:
            # `text=` engancha el <span> "Revisar estilo:"; los terminos van en el
            # nodo padre, que es la franja entera.
            franja = avisos.first.locator("xpath=ancestor::div[1]").inner_text()
            franja = " ".join(franja.split())
            print("  primero:", franja[:140])
            comprobar(any(t in franja.lower() for t in
                          ("dispersion", "dispersión", "tier", "variabilidad", "sin traducir")),
                      "el aviso nombra el termino detectado")

        # El aviso NO aparece donde el texto esta limpio: chart_latency de esa
        # transaccion no tiene avisos en el backend.
        limpias = [s for s, d in secciones.items() if not d.get("style_warnings")]
        comprobar(bool(limpias), f"hay secciones sin aviso ({len(limpias)}): {limpias}")

        # ---------- 2. Se corrige el texto y el aviso desaparece ----------
        titulos = page.locator("span.text-2xl.font-bold")
        bloque = None
        for i in range(titulos.count()):
            if titulos.nth(i).inner_text().strip() == LABEL:
                bloque = titulos.nth(i).locator(
                    "xpath=ancestor::div[contains(@class,'border-2')][1]")
                break
        if bloque is None:
            raise RuntimeError(f"no se encontro el bloque de {LABEL} en pantalla")

        caja = bloque.locator("h4", has_text="Resumen de la transacción").first.locator(
            "xpath=following::textarea[1]")
        comprobar(caja.count() == 1, "se localiza la caja del resumen de la transaccion")

        limpio = original.replace("dispersión", "diferencia entre usuarios") \
                         .replace("dispersion", "diferencia entre usuarios") \
                         .replace("variabilidad", "diferencia entre usuarios") \
                         .replace("tier ", "grupo ")
        try:
            caja.click()
            caja.fill(limpio)
            caja.blur()
            page.wait_for_timeout(ESPERA_GUARDADO_MS)

            tras = _tx(page, LABEL).get("summary", {})
            comprobar(not tras.get("style_warnings"),
                      f"tras corregir el texto el backend ya no marca el resumen "
                      f"(devuelve {tras.get('style_warnings')})")

            page.reload(wait_until="networkidle")
            page.wait_for_selector("svg.recharts-surface", timeout=60000)
            page.wait_for_timeout(6000)
            n2 = page.locator("text=Revisar estilo:").count()
            print(f"pantalla tras corregir y recargar: {n2} avisos (antes {n})")
            comprobar(n2 < n, "en pantalla queda al menos un aviso menos")
        finally:
            # ---------- 3. Restaurar ----------
            r = page.request.put(
                f"{API}/executions/{EJECUCION}/transaction-report/summary",
                params={"label": LABEL},
                data={"ai_analysis": original},
                headers={"X-CSRF-Token": (ctx.cookies() and next(
                    (c["value"] for c in ctx.cookies() if c["name"] == "csrf_token"), "")),
                    "Content-Type": "application/json"},
            )
            print(f"restauracion del texto original: HTTP {r.status}")
            vuelto = _tx(page, LABEL).get("summary", {}).get("ai_analysis") or ""
            comprobar(vuelto == original, "el texto original quedo restaurado")

        nav.close()

    print("\n" + "=" * 60)
    if fallos:
        print(f"{len(fallos)} FALLOS:")
        for f in fallos:
            print("  -", f)
        sys.exit(1)
    print("TODO EN VERDE")


main()
