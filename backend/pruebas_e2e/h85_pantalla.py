"""ETAPA H8.5 — el bloque de borrado en la pantalla de Importación (§4.3).

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/h85_pantalla.py

Lo que se comprueba aquí y no en el backend:

- que el bloque está **plegado por defecto** y hay que abrirlo;
- que **cambiar el rango invalida la previa**, la casilla y el texto tecleado
  —lo único que impide confirmar un rango distinto del revisado—;
- y que el botón no se activa hasta tener **la casilla marcada Y la frase
  exacta**, ni con una sola de las dos.

**Hasta el último paso no se borra nada**: los pasos anteriores comprueban que
el botón está apagado, que es lo contrario de pulsarlo.

Datos `ZZTEST-H85P` (regla 29), base de pruebas (regla 34). 0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys

import httpx
from playwright.sync_api import sync_playwright

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
PUERTO_API = os.environ.get("KX_API_PUERTO", "8002")

MARCA = "ZZTEST-H85P"
DIAS = ["2026-08-11", "2026-08-12"]
FRASE = "agosto de 2026"

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
        f"delete from time_entry_purges where desde = '2026-08-01' and hasta = '2026-08-31';"
    )


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    cliente = cli.get(f"{API}/clients").json()[0]["id"]
    act = cli.get(f"{API}/time/activities").json()[0]["id"]
    pid = cli.post(f"{API}/time/projects", json={
        "client_id": cliente, "name": f"{MARCA}-proyecto",
        "activities": [{"activity_id": act, "estimated_hours": 40}]}).json()["id"]
    for f in DIAS:
        cli.post(f"{API}/time/entries", json={
            "project_id": pid, "activity_id": act, "date": f, "hours": "4",
            "billable": True, "overtime": False, "notes": f"{MARCA} prueba"})

    def registros():
        return int(psql("select count(*) from time_entries;").stdout.strip() or 0)

    antes = registros()
    print(f"registros antes: {antes}")

    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1600, "height": 1400},
                              storage_state=SESION, locale="es-CO")
        page = ctx.new_page()
        desviar(page)
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))

        print("\n=== 1. Plegado por defecto ===")
        page.goto(f"{WEB}/horas/importar", wait_until="networkidle")
        page.wait_for_selector("[data-testid='bloque-borrar-periodo']", timeout=25000)
        ok(page.locator("[data-testid='panel-borrar-periodo']").count() == 0,
           "el bloque está plegado: no se ve el panel")
        ok(page.locator("[data-testid='abrir-borrar-periodo']").count() == 1,
           "y hay que abrirlo a propósito")
        page.locator("[data-testid='abrir-borrar-periodo']").click()
        page.wait_for_selector("[data-testid='panel-borrar-periodo']", timeout=10000)
        ok(True, "abierto")

        print("\n=== 2. La vista previa ===")
        page.locator("[data-testid='borrado-desde']").fill("2026-08-01")
        page.locator("[data-testid='borrado-hasta']").fill("2026-08-31")
        page.locator("[data-testid='ver-que-se-borra']").click()
        page.wait_for_selector("[data-testid='previa-borrado']", timeout=20000)
        totales = page.locator("[data-testid='borrado-totales']").inner_text()
        ok("2 registro" in totales, f"dice cuántos: «{' '.join(totales.split())}»")
        ok("a mano" in totales, "y de dónde vinieron")
        ok(page.locator("[data-testid='borrado-por-persona'] tbody tr").count() >= 1,
           "y de quién son")
        no_se_borra = page.locator("[data-testid='lo-que-no-se-borra']").inner_text()
        ok("SOLO registros de horas" in no_se_borra,
           "y qué sobrevive, con esas palabras")
        ok("pg_dump" in page.locator("[data-testid='comando-copia']").inner_text(),
           "el comando de la copia está a la vista")
        ok(registros() == antes, "**y la previa no borró nada**")

        print("\n=== 3. El botón no se activa a medias ===")
        boton = page.locator("[data-testid='borrar-periodo']")
        ok(boton.is_disabled(), "apagado nada más ver la previa")
        page.locator("[data-testid='copia-hecha']").check()
        ok(boton.is_disabled(), "apagado con la casilla pero sin la frase")
        page.locator("[data-testid='frase-confirmacion']").fill("agosto 2026")
        ok(boton.is_disabled(), "apagado con la frase casi bien («agosto 2026»)")
        page.locator("[data-testid='frase-confirmacion']").fill(FRASE)
        ok(boton.is_enabled(), "encendido con las dos cosas")
        page.locator("[data-testid='frase-confirmacion']").fill("  AGOSTO  de 2026 ")
        ok(boton.is_enabled(),
           "y sigue encendido con mayúsculas y espacios de más, como el backend")

        print("\n=== 4. Cambiar el rango invalida la previa ===")
        page.locator("[data-testid='borrado-hasta']").fill("2026-08-15")
        page.wait_for_timeout(600)
        ok(page.locator("[data-testid='previa-borrado']").count() == 0,
           "**la previa desaparece al tocar las fechas**")
        ok(page.locator("[data-testid='borrar-periodo']").count() == 0,
           "y con ella el botón: no se puede confirmar un rango sin revisar")
        page.locator("[data-testid='ver-que-se-borra']").click()
        page.wait_for_selector("[data-testid='previa-borrado']", timeout=20000)
        ok(not page.locator("[data-testid='copia-hecha']").is_checked(),
           "la casilla vuelve a estar sin marcar")
        ok(page.locator("[data-testid='frase-confirmacion']").input_value() == "",
           "y el texto tecleado, vacío")
        ok(registros() == antes, "y sigue sin borrarse nada")

        print("\n=== 5. El borrado, ya de verdad ===")
        page.locator("[data-testid='borrado-desde']").fill("2026-08-01")
        page.locator("[data-testid='borrado-hasta']").fill("2026-08-31")
        page.locator("[data-testid='ver-que-se-borra']").click()
        page.wait_for_selector("[data-testid='previa-borrado']", timeout=20000)
        page.locator("[data-testid='copia-hecha']").check()
        page.locator("[data-testid='frase-confirmacion']").fill(FRASE)
        page.locator("[data-testid='borrar-periodo']").click()
        page.wait_for_selector("[data-testid='resumen-borrado']", timeout=20000)
        texto = page.locator("[data-testid='resumen-borrado']").inner_text()
        ok("2 registros" in texto, f"el resumen dice qué pasó: «{' '.join(texto.split())[:90]}»")
        ok(registros() == antes - len(DIAS),
           f"y se fueron los {len(DIAS)} del rango: {registros()} de {antes}")

        ok(not errores, f"la consola queda limpia ({len(errores)}): {errores[:2]}")
        ctx.close()
        nav.close()

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
