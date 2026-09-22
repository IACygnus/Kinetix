"""ETAPA O2c — el menu y la pantalla de servidores, de punta a punta.

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/o2c_pantalla.py

Hace el recorrido entero, el mismo que haria Fredy:

  A. El menu: «Observabilidad» es una seccion propia con sus dos entradas,
     Analisis conserva las suyas, y una ruta antigua redirige a la nueva (O-D29
     a O-D31).
  B. La pantalla: alta de los dos servidores del laboratorio, edicion, prueba de
     conexion y generador de configuracion (O-D24, O-D25, O-D26).
  E. Y lo que importa: las metricas de esos servidores llegan bajo la corrida.

Regla 34 y H-D76: contra `jmeter_analyzer_test` por el 8002 (el navegador desvia
las llamadas). Regla 29: todo marcado ZZTEST-. 0 llamadas a la IA.
"""
import json
import os
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
CLAVE_PG = os.environ.get("LAB_PG_LECTOR_PASSWORD", "")
LLAVE_SSH = os.environ.get("KX_LLAVE_SSH", "")

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def desviar(page):
    """Las llamadas que la pantalla hace al 8001 van al backend de PRUEBAS."""
    if PUERTO_API == "8001":
        return
    page.route("http://localhost:8001/**", lambda ruta: ruta.continue_(
        url=ruta.request.url.replace("localhost:8001", f"localhost:{PUERTO_API}")))


