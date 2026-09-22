"""ETAPA H2b.3 — el registro de horas en la pantalla real (el calendario del mes).

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/h2b3_pantalla.py

Sustituye a `h24_pantalla.py`, que probaba la vista SEMANAL retirada en H2b.3:
aquellos `data-testid` ('dia', 'salto-fecha', 'alta-*', 'editar-*') ya no
existen en el producto. Aquí se prueba lo que hay: el calendario del mes, el
detalle del día y el popup de registro.

H-D76: corre contra la base de pruebas. La pantalla es la de siempre —apunta al
8001— y el navegador desvía sus llamadas al backend de pruebas del 8002, así que
lo que se escribe no toca la base de Fredy.

Crea SUS PROPIOS datos, todos con la marca ZZTEST- (regla 29), y los borra al
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
PROYECTO = "ZZTEST-Proyecto H2b.3"
FESTIVO = "ZZTEST-Festivo de prueba H2b.3"

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def desviar_al_backend_de_pruebas(page):
    """El navegador pide al 8001; se reescribe al puerto de pruebas (H-D76)."""
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
    """Borra SOLO lo que esta prueba marcó con ZZTEST- (reglas 29 y 30).

    Y solo en una base de pruebas: si el nombre no lleva 'test', se para.
    """
    if "test" not in BASE:
        sys.exit(f"PARADA: '{BASE}' no es una base de pruebas. No se borra nada.")
    psql(
        f"delete from time_entries where project_id in (select id from projects where name='{PROYECTO}');"
        f"delete from project_activity_changes where project_id in (select id from projects where name='{PROYECTO}');"
        f"delete from project_activities where project_id in (select id from projects where name='{PROYECTO}');"
        f"delete from projects where name='{PROYECTO}';"
        f"delete from holidays where name='{FESTIVO}';"
    )


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    hoy = date.today()
    # La semana pasada: días ya cumplidos, del mes que la pantalla abre por
    # defecto. Si cayera en el mes anterior, se usa la primera semana de éste.
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    if lunes.month != hoy.month:
        lunes = date(hoy.year, hoy.month, 1)
        lunes -= timedelta(days=lunes.weekday())
        if lunes.month != hoy.month:
            lunes += timedelta(days=7)
    martes, miercoles, jueves, viernes = (lunes + timedelta(days=i) for i in (1, 2, 3, 4))
    print(f"semana de prueba: {lunes} … {viernes}")

    # Una actividad con MUY pocas horas estimadas, para forzar el desfase.
    cliente = cli.get(f"{API}/clients").json()[0]["id"]
    acts = cli.get(f"{API}/time/activities").json()[:2]
    a_corta, a_larga = acts[0], acts[1]
    r = cli.post(f"{API}/time/projects", json={
        "client_id": cliente, "name": PROYECTO,
        "activities": [{"activity_id": a_corta["id"], "estimated_hours": 4},
                       {"activity_id": a_larga["id"], "estimated_hours": 100}]})
    if r.status_code != 201:
        sys.exit(f"no se pudo crear el proyecto de prueba: {r.status_code} {r.text[:200]}")
    proy_id = r.json()["id"]
    psql(f"insert into holidays(id,date,name,user_id,kind) values "
         f"(gen_random_uuid(),'{viernes}','{FESTIVO}',null,'festivo');")

    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1500},
                              storage_state=SESION, locale="es-CO")
        page = ctx.new_page()
        desviar_al_backend_de_pruebas(page)
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        page.on("dialog", lambda d: d.accept())

        def abrir():
            page.goto(f"{WEB}/horas/registro", wait_until="networkidle")
            page.wait_for_selector("[data-testid='calendario']", timeout=25000)
            page.wait_for_timeout(800)

        def casilla(dia):
            return page.locator(f"[data-testid='casilla'][data-fecha='{dia}']")

        def elegir(dia):
            casilla(dia).click()
            page.wait_for_timeout(600)

        def registrar(dia, actividad, horas_txt, extra=False, facturable=True, guardar=True):
            """Abre el popup sobre ese día y lo rellena.

            «¿Se cobra?» nace sin elegir a propósito: hay que marcarlo, o el
            botón de guardar no se habilita.
            """
            elegir(dia)
            page.locator("[data-testid='anadir-registro']").click()
            page.wait_for_selector("[data-testid='popup-registro']", timeout=15000)
            page.locator("[data-testid='popup-cliente']").select_option(cliente)
            page.wait_for_timeout(900)
            page.locator("[data-testid='popup-proyecto']").select_option(label=PROYECTO)
            page.wait_for_timeout(900)
            page.locator("[data-testid='popup-actividad']").select_option(value=actividad)
            page.wait_for_timeout(600)
            page.locator("[data-testid='popup-horas']").fill(str(horas_txt))
            page.locator(
                f"[data-testid='popup-{'facturable' if facturable else 'no-facturable'}']"
            ).check()
            if extra:
                page.locator("[data-testid='popup-extra']").check()
            page.wait_for_timeout(500)
            if guardar:
                page.locator("[data-testid='popup-guardar']").click()
                page.wait_for_timeout(2200)

        abrir()

        # ---------- 1. La cabecera del mes ----------
        print("\n--- 1. El mes que se abre (H-D20) ---")
        visible = page.locator("[data-testid='mes-visible']").inner_text().strip().lower()
        print(f"    «{visible}»")
        ok(MESES[hoy.month - 1] in visible and str(hoy.year) in visible,
           "abre en el mes de hoy, con su nombre en español")
        ok(page.locator("[data-testid='casilla']").count() >= 28,
           f"el calendario pinta el mes entero ({page.locator('[data-testid=casilla]').count()} casillas)")
        ok(page.locator("[data-testid='leyenda']").count() == 1,
           "y lleva su leyenda de colores (§4.1: el color solo no basta)")

        page.locator("[data-testid='mes-anterior']").click()
        page.wait_for_timeout(1500)
        anterior = page.locator("[data-testid='mes-visible']").inner_text().strip().lower()
        ok(anterior != visible, f"«mes anterior» cambia de mes ({anterior})")
        page.locator("[data-testid='hoy']").click()
        page.wait_for_timeout(1500)
        ok(page.locator("[data-testid='mes-visible']").inner_text().strip().lower() == visible,
           "y «hoy» vuelve al mes de hoy")

        # ---------- 2. Registrar la jornada completa ----------
        print("\n--- 2. Registrar la jornada de un día ---")
        # «¿Se cobra?» no trae nada marcado: es una decisión, no un defecto.
        elegir(str(lunes))
        page.locator("[data-testid='anadir-registro']").click()
        page.wait_for_selector("[data-testid='popup-registro']", timeout=15000)
        ok(page.locator("[data-testid='popup-facturable']").is_checked() is False
           and page.locator("[data-testid='popup-no-facturable']").is_checked() is False,
           "«¿Se cobra?» abre sin nada marcado")
        ok(page.locator("[data-testid='popup-guardar']").is_disabled(),
           "y sin elegirlo no se puede guardar")
        page.locator("[data-testid='popup-cancelar']").click()
        page.wait_for_timeout(500)

        registrar(str(lunes), a_larga["id"], "8.5")
        ok(page.locator("[data-testid='total-dia']").inner_text().strip() == "8,5",
           f"el lunes suma 8,5 ({page.locator('[data-testid=total-dia]').inner_text().strip()})")
        ok(casilla(str(lunes)).get_attribute("data-estado") == "completo",
           "y su casilla queda «completo»")
        ok(page.locator("[data-testid='registros-dia'] [data-testid='registro']").count() == 1,
           "con una línea en el detalle del día")

        # ---------- 3. Media jornada: incompleto ----------
        print("\n--- 3. Media jornada deja el día incompleto (H-D15) ---")
        registrar(str(miercoles), a_larga["id"], "4")
        c = casilla(str(miercoles))
        ok(c.get_attribute("data-estado") == "incompleto", "la casilla queda «incompleto»")
        falta = c.locator("[data-testid='casilla-faltan']")
        ok(falta.count() == 1 and "4,5" in falta.inner_text(),
           f"y dice cuántas faltan ({falta.inner_text().strip() if falta.count() else '—'})")
        ok(page.locator("[data-testid='marca-incompleto']").count() == 1,
           "el detalle del día lo repite arriba")

        # ---------- 4. Pasarse de lo estimado ----------
        print("\n--- 4. Superar lo estimado: avisa, pero deja guardar (H-D16) ---")
        registrar(str(jueves), a_corta["id"], "6", guardar=False)
        rest = page.locator("[data-testid='popup-restantes']")
        ok(rest.count() == 1, "el popup dice lo que queda de la actividad")
        if rest.count():
            print(f"    «{rest.inner_text().strip()}»")
        aviso = page.locator("[data-testid='aviso-desfase']")
        ok(aviso.count() == 1, "aparece el aviso de desfase")
        if aviso.count():
            print(f"    «{aviso.inner_text().strip()[:140]}»")
        ok(not page.locator("[data-testid='popup-guardar']").is_disabled(),
           "y SE PUEDE guardar igual: avisa, no bloquea")
        page.locator("[data-testid='popup-guardar']").click()
        page.wait_for_timeout(2400)

        fila = page.locator("[data-testid='registros-dia'] [data-testid='registro']").first
        ok(fila.get_attribute("data-desfase") == "si", "el registro queda marcado en el detalle")
        ok(page.locator("[data-testid='marca-desfase']").count() >= 1, "con su etiqueta «desfase»")
        cj = casilla(str(jueves))
        ok(cj.get_attribute("data-desfase") == "si", "y la casilla del día también lo dice")
        ok(cj.locator("[data-testid='casilla-desfase']").count() == 1,
           "con la palabra «desfase» escrita, no solo el color")

        det = cli.get(f"{API}/time/projects/{proy_id}").json()
        act = [a for a in det["activities"] if a["activity_id"] == a_corta["id"]][0]
        ok(act["over_estimate"] is True,
           f"y el proyecto lo marca igual ({act['consumed_hours']} de {act['estimated_hours']})")

        # ---------- 5. Horas extra ----------
        print("\n--- 5. Las horas extra van aparte (H-D17) ---")
        registrar(str(martes), a_larga["id"], "8.5")
        registrar(str(martes), a_larga["id"], "3", extra=True)
        ok(page.locator("[data-testid='total-extra']").count() == 1,
           "el detalle del día separa las extra de las ordinarias")
        cm = casilla(str(martes))
        ok(cm.locator("[data-testid='casilla-extra']").count() == 1,
           "la casilla lleva su rayo con las extra")
        ok(cm.get_attribute("data-estado") == "completo",
           "y el día sigue completo: las extra no lo descuadran")
        tarjeta_extra = page.locator("[data-testid='total-Horas extra']").inner_text().strip()
        ok(tarjeta_extra == "3", f"el resumen del mes suma 3 h extra ({tarjeta_extra})")

        # ---------- 6. El festivo ----------
        print("\n--- 6. El festivo no se reclama (§4.2.7) ---")
        cv = casilla(str(viernes))
        ok(cv.get_attribute("data-estado") == "festivo", "el viernes sale como festivo")
        motivo = cv.locator("[data-testid='casilla-motivo']")
        ok(motivo.count() == 1 and FESTIVO in motivo.inner_text(),
           f"con su nombre escrito ({motivo.inner_text().strip() if motivo.count() else '—'})")
        ok(cv.locator("[data-testid='casilla-faltan']").count() == 0,
           "y no reclama horas")

        # ---------- 7. El resumen del mes ----------
        print("\n--- 7. El resumen del mes cuadra ---")
        registradas = page.locator("[data-testid='total-Registradas']").inner_text().strip()
        mes = cli.get(f"{API}/time/month",
                      params={"anio": lunes.year, "mes": lunes.month}).json()
        ok(registradas.replace(".", "").replace(",", ".") == f"{float(mes['total_ordinary']):g}",
           f"«Registradas» en pantalla ({registradas}) = /time/month ({mes['total_ordinary']})")
        pend = page.locator("[data-testid='total-Días pendientes']").inner_text().strip()
        ok(pend == str(mes["pending_days"]),
           f"«Días pendientes» ({pend}) = /time/month ({mes['pending_days']})")

        # ---------- 8. Editar y borrar ----------
        print("\n--- 8. Editar y borrar (H-D19) ---")
        elegir(str(lunes))
        page.locator("[data-testid='editar-registro']").first.click()
        page.wait_for_selector("[data-testid='popup-registro']", timeout=15000)
        traido = page.locator("[data-testid='popup-horas']").input_value()
        ok(float(traido) == 8.5, f"el popup abre con las horas que había ({traido})")
        page.locator("[data-testid='popup-horas']").fill("6")
        page.locator("[data-testid='popup-guardar']").click()
        page.wait_for_timeout(2400)
        t = page.locator("[data-testid='total-dia']").inner_text().strip()
        ok(t == "6", f"el lunes pasa a 6 h ({t})")
        ok(casilla(str(lunes)).get_attribute("data-estado") == "incompleto",
           "y con eso el día queda incompleto")

        antes = page.locator("[data-testid='registros-dia'] [data-testid='registro']").count()
        page.locator("[data-testid='borrar-registro']").first.click()
        page.wait_for_timeout(2400)
        despues = page.locator("[data-testid='registros-dia'] [data-testid='registro']").count()
        ok(despues == antes - 1, f"el admin borra un registro ({antes} -> {despues})")
        ok(page.locator("[data-testid='dia-sin-registros']").count() == 1,
           "y el día se queda sin registros, dicho con palabras")

        # ---------- 9. Consola ----------
        print("\n--- 9. Consola ---")
        ok(not errores, f"cero errores de JavaScript ({errores[:2]})")

        os.makedirs("/tmp/e2e_salida", exist_ok=True)
        page.screenshot(path="/tmp/e2e_salida/h2b3_registro.png", full_page=True)
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
        print("H2b.3 — EL CALENDARIO DE REGISTRO, DE PUNTA A PUNTA: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        limpiar()
        raise
