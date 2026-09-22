"""ETAPA H7.1 — la portada, el destinatario y la capacidad base.

Contra la BASE DE PRUEBAS (H-D76). 0 llamadas a la IA.
"""
import json, os, sys
import httpx
sys.path.insert(0, "/app")

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
fallos = []

def ok(c, t):
    print(f"{'PASA ' if c else 'FALLA'} | {t}")
    if not c:
        fallos.append(t)
    return c

ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=180)
par = {"desde": "2026-09-01", "hasta": "2026-09-30"}

print("=== 1. La capacidad base (H-D75) ===")
d = cli.get(f"{API}/time/informe", params=par).json()
cap = d["capacidad"]
print(f"    {cap}")
ok(cap["working_days"] == 22, f"septiembre de 2026 tiene 22 dias habiles ({cap['working_days']})")
# 18 dias de lunes a jueves a 8,5 + 4 viernes a 8,0 = 185
ok(float(cap["hours_per_analyst"]) == 185.0,
   f"y {cap['hours_per_analyst']} h por analista (18x8,5 + 4x8,0)")
ok(float(cap["total_hours"]) == float(cap["hours_per_analyst"]) * cap["people_count"],
   "el total del equipo es las horas por analista por las personas")

print("\n--- cuadra con el calendario ---")
mes = cli.get(f"{API}/time/month", params={"anio": 2026, "mes": 9}).json()
habiles_mes = [x for x in mes["days"] if float(x["expected_hours"]) > 0]
ok(len(habiles_mes) == cap["working_days"],
   f"el calendario dice {len(habiles_mes)} dias habiles y la portada {cap['working_days']}")

print("\n=== 2. El destinatario (H-D74) ===")
ok("Rodríguez Santos" in d["filtros"]["dirigido_a"],
   f"por defecto: «{d['filtros']['dirigido_a']}»")
d2 = cli.get(f"{API}/time/informe", params={**par, "dirigido_a": "Ana Ruiz · Gerente"}).json()
ok(d2["filtros"]["dirigido_a"] == "Ana Ruiz · Gerente",
   f"se puede cambiar: «{d2['filtros']['dirigido_a']}»")
d3 = cli.get(f"{API}/time/informe", params={**par, "dirigido_a": "   "}).json()
ok("Rodríguez Santos" in d3["filtros"]["dirigido_a"],
   "y si se deja vacio, vuelve el de por defecto")

print("\n=== 3. La portada en el documento (H-D73) ===")
html = cli.get(f"{API}/time/informe/html", params=par).text
for trozo, que in (
        ('class="cabecera"', "la cabecera tiene su bloque"),
        ('<img class="logo"', "el logo va embebido"),
        ("Centro de Excelencia", "«Centro de Excelencia»"),
        ("<strong>Performance</strong>", "y «Performance» destacado"),
        ('class="banda"', "la banda azul"),
        ('class="banda-naranja"', "con su tramo naranja"),
        ("Dirigido a", "el rotulo «Dirigido a»"),
        ("Período", "el rotulo «Período»"),
        ("Equipo", "el rotulo «Equipo»"),
        ("Capacidad base", "y «Capacidad base»"),
        ("días hábiles", "con los dias habiles"),
        ("por analista", "y las horas por analista")):
    ok(trozo in html, que)
ok("Rodríguez Santos" in html, "el destinatario sale en el documento")

html2 = cli.get(f"{API}/time/informe/html",
                params={**par, "dirigido_a": "Ana Ruiz · Gerente"}).text
ok("Ana Ruiz" in html2 and "Rodríguez Santos" not in html2,
   "y cambiarlo cambia el documento")

print("\n=== 4. Tambien en el PDF ===")
from weasyprint import HTML as WeasyHTML
from app.schemas.time_tracking import InformeDatos
from app.services.horas.informe import CLAVES, documento_pdf_html
datos = InformeDatos(**d)
himp = documento_pdf_html(datos, [c for c in CLAVES if c != "detalle"])
ok('class="cabecera"' in himp and "Capacidad base" in himp, "la portada esta en la rama de impresion")
doc = WeasyHTML(string=himp).render()
orient = ["HORIZONTAL" if p.width > p.height else "vertical" for p in doc.pages]
ok(all(x == "vertical" for x in orient), f"y sigue todo vertical ({set(orient)})")
r = cli.get(f"{API}/time/informe/pdf", params=par)
ok(r.status_code == 200 and b"/Image" in r.content,
   f"el PDF lleva el logo dentro ({r.headers.get('x-total-paginas')} paginas)")

print("\n=== 5. Reglas de impresion, intactas ===")
from app.services.horas import informe as gen
import re
ok("display:flex" not in gen._PDF_CSS and "display:grid" not in gen._PDF_CSS,
   "la rama de impresion sigue sin flex ni grid")
ok("rem" not in gen._PDF_CSS, "ni rem")
tam = [float(x) for x in re.findall(r"font-size:([\d.]+)pt", gen._BASE_CSS + gen._PDF_CSS)]
ok(min(tam) >= 8.0, f"ningun texto por debajo de 8 pt (el menor: {min(tam)})")

print("\n" + "=" * 70)
if fallos:
    print(f"{len(fallos)} FALLO(S):")
    for f in fallos:
        print("  -", f)
else:
    print("H7.1 — LA PORTADA: TODO PASA")
print("=" * 70)
sys.exit(1 if fallos else 0)
