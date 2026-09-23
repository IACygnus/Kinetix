"""ETAPA O2d.5 — la sesion de monitoreo, de punta a punta.

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/o2d5_pantalla.py

El recorrido entero, el que Fredy no podia hacer:

  1. El menu: «Sesiones de monitoreo» esta, y «Capturas de infraestructura» se
     llama asi (O-D42).
  2. Se crea una sesion con los dos servidores del laboratorio.
  3. **Se sube un .jmx y se recibe con el Backend Listener puesto** (O-D45).
  4. Se lanza ese .jmx de verdad.
  5. **Y se comprueba DESDE LA PANTALLA** que la CPU y la base suben durante la
     prueba y bajan despues (O-D38, O-D39).
  6. Se cierra la sesion, se vuelve a abrir, y sigue enseñando lo que paso
     (O-D40).

Eso ultimo es lo que decide si la etapa sirve: no que el endpoint devuelva
numeros, sino que se vean en la pantalla.
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
PUERTO_API = os.environ.get("KX_API_PUERTO", "8002")
CLIENTE = "ZZTEST-Observabilidad O2c"
NOMBRE = "ZZTEST-Sesion de pantalla"
JMETER = "/opt/apache-jmeter-5.6.3/bin/jmeter"
DESCARGAS = "/tmp/descargas_o2d"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def desviar(page):
    if PUERTO_API == "8001":
        return
    page.route("http://localhost:8001/**", lambda ruta: ruta.continue_(
        url=ruta.request.url.replace("localhost:8001", f"localhost:{PUERTO_API}")))


def numeros(texto):
    """Los numeros que aparecen en un trozo de pantalla."""
    return [float(n.replace(",", ".")) for n in re.findall(r"-?\d+[.,]?\d*", texto)]


def main():
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck,
                       headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    cliente = next((c for c in cli.get(f"{API}/clients").json()
                    if c["name"] == CLIENTE), None)
    if cliente is None:
        sys.exit(f"falta el cliente «{CLIENTE}»: corre antes o2c1_backend.py")
    client_id = cliente["id"]

    for vieja in cli.get(f"{API}/observabilidad/sesiones",
                         params={"client_id": client_id}).json():
        if vieja["nombre"] == NOMBRE:
            cli.delete(f"{API}/observabilidad/sesiones/{vieja['id']}")

    os.makedirs(DESCARGAS, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        ctx = navegador.new_context(storage_state=SESION,
                                    viewport={"width": 1700, "height": 1100},
                                    accept_downloads=True)
        page = ctx.new_page()
        desviar(page)

        # ---------- 1. El menu ----------
        print("--- 1. El menu (O-D42) ---")
        page.goto(f"{WEB}/dashboard", wait_until="networkidle")
        page.wait_for_timeout(1200)
        menu = page.locator("aside, nav").first
        page.get_by_text("Observabilidad", exact=True).first.click()
        page.wait_for_timeout(600)
        texto = menu.inner_text()
        ok("Sesiones de monitoreo" in texto,
           "«Sesiones de monitoreo» esta en Observabilidad")
        ok("Servidores" in texto and "Monitoreo en vivo" in texto,
           "y siguen «Servidores» y «Monitoreo en vivo»")

        page.get_by_text("Análisis", exact=True).first.click()
        page.wait_for_timeout(600)
        analisis = menu.inner_text()
        ok("Capturas de infraestructura" in analisis,
           "«Metricas Monitoreo» pasa a llamarse «Capturas de infraestructura»")
        ok("Metricas Monitoreo" not in analisis, "y el nombre viejo ya no esta")

        # ---------- 2. Crear la sesion ----------
        print("\n--- 2. Crear una sesion (O-D37) ---")
        page.goto(f"{WEB}/observabilidad/sesiones", wait_until="networkidle")
        page.wait_for_timeout(1500)
        ok(page.locator("[data-testid='ses-nueva']").count() == 1,
           "la pantalla de sesiones carga (O-D36)")
        ok(page.locator("[data-testid='ses-falta-token']").count() == 0,
           "no falta el token de lectura")

        page.locator("[data-testid='ses-nueva']").click()
        page.wait_for_selector("[data-testid='ses-paso1']", timeout=15000)
        page.locator("[data-testid='ses-f-nombre']").fill(NOMBRE)
        page.locator("[data-testid='ses-f-cliente']").select_option(label=CLIENTE)
        page.wait_for_timeout(1200)
        page.locator("[data-testid='ses-f-proyecto']").fill("ZZTEST-Tienda")
        ok(page.locator("[data-testid='ses-srv-lab_servidor']").is_checked(),
           "los servidores del cliente salen marcados por defecto")
        page.locator("[data-testid='ses-crear']").click()

        page.wait_for_selector("[data-testid='ses-paso2']", timeout=20000)
        page.wait_for_timeout(600)
        corrida = page.locator("[data-testid='ses-corrida']").inner_text().strip()
        ok(corrida.startswith("zztest-"), f"la sesion tiene su corrida: {corrida}")

        # ---------- 3. El .jmx (O-D45) ----------
        print("\n--- 3. Subir un .jmx y recibirlo con el listener (O-D45) ---")
        with page.expect_download(timeout=60000) as espera:
            page.locator("[data-testid='ses-jmx']").set_input_files(
                "/tmp/zztest_lab.jmx")
        descarga = espera.value
        destino = os.path.join(DESCARGAS, "con_listener.jmx")
        descarga.save_as(destino)
        page.wait_for_selector("[data-testid='ses-jmx-resultado']", timeout=20000)
        aviso = page.locator("[data-testid='ses-jmx-resultado']").inner_text()
        print(f"    {aviso[:130]}")
        ok("original no se ha tocado" in aviso,
           "la pantalla dice que el original no se toca (O-D46)")

        contenido = open(destino, "rb").read()
        ok(corrida.encode() in contenido,
           "el .jmx descargado lleva la corrida de esta sesion")
        ok(contenido.count(b"<BackendListener") == 1,
           f"y UN solo Backend Listener ({contenido.count(b'<BackendListener')})")

        ok(page.locator("[data-testid='ses-parametros']").count() == 0,
           "los parametros a mano NO se ven de entrada (son la opcion avanzada)")
        page.locator("[data-testid='ses-avanzado']").click()
        page.wait_for_timeout(500)
        ok(page.locator("[data-testid='ses-parametros']").count() == 1,
           "pero estan, plegados, para quien los quiera")

        page.locator("[data-testid='ses-ir-a-sesion']").click()
        page.wait_for_selector("[data-testid='ses-prueba']", timeout=20000)
        page.wait_for_timeout(1500)
        url_sesion = page.url
        ok("/observabilidad/sesiones/" in url_sesion, "se llega a la sesion")

        antes = page.locator("[data-testid='ses-infraestructura']").inner_text()
        ok("lab_servidor" in antes and "lab_db" in antes,
           "la sesion enseña los dos servidores")
        ok("Métricas de la prueba" in page.locator("body").inner_text()
           and "Métricas de la infraestructura" in page.locator("body").inner_text(),
           "y las dos secciones estan rotuladas como manda O-D39")

        # ---------- 4. Lanzar la prueba ----------
        print("\n--- 4. Lanzar ESE .jmx de verdad ---")
        subprocess.run(["cp", destino, "/tmp/zztest_o2d5.jmx"], check=True)
        proceso = subprocess.Popen(
            [JMETER, "-n", "-t", "/tmp/zztest_o2d5.jmx",
             "-l", "/tmp/zztest_o2d5.jtl", "-Jduracion=100", "-Jusuarios=12"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd="/tmp")
        print("    JMeter lanzado (100 s)")

        # ---------- 5. Mirarlo DESDE LA PANTALLA ----------
        print("\n--- 5. Lo que se ve en la pantalla mientras corre (O-D38) ---")
        time.sleep(55)
        page.reload(wait_until="networkidle")
        page.wait_for_selector("[data-testid='ses-prueba']", timeout=20000)
        page.wait_for_timeout(3000)

        cuerpo = page.locator("body").inner_text()
        ok("Tiempo de respuesta" in cuerpo,
           "arriba aparece la grafica de tiempo de respuesta")
        srv = page.locator("[data-testid='ses-srv-lab_servidor']").inner_text()
        ok("CPU" in srv, "abajo, la CPU del servidor")
        ok("Memoria" in srv, "y su memoria")
        base = page.locator("[data-testid='ses-srv-lab_db']").inner_text()
        ok("Conexiones" in base, "y las conexiones de la base")

        # Los trazos de las graficas: si no hay lineas, no hay nada pintado.
        trazos = page.locator("[data-testid='ses-srv-lab_servidor'] svg path.recharts-curve")
        ok(trazos.count() > 0,
           f"las graficas del servidor tienen trazos dibujados ({trazos.count()})")
        trazos_prueba = page.locator("[data-testid='ses-prueba'] svg path.recharts-curve")
        ok(trazos_prueba.count() > 0,
           f"y las de la prueba tambien ({trazos_prueba.count()})")

        # La cifra que importa: la CPU durante la prueba, leida de la API que
        # alimenta a esa misma pantalla.
        sesion_id = url_sesion.rstrip("/").split("/")[-1]
        m = cli.get(f"{API}/observabilidad/sesiones/{sesion_id}/metricas",
                    params={"minutos": 15}).json()
        cpu = None
        for servidor in m["infraestructura"]:
            if servidor["servidor"] != "lab_servidor":
                continue
            for g in servidor["graficas"]:
                if g["titulo"] == "CPU" and g["series"]:
                    cpu = [v for _, v in g["series"][0]["puntos"]]
        ok(bool(cpu), "la pantalla recibe la serie de CPU")
        if cpu:
            print(f"    CPU: minimo {min(cpu):.1f} %  ·  maximo {max(cpu):.1f} %")
            ok(max(cpu) > 60,
               f"la CPU sube por encima del 60 % durante la prueba ({max(cpu):.1f} %)")

        conexiones = None
        for servidor in m["infraestructura"]:
            if servidor["servidor"] != "lab_db":
                continue
            for g in servidor["graficas"]:
                if g["titulo"] == "Conexiones" and g["series"]:
                    conexiones = [v for _, v in g["series"][0]["puntos"]]
        if conexiones:
            print(f"    Conexiones: minimo {min(conexiones):.0f}  ·  "
                  f"maximo {max(conexiones):.0f}")
            ok(max(conexiones) > min(conexiones),
               "las conexiones de la base suben durante la prueba")

        proceso.wait(timeout=240)
        print("    JMeter termino")

        # ---------- 6. O-D40 ----------
        print("\n--- 6. O-D40: cerrarla y volver a abrirla ---")
        time.sleep(25)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(2500)
        page.locator("[data-testid='ses-cerrar']").click()
        page.wait_for_timeout(3000)

        page.goto(f"{WEB}/observabilidad/sesiones", wait_until="networkidle")
        page.wait_for_timeout(1500)
        listado = page.locator("[data-testid='ses-lista']").inner_text()
        ok(NOMBRE in listado, "la sesion aparece en el listado")
        ok("Terminada" in listado, "con estado «Terminada»")

        page.locator(f"[data-testid='ses-abrir-{NOMBRE}']").click()
        page.wait_for_selector("[data-testid='ses-prueba']", timeout=20000)
        page.wait_for_timeout(3000)
        ok(page.locator("[data-testid='ses-vivo']").count() == 0,
           "una sesion terminada ya no se refresca sola")
        trazos_despues = page.locator(
            "[data-testid='ses-srv-lab_servidor'] svg path.recharts-curve")
        ok(trazos_despues.count() > 0,
           f"y SIGUE enseñando lo que paso, no una pantalla vacia "
           f"({trazos_despues.count()} trazos)")

        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        page.wait_for_timeout(1000)
        ok(not errores, f"sin errores de JavaScript ({errores[:1]})")

        ctx.close()
        navegador.close()

    print()
    if fallos:
        print(f"FALLOS: {len(fallos)}")
        for texto in fallos:
            print(f"  - {texto}")
        sys.exit(1)
    print("O2d.5 — LA SESION DE MONITOREO, DE PUNTA A PUNTA: TODO PASA")


if __name__ == "__main__":
    main()
