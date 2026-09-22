"""Abre el HTML exportado en Chromium y comprueba que Plotly pinta de verdad."""
import json, os, sys, time
import httpx
from playwright.sync_api import sync_playwright
API = "http://localhost:8001/api/v1"
EID = os.environ.get("KX_EID", "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8")
ck = {c["name"]: c["value"] for c in json.load(open("/tmp/e2e_sesion.json"))["cookies"]}
with httpx.Client(cookies=ck, timeout=600.0) as cli:
    r = cli.get(f"{API}/executions/{EID}/export/html")
open("/tmp/export.html", "wb").write(r.content)
errores = []
with sync_playwright() as p:
    nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = nav.new_page(viewport={"width": 1600, "height": 1200})
    page.on("console", lambda m: errores.append(m.text[:160]) if m.type == "error" else None)
    page.on("pageerror", lambda e: errores.append("pageerror: " + str(e)[:160]))
    page.goto("file:///tmp/export.html", wait_until="networkidle")
    page.wait_for_timeout(6000)
    pintadas = page.evaluate("document.querySelectorAll('.js-plotly-plot').length")
    divs = page.evaluate("document.querySelectorAll('.plotly-chart').length")
    print("divs de grafica:", divs, "· pintadas por Plotly:", pintadas)
    page.screenshot(path="/tmp/export_html.png", full_page=True)
    nav.close()
print("errores de consola:", errores[:5] or "ninguno")
print("PASA " if pintadas >= divs - 1 and not errores else "FALLA", "| el HTML exportado pinta sus graficas")
