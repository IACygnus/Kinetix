"""Comprueba en PANTALLA el estado de 919b350d tras la perdida (reporte 38)."""
import os, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
USUARIO, CLAVE = os.environ.get("KX_USER", "admin"), os.environ.get("KX_PWD", "")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
EJ = "919b350d-61f5-4c74-bd51-bf812f48f7e0"


def _entrar(page):
    page.goto(BASE, wait_until="networkidle")
    if page.locator('input[type="password"]').count():
        page.locator('input[type="text"]').first.fill(USUARIO)
        page.locator('input[type="password"]').first.fill(CLAVE)
        page.locator('button[type="submit"]').first.click()
        page.wait_for_url("**/dashboard", timeout=30000)


with sync_playwright() as p:
    nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = nav.new_context(viewport={"width": 1600, "height": 1400},
                          storage_state=SESION if os.path.exists(SESION) else None)
    page = ctx.new_page()
    _entrar(page)
    ctx.storage_state(path=SESION)

    for ruta in ("monitoring-analysis", "evidence-analysis"):
        r = page.request.get(f"{API}/executions/{EJ}/{ruta}")
        d = r.json()
        print(f"API {ruta:20s} -> analisis={d.get('analysis')!r} "
              f"avisos={d.get('style_warnings')}")

    r = page.request.get(f"{API}/executions/{EJ}/image-analyses",
                         params={"attachment_type": "monitoring"})
    print(f"API image-analyses (monitoring) -> {len(r.json())} imagenes, "
          f"{sum(1 for a in r.json() if a.get('ai_analysis'))} con analisis")
    r = page.request.get(f"{API}/executions/{EJ}/image-analyses",
                         params={"attachment_type": "evidence"})
    print(f"API image-analyses (evidence)   -> {len(r.json())} imagenes, "
          f"{sum(1 for a in r.json() if a.get('ai_analysis'))} con analisis")

    for pagina, titulo in (("monitoring", "Analisis Global de Metricas"),
                           ("evidence", "Analisis Global de Evidencias")):
        page.goto(f"{BASE}/performance/{pagina}", wait_until="networkidle")
        page.wait_for_timeout(2500)
        # La pagina elige la ejecucion con un <select>, no por la URL.
        sel = page.locator("select").first
        opciones = sel.locator("option")
        valor = None
        for i in range(opciones.count()):
            v = opciones.nth(i).get_attribute("value") or ""
            if v.startswith(EJ[:8]) or "prueba final 2" in (opciones.nth(i).inner_text() or ""):
                valor = v
                break
        if not valor:
            print(f"pantalla /{pagina}: 'prueba final 2' no esta entre las "
                  f"{opciones.count()} opciones del selector")
            continue
        sel.select_option(valor)
        page.wait_for_timeout(4000)
        hay_global = page.locator(f"text={titulo}").count()
        boton = page.locator("text=Generar Analisis Global").count()
        cajas = page.locator("h4:has-text('Analisis')").count()
        print(f"pantalla /{pagina:11s} -> caja de analisis global: {hay_global} · "
              f"boton para generarlo: {boton} · analisis por imagen en pantalla: {cajas}")
        page.screenshot(path=f"/tmp/e3/919b_{pagina}.png", full_page=False)
    nav.close()
print("captura en /tmp/e3/919b_monitoring.png")
