"""Reporte 150, parte 3 — los criterios tras la prueba real de Fredy, con el caso suyo en sintético.

    docker exec -e PYTHONPATH=/app/pruebas_e2e:/app \
        -e DATABASE_URL=postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_test \
        -e GEMINI_API_KEY= -e OPENAI_API_KEY= jmeter_backend python3 /app/pruebas_e2e/b5_f_criterios_v2.py

Un JTL ZZTEST de 35 minutos con tres servicios, como el de Fredy (escalado):
  A «1. ZZ_AsegurarFondos»  lento (promedio ~4,8 s, máximo 9.221 ms), grupo de 28 usuarios
  B «3. ZZ_Originator»      rápido, el mismo grupo de 28
  C «1. ZZ_Receptor»        rápido, con un pico de 21.038 ms, grupo de 7
En proceso (la app sobre ASGI) con la IA sustituida por un guion:
  1. «5 s de espera, 6.400 entre A y B en 30 min, 800 para C, 28 usuarios en A y B»:
     el volumen entre A y B es una SUMA; el tiempo sin medida, P90 supuesto; la
     respuesta lleva «Así los entendí» por servicio;
  2. «el máximo»: el tiempo se REEMPLAZA por el máximo, por transacción, y no
     cumple nombrando A y C;
  3. «es por servicio, no el total» (sin `reemplaza`: lo resuelve el servidor):
     la suma desaparece y queda un volumen por servicio, calculado.
Y sin IA: el volumen sin servicio no se evalúa contra el total; el veredicto sale
de los criterios.
"""
import asyncio
import csv
import io
import json
import os
import random

import httpx
import pandas as pd

import b5_comun as B
from b5_comun import ok

assert "test" in os.environ.get("DATABASE_URL", ""), "PARADA: DATABASE_URL no apunta a la base de pruebas"
JTL = "/app/uploads/ZZTEST-B5_fredy.jtl"
A_, B_, C_ = "1. ZZ_AsegurarFondos", "3. ZZ_Originator", "1. ZZ_Receptor"


def fabricar():
    """35 min. A y B en el grupo «Originador» (28), C en «Receptor» (7)."""
    random.seed(1501)
    t0 = 1790804400000
    filas = []
    for label, n, media, pico, grupo, err in ((A_, 1100, 4800, 9221, 28, 1), (B_, 1090, 140, 788, 28, 0),
                                              (C_, 3478, 390, 21038, 7, 1)):
        for i in range(n):
            ts = t0 + int(i * 2100000 / n) + random.randint(0, 900)
            el = max(20, int(random.gauss(media, media * 0.15)))
            if i == n // 2:
                el = pico
            fallo = err and i == n // 3
            filas.append([ts, el, label, "409" if fallo else "200", "Conflict" if fallo else "OK",
                          f"{'Originador' if grupo == 28 else 'Receptor'} 1-{i % grupo + 1}", "text",
                          "false" if fallo else "true", "", 900, 1100, grupo, 35, "https://zz.local/x", el, 0, 30])
    filas.sort()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timeStamp", "elapsed", "label", "responseCode", "responseMessage", "threadName", "dataType",
                "success", "failureMessage", "bytes", "sentBytes", "grpThreads", "allThreads", "URL", "Latency",
                "IdleTime", "Connect"])
    w.writerows(filas)
    open(JTL, "w", encoding="utf-8").write(buf.getvalue())
    df = pd.DataFrame(filas, columns=["ts", "el", "label", "rc", "rm", "tn", "dt", "s", "fm", "b", "sb", "g", "a",
                                      "u", "l", "it", "c"])
    df["ok"] = df["s"] == "true"
    return df


DF = fabricar()
T0 = DF["ts"].min()


def correctas(label, ventana_min=None):
    d = DF[(DF["label"] == label) & DF["ok"]]
    if ventana_min is not None:
        d = d[(d["ts"] - T0) / 1000 <= ventana_min * 60]
    return int(len(d))


from app.main import app   # noqa: E402
from app.api.v1.endpoints import analista as EP   # noqa: E402
from app.services.analista import criterios_libres as CL   # noqa: E402

GUION = []


async def _llamador(db):
    async def falsa(prompt, sistema, sanear):
        x = GUION.pop(0) if GUION else None
        return (json.dumps(x) if isinstance(x, dict) else x, "") if x is not None else (None, "sin guion")
    return falsa


EP.llamador = _llamador
EP.RITMO_MENSAJES = 1000


def turno_ia(respuesta, criterios, reemplaza=()):
    return {"respuesta": respuesta, "criterios": criterios, "relato": [], "contexto": {},
            "pendientes_resueltos": [], "sin_criterios": False, "reemplaza": list(reemplaza)}