def main():
    if not CLAVE_PG or not LLAVE_SSH:
        sys.exit("faltan LAB_PG_LECTOR_PASSWORD o KX_LLAVE_SSH en el entorno")

    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck,
                       headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=90.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    # El cliente y la limpieza de lo de antes (solo lo de ESTE cliente ZZTEST).
    clientes = cli.get(f"{API}/clients").json()
    fila = next((c for c in clientes if c["name"] == CLIENTE), None)
    if fila is None:
        fila = cli.post(f"{API}/clients", json={
            "name": CLIENTE, "description": "Cliente de prueba de O2c."}).json()
    client_id = fila["id"]
    for viejo in cli.get(f"{API}/observabilidad/servidores",
                         params={"client_id": client_id}).json():
        cli.delete(f"{API}/observabilidad/servidores/{viejo['id']}")

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        ctx = navegador.new_context(storage_state=SESION, viewport={"width": 1500, "height": 1000})
        page = ctx.new_page()
        desviar(page)

        # ---------- A. El menu (O-D29 a O-D31) ----------
        print("\n--- A. El menu ---")
        page.goto(f"{WEB}/dashboard", wait_until="networkidle")
        page.wait_for_timeout(1200)

        menu = page.locator("aside, nav").first
        texto_menu = menu.inner_text()
        ok("Observabilidad" in texto_menu,
           "«Observabilidad» es una seccion del menu")
        ok("Análisis" in texto_menu, "y Analisis sigue estando")

        page.get_by_text("Observabilidad", exact=True).first.click()
        page.wait_for_timeout(600)
        abierto = menu.inner_text()
        ok("Monitoreo en vivo" in abierto,
           "Observabilidad contiene «Monitoreo en vivo»")
        ok("Servidores" in abierto, "y «Servidores»")

        page.get_by_text("Análisis", exact=True).first.click()
        page.wait_for_timeout(600)
        analisis = menu.inner_text()
        for entrada in ("Nuevo Reporte", "Historial Reporte", "Metricas Monitoreo",
                        "Evidencias", "Informe Integrado"):
            ok(entrada in analisis, f"Analisis conserva «{entrada}»")
        ok(analisis.count("Monitoreo en vivo") <= 1,
           "«Monitoreo en vivo» ya no esta duplicado en Analisis")

        # O-D31: la ruta antigua sigue valiendo.
        page.goto(f"{WEB}/monitoring/vivo", wait_until="networkidle")
        page.wait_for_timeout(1500)
        ok(page.url.endswith("/observabilidad/vivo"),
           f"la ruta antigua redirige a la nueva ({page.url.split('//')[-1]})")

        # ---------- B. La pantalla ----------
        print("\n--- B. La pantalla de servidores ---")
        page.goto(f"{WEB}/observabilidad/servidores", wait_until="networkidle")
        page.wait_for_timeout(1500)
        ok(page.locator("[data-testid='srv-nuevo']").count() == 1,
           "la pantalla carga y tiene «Anadir servidor»")

        def alta(nombre, tipo, direccion, puerto, usuario, credencial, notas=""):
            page.locator("[data-testid='srv-nuevo']").click()
            page.wait_for_timeout(500)
            page.locator("[data-testid='srv-f-cliente']").select_option(label=CLIENTE)
            page.locator("[data-testid='srv-f-nombre']").fill(nombre)
            page.locator("[data-testid='srv-f-tipo']").select_option(tipo)
            page.locator("[data-testid='srv-f-direccion']").fill(direccion)
            page.locator("[data-testid='srv-f-puerto']").fill(str(puerto))
            page.locator("[data-testid='srv-f-usuario']").fill(usuario)
            page.locator("[data-testid='srv-f-credencial']").fill(credencial)
            if notas:
                page.locator("[data-testid='srv-f-notas']").fill(notas)
            page.locator("[data-testid='srv-f-guardar']").click()
            page.wait_for_timeout(2000)

        alta("lab_servidor", "linux", "lab_servidor", 22, "kinetix_lector", LLAVE_SSH)
        ok(page.locator("[data-testid='srv-fila-lab_servidor']").count() == 1,
           "se da de alta el Linux del laboratorio desde la pantalla")

        # El puerto se propone solo al cambiar de tipo.
        page.locator("[data-testid='srv-nuevo']").click()
        page.wait_for_timeout(500)
        page.locator("[data-testid='srv-f-tipo']").select_option("postgresql")
        page.wait_for_timeout(300)
        ok(page.locator("[data-testid='srv-f-puerto']").input_value() == "5432",
           "al elegir PostgreSQL, el puerto se propone solo (5432)")
        page.locator("[data-testid='srv-cerrar']").click()
        page.wait_for_timeout(400)

        alta("lab_db", "postgresql", "lab_db", 5432, "kinetix_lector",
             CLAVE_PG, notas="tienda")
        ok(page.locator("[data-testid='srv-fila-lab_db']").count() == 1,
           "y la base de datos del laboratorio")

        # ---------- O-D26 en la pantalla ----------
        print("\n--- O-D26: la credencial no se ensena ---")
        cuerpo = page.locator("body").inner_text()
        ok(LLAVE_SSH.strip().splitlines()[1] not in cuerpo,
           "la llave SSH no aparece en ninguna parte de la pantalla")
        ok(CLAVE_PG not in cuerpo, "ni la contrasena de la base")
        ok("Credencial guardada" in cuerpo, "pero si dice que la hay")

        page.locator("[data-testid='srv-editar-lab_servidor']").click()
        page.wait_for_timeout(700)
        ok(page.locator("[data-testid='srv-f-credencial']").input_value() == "",
           "al editar, el campo de credencial esta VACIO")
        page.locator("[data-testid='srv-f-notas']").fill("ZZTEST editado")
        page.locator("[data-testid='srv-f-guardar']").click()
        page.wait_for_timeout(2000)
        ok("Credencial guardada" in page.locator(
            "[data-testid='srv-fila-lab_servidor']").inner_text(),
           "y guardar sin tocarla la deja intacta")

        # ---------- O-D24: la prueba de conexion ----------
        print("\n--- O-D24: la prueba de conexion ---")
        for nombre in ("lab_servidor", "lab_db"):
            page.locator(f"[data-testid='srv-probar-{nombre}']").click()
            page.wait_for_selector(f"[data-testid='srv-resultado-{nombre}']", timeout=90000)
            page.wait_for_timeout(500)
            resultado = page.locator(f"[data-testid='srv-resultado-{nombre}']").inner_text()
            print(f"    {nombre}: {resultado.splitlines()[0]}")
            for linea in resultado.splitlines()[1:6]:
                print(f"        {linea[:95]}")
            ok("✓" in resultado, f"{nombre}: la prueba enseña lo que SI se puede leer")

        salud = page.locator("[data-testid='srv-resultado-lab_servidor']").inner_text()
        ok("credencial sirve" in salud,
           "en el Linux, la credencial se comprueba de verdad (O-D32)")
        ok("hace" in salud and "segundos" in salud or "minutos" in salud,
           "y dice cuando llego su ultima metrica (O-D34)")

        base = page.locator("[data-testid='srv-resultado-lab_db']").inner_text()
        ok("pg_stat_database" in base, "en la base, lee pg_stat_database")
        ok("pg_stat_statements" in base, "y pg_stat_statements")

        # ---------- O-D25 y O-D28: el generador ----------
        print("\n--- O-D25: el generador de configuracion ---")
        page.locator("[data-testid='srv-config-lab_servidor']").click()
        page.wait_for_selector("[data-testid='srv-configuracion']", timeout=15000)
        page.wait_for_timeout(600)
        cfg = page.locator("[data-testid='srv-configuracion']").inner_text()
        ok("KX_OBJETIVOS" in cfg, "modo sin agente: da los parametros del recolector")
        ok(page.locator("[data-testid='srv-copiar-KX_OBJETIVOS']").count() == 1,
           "cada parametro tiene su boton de copiar")
        ok("NO la ejecuta" in cfg, "y el aviso de O-D28, bien visible")
        ok(LLAVE_SSH.strip().splitlines()[1] not in cfg,
           "la configuracion generada no lleva la credencial dentro")
        page.locator("[data-testid='srv-config-cerrar']").click()
        page.wait_for_timeout(400)

        # El mismo servidor, en modo agente.
        page.locator("[data-testid='srv-editar-lab_servidor']").click()
        page.wait_for_timeout(700)
        page.locator("[data-testid='srv-f-modo']").select_option("agente")
        page.locator("[data-testid='srv-f-guardar']").click()
        page.wait_for_timeout(2000)
        page.locator("[data-testid='srv-config-lab_servidor']").click()
        page.wait_for_selector("[data-testid='srv-configuracion']", timeout=15000)
        page.wait_for_timeout(600)
        cfg = page.locator("[data-testid='srv-configuracion']").inner_text()
        ok("instalar_agente.sh" in cfg, "modo agente: da la orden de instalacion")
        ok("--token-fichero" in cfg,
           "con --token-fichero, para que el token no quede en la linea de ordenes")
        page.locator("[data-testid='srv-config-cerrar']").click()
        page.wait_for_timeout(400)
        page.locator("[data-testid='srv-editar-lab_servidor']").click()
        page.wait_for_timeout(700)
        page.locator("[data-testid='srv-f-modo']").select_option("sin_agente")
        page.locator("[data-testid='srv-f-guardar']").click()
        page.wait_for_timeout(1500)

        # ---------- E. Los servidores de la corrida (O-D27) ----------
        print("\n--- O-D27: los servidores activos van con la corrida ---")
        de_corrida = cli.get(f"{API}/observabilidad/servidores/de-corrida",
                             params={"client_id": client_id}).json()
        ok(len(de_corrida) == 2,
           f"los dos servidores activos del cliente entran en la corrida: {len(de_corrida)}")
        nombres = {s["name"] for s in de_corrida}
        ok(nombres == {"lab_servidor", "lab_db"}, f"y son los suyos: {sorted(nombres)}")

        # ---------- La baja ----------
        print("\n--- La baja ---")
        page.on("dialog", lambda d: d.accept())
        page.locator("[data-testid='srv-borrar-lab_db']").click()
        page.wait_for_timeout(2000)
        ok(page.locator("[data-testid='srv-fila-lab_db']").count() == 0,
           "se da de baja desde la pantalla")

        ctx.close()
        navegador.close()

    print()
    if fallos:
        print(f"FALLOS: {len(fallos)}")
        for texto in fallos:
            print(f"  - {texto}")
        sys.exit(1)
    print("O2c — EL MENU Y LA PANTALLA DE SERVIDORES: TODO PASA")


if __name__ == "__main__":
    main()
