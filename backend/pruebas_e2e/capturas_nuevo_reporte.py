"""BLOQUE 4.0 — capturas de la pantalla «Nuevo Reporte» tal como es hoy (solo mirar).

    docker exec jmeter_backend sh /app/pruebas_e2e/reiniciar_8002.sh
    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_datos.py
    docker exec jmeter_backend python3 /app/pruebas_e2e/capturas_nuevo_reporte.py
    docker cp jmeter_backend:/tmp/mockups_actual/. C:\\proyectos\\Kinetix_pruebas\\mockups\\actual\\

Contra el 5173 con localhost:8001 resuelto al 8002 (base de PRUEBAS). El 8002 no
tiene IA, asi que:
  - 01 es la pantalla REAL sin IA (el bloqueo de F2);
  - de la 02 en adelante se simula que `/ai-config/estado` responde «ok» para
    ver la pantalla normal. La generacion corre de verdad en el 8002 y cae al
    respaldo: por eso la 07 es el aviso de F2 «tras generar».
La subida se retiene unos segundos para poder fotografiar el «analizando».
Crea UNA ejecucion en la base de pruebas, proyecto «ZZTEST-B4 captura» (regla 29).
"""
import json
import os
import sys
import threading
import time
import uuid
from datetime import timedelta

import psycopg2
from playwright.sync_api import sync_playwright

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/pruebas_e2e")
from app.core.security import create_access_token  # noqa: E402
import r1_integrado as R1  # noqa: E402

WEB = "http://localhost:5173"
PUERTO = os.environ.get("KX_API_PUERTO", "8002")
DB = os.environ.get("KX_DB", "jmeter_analyzer_test")
if "test" not in DB:
    sys.exit("PARADA: la base no es de pruebas")
SALIDA = "/tmp/mockups_actual"
JTL = "/app/uploads/ZZTEST-R1_carga.jtl"
TIEMPOS = {}


def admin():
    c = psycopg2.connect(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB)
    cur = c.cursor()
    cur.execute("select id, username, role from users where username='admin'")
    f = cur.fetchone()
    c.close()
    return f


def main():
    os.makedirs(SALIDA, exist_ok=True)
    uid, un, role = admin()
    tok = create_access_token({"sub": str(uid), "username": un, "role": role}, timedelta(minutes=60))
    csrf = uuid.uuid4().hex
    threading.Thread(target=R1._rele, daemon=True).start()
    time.sleep(0.5)
    with sync_playwright() as p:
        b = p.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO}"])
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_cookies([{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
                         {"name": "csrf_token", "value": csrf, "domain": "localhost", "path": "/"}])
        pg = ctx.new_page()

        def foto(n, nombre):
            pg.wait_for_timeout(600)
            ruta = f"{SALIDA}/{n:02d}_{nombre}.png"
            pg.screenshot(path=ruta, full_page=True)
            print("captura", ruta)

        # 01 — la pantalla real, sin IA en el 8002: el bloqueo de F2
        pg.goto(f"{WEB}/performance/new", wait_until="networkidle", timeout=120000)
        pg.get_by_text("Configuracion del Reporte de Performance").wait_for(timeout=60000)
        foto(1, "vacia_sin_ia_bloqueo")

        # 02 — vacia, con la IA «disponible» (simulada)
        pg.route("**/ai-config/estado**", lambda r: r.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"ok": True, "motivo_tipo": None, "detalle": None, "cache": False})))
        pg.goto(f"{WEB}/performance/new", wait_until="networkidle", timeout=120000)
        pg.get_by_role("button", name="Generar Reporte").wait_for(timeout=60000)
        foto(2, "vacia")

        # 03 — tipo, cliente, proyecto y el JTL elegido (panel de transacciones)
        pg.get_by_role("button", name="Stress Test").click()
        sel = pg.locator("select").first
        opciones = sel.locator("option").all_inner_texts()
        cliente = next((o for o in opciones if o.startswith("ZZTEST")), None)
        if cliente:
            sel.select_option(label=cliente)
        pg.get_by_placeholder("Nombre del proyecto").fill("ZZTEST-B4 captura")
        t0 = time.time()
        pg.locator('input[type="file"]').set_input_files(JTL)
        pg.get_by_text("Transacciones del JTL").wait_for(timeout=120000)
        TIEMPOS["panel_transacciones_s"] = round(time.time() - t0, 1)
        foto(3, "con_jtl")

        # 04 — criterios: los generales y los propios de una transaccion abiertos
        for ph, v in (("100", "50"), ("2000", "1500"), ("99.5", "99")):
            pg.get_by_placeholder(ph, exact=True).first.fill(v)
        fila = pg.locator("button[data-tx]").first
        if fila.count():
            fila.click()
        foto(4, "con_criterios")

        # 05 — analizando: se retiene la subida para poder fotografiarla
        retenidas = []
        es_subida = lambda url: "/api/v1/upload" in url   # noqa: E731 (puede llevar parametros)
        pg.route(es_subida, lambda r: retenidas.append(r) if r.request.method == "POST" else r.continue_())
        pg.get_by_role("button", name="Generar Reporte").click()
        for _ in range(60):
            if retenidas:
                break
            pg.wait_for_timeout(250)
        try:
            pg.get_by_text("generando analisis").first.wait_for(timeout=30000)
        except Exception:
            pg.screenshot(path=f"{SALIDA}/99_depuracion.png", full_page=True)
            print("retenidas:", len(retenidas), "texto:", pg.locator("body").inner_text()[-600:])
            raise
        foto(5, "analizando")
        t0 = time.time()
        for r in retenidas:
            r.continue_()
        pg.unroute(es_subida)

        # 06/07 — al terminar: sin IA cae al respaldo y sale el aviso de F2; con IA
        # iria directo al informe (/performance/report/<id>).
        pg.wait_for_function("() => !document.body.innerText.includes('generando analisis')", timeout=600000)
        TIEMPOS["subida_y_analisis_sin_ia_s"] = round(time.time() - t0, 1)
        foto(6, "al_terminar_aviso_respaldo")
        boton = pg.get_by_test_id("aviso-tras-generar-ver")
        if boton.count():
            boton.first.click()
        pg.wait_for_url("**/performance/report/**", timeout=120000)
        pg.wait_for_load_state("networkidle", timeout=180000)
        TIEMPOS["url_final"] = pg.url.split("/performance/")[1][:20] + "…"
        foto(7, "informe_abierto")
        b.close()
    json.dump(TIEMPOS, open(f"{SALIDA}/tiempos.json", "w"), indent=1)
    print(json.dumps(TIEMPOS))


if __name__ == "__main__":
    main()
