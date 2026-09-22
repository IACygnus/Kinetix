"""HF-4 (D38): el bloque "Analisis por Transaccion Critica" no esta en ninguna
de las cuatro salidas, y la tabla de cada bloque por transaccion es la misma
del informe general (mismo titulo y mismas columnas).

CERO llamadas a la IA: solo se lee lo ya guardado y se vuelven a construir
informes con ello.

    python3 /tmp/e2e/hf4_check.py [execution_id]
"""
import asyncio
import json
import os
import re
import sys

import httpx

sys.path.insert(0, "/app")

API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
WEB = os.environ.get("KX_WEB", "http://localhost:5173")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
EID = sys.argv[1] if len(sys.argv) > 1 else "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8"

# Lo que NO puede aparecer en ninguna salida (D38).
PROHIBIDO = ("Transaccion Critica", "Transacción Crítica",
             "no se genero su analisis individual",
             "no se generó su análisis individual")

# El titulo y las columnas de la tabla del informe general. Cada bloque por
# transaccion tiene que usar EXACTAMENTE los mismos.
# ETAPA 6 (D52): los titulos visibles llevan tilde en las cuatro salidas.
TITULO_TABLA = "Reporte Resumen por Transacción"
COLUMNAS = ("Transacción", "Muestras", "Errores", "% Error", "Promedio", "Mediana",
            "P90", "P95", "P99", "Min", "Max", "TPS", "KB/s Recv", "KB/s Sent")

fallos = []


def comprobar(ok, texto):
    print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
    if not ok:
        fallos.append(texto)


def _sin_bloque(nombre, texto):
    for frase in PROHIBIDO:
        comprobar(frase not in texto, f"{nombre}: sin '{frase}'")


def _misma_tabla(nombre, html, bloques):
    """El titulo del general aparece una vez por el general y una por bloque, y
    todas esas tablas llevan las mismas columnas."""
    n = html.count(TITULO_TABLA)
    comprobar(n == 1 + bloques,
              f"{nombre}: el titulo '{TITULO_TABLA}' aparece {n} veces "
              f"(1 del general + {bloques} por transaccion)")
    faltan = [c for c in COLUMNAS if html.count(f">{c}<") < n]
    comprobar(not faltan,
              f"{nombre}: las {n} tablas llevan las mismas columnas"
              + (f" — faltan {faltan}" if faltan else ""))


# ====================== 1. PANTALLA ======================
def pantalla():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1600, "height": 1400},
                              storage_state=SESION if os.path.exists(SESION) else None)
        page = ctx.new_page()
        # Un solo login si la sesion guardada ya no vale (el limitador de
        # /auth/login cuenta tambien los correctos).
        page.goto(WEB, wait_until="networkidle")
        if page.locator('input[type="password"]').count():
            page.locator('input[type="text"]').first.fill(os.environ.get("KX_USER", "admin"))
            page.locator('input[type="password"]').first.fill(os.environ.get("KX_PWD", ""))
            page.locator('button[type="submit"]').first.click()
            page.wait_for_url("**/dashboard", timeout=30000)
            ctx.storage_state(path=SESION)
        page.goto(f"{WEB}/performance/report/{EID}", wait_until="networkidle")
        page.wait_for_selector("svg.recharts-surface", timeout=60000)
        page.wait_for_timeout(6000)     # las transacciones cargan en serie
        cuerpo = page.inner_text("body")
        n_tablas = page.locator("h2", has_text="Reporte Resumen").count()
        nav.close()
    _sin_bloque("Pantalla", cuerpo)
    comprobar(n_tablas >= 1,
              f"Pantalla: {n_tablas} tablas 'Reporte Resumen' (general + transacciones)")


# ====================== 2 a 4. LAS TRES SALIDAS EXPORTADAS ======================
async def exportados():
    from sqlalchemy import select

    import app.api.v1.endpoints.export_pdf as ep
    from app.db.models.user import User
    from app.db.session import AsyncSessionLocal

    capturado = {}
    _orig = ep.build_pdf_html

    def _espia(*a, **k):
        capturado["pdf"] = _orig(*a, **k)
        return capturado["pdf"]

    ep.build_pdf_html = _espia

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()
        await ep.export_pdf(EID, db=db, current_user=user)

    html_pdf = capturado["pdf"]
    bloques = len(re.findall(
        r"break-before:page;page-break-before:always;background:#0a1628", html_pdf))
    print(f"\nPDF individual: {len(html_pdf)} chars · {bloques} bloques por transaccion")
    _sin_bloque("PDF", html_pdf)
    _misma_tabla("PDF", html_pdf, bloques)
    return bloques


def html_y_integrado(bloques):
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    hdr = {"X-CSRF-Token": ck.get("csrf_token", "")}
    with httpx.Client(cookies=ck, headers=hdr, timeout=900.0) as cli:
        r = cli.get(f"{API}/executions/{EID}/export/html")
        r.raise_for_status()
        h = r.text
        print(f"\nHTML individual: {len(h)} chars")
        _sin_bloque("HTML", h)
        _misma_tabla("HTML", h, bloques)

        payload = {"sections": [{"type": "load_test", "order": 0,
                                 "source_id": EID, "source_name": "HF-4"}]}
        ri = cli.post(f"{API}/reports/integrated/export-html", json=payload)
        ri.raise_for_status()
        hi = ri.text
        print(f"\nIntegrado (HTML): {len(hi)} chars")
        _sin_bloque("Integrado", hi)
        _misma_tabla("Integrado", hi, bloques)


if __name__ == "__main__":
    pantalla()
    n = asyncio.run(exportados())
    html_y_integrado(n)
    print("\n" + "=" * 62)
    if fallos:
        print(f"{len(fallos)} FALLOS:")
        for f in fallos:
            print("  -", f)
        sys.exit(1)
    print("HF-4: EL BLOQUE NO ESTA EN NINGUNA DE LAS CUATRO SALIDAS")
    print("=" * 62)
