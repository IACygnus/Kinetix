"""Reporte 151, parte 3 — la columna de umbral del «Veredicto por Transacción» (Dashboard.tsx).

    docker exec jmeter_backend sh /app/pruebas_e2e/reiniciar_8002.sh
    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_datos.py
    docker exec jmeter_backend python3 /app/pruebas_e2e/b5_j_umbral.py

Contra el 5173 con localhost:8001 resuelto al 8002 (base de PRUEBAS):
  1. una ejecución del Analista IA con un criterio de tiempo MÁXIMO solo para
     «1. Auth» y disponibilidad para cada transacción: la columna se llama
     «Criterio de tiempo», Auth dice «máximo ≤ 5 s» y las demás «sin criterio».
     Nunca 2.000;
  2. una ejecución de Nuevo Reporte (ZZTEST-R1 carga): la columna «Umbral RT (ms)»
     con sus números, como siempre.
"""
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

WEB = "http://localhost:5173"
PUERTO = os.environ.get("KX_API_PUERTO", "8002")
A = B.API + "/analista/sesiones"


def generar_analista():
    c = B.cliente()
    sid = B.crear(c, proyecto="ZZTEST-B5 umbral").json()["id"]
    r = c.patch(f"{A}/{sid}", json={"criterios": {"agregar": [
        {"texto": "Auth en menos de 5 segundos como máximo", "tipo": "tiempo_respuesta", "metrica": "max",
         "operador": "<=", "valor": 5, "unidad": "s", "transacciones": ["1. Auth"]},
        {"texto": "99 % de disponibilidad por servicio", "tipo": "disponibilidad_o_error", "metrica": "disponibilidad",
         "valor": 99, "cada_transaccion": True}]}})
    assert r.status_code == 200, r.text
    d = c.post(f"{A}/{sid}/generar").json()
    return d["execution_id"]


def main():
    eid = generar_analista()
    viejo = B.sql("select id::text, acceptance_criteria_json::text from test_executions where name='ZZTEST-R1 carga'")[0]
    crit_viejo = json.loads(viejo[1])
    uid = B.sql("select id from users where username='admin'")[0][0]
    tok = create_access_token({"sub": str(uid), "username": "admin", "role": "admin"}, timedelta(minutes=30))
    threading.Thread(target=R1._rele, daemon=True).start()
    time.sleep(0.5)
    with sync_playwright() as p:
        b = p.chromium.launch(args=[f"--host-resolver-rules=MAP localhost:8001 127.0.0.1:{PUERTO}"])
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_cookies([{"name": "access_token", "value": tok, "domain": "localhost", "path": "/"},
                         {"name": "csrf_token", "value": uuid.uuid4().hex, "domain": "localhost", "path": "/"}])
        pg = ctx.new_page()

        def tabla(execution_id):
            pg.goto(f"{WEB}/performance/report/{execution_id}", wait_until="networkidle", timeout=120000)
            pg.get_by_text("Veredicto por Transacción").wait_for(timeout=120000)
            caja = pg.get_by_text("Veredicto por Transacción").locator("xpath=ancestor::div[contains(@class,'rounded-2xl')][1]")
            cab = caja.locator("thead th").all_inner_texts()
            filas = {}
            for tr in caja.locator("tbody tr").all():
                celdas = tr.locator("td").all_inner_texts()
                filas[celdas[0].strip()] = celdas[2].strip()
            return cab, filas, caja

        print("== 1. Ejecución del Analista IA")
        cab, filas, caja = tabla(eid)
        ok(any(h.strip().lower() == "criterio de tiempo" for h in cab), f"la columna se llama «Criterio de tiempo» ({cab})")
        ok(filas.get("1. Auth") == "máximo ≤ 5 s", f"Auth: el criterio declarado con su valor y su medida ({filas.get('1. Auth')})")
        otras = {k: v for k, v in filas.items() if k != "1. Auth"}
        ok(len(otras) == 5 and set(otras.values()) == {"sin criterio"}, f"las otras 5: «sin criterio» ({set(otras.values())})")
        ok(not any("2000" in v or "2.000" in v for v in filas.values()), "nunca 2.000 por defecto")
        caja.screenshot(path="/tmp/b5_j_analista.png")

        print("== 2. Ejecución de Nuevo Reporte (como hoy)")
        cab, filas, caja = tabla(viejo[0])
        ok(any(h.strip().lower() == "umbral rt (ms)" for h in cab), f"la columna sigue siendo «Umbral RT (ms)» ({cab})")
        esperado = {t: str((crit_viejo.get("per_transaction") or {}).get(t, {}).get("response_time")
                           or crit_viejo.get("response_time") or 2000) for t in filas}
        ok(filas == esperado, f"los números de siempre ({sorted(set(filas.values()))})")
        caja.screenshot(path="/tmp/b5_j_viejo.png")
        b.close()


main()
B.fin("B5 J (umbral de tiempo en el Dashboard)")
