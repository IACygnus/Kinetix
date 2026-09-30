"""O2e.4a — los tokens de ingesta en la pantalla de Servidores.

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /app/pruebas_e2e/o2e4a_pantalla.py

Regla 34: la pantalla del 5173 con sus llamadas desviadas del 8001 al 8002, que
corre contra `jmeter_analyzer_test`. Regla 29: el cliente es
«ZZTEST-Tokens O2e4a»; se crea si no existe y no se borra. Los tokens de la
suite quedan REVOCADOS, no borrados (regla 28). La suite no imprime ningún
token: solo sus prefijos.

  (a) el bloque aparece para el cliente; sin cliente, la línea que lo pide; la
      línea de InfluxDB, siempre
  (b) crear → modal con un token kxi_…; Escape y un clic fuera no lo cierran;
      «Copiar» lo deja en el portapapeles
  (c) tras «Ya lo copié» el token no está en el DOM, ni en la consola, ni en el
      almacenamiento del navegador, ni en ninguna respuesta de red salvo el
      POST del alta, ni en el log del backend
  (d) el prefijo de la fila son los 12 primeros caracteres del token
  (e) revocar → confirmación con el texto pedido, la fila dice «revocado el …»,
      los activos van primero, y una escritura con ese token da 401
  (f) como analista: la lista y la línea de InfluxDB, sin «Crear token»,
      «Revocar» ni «Cargar»
  (g) la línea de InfluxDB dice lo que contesta GET /ingesta/token-escritura.
      No se carga ni se reemplaza nada
"""
import json
import os
import sys

import httpx
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analista_de_pruebas  # noqa: E402

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
PUERTO_API = os.environ.get("KX_API_PUERTO", "8002")
LOG = os.environ.get("KX_LOG", "/tmp/backend_test.log")
CLIENTE = "ZZTEST-Tokens O2e4a"
AVISO_REVOCAR = ("Los servidores que usan este token dejan de enviar en el acto. "
                 "No se puede deshacer.")

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


def sesion_admin():
    """La sesión de pruebas, renovada (sliding session, sin gastar login)."""
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=60.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion de pruebas caducada: corre refrescar_sesion.py con KX_API y KX_SESION")
    r = cli.post(f"{API}/auth/refresh")
    if r.status_code == 200:
        ck.update(dict(r.cookies))
        cli.cookies.update(r.cookies)
        cli.headers["X-CSRF-Token"] = ck.get("csrf_token", "")
        json.dump({"cookies": [{"name": k, "value": v, "domain": "localhost", "path": "/",
                                "expires": -1, "httpOnly": False, "secure": False,
                                "sameSite": "Lax"} for k, v in ck.items()],
                   "origins": []}, open(SESION, "w"))
    return cli


def main():
    if "8002" not in API:
        sys.exit(f"PARADA: {API} no es el backend de pruebas")
    cli = sesion_admin()
    log_inicio = os.path.getsize(LOG) if os.path.exists(LOG) else 0

    r = cli.get(f"{API}/clients")
    fila = next((c for c in r.json() if c["name"] == CLIENTE), None)
    if fila is None:
        fila = cli.post(f"{API}/clients", json={
            "name": CLIENTE, "description": "Prueba O2e.4a. Marca ZZTEST."}).json()
    client_id = fila["id"]

    tokens = []          # los de esta corrida; nunca se imprimen enteros
    try:
        correr(cli, client_id, tokens)
    finally:
        # Regla 28: se revocan, no se borran.
        for t in cli.get(f"{API}/ingesta/tokens", params={"client_id": client_id}).json():
            if not t["revocado_en"]:
                cli.post(f"{API}/ingesta/tokens/{t['id']}/revocar")
        vivos = [t for t in cli.get(f"{API}/ingesta/tokens",
                                    params={"client_id": client_id}).json()
                 if not t["revocado_en"]]
        ok(not vivos, "al terminar no queda ningun token activo del cliente de la suite")

    with open(LOG, encoding="utf-8", errors="replace") as f:
        f.seek(log_inicio)
        log = f.read()
    ok(tokens and not any(t in log for t in tokens),
       f"(c) ninguno de los {len(tokens)} tokens aparece en el log del backend")

    print()
    print("RESULTADO:", "TODO BIEN" if not fallos else f"{len(fallos)} FALLOS")
    for f in fallos:
        print("   -", f)
    sys.exit(1 if fallos else 0)


