"""ETAPA H3.2 — la consulta de proyectos, por HTTP.

    docker exec jmeter_backend python3 /tmp/e2e/h32_consulta.py

Crea SUS PROPIOS datos y los borra al terminar, incluso si falla a mitad
(regla del reporte 38). 0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import httpx

# H7.2 (H-D76): por defecto, la base de PRUEBAS. Nunca la de Fredy.
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
UNO = "Proyecto H3.2 uno"
DOS = "Proyecto H3.2 dos"
CORTO = "Proyecto H3.2 desfasado"
NOMBRES = (UNO, DOS, CORTO)

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def limpiar():
    lista = ",".join(f"'{n}'" for n in NOMBRES)
    subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", os.environ.get("KX_DB", "jmeter_analyzer_test"), "-q", "-c",
         f"delete from time_entries where project_id in (select id from projects where name in ({lista}));"
         f"delete from project_activity_changes where project_id in (select id from projects where name in ({lista}));"
         f"delete from project_activities where project_id in (select id from projects where name in ({lista}));"
         f"delete from projects where name in ({lista});"],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True)


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=120.0)
    r = cli.get(f"{API}/auth/me")
    if r.status_code != 200:
        print("sesion caducada: corre refrescar_sesion.py"); return 1
    yo = r.json()

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    fuera = lunes - timedelta(days=30)          # un dia FUERA del rango consultado

    clientes = cli.get(f"{API}/clients").json()
    c1 = clientes[0]
    c2 = next((c for c in clientes if c["id"] != c1["id"]), c1)
    acts = cli.get(f"{API}/time/activities").json()[:2]
    a1, a2 = acts[0], acts[1]
    otros = [u for u in cli.get(f"{API}/users").json() if u["id"] != yo["id"]]

    print("=== 0. Tres proyectos y sus horas ===")
    proy = {}
    for nombre, cliente, est in ((UNO, c1, 100), (DOS, c2, 100), (CORTO, c1, 4)):
        r = cli.post(f"{API}/time/projects", json={
            "client_id": cliente["id"], "name": nombre,
            "activities": [{"activity_id": a1["id"], "estimated_hours": est},
                           {"activity_id": a2["id"], "estimated_hours": est}]})
        ok(r.status_code == 201, f"'{nombre}' creado ({r.status_code})")
        proy[nombre] = r.json()["id"]

    def registrar(dia, nombre, act, horas, facturable=True, extra=False, de=None, notas=None):
        cuerpo = {"date": str(dia), "project_id": proy[nombre], "activity_id": act["id"],
                  "hours": horas, "billable": facturable, "overtime": extra}
        if de:
            cuerpo["user_id"] = de
        if notas:
            cuerpo["notes"] = notas
        r = cli.post(f"{API}/time/entries", json=cuerpo)
        ok(r.status_code == 201, f"{dia} · {horas} h en '{nombre}' ({r.status_code})")
        return r.json()

    # Mis horas
    registrar(lunes, UNO, a1, 8, notas="lunes en el uno")
    registrar(lunes + timedelta(days=1), UNO, a2, 4, facturable=False)
    registrar(lunes + timedelta(days=2), UNO, a1, 2, extra=True)
    registrar(lunes, DOS, a1, 3)
    registrar(lunes + timedelta(days=1), CORTO, a1, 9)      # 9 de 4: desfasado
    # Fuera del rango que se va a consultar: no debe aparecer en las horas del rango
    registrar(fuera, UNO, a1, 5, notas="fuera del rango")
    # De otra persona, si la hay
    if otros:
        registrar(lunes + timedelta(days=3), UNO, a1, 6, de=otros[0]["id"])

    desde, hasta = str(lunes), str(lunes + timedelta(days=6))

    print("\n=== 1. La consulta del rango ===")
    r = cli.get(f"{API}/time/consulta", params={"desde": desde, "hasta": hasta})
    ok(r.status_code == 200, f"GET /time/consulta ({r.status_code})")
    datos = r.json()
    mios = {p["project_name"]: p for p in datos["projects"] if p["project_name"] in NOMBRES}
    ok(len(mios) == 3, f"salen los tres proyectos ({len(mios)})")

    uno = mios[UNO]
    esperadas = 8 + 4 + 2 + (6 if otros else 0)
    ok(float(uno["hours_in_range"]) == esperadas,
       f"'{UNO}' suma {uno['hours_in_range']} h en el rango (esperado {esperadas})")
    ok(float(uno["overtime_in_range"]) == 2.0,
       f"y sus extra van aparte: {uno['overtime_in_range']}")

    print("\n--- las dos cifras de horas NO son la misma ---")
    ok(float(uno["consumed_hours"]) == esperadas + 5,
       f"lo consumido de siempre incluye el dia de fuera del rango: {uno['consumed_hours']}")
    ok(float(uno["consumed_hours"]) > float(uno["hours_in_range"]),
       "el total historico es mayor que lo del rango, como debe ser")
    ok(float(uno["estimated_hours"]) == 200.0, f"estimadas {uno['estimated_hours']}")
    ok(float(uno["remaining_hours"]) == 200.0 - float(uno["consumed_hours"]),
       f"restantes {uno['remaining_hours']}")

    print("\n--- quien registro y cuanto (H-D32) ---")
    gente = {p["user_name"]: p for p in uno["people"]}
    print(f"    {[(k, v['hours']) for k, v in gente.items()]}")
    yo_nombre = yo.get("full_name") or yo["username"]
    ok(yo_nombre in gente, f"aparezco yo ({yo_nombre})")
    ok(float(gente[yo_nombre]["hours"]) == 14.0, f"con mis 14 h del rango ({gente[yo_nombre]['hours']})")
    ok(float(gente[yo_nombre]["billable_hours"]) == 10.0,
       f"de las cuales 10 facturables ({gente[yo_nombre]['billable_hours']})")
    ok(float(gente[yo_nombre]["overtime_hours"]) == 2.0,
       f"y 2 extra ({gente[yo_nombre]['overtime_hours']})")
    ok(gente[yo_nombre]["entries_count"] == 3, f"en 3 registros ({gente[yo_nombre]['entries_count']})")
    if otros:
        ok(len(uno["people"]) == 2, f"y sale la otra persona tambien ({len(uno['people'])})")
        ok(float(uno["people"][0]["hours"]) >= float(uno["people"][1]["hours"]),
           "la gente viene ordenada de mas a menos horas")

    print("\n=== 2. El desfase se mide contra el TOTAL (§5.1) ===")
    corto = mios[CORTO]
    ok(corto["overrun_status"] == "desfasado", f"'{CORTO}': {corto['overrun_status']}")
    ok(corto["overrun_label"] == "Desfasado +1 h", f"su etiqueta: «{corto['overrun_label']}»")
    ok(mios[UNO]["overrun_status"] == "en_rango", f"'{UNO}': {mios[UNO]['overrun_status']}")
    ok(datos["overrun_count"] >= 1, f"el aviso cuenta los desfasados ({datos['overrun_count']})")
    orden = [p["overrun_status"] for p in datos["projects"]]
    ok(orden == sorted(orden, key=lambda e: {"desfasado": 0, "por_agotarse": 1}.get(e, 2)),
       f"los desfasados salen primero: {orden[:4]}")

    print("\n=== 3. Los filtros ===")
    r = cli.get(f"{API}/time/consulta", params={"desde": desde, "hasta": hasta, "client_id": c1["id"]})
    nombres = [p["project_name"] for p in r.json()["projects"] if p["project_name"] in NOMBRES]
    ok(UNO in nombres and CORTO in nombres, f"filtro por cliente: {nombres}")
    if c2["id"] != c1["id"]:
        ok(DOS not in nombres, f"y deja fuera el del otro cliente")

    r = cli.get(f"{API}/time/consulta", params={"desde": desde, "hasta": hasta,
                                                "project_id": proy[DOS]})
    ok([p["project_name"] for p in r.json()["projects"]] == [DOS], "filtro por proyecto")

    r = cli.get(f"{API}/time/consulta", params={"desde": desde, "hasta": hasta,
                                                "user_id": yo["id"]})
    u = {p["project_name"]: p for p in r.json()["projects"]}[UNO]
    ok(float(u["hours_in_range"]) == 14.0, f"filtro por persona: {u['hours_in_range']} h mias")
    ok(len(u["people"]) == 1, "y solo esa persona en el desglose")

    r = cli.get(f"{API}/time/consulta", params={"desde": desde, "hasta": hasta,
                                                "solo_desfasados": True})
    estados = {p["overrun_status"] for p in r.json()["projects"]}
    ok(estados <= {"desfasado"}, f"filtro de solo desfasados: {estados}")

    r = cli.get(f"{API}/time/consulta", params={"desde": hasta, "hasta": desde})
    ok(r.status_code == 400, f"rango al reves -> {r.status_code}")

    r = cli.get(f"{API}/time/consulta", params={"desde": "2001-01-01", "hasta": "2001-01-31"})
    ok(r.status_code == 200 and r.json()["projects"] == [],
       "un rango sin nada devuelve vacio, no un error")

    print("\n=== 4. Al ampliar la fila, los dias (H-D33) ===")
    r = cli.get(f"{API}/time/consulta/dias", params={
        "project_id": proy[UNO], "user_id": yo["id"], "desde": desde, "hasta": hasta})
    ok(r.status_code == 200, f"GET /time/consulta/dias ({r.status_code})")
    dias = r.json()
    ok(len(dias) == 3, f"mis 3 registros de ese proyecto ({len(dias)})")
    ok([d["date"] for d in dias] == sorted(d["date"] for d in dias), "ordenados por fecha")
    primero = dias[0]
    for campo in ("date", "activity_name", "hours", "billable", "notes"):
        ok(campo in primero, f"trae «{campo}»")
    ok(primero["notes"] == "lunes en el uno", f"las observaciones llegan: «{primero['notes']}»")
    ok(primero["activity_name"] == a1["name"], f"y la actividad: {primero['activity_name']}")
    ok(any(d["overtime"] for d in dias), "se ve cual fue hora extra")
    ok(any(not d["billable"] for d in dias), "y cual no se cobra")
    ok(all(d["date"] >= desde and d["date"] <= hasta for d in dias),
       "ninguno se sale del rango: el de hace un mes no esta")

    r = cli.get(f"{API}/time/consulta/dias", params={
        "project_id": proy[CORTO], "desde": desde, "hasta": hasta})
    ok(r.json()[0]["over_estimate"] is True, "el dia desfasado viene marcado")

    if otros:
        r = cli.get(f"{API}/time/consulta/dias", params={
            "project_id": proy[UNO], "desde": desde, "hasta": hasta})
        ok(len(r.json()) == 4, f"sin user_id trae los de todo el mundo ({len(r.json())})")

    limpiar()
    print("\n    datos de prueba borrados")
    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("H3.2 — LA CONSULTA DE PROYECTOS: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


try:
    sys.exit(main())
except Exception:
    limpiar()
    raise
