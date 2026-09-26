"""ETAPA R1.3 — el historial del informe integrado: trabajo guardado y contenido.

    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_historial.py

Base de PRUEBAS (regla 34), Chromium con el 8001 resuelto al 8002. Necesita que
antes hayan corrido r1_integrado.py (deja ediciones en 'ZZTEST-R1 integrado') y
r1_seleccion.py (deja seleccion en 'ZZTEST-R1 seleccion').

Lo que demuestra (R-D6 y el apunte de Fredy):
  1. La lista dice, sin abrir el informe, cuantos textos editados tiene guardados,
     contados una vez aunque viajen en varias secciones de la misma ejecucion.
  2. Dice que contenido se eligio, y «Todo» si no se eligio nada.
  3. El filtro «Con ediciones guardadas» deja fuera a los que no tienen trabajo.
"""
import os
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


def ediciones_esperadas(nombre):
    """Lo mismo que debe contar el backend, calculado aqui por otro camino (SQL)."""
    return sql("""
        select count(*) from (
          select distinct s->>'source_id', t.tipo, t.clave
          from integrated_reports r, jsonb_array_elements(r.sections) s,
               lateral (select 'analysis' tipo, k clave from jsonb_object_keys(coalesce(s->'overrides'->'analysis','{}')) k
                        union all
                        select 'images', k from jsonb_object_keys(coalesce(s->'overrides'->'images','{}')) k) t
          where r.name=%s) x""", (nombre,))[0][0]


def main():
    uid, uname, role = sql("select id, username, role from users where username='admin'")[0]
    tok = create_access_token({"sub": str(uid), "username": uname, "role": role}, timedelta(minutes=60))
    csrf = uuid.uuid4().hex

    with httpx.Client(cookies={"access_token": tok, "csrf_token": csrf}, timeout=60) as cli:
        lista = {r["name"]: r for r in cli.get(f"{API_TEST}/reports/integrated-reports").json()}
    ed = lista["ZZTEST-R1 integrado"]
    esperadas = ediciones_esperadas("ZZTEST-R1 integrado")
    comprobar(ed["ediciones_seccion"] == esperadas and esperadas > 0,
              f"API: 'ZZTEST-R1 integrado' cuenta {ed['ediciones_seccion']} textos editados (SQL: {esperadas})")
    comprobar(lista["ZZTEST-R1 solo carga"]["ediciones_seccion"] == 0
              and not lista["ZZTEST-R1 solo carga"]["consolidado_editado"],
              "API: 'ZZTEST-R1 solo carga' sin ediciones")
    sel = {(x["tipo"], x["elegidas"]) for x in lista["ZZTEST-R1 seleccion"]["seleccion"]}
    comprobar(sel == {("load_test", 1), ("monitoring", 1), ("evidence", 0)},
              f"API: 'ZZTEST-R1 seleccion' resume su seleccion {sorted(sel)}")
    comprobar(lista["ZZTEST-R1 solo carga"]["seleccion"] == [], "API: sin seleccion, lista vacia (= todo)")

    threading.Thread(target=_rele, daemon=True).start()
    time.sleep(0.5)
    with sync_playwright() as p:
        b = p.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO_TEST}"])
        ctx = b.new_context(viewport={"width": 1700, "height": 1000})
        ctx.add_cookies([{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
                         {"name": "csrf_token", "value": csrf, "domain": "localhost", "path": "/"}])
        pg = ctx.new_page()
        pg.goto(f"{WEB}/performance/integrated/history", wait_until="networkidle", timeout=120000)
        pg.get_by_text("ZZTEST-R1 integrado").first.wait_for(timeout=60000)

        def fila(nombre):
            return pg.locator("tr", has=pg.get_by_text(nombre, exact=True))

        t = fila("ZZTEST-R1 integrado").get_by_test_id("trabajo-guardado").inner_text()
        comprobar(f"{esperadas} textos editados" in t, f"pantalla: 'ZZTEST-R1 integrado' dice «{t}»")
        t = fila("ZZTEST-R1 solo carga").get_by_test_id("trabajo-guardado").inner_text()
        comprobar(t == "Sin ediciones", f"pantalla: 'ZZTEST-R1 solo carga' dice «{t}»")
        c = fila("ZZTEST-R1 seleccion").get_by_test_id("contenido-elegido").inner_text()
        comprobar("1 transacción" in c and "1 captura" in c and "ninguna captura" in c,
                  f"pantalla: el contenido elegido se lee «{' | '.join(c.splitlines())}»")
        c = fila("ZZTEST-R1 solo carga").get_by_test_id("contenido-elegido").inner_text()
        comprobar(c == "Todo", f"pantalla: sin seleccion dice «{c}»")

        pg.locator("select").filter(has=pg.locator("option[value=editados]")).select_option("editados")
        pg.wait_for_timeout(500)
        comprobar(fila("ZZTEST-R1 integrado").count() == 1 and fila("ZZTEST-R1 solo carga").count() == 0,
                  "filtro «Con ediciones guardadas»: queda el editado y sale el que no tiene trabajo")
        b.close()

    print(f"\n{'TODO PASA' if not fallos else f'{len(fallos)} FALLO(S)'}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
