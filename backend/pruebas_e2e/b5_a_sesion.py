"""BLOQUE 5, parte A — la sesión y la ficha del «Analista IA», sin IA.

    docker exec -e PYTHONPATH=/app/pruebas_e2e jmeter_backend python3 /app/pruebas_e2e/b5_a_sesion.py

Contra el 8002 y la base de pruebas (regla 34). Las sesiones que deja llevan el
proyecto «ZZTEST-B5 …» (regla 29). Comprueba:

  1. la ficha inicial con el JTL de ZZTEST-R1: fases y concentración iguales a
     las que calcula el motor, criterios `sin_declarar`, contador 0 de N;
  2. los criterios de tiempo, disponibilidad, concurrencia y proceso con el
     resultado del SERVIDOR (recalculado aquí, a mano, sobre el JTL);
  3. los que encajan con el motor, traducidos a sus claves; la marca crítica;
  4. «no hay criterios acordados»; las casillas a mano; ambiente y versión;
  5. PATCH inválidos (422) y que nadie ve la sesión de otro;
  6. la tolerancia del motor a criterios ausentes (en proceso).
"""
import sys

import pandas as pd

import b5_comun as B
from b5_comun import ok

sys.path.insert(0, "/app")
from app.services.ai import criterios as CR   # noqa: E402
from app.services.ai import fases as F   # noqa: E402
from app.services.ai.gemini import compute_per_transaction_verdicts, compute_verdict   # noqa: E402
from app.services.ai.resumen_serie import _ok   # noqa: E402
from app.services.jtl.jtl_parser import JTLParser   # noqa: E402

admin = B.cliente()
A = B.API + "/analista/sesiones"

print("== 1. La ficha inicial")
r = B.crear(admin)
ok(r.status_code == 201, f"crear la sesión -> 201 ({r.status_code})")
s = r.json()
sid, f = s["id"], s["ficha"]
p = JTLParser(B.JTL_R1)
p.parse()
df = p.df_main if p.df_main is not None and len(p.df_main) else p.df
fa = F.calcular(df)
ok(f["fases"]["subida_hasta_s"] == fa.subida_hasta_s and f["fases"]["bajada_desde_s"] == fa.bajada_desde_s
   and f["fases"]["max_usuarios"] == fa.max_hilos,
   f"fases iguales a las del motor (subida {fa.subida_hasta_s}, bajada {fa.bajada_desde_s}, {fa.max_hilos} usuarios)")
ok(f["fases"]["texto"].startswith("FASES DE LA PRUEBA") and "2:19" in f["fases"]["texto"], "el texto de las fases (2:19)")
okmask = _ok(df)
conc = F.concentracion(df[~okmask]["timestamp"], fa, "fallos")
ok(f["fallos"]["concentracion"] == conc, "la concentración de fallos es la del motor")
ok(f["fallos"]["total"] == int((~okmask).sum()) == 1988, "1.988 fallos")
ok("HECHOS DE LA PRUEBA" in f["hechos"], "los hechos de la prueba")
ok(f["criterios"]["estado"] == "sin_declarar", "criterios sin_declarar")
ok(f["listo"]["puede_generar"] is False and f["listo"]["faltan"] == ["criterios"]
   and f["listo"]["n"] == 0 and f["listo"]["obligatorios"]["total"] == 1, f"listo 0 de {f['listo']['m']}")
con_err = sorted(t["label"] for t in f["transacciones"] if t["errores"] > 0)
ok(sorted(t["label"] for t in f["transacciones"] if t["informe"]) == con_err,
   f"sin criterios, informe propio = las que tienen errores ({len(con_err)})")
ok(s["mensajes"] == [] or all(m["rol"] in ("ia", "analista", "sistema") for m in s["mensajes"]), "mensajes")
from datetime import datetime   # noqa: E402
from app.services.zona_informe import a_informe   # noqa: E402
creada = datetime.fromisoformat(s["creada"])
ok(abs((creada - a_informe(datetime.utcnow())).total_seconds()) < 120
   and abs((datetime.fromisoformat(s["mensajes"][0]["momento"]) - creada).total_seconds()) < 120,
   f"las horas de la API, en hora de informe (creada {s['creada']})")

