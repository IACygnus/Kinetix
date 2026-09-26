"""ETAPA R1.2 — el selector de secciones del informe integrado, punta a punta.

    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_datos.py
    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_seleccion.py

Contra la base de PRUEBAS (regla 34), con el 8001 resuelto al 8002 por el propio
Chromium (ver r1_integrado.py). Token generado en proceso: sin cupo de login.

Lo que demuestra:
  1. Opcion (a) de Fredy: una seccion de carga ya NO pinta dentro sus capturas ni
     sus evidencias.
  2. En la pantalla, quitar transacciones, capturas y evidencias las quita.
  3. La seleccion se guarda con el informe y vuelve al reabrirlo.
  4. El HTML y el PDF exportados respetan la seleccion (el PDF se lee fuera del
     contenedor con r1_pdf_texto.py).
  5. El consolidado: lo quitado NO llega a su prompt, y el prompt dice que
     transacciones detalla el documento. **0 llamadas a la IA**: el prompt se
     captura con un sustituto de la IA que no llama a nadie.
"""
import json
import os
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
PG = dict(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB_TEST)
if "test" not in DB_TEST:
    sys.exit("PARADA: la base no es de pruebas")

QUEDA_TX = "6. Delete_Booking_Id"
FUERA_TX = ["4. Get_Booking_Id", "5. Put_Update_Booking"]
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


def firma_tx(carga, label):
    """Un trozo del texto del informe propio de la transaccion: solo aparece si su
    bloque esta en el documento (la tabla resumen general lleva el NOMBRE de todas)."""
    t = sql("select ai_analysis from transaction_chart_analyses where execution_id=%s and label=%s "
            "and section='summary'", (carga, label))[0][0]
    return " ".join(t.split()[:8])


