"""F2 (aviso de respaldo) — las pantallas, contra el backend de PRUEBAS.

    docker exec -e KX_API=http://localhost:8002/api/v1 -e KX_API_PUERTO=8002 \
        -e KX_DB=jmeter_analyzer_test jmeter_backend python3 /app/pruebas_e2e/f2_pantallas.py

El 8002 no tiene clave de IA: es exactamente el caso a probar, y no puede
escaparse ni una llamada. Chromium habla con el 8002 por --host-resolver-rules
(memoria del proyecto: nada de page.route para esto).

  1. Subir: la pantalla para ANTES de generar (panel, el boton de siempre
     oculto, «generar sin IA» bloqueado hasta aceptar), y al terminar un aviso
     que NO se cierra solo.
  2. El informe: la franja con el texto, arriba.
  3. Una transaccion: el rotulo en cada seccion.
  4. Exportar: el aviso y «Exportar PDF igualmente».
  5. El historial: la columna y el filtro.
  6. El integrado: la franja dentro y la confirmacion al exportar.
Capturas en /tmp/f2/. Limpieza por la API y solo de lo ZZTEST-F2.
"""
import json
import os
import sys
import threading
import time
import uuid
from datetime import timedelta

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/pruebas_e2e")

import httpx
import psycopg2
from playwright.sync_api import sync_playwright

from app.core.security import create_access_token
import r1_integrado as R1   # el rele 5173 -> jmeter_frontend

WEB = "http://localhost:5173"
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
PUERTO = os.environ.get("KX_API_PUERTO", "8002")
DB = os.environ.get("KX_DB", "jmeter_analyzer_test")
if "test" not in DB:
    sys.exit("PARADA: la base no es de pruebas")
PG = dict(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB)
JTL = "/app/uploads/20251222_201217_resultados_general_carga_22-dic-2025-150249.jtl"
MARCA = "ZZTEST-F2"
SALIDA = "/tmp/f2"

fallos = []


def ok(c, msg):
    print(("PASA  | " if c else "FALLA | ") + msg, flush=True)
    if not c:
        fallos.append(msg)
    return c


def sql(q, args=(), escribir=False):
    c = psycopg2.connect(**PG)
    cur = c.cursor()
    cur.execute(q, args)
    filas = cur.fetchall() if cur.description else []
    if escribir:
        c.commit()
    c.close()
    return filas