print("== 2. Criterios: el resultado lo calcula el servidor")
n_ok = int(okmask.sum())
r = admin.patch(f"{A}/{sid}", json={"criterios": {"agregar": [
    {"texto": "El 90 % en menos de 500 ms", "tipo": "tiempo_respuesta", "metrica": "p90", "operador": "<=",
     "valor": 500, "unidad": "ms"},
    {"texto": "Disponibilidad del 99,5 %", "tipo": "disponibilidad_o_error", "metrica": "disponibilidad",
     "operador": ">=", "valor": 99.5, "unidad": "%"},
    {"texto": "Menos del 50 % de errores en Get_Booking_Id", "tipo": "disponibilidad_o_error",
     "metrica": "tasa_error", "operador": "<", "valor": 50, "transaccion": "4. get_booking_id"},
    {"texto": "Procesar 2.000 registros en menos de 5 minutos", "tipo": "proceso",
     "metrica": "registros_en_tiempo", "operador": "<=", "valor": 5, "unidad": "min", "cantidad": 2000},
    {"texto": "Procesar 20.000 registros en menos de 30 minutos", "tipo": "proceso", "cantidad": 20000,
     "valor": 30, "unidad": "min"},
    {"texto": "Auth en menos de 1 s", "tipo": "tiempo_respuesta", "valor": 1, "unidad": "s",
     "transaccion": "1. Auth"},
    {"texto": "5 usuarios", "tipo": "concurrencia", "valor": 5},
    {"texto": "Caudal de 20 por segundo", "tipo": "caudal", "valor": 20},
    {"texto": "Que el cliente lo apruebe", "tipo": "otro"},
    {"texto": "Login en menos de 2 s", "tipo": "tiempo_respuesta", "valor": 2, "unidad": "s",
     "transaccion": "Login que no existe"},
    {"texto": "Ninguna transacción por encima del 5 % de errores", "tipo": "disponibilidad_o_error",
     "metrica": "tasa_error", "valor": 5, "cada_transaccion": True},
]}})
ok(r.status_code == 200, f"PATCH con 11 criterios -> 200 ({r.status_code})")
f = r.json()["ficha"]
L = {c["texto"]: c for c in f["criterios"]["lista"]}
res = lambda t: L[t]["resultado"]
p90 = float(df["elapsed"].quantile(0.90))
ok(res("El 90 % en menos de 500 ms")["estado"] == "cumple" and abs(res("El 90 % en menos de 500 ms")["medido"] - p90) < 0.01,
   f"P90 global {p90:.0f} ms ≤ 500 -> cumple")
ok("1 de 6 transacciones" in (res("El 90 % en menos de 500 ms")["nota"] or ""), "la nota: cuántas no lo cumplen por su cuenta")
disp = 100 * okmask.mean()
ok(res("Disponibilidad del 99,5 %")["estado"] == "no_cumple" and abs(res("Disponibilidad del 99,5 %")["medido"] - disp) < 0.01,
   f"disponibilidad {disp:.2f} % < 99,5 -> no_cumple")
g = df[df["label"] == "4. Get_Booking_Id"]
tasa_g = 100 * (1 - _ok(g).mean())
c3 = L["Menos del 50 % de errores en Get_Booking_Id"]
ok(c3["alcance"]["transaccion"] == "4. Get_Booking_Id", "el nombre de la transacción se normaliza al del JTL")
ok(c3["resultado"]["estado"] == "no_cumple" and abs(c3["resultado"]["medido"] - tasa_g) < 0.01,
   f"tasa de error de Get_Booking_Id {tasa_g:.2f} % -> no_cumple")
t0 = df["timestamp"].min()
okdf = df[okmask]
fin = ((okdf["timestamp"] - t0).dt.total_seconds() + okdf["elapsed"] / 1000).sort_values().to_numpy()
t2000 = fin[1999] / 60
r4 = res("Procesar 2.000 registros en menos de 5 minutos")
ok(r4["estado"] == ("cumple" if t2000 <= 5 else "no_cumple") and abs(r4["medido"] - round(t2000, 2)) < 0.01,
   f"proceso: las 2.000 primeras correctas en {t2000:.2f} min -> {r4['estado']}")
