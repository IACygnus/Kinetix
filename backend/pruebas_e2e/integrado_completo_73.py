"""ETAPA 7.3 — el informe integrado completo, de punta a punta (D57-D61).

    docker exec -e KX_PWD=... jmeter_backend python3 /tmp/e2e/integrado_completo_73.py

0 llamadas a la IA: solo lee informes ya generados y vuelve a exportarlos.
Al terminar DEJA EL TEXTO COMO ESTABA (restaura el original).

  1. La pantalla del integrado muestra, por ejecucion, los mismos bloques que
     Historial Reporte.
  2. Editar un analisis de una transaccion en el integrado -> autosave ->
     recargar -> persiste.
  3. El override esta en integrated_reports.sections y transaction_chart_analyses
     NO cambio; Historial Reporte de esa ejecucion sigue con el texto original.
  4. PDF y HTML del integrado traen los bloques completos y el texto editado.
  5. Se restaura y todo vuelve a su sitio.
"""
import json
import os
import re
import sys

import httpx
from playwright.sync_api import sync_playwright

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
RID = os.environ.get("KX_RID", "8713aad1-5de9-4dcb-b294-360ce8ecaee8")
EJEC = os.environ.get("KX_EID", "20bb2356-410d-465f-8717-c9a025e26e03")
LABEL = "4. Get_Booking_Id"
SECCION = "chart_tps"
MARCA = "[ETAPA 7.3] texto editado dentro del informe integrado."

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def cli():
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    return httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                        timeout=1800.0)


def estable(page, timeout_s=150):
    import time as _t
    ini, prev, desde = _t.monotonic(), None, None
    while _t.monotonic() - ini < timeout_s:
        n = page.locator("svg.recharts-surface").count()
        if n and n == prev:
            if desde is None:
                desde = _t.monotonic()
            elif _t.monotonic() - desde >= 2.5:
                return n
        else:
            desde = None
        prev = n
        page.wait_for_timeout(300)
    return prev or 0


def cuenta(page):
    return {
        "graficas": estable(page),
        "rt": page.get_by_text("Response Times por Transacción", exact=False).count(),
        "resumen": page.get_by_text("Reporte Resumen", exact=False).count(),
    }


def texto_original(c):
    r = c.get(f"{API}/executions/{EJEC}/transaction-report",
              params={"label": LABEL})
    r.raise_for_status()
    for s in r.json().get("sections", []):
        if s.get("section") == SECCION:
            return s.get("ai_analysis") or ""
    return ""


def bloques_tx(h):
    return [x.strip() for x in re.findall(r'font-size:1\.5rem;font-weight:700">([^<]+)</div>', h)]


