"""ETAPA H2.2 — el backend del registro de horas, por HTTP.

    docker exec -e KX_PWD=... jmeter_backend python3 /tmp/e2e/h22_backend.py

Crea SUS PROPIOS datos (un proyecto y sus registros) y los borra al terminar,
incluso si falla a mitad. 0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import httpx

# H7.2 (H-D76): por defecto, la base de PRUEBAS. Nunca la de Fredy.
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
PROYECTO = "Proyecto H2.2"
CERRADO = "Proyecto H2.2 cerrado"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def limpiar():
    sql = (
        f"delete from time_entries where project_id in (select id from projects where name in ('{PROYECTO}','{CERRADO}'));"
        f"delete from project_activity_changes where project_id in (select id from projects where name in ('{PROYECTO}','{CERRADO}'));"
        f"delete from project_activities where project_id in (select id from projects where name in ('{PROYECTO}','{CERRADO}'));"
        f"delete from projects where name in ('{PROYECTO}','{CERRADO}');"
        "delete from holidays where name = 'Festivo de prueba H2.2';"
    )
    subprocess.run(["psql", "-U", "jmeter_user", "-d", os.environ.get("KX_DB", "jmeter_analyzer_test"), "-q", "-c", sql],
                   env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
                   capture_output=True)


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        print("sesion caducada: corre refrescar_sesion.py"); return 1

    yo = cli.get(f"{API}/auth/me").json()
    # Lunes de la semana pasada, para tener días ya cumplidos y no futuros.
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday() + 7)

    print("=== 0. Preparar un proyecto de prueba ===")
    cliente = cli.get(f"{API}/clients").json()[0]["id"]
    acts = cli.get(f"{API}/time/activities").json()[:2]
    a1, a2 = acts[0]["id"], acts[1]["id"]
    r = cli.post(f"{API}/time/projects", json={
        "client_id": cliente, "name": PROYECTO,
        "activities": [{"activity_id": a1, "estimated_hours": 10},
                       {"activity_id": a2, "estimated_hours": 40}]})
    ok(r.status_code == 201, f"proyecto de prueba creado ({r.status_code})")
    proy = r.json()["id"]

    print("\n=== 1. Alta correcta ===")
    r = cli.post(f"{API}/time/entries", json={
        "date": str(lunes), "project_id": proy, "activity_id": a2,
        "hours": 8.5, "billable": True, "overtime": False, "notes": "Primer registro"})
    ok(r.status_code == 201, f"registrar 8,5 h ({r.status_code})")
    e1 = r.json()
    ok(e1["over_estimate"] is False, "no marca exceso: 8,5 de 40")
    ok(e1["created_by"] == yo["id"], "created_by guarda quien registro")
    ok(e1["client_name"] and e1["project_name"] and e1["activity_name"],
       f"resuelve cliente/proyecto/actividad: {e1['client_name']} · {e1['project_name']} · {e1['activity_name']}")

    print("\n=== 2. Superar lo estimado: avisa pero GUARDA (H-D16) ===")
    r = cli.get(f"{API}/time/projects/{proy}/disponibilidad")
    disp = {d["activity_id"]: d for d in r.json()}
    ok(float(disp[a1]["remaining_hours"]) == 10.0, "la actividad de 10 h tiene 10 restantes")
    r = cli.post(f"{API}/time/entries", json={
        "date": str(lunes + timedelta(days=1)), "project_id": proy, "activity_id": a1,
        "hours": 12, "billable": False, "overtime": False})
    ok(r.status_code == 201, f"12 h sobre una estimacion de 10 SE GUARDA ({r.status_code})")
    e2 = r.json()
    ok(e2["over_estimate"] is True, "y viene marcada como exceso")
    r = cli.get(f"{API}/time/projects/{proy}/disponibilidad")
    disp = {d["activity_id"]: d for d in r.json()}
    ok(float(disp[a1]["remaining_hours"]) == -2.0, f"restantes en negativo: {disp[a1]['remaining_hours']}")
    ok(disp[a1]["over_estimate"] is True, "la disponibilidad tambien lo marca")

    print("\n=== 3. El detalle del proyecto refleja lo consumido (H-D22) ===")
    d = cli.get(f"{API}/time/projects/{proy}").json()
    por_act = {a["activity_id"]: a for a in d["activities"]}
    ok(float(por_act[a1]["consumed_hours"]) == 12.0, f"consumido {por_act[a1]['consumed_hours']}")
    ok(por_act[a1]["over_estimate"] is True, "el detalle marca el exceso")
    ok(float(d["total_consumed_hours"]) == 20.5, f"total consumido {d['total_consumed_hours']}")

    print("\n=== 4. Los errores esperados ===")
    casos = [
        ("paso invalido (0,3)", {"date": str(lunes), "project_id": proy, "activity_id": a2,
                                 "hours": 0.3, "billable": True}, 422),
        ("fecha futura (H-D21)", {"date": str(hoy + timedelta(days=1)), "project_id": proy,
                                  "activity_id": a2, "hours": 1, "billable": True}, 422),
        ("horas cero", {"date": str(lunes), "project_id": proy, "activity_id": a2,
                        "hours": 0, "billable": True}, 422),
    ]
    for texto, cuerpo, esperado in casos:
        r = cli.post(f"{API}/time/entries", json=cuerpo)
        ok(r.status_code == esperado, f"{texto} -> {r.status_code}")
    # Actividad que no esta en el proyecto
    otras = [a["id"] for a in cli.get(f"{API}/time/activities").json() if a["id"] not in (a1, a2)]
    if otras:
        r = cli.post(f"{API}/time/entries", json={
            "date": str(lunes), "project_id": proy, "activity_id": otras[0],
            "hours": 1, "billable": True})
        ok(r.status_code == 400, f"actividad que no esta en el proyecto -> {r.status_code}")

    print("\n=== 5. Proyecto cerrado (H-D20) ===")
    r = cli.post(f"{API}/time/projects", json={
        "client_id": cliente, "name": CERRADO,
        "activities": [{"activity_id": a1, "estimated_hours": 5}]})
    proy_c = r.json()["id"]
    cli.post(f"{API}/time/projects/{proy_c}/cerrar")
    r = cli.post(f"{API}/time/entries", json={
        "date": str(lunes), "project_id": proy_c, "activity_id": a1,
        "hours": 1, "billable": True})
    ok(r.status_code == 409, f"un proyecto cerrado no admite registros -> {r.status_code}")
    ok("cerrado" in r.text, "y el motivo lo dice")

    print("\n=== 6. Horas extra (H-D17) ===")
    r = cli.post(f"{API}/time/entries", json={
        "date": str(lunes + timedelta(days=2)), "project_id": proy, "activity_id": a2,
        "hours": 3, "billable": True, "overtime": True})
    ok(r.status_code == 201, f"registrar 3 h extra ({r.status_code})")
    d = cli.get(f"{API}/time/projects/{proy}").json()
    ok(float(d["total_consumed_hours"]) == 23.5,
       f"las extra CONSUMEN la estimacion: {d['total_consumed_hours']}")

    print("\n=== 7. La semana (H-D14) ===")
    r = cli.get(f"{API}/time/week", params={"fecha": str(lunes)})
    ok(r.status_code == 200, f"GET /time/week ({r.status_code})")
    w = r.json()
    ok(w["week_start"] == str(lunes), f"empieza el lunes {w['week_start']}")
    ok(len(w["days"]) == 7, f"siete dias ({len(w['days'])})")
    por_fecha = {d["date"]: d for d in w["days"]}
    l = por_fecha[str(lunes)]
    ok(float(l["expected_hours"]) == 8.5 and float(l["ordinary_hours"]) == 8.5,
       f"lunes: esperadas {l['expected_hours']} · ordinarias {l['ordinary_hours']}")
    ok(l["incomplete"] is False, "el lunes esta completo")
    ma = por_fecha[str(lunes + timedelta(days=1))]
    ok(float(ma["ordinary_hours"]) == 12.0 and ma["incomplete"] is False, "el martes, con 12 h, no falta")
    mi = por_fecha[str(lunes + timedelta(days=2))]
    ok(float(mi["overtime_hours"]) == 3.0, f"el miercoles tiene 3 h extra separadas ({mi['overtime_hours']})")
    ok(mi["incomplete"] is False, "y un dia con extras NO se marca incompleto (H-D17)")
    ju = por_fecha[str(lunes + timedelta(days=3))]
    ok(ju["incomplete"] is True and float(ju["missing_hours"]) == 8.5,
       f"el jueves, sin registros, falta {ju['missing_hours']}")
    sa = por_fecha[str(lunes + timedelta(days=5))]
    ok(float(sa["expected_hours"]) == 0 and sa["incomplete"] is False, "el sabado no se reclama")
    print(f"    totales: esperadas {w['total_expected']} · ordinarias {w['total_ordinary']} · extra {w['total_overtime']}")

    print("\n=== 8. Un festivo no se reclama (§4.2.7) ===")
    viernes = lunes + timedelta(days=4)
    subprocess.run(["psql", "-U", "jmeter_user", "-d", os.environ.get("KX_DB", "jmeter_analyzer_test"), "-q", "-c",
                    f"insert into holidays(id,date,name,user_id,kind) values "
                    f"(gen_random_uuid(),'{viernes}','Festivo de prueba H2.2',null,'festivo');"],
                   env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
                   capture_output=True)
    w = cli.get(f"{API}/time/week", params={"fecha": str(lunes)}).json()
    v = {d["date"]: d for d in w["days"]}[str(viernes)]
    ok(v["is_holiday"] is True, "el viernes sale como festivo")
    ok(v["incomplete"] is False, "y NO se reclama aunque no tenga horas")
    ok(v["non_working_reason"] == "Festivo de prueba H2.2", f"con su nombre: {v['non_working_reason']}")

    print("\n=== 9. Dias pendientes (H-D18) ===")
    r = cli.get(f"{API}/time/pending-days",
                params={"desde": str(lunes), "hasta": str(lunes + timedelta(days=6))})
    ok(r.status_code == 200, f"GET /time/pending-days ({r.status_code})")
    pend = r.json()
    fechas = [p["date"] for p in pend]
    print(f"    pendientes: {fechas}")
    ok(str(lunes + timedelta(days=3)) in fechas, "el jueves esta pendiente")
    ok(str(viernes) not in fechas, "el festivo NO esta pendiente")
    ok(str(lunes + timedelta(days=2)) not in fechas, "el dia con extras tampoco")
    ok(str(lunes + timedelta(days=5)) not in fechas, "ni el sabado")
    if pend:
        ok(pend[0]["week_start"] == str(lunes), f"trae el lunes de su semana para el enlace")

    print("\n=== 10. Editar y borrar (H-D19, §8) ===")
    r = cli.put(f"{API}/time/entries/{e1['id']}", json={"hours": 6, "notes": "editado"})
    ok(r.status_code == 200 and float(r.json()["hours"]) == 6.0, f"editar las horas ({r.status_code})")
    r = cli.put(f"{API}/time/entries/{e1['id']}", json={"hours": 0.3})
    ok(r.status_code == 422, f"editar con un paso invalido -> {r.status_code}")
    r = cli.delete(f"{API}/time/entries/{e1['id']}")
    ok(r.status_code == 204, f"el admin borra ({r.status_code})")

    print("\n=== 11. Registrar por otro: solo admin (H-D13) ===")
    otros = [u for u in cli.get(f"{API}/users").json() if u["id"] != yo["id"]]
    if otros:
        r = cli.post(f"{API}/time/entries", json={
            "user_id": otros[0]["id"], "date": str(lunes), "project_id": proy,
            "activity_id": a2, "hours": 2, "billable": True})
        ok(r.status_code == 201, f"el admin registra por {otros[0]['username']} ({r.status_code})")
        e = r.json()
        ok(e["user_id"] == otros[0]["id"] and e["created_by"] == yo["id"],
           "las horas son de esa persona y created_by es quien las registro")
    else:
        print("OMIT  | no hay otro usuario para probarlo")

    limpiar()
    print("\n    datos de prueba borrados")
    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("H2.2 — BACKEND DEL REGISTRO DE HORAS: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


try:
    sys.exit(main())
except Exception:
    limpiar()
    raise