r5 = res("Procesar 20.000 registros en menos de 30 minutos")
ok(r5["estado"] == "lo_confirma_el_analista" and r5["medido"] == n_ok and r5["motivo"],
   f"proceso: {n_ok} correctas < 20.000 -> lo confirma el analista")
ok(res("Auth en menos de 1 s")["estado"] == "cumple", "Auth P90 < 1 s -> cumple")
ok(res("5 usuarios")["estado"] == "cumple" and res("5 usuarios")["medido"] == 5, "concurrencia 5 -> cumple")
ok(res("Caudal de 20 por segundo")["estado"] == "no_cumple", "caudal 16/s < 20 -> no_cumple")
ok(res("Que el cliente lo apruebe")["estado"] == "lo_confirma_el_analista", "«otro» -> lo confirma el analista")
ok(res("Login en menos de 2 s")["estado"] == "no_evaluado" and "no está en el JTL" in res("Login en menos de 2 s")["motivo"],
   "transacción inexistente -> no_evaluado con motivo")
cada = L["Ninguna transacción por encima del 5 % de errores"]
peor = 100 * (1 - _ok(df[df["label"] == "6. Delete_Booking_Id"]).mean())
ok(cada["alcance"]["tipo"] == "cada_transaccion" and cada["operador"] == "<=", "«cada transacción»: alcance y operador por defecto")
ok(cada["resultado"]["estado"] == "no_cumple" and abs(cada["resultado"]["medido"] - peor) < 0.01
   and "3 de 6 no lo cumplen" in cada["resultado"]["nota"], f"«cada transacción»: la peor, Delete ({peor:.2f} %), y cuáles no")
ok(f["criterios"]["estado"] == "declarados" and f["listo"]["puede_generar"], "declarados -> se puede generar")

print("== 3. Los que encajan con el motor")
from app.services.analista import ficha as FI   # noqa: E402
m = FI.motor(f)
ok(m.get("response_time") == 500 and m.get("availability") == 99.5 and m.get("concurrency") == 5,
   f"claves del motor: {{response_time 500, availability 99.5, concurrency 5}} ({ {k: m.get(k) for k in ('response_time', 'availability', 'concurrency')} })")
ok(m["per_transaction"]["1. Auth"] == {"response_time": 1000.0}
   and m["per_transaction"]["4. Get_Booking_Id"] == {"availability": 50.0}, "per_transaction de Auth y Get_Booking_Id")
ok(not L["Caudal de 20 por segundo"]["en_motor"] and L["Disponibilidad del 99,5 %"]["en_motor"], "en_motor marcado")
ok(all(t["informe"] == t["critica"] for t in f["transacciones"]), "con criterios, informe propio = las críticas")
crit = {t["label"]: t for t in f["transacciones"]}
ok(crit["6. Delete_Booking_Id"]["verdict"] == "NO APTO" and crit["1. Auth"]["verdict"] == "APTO",
   "veredictos por transacción del motor")

print("== 4. Casillas, contexto, «no hay criterios»")
r = admin.patch(f"{A}/{sid}", json={"transacciones": {"1. Auth": True}, "contexto": {"ambiente": "QA"}})
f = r.json()["ficha"]
auth = next(t for t in f["transacciones"] if t["label"] == "1. Auth")
ok(auth["informe"] and auth["informe_origen"] == "analista", "la casilla a mano se queda")
ok(next(p for p in f["pendientes"] if p["id"] == "ambiente")["estado"] == "resuelto" and f["listo"]["n"] == 2,
   f"ambiente resuelto: listo {f['listo']['n']} de {f['listo']['m']}")