def main():
    c = cli()
    original = texto_original(c)
    ok(bool(original), f"la seccion '{SECCION}' de '{LABEL}' tiene texto original ({len(original)} chars)")

    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1400},
                              storage_state=SESION, locale="es-CO")
        page = ctx.new_page()

        # ---------- 1. La pantalla muestra lo mismo que el individual ----------
        print("\n--- 1. La pantalla del integrado ya trae los bloques ---")
        page.goto(f"{WEB}/performance/report/{EJEC}", wait_until="networkidle")
        ind = cuenta(page)
        page.goto(f"{WEB}/performance/integrated/{RID}", wait_until="networkidle")
        inte = cuenta(page)
        print(f"    individual: {ind}")
        print(f"    integrado : {inte}")
        # El integrado de prueba tiene DOS ejecuciones: una con 3 transacciones y
        # otra con 0. Los bloques por transaccion son los mismos que en el suelto.
        tx_ind = ind["rt"] - 1                 # menos el general
        tx_inte = inte["rt"] - 2               # menos los dos generales
        ok(tx_inte == tx_ind,
           f"los bloques por transaccion coinciden: {tx_inte} en el integrado, {tx_ind} sueltos")
        ok(inte["graficas"] == inte["graficas"] and inte["graficas"] > ind["graficas"],
           f"el integrado pinta {inte['graficas']} graficas (antes de la etapa: 21)")

        # ---------- 2. Editar dentro del integrado ----------
        print("\n--- 2. Editar un analisis por transaccion en el integrado ---")
        # La caja de esa seccion: se busca por el titulo del bloque y su grafica.
        cajas = page.locator("textarea")
        objetivo = None
        for i in range(cajas.count()):
            if (cajas.nth(i).input_value() or "").strip() == original.strip():
                objetivo = cajas.nth(i)
                break
        if not ok(objetivo is not None, "se localiza la caja de esa seccion en la pantalla"):
            nav.close()
            return 1
        objetivo.fill(MARCA)
        objetivo.blur()
        page.wait_for_timeout(4000)      # autoguardado del integrado

        # ---------- 3. Persistencia y aislamiento ----------
        print("\n--- 3. Donde quedo guardado ---")
        rep = c.get(f"{API}/reports/integrated-reports/{RID}").json()
        clave = f"tx|{LABEL}|{SECCION}"
        guardado = None
        for s in rep.get("sections") or []:
            guardado = ((s.get("overrides") or {}).get("analysis") or {}).get(clave) or guardado
        ok(guardado == MARCA, f"el override '{clave}' esta en integrated_reports.sections")
        ok(texto_original(c) == original,
           "transaction_chart_analyses NO cambio: la ejecucion conserva su texto")

        page.reload(wait_until="networkidle")
        estable(page)
        page.wait_for_timeout(1500)
        vals = [cajas.nth(i).input_value() for i in range(page.locator("textarea").count())]
        ok(any((v or "").strip() == MARCA for v in vals),
           "al recargar el integrado, el texto editado sigue ahi")

        page.goto(f"{WEB}/performance/report/{EJEC}", wait_until="networkidle")
        estable(page)
        page.wait_for_timeout(1000)
        vals_ind = [page.locator("textarea").nth(i).input_value()
                    for i in range(page.locator("textarea").count())]
        ok(not any((v or "").strip() == MARCA for v in vals_ind),
           "Historial Reporte de esa ejecucion NO muestra el texto del integrado")
        ok(any((v or "").strip() == original.strip() for v in vals_ind),
           "y sigue mostrando su texto original")

        # ---------- 4. Los exportados ----------
        print("\n--- 4. PDF y HTML del integrado ---")
        rep = c.get(f"{API}/reports/integrated-reports/{RID}").json()
        payload = {"sections": rep.get("sections") or [], "report_id": RID,
                   "name": rep.get("name") or "Integrado"}
        rh = c.post(f"{API}/reports/integrated/export-html", json=payload)
        h = rh.text if rh.status_code == 200 else ""
        bl = bloques_tx(h)
        ok(rh.status_code == 200, f"export-html {rh.status_code}")
        ok(len(bl) == tx_ind, f"el HTML trae los {tx_ind} bloques por transaccion: {bl}")
        ok(MARCA in h, "y el HTML trae el texto editado en el integrado")
        open("/tmp/integrado73.html", "w", encoding="utf-8").write(h)

        rp = c.post(f"{API}/reports/integrated/export-pdf", json=payload)
        ok(rp.status_code == 200 and rp.content[:4] == b"%PDF",
           f"export-pdf {rp.status_code}, {len(rp.content):,} bytes, PDF valido")

        # ---------- 5. El HTML exportado, en el navegador ----------
        print("\n--- 5. El HTML exportado abre sin errores ---")
        errores = []
        p2 = ctx.new_page()
        p2.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        p2.on("pageerror", lambda e: errores.append(str(e)))
        p2.goto("file:///tmp/integrado73.html", wait_until="networkidle")
        p2.wait_for_timeout(2500)
        ok(not errores, f"cero errores de consola ({errores[:2]})")

        nav.close()

    # ---------- 6. Restaurar ----------
    print("\n--- 6. Restaurar el texto ---")
    rep = c.get(f"{API}/reports/integrated-reports/{RID}").json()
    secciones = rep.get("sections") or []
    for s in secciones:
        an = (s.get("overrides") or {}).get("analysis") or {}
        an.pop(f"tx|{LABEL}|{SECCION}", None)
    r = c.patch(f"{API}/reports/integrated-reports/{RID}",
                json={"sections": secciones})
    ok(r.status_code in (200, 204), f"PATCH de restauracion {r.status_code}")
    rep2 = c.get(f"{API}/reports/integrated-reports/{RID}").json()
    quedan = [k for s in (rep2.get("sections") or [])
              for k in ((s.get("overrides") or {}).get("analysis") or {})
              if k.startswith("tx|")]
    ok(not quedan, f"no queda ningun override por transaccion: {quedan}")
    ok(texto_original(c) == original, "y la ejecucion sigue con su texto original")

    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("7.3 — EL INFORME INTEGRADO COMPLETO: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


sys.exit(main())
