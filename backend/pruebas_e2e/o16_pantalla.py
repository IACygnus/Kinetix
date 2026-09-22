"""ETAPA O1.6 — Monitoreo en vivo, de punta a punta.

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/o16_pantalla.py

Hace el recorrido entero, el mismo del guion de Fredy:

  1. La entrada «Monitoreo en vivo» está en el menú.
  2. Se elige cliente y proyecto y la pantalla genera la configuración.
  3. El nombre de la corrida cumple O-D4 y el token viene tapado hasta pedirlo.
  4. Se copian de la pantalla la URL, el token y el nombre de la corrida, y con
     ESOS MISMOS valores se lanza un JMeter de verdad.
  5. Los puntos aparecen en InfluxDB bajo esa corrida y solo bajo ésa.
  6. El tablero embebido está filtrado por ella.

H-D76 y regla 34: contra la base de pruebas (el navegador desvía al 8002). La
corrida va marcada `zztest-` (regla 29) y al terminar se borran sus puntos de
InfluxDB, solo los suyos. 0 llamadas a la IA.
"""
import json
import os
import re
import subprocess
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
PUERTO_API = os.environ.get("KX_API_PUERTO", "8002")

# La infraestructura de monitoreo es una sola: el InfluxDB y el Grafana de
# siempre. Lo que cambia es que la corrida va marcada.
INFLUX_INTERNO = "http://influxdb:8086"
OPERADOR = os.environ.get("KX_INFLUX_TOKEN", "jmeter-token-2024-super-secret")
PROYECTO = "ZZTEST Corrida O1.6"

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


