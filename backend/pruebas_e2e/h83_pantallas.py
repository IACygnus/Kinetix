"""ETAPA H8.3 — el estado en las pantallas y en el informe.

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/h83_pantallas.py

Lo que más importa aquí (y lo pidió Fredy por su nombre): **que los campos de
estimación se deshabiliten según `can_edit_estimates` y no según una regla
escrita en TypeScript.** Si esa regla se duplicara, el día que cambiara una de
las dos copias tendríamos una pantalla que permite lo que el backend rechaza.
La prueba lo comprueba de la única forma que lo demuestra: **mintiéndole a la
pantalla**. Se intercepta la respuesta del backend y se le cambia
`can_edit_estimates` sin tocar el estado; si la pantalla obedece al campo, los
controles cambian; si dedujera de `status`, no se enteraría.

H-D76: contra la base de pruebas. La pantalla apunta al 8001 y el navegador
desvía sus llamadas al 8002. Datos `ZZTEST-` (regla 29), limpieza solo por ese
prefijo (regla 30). 0 llamadas a la IA.
"""
import json
import os
import re
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

MARCA = "ZZTEST-H83"
VIVO = f"{MARCA}-en-ejecucion"
PARADO = f"{MARCA}-detenido"
MUERTO = f"{MARCA}-finalizado"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def desviar(page):
    if PUERTO_API == "8001":
        return
    page.route("http://localhost:8001/**", lambda r: r.continue_(
        url=r.request.url.replace("localhost:8001", f"localhost:{PUERTO_API}")))


def psql(sql):
    return subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", BASE, "-q", "-t", "-A", "-c", sql],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True, text=True)


