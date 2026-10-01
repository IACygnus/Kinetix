"""BLOQUE 3.5 — la pantalla de la caja unica del integrado, con Playwright.

    docker exec jmeter_backend sh /app/pruebas_e2e/reiniciar_8002.sh
    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_datos.py
    docker exec jmeter_backend python3 /app/pruebas_e2e/pantalla_conclusion_unica.py

Contra la base de PRUEBAS y el 8002 (regla 34): Chromium resuelve localhost:8001
al 8002. Siembra (insert o update, nunca delete) dos integrados ZZTEST con las
mismas ejecuciones de R1:
  - «ZZTEST-B3 unico»: `unico` + `_legado` (el consolidado por tipo de antes);
  - «ZZTEST-B3 por tipo»: el consolidado de siempre, sin `unico`.
Comprueba:
  1. con «unico»: dos cajas a lo ancho, «Conclusiones» y «Recomendaciones», sin el
     rotulo crudo ni «Prueba de Carga»/«Prueba de Estres»;
  2. el legado: plegado, «Versión anterior (solo lectura)», sin cajas de edicion,
     con su fecha y texto seleccionable;
  3. se edita, se guarda (el indicador dice «Guardado» y la base lo tiene, con el
     legado intacto) y se recarga con la edicion;
  4. sin «unico»: las cajas por tipo de siempre, sin legado;
  5. regenerar sin IA (el 8002 no tiene clave): la confirmacion de F5, un aviso
     visible con el motivo y ni la pantalla ni la base pierden nada.
0 llamadas a la IA.
"""
import json
import os
import sys
import threading
import time
import uuid
from datetime import timedelta

import psycopg2
import psycopg2.extras
from playwright.sync_api import sync_playwright

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/pruebas_e2e")
from app.core.security import create_access_token  # noqa: E402
import r1_integrado as R1  # noqa: E402

WEB = "http://localhost:5173"
PUERTO_TEST = os.environ.get("KX_API_PUERTO", "8002")
DB_TEST = os.environ.get("KX_DB", "jmeter_analyzer_test")
if "test" not in DB_TEST:
    sys.exit("PARADA: la base no es de pruebas")
PG = dict(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB_TEST)
FALLOS = []

UNICO = {"conclusions": "• ZZTEST-B3 conclusion unica uno.\n• ZZTEST-B3 conclusion unica dos.",
         "recommendations": "• ZZTEST-B3 recomendacion unica.",
         "generated_at": "2026-10-01T09:00:00-05:00", "edited": False, "ejecuciones": ["ZZTEST-R1 carga"]}
LEGADO = {"load": {"conclusions": "ZZTEST-B3 legado carga conclusiones.",
                   "recommendations": "ZZTEST-B3 legado carga recomendaciones.",
                   "generated_at": "2026-09-25T10:00:00-05:00", "edited": True},
          "stress": {"conclusions": "ZZTEST-B3 legado estres conclusiones.",
                     "recommendations": "ZZTEST-B3 legado estres recomendaciones.",
                     "generated_at": "2026-09-25T10:00:00-05:00", "edited": False}}
POR_TIPO = {"load": {"conclusions": "ZZTEST-B3 por tipo carga conclusiones.",
                     "recommendations": "ZZTEST-B3 por tipo carga recomendaciones.",
                     "generated_at": None, "edited": False},
            "stress": {"conclusions": "ZZTEST-B3 por tipo estres conclusiones.",
                       "recommendations": "ZZTEST-B3 por tipo estres recomendaciones.",
                       "generated_at": None, "edited": False}}


def ok(c, m):
    print(("PASA  | " if c else "FALLA | ") + m)
    if not c:
        FALLOS.append(m)
    return c


def sql(q, a=(), escribir=False):
    c = psycopg2.connect(**PG)
    cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(q, a)
    filas = cur.fetchall() if cur.description else []
    if escribir:
        c.commit()
    c.close()
    return filas


