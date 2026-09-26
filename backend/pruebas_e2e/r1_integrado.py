"""ETAPA R1.1 — el guardado del informe integrado, punta a punta.

    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_datos.py
    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_integrado.py

Contra la base de PRUEBAS (regla 34): el navegador abre la pantalla real en
localhost:5173 y TODA llamada al 8001 se desvia al 8002. No se gasta cupo de
login: el token se genera en proceso con el usuario admin de la base de pruebas.

Lo que demuestra (reporte 120 §1):
  1. Editar tres cajas (una general, una por transaccion y una de captura) y
     SALIR DE INMEDIATO por los tres caminos —menu, F5, cerrar la pestaña— deja
     las tres ediciones en la base.
  2. El indicador dice «Cambios sin guardar» mientras no hay confirmacion, y
     «Guardado» solo despues.
  3. Si el guardado falla, sale un aviso visible; si ademas falla al salir, al
     volver la pagina ofrece recuperar lo escrito, y recuperarlo lo guarda.
  4. Lo guardado sale en el HTML y en el PDF exportados. El texto del PDF se
     comprueba ademas fuera del contenedor (ver el reporte de cierre).

0 llamadas a la IA: no se genera ni el informe ni el consolidado.
"""
import asyncio
import json
import os
import random
import string
import sys
import threading
import time
import uuid
from datetime import timedelta

import httpx
import psycopg2
from playwright.sync_api import sync_playwright

sys.path.insert(0, "/app")
from app.core.security import create_access_token  # noqa: E402

WEB = "http://localhost:5173"
API_TEST = os.environ.get("KX_API", "http://localhost:8002/api/v1")
PUERTO_TEST = os.environ.get("KX_API_PUERTO", "8002")
DB_TEST = os.environ.get("KX_DB", "jmeter_analyzer_test")
PG = dict(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB_TEST)
if "test" not in DB_TEST:
    sys.exit("PARADA: la base no es de pruebas")

fallos = []


def comprobar(ok, texto):
    print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
    if not ok:
        fallos.append(texto)


# ── rele 5173 -> jmeter_frontend (mismo motivo que rele_5173.py: el origen) ──
def _rele():
    async def bombear(r, w):
        try:
            while True:
                d = await r.read(65536)
                if not d:
                    break
                w.write(d)
                await w.drain()
        except Exception:
            pass
        finally:
            try:
                w.close()
            except Exception:
                pass

    async def atender(r, w):
        r2, w2 = await asyncio.open_connection("jmeter_frontend", 5173)
        await asyncio.gather(bombear(r, w2), bombear(r2, w))

    async def main():
        srv = await asyncio.start_server(atender, "127.0.0.1", 5173)
        async with srv:
            await srv.serve_forever()
    try:
        asyncio.run(main())
    except OSError:
        pass   # ya hay un rele escuchando


def sql(q, args=()):
    c = psycopg2.connect(**PG)
    cur = c.cursor()
    cur.execute(q, args)
    filas = cur.fetchall()
    c.close()
    return filas


def overrides_guardados(rid):
    secs = sql("select sections from integrated_reports where id=%s", (rid,))[0][0]
    out = {}
    for s in secs:
        ov = s.get("overrides") or {}
        d = out.setdefault(s["source_id"], {"analysis": {}, "images": {}})
        d["analysis"].update(ov.get("analysis") or {})
        d["images"].update(ov.get("images") or {})
    return out


