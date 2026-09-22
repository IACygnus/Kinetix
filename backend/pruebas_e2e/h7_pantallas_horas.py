"""ETAPA H7.4 — las tres pantallas que quedaban sin suite: consulta, importar e informes.

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/h7_pantallas_horas.py

Al cerrar el módulo, Registro (h2b3_pantalla.py), Actividades y Proyectos
(h15_pantallas.py) tenían prueba de navegador; estas tres no. No pretende
repetir lo que ya comprueban las suites de backend: mira que la pantalla carga,
que sus controles están, que una acción de verdad llega hasta los datos y que la
consola queda limpia.

H-D76: contra la base de pruebas. La pantalla es la de siempre —apunta al
8001— y el navegador desvía sus llamadas al 8002.

Crea SUS PROPIOS datos, marcados con ZZTEST- (regla 29), y los borra al
terminar aunque falle a mitad. 0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import httpx
from playwright.sync_api import sync_playwright

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
PUERTO_API = os.environ.get("KX_API_PUERTO", "8002")
PROYECTO = "ZZTEST-Proyecto H7.4"
LIBRO = "/tmp/e2e/zztest_h74.xlsx"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def desviar_al_backend_de_pruebas(page):
    if PUERTO_API == "8001":
        return
    page.route(
        "http://localhost:8001/**",
        lambda ruta: ruta.continue_(
            url=ruta.request.url.replace("localhost:8001", f"localhost:{PUERTO_API}")))


def psql(sql):
    subprocess.run(["psql", "-U", "jmeter_user", "-d", BASE, "-q", "-c", sql],
                   env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
                   capture_output=True)


def limpiar():
    """Borra SOLO lo marcado con ZZTEST- (reglas 29 y 30), y solo en pruebas."""
    if "test" not in BASE:
        sys.exit(f"PARADA: '{BASE}' no es una base de pruebas. No se borra nada.")
    psql(
        "delete from time_entries where project_id in "
        f"  (select id from projects where name like 'ZZTEST-%H7.4%');"
        "delete from project_activity_changes where project_id in "
        f"  (select id from projects where name like 'ZZTEST-%H7.4%');"
        "delete from project_activities where project_id in "
        f"  (select id from projects where name like 'ZZTEST-%H7.4%');"
        f"delete from projects where name like 'ZZTEST-%H7.4%';"
    )


def escribir_libro(ruta, cliente, proyecto, actividad, dias):
    """Un Excel mínimo con las seis columnas obligatorias (§6.2)."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Proyecto", "Tarea", "Fecha", "Tiempo total", "Facturable"])
    for d, h in dias:
        ws.append([cliente, proyecto, actividad, d, h, "Sí"])
    wb.save(ruta)


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    cliente = cli.get(f"{API}/clients").json()[0]
    acts = cli.get(f"{API}/time/activities").json()[:2]
    r = cli.post(f"{API}/time/projects", json={
        "client_id": cliente["id"], "name": PROYECTO,
        "activities": [{"activity_id": acts[0]["id"], "estimated_hours": 20},
                       {"activity_id": acts[1]["id"], "estimated_hours": 20}]})
    if r.status_code != 201:
        sys.exit(f"no se pudo crear el proyecto de prueba: {r.status_code} {r.text[:200]}")
    proy = r.json()
    for i, h in enumerate(("8.5", "8.5", "4")):
        cli.post(f"{API}/time/entries", json={
            "project_id": proy["id"], "activity_id": acts[0]["id"],
            "date": str(lunes + timedelta(days=i)), "hours": h,
            "billable": True, "overtime": False})

    # El libro para la importación: otro proyecto, que la pantalla creará.
    escribir_libro(LIBRO, cliente["name"], "ZZTEST-Proyecto importado H7.4",
                   acts[1]["name"],
                   [(str(lunes + timedelta(days=i)), 2) for i in range(3)])

    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1500},
                              storage_state=SESION, locale="es-CO")
        page = ctx.new_page()
        desviar_al_backend_de_pruebas(page)
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        page.on("dialog", lambda d: d.accept())

        # ================= 1. La consulta (§5) =================
        print("--- 1. La consulta de proyectos ---")
        page.goto(f"{WEB}/horas/consulta", wait_until="networkidle")
        page.wait_for_selector("[data-testid='filtro-desde']", timeout=25000)
        for t in ("filtro-desde", "filtro-hasta", "filtro-cliente",
                  "filtro-proyecto", "filtro-persona", "incluir-cerrados"):
            ok(page.locator(f"[data-testid='{t}']").count() == 1, f"está el filtro «{t}»")

        page.locator("[data-testid='filtro-desde']").fill(str(lunes))
        page.locator("[data-testid='filtro-hasta']").fill(str(lunes + timedelta(days=6)))
        page.wait_for_timeout(2500)
        filas = page.locator("[data-testid='fila-proyecto']")
        ok(filas.count() >= 1, f"el rango trae proyectos ({filas.count()})")
        nuestra = page.locator(f"[data-testid='fila-proyecto']:has-text('{PROYECTO}')")
        ok(nuestra.count() == 1, "entre ellos el de la prueba")
        total = page.locator("[data-testid='horas-rango']").first.inner_text().strip()
        print(f"    horas del rango: {total}")

        # La misma cifra que da el backend para ese rango.
        api = cli.get(f"{API}/time/consulta", params={
            "desde": str(lunes), "hasta": str(lunes + timedelta(days=6))}).json()
        mio = [p_ for p_ in api["projects"] if p_["project_name"] == PROYECTO][0]
        ok(float(mio["hours_in_range"]) == 21.0,
           f"y el backend cuenta las 21 h de la prueba ({mio['hours_in_range']})")

        nuestra.locator("[data-testid='ampliar-proyecto']").click()
        page.wait_for_timeout(1500)
        ok(page.locator("[data-testid='fila-persona']").count() >= 1,
           "al ampliar, se ve el desglose por persona")

        # ================= 2. La importación (§6) =================
        print("\n--- 2. La importación del Excel ---")
        page.goto(f"{WEB}/horas/importar", wait_until="networkidle")
        page.wait_for_selector("[data-testid='archivo']", timeout=25000)
        ok(page.locator("[data-testid='analizar']").is_disabled(),
           "sin archivo, «analizar» está apagado")
        page.locator("[data-testid='archivo']").set_input_files(LIBRO)
        page.wait_for_timeout(800)
        ok(not page.locator("[data-testid='analizar']").is_disabled(),
           "con archivo, se enciende")
        page.locator("[data-testid='analizar']").click()
        page.wait_for_selector("[data-testid='vista-previa']", timeout=30000)
        previas = page.locator("[data-testid='fila-previa']")
        ok(previas.count() == 3, f"la vista previa trae las tres filas ({previas.count()})")
        ok(page.locator("[data-testid='confirmar-importacion']").count() == 1,
           "y hay que confirmar: no importa sola")
        page.locator("[data-testid='confirmar-importacion']").click()
        page.wait_for_selector("[data-testid='resumen-importacion']", timeout=30000)
        resumen = page.locator("[data-testid='resumen-importacion']").inner_text()
        print(f"    {resumen.replace(chr(10), ' · ')[:160]}")
        ok("3" in resumen, "el resumen dice cuántas entraron")
        ok(page.locator("[data-testid='enlace-proyecto-creado']").count() >= 1,
           "y enlaza el proyecto que creó")
        creado = cli.get(f"{API}/time/projects",
                         params={"texto": "ZZTEST-Proyecto importado H7.4"}).json()
        ok(len(creado) == 1, "el proyecto nuevo existe de verdad en la base")

        # ================= 3. El informe (§7) =================
        print("\n--- 3. El informe ---")
        page.goto(f"{WEB}/horas/informes", wait_until="networkidle")
        page.wait_for_selector("[data-testid='inf-desde']", timeout=25000)
        # La previa se genera sola al entrar (H-D57).
        page.wait_for_selector("[data-testid='previa-marco']", timeout=60000)
        for t in ("inf-desde", "inf-hasta", "inf-cliente", "inf-proyecto",
                  "inf-personas", "inf-facturables", "inf-secciones",
                  "inf-dirigido-a", "previa-marco"):
            ok(page.locator(f"[data-testid='{t}']").count() == 1, f"está «{t}»")

        secciones = page.locator("[data-testid='inf-seccion']")
        ok(secciones.count() >= 6, f"se pueden elegir las secciones ({secciones.count()})")
        pestanas = page.locator("[data-testid='inf-pestana']")
        claves = [pestanas.nth(i).get_attribute("data-pestana") for i in range(pestanas.count())]
        ok(claves == ["previa", "proyectos", "mensual", "ocupacion"],
           f"las cuatro pestañas, en su orden ({claves})")

        # H-D74: el destinatario se puede cambiar y viaja al documento.
        page.locator("[data-testid='inf-desde']").fill(str(lunes))
        page.locator("[data-testid='inf-hasta']").fill(str(lunes + timedelta(days=6)))
        page.locator("[data-testid='inf-dirigido-a']").fill("ZZTEST Destinataria de prueba")
        page.locator("[data-testid='rehacer-previa']").click()
        page.wait_for_timeout(8000)
        cuerpo = page.frame_locator("[data-testid='previa-marco']").locator("body").inner_text()
        # Los rótulos de la portada van en versalitas por CSS, así que lo que
        # se lee en pantalla está en mayúsculas: se compara sin distinguirlas.
        bajo = cuerpo.lower()
        ok("zztest destinataria de prueba" in bajo,
           "el destinatario escrito sale en la portada de la previa")
        ok("capacidad base" in bajo and "días hábiles" in bajo and "por analista" in bajo,
           "y la portada trae la capacidad base (H-D75)")
        ok("centro de excelencia" in bajo, "con la cabecera del COE (H-D73)")
        ok(PROYECTO.lower() in bajo, "el informe incluye el proyecto de la prueba")

        # Las otras tres pestañas pintan sus tablas.
        for clave, tabla in (("proyectos", "tabla-inf-proyectos"),
                             ("mensual", "tabla-inf-mapa"),
                             ("ocupacion", "tabla-inf-facturacion")):
            page.locator(f"[data-testid='inf-pestana'][data-pestana='{clave}']").click()
            page.wait_for_timeout(2000)
            ok(page.locator(f"[data-testid='{tabla}']").count() == 1,
               f"la pestaña «{clave}» pinta su tabla")

        # ================= 4. Consola =================
        print("\n--- 4. Consola ---")
        ok(not errores, f"cero errores de JavaScript ({errores[:2]})")

        os.makedirs("/tmp/e2e_salida", exist_ok=True)
        page.screenshot(path="/tmp/e2e_salida/h74_informes.png", full_page=True)
        ctx.close()
        nav.close()

    limpiar()
    print("\n    datos de prueba borrados")
    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("H7.4 — CONSULTA, IMPORTACIÓN E INFORME EN PANTALLA: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        limpiar()
        raise
