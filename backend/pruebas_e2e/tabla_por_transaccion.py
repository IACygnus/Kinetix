"""ETAPA 2 (D15) — la tabla resumen de cada bloque por transaccion.

Comprueba sobre la pantalla real que:
  1. cada bloque por transaccion tiene UNA tabla,
  2. con UNA sola fila de datos y sin fila TOTAL,
  3. y que sus celdas son EXACTAMENTE las de la fila de esa transaccion en la
     tabla resumen del informe general.

Uso (dentro de jmeter_backend, con el rele 5173 arriba):
    python3 /tmp/e2e/tabla_por_transaccion.py [execution_id]
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
USUARIO = os.environ.get("KX_USER", "admin")
CLAVE = os.environ.get("KX_PWD", "")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
EJECUCION = sys.argv[1] if len(sys.argv) > 1 else "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8"

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


def _celdas(fila):
    return [c.strip() for c in fila.locator("td").all_inner_texts()]


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1600, "height": 1200},
                              storage_state=SESION if os.path.exists(SESION) else None)
        page = ctx.new_page()
        _entrar(page)
        ctx.storage_state(path=SESION)
        page.goto(f"{BASE}/performance/report/{EJECUCION}", wait_until="networkidle")
        page.wait_for_selector("svg.recharts-surface", timeout=60000)
        page.wait_for_timeout(6000)     # los bloques cargan en serie

        # --- tabla del informe general: la PRIMERA titulada "Reporte Resumen".
        # No vale coger la primera tabla de la pagina: antes esta la de criterios
        # por transaccion (KNX-09), que tiene otras columnas.
        h2 = page.get_by_role("heading", name="Reporte Resumen").first
        general = h2.locator("xpath=ancestor::div[1]/following-sibling::table[1]")
        filas_gen = {}
        for i in range(general.locator("tbody tr").count()):
            c = _celdas(general.locator("tbody tr").nth(i))
            if c and not c[0].startswith("TOTAL"):
                filas_gen[c[0]] = c
        comprobar(len(filas_gen) >= 1, f"la tabla general trae {len(filas_gen)} transacciones")

        titulos = page.locator("span.text-2xl.font-bold")
        n = titulos.count()
        comprobar(n >= 1, f"hay {n} bloque(s) por transaccion")

        for i in range(n):
            label = titulos.nth(i).inner_text().strip()
            bloque = titulos.nth(i).locator("xpath=ancestor::div[contains(@class,'border-2')][1]")
            tablas = bloque.locator("table")
            comprobar(tablas.count() == 1, f"[{label}] tiene UNA tabla resumen")
            if tablas.count() != 1:
                continue
            filas = tablas.first.locator("tbody tr")
            comprobar(filas.count() == 1,
                      f"[{label}] la tabla tiene UNA fila y ninguna de TOTAL ({filas.count()})")
            if filas.count() != 1:
                continue
            c = _celdas(filas.first)
            esperado = filas_gen.get(label)
            if esperado is None:
                comprobar(False, f"[{label}] no esta en la tabla general")
                continue
            comprobar(c == esperado,
                      f"[{label}] sus celdas son las mismas que en la tabla general")
            if c != esperado:
                print("   general :", esperado)
                print("   bloque  :", c)

        # Las columnas tienen que ser las mismas, no solo los valores.
        cab_gen = [t.strip() for t in general.locator("thead th").all_inner_texts()]
        for i in range(n):
            bloque = titulos.nth(i).locator("xpath=ancestor::div[contains(@class,'border-2')][1]")
            if bloque.locator("table").count() != 1:
                continue
            cab = [t.strip() for t in bloque.locator("table thead th").all_inner_texts()]
            comprobar(cab == cab_gen,
                      f"[{titulos.nth(i).inner_text().strip()}] mismas columnas que el general")

        graficas = page.locator("svg.recharts-surface").count()
        # ETAPA 5: 11 del general + 5 por cada bloque. Antes estaba fijo en 26,
        # que son 3 transacciones, y fallaba con informes de otro numero.
        esperadas = 11 + 5 * n
        comprobar(graficas == esperadas,
                  f"son {esperadas} graficas: 11 del general + 5 x {n} transacciones ({graficas})")
        nav.close()

    print(f"\n=== {'TODO PASA' if not fallos else f'{len(fallos)} FALLOS'} ===")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