r = admin.patch(f"{A}/{sid}", json={"criterios": {"ninguno_acordado": True}})
ok(r.status_code == 422, "«ninguno acordado» con criterios en la lista -> 422")
ids = [c["id"] for c in f["criterios"]["lista"]]
r = admin.patch(f"{A}/{sid}", json={"criterios": {"quitar": ids}})
f = r.json()["ficha"]
ok(f["criterios"]["estado"] == "sin_declarar" and not f["listo"]["puede_generar"], "sin criterios -> sin_declarar otra vez")
ok(all(t["critica"] == t["pico"] and t["motivo"] == t["motivo_pico"] and t["verdict"] is None
       for t in f["transacciones"]), "sin criterios, la marca crítica vuelve a ser la del pico, con su motivo")
r = admin.patch(f"{A}/{sid}", json={"criterios": {"ninguno_acordado": True}})
f = r.json()["ficha"]
ok(f["criterios"]["estado"] == "no_hay_criterios_acordados" and f["listo"]["puede_generar"], "no_hay_criterios_acordados -> se puede generar")
ok(sorted(t["label"] for t in f["transacciones"] if t["informe"] and t["informe_origen"] == "auto") == con_err,
   "sin criterios acordados, informe propio = las que tienen errores")
m = FI.motor(f)
ok(not CR.tiene_numericos(m) and not CR.evaluables(m), "sin criterios: el motor no ve ninguno")

print("== 5. PATCH inválidos y visibilidad")
for nombre, cuerpo in (
        ("cambiar las cifras", {"cifras": {"peticiones": 1}}),
        ("cambiar las fases", {"fases": {}}),
        ("criterio con resultado", {"criterios": {"agregar": [{"texto": "x", "tipo": "otro", "resultado": {"estado": "cumple"}}]}}),
        ("editar el resultado", {"criterios": {"editar": [{"id": "c1", "resultado": "cumple"}]}}),
        ("tipo inventado", {"criterios": {"agregar": [{"texto": "x", "tipo": "magia"}]}}),
        ("operador inventado", {"criterios": {"agregar": [{"texto": "x", "tipo": "caudal", "operador": "~"}]}}),
        ("unidad que no va", {"criterios": {"agregar": [{"texto": "x", "tipo": "tiempo_respuesta", "unidad": "%"}]}}),
        ("valor negativo", {"criterios": {"agregar": [{"texto": "x", "tipo": "caudal", "valor": -3}]}}),
        ("concurrencia por cada transacción", {"criterios": {"agregar": [{"texto": "x", "tipo": "concurrencia",
                                                                         "valor": 5, "cada_transaccion": True}]}}),
        ("casilla de una transacción que no existe", {"transacciones": {"No existe": True}}),
        ("quitar una línea que no existe", {"relato": {"quitar": ["r99"]}}),
        ("descartar los criterios", {"pendientes": {"descartar": ["criterios"]}}),
        ("línea vacía", {"relato": {"agregar": [""]}}),
        ("texto de 501", {"relato": {"agregar": ["x" * 501]}})):
    r = admin.patch(f"{A}/{sid}", json=cuerpo)
    ok(r.status_code == 422, f"{nombre} -> 422 ({r.status_code})")
ok(admin.get(f"{A}/{sid}").json()["ficha"]["cifras"]["peticiones"] == 4811, "las cifras siguen intactas")

# confirmar a mano solo un «lo confirma el analista»
admin.patch(f"{A}/{sid}", json={"criterios": {"ninguno_acordado": False}})
r = admin.patch(f"{A}/{sid}", json={"criterios": {"agregar": [
    {"texto": "Que el cliente lo apruebe", "tipo": "otro"},
    {"texto": "P90 bajo 500", "tipo": "tiempo_respuesta", "valor": 500}]}})
lista = r.json()["ficha"]["criterios"]["lista"]
otro = next(c for c in lista if c["tipo"] == "otro")
tiempo = next(c for c in lista if c["tipo"] == "tiempo_respuesta")
r = admin.patch(f"{A}/{sid}", json={"criterios": {"editar": [{"id": otro["id"], "confirmacion": "cumple"}]}})
ok(r.status_code == 200 and next(c for c in r.json()["ficha"]["criterios"]["lista"] if c["id"] == otro["id"])["confirmacion"] == "cumple",
   "confirmar a mano un «lo confirma el analista»")
