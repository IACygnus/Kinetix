"""BLOQUE 5 — la pantalla «Analista IA», en el navegador (reporte 148).

    docker exec jmeter_backend sh /app/pruebas_e2e/reiniciar_8002.sh --ia-falsa
    docker exec jmeter_backend python3 /app/pruebas_e2e/b5_pantalla.py
    docker cp jmeter_backend:/tmp/b5_pantalla/. C:\\proyectos\\Kinetix_pruebas\\mockups\\analista\\

Contra el 5173 con localhost:8001 resuelto al 8002 (--host-resolver-rules), que
corre con la IA del chat SUSTITUIDA por el guion de /tmp/b5_ia_guion.json
(app_ia_falsa.py). El informe, al generar, no tiene IA: sale con el respaldo.
`/ai-config/estado` se simula «ok» salvo en el paso de la IA caída.

  1. ventana inicial (menú, aviso, JTL soltado FUERA de la zona)
  2. ficha inicial (falta 1 obligatorio, criterios en rojo, mini gráfico, casillas)
  3. generar sin criterios -> la pregunta en el chat, y no genera
  4. mensaje -> ficha actualizada (criterios con su resultado, relato, «listo»)
  5. adjunto -> tarjeta de errores; adjunto rechazado -> aviso
  6. casillas · «Cambiar datos de la prueba»
  7. recargar y que la sesión siga
  8. IA caída: el turno y la franja
  9. sesión que no es tuya
 10. generar con criterios -> «Procesando», el aviso del respaldo y el informe
Todo en la base de PRUEBAS; proyecto «ZZTEST-B5 pantalla».
"""
import base64
import csv
import io
import json
import os
import sys
import threading
import time
import uuid
from datetime import timedelta

from playwright.sync_api import sync_playwright

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/pruebas_e2e")
import b5_comun as B   # noqa: E402
from b5_comun import ok   # noqa: E402
import r1_integrado as R1   # noqa: E402
from app.core.security import create_access_token   # noqa: E402
from app.services.ai.resumen_serie import _ok   # noqa: E402
from app.services.jtl.jtl_parser import JTLParser   # noqa: E402

WEB = "http://localhost:5173"
PUERTO = os.environ.get("KX_API_PUERTO", "8002")
GUION = "/tmp/b5_ia_guion.json"
SALIDA = "/tmp/b5_pantalla"
PROYECTO = "ZZTEST-B5 pantalla"


def guion(*entradas):
    json.dump(list(entradas), open(GUION, "w", encoding="utf-8"), ensure_ascii=False)


