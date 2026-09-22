"""ETAPA 7.1 — que pinta HOY la pantalla del informe integrado (read-only).

    docker exec -e KX_PWD=... jmeter_backend python3 /tmp/e2e/pantalla_integrado_71.py [rid]

Abre el integrado y cuenta lo que se ve, y lo compara con lo que la MISMA
ejecucion pinta en Historial Reporte. No edita ni genera nada. 0 llamadas a la IA.
"""
import os
import sys

from playwright.sync_api import sync_playwright

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
RID = sys.argv[1] if len(sys.argv) > 1 else "8713aad1-5de9-4dcb-b294-360ce8ecaee8"
EJEC = sys.argv[2] if len(sys.argv) > 2 else "20bb2356-410d-465f-8717-c9a025e26e03"


def estable(page, timeout_s=120):
    import time as _t
    ini, prev, desde = _t.monotonic(), None, None
    while _t.monotonic() - ini < timeout_s:
        n = page.locator("svg.recharts-surface").count()
        if n and n == prev:
            if desde is None:
                desde = _t.monotonic()
            elif _t.monotonic() - desde >= 2.5:
                return n
        else:
            desde = None
        prev = n
        page.wait_for_timeout(300)
    return prev or 0


def medir(page, url, etiqueta):
    page.goto(url, wait_until="networkidle")
    n_graf = estable(page)
    # El titulo de un bloque por transaccion en pantalla es un h3 con el nombre;
    # el marcador estable es el encabezado navy de TransactionReportSection.
    bloques = page.locator("[data-testid='bloque-transaccion']").count()
    # Respaldo por texto, por si el componente no lleva testid.
    rt = page.get_by_text("Response Times por Transacción", exact=False).count()
    resumenes = page.get_by_text("Reporte Resumen", exact=False).count()
    print(f"  {etiqueta}")
    print(f"     graficas recharts        : {n_graf}")
    print(f"     'Response Times por Tx'  : {rt}")
    print(f"     tablas 'Reporte Resumen' : {resumenes}")
    print(f"     bloques con testid       : {bloques}")
    return {"graficas": n_graf, "rt": rt, "resumenes": resumenes}


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1400},
                              storage_state=SESION if os.path.exists(SESION) else None,
                              locale="es-CO")
        page = ctx.new_page()
        page.goto(WEB, wait_until="networkidle")
        if page.locator('input[type="password"]').count():
            page.locator('input[type="text"]').first.fill(os.environ.get("KX_USER", "admin"))
            page.locator('input[type="password"]').first.fill(os.environ.get("KX_PWD", ""))
            page.locator('button[type="submit"]').first.click()
            page.wait_for_url("**/dashboard", timeout=30000)
            ctx.storage_state(path=SESION)

        print("--- Historial Reporte (informe individual) ---")
        ind = medir(page, f"{WEB}/performance/report/{EJEC}", "E3-estilo-pruebakinetix, suelto")

        print("\n--- Historial Integrado (la misma ejecucion, embebida) ---")
        inte = medir(page, f"{WEB}/performance/integrated/{RID}", "el integrado entero")

        print("\n" + "=" * 70)
        print(f"individual : {ind['graficas']} graficas · {ind['rt']} 'Response Times por Tx' · "
              f"{ind['resumenes']} tablas resumen")
        print(f"integrado  : {inte['graficas']} graficas · {inte['rt']} 'Response Times por Tx' · "
              f"{inte['resumenes']} tablas resumen")
        print("=" * 70)
        page.screenshot(path="/tmp/e2e_salida/etapa7_1_integrado.png", full_page=False)
        nav.close()
    return 0


sys.exit(main())