def correr(cli, client_id, tokens):
    estado_escritura = cli.get(f"{API}/ingesta/token-escritura").json()

    with sync_playwright() as p:
        navegador = p.chromium.launch()

        # ================= Como admin =================
        ctx = navegador.new_context(storage_state=SESION, viewport={"width": 1500, "height": 1000})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=WEB)
        page = ctx.new_page()
        desviar(page)
        consola, respuestas, dialogos = [], [], []
        page.on("console", lambda m: consola.append(m.text))
        page.on("response", lambda r: respuestas.append(r))

        def al_dialogo(d):
            dialogos.append(d.message)
            d.accept()
        page.on("dialog", al_dialogo)

        page.goto(f"{WEB}/observabilidad/servidores", wait_until="networkidle")
        page.wait_for_timeout(800)

        print("\n--- (a) y (g) El bloque y la linea de InfluxDB ---")
        ok(page.get_by_test_id("ing-elige-cliente").is_visible(),
           "(a) sin cliente elegido: «Elige un cliente para ver y crear sus tokens de ingesta.»")
        ok(page.get_by_test_id("ing-bloque").count() == 0, "(a) y el bloque de tokens no esta")
        ok(page.get_by_test_id("inf-linea").is_visible(),
           "(a) la linea de InfluxDB se ve sin cliente elegido")
        # La contraprueba de (f): si el admin tampoco lo viera, (f) pasaria igual.
        ok(page.get_by_test_id("inf-cargar").is_visible(),
           "(f, contraprueba) el admin SI ve «Cargar» (no se pulsa: (g) no carga nada)")
        esperado = "sí" if estado_escritura["hay_token"] else "no"
        visto = page.get_by_test_id("inf-estado").inner_text().strip()
        ok(visto == esperado,
           f"(g) «Token de escritura cargado: {visto}» y GET /ingesta/token-escritura dice "
           f"hay_token={estado_escritura['hay_token']}")

        page.get_by_test_id("srv-filtro-cliente").select_option(client_id)
        page.wait_for_timeout(800)
        bloque = page.get_by_test_id("ing-bloque")
        ok(bloque.is_visible() and CLIENTE in bloque.inner_text(),
           "(a) con el cliente elegido aparece el bloque «Token de ingesta» con su nombre")
        ok(page.get_by_test_id("ing-crear").is_visible(),
           "(f, contraprueba) el admin SI ve «Crear token»")
        ok(page.get_by_test_id("inf-linea").is_visible(),
           "(a) y la linea de InfluxDB sigue ahi, fuera del bloque")
        ok(page.get_by_test_id("ing-bloque").get_by_test_id("inf-linea").count() == 0,
           "(a) la linea de InfluxDB no esta dentro del bloque de tokens")

        print("\n--- (b) Crear ---")
        creados = []
        for _ in range(2):   # dos: para ver el orden activos/revocados en (e)
            with page.expect_response(lambda r: r.url.endswith("/ingesta/tokens")
                                      and r.request.method == "POST") as info:
                page.get_by_test_id("ing-crear").click()
            alta = info.value.json()
            creados.append(alta)
            tokens.append(alta["token"])
            modal = page.get_by_test_id("ing-modal")
            modal.wait_for(state="visible")
            en_pantalla = page.get_by_test_id("ing-token").inner_text().strip()
            ok(en_pantalla == alta["token"] and en_pantalla.startswith("kxi_"),
               f"(b) el modal muestra el token {alta['prefijo']}… que devolvio el alta")
            ok(page.get_by_test_id("ing-aviso").inner_text().strip() == alta["aviso"],
               "(b) con el aviso que devuelve el backend")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            ok(modal.is_visible(), "(b) Escape no cierra el modal")
            page.mouse.click(8, 8)
            page.wait_for_timeout(300)
            ok(modal.is_visible(), "(b) un clic fuera no lo cierra")
            page.get_by_test_id("ing-copiar").click()
            page.wait_for_timeout(300)
            portapapeles = page.evaluate("navigator.clipboard.readText()")
            ok(portapapeles == alta["token"], "(b) «Copiar» lo deja en el portapapeles")
            page.get_by_test_id("ing-ya-copie").click()
            page.wait_for_timeout(500)
            ok(modal.count() == 0, "(b) «Ya lo copié» cierra el modal")
            # El portapapeles se vacia: lo que se mira en (c) es la pagina.
            page.evaluate("navigator.clipboard.writeText('')")

        print("\n--- (c) El token ya no esta en ningun sitio ---")
        page.wait_for_timeout(800)
        html = page.content()
        texto = page.evaluate("document.body.innerText")
        valores = page.evaluate(
            "Array.from(document.querySelectorAll('input,textarea')).map(e => e.value).join('\\n')")
        almacen = page.evaluate(
            "JSON.stringify({l: {...localStorage}, s: {...sessionStorage}})")
        for t in tokens:
            p12 = t[:12]
            ok(t not in html and t not in texto and t not in valores,
               f"(c) {p12}…: no esta en el DOM (HTML, texto ni campos)")
            ok(not any(t in m for m in consola), f"(c) {p12}…: no esta en la consola del navegador")
            ok(t not in almacen, f"(c) {p12}…: no esta en localStorage ni sessionStorage")
        cuerpos, leidas = [], 0
        for r in respuestas:
            if r.request.method == "POST" and r.url.endswith("/ingesta/tokens"):
                continue
            try:
                cuerpos.append(r.text())
                leidas += 1
            except Exception:   # noqa: BLE001 — redirecciones, sin cuerpo
                pass
        ok(leidas > 0 and not any(t in c for c in cuerpos for t in tokens),
           f"(c) ninguna de las otras {leidas} respuestas de red lleva un token")

        print("\n--- (d) El prefijo de la lista ---")
        for alta in creados:
            p12 = alta["token"][:12]
            fila = page.get_by_test_id(f"ing-fila-{p12}")
            ok(fila.count() == 1, f"(d) hay una fila {p12}…")
            if fila.count():
                pref = fila.get_by_test_id("ing-prefijo")
                clase = pref.get_attribute("class") or ""
                ok(pref.inner_text().strip() == f"{p12}…" and alta["prefijo"] == p12,
                   "(d) el prefijo de la fila son los 12 primeros caracteres del token")
                ok("font-mono" in clase and "text-gray" in clase, "(d) en gris y monoespaciado")
                ok("activo" == fila.get_by_test_id("ing-estado").inner_text().strip(),
                   "(d) y su estado es «activo»")
                ok("nunca" in fila.inner_text(), "(d) último uso: «nunca»")

        print("\n--- (e) Revocar ---")
        primero, segundo = creados
        p12 = primero["token"][:12]
        page.get_by_test_id(f"ing-revocar-{p12}").click()
        page.wait_for_timeout(1000)
        ok(dialogos and AVISO_REVOCAR in dialogos[-1],
           f"(e) pide confirmacion con el texto pedido: «{(dialogos or [''])[-1][-90:]}»")
        estado = page.get_by_test_id(f"ing-fila-{p12}").get_by_test_id("ing-estado").inner_text()
        ok(estado.startswith("revocado el "), f"(e) la fila dice «{estado.strip()}»")
        ok(page.get_by_test_id(f"ing-revocar-{p12}").count() == 0,
           "(e) y ya no tiene botón «Revocar»")
        orden = page.locator("[data-testid^='ing-fila-']").evaluate_all(
            "fs => fs.map(f => f.getAttribute('data-testid'))")
        pos = {v: i for i, v in enumerate(orden)}
        ok(pos.get(f"ing-fila-{segundo['token'][:12]}", 99) < pos.get(f"ing-fila-{p12}", -1),
           "(e) el activo va antes que el revocado")
        estados = [e.strip() for e in page.get_by_test_id("ing-estado").all_inner_texts()]
        ok(estados == sorted(estados, key=lambda e: e != "activo"),
           f"(e) todos los activos primero: {[e[:8] for e in estados]}")
        w = httpx.post(f"{API}/ingesta/api/v2/write", params={"bucket": "infra"},
                       headers={"Authorization": f"Token {primero['token']}"},
                       content="zztest_o2e4a,cliente=ZZTEST-Tokens\\ O2e4a valor=1i\n")
        ok(w.status_code == 401 and "revoco" in w.text,
           f"(e) una escritura con el token revocado da {w.status_code}")

        ctx.close()

        # ================= Como analista =================
        print("\n--- (f) Como analista ---")
        analista = analista_de_pruebas.obtener(cli, API)
        if not ok(analista is not None, "(f) hay sesion de analista"):
            navegador.close()
            return
        ctx = navegador.new_context(viewport={"width": 1500, "height": 1000})
        ctx.add_cookies([{"name": k, "value": v, "domain": "localhost", "path": "/"}
                         for k, v in analista.cookies.items()])
        page = ctx.new_page()
        desviar(page)
        page.goto(f"{WEB}/observabilidad/servidores", wait_until="networkidle")
        page.wait_for_timeout(800)
        ok(page.get_by_test_id("inf-linea").is_visible(), "(f) ve la linea de InfluxDB")
        ok(page.get_by_test_id("inf-estado").inner_text().strip() == esperado,
           "(f) con el mismo estado que ve el admin")
        page.get_by_test_id("srv-filtro-cliente").select_option(client_id)
        page.wait_for_timeout(800)
        ok(page.get_by_test_id("ing-bloque").is_visible()
           and page.locator("[data-testid^='ing-fila-']").count() >= 2,
           "(f) ve el bloque y la lista de tokens")
        ok(page.get_by_test_id("ing-crear").count() == 0, "(f) no existe «Crear token»")
        ok(page.locator("[data-testid^='ing-revocar-']").count() == 0
           and page.get_by_role("button", name="Revocar").count() == 0,
           "(f) no existe «Revocar»")
        ok(page.get_by_test_id("inf-cargar").count() == 0
           and page.get_by_role("button", name="Cargar").count() == 0,
           "(f) no existe «Cargar»")
        ctx.close()
        navegador.close()

    ok(cli.get(f"{API}/ingesta/token-escritura").json() == estado_escritura,
       "(g) el token de escritura de la base de pruebas no ha cambiado")


if __name__ == "__main__":
    main()
