"""E3 ajuste 3 — D36 en el INFORME GENERAL, sobre la pantalla real.

  1. En E2-validacion, el backend marca varias columnas ai_* del general.
  2. Esas franjas ambar se pintan en las cajas del informe general (resumen,
     errores, conclusiones, recomendaciones y las cajas de grafica).
  3. Al quitar la jerga de una y guardarla, el aviso desaparece tras recargar.
  4. El texto original se restaura, pase lo que pase.

CERO llamadas a la IA.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
USUARIO = os.environ.get("KX_USER", "admin")
CLAVE = os.environ.get("KX_PWD", "")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
EJECUCION = sys.argv[1] if len(sys.argv) > 1 else "59e25069-5104-4b23-9b79-d305f5b38abd"

CAMPO = "ai_analysis_summary"          # el resumen: trae "tier" y el veredicto
ESPERA_GUARDADO_MS = 4000              # debounce 1,8 s + margen

fallos = []


def comprobar(ok, texto):
    print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
    if not ok:
        fallos.append(texto)


def _entrar(page):
    page.goto(BASE, wait_until="networkidle")
    if page.locator('input[type="password"]').count():
        page.locator('input[type="text"]').first.fill(USUARIO)
        page.locator('input[type="password"]').first.fill(CLAVE)
        page.locator('button[type="submit"]').first.click()
        page.wait_for_url("**/dashboard", timeout=30000)
        return
    r = page.request.get(f"{API}/auth/me")
    if r.status != 200:
        raise RuntimeError(f"/auth/me devolvio {r.status}; se aborta sin reintentar")


def _general(page):
    return page.request.get(f"{API}/executions/{EJECUCION}").json()


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1600, "height": 1400},
                              storage_state=SESION if os.path.exists(SESION) else None)
        page = ctx.new_page()
        _entrar(page)
        ctx.storage_state(path=SESION)

        # ---------- 0. Lo que dice el backend ----------
        ej = _general(page)
        avisos = ej.get("style_warnings") or {}
        print(f"backend: {len(avisos)} columnas del general marcadas -> {sorted(avisos)}")
        comprobar(bool(avisos), "el backend marca columnas del informe general")
        comprobar(CAMPO in avisos, f"{CAMPO} trae aviso ({avisos.get(CAMPO, [])[:3]})")
        original = ej.get(CAMPO) or ""

        page.goto(f"{BASE}/performance/report/{EJECUCION}", wait_until="networkidle")
        page.wait_for_selector("svg.recharts-surface", timeout=60000)
        page.wait_for_timeout(6000)     # los bloques por transaccion cargan en serie

        # ---------- 1. Las franjas del GENERAL se pintan ----------
        # Se cuentan solo las que estan por encima del bloque por transaccion:
        # la caja del resumen general es la primera del informe.
        caja_resumen = page.locator("h3", has_text="Analisis del Reporte Resumen").first
        comprobar(caja_resumen.count() == 1, "existe la caja del resumen del informe general")
        # Se busca DENTRO del contenedor del resumen, no con following::, que se
        # escaparia a la siguiente caja del informe cuando esta no tenga franja.
        contenedor = caja_resumen.locator("xpath=..")
        franja = contenedor.locator("div.bg-amber-50")
        texto_franja = " ".join(franja.inner_text().split()) if franja.count() else ""
        print(f"  franja del resumen general: {texto_franja[:140]!r}")
        comprobar(franja.count() >= 1, "el resumen del informe general pinta su franja ambar")
        comprobar("Revisar estilo" in texto_franja, "la franja dice 'Revisar estilo'")
        comprobar(any(t.split(":")[0].strip().lower() in texto_franja.lower()
                      for t in avisos.get(CAMPO, [])),
                  "la franja nombra alguno de los terminos que devolvio el backend")

        total_antes = page.locator("text=Revisar estilo:").count()
        print(f"  franjas ambar en toda la pagina: {total_antes}")
        comprobar(total_antes >= len(avisos),
                  f"hay al menos {len(avisos)} franjas (general + transacciones): {total_antes}")

        # Conclusiones y recomendaciones tambien son cajas del general
        for titulo, campo in (("Conclusiones", "ai_conclusions"),
                              ("Recomendaciones", "ai_recommendations")):
            if campo not in avisos:
                continue
            h = page.locator("h2", has_text=titulo).first
            if not h.count():
                h = page.locator("h3", has_text=titulo).first
            f2 = h.locator("xpath=ancestor::div[2]").locator("div.bg-amber-50")
            comprobar(f2.count() >= 1, f"la caja de {titulo} pinta su franja ambar")

        # ---------- 2. Se corrige el texto y el aviso desaparece ----------
        caja = caja_resumen.locator("xpath=following::textarea[1]")
        comprobar(caja.count() == 1, "se localiza el textarea del resumen general")
        limpio = (original.replace("tier excelente", "tiempos bajos")
                          .replace("tier", "grupo")
                          .replace("No debería liberarse", "Quedan por corregir los errores")
                          .replace("179.73ms", "180 ms").replace("33.59", "33,59")
                          .replace("3.9x mayor", "3,9 veces mayor")
                          .replace("41.26%", "41,26%").replace("56.77%", "56,77%")
                          .replace("71.42%", "71,42%").replace("108ms", "108 ms")
                          .replace("422ms", "422 ms"))
        try:
            caja.click()
            caja.fill(limpio)
            caja.blur()
            page.wait_for_timeout(ESPERA_GUARDADO_MS)

            tras = (_general(page).get("style_warnings") or {})
            print(f"  backend tras corregir: {CAMPO} -> {tras.get(CAMPO)}")
            comprobar(CAMPO not in tras,
                      "tras corregir el texto el backend ya no marca el resumen")

            page.reload(wait_until="networkidle")
            page.wait_for_selector("svg.recharts-surface", timeout=60000)
            page.wait_for_timeout(6000)
            f3 = page.locator("h3", has_text="Analisis del Reporte Resumen").first.locator(
                "xpath=..").locator("div.bg-amber-50")
            hay = f3.count() > 0
            total_despues = page.locator("text=Revisar estilo:").count()
            print(f"  franjas ambar tras recargar: {total_despues} (antes {total_antes})")
            comprobar(not hay, "la franja del resumen general desaparecio al recargar")
            comprobar(total_despues < total_antes, "queda al menos una franja menos")
        finally:
            # ---------- 3. Restaurar ----------
            csrf = next((c["value"] for c in ctx.cookies() if c["name"] == "csrf_token"), "")
            r = page.request.put(f"{API}/executions/{EJECUCION}/analysis",
                                 data={CAMPO: original},
                                 headers={"X-CSRF-Token": csrf,
                                          "Content-Type": "application/json"})
            print(f"  restauracion: HTTP {r.status}")
            vuelto = _general(page)
            comprobar((vuelto.get(CAMPO) or "") == original,
                      "el texto original quedo restaurado")
            comprobar(CAMPO in (vuelto.get("style_warnings") or {}),
                      "y su aviso vuelve a aparecer, como debe")

        nav.close()

    print("\n" + "=" * 60)
    if fallos:
        print(f"{len(fallos)} FALLOS:")
        for f in fallos:
            print("  -", f)
        sys.exit(1)
    print("TODO EN VERDE")


main()
