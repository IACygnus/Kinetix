"""ETAPA 6.2 — capas y tooltip en pantalla (D46, D47, D48).

    docker exec -e KX_PWD=... jmeter_backend python3 /tmp/e2e/capas_tooltip.py <exec_id>

Comprueba, sobre un informe YA GENERADO (0 llamadas a la IA):

  1. Hay un selector de capas en la grafica Response Times del informe general y
     otro en cada bloque por transaccion. Solo ahi: ninguna otra grafica lo lleva.
  2. "Promedio" deja solo lineas solidas, "Máximo" solo punteadas y "Ambas" las
     dos. Se cuentan los trazos reales del SVG, no las clases del boton.
  3. El tooltip trae UNA linea por transaccion visible, con el maximo plegado
     dentro ("Auth  422 ms (máx. 1.013 ms)") y sin ninguna entrada "(max)".
  4. Capa y leyenda son ejes independientes: una transaccion apagada en la
     leyenda sigue apagada en cualquier capa, y no aparece en el tooltip.
  5. La seleccion es POR GRAFICA: cambiar la del general no mueve la del bloque.
"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
USUARIO = os.environ.get("KX_USER", "admin")
CLAVE = os.environ.get("KX_PWD", "")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")

EJECUCION = sys.argv[1] if len(sys.argv) > 1 else "20bb2356-410d-465f-8717-c9a025e26e03"

fallos = []


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
    """Un solo login: /auth/login limita a 5 por 15 min y por IP, y cuenta los
    correctos. Nunca un bucle de reintentos."""
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
    """Espera a que el numero de graficas se repita durante 2 s."""
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
    raise RuntimeError(f"la pagina no se estabilizo ({previo} graficas)")


def tarjeta(page, i):
    """La tarjeta de grafica que contiene el i-esimo selector de capas."""
    return page.locator("[data-testid='selector-capas']").nth(i).locator("xpath=../..")


def trazos(card):
    """(solidos, punteados) de esa tarjeta. recharts NO pinta una Line con
    hide=true, asi que contar trazos es contar lo que se ve."""
    lineas = card.locator("path.recharts-line-curve")
    sol = pun = 0
    for k in range(lineas.count()):
        da = lineas.nth(k).get_attribute("stroke-dasharray")
        if da and da.strip():
            pun += 1
        else:
            sol += 1
    return sol, pun


def pulsar(card, capa):
    card.locator(f"[data-testid='selector-capas'] [data-capa='{capa}']").click()
    card.page.wait_for_timeout(400)


def tooltip(card):
    """Pasa el cursor por el centro del area de trazado y devuelve las filas
    del tooltip como [(nombre, valor)]."""
    svg = card.locator("svg.recharts-surface").first
    caja = svg.bounding_box()
    page = card.page
    filas = []
    # Varias posiciones: en un hueco de la serie el tooltip puede no tener filas.
    for frac in (0.5, 0.35, 0.65, 0.2):
        page.mouse.move(caja["x"] + caja["width"] * frac, caja["y"] + caja["height"] * 0.5)
        page.wait_for_timeout(350)
        tt = page.locator(".recharts-tooltip-wrapper div.bg-slate-900").first
        if not tt.count():
            continue
        nombres = tt.locator("span.truncate")
        valores = tt.locator("span.font-mono.font-semibold")
        if valores.count() == 0:
            continue
        filas = [(nombres.nth(k).inner_text().strip(), valores.nth(k).inner_text().strip())
                 for k in range(valores.count())]
        if filas:
            break
    page.mouse.move(5, 5)
    page.wait_for_timeout(200)
    return filas


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        import pathlib
        estado = SESION if pathlib.Path(SESION).exists() else None
        ctx = nav.new_context(viewport={"width": 1600, "height": 1200},
                              storage_state=estado, locale="es-CO")
        page = ctx.new_page()
        _entrar(page)
        ctx.storage_state(path=SESION)
        page.goto(f"{BASE}/performance/report/{EJECUCION}", wait_until="networkidle")
        n = _estable(page)
        print(f"informe cargado: {n} graficas\n")

        sels = page.locator("[data-testid='selector-capas']")
        n_sel = sels.count()
        print(f"--- 1. Cuantos selectores y donde ---")
        ok(n_sel >= 2, f"hay {n_sel} selectores de capas (1 del general + 1 por transaccion)")
        # Ninguna grafica de una sola capa lo lleva: los selectores tienen que ser
        # tantos como graficas con serie punteada.
        con_punteada = 0
        for k in range(page.locator("svg.recharts-surface").count()):
            svg = page.locator("svg.recharts-surface").nth(k)
            das = svg.locator("path.recharts-line-curve[stroke-dasharray]")
            if das.count():
                con_punteada += 1
        ok(n_sel == con_punteada,
           f"{n_sel} selectores para {con_punteada} graficas con serie dual (uno por grafica, D46)")
        titulos = [tarjeta(page, i).locator("h3").first.inner_text().strip() for i in range(n_sel)]
        ok(all("Response Times" in t for t in titulos),
           f"todos en Response Times: {titulos}")
        ok(all("Transacción" in t for t in titulos),
           "el titulo lleva tilde: 'Response Times por Transacción'")

        print("\n--- 2. Las tres capas, en el general (indice 0) ---")
        gen = tarjeta(page, 0)
        s0, p0 = trazos(gen)
        ok(s0 > 0 and p0 > 0, f"por defecto 'Ambas': {s0} solidas + {p0} punteadas")
        ok(gen.locator("[data-capa='ambas'][aria-pressed='true']").count() == 1,
           "'Ambas' viene marcado por defecto (D46)")

        pulsar(gen, "maximo")
        s1, p1 = trazos(gen)
        ok(s1 == 0 and p1 == p0, f"'Máximo': {s1} solidas + {p1} punteadas")

        pulsar(gen, "promedio")
        s2, p2 = trazos(gen)
        ok(p2 == 0 and s2 == s0, f"'Promedio': {s2} solidas + {p2} punteadas")

        print("\n--- 3. El tooltip: una linea por transaccion (D47) ---")
        pulsar(gen, "ambas")
        filas = tooltip(gen)
        print("   " + " | ".join(f"{a} -> {b}" for a, b in filas))
        ok(len(filas) > 0, f"el tooltip trae {len(filas)} fila(s)")
        ok(all("(max)" not in a for a in [f[0] for f in filas]),
           "ninguna fila se llama '… (max)'")
        nombres = [f[0] for f in filas]
        ok(len(nombres) == len(set(nombres)), f"sin nombres repetidos: {nombres}")
        ok(len(filas) == s0, f"{len(filas)} filas para {s0} transacciones visibles")
        con_max = [v for _, v in filas if "máx." in v]
        ok(len(con_max) == len(filas),
           f"las {len(filas)} filas plegan su maximo: ej. {filas[0][1] if filas else ''}")
        ok(all(re.match(r"^[\d.,]+ ms \(máx\. [\d.,]+ ms\)$", v) for _, v in filas),
           "formato D47 exacto: '422 ms (máx. 1.013 ms)'")

        pulsar(gen, "maximo")
        filas_max = tooltip(gen)
        print("   " + " | ".join(f"{a} -> {b}" for a, b in filas_max))
        ok(len(filas_max) == len(filas), f"con una sola capa siguen {len(filas_max)} filas")
        ok(all("máx." not in v for _, v in filas_max),
           "con una sola capa se muestra solo ese valor, sin el rotulo 'máx.'")
        pulsar(gen, "ambas")

        print("\n--- 4. Capa y leyenda son ejes independientes ---")
        botones = gen.locator("div.w-full.px-2 button")
        # El primero es el maestro 'Ocultar todas' cuando hay mas de una serie.
        idx = 1 if botones.count() > s0 else 0
        apagada = botones.nth(idx).inner_text().strip()
        botones.nth(idx).click()
        page.wait_for_timeout(400)
        s3, p3 = trazos(gen)
        ok(s3 == s0 - 1 and p3 == p0 - 1,
           f"apagar '{apagada}' en la leyenda quita sus DOS capas: {s3}+{p3}")
        pulsar(gen, "maximo")
        s4, p4 = trazos(gen)
        ok(s4 == 0 and p4 == p0 - 1, f"sigue apagada en la capa 'Máximo': {s4}+{p4}")
        filas_leg = tooltip(gen)
        ok(all(apagada not in nom for nom, _ in filas_leg),
           f"'{apagada}' tampoco aparece en el tooltip")
        pulsar(gen, "ambas")
        botones.nth(idx).click()
        page.wait_for_timeout(400)

        print("\n--- 5. La seleccion es por grafica (D46) ---")
        tx = tarjeta(page, 1)
        st0, pt0 = trazos(tx)
        ok(st0 > 0 and pt0 > 0, f"el bloque por transaccion abre en 'Ambas': {st0}+{pt0}")
        pulsar(tx, "maximo")
        st1, pt1 = trazos(tx)
        sg, pg = trazos(gen)
        ok(st1 == 0, f"la transaccion pasa a 'Máximo': {st1}+{pt1}")
        ok(sg == s0 and pg == p0, f"el general NO se movio: {sg}+{pg}")
        ok(gen.locator("[data-capa='ambas'][aria-pressed='true']").count() == 1,
           "el selector del general sigue en 'Ambas'")
        filas_tx = tooltip(tx)
        print("   " + " | ".join(f"{a} -> {b}" for a, b in filas_tx))
        ok(len(filas_tx) == 1 and "(max)" not in filas_tx[0][0],
           f"el tooltip del bloque trae 1 fila: {filas_tx}")

        print("\n--- 6. La seleccion no se persiste (D48) ---")
        page.reload(wait_until="networkidle")
        _estable(page)
        ok(page.locator("[data-testid='selector-capas'] [data-capa='ambas'][aria-pressed='true']").count()
           == page.locator("[data-testid='selector-capas']").count(),
           "tras recargar, todas las graficas vuelven a 'Ambas'")

        page.screenshot(path="/tmp/e2e_salida/etapa6_2_capas.png", full_page=True)
        nav.close()

    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("6.2 — CAPAS Y TOOLTIP EN PANTALLA: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
