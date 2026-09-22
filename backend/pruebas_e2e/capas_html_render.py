"""ETAPA 6.4 — el HTML exportado, abierto en Chromium (D49).

    docker exec jmeter_backend python3 /tmp/e2e/capas_html_render.py [ruta]

Abre el documento que dejo `capas_exportadas.py` (exportado con la general en
"Máximo") y comprueba lo que solo se puede ver en un navegador: que abre con esa
capa, que los botones alternan de verdad, que el hover muestra SOLO las trazas
visibles y que no hay un solo error de consola.
"""
import sys

from playwright.sync_api import sync_playwright

RUTA = sys.argv[1] if len(sys.argv) > 1 else "/tmp/e2e_capas.html"

fallos = []
errores_consola = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def visibles(page, chart_id):
    """Nombres de las trazas que Plotly esta pintando ahora mismo."""
    return page.evaluate(
        """(id) => {
            const d = document.getElementById(id);
            if (!d || !d.data) return null;
            return d.data.filter(t => t.visible === undefined || t.visible === true)
                         .map(t => t.name);
        }""", chart_id)


def hover(page, chart_id):
    """El texto del hover unificado de Plotly.

    Se lee por `textContent` y no por `inner_text`: son nodos <text> de SVG y
    Playwright devuelve cadena vacia para ellos, lo que haria pasar la
    comprobacion sin haber mirado nada.
    """
    caja = page.locator(f"#{chart_id} .nsewdrag").first.bounding_box()
    for frac in (0.5, 0.35, 0.65, 0.25, 0.8):
        page.mouse.move(5, 5)
        page.wait_for_timeout(150)
        page.mouse.move(caja["x"] + caja["width"] * frac,
                        caja["y"] + caja["height"] * 0.5)
        page.wait_for_timeout(500)
        txt = page.evaluate(
            """(id) => {
                const d = document.getElementById(id);
                const hl = d && d.querySelector('.hoverlayer');
                if (!hl) return '';
                return Array.from(hl.querySelectorAll('text'))
                            .map(t => t.textContent).filter(Boolean).join(' | ');
            }""", chart_id)
        if txt:
            return txt
    return ""


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = nav.new_context(viewport={"width": 1600, "height": 1200}).new_page()
        page.on("console", lambda m: errores_consola.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errores_consola.append(str(e)))
        page.goto(f"file://{RUTA}", wait_until="networkidle")
        page.wait_for_selector("#chart-rt-label .plotly", timeout=60000)
        page.wait_for_timeout(1500)

        print("--- 1. El documento abre con la capa recibida ---")
        v = visibles(page, "chart-rt-label")
        ok(v is not None and len(v) > 0, f"la grafica general se pinto ({len(v or [])} trazas visibles)")
        ok(all(n.endswith(" (max)") for n in v),
           f"abre en 'Máximo': solo trazas de maximos ({v[:3]}…)")
        activo = page.locator("#chart-rt-label").locator(
            "xpath=../..").locator(".capa-btn.active").first.inner_text()
        ok(activo.strip() == "Máximo", f"el boton marcado es '{activo.strip()}'")

        print("\n--- 2. Los botones alternan de verdad ---")
        grupo = page.locator("[data-chart='chart-rt-label']")
        grupo.locator("[data-capa='promedio']").click()
        page.wait_for_timeout(600)
        v = visibles(page, "chart-rt-label")
        ok(v and not any(n.endswith(" (max)") for n in v), f"'Promedio': {len(v)} trazas, ninguna de maximos")
        ok(grupo.locator(".capa-btn.active").first.inner_text().strip() == "Promedio",
           "el boton activo se movio a 'Promedio'")

        grupo.locator("[data-capa='ambas']").click()
        page.wait_for_timeout(600)
        v_ambas = visibles(page, "chart-rt-label")
        n_max = sum(1 for n in v_ambas if n.endswith(" (max)"))
        ok(n_max > 0 and n_max < len(v_ambas),
           f"'Ambas': {len(v_ambas)} trazas, {n_max} de maximos y {len(v_ambas)-n_max} de promedio")

        print("\n--- 3. El hover muestra solo lo visible (§3) ---")
        grupo.locator("[data-capa='promedio']").click()
        page.wait_for_timeout(600)
        h_prom = hover(page, "chart-rt-label")
        print("   hover:", h_prom[:240])
        ok(bool(h_prom), "el hover unificado aparece y trae texto")
        ok("(max)" not in h_prom, "el hover NO menciona ninguna serie de maximos")

        grupo.locator("[data-capa='maximo']").click()
        page.wait_for_timeout(600)
        h_max = hover(page, "chart-rt-label")
        print("   hover:", h_max[:240])
        ok("(max)" in h_max, "con 'Máximo', el hover trae las series de maximos")
        # Ninguna serie de promedio: el hover unificado nombra una traza por fila,
        # y con esta capa todas las que nombra tienen que acabar en '(max)'.
        sueltas = [t.strip() for t in h_max.split("|")
                   if t.strip() and "ms" in t and "(max)" not in t]
        ok(not sueltas, f"y ninguna fila de promedio: {sueltas[:4]}")

        print("\n--- 4. Los bloques por transaccion, igual ---")
        tx = page.locator("[data-chart='chart-tx0-response-times']")
        ok(tx.count() == 1, "el primer bloque por transaccion tiene su selector")
        ok(len(visibles(page, "chart-tx0-response-times")) == 2,
           "abre con sus dos capas (la general estaba en 'Máximo', el bloque no)")
        tx.locator("[data-capa='maximo']").click()
        page.wait_for_timeout(600)
        v = visibles(page, "chart-tx0-response-times")
        ok(v == ["Promedio (max)"], f"el bloque pasa a 'Máximo': {v}")
        ok(len(visibles(page, "chart-rt-label")) == len(v_ambas) // 2,
           "la general no se movio al tocar el bloque (selector por grafica)")

        print("\n--- 5. Consola limpia ---")
        ok(len(errores_consola) == 0, f"cero errores de consola ({errores_consola[:3]})")

        page.screenshot(path="/tmp/e2e_salida/etapa6_4_html.png", full_page=False)
        nav.close()

    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("6.4 (HTML en navegador) — TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