def main():
    rid = sql("select id from integrated_reports where name='ZZTEST-R1 integrado'")[0][0]
    carga = sql("select id from test_executions where name='ZZTEST-R1 carga'")[0][0]
    att = sql("select id from execution_attachments where execution_id=%s order by sort_order", (carga,))[0][0]
    uid, uname, role = sql("select id, username, role from users where username='admin'")[0]
    tok = create_access_token({"sub": str(uid), "username": uname, "role": role}, timedelta(minutes=60))
    csrf = uuid.uuid4().hex
    rid, carga, att = str(rid), str(carga), str(att)
    tx_label = sql("select label from transaction_chart_analyses where execution_id=%s order by label limit 1",
                   (carga,))[0][0]
    clave_tx = f"tx|{tx_label}|summary"
    print(f"integrado {rid} · carga {carga} · captura {att} · transaccion '{tx_label}'")

    threading.Thread(target=_rele, daemon=True).start()
    time.sleep(0.5)

    url = f"{WEB}/performance/integrated/{rid}"
    marcas = []

    with sync_playwright() as p:
        # Todo lo que la pantalla pide al 8001 va al 8002 EN LA RESOLUCION DEL
        # PROPIO CHROMIUM, no interceptando con page.route(). La interceptacion
        # muere con el documento: con ella, el envio de «salir» se perdia al
        # descargar o cerrar la pestaña, y la prueba no distinguia un fallo del
        # producto de uno suyo. Comprobado con una sonda: llega al 8002, no al 8001.
        b = p.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO_TEST}"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1000})
        ctx.add_cookies([{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
                         {"name": "csrf_token", "value": csrf, "domain": "localhost", "path": "/"}])
        # Solo el caso 5 intercepta —y solo mientras dura—, para SIMULAR que el
        # servidor falla.
        RUTA_PATCH = "http://localhost:8001/**/integrated-reports/**"

        def fallar_patch(route, req):
            if req.method == "PATCH":
                return route.fulfill(status=500, body="fallo simulado R1")
            route.continue_()

        def abrir():
            pg = ctx.new_page()
            pg.goto(url, wait_until="networkidle", timeout=120000)
            # la caja por transaccion es lo ultimo en aparecer
            pg.get_by_text("Se guarda con el informe integrado").first.wait_for(timeout=120000)
            return pg

        def indices(pg):
            return pg.evaluate("""([att]) => {
              const tas = [...document.querySelectorAll('textarea')];
              const tx = tas.findIndex(t => (t.nextElementSibling?.textContent || '')
                                              .includes('Se guarda con el informe integrado'));
              const img = tas.findIndex(t => t.value.includes('ZZTEST analisis original de la captura 1'));
              return {gen: 0, tx, img, n: tas.length};
            }""", [att])

        def escribir(pg, idx, texto):
            ta = pg.locator("textarea").nth(idx)
            ta.scroll_into_view_if_needed()
            ta.click()
            pg.keyboard.press("Control+End")
            pg.keyboard.type(texto)

        def editar_tres(pg, m):
            ix = indices(pg)
            comprobar(ix["tx"] >= 0 and ix["img"] >= 0, f"[{m}] las tres cajas estan en pantalla ({ix})")
            escribir(pg, ix["gen"], f" {m}-gen")
            escribir(pg, ix["tx"], f" {m}-tx")
            escribir(pg, ix["img"], f" {m}-img")   # el foco se QUEDA aqui: nadie hace blur

        def comprobar_base(m):
            time.sleep(3)
            ov = overrides_guardados(rid).get(carga, {"analysis": {}, "images": {}})
            comprobar(f"{m}-gen" in (ov["analysis"].get("ai_analysis_summary") or ""),
                      f"[{m}] la caja general esta en la base")
            comprobar(f"{m}-tx" in (ov["analysis"].get(clave_tx) or ""),
                      f"[{m}] la caja por transaccion esta en la base")
            comprobar(f"{m}-img" in (ov["images"].get(att) or ""),
                      f"[{m}] la caja de captura esta en la base")

        def marca(nombre):
            m = f"ZZR1{nombre}" + "".join(random.choices(string.ascii_uppercase, k=4))
            marcas.append(m)
            return m

        # ── 1. salir por el MENU de inmediato ──
        m = marca("MENU")
        pg = abrir()
        editar_tres(pg, m)
        estado = pg.get_by_test_id("estado-guardado").inner_text()
        # Con el retardo de la primera caja corriendo puede decir «Guardando...»;
        # lo que no puede decir con la ultima caja sin enviar es «Guardado».
        comprobar(estado in ("Cambios sin guardar", "Guardando..."),
                  f"[{m}] con cambios, el indicador dice «{estado}» (nunca «Guardado»)")
        pg.locator("a[href='/performance/integrated/history']").first.click()
        comprobar_base(m)
        pg.close()

        # ── 2. F5 con el cursor dentro de la caja ──
        m = marca("F5")
        pg = abrir()
        editar_tres(pg, m)
        pg.reload(wait_until="domcontentloaded")
        comprobar_base(m)
        pg.close()

        # ── 3a. DESCARGAR el documento (lo que hace el navegador al cerrar una
        #        pestaña: beforeunload + unload), con la pagina de Playwright viva
        #        para que el desvio 8001->8002 pueda atender el envio ──
        m = marca("DESCARGA")
        pg = abrir()
        editar_tres(pg, m)
        pg.goto("about:blank")
        comprobar_base(m)
        pg.close()

        # ── 3b. CERRAR la pestaña de verdad. El desvio de Playwright muere con la
        #        pagina, asi que aqui lo que se prueba es la RED DE SEGURIDAD: si
        #        el envio no llego, al volver se ofrece recuperarlo ──
        m = marca("CIERRE")
        pg = abrir()
        editar_tres(pg, m)
        pg.close(run_before_unload=True)
        time.sleep(3)
        ov = overrides_guardados(rid).get(carga, {"analysis": {}, "images": {}})
        llego = f"{m}-img" in (ov["images"].get(att) or "")
        print(f"INFO  | [{m}] cierre real: el envio {'LLEGO' if llego else 'NO llego'} a la base")
        pg = ctx.new_page()
        pg.goto(url, wait_until="networkidle", timeout=120000)
        pg.wait_for_timeout(3000)
        rec = pg.get_by_test_id("aviso-recuperar")
        if llego:
            comprobar(rec.count() == 0, f"[{m}] llego: al volver NO se ofrece recuperar (copia descartada sola)")
        else:
            comprobar(rec.count() == 1, f"[{m}] no llego: al volver se ofrece recuperarlo")
            rec.get_by_role("button", name="Recuperar y guardar").click()
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(3000)
        comprobar_base(m)
        pg.close()

        # ── 4. el indicador solo dice «Guardado» tras el servidor ──
        m = marca("IND")
        pg = abrir()
        escribir(pg, 0, f" {m}-gen")
        pg.locator("h1").first.click()     # blur: arranca el retardo de 1,8 s
        comprobar(pg.get_by_test_id("estado-guardado").inner_text() == "Cambios sin guardar",
                  f"[{m}] antes de que responda el servidor no dice «Guardado»")
        pg.wait_for_timeout(4000)
        estado = pg.get_by_test_id("estado-guardado").inner_text()
        comprobar(estado.startswith("Guardado"), f"[{m}] tras el PATCH dice «{estado}»")
        pg.close()

        # ── 5. el guardado FALLA: aviso visible, y al volver se recupera ──
        m = marca("FALLO")
        ctx.route(RUTA_PATCH, fallar_patch)
        pg = abrir()
        escribir(pg, 0, f" {m}-gen")
        pg.locator("h1").first.click()
        pg.wait_for_timeout(4000)
        aviso = pg.get_by_test_id("aviso-guardado")
        comprobar(aviso.count() == 1 and aviso.is_visible(), f"[{m}] el fallo sale como aviso visible")
        comprobar(pg.get_by_test_id("estado-guardado").inner_text() == "No se guardó",
                  f"[{m}] el indicador dice «No se guardó»")
        pg.locator("a[href='/performance/integrated/history']").first.click()   # sale, y el envio tambien falla
        pg.wait_for_timeout(2000)
        ov = overrides_guardados(rid).get(carga, {"analysis": {}})
        comprobar(m not in (ov["analysis"].get("ai_analysis_summary") or ""),
                  f"[{m}] (control) con el servidor fallando NO llego a la base")
        ctx.unroute(RUTA_PATCH, fallar_patch)
        pg.goto(url, wait_until="networkidle")
        rec = pg.get_by_test_id("aviso-recuperar")
        rec.wait_for(timeout=60000)
        comprobar(rec.is_visible(), f"[{m}] al volver, la pagina ofrece recuperar lo escrito")
        rec.get_by_role("button", name="Recuperar y guardar").click()
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(3000)
        ov = overrides_guardados(rid).get(carga, {"analysis": {}})
        comprobar(f"{m}-gen" in (ov["analysis"].get("ai_analysis_summary") or ""),
                  f"[{m}] recuperado: esta en la base")
        comprobar(pg.get_by_test_id("aviso-recuperar").count() == 0,
                  f"[{m}] tras recuperar, el aviso desaparece")
        pg.close()
        b.close()

    # ── 6. los exportados ──
    secs = sql("select sections from integrated_reports where id=%s", (rid,))[0][0]
    cuerpo = {"sections": [{k: s[k] for k in ("order", "type", "source_id", "source_name")} for s in secs],
              "unified_conclusions": "", "report_id": rid}
    ck = {"access_token": tok, "csrf_token": csrf}
    with httpx.Client(cookies=ck, headers={"X-CSRF-Token": csrf}, timeout=600) as cli:
        html = cli.post(f"{API_TEST}/reports/integrated/export-html", json=cuerpo)
        comprobar(html.status_code == 200, f"export HTML {html.status_code}")
        pdf = cli.post(f"{API_TEST}/reports/integrated/export-pdf", json=cuerpo)
        comprobar(pdf.status_code == 200, f"export PDF {pdf.status_code}")
    texto = html.content.decode("utf-8", "replace")
    for m in marcas:
        if "IND" in m:
            partes = ["gen"]
        elif "FALLO" in m:
            partes = ["gen"]
        else:
            partes = ["gen", "tx", "img"]
        for parte in partes:
            comprobar(f"{m}-{parte}" in texto, f"HTML exportado lleva {m}-{parte}")
    open("/tmp/r1_integrado.pdf", "wb").write(pdf.content)
    open("/tmp/r1_marcas.json", "w").write(json.dumps(marcas))
    print(f"PDF en /tmp/r1_integrado.pdf ({len(pdf.content)} bytes) · marcas en /tmp/r1_marcas.json")

    print(f"\n{'TODO PASA' if not fallos else f'{len(fallos)} FALLO(S)'}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