def flux(consulta):
    """Una consulta a InfluxDB con el token de operador, para comprobar."""
    r = httpx.post(f"{INFLUX_INTERNO}/api/v2/query", params={"org": "performance"},
                   headers={"Authorization": f"Token {OPERADOR}",
                            "Content-Type": "application/vnd.flux",
                            "Accept": "application/csv"},
                   content=consulta, timeout=60)
    r.raise_for_status()
    return [ln for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")]


def limpiar(application):
    """Borra de InfluxDB SOLO los puntos de esta corrida (reglas 29 y 30)."""
    if not application or not application.startswith("zztest-"):
        return
    httpx.post(f"{INFLUX_INTERNO}/api/v2/delete",
               params={"org": "performance", "bucket": "jmeter"},
               headers={"Authorization": f"Token {OPERADOR}"},
               json={"start": "2020-01-01T00:00:00Z", "stop": "2030-01-01T00:00:00Z",
                     "predicate": f'application="{application}"'}, timeout=60)


def preparar_configuracion(cli):
    """La base de pruebas apunta al mismo InfluxDB y al mismo Grafana."""
    r = cli.put(f"{API}/monitoring/config", json={
        "grafana_url": "http://grafana:3000",
        "grafana_dashboard_uid": "jmeter-performance",
        "influxdb_url": INFLUX_INTERNO,
        "influxdb_org": "performance",
        "influxdb_bucket": "jmeter",
        "influxdb_token": os.environ["KX_TOKEN_ESCRITURA"],
    })
    if r.status_code != 200:
        sys.exit(f"no se pudo preparar la configuracion de monitoreo: {r.status_code} {r.text[:200]}")


def main():
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")
    preparar_configuracion(cli)

    # Los dos relés: el 5173 para la pantalla y el 3000 para el tablero embebido.
    for rele in ("rele_5173.py", "rele_3000.py"):
        subprocess.Popen(["python3", f"/tmp/e2e/{rele}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    application = ""
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1500},
                              storage_state=SESION, locale="es-CO")
        page = ctx.new_page()
        desviar_al_backend_de_pruebas(page)
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))

        # ---------- 1. El menú ----------
        print("--- 1. La entrada del menú ---")
        page.goto(f"{WEB}/dashboard", wait_until="networkidle")
        page.wait_for_timeout(1200)
        analisis = page.get_by_text("Análisis", exact=True)
        if analisis.count():
            analisis.first.click()
            page.wait_for_timeout(700)
        enlace = page.get_by_role("link", name="Monitoreo en vivo")
        ok(enlace.count() >= 1, "«Monitoreo en vivo» está en el menú")

        # ---------- 2. Generar la configuración ----------
        print("\n--- 2. Elegir cliente y proyecto (O-D5) ---")
        page.goto(f"{WEB}/monitoring/vivo", wait_until="networkidle")
        page.wait_for_selector("[data-testid='mon-cliente']", timeout=25000)
        ok(page.locator("[data-testid='mon-sin-corrida']").count() == 1,
           "sin elegir nada, la pantalla lo dice con palabras")
        ok(page.locator("[data-testid='mon-generar']").is_disabled(),
           "y el botón de generar está apagado")

        opciones = page.locator("[data-testid='mon-cliente'] option")
        nombres = [opciones.nth(i).inner_text() for i in range(opciones.count())]
        zz = [n for n in nombres if n.startswith("ZZTEST-")]
        ok(bool(zz), f"el desplegable trae los clientes ({len(nombres) - 1})")
        page.locator("[data-testid='mon-cliente']").select_option(label=zz[0])
        page.wait_for_timeout(900)
        page.locator("[data-testid='mon-proyecto']").fill(PROYECTO)
        page.wait_for_timeout(400)
        ok(not page.locator("[data-testid='mon-generar']").is_disabled(),
           "con cliente y proyecto, se enciende")
        page.locator("[data-testid='mon-generar']").click()
        page.wait_for_selector("[data-testid='mon-application']", timeout=25000)

        # ---------- 3. El nombre de la corrida (O-D4) ----------
        print("\n--- 3. El nombre de la corrida (O-D4) ---")
        application = page.locator("[data-testid='mon-application']").inner_text().strip()
        print(f"    {application}")
        ok(re.fullmatch(r"[a-z0-9-]+-\d{8}-\d{4}", application),
           "minúsculas, sin tildes ni espacios, y termina en aaaammdd-hhmm")
        ok(application.startswith("zztest-"), "lleva la marca de prueba (regla 29)")
        ok("zztest-corrida-o1-6" in application, "y el proyecto sale dentro del nombre")
        ok(page.locator("[data-testid='mon-aviso']").count() == 0,
           "no hay aviso: el token es utilizable")

        # ---------- 4. Los parámetros ----------
        print("\n--- 4. Los diez parámetros, listos para copiar ---")
        filas = page.locator("[data-testid='mon-parametro']")
        puestos = [filas.nth(i).get_attribute("data-nombre") for i in range(filas.count())]
        esperados = ["influxdbMetricsSender", "influxdbUrl", "influxdbToken", "application",
                     "measurement", "summaryOnly", "samplersRegex", "percentiles",
                     "testTitle", "eventTags"]
        ok(puestos == esperados, f"están los diez y en su orden ({len(puestos)})")

        def valor(nombre):
            return page.locator(
                f"[data-testid='mon-parametro'][data-nombre='{nombre}'] [data-testid='mon-valor']"
            ).inner_text().strip()

        ok(set(valor("influxdbToken")) == {"•"}, "el token sale tapado")
        page.locator("[data-testid='mon-ver-token']").click()
        page.wait_for_timeout(500)
        token_pantalla = valor("influxdbToken")
        ok(len(token_pantalla) > 40 and "•" not in token_pantalla,
           "y se destapa al pedirlo")
        ok(valor("application") == application,
           "el parámetro «application» es el mismo nombre de arriba")
        ok(valor("measurement") == "jmeter", "la medida es «jmeter», la que busca el tablero")
        ok(valor("summaryOnly") == "false", "«summaryOnly» en false, para ver cada transacción")

        url_pantalla = valor("influxdbUrl")
        print(f"    influxdbUrl = {url_pantalla}")
        ok("/api/v2/write" in url_pantalla and "org=performance" in url_pantalla
           and "bucket=jmeter" in url_pantalla,
           "la URL lleva la ruta de escritura, la organización y el cubo")

        ok(page.locator("[data-testid='mon-descargar-jmx']").count() == 1,
           "hay descarga del componente .jmx")

        # ---------- 5. El tablero, filtrado (O-D6) ----------
        print("\n--- 5. El tablero mira esta corrida y no otra (O-D6) ---")
        src = page.locator("[data-testid='mon-tablero']").get_attribute("src")
        ok(f"var-application={application}" in src,
           "el tablero embebido filtra por esta corrida")
        ok("/d/jmeter-performance" in src, "y apunta al tablero que existe")

        # ---------- 6. Lanzar JMeter con esos mismos valores ----------
        print("\n--- 6. Lanzar un JMeter con lo que dice la pantalla ---")
        limpiar(application)
        # El JMeter de la prueba corre DENTRO del contenedor, donde InfluxDB se
        # llama por su nombre de servicio; la pantalla da la URL de fuera.
        url_para_dentro = url_pantalla.replace("localhost:8086", "influxdb:8086")
        salida = subprocess.run(
            ["/opt/apache-jmeter-5.6.3/bin/jmeter", "-n", "-t", "/tmp/zztest_o14.jmx",
             "-l", "/tmp/zztest_o16.jtl",
             f"-JinfluxdbUrl={url_para_dentro}",
             f"-JinfluxdbToken={token_pantalla}",
             f"-Japplication={application}"],
            capture_output=True, text=True, timeout=180, cwd="/tmp")
        resumen = [l for l in salida.stdout.splitlines() if l.startswith("summary =")]
        print(f"    {resumen[-1] if resumen else salida.stdout[-200:]}")
        ok(bool(resumen) and "Err:     0" in resumen[-1], "la prueba corrió sin errores")
        log = open("/tmp/jmeter.log", encoding="utf-8", errors="ignore").read() \
            if os.path.exists("/tmp/jmeter.log") else ""
        ok("Error writing metrics to influxDB" not in log,
           "y el Backend Listener no se quejó al escribir")

        # ---------- 7. Los puntos están, y bajo esa corrida ----------
        print("\n--- 7. Los puntos llegaron a InfluxDB ---")
        time.sleep(3)
        filas_datos = flux(
            f'from(bucket:"jmeter") |> range(start:-1h)'
            f' |> filter(fn:(r) => r["_measurement"]=="jmeter")'
            f' |> filter(fn:(r) => r["application"]=="{application}")'
            f' |> filter(fn:(r) => r["_field"]=="avg")'
            f' |> filter(fn:(r) => r["statut"]=="all")')
        ok(len(filas_datos) > 1, f"la consulta del tablero devuelve datos ({len(filas_datos) - 1} filas)")

        transacciones = flux(
            f'import "influxdata/influxdb/schema"'
            f' schema.tagValues(bucket:"jmeter", tag:"transaction", start:-1h,'
            f' predicate: (r) => r["application"]=="{application}")')
        texto_tx = "\n".join(transacciones)
        ok("ZZTEST salud" in texto_tx,
           "y se ve la transacción por su nombre, no solo el total")

        otras = flux(
            f'import "influxdata/influxdb/schema"'
            f' schema.tagValues(bucket:"jmeter", tag:"application", start:-1h)')
        ok(all(("zztest-" in l or "," not in l or "_value" in l) for l in otras),
           "en el cubo no hay más corridas que las marcadas de prueba")

        # ---------- 8. Consola ----------
        print("\n--- 8. Consola ---")
        ok(not errores, f"cero errores de JavaScript ({errores[:2]})")

        os.makedirs("/tmp/e2e_salida", exist_ok=True)
        page.screenshot(path="/tmp/e2e_salida/o16_monitoreo.png", full_page=True)
        ctx.close()
        nav.close()

    limpiar(application)
    print("\n    puntos de prueba borrados de InfluxDB")
    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("O1.6 — MONITOREO EN VIVO, DE PUNTA A PUNTA: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