async def main():
    c0 = B.cliente()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://kx",
                                 cookies=dict(c0.cookies), headers={"X-CSRF-Token": c0.headers["x-csrf-token"]},
                                 timeout=600) as c:
        base = "/api/v1/analista/sesiones"
        with open(JTL, "rb") as f:
            r = await c.post(base, data={"proyecto": "ZZTEST-B5 criterios v2", "tipo": "load"},
                             files={"files": ("ZZTEST-B5_fredy.jtl", f)})
        ok(r.status_code == 201, f"sesión con el JTL sintético ({r.status_code})")
        sid = r.json()["id"]
        ficha = r.json()["ficha"]
        tx = {t["label"]: t for t in ficha["transacciones"]}
        ok(tx[A_]["usuarios_grupo"] == 28 and tx[C_]["usuarios_grupo"] == 7, "los usuarios del grupo de cada servicio")
        ok(tx[A_]["max"] == 9221 and tx[C_]["max"] == 21038, "los máximos sembrados")

        print("== 1. Los criterios de Fredy, como los dijo")
        GUION.append(turno_ia(
            "Los anoté. ¿El tiempo de 5 segundos es sobre el promedio, el P90, el P95 o el máximo?",
            [{"texto": "5 segundos el tiempo de espera", "tipo": "tiempo_respuesta", "operador": "<=", "valor": 5,
              "unidad": "s", "cada_transaccion": True},
             {"texto": "6.400 transacciones total entre asegurar fondos y originador en 30 minutos", "tipo": "volumen",
              "valor": 6400, "transacciones": ["asegurar fondos", "originator"], "suma": True,
              "ventana_valor": 30, "ventana_unidad": "min"},
             {"texto": "800 transacciones para receptor", "tipo": "volumen", "valor": 800, "transacciones": ["receptor"],
              "ventana_valor": 30, "ventana_unidad": "min"},
             {"texto": "28 usuarios concurrentes en esos dos servicios", "tipo": "concurrencia", "valor": 28,
              "transacciones": [A_, B_]}]))
        r = await c.post(f"{base}/{sid}/mensajes", json={"texto": "5 s de espera, 6.400 entre asegurar fondos y "
                                                                  "originador y 800 para receptor en 30 min; 28 usuarios"})
        d = r.json()
        L = d["ficha"]["criterios"]["lista"]
        ok(len(L) == 4, f"cuatro criterios ({len(L)})")
        t = next(x for x in L if x["tipo"] == "tiempo_respuesta")
        ok(t["metrica"] == "p90" and t["metrica_supuesta"] and t["alcance"]["tipo"] == "cada_transaccion",
           "tiempo sin medida: P90 supuesto, por transacción")
        ok("medida supuesta" in CL.describir(t), "y la ficha lo dice")
        v = next(x for x in L if x["tipo"] == "volumen" and x["alcance"]["tipo"] == "suma")
        ok(v["alcance"]["transacciones"] == [A_, B_], "«asegurar fondos» y «originator» se resuelven a sus transacciones")
        suma = correctas(A_, 30) + correctas(B_, 30)
        ok(v["resultado"]["estado"] == ("cumple" if suma >= 6400 else "no_cumple") and v["resultado"]["medido"] == suma,
           f"«entre A y B» = la SUMA: {suma} frente a 6.400 -> {v['resultado']['estado']}")
        vc = next(x for x in L if x["tipo"] == "volumen" and x["alcance"]["transacciones"] == [C_])
        ok(vc["resultado"]["estado"] == "cumple" and vc["resultado"]["medido"] == correctas(C_, 30),
           f"«800 para receptor»: {correctas(C_, 30)} correctas en 30 min -> cumple (calculado, no «lo confirma»)")
        cc = next(x for x in L if x["tipo"] == "concurrencia")
        ok(cc["resultado"]["estado"] == "cumple" and [p["medido"] for p in cc["resultado"]["por_transaccion"]] == [28, 28],
           "concurrencia de A y B por su grupo de hilos (28 y 28), no por la prueba entera (35)")
        texto = d["mensajes"][-1]["texto"]
        ok("Así los entendí:" in texto and f"• {A_}:" in texto and f"• {C_}:" in texto
           and f"{A_} + {B_} (en suma)" in texto, "«Así los entendí», por servicio y con la suma aparte")
        ok(d["mensajes"][-1]["pregunta"], "y la pregunta por la medida")
        g = {x["grupo"] for x in d["ficha"]["criterios"]["grupos"]}
        ok({A_, B_, C_} <= g, "la ficha los agrupa por transacción")

        print("== 2. «El máximo»: el tiempo se reemplaza")
        GUION.append(turno_ia("Corregido: el tiempo es el máximo.",
                              [{"texto": "5 segundos de tiempo máximo en cada servicio", "tipo": "tiempo_respuesta",
                                "metrica": "max", "operador": "<=", "valor": 5, "unidad": "s",
                                "cada_transaccion": True}], reemplaza=[t["id"]]))
        r = await c.post(f"{base}/{sid}/mensajes", json={"texto": "el máximo"})
        L = r.json()["ficha"]["criterios"]["lista"]
        tiempos = [x for x in L if x["tipo"] == "tiempo_respuesta"]
        ok(len(tiempos) == 1 and tiempos[0]["metrica"] == "max" and not tiempos[0]["metrica_supuesta"],
           "un solo criterio de tiempo, ahora sobre el máximo")
        res = tiempos[0]["resultado"]
        ok(res["estado"] == "no_cumple" and sorted(res["fallan"]) == sorted([A_, C_]) and not res.get("nota"),
           "no cumple, y nombra cuáles: A (9.221 ms) y C (21.038 ms); sin «cumple» con nota")
        ok(f"«{A_}» 9.221 ms (no cumple)" in res["texto"] and f"«{B_}» 788 ms" in res["texto"],
           "el detalle por transacción en el texto")

        print("== 3. «Es por servicio, no el total»")
        GUION.append(turno_ia("Entendido: por servicio.",
                              [{"texto": "3.200 por servicio entre asegurar fondos y originador en 30 minutos",
                                "tipo": "volumen", "valor": 3200, "transacciones": [A_, B_], "suma": False,
                                "ventana_valor": 30, "ventana_unidad": "min"}]))   # sin «reemplaza»
        r = await c.post(f"{base}/{sid}/mensajes", json={"texto": "es por servicio, no el total"})
        d = r.json()
        L = d["ficha"]["criterios"]["lista"]
        vols = [x for x in L if x["tipo"] == "volumen"]
        ok(not any(x["alcance"]["tipo"] == "suma" for x in vols) and len(vols) == 2,
           "la suma desapareció: la corrección la REEMPLAZA (no hay duplicados)")
        nv = next(x for x in vols if x["alcance"]["transacciones"] == [A_, B_])
        pt = {p["transaccion"]: p["medido"] for p in nv["resultado"]["por_transaccion"]}
        ok(pt == {A_: correctas(A_, 30), B_: correctas(B_, 30)} and nv["resultado"]["estado"] == "no_cumple",
           f"volumen por servicio, calculado: A {pt.get(A_)}, B {pt.get(B_)} frente a 3.200 -> no cumple")
        ok("Así los entendí:" in d["mensajes"][-1]["texto"], "y vuelve a confirmar la lista")
        ver = d["ficha"]["criterios"]["veredicto"]
        ok(ver["verdict"] == "NO APTO" and ver["verdicts_per_transaction"] == {A_: "NO APTO", B_: "NO APTO", C_: "NO APTO"},
           f"el veredicto sale de los criterios: {ver['verdicts_per_transaction']}")
        crit = {t["label"]: t for t in d["ficha"]["transacciones"]}
        ok(all(crit[x]["critica"] for x in (A_, B_, C_)) and "no cumple:" in crit[A_]["motivo"],
           "las tres, críticas por sus criterios")

        print("== 4. Sin servicio, nunca contra el total")
        r = await c.patch(f"{base}/{sid}", json={"criterios": {"agregar": [
            {"texto": "10.000 transacciones", "tipo": "volumen", "valor": 10000}]}})
        x = next(x for x in r.json()["ficha"]["criterios"]["lista"] if x["texto"] == "10.000 transacciones")
        ok(x["resultado"]["estado"] == "no_evaluado" and "a qué servicio" in x["resultado"]["motivo"],
           "un volumen sin servicio no se evalúa contra el total: pide a qué servicio")
        r = await c.patch(f"{base}/{sid}", json={"criterios": {"editar": [{"id": x["id"], "toda_la_prueba": True}]}})
        x = next(y for y in r.json()["ficha"]["criterios"]["lista"] if y["id"] == x["id"])
        ok(x["alcance"]["tipo"] == "global" and x["resultado"]["estado"] in ("cumple", "no_cumple"),
           "si el analista dice «toda la prueba», entonces sí")
        ok(not GUION, "se consumió el guion")


asyncio.run(main())
B.fin("B5 F (criterios v2)")
