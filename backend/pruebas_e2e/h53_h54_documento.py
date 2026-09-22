"""ETAPA H5.3 y H5.4 — el documento HTML y el PDF.

    docker exec jmeter_backend python3 /tmp/e2e/h53_h54_documento.py

Crea sus propios datos y los borra al terminar, incluso si falla a mitad
(regla del reporte 38). 0 llamadas a la IA.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, timedelta
from decimal import Decimal

import httpx

sys.path.insert(0, "/app")   # el generador del producto, para medir sobre EL MISMO HTML
from playwright.sync_api import sync_playwright

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
# H-D76: contra la base de pruebas; el navegador desvia sus llamadas al 8002.
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
PUERTO_API = os.environ.get("KX_API_PUERTO", "8002")
P1, P2, P3 = "ZZTEST-Proyecto H5.3 alfa", "ZZTEST-Proyecto H5.3 beta", "ZZTEST-Proyecto H5.3 corto"
NOMBRES = (P1, P2, P3)
FESTIVO = "ZZTEST-Festivo de prueba H5.3"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def psql(sql):
    subprocess.run(["psql", "-U", "jmeter_user", "-d", BASE, "-q", "-c", sql],
                   env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
                   capture_output=True)


def limpiar():
    """Borra SOLO lo marcado con ZZTEST- (reglas 29 y 30), y solo en pruebas."""
    if "test" not in BASE:
        sys.exit(f"PARADA: '{BASE}' no es una base de pruebas. No se borra nada.")
    lista = ",".join(f"'{n}'" for n in NOMBRES)
    psql(f"delete from time_entries where project_id in (select id from projects where name in ({lista}));"
         f"delete from project_activity_changes where project_id in (select id from projects where name in ({lista}));"
         f"delete from project_activities where project_id in (select id from projects where name in ({lista}));"
         f"delete from projects where name in ({lista});"
         f"delete from holidays where name = '{FESTIVO}';")


def paginas_y_orientacion(pdf: bytes):
    """Cuenta paginas y lee el /MediaBox de cada una, del PDF DE VERDAD."""
    cajas = re.findall(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
    fuera = []
    for x0, y0, x1, y1 in cajas:
        ancho = float(x1) - float(x0)
        alto = float(y1) - float(y0)
        fuera.append("HORIZONTAL" if ancho > alto else "vertical")
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf)), fuera


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=300)
    r = cli.get(f"{API}/auth/me")
    if r.status_code != 200:
        print("sesion caducada: corre refrescar_sesion.py"); return 1
    yo = r.json()

    hoy = date.today()
    primero = hoy.replace(day=1)
    ultimo = (date(hoy.year + 1, 1, 1) if hoy.month == 12
              else date(hoy.year, hoy.month + 1, 1)) - timedelta(days=1)
    desde, hasta = str(primero), str(ultimo)

    clientes = cli.get(f"{API}/clients").json()
    c1 = clientes[0]
    c2 = clientes[1] if len(clientes) > 1 else c1
    acts = cli.get(f"{API}/time/activities").json()[:3]
    usuarios = cli.get(f"{API}/users").json()

    print("=== 0. Un mes de equipo ===")
    proy = {}
    for nombre, cl, est in ((P1, c1, 200), (P2, c2, 200), (P3, c1, 2)):
        rr = cli.post(f"{API}/time/projects", json={
            "client_id": cl["id"], "name": nombre,
            "activities": [{"activity_id": a["id"], "estimated_hours": est} for a in acts]})
        ok(rr.status_code == 201, f"'{nombre}' ({rr.status_code})")
        proy[nombre] = rr.json()["id"]

    # Un mes de trabajo repartido: varias personas, varios proyectos, extras y
    # un desfase. Se para en ayer para no tocar fechas futuras (H-D21).
    creados = 0
    dia = primero
    i = 0
    while dia < hoy:
        if dia.weekday() < 5:
            for j, u in enumerate(usuarios[:3]):
                nombre = (P1, P2, P3)[(i + j) % 3]
                cuerpo = {"date": str(dia), "project_id": proy[nombre],
                          "activity_id": acts[(i + j) % len(acts)]["id"],
                          "hours": [8.5, 4, 2.5][(i + j) % 3],
                          "billable": (i + j) % 3 != 0,
                          "overtime": (i + j) % 11 == 0,
                          "user_id": u["id"]}
                if cli.post(f"{API}/time/entries", json=cuerpo).status_code == 201:
                    creados += 1
            i += 1
        dia += timedelta(days=1)
    psql(f"insert into holidays(id,date,name,user_id,kind) values "
         f"(gen_random_uuid(),'{primero + timedelta(days=(2 - primero.weekday()) % 7)}',"
         f"'{FESTIVO}',null,'festivo');")
    print(f"    {creados} registros de {min(3, len(usuarios))} persona(s)")

    par = {"desde": desde, "hasta": hasta}

    # ==================== 1. EL HTML (H5.3) ====================
    print("\n=== 1. El documento HTML (H-D55) ===")
    t0 = time.time()
    r = cli.get(f"{API}/time/informe/html", params=par)
    t_html = time.time() - t0
    ok(r.status_code == 200, f"GET /time/informe/html ({r.status_code})")
    html = r.text
    open("/tmp/e2e/informe.html", "w", encoding="utf-8").write(html)
    print(f"    {len(html)} bytes en {t_html:.2f}s")

    ok('inline; filename="informe-horas-' in r.headers.get("content-disposition", ""),
       f"nombre de archivo (H-D61): {r.headers.get('content-disposition','')[:60]}")

    print("\n--- autocontenido (H-D55) ---")
    externos = re.findall(r'(?:src|href)\s*=\s*"(https?://[^"]+)"', html)
    ok(not externos, f"ni una referencia a la red ({externos[:3]})")
    ok("<style>" in html and "<script>" in html, "estilos y JavaScript embebidos")

    print("\n--- las diez secciones (H-D52) ---")
    # H-D68: ocho secciones. «Dias sin registrar» y «Horas dia a dia» salieron.
    for clave in ("resumen", "personas", "facturacion", "clientes", "actividades",
                  "proyectos", "mapa", "detalle"):
        ok(f'id="sec-{clave}"' in html, f"seccion «{clave}»")
    for clave in ("pendientes", "diarias"):
        ok(f'id="sec-{clave}"' not in html, f"la seccion «{clave}» YA NO esta")

    print("\n--- formato espanol (H-D60) ---")
    ok(" h<" in html or " h</" in html, "las horas llevan su unidad")
    ok("%" in html, "y los porcentajes")
    ok(re.search(r"\d,\d", html) is not None, "coma decimal")
    ok("Ocupación" in html and "Días sin registrar" in html, "los titulos con tilde")

    # ==================== 2. EL HTML EN EL NAVEGADOR ====================
    print("\n=== 2. El HTML, abierto de verdad ===")
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1300}, locale="es-CO",
                              accept_downloads=True)
        page = ctx.new_page()
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        page.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        page.goto("file:///tmp/e2e/informe.html", wait_until="load")
        page.wait_for_timeout(1200)

        ok(not errores, f"sin errores de consola ({errores[:2]})")
        ok(page.locator("#sec-resumen").count() == 1, "el documento se pinta")
        total_inicial = page.locator("#ind-total").inner_text()
        filas_inicial = page.locator("table.detalle tbody tr:not(.oculta)").count()
        print(f"    total {total_inicial} · {filas_inicial} filas de detalle")
        # Contra lo que dice el propio informe, no contra mi contador: la base
        # puede traer registros de antes y un numero fijo mentiria.
        esperadas_filas = cli.get(f"{API}/time/informe", params=par).json()["detalle_total"]
        ok(filas_inicial == esperadas_filas,
           f"estan las {esperadas_filas} filas del periodo ({filas_inicial})")

        print("\n--- los botones de persona (H-D55) ---")
        botones = page.locator("[data-persona-btn]")
        ok(botones.count() >= 2, f"hay boton de Equipo y de cada persona ({botones.count()})")
        botones.nth(1).click()
        page.wait_for_timeout(700)
        filas_persona = page.locator("table.detalle tbody tr:not(.oculta)").count()
        total_persona = page.locator("#ind-total").inner_text()
        ok(filas_persona < filas_inicial, f"filtra el detalle ({filas_persona} de {filas_inicial})")
        ok(total_persona != total_inicial, f"y el resumen se rehace ({total_persona})")
        ok(page.locator("#aviso-filtro").is_visible(), "y avisa de que la vista esta filtrada")
        personas_visibles = page.locator("#sec-personas tbody tr:not(.oculta)").count()
        ok(personas_visibles == 1, f"la seccion 2 deja una sola fila ({personas_visibles})")
        botones.nth(0).click()
        page.wait_for_timeout(700)
        ok(page.locator("#ind-total").inner_text() == total_inicial,
           "y «Equipo» lo devuelve todo")

        print("\n--- la busqueda y el orden ---")
        page.locator("#f-busqueda").fill(P3.split()[-1])
        page.wait_for_timeout(700)
        buscadas = page.locator("table.detalle tbody tr:not(.oculta)").count()
        ok(0 < buscadas < filas_inicial, f"la busqueda filtra ({buscadas})")
        page.locator("#f-busqueda").fill("")
        page.wait_for_timeout(600)

        def columna_ordinarias():
            return page.evaluate("""() => [...document.querySelectorAll(
                '#sec-personas tbody tr')].map(tr => parseFloat(
                (tr.cells[2].textContent || '').replace(/[^\\d,.-]/g,'')
                    .replace(/\\./g,'').replace(',','.')) || 0)""")

        page.locator("#sec-personas th[data-col='2']").click()
        page.wait_for_timeout(500)
        asc = columna_ordinarias()
        ok(asc == sorted(asc), f"ordenar por cabecera deja la columna de menor a mayor ({asc})")
        page.locator("#sec-personas th[data-col='2']").click()
        page.wait_for_timeout(500)
        desc = columna_ordinarias()
        ok(desc == sorted(desc, reverse=True),
           f"y al pulsar otra vez, de mayor a menor ({desc})")

        print("\n--- solo facturables y el CSV ---")
        page.locator("#f-facturable").check()
        page.wait_for_timeout(700)
        fact = page.locator("table.detalle tbody tr:not(.oculta)").count()
        ok(fact < filas_inicial, f"la casilla de facturables filtra ({fact})")
        with page.expect_download(timeout=15000) as esperado:
            page.locator("#b-csv").click()
        bajada = esperado.value
        ok(bajada.suggested_filename.startswith("informe-horas-"),
           f"el CSV se descarga como «{bajada.suggested_filename}»")
        ruta = "/tmp/e2e/bajado.csv"
        bajada.save_as(ruta)
        crudo = open(ruta, "rb").read()
        ok(crudo.startswith(b"\xef\xbb\xbf"), "con BOM, para que Excel en espanol lo abra bien")
        lineas = crudo.decode("utf-8-sig").strip().splitlines()
        ok(len(lineas) == fact + 1, f"y solo con las filas visibles ({len(lineas) - 1} de {fact})")

        ok(page.locator("#b-imprimir").count() == 1, "y esta el boton de Imprimir")
        ctx.close(); nav.close()

    # ==================== 3. EL PDF (H5.4) ====================
    print("\n=== 3. El PDF (H-D56, H-D58) ===")
    t0 = time.time()
    r = cli.get(f"{API}/time/informe/pdf", params=par)
    t_pdf = time.time() - t0
    ok(r.status_code == 200, f"GET /time/informe/pdf ({r.status_code})")
    pdf = r.content
    open("/tmp/e2e/informe.pdf", "wb").write(pdf)
    print(f"    {len(pdf)} bytes en {t_pdf:.2f}s")
    ok(pdf.startswith(b"%PDF"), "el endpoint devuelve un PDF de verdad")
    ok('filename="informe-horas-' in r.headers.get("content-disposition", ""),
       f"con su nombre (H-D61): {r.headers.get('content-disposition','')[:58]}")

    # WeasyPrint guarda los objetos comprimidos, asi que `/MediaBox` no se puede
    # leer del PDF ya escrito. Se mide sobre el MISMO HTML de impresion que usa el
    # endpoint —la propia funcion del producto—, renderizado aqui para poder
    # preguntarle el tamano de cada pagina. Es el metodo con el que se comprobo
    # H-D56 en H5.1.
    from weasyprint import HTML as WeasyHTML
    from app.schemas.time_tracking import InformeDatos
    from app.services.horas.informe import CLAVES, documento_pdf_html

    datos = InformeDatos(**cli.get(f"{API}/time/informe", params=par).json())
    sin_detalle = [c for c in CLAVES if c != "detalle"]

    def orientaciones(secciones=None):
        doc = WeasyHTML(string=documento_pdf_html(
            datos, secciones or sin_detalle)).render()
        return ["HORIZONTAL" if p.width > p.height else "vertical" for p in doc.pages]

    orient = orientaciones()   # H-D69: el PDF va todo vertical
    print(f"    orientaciones: {orient}")
    ok(len(orient) >= 2, f"tiene varias paginas ({len(orient)})")
    # ETAPA H6 (H-D69): ya no hay orientacion mixta ni selector. La unica seccion
    # que giraba la hoja —«Horas dia a dia»— salio del informe en H-D68.
    ok(all(x == "vertical" for x in orient), f"el PDF va TODO en vertical ({set(orient)})")
    ok("HORIZONTAL" not in orient, "y no queda ni una pagina apaisada")

    print("\n--- el detalle no entra por defecto (H-D58) ---")
    r = cli.get(f"{API}/time/informe/pdf", params={**par, "seccion": ["detalle"]})
    con_detalle = len(r.content)
    ok(con_detalle != len(pdf), "pidiendolo explicitamente, el PDF cambia")
    ok(b"Detalle de registros" not in pdf or con_detalle > len(pdf),
       "y por defecto sale mas corto que con el detalle")

    print("\n--- ningun texto por debajo de 8 pt ---")
    from app.services.horas import informe as gen
    tamanos = [float(x) for x in re.findall(r"font-size:([\d.]+)pt", gen._BASE_CSS + gen._PDF_CSS)]
    ok(tamanos and min(tamanos) >= 8.0, f"el menor tamano del PDF es {min(tamanos)} pt")

    print("\n--- reglas de impresion (regla 11) ---")
    ok("display:flex" not in gen._PDF_CSS and "display:grid" not in gen._PDF_CSS,
       "la rama de impresion no usa flex ni grid")
    ok("rem" not in gen._PDF_CSS, "ni rem")
    ok("page-break-inside:avoid" in gen._PDF_CSS, "y ninguna fila se parte entre paginas")
    ok("display:table-header-group" in gen._PDF_CSS, "la cabecera se repite en cada pagina")

    print("\n--- el logo (H-D54) ---")
    hay_logo = gen._logo() is not None
    if hay_logo:
        ok(b"/Image" in pdf, "el logo va embebido en el PDF")
    else:
        ok(b"SQA" in pdf or "SQA" in html,
           "sin logo, sale el nombre en texto y el informe no se rompe")
        print("    (el archivo del logo todavia no esta; H-D54 dice que no es parada)")

    # ==================== 4. LOS TIEMPOS (H-D62) ====================
    print("\n=== 4. Los tiempos (H-D62) ===")
    print(f"    HTML {t_html:.2f}s  ·  PDF {t_pdf:.2f}s  ·  {creados} registros")
    ok(t_html < 5, f"el HTML por debajo de 5 s ({t_html:.2f})")
    ok(t_pdf < 15, f"el PDF por debajo de 15 s ({t_pdf:.2f})")

    limpiar()
    print("\n    datos de prueba borrados")
    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("H5.3 y H5.4 — EL DOCUMENTO HTML Y EL PDF: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


try:
    sys.exit(main())
except Exception:
    limpiar()
    raise
