"""ETAPA R1.4 — el informe integrado de punta a punta, como lo usaria Fredy.

    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_datos.py
    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_punta_a_punta.py

Base de PRUEBAS (regla 34), Chromium con el 8001 resuelto al 8002. El backend de
pruebas tiene que correr SIN clave de IA (GEMINI_API_KEY vacia): «Generar informe
integrado» pide unas conclusiones unificadas, y sin clave el analizador no llega a
construirse. La suite lo comprueba contando `AI CALL` en su log: 0 llamadas.

  1. Crea un integrado DESDE LA PANTALLA: carga + monitoreo + evidencias + estres.
  2. Antes de generar, en el selector: la carga sin transacciones y el monitoreo
     sin la captura 2.
  3. Genera, edita tres cajas (general de carga, general de estres y una captura)
     y SALE A LO BRUTO por el menu, con el foco dentro de la ultima.
  4. Vuelve: las ediciones estan en pantalla, y la seleccion tambien.
  5. HTML y PDF: llevan las ediciones y NO las transacciones ni la captura quitadas.
  6. Consolidado: su prompt NO lleva lo quitado, dice que la carga no detalla
     ninguna transaccion y SI lleva las ediciones (capturado sin llamar a la IA).
"""
import json
import os
import random
import string
import subprocess
import sys
import threading
import time
import uuid
from datetime import timedelta

import httpx
import psycopg2
from playwright.sync_api import sync_playwright

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/pruebas_e2e")
from app.core.security import create_access_token  # noqa: E402
from r1_integrado import _rele  # noqa: E402

WEB = "http://localhost:5173"
API_TEST = os.environ.get("KX_API", "http://localhost:8002/api/v1")
PUERTO_TEST = os.environ.get("KX_API_PUERTO", "8002")
DB_TEST = os.environ.get("KX_DB", "jmeter_analyzer_test")
LOG_TEST = "/tmp/backend_test.log"
PG = dict(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB_TEST)
if "test" not in DB_TEST:
    sys.exit("PARADA: la base no es de pruebas")
fallos = []


def comprobar(ok, texto):
    print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
    if not ok:
        fallos.append(texto)


def sql(q, args=()):
    c = psycopg2.connect(**PG)
    cur = c.cursor()
    cur.execute(q, args)
    filas = cur.fetchall()
    c.close()
    return filas


def llamadas_ia():
    try:
        return sum(1 for l in open(LOG_TEST, errors="replace") if "AI CALL:" in l)
    except FileNotFoundError:
        return -1