def limpiar():
    if "test" not in BASE:
        sys.exit(f"PARADA: «{BASE}» no es una base de pruebas. No se borra nada.")
    p = f"name like '{MARCA}%'"
    psql(
        f"delete from time_entries where project_id in (select id from projects where {p});"
        f"delete from project_status_changes where project_id in (select id from projects where {p});"
        f"delete from project_activity_changes where project_id in (select id from projects where {p});"
        f"delete from project_activities where project_id in (select id from projects where {p});"
        f"delete from projects where {p};"
    )


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    cliente = cli.get(f"{API}/clients").json()[0]
    act = cli.get(f"{API}/time/activities").json()[0]

    proy = {}
    for nombre, estimadas in ((VIVO, 20), (PARADO, 20), (MUERTO, 4)):
        r = cli.post(f"{API}/time/projects", json={
            "client_id": cliente["id"], "name": nombre,
            "activities": [{"activity_id": act["id"], "estimated_hours": estimadas}]})
        if r.status_code != 201:
            sys.exit(f"no se pudo crear «{nombre}»: {r.status_code} {r.text[:200]}")
        proy[nombre] = r.json()

    # Horas en los tres, ANTES de cambiarles el estado: el proyecto finalizado
    # tiene que quedar desfasado, que es el caso que enseña las dos columnas.
    for nombre, horas_ in ((VIVO, "8.5"), (PARADO, "4"), (MUERTO, "8.5")):
        cli.post(f"{API}/time/entries", json={
            "project_id": proy[nombre]["id"], "activity_id": act["id"],
            "date": str(lunes), "hours": horas_, "billable": True, "overtime": False,
            "notes": f"{MARCA} prueba"})
    cli.post(f"{API}/time/projects/{proy[PARADO]['id']}/estado", json={"status": "detenido"})
    cli.post(f"{API}/time/projects/{proy[MUERTO]['id']}/estado", json={"status": "finalizado"})

    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1600},
                              storage_state=SESION, locale="es-CO")
        page = ctx.new_page()
        desviar(page)
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        page.on("dialog", lambda d: d.accept())

        # ============ 1. El listado de Proyectos ============
        print("--- 1. Proyectos: Estado y Consumo, dos columnas ---")
        page.goto(f"{WEB}/horas/proyectos", wait_until="networkidle")
        page.wait_for_selector("[data-testid='tabla-proyectos'] tr", timeout=25000)

        cabeceras = [t.strip().upper() for t in page.locator("thead th").all_inner_texts()]
        ok("ESTADO" in cabeceras and "CONSUMO" in cabeceras,
           f"la tabla tiene las DOS columnas: {cabeceras}")
        ok(cabeceras.index("ESTADO") < cabeceras.index("CONSUMO"),
           "«Estado» va antes que «Consumo»")

        fila_viva = page.locator(f"tr[data-proyecto='{VIVO}']")
        ok(fila_viva.count() == 1, "el proyecto en ejecución sale en el listado")
        ok(fila_viva.locator("[data-testid='selector-estado-fila']").count() == 1,
           "y el estado se cambia desde el listado, sin abrirlo (H-D83)")
        ok(fila_viva.locator("[data-proyecto-estado]").get_attribute(
               "data-proyecto-estado") == "en_ejecucion",
           "con su estado en su propia celda")

        # H-D84: por defecto, fuera los finalizados y los no viables.
        ok(page.locator(f"tr[data-proyecto='{MUERTO}']").count() == 0,
           "el finalizado NO sale por defecto (H-D84)")
        ok(page.locator(f"tr[data-proyecto='{PARADO}']").count() == 1,
           "el detenido SÍ sale: no está cerrado, solo parado")
        page.locator("[data-testid='incluir-finalizados']").check()
        page.wait_for_timeout(1800)
        fila_muerta = page.locator(f"tr[data-proyecto='{MUERTO}']")
        ok(fila_muerta.count() == 1, "con la casilla marcada, el finalizado vuelve")

        # H-D82: las dos celdas dicen cosas distintas en la MISMA fila.
        estado_txt = fila_muerta.locator("[data-testid='selector-estado-fila']").input_value()
        consumo_txt = fila_muerta.locator("[data-testid='chip-desfase']").inner_text().strip()
        ok(estado_txt == "finalizado", f"el estado de la fila dice «{estado_txt}»")
        ok(consumo_txt.startswith("Desfasado"),
           f"y su consumo, en otra celda, dice «{consumo_txt}»")
        ok(estado_txt != consumo_txt, "no son lo mismo, que es de lo que trata H-D82")

        # ============ 2. El detalle, y la regla que NO se duplica ============
        print("--- 2. El detalle: `can_edit_estimates` manda ---")
        # Se pulsa la celda del NOMBRE, no la fila entera: el selector de estado
        # para la propagación a propósito, para que elegir un estado desde el
        # listado no abra el proyecto.
        page.locator(f"tr[data-proyecto='{VIVO}'] td").nth(1).click()
        page.wait_for_selector("[data-testid='tabla-actividades-proyecto']", timeout=20000)
        ok(page.locator("[data-testid='selector-estado']").count() == 1,
           "el detalle tiene el selector de estado (H-D83)")
        ok(page.locator("[data-testid='estimacion']").first.is_enabled(),
           "en ejecución, la estimación se puede editar")

        # **La prueba de que la regla viene del backend.** Se intercepta la
        # respuesta y se le pone `can_edit_estimates: false` SIN tocar `status`.
        # Si la pantalla dedujera de `status`, seguiría dejando editar.
        def mentir(ruta):
            # Ojo: esta ruta se registra DESPUÉS de `desviar`, así que gana ella
            # y el desvío al 8002 no llega a aplicarse. Hay que hacerlo aquí.
            respuesta = ruta.fetch(url=ruta.request.url.replace(
                "localhost:8001", f"localhost:{PUERTO_API}"))
            cuerpo = respuesta.json()
            cuerpo["can_edit_estimates"] = False
            cuerpo["status_label"] = "En ejecución"      # el estado NO cambia
            ruta.fulfill(response=respuesta, json=cuerpo)

        # El detalle es estado interno de la página, no una URL: recargar
        # devolvería al listado. Se sale al listado y se vuelve a entrar, ya con
        # la respuesta interceptada.
        pid = proy[VIVO]["id"]
        page.get_by_text("Volver a proyectos").click()
        page.wait_for_selector("[data-testid='tabla-proyectos'] tr", timeout=20000)
        page.route(f"**/api/v1/time/projects/{pid}", mentir)
        page.locator(f"tr[data-proyecto='{VIVO}'] td").nth(1).click()
        page.wait_for_selector("[data-testid='tabla-actividades-proyecto']", timeout=20000)

        sigue_en_ejecucion = page.locator(
            "[data-testid='estado-proyecto']").get_attribute("data-estado")
        ok(sigue_en_ejecucion == "en_ejecucion",
           f"el estado que ve la pantalla sigue siendo «{sigue_en_ejecucion}»")
        ok(page.locator("[data-testid='estimacion']").first.is_disabled(),
           "y AUN ASÍ la estimación queda bloqueada: la pantalla obedece a "
           "`can_edit_estimates`, no a una regla suya")
        ok(page.locator("[data-testid='quitar-actividad']").first.is_disabled(),
           "lo mismo con el botón de quitar la actividad")
        page.unroute(f"**/api/v1/time/projects/{pid}")

        # ============ 3. El historial de estados (H-D83) ============
        print("--- 3. El historial, junto al de estimaciones ---")
        page.goto(f"{WEB}/horas/proyectos", wait_until="networkidle")
        page.locator("[data-testid='incluir-finalizados']").check()
        page.wait_for_timeout(1500)
        page.locator(f"tr[data-proyecto='{MUERTO}'] td").nth(1).click()
        page.wait_for_selector("[data-testid='ver-historial']", timeout=20000)
        page.locator("[data-testid='ver-historial']").click()
        page.wait_for_selector("[data-testid='tabla-historial-estado'] tr", timeout=15000)
        filas = page.locator("[data-testid='tabla-historial-estado'] tr")
        ok(filas.count() == 1, f"una línea de cambio de estado ({filas.count()})")
        texto = filas.first.inner_text()
        ok("En ejecución" in texto and "Finalizado" in texto,
           f"de dónde venía y a dónde fue: «{' '.join(texto.split())}»")
        ok(page.locator("[data-testid='tabla-historial'] tr").count() >= 1,
           "y el de estimaciones sigue estando, debajo")

        # ============ 4. La consulta ============
        print("--- 4. La consulta: Estado en su columna ---")
        page.goto(f"{WEB}/horas/consulta", wait_until="networkidle")
        page.wait_for_selector("[data-testid='filtro-desde']", timeout=25000)
        page.locator("[data-testid='filtro-desde']").fill(str(lunes))
        page.locator("[data-testid='filtro-hasta']").fill(str(lunes + timedelta(days=6)))
        page.wait_for_timeout(2500)
        cabeceras = [t.strip().upper() for t in page.locator("thead th").all_inner_texts()]
        ok("ESTADO" in cabeceras and "CONSUMO" in cabeceras,
           f"la consulta tiene las dos columnas: {cabeceras}")
        fila = page.locator(f"[data-testid='fila-proyecto']:has-text('{PARADO}')")
        ok(fila.count() == 1, "el proyecto detenido sale en la consulta")
        ok(fila.locator("[data-testid='chip-estado']").inner_text().strip() == "Detenido",
           "con su estado en la columna nueva")
        ok(page.locator(f"[data-testid='fila-proyecto']:has-text('{MUERTO}')").count() == 0,
           "y el finalizado no sale hasta que se pide (H-D84)")
        page.locator("[data-testid='incluir-finalizados']").check()
        page.wait_for_timeout(2000)
        ok(page.locator(f"[data-testid='fila-proyecto']:has-text('{MUERTO}')").count() == 1,
           "marcada la casilla, sí sale")

        ok(not errores, f"la consola del navegador queda limpia ({len(errores)}): {errores[:2]}")
        ctx.close()
        nav.close()

    # ============ 5. El informe, en sus tres soportes ============
    print("--- 5. El informe (§7.2 sección 6) ---")
    params = {"desde": str(lunes), "hasta": str(lunes + timedelta(days=6))}

    datos = cli.get(f"{API}/time/informe", params=params).json()
    bloque = {p["project_name"]: p for p in datos["proyectos"]}
    if ok(MUERTO in bloque, "el informe trae el proyecto finalizado"):
        b = bloque[MUERTO]
        ok(b["status"] == "finalizado" and b["status_label"] == "Finalizado",
           f"con su estado: {b['status_label']}")
        ok(b["overrun_status"] == "desfasado",
           f"y su consumo aparte: {b['overrun_label']}")

    # Lo que el INFORME enseña lo fija `h83b_informe.py` (H-D102): aquí solo se
    # comprueba que los datos siguen trayendo las dos cosas por separado, que es
    # lo que hace posible que cada salida elija qué enseña.
    html = cli.get(f"{API}/time/informe/html", params=params).text
    ok(">Estado</th>" in html, "el HTML tiene la columna de estado")
    ok(">En el periodo</th>" in html, "y las columnas de horas siguen ahí")

    pdf = cli.get(f"{API}/time/informe/pdf", params=params)
    ok(pdf.status_code == 200 and pdf.content[:4] == b"%PDF",
       f"el PDF se genera ({pdf.status_code}, {len(pdf.content)} bytes)")

    print()
    if fallos:
        print(f"=== {len(fallos)} FALLO(S) ===")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("=== TODO PASA ===")
    return 0


if __name__ == "__main__":
    codigo = 1
    try:
        codigo = main()
    finally:
        limpiar()
    sys.exit(codigo)