def main():
    os.makedirs(SALIDA, exist_ok=True)
    uid, uname, role = sql("select id, username, role from users where username='admin'")[0]
    tok = create_access_token({"sub": str(uid), "username": uname, "role": role}, timedelta(minutes=60))
    csrf = uuid.uuid4().hex
    api = httpx.Client(cookies={"access_token": tok, "csrf_token": csrf},
                       headers={"X-CSRF-Token": csrf}, timeout=600)
    threading.Thread(target=R1._rele, daemon=True).start()
    time.sleep(0.5)

    with sync_playwright() as p:
        b = p.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO}"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1100})
        ctx.add_cookies([{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
                         {"name": "csrf_token", "value": csrf, "domain": "localhost", "path": "/"}])
        pg = ctx.new_page()

        print("\n=== 1. Subir: parar antes, avisar despues ===")
        pg.goto(f"{WEB}/performance/new", wait_until="networkidle", timeout=120000)
        panel = pg.get_by_test_id("panel-ia-no-disponible")
        panel.wait_for(timeout=30000)
        ok(panel.is_visible(), "el panel «La IA no está disponible» aparece al abrir la pantalla")
        ok("no hay ninguna IA configurada" in panel.inner_text(), "y dice por qué")
        ok(not pg.get_by_role("button", name="Generar Reporte").is_visible(), "el botón de siempre no está")
        pg.get_by_placeholder("Nombre del proyecto").fill(MARCA)
        pg.locator('input[type="file"]').first.set_input_files(JTL)
        pg.wait_for_timeout(2500)
        boton = pg.get_by_test_id("ia-subir-sin-ia")
        ok(boton.is_disabled(), "«Generar sin IA» está bloqueado hasta aceptar")
        pg.screenshot(path=f"{SALIDA}/1_subir_bloqueado.png", full_page=False)
        panel.scroll_into_view_if_needed()
        pg.screenshot(path=f"{SALIDA}/1_subir_panel.png")
        pg.get_by_test_id("ia-aceptar-sin-ia").check()
        ok(boton.is_enabled(), "al aceptar, se desbloquea")
        boton.click()
        aviso = pg.get_by_test_id("aviso-tras-generar")
        aviso.wait_for(timeout=300000)
        ok("no las escribió la IA" in aviso.inner_text(), f"al terminar: «{aviso.inner_text().splitlines()[0][:90]}»")
        pg.wait_for_timeout(7000)
        ok(aviso.is_visible(), "7 s después sigue ahí: no se cierra solo")
        pg.screenshot(path=f"{SALIDA}/2_tras_generar.png")
        pg.get_by_test_id("aviso-tras-generar-ver").click()
        pg.wait_for_url("**/performance/report/**", timeout=60000)
        eid = pg.url.rstrip("/").split("/")[-1]
        print(f"      ejecucion {eid}")

        print("\n=== 2. El informe ===")
        franja = pg.get_by_test_id("franja-respaldo")
        franja.wait_for(timeout=60000)
        t = franja.inner_text()
        ok("no lo escribió la IA" in t or "no las escribió la IA" in t, f"la franja: «{t.splitlines()[0][:90]}»")
        ok("Por qué" in t and "no hay ninguna IA configurada" in t, "con el motivo")
        # Decision de Fredy (29/09): arriba del todo, bajo la cabecera. Se ve sin bajar.
        pg.evaluate("window.scrollTo(0, 0)")
        pg.wait_for_timeout(300)
        caja_kpis = pg.get_by_text("Dashboard de KPIs").first.bounding_box()
        caja = franja.bounding_box()
        ok(caja["y"] < caja_kpis["y"], "antes de los KPIs")
        ok(caja["y"] < 1100, f"a la vista al abrir el informe, sin bajar (empieza en y={caja['y']:.0f} de 1100)")
        ok(pg.get_by_test_id("franja-respaldo").count() == 1, "una sola franja, no dos")
        pg.screenshot(path=f"{SALIDA}/3_informe_arriba.png")
        franja.scroll_into_view_if_needed()
        pg.screenshot(path=f"{SALIDA}/3_informe_franja.png")

        print("\n=== 3. Una transaccion ===")
        from app.services.jtl.jtl_parser import JTLParser
        tx = str(JTLParser(JTL).parse()[0]["label"].iloc[0])
        g = api.post(f"{API}/executions/{eid}/transaction-report", params={"label": tx})
        ok(g.status_code == 200, f"se genera el informe de «{tx}» ({g.status_code}), sin IA")
        pg.reload(wait_until="networkidle")
        pg.get_by_test_id("franja-respaldo").wait_for(timeout=60000)
        pg.wait_for_timeout(4000)
        rot = pg.get_by_test_id("rotulo-respaldo")
        n = rot.count()
        ok(n >= 5, f"rótulos por sección en la transacción: {n}")
        if n:
            ok("la IA no lo generó" in rot.first.inner_text(), f"«{rot.first.inner_text()[:80]}»")
            rot.first.scroll_into_view_if_needed()
            pg.screenshot(path=f"{SALIDA}/4_transaccion_rotulo.png")
        franja_t = pg.get_by_test_id("franja-respaldo").inner_text()
        ok(tx in franja_t, "la franja nombra también la transacción")

        print("\n=== 4. Exportar ===")
        pg.get_by_role("button", name="Exportar PDF").first.click()
        dlg = pg.get_by_test_id("dialogo-export")
        dlg.wait_for(timeout=30000)
        pg.get_by_test_id("aviso-exportar").wait_for(timeout=30000)
        ok("no las escribió la IA" in pg.get_by_test_id("aviso-exportar").inner_text(), "el diálogo lo dice")
        ok("igualmente" in pg.get_by_test_id("export-confirmar").inner_text(), f"botón: «{pg.get_by_test_id('export-confirmar').inner_text()}»")
        pg.screenshot(path=f"{SALIDA}/5_exportar.png")
        pg.get_by_test_id("export-cancelar").click()

        print("\n=== 4b. Exportar un informe SIN respaldo: como siempre ===")
        limpio = sql("select id from test_executions where name='ZZTEST-R1 carga'")
        if limpio:
            pg.goto(f"{WEB}/performance/report/{limpio[0][0]}", wait_until="networkidle", timeout=120000)
            pg.get_by_role("button", name="Exportar PDF").first.wait_for(timeout=60000)
            pg.wait_for_timeout(2000)
            ok(pg.get_by_test_id("franja-respaldo").count() == 0, "sin franja")
            pg.get_by_role("button", name="Exportar PDF").first.click()
            pg.get_by_test_id("dialogo-export").wait_for(timeout=30000)
            pg.wait_for_timeout(1500)
            ok(pg.get_by_test_id("aviso-exportar").count() == 0, "el diálogo no avisa de nada")
            ok(pg.get_by_test_id("export-confirmar").inner_text().strip() == "Exportar PDF",
               f"y el botón es el de siempre: «{pg.get_by_test_id('export-confirmar').inner_text().strip()}»")
            pg.get_by_test_id("export-cancelar").click()
        else:
            ok(False, "no está ZZTEST-R1 carga en la base de pruebas (correr r1_datos.py)")

        print("\n=== 5. El historial ===")
        pg.goto(f"{WEB}/performance/history", wait_until="networkidle", timeout=120000)
        pg.get_by_text("Origen del texto").wait_for(timeout=30000)
        fila = pg.locator("tr", has_text=MARCA).first
        ok("Sin IA" in fila.inner_text(), f"la fila de {MARCA}: «{fila.get_by_test_id('origen-sin-ia').inner_text().splitlines()[0]}»")
        antes = pg.locator("tbody tr").count()
        pg.get_by_test_id("filtro-sin-ia").check()
        pg.wait_for_timeout(500)
        despues = pg.locator("tbody tr").count()
        con = pg.get_by_test_id("origen-sin-ia").count()
        ok(despues <= antes and con == despues, f"el filtro deja solo las que tienen secciones sin IA ({antes} -> {despues})")
        pg.screenshot(path=f"{SALIDA}/6_historial.png")

        print("\n=== 6. El integrado ===")
        rid = str(uuid.uuid4())
        sql("insert into integrated_reports (id, name, sections, consolidated_analysis, created_by, created_at, updated_at) "
            "values (%s,%s,%s,'{}',%s,now(),now())",
            (rid, f"{MARCA} integrado", json.dumps([{"order": 0, "type": "load_test", "source_id": eid,
                                                       "source_name": MARCA}]), str(uid)), escribir=True)
        pg.goto(f"{WEB}/performance/integrated/{rid}", wait_until="networkidle", timeout=120000)
        pg.get_by_test_id("franja-respaldo").first.wait_for(timeout=120000)
        ok(True, "la franja sale también dentro del integrado")
        pg.get_by_role("button", name="Exportar PDF").last.click()
        conf = pg.get_by_test_id("confirmar-export-integrado")
        conf.wait_for(timeout=30000)
        ok(MARCA in conf.inner_text() and "igualmente" in conf.inner_text(), "exportar el integrado pide confirmación y nombra la ejecución")
        pg.screenshot(path=f"{SALIDA}/7_integrado_exportar.png")
        pg.get_by_test_id("export-integrado-cancelar").click()
        b.close()

    # Limpieza: solo lo ZZTEST-F2, por la API (reglas 29 y 30).
    for r in api.get(f"{API}/reports/integrated-reports").json():
        if str(r.get("name", "")).startswith(MARCA):
            api.delete(f"{API}/reports/integrated-reports/{r['id']}")
    for x in api.get(f"{API}/executions").json():
        if x["name"].startswith(MARCA):
            api.delete(f"{API}/executions/{x['id']}")
    quedan = [x for x in api.get(f"{API}/executions").json() if x["name"].startswith(MARCA)]
    ok(not quedan, "limpieza: no queda ninguna ejecución ZZTEST-F2")

    print("\nF2 PANTALLAS: TODO PASA" if not fallos else f"\nF2 PANTALLAS: {len(fallos)} FALLA(N)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