def sembrar(nombre, consolidado, secciones, admin):
    """Insert o update por nombre ZZTEST (regla 29). Nunca delete (regla 28)."""
    f = sql("select id from integrated_reports where name=%s", (nombre,))
    if f:
        sql("update integrated_reports set sections=%s, consolidated_analysis=%s, updated_at=now() where id=%s",
            (json.dumps(secciones), json.dumps(consolidado), f[0]["id"]), escribir=True)
        return str(f[0]["id"])
    rid = str(uuid.uuid4())
    sql("insert into integrated_reports (id, name, sections, consolidated_analysis, created_by, created_at, "
        "updated_at) values (%s,%s,%s,%s,%s,now(),now())",
        (rid, nombre, json.dumps(secciones), json.dumps(consolidado), admin), escribir=True)
    return rid


def consolidado_de(rid):
    return sql("select consolidated_analysis from integrated_reports where id=%s", (rid,))[0]["consolidated_analysis"]


def main():
    carga = str(sql("select id from test_executions where name='ZZTEST-R1 carga'")[0]["id"])
    estres = str(sql("select id from test_executions where name='ZZTEST-R1 estres'")[0]["id"])
    u = sql("select id, username, role from users where username='admin'")[0]
    secs = [{"order": 0, "type": "load_test", "source_id": carga, "source_name": "ZZTEST-R1 carga"},
            {"order": 1, "type": "stress_test", "source_id": estres, "source_name": "ZZTEST-R1 estres"}]
    rid_u = sembrar("ZZTEST-B3 unico", {"unico": UNICO, "_legado": LEGADO}, secs, u["id"])
    rid_t = sembrar("ZZTEST-B3 por tipo", POR_TIPO, secs, u["id"])
    tok = create_access_token({"sub": str(u["id"]), "username": u["username"], "role": u["role"]},
                              timedelta(minutes=60))
    csrf = uuid.uuid4().hex
    threading.Thread(target=R1._rele, daemon=True).start()
    time.sleep(0.5)

    with sync_playwright() as p:
        b = p.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO_TEST}"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1000})
        ctx.add_cookies([{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
                         {"name": "csrf_token", "value": csrf, "domain": "localhost", "path": "/"}])
        pg = ctx.new_page()

        def abrir(rid, titulo):
            pg.goto(f"{WEB}/performance/integrated/{rid}", wait_until="networkidle", timeout=180000)
            pg.get_by_role("heading", name=titulo).wait_for(timeout=180000)
            return pg.locator("div.border-t-4").filter(has=pg.get_by_role("heading", name=titulo)).last

        # ── 1. con «unico» ──
        zona = abrir(rid_u, "Conclusiones y Recomendaciones")
        cajas = zona.locator('[data-caja="unico"] textarea')
        ok(cajas.count() == 2, f"dos cajas en la caja unica ({cajas.count()})")
        ok(cajas.nth(0).input_value() == UNICO["conclusions"]
           and cajas.nth(1).input_value() == UNICO["recommendations"], "con su texto, en ese orden")
        titulos = zona.locator('[data-caja="unico"] h5').all_inner_texts()
        ok(titulos == ["Conclusiones", "Recomendaciones"], f"titulos: {titulos}")
        caja_c, caja_r = (cajas.nth(i).bounding_box() for i in (0, 1))
        ok(caja_r["y"] > caja_c["y"] + caja_c["height"] - 1 and abs(caja_c["width"] - caja_r["width"]) < 2,
           "a lo ancho, una debajo de la otra")
        visibles = [t for t in zona.locator("h4, h5").all_inner_texts() if t.strip()]
        ok(not any(t.strip().lower() == "unico" for t in visibles), "sin el rotulo crudo «unico»")
        ok(zona.locator("textarea").count() == 2, "ninguna otra caja editable (ni por tipo ni del legado)")

        # ── 2. el legado ──
        leg = zona.locator("details[data-legado]")
        ok(leg.count() == 1, "hay un bloque de version anterior")
        ok(leg.get_attribute("open") is None, "plegado de entrada")
        ok("Versión anterior (solo lectura)" in leg.locator("summary").inner_text(), "con su rotulo")
        ok(not zona.get_by_text("ZZTEST-B3 legado carga conclusiones.").is_visible(), "sus textos, ocultos al estar plegado")
        visibles_tipo = [t for t in zona.locator("h4").all_inner_texts() if "Prueba de" in t]
        ok(not any(zona.locator("h4").filter(has_text="Prueba de").nth(i).is_visible()
                   for i in range(len(visibles_tipo))), "sin «Prueba de Carga/Estres» a la vista")
        leg.locator("summary").click()
        texto_leg = zona.get_by_text("ZZTEST-B3 legado carga conclusiones.")
        ok(texto_leg.is_visible(), "al desplegar, el texto anterior se ve")
        ok(leg.locator("textarea, input, [contenteditable=true]").count() == 0, "y no se puede editar")
        ok(texto_leg.evaluate("e => getComputedStyle(e).userSelect") != "none", "y se puede seleccionar para copiar")
        cab = leg.inner_text()
        ok("Prueba de Carga" in cab and "Prueba de Estres" in cab and "2026" in cab and "editada a mano" in cab,
           "con su tipo, su fecha y la marca de edicion")

        # ── 3. editar, guardar, recargar ──
        cajas.nth(0).click()
        pg.keyboard.press("Control+End")
        pg.keyboard.type("\n• ZZTEST-B3 editada en pantalla.")
        zona.locator('[data-caja="unico"] h5').first.click()   # blur
        estado = ""
        for _ in range(40):
            estado = pg.get_by_test_id("estado-guardado").inner_text()
            if estado.startswith("Guardado"):
                break
            pg.wait_for_timeout(500)
        ok(estado.startswith("Guardado"), f"el indicador dice «{estado}»")
        ca = consolidado_de(rid_u)
        ok("ZZTEST-B3 editada en pantalla." in ca["unico"]["conclusions"] and ca["unico"].get("edited") is True,
           "la base tiene la edicion, marcada como editada")
        ok(ca.get("_legado") == LEGADO, "y el legado intacto")
        zona = abrir(rid_u, "Conclusiones y Recomendaciones")
        ok("ZZTEST-B3 editada en pantalla." in zona.locator('[data-caja="unico"] textarea').nth(0).input_value(),
           "tras recargar, la edicion sigue")

        # ── 5. regenerar sin IA: confirmacion F5, aviso, nada perdido ──
        antes_pantalla = [zona.locator('[data-caja="unico"] textarea').nth(i).input_value() for i in (0, 1)]
        antes_base = consolidado_de(rid_u)
        zona.get_by_role("button", name="Regenerar", exact=True).click()
        conf = pg.get_by_role("button", name="Regenerar y reemplazar")
        ok(conf.is_visible(), "con ediciones, regenerar pide confirmacion (F5)")
        conf.click()
        aviso = zona.get_by_role("alert")
        aviso.wait_for(timeout=180000)
        txt = aviso.inner_text()
        ok("No se generaron las conclusiones" in txt and "No se guardo nada" in txt, f"aviso visible: «{txt[:110]}…»")
        despues = [zona.locator('[data-caja="unico"] textarea').nth(i).input_value() for i in (0, 1)]
        ok(despues == antes_pantalla and all(despues), "las cajas siguen como estaban, nunca vacias")
        ok(consolidado_de(rid_u) == antes_base, "la base no cambia")

        # ── 4. sin «unico»: como siempre ──
        zona = abrir(rid_t, "Analisis Consolidado")
        tipos = zona.locator("h4").all_inner_texts()
        ok("Prueba de Carga" in tipos and "Prueba de Estres" in tipos, f"las cajas por tipo de siempre ({tipos})")
        ok(zona.locator("textarea").count() == 4, f"cuatro cajas ({zona.locator('textarea').count()})")
        ok(zona.locator('[data-caja="unico"], details[data-legado]').count() == 0, "sin caja unica ni legado")
        ok(any("ZZTEST-B3 por tipo estres recomendaciones." == zona.locator("textarea").nth(i).input_value()
               for i in range(4)), "con sus textos")
        b.close()

    # Deja los dos integrados como se sembraron.
    sembrar("ZZTEST-B3 unico", {"unico": UNICO, "_legado": LEGADO}, secs, u["id"])
    print()
    print("PANTALLA CONCLUSION UNICA: TODO PASA" if not FALLOS else f"PANTALLA CONCLUSION UNICA: {len(FALLOS)} FALLOS")
    return 0 if not FALLOS else 1


if __name__ == "__main__":
    sys.exit(main())