def cookies(nombre, rol):
    if nombre == "admin":
        uid = B.sql("select id from users where username='admin'")[0][0]
    else:
        B.cliente(nombre, rol)   # lo crea si falta
        uid = B.sql("select id from users where username=%s", (nombre,))[0][0]
    tok = create_access_token({"sub": str(uid), "username": nombre, "role": rol}, timedelta(minutes=60))
    return [{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
            {"name": "csrf_token", "value": uuid.uuid4().hex, "domain": "localhost", "path": "/"}]


def csv_errores():
    p = JTLParser(B.JTL_R1)
    p.parse()
    err = p.df_main[~_ok(p.df_main)]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timeStamp", "label", "responseCode", "responseMessage", "success", "failureMessage"])
    for _, r in err.iterrows():
        w.writerow([int(r["timeStamp"]), r["label"], r["responseCode"], r["responseMessage"], "false",
                    r.get("failureMessage") or ""])
    return buf.getvalue().encode()


ESTADO_OK = json.dumps({"ok": True, "provider": "openai", "model": "gpt-5.5", "motivo_tipo": None,
                        "motivo_frase": None, "detalle": None, "comprobado_en": "", "limite": ""})


def main():
    os.makedirs(SALIDA, exist_ok=True)
    threading.Thread(target=R1._rele, daemon=True).start()
    time.sleep(0.5)
    guion()
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO}"])
        ctx = nav.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_cookies(cookies("admin", "admin"))
        estado_ok = lambda r: r.fulfill(status=200, content_type="application/json", body=ESTADO_OK)
        ctx.route("**/ai-config/estado**", estado_ok)
        pg = ctx.new_page()
        errores_js = []
        pg.on("pageerror", lambda e: errores_js.append(str(e)))

        def foto(n, nombre):
            pg.wait_for_timeout(500)
            pg.screenshot(path=f"{SALIDA}/{n:02d}_{nombre}.png", full_page=False)

        # ---------------------------------------------------------------- 1
        print("== 1. Ventana inicial")
        pg.goto(f"{WEB}/performance/analista", wait_until="networkidle", timeout=120000)
        pg.get_by_test_id("analista-nueva").wait_for(timeout=60000)
        ok(pg.get_by_role("link", name="Analista IA").count() >= 1 or pg.get_by_text("Analista IA").count() >= 1,
           "la entrada «Analista IA» está en el menú")
        ok(pg.get_by_text("Nuevo Reporte").count() >= 1, "y «Nuevo Reporte» sigue ahí")
        ok("no se escriben aquí" in pg.get_by_test_id("analista-nueva").inner_text(), "el aviso: los criterios se cuentan en la conversación")
        ok(pg.get_by_test_id("nueva-leer").is_disabled(), "«Leer la prueba y conversar» desactivado sin proyecto ni JTL")
        opciones = pg.get_by_test_id("nueva-cliente").locator("option").all_inner_texts()
        cliente = next((o for o in opciones if o.startswith("ZZTEST-R1")), None)
        if cliente:
            pg.get_by_test_id("nueva-cliente").select_option(label=cliente)
        pg.get_by_test_id("nueva-proyecto").fill(PROYECTO)
        pg.get_by_test_id("nueva-tipo-stress").click()
        # Soltar el JTL FUERA de la zona punteada: sobre el título de la ventana.
        b64 = base64.b64encode(open(B.JTL_R1, "rb").read()).decode()
        dt = pg.evaluate_handle("""(b64) => {
            const bin = atob(b64); const u = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
            const dt = new DataTransfer(); dt.items.add(new File([u], 'ZZTEST-B5_pantalla.jtl')); return dt; }""", b64)
        titulo = pg.get_by_text("Nueva prueba", exact=True)
        for ev in ("dragenter", "dragover", "drop"):
            titulo.dispatch_event(ev, {"dataTransfer": dt})
        ok("ZZTEST-B5_pantalla.jtl" in pg.get_by_test_id("nueva-lista").inner_text(), "el JTL soltado fuera de la zona entra en la lista")
        foto(1, "ventana_inicial")
        guion({"respuesta": "Leí una prueba de estrés de 5 minutos con un 41 % de errores.\n"
                            "Los fallos están en Get, Put y Delete por id.\n"
                            "¿Qué criterios de aceptación se acordaron con el cliente?"})
        pg.get_by_test_id("nueva-leer").click()
        pg.wait_for_url("**/performance/analista/*", timeout=120000)
        sid = pg.url.rstrip("/").split("/")[-1]
        pg.get_by_test_id("analista-conversacion").wait_for(timeout=60000)

        # ---------------------------------------------------------------- 2
        print("== 2. Ficha inicial")
        ok(PROYECTO in pg.get_by_test_id("cabecera-titulo").inner_text(), "la cabecera con el proyecto")
        ok(not cliente or cliente in pg.get_by_test_id("cabecera-titulo").inner_text(), "y el cliente")
        ok(pg.get_by_test_id("cabecera-cambiar").is_visible() and pg.get_by_test_id("cabecera-nueva").is_visible(),
           "«Cambiar datos de la prueba» y «Nueva conversación»")
        ok(pg.get_by_test_id("ficha-listo").inner_text() == "Falta 1 dato obligatorio", "«Falta 1 dato obligatorio»")
        crit = pg.get_by_test_id("tarjeta-criterios")
        ok("obligatorio" in crit.inner_text() and "border-red-400" in crit.get_attribute("class"), "criterios en rojo y «obligatorio»")
        ok(pg.get_by_test_id("mini-grafico").locator("svg").count() >= 1, "el mini gráfico de usuarios y errores")
        ok("4.811" in pg.get_by_test_id("tarjeta-prueba").inner_text(), "las cifras de la prueba")
        casillas = pg.get_by_test_id("tx-casilla")
        ok(casillas.count() == 6 and sum(1 for i in range(6) if casillas.nth(i).is_checked()) == 3,
           "6 transacciones, 3 con informe propio (las que tienen errores)")
        ok(pg.get_by_test_id("pendiente").count() >= 2, "los pendientes opcionales en ámbar")
        ia = pg.get_by_test_id("mensaje-ia")
        ok(ia.count() == 1 and "estrés de 5 minutos" in ia.first.inner_text(), "el primer mensaje de la IA")
        foto(2, "ficha_inicial")

        # ---------------------------------------------------------------- 3
        print("== 3. Generar sin criterios")
        pg.get_by_test_id("ficha-generar").click()
        pg.get_by_text("Antes de generar necesito los criterios").wait_for(timeout=30000)
        ok("/performance/analista/" in pg.url, "no genera: sigue en la conversación")
        ok("animate-pulse" in crit.locator("span.rounded-full").first.get_attribute("class"), "la tarjeta de criterios, resaltada")
        ok(B.sql("select count(*) from test_executions where name=%s", (PROYECTO,))[0][0] == 0, "no hay ejecución")
        foto(3, "faltan_criterios")

        # ---------------------------------------------------------------- 4
        print("== 4. Mensaje -> ficha actualizada")
        guion({"respuesta": "Anoté los dos criterios y que era una ronda corta. ¿En qué ambiente se corrió?",
               "criterios": [{"texto": "El 90 % en menos de 1 segundo", "tipo": "tiempo_respuesta", "metrica": "p90",
                              "operador": "<", "valor": 1, "unidad": "s"},
                             {"texto": "Disponibilidad del 99 %", "tipo": "disponibilidad_o_error",
                              "metrica": "disponibilidad", "operador": ">=", "valor": 99, "unidad": "%"}],
               "relato": ["Era una ronda corta para validar el script."], "contexto": {},
               "pendientes_resueltos": [], "sin_criterios": False})
        pg.get_by_test_id("chat-caja").fill("P90 por debajo de 1 segundo y 99 % de disponibilidad. Era una ronda corta.")
        pg.get_by_test_id("chat-caja").press("Control+Enter")
        pg.get_by_test_id("criterio").nth(1).wait_for(timeout=30000)
        res = pg.get_by_test_id("criterio-resultado").all_inner_texts()
        ok(res == ["Cumple", "No cumple"], f"los criterios con el resultado del servidor ({res})")
        ok(pg.get_by_test_id("ficha-listo").inner_text().startswith("Listo para generar:"), "«Listo para generar: N de M»")
        ok("border-red-400" not in crit.get_attribute("class"), "la tarjeta de criterios ya no está en rojo")
        ok(pg.get_by_test_id("relato-linea").count() == 1, "la línea en «Lo que contaste»")
        ok(pg.get_by_test_id("chat-caja").input_value() == "", "la caja se vacía al enviar (Ctrl+Enter)")
        ok(pg.get_by_test_id("rapido-Ambiente y versión").is_visible() and pg.get_by_test_id("rapido-No sé, sigue sin eso").is_visible(),
           "los botones rápidos")
        # 150: la ficha agrupa los criterios por transacción
        grupos = pg.get_by_test_id("grupo-nombre").all_inner_texts()
        ok(len(grupos) == 6 and "1. Auth" in grupos, f"criterios agrupados por transacción ({len(grupos)} grupos)")
        ok(pg.get_by_test_id("criterios-veredicto").inner_text() == "NO APTO", "con el veredicto según los criterios")
        foto(4, "ficha_con_criterios")

        # ---------------------------------------------------------------- 5
        print("== 5. Adjunto (soltado sobre el chat)")
        b64e = base64.b64encode(csv_errores()).decode()
        dte = pg.evaluate_handle("""(b64) => {
            const bin = atob(b64); const u = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
            const dt = new DataTransfer(); dt.items.add(new File([u], 'errores_zztest.csv')); return dt; }""", b64e)
        chat = pg.get_by_test_id("chat-mensajes")
        chat.dispatch_event("dragenter", {"dataTransfer": dte})
        ok(pg.get_by_test_id("chat-soltar").is_visible(), "al arrastrar sobre el chat, «Suelta aquí el archivo…»")
        chat.dispatch_event("dragover", {"dataTransfer": dte})
        chat.dispatch_event("drop", {"dataTransfer": dte})
        pg.get_by_test_id("tarjeta-errores").wait_for(timeout=60000)
        ok("Cuadra con el JTL" in pg.get_by_test_id("adjunto-cruce").inner_text(), "la tarjeta de errores, con el cruce")
        ok(pg.get_by_test_id("chat-aviso-ok").is_visible(), "y el aviso en el chat")
        pg.get_by_test_id("chat-archivo").set_input_files({"name": "notas.txt", "mimeType": "text/plain", "buffer": b"hola"})
        pg.get_by_test_id("chat-aviso-error").wait_for(timeout=30000)
        ok("Adjunto rechazado" in pg.get_by_test_id("chat-aviso-error").inner_text(), "adjunto rechazado: se ve el motivo")
        foto(5, "adjunto")

        # ---------------------------------------------------------------- 6
        print("== 6. Casillas y datos de la prueba")
        auth = pg.locator("label", has_text="1. Auth").get_by_test_id("tx-casilla")
        antes = auth.is_checked()
        auth.click()
        pg.wait_for_timeout(1500)
        ok(auth.is_checked() != antes, "la casilla cambia")
        pg.get_by_test_id("cabecera-cambiar").click()
        pg.get_by_test_id("datos-proyecto").fill(PROYECTO + " 2")
        pg.get_by_test_id("datos-guardar").click()
        pg.get_by_test_id("modal-datos").wait_for(state="detached", timeout=60000)
        ok(PROYECTO + " 2" in pg.get_by_test_id("cabecera-titulo").inner_text(), "«Cambiar datos de la prueba»")

        # ---------------------------------------------------------------- 7
        print("== 7. Recargar")
        n_msj = pg.get_by_test_id("chat-mensajes").locator("[data-testid^=mensaje-]").count()
        pg.reload(wait_until="networkidle")
        pg.get_by_test_id("analista-conversacion").wait_for(timeout=60000)
        ok(pg.url.endswith(sid), "la misma URL")
        ok(pg.get_by_test_id("criterio").count() == 2 and pg.get_by_test_id("tarjeta-errores").is_visible(), "criterios y errores siguen")
        ok(pg.get_by_test_id("chat-mensajes").locator("[data-testid^=mensaje-]").count() == n_msj, f"los {n_msj} mensajes siguen")
        ok(pg.locator("label", has_text="1. Auth").get_by_test_id("tx-casilla").is_checked() != antes, "la casilla sigue como se dejó")

        # ---------------------------------------------------------------- 8
        print("== 8. IA caída")
        guion(None)
        pg.get_by_test_id("chat-caja").fill("Corrió en QA")
        pg.get_by_test_id("chat-enviar").click()
        pg.get_by_test_id("chat-aviso-error").wait_for(timeout=30000)
        ult = pg.get_by_test_id("mensaje-ia").last
        ok(ult.get_attribute("data-origen") == "error" and "quedó guardado" in ult.inner_text(), "el turno fallido se ve en el chat")
        ok("Corrió en QA" in pg.get_by_test_id("mensaje-analista").last.inner_text(), "el mensaje del analista se conserva")
        ctx.unroute("**/ai-config/estado**")
        pg.reload(wait_until="networkidle")
        pg.get_by_test_id("ia-caida").wait_for(timeout=60000)
        ok("La IA no está disponible" in pg.get_by_test_id("ia-caida").inner_text(), "la franja «La IA no está disponible»")
        foto(6, "ia_caida")
        ctx.route("**/ai-config/estado**", estado_ok)

        # ---------------------------------------------------------------- 9
        print("== 9. Sesión que no es tuya")
        ajena = B.crear(B.cliente("zztest_b5_analista_b", "analyst"), proyecto="ZZTEST-B5 ajena").json()["id"]
        ctx2 = nav.new_context(viewport={"width": 1440, "height": 900})
        ctx2.add_cookies(cookies("zztest_b5_analista_a", "analyst"))
        p2 = ctx2.new_page()
        p2.goto(f"{WEB}/performance/analista/{ajena}", wait_until="networkidle", timeout=120000)
        p2.get_by_test_id("sesion-no-tuya").wait_for(timeout=60000)
        ok("no es tuya" in p2.get_by_test_id("sesion-no-tuya").inner_text(), "«Esta conversación no existe o no es tuya»")
        p2.screenshot(path=f"{SALIDA}/07_no_es_tuya.png")
        ctx2.close()

        # ---------------------------------------------------------------- 10
        print("== 10. Generar con criterios")
        pg.goto(f"{WEB}/performance/analista/{sid}", wait_until="networkidle", timeout=120000)
        pg.get_by_test_id("analista-conversacion").wait_for(timeout=60000)
        pg.get_by_test_id("ficha-generar").click()
        pg.get_by_text("generando análisis").wait_for(timeout=30000)
        ok(True, "el bloqueo de «Procesando» de hoy")
        foto(8, "procesando")
        pg.get_by_test_id("aviso-tras-generar").wait_for(timeout=300000)
        ok(True, "sin IA en el 8002: el aviso de F2 tras generar")
        pg.get_by_test_id("aviso-tras-generar-ver").click()
        pg.wait_for_url("**/performance/report/*", timeout=60000)
        eid = pg.url.rstrip("/").split("/")[-1]
        fila = B.sql("select name, test_type, acceptance_criteria_json::text from test_executions where id=%s", (eid,))
        ok(fila and fila[0][0] == PROYECTO + " 2" and fila[0][1] == "stress", "al terminar, el informe de esta prueba")
        ok(json.loads(fila[0][2])["response_time"] == 1000, "con los criterios de la ficha")
        foto(9, "informe")
        ok(not errores_js, f"sin errores de JavaScript ({errores_js[:2]})")
        nav.close()


main()
B.fin("B5 pantalla")