def main():
    rid = str(sql("select id from integrated_reports where name='ZZTEST-R1 seleccion'")[0][0])
    solo = str(sql("select id from integrated_reports where name='ZZTEST-R1 solo carga'")[0][0])
    carga = str(sql("select id from test_executions where name='ZZTEST-R1 carga'")[0][0])
    uid, uname, role = sql("select id, username, role from users where username='admin'")[0]
    tok = create_access_token({"sub": str(uid), "username": uname, "role": role}, timedelta(minutes=60))
    csrf = uuid.uuid4().hex
    firmas = {l: firma_tx(carga, l) for l in [QUEDA_TX] + FUERA_TX}

    threading.Thread(target=_rele, daemon=True).start()
    time.sleep(0.5)

    with sync_playwright() as p:
        b = p.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO_TEST}"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1000})
        ctx.add_cookies([{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
                         {"name": "csrf_token", "value": csrf, "domain": "localhost", "path": "/"}])

        def titulos_tx(pg):
            # Solo los bloques de la seccion de CARGA (la primera): la de estres
            # tiene los suyos y no se ha tocado.
            return pg.locator("div.border-b-2.pb-4.mb-4").first.locator("span.text-2xl.font-bold").all_inner_texts()

        # ── 1. opcion (a): la seccion de carga ya no lleva sus capturas dentro ──
        pg = ctx.new_page()
        pg.goto(f"{WEB}/performance/integrated/{solo}", wait_until="networkidle", timeout=120000)
        pg.get_by_text(QUEDA_TX, exact=True).first.wait_for(timeout=120000)
        pg.wait_for_timeout(3000)
        comprobar(pg.locator("img[alt^='ZZTEST']").count() == 0,
                  "opcion (a): una seccion de carga sola NO pinta capturas ni evidencias dentro")
        pg.close()

        # ── 2. el selector en pantalla ──
        pg = ctx.new_page()
        pg.goto(f"{WEB}/performance/integrated/{rid}", wait_until="networkidle", timeout=120000)
        pg.get_by_text("Se guarda con el informe integrado").first.wait_for(timeout=120000)

        def selector(tipo):
            s = pg.get_by_test_id(f"selector-{tipo}-{carga}")
            if s.locator("input[type=checkbox]").count() == 0:
                s.get_by_test_id("selector-resumen").click()
            return s

        s = selector("load_test")
        s.get_by_role("button", name="Todas", exact=True).click()
        for l in FUERA_TX:
            s.locator(f"input[data-opcion='{l}']").uncheck()
        s = selector("monitoring")
        s.get_by_role("button", name="Todas", exact=True).click()
        s.locator("input[data-opcion='ZZTEST captura 2']").uncheck()
        s = selector("evidence")
        s.get_by_role("button", name="Ninguna", exact=True).click()

        pg.wait_for_timeout(2000)
        tx = titulos_tx(pg)
        comprobar(QUEDA_TX in tx and not any(l in tx for l in FUERA_TX),
                  f"pantalla: solo queda el bloque de '{QUEDA_TX}' (bloques: {tx})")
        comprobar(pg.locator("img[alt='ZZTEST captura 1']").count() == 1
                  and pg.locator("img[alt='ZZTEST captura 2']").count() == 0,
                  "pantalla: queda la captura 1 y no la 2")
        comprobar(pg.locator("img[alt='ZZTEST evidencia 1']").count() == 0,
                  "pantalla: sin evidencias, la seccion de evidencias no pinta nada")
        pg.wait_for_function(
            "() => (document.querySelector('[data-testid=estado-guardado]')?.textContent || '').startsWith('Guardado')",
            timeout=90000)

        secs = sql("select sections from integrated_reports where id=%s", (rid,))[0][0]
        por_tipo = {s["type"]: s.get("seleccion") for s in secs}
        att1 = str(sql("select id from execution_attachments where execution_id=%s and title='ZZTEST captura 1'",
                       (carga,))[0][0])
        comprobar(por_tipo.get("load_test") == {"tx": [QUEDA_TX]}, f"base: carga guarda {por_tipo.get('load_test')}")
        comprobar(por_tipo.get("monitoring") == {"adjuntos": [att1]}, f"base: monitoreo guarda {por_tipo.get('monitoring')}")
        comprobar(por_tipo.get("evidence") == {"adjuntos": []}, f"base: evidencias guarda {por_tipo.get('evidence')}")
        comprobar(por_tipo.get("stress_test") in ({}, None), f"base: estres sin tocar ({por_tipo.get('stress_test')})")
        pg.close()

        # ── 3. al reabrir, la seleccion vuelve ──
        pg = ctx.new_page()
        pg.goto(f"{WEB}/performance/integrated/{rid}", wait_until="networkidle", timeout=120000)
        pg.get_by_text("Se guarda con el informe integrado").first.wait_for(timeout=120000)
        res = {t: pg.get_by_test_id(f"selector-{t}-{carga}").get_by_test_id("selector-resumen").inner_text()
               for t in ("load_test", "monitoring", "evidence")}
        comprobar("1 de 3 transacciones" in res["load_test"], f"al reabrir, carga dice «{res['load_test']}»")
        comprobar("1 de 2 capturas" in res["monitoring"], f"al reabrir, monitoreo dice «{res['monitoring']}»")
        comprobar("ninguna captura" in res["evidence"], f"al reabrir, evidencias dice «{res['evidence']}»")
        tx = titulos_tx(pg)
        comprobar(tx == [QUEDA_TX], f"al reabrir, la pantalla sigue con un solo bloque ({tx})")
        pg.close()
        b.close()

    # ── 4. los exportados, con la seleccion GUARDADA ──
    secs = sql("select sections from integrated_reports where id=%s", (rid,))[0][0]
    cuerpo = {"sections": [{k: s.get(k) for k in ("order", "type", "source_id", "source_name", "seleccion")}
                           for s in secs], "unified_conclusions": "", "report_id": rid}
    with httpx.Client(cookies={"access_token": tok, "csrf_token": csrf},
                      headers={"X-CSRF-Token": csrf}, timeout=600) as cli:
        html = cli.post(f"{API_TEST}/reports/integrated/export-html", json=cuerpo)
        pdf = cli.post(f"{API_TEST}/reports/integrated/export-pdf", json=cuerpo)
    comprobar(html.status_code == 200 and pdf.status_code == 200, f"exportados {html.status_code}/{pdf.status_code}")
    texto = html.content.decode("utf-8", "replace")
    comprobar(firmas[QUEDA_TX] in texto, f"HTML: lleva el informe de '{QUEDA_TX}'")
    for l in FUERA_TX:
        comprobar(firmas[l] not in texto, f"HTML: NO lleva el informe de '{l}'")
    comprobar("ZZTEST captura 1" in texto and "ZZTEST captura 2" not in texto, "HTML: captura 1 si, captura 2 no")
    comprobar("ZZTEST evidencia 1" not in texto, "HTML: sin la evidencia quitada")
    open("/tmp/r1_seleccion.pdf", "wb").write(pdf.content)
    json.dump({"presentes": [firmas[QUEDA_TX], "ZZTEST captura 1"],
               "ausentes": [firmas[l] for l in FUERA_TX] + ["ZZTEST captura 2", "ZZTEST evidencia 1"]},
              open("/tmp/r1_seleccion_esperado.json", "w"), ensure_ascii=False)

    # ── 5. el consolidado: el prompt, capturado sin llamar a la IA ──
    out = subprocess.run(
        [sys.executable, "/app/pruebas_e2e/r1_prompt_consolidado.py", rid],
        env={**os.environ, "DATABASE_URL": f"postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/{DB_TEST}"},
        capture_output=True, text=True, timeout=600)
    prompts = [l for l in out.stdout.splitlines() if l.startswith("PROMPT ")]
    comprobar(out.returncode == 0 and prompts, f"consolidado: prompt capturado (salida {out.returncode})")
    if prompts:
        # Un prompt por tipo de prueba (carga y estres): se miran todos juntos.
        prompt = " ||| ".join(json.loads(l[len("PROMPT "):]) for l in prompts)
        comprobar("ZZTEST analisis original de la captura 1" in prompt, "consolidado: la captura elegida SI llega")
        comprobar("captura 2" not in prompt, "consolidado: la captura quitada NO llega")
        comprobar("evidencia 1" not in prompt, "consolidado: la evidencia quitada NO llega")
        comprobar(f"- ZZTEST-R1 carga: {QUEDA_TX}" in prompt,
                  "consolidado: el prompt dice que transaccion detalla el documento")
    print(out.stdout[-600:] if out.returncode else "", out.stderr[-1500:] if out.returncode else "")

    print(f"\n{'TODO PASA' if not fallos else f'{len(fallos)} FALLO(S)'}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