r = admin.patch(f"{A}/{sid}", json={"criterios": {"editar": [{"id": tiempo["id"], "confirmacion": "no_cumple"}]}})
ok(r.status_code == 422, "confirmar a mano uno que calcula el servidor -> 422")
r = admin.patch(f"{A}/{sid}", json={"relato": {"agregar": ["Era una ronda corta"]}})
rid = r.json()["ficha"]["relato"][0]["id"]
r = admin.patch(f"{A}/{sid}", json={"relato": {"editar": [{"id": rid, "texto": "Era una ronda corta de 5 min"}]}})
ok(r.json()["ficha"]["relato"][0]["texto"] == "Era una ronda corta de 5 min", "editar una línea del relato")
r = admin.patch(f"{A}/{sid}", json={"relato": {"quitar": [rid]}})
ok(r.json()["ficha"]["relato"] == [], "quitar una línea del relato")

ana = B.cliente("zztest_b5_analista_a", "analyst")
anb = B.cliente("zztest_b5_analista_b", "analyst")
vis = B.cliente("zztest_b5_viewer", "viewer")
r = B.crear(ana, proyecto="ZZTEST-B5 de A")
ok(r.status_code == 201, "el analista A crea su sesión")
sa = r.json()["id"]
ok(anb.get(f"{A}/{sa}").status_code == 404, "el analista B no la ve (404)")
ok(anb.patch(f"{A}/{sa}", json={"contexto": {"ambiente": "x"}}).status_code == 404, "ni la toca (404)")
ok(all(x["id"] != sa for x in anb.get(A).json()), "ni le sale en su lista")
ok(any(x["id"] == sa for x in ana.get(A).json()), "a A sí le sale")
ok(admin.get(f"{A}/{sa}").status_code == 200, "el admin la ve")
ok(vis.get(A).status_code == 403, "un viewer no entra (403)")
ok(ana.get(f"{A}/no-es-un-uuid").status_code == 404, "id que no es uuid -> 404")

print("== 6. Tolerancia del motor a criterios ausentes")
sum_df = p.get_summary_table_data()
viejo = {"concurrency": 5, "response_time": 500, "availability": 99.5}
ok(CR.bloque_completo(viejo).count("Tiempo de respuesta máximo: 500 ms") == 1 and "99,5%" in CR.bloque_completo(viejo),
   "el flujo de siempre: el bloque de criterios no cambia")
solo_rt = {"response_time": 500, "analista": {}}
ok("Disponibilidad" not in CR.bloque_completo(solo_rt) and "500 ms" in CR.bloque_completo(solo_rt),
   "del analista solo con tiempo: no se inventa la disponibilidad del 99 %")
ok(CR.criterios_efectivos(solo_rt, "1. Auth") == (500.0, None, False), "criterios_efectivos: disponibilidad None")
ok(CR.criterios_efectivos(viejo | {"response_time": None}, "1. Auth")[0] == 2000.0,
   "sin la marca del analista, el defecto de siempre (2.000 ms)")
v = compute_per_transaction_verdicts(sum_df, solo_rt)["verdicts_per_transaction"]
ok(v["6. Delete_Booking_Id"] == "APTO", "con solo tiempo, el 96 % de errores no da NO APTO (no se declaró)")
ok(compute_per_transaction_verdicts(sum_df, {"analista": {}}) == {}, "sin ninguno: no hay veredictos")
ok(compute_verdict({"avg_response_time": 220, "error_rate": 41}, {"analista": {}, "response_time": 500}) == "APTO",
   "veredicto global con solo tiempo")
ok(compute_verdict({"avg_response_time": 220, "error_rate": 41}, viejo) == "NO APTO", "veredicto de siempre")
ok(not CR.evaluables({"analista": {}, "concurrency": 5}) and CR.evaluables(viejo), "evaluables")
ok(CR.bloque_de_transaccion({"analista": {}, "concurrency": 5}, "1. Auth") == "", "bloque por transacción vacío sin límites")

B.fin("B5 A (sesión y ficha)")