def main():
    carga = str(sql("select id from test_executions where name='ZZTEST-R1 carga'")[0][0])
    estres = str(sql("select id from test_executions where name='ZZTEST-R1 estres'")[0][0])
    att1, att2 = [str(r[0]) for r in sql(
        "select id from execution_attachments where execution_id=%s and attachment_type='monitoring' "
        "order by sort_order", (carga,))]
    firmas_tx = [" ".join(r[0].split()[:8]) for r in sql(
        "select ai_analysis from transaction_chart_analyses where execution_id=%s and section='summary'", (carga,))]
    uid, uname, role = sql("select id, username, role from users where username='admin'")[0]
    tok = create_access_token({"sub": str(uid), "username": uname, "role": role}, timedelta(minutes=60))
    csrf = uuid.uuid4().hex
    ia_antes = llamadas_ia()
    m = "ZZR1E2E" + "".join(random.choices(string.ascii_uppercase, k=4))
    print(f"marca {m}")

    threading.Thread(target=_rele, daemon=True).start()
    time.sleep(0.5)

    with sync_playwright() as p:
        b = p.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO_TEST}"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1000})
        ctx.add_cookies([{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
                         {"name": "csrf_token", "value": csrf, "domain": "localhost", "path": "/"}])

        # ── 1. crear el integrado desde la pantalla ──
        pg = ctx.new_page()
        pg.goto(f"{WEB}/performance/integrated", wait_until="networkidle", timeout=120000)

        def fila(nombre):
            return pg.locator("div.justify-between", has=pg.get_by_text(nombre, exact=True)).first

        fila("ZZTEST-R1 carga").get_by_role("button", name="Monitor (2)").wait_for(timeout=60000)
        fila("ZZTEST-R1 carga").get_by_role("button", name="Reporte").click()
        fila("ZZTEST-R1 carga").get_by_role("button", name="Monitor (2)").click()
        fila("ZZTEST-R1 carga").get_by_role("button", name="Evidencia (1)").click()
        fila("ZZTEST-R1 estres").get_by_role("button", name="Reporte").click()

        # ── 2. el selector, ANTES de generar ──
        s = pg.get_by_test_id(f"selector-load_test-{carga}")
        s.get_by_test_id("selector-resumen").wait_for(timeout=60000)
        s.get_by_test_id("selector-resumen").click()
        s.get_by_role("button", name="Ninguna", exact=True).click()
        s = pg.get_by_test_id(f"selector-monitoring-{carga}")
        s.get_by_test_id("selector-resumen").click()
        s.locator("input[data-opcion='ZZTEST captura 2']").uncheck()
        comprobar("solo el informe general" in pg.get_by_test_id(f"selector-load_test-{carga}").inner_text(),
                  "antes de generar: la carga dice «solo el informe general»")

        # ── 3. generar, editar y salir a lo bruto ──
        pg.get_by_role("button", name="Generar Informe Integrado").click()
        pg.wait_for_function("() => location.pathname.split('/').length === 4 && "
                             "/performance\\/integrated\\/[0-9a-f-]{36}/.test(location.pathname)", timeout=180000)
        rid = pg.evaluate("() => location.pathname.split('/').pop()")
        print(f"integrado creado {rid}")
        # R2: el registro de prueba lleva la marca ZZTEST- en el nombre
        with httpx.Client(cookies={"access_token": tok, "csrf_token": csrf},
                          headers={"X-CSRF-Token": csrf}, timeout=60) as cli:
            cli.patch(f"{API_TEST}/reports/integrated-reports/{rid}", json={"name": f"ZZTEST-R1 punta a punta {m}"})
        pg.get_by_test_id("estado-guardado").wait_for(timeout=60000)
        embebidos = pg.locator("div.border-b-2.pb-4.mb-4")
        embebidos.nth(1).locator("textarea").first.wait_for(timeout=120000)
        comprobar(embebidos.nth(0).locator("span.text-2xl.font-bold").count() == 0,
                  "tras generar: la carga no pinta ningun bloque por transaccion")
        comprobar(pg.locator("img[alt='ZZTEST captura 2']").count() == 0 and
                  pg.locator("img[alt='ZZTEST captura 1']").count() == 1,
                  "tras generar: la captura 2 no esta y la 1 si")

        def escribir(loc, texto):
            loc.scroll_into_view_if_needed()
            loc.click()
            pg.keyboard.press("Control+End")
            pg.keyboard.type(texto)

        escribir(embebidos.nth(0).locator("textarea").first, f" {m}-carga")
        escribir(embebidos.nth(1).locator("textarea").first, f" {m}-estres")
        idx = pg.evaluate("() => [...document.querySelectorAll('textarea')].findIndex("
                          "t => t.value.includes('ZZTEST analisis original de la captura 1'))")
        escribir(pg.locator("textarea").nth(idx), f" {m}-img")
        pg.locator("a[href='/performance/integrated/history']").first.click()   # a lo bruto
        pg.wait_for_timeout(3000)

        secs = sql("select sections from integrated_reports where id=%s", (rid,))[0][0]
        ov = {}
        for s_ in secs:
            for tipo in ("analysis", "images"):
                for k, v in ((s_.get("overrides") or {}).get(tipo) or {}).items():
                    ov[(s_["source_id"], tipo, k)] = v
        comprobar(f"{m}-carga" in (ov.get((carga, "analysis", "ai_analysis_summary")) or ""), "base: la edicion de la carga")
        comprobar(f"{m}-estres" in (ov.get((estres, "analysis", "ai_analysis_summary")) or ""), "base: la edicion del estres")
        comprobar(f"{m}-img" in (ov.get((carga, "images", att1)) or ""), "base: la edicion de la captura")
        sel = {s_["type"]: s_.get("seleccion") for s_ in secs}
        comprobar(sel.get("load_test") == {"tx": []} and sel.get("monitoring") == {"adjuntos": [att1]},
                  f"base: la seleccion ({sel.get('load_test')}, {sel.get('monitoring')})")

        # ── 4. volver ──
        pg.goto(f"{WEB}/performance/integrated/{rid}", wait_until="networkidle", timeout=120000)
        embebidos = pg.locator("div.border-b-2.pb-4.mb-4")
        embebidos.nth(1).locator("textarea").first.wait_for(timeout=120000)
        pg.wait_for_timeout(2000)
        valores = pg.evaluate("() => [...document.querySelectorAll('textarea')].map(t => t.value).join(' ')")
        for parte in ("carga", "estres", "img"):
            comprobar(f"{m}-{parte}" in valores, f"al volver: se ve la edicion {m}-{parte}")
        comprobar("solo el informe general" in pg.get_by_test_id(f"selector-load_test-{carga}").inner_text()
                  and "1 de 2 capturas" in pg.get_by_test_id(f"selector-monitoring-{carga}").inner_text(),
                  "al volver: la seleccion se ve en las tarjetas")
        comprobar(pg.get_by_test_id("aviso-recuperar").count() == 0, "al volver: no hay nada que recuperar")
        b.close()

    # ── 5. exportados ──
    secs = sql("select sections from integrated_reports where id=%s", (rid,))[0][0]
    cuerpo = {"sections": [{k: s_.get(k) for k in ("order", "type", "source_id", "source_name", "seleccion")}
                           for s_ in secs], "unified_conclusions": "", "report_id": rid}
    with httpx.Client(cookies={"access_token": tok, "csrf_token": csrf},
                      headers={"X-CSRF-Token": csrf}, timeout=600) as cli:
        html = cli.post(f"{API_TEST}/reports/integrated/export-html", json=cuerpo)
        pdf = cli.post(f"{API_TEST}/reports/integrated/export-pdf", json=cuerpo)
    comprobar(html.status_code == 200 and pdf.status_code == 200, f"exportados {html.status_code}/{pdf.status_code}")
    texto = html.content.decode("utf-8", "replace")
    for parte in ("carga", "estres", "img"):
        comprobar(f"{m}-{parte}" in texto, f"HTML: lleva {m}-{parte}")
    comprobar(not any(f in texto for f in firmas_tx), "HTML: ningun informe por transaccion de la carga")
    comprobar("ZZTEST captura 2" not in texto and "ZZTEST captura 1" in texto, "HTML: captura 1 si, captura 2 no")
    open("/tmp/r1_e2e.pdf", "wb").write(pdf.content)
    json.dump({"presentes": [f"{m}-carga", f"{m}-estres", f"{m}-img", "ZZTEST captura 1"],
               "ausentes": firmas_tx + ["ZZTEST captura 2"]},
              open("/tmp/r1_e2e_esperado.json", "w"), ensure_ascii=False)

    # ── 6. consolidado, sin IA ──
    out = subprocess.run(
        [sys.executable, "/app/pruebas_e2e/r1_prompt_consolidado.py", rid],
        env={**os.environ, "DATABASE_URL": f"postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/{DB_TEST}"},
        capture_output=True, text=True, timeout=600)
    prompts = [json.loads(l[len("PROMPT "):]) for l in out.stdout.splitlines() if l.startswith("PROMPT ")]
    prompt = " ||| ".join(prompts)
    comprobar(out.returncode == 0 and prompts, f"consolidado: prompt capturado ({len(prompts)})")
    comprobar(not any(f in prompt for f in firmas_tx), "consolidado: ningun texto por transaccion de la carga")
    comprobar("- ZZTEST-R1 carga: ninguna (solo el informe general)" in prompt,
              "consolidado: dice que la carga no detalla ninguna transaccion")
    comprobar("captura 2" not in prompt and "captura 1" in prompt, "consolidado: captura 1 si, captura 2 no")
    comprobar(f"{m}-carga" in prompt and f"{m}-img" in prompt, "consolidado: se redacta sobre las ediciones")

    ia = llamadas_ia()
    comprobar(ia == ia_antes, f"0 llamadas a la IA en el backend de pruebas (log: {ia_antes} -> {ia})")
    print(f"\n{'TODO PASA' if not fallos else f'{len(fallos)} FALLO(S)'}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
