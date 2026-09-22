"""ETAPA H5.2 — los datos del informe, por HTTP.

    docker exec jmeter_backend python3 /tmp/e2e/h52_informe.py

Lo que de verdad se comprueba aqui: que **las cifras del informe cuadren con las
de la consulta y las del calendario**. Una cifra, una fuente.

Crea sus propios datos y los borra al terminar, incluso si falla a mitad
(regla del reporte 38). 0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal

import httpx

# H7.2 (H-D76): por defecto, la base de PRUEBAS. Nunca la de Fredy.
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
UNO = "Proyecto H5.2 uno"
DOS = "Proyecto H5.2 dos"
NOMBRES = (UNO, DOS)
FESTIVO = "Festivo de prueba H5.2"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def psql(sql):
    subprocess.run(["psql", "-U", "jmeter_user", "-d", os.environ.get("KX_DB", "jmeter_analyzer_test"), "-q", "-c", sql],
                   env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
                   capture_output=True)


def limpiar():
    lista = ",".join(f"'{n}'" for n in NOMBRES)
    psql(f"delete from time_entries where project_id in (select id from projects where name in ({lista}));"
         f"delete from project_activity_changes where project_id in (select id from projects where name in ({lista}));"
         f"delete from project_activities where project_id in (select id from projects where name in ({lista}));"
         f"delete from projects where name in ({lista});"
         f"delete from holidays where name = '{FESTIVO}';")


def D(x):
    return Decimal(str(x))


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=180)
    r = cli.get(f"{API}/auth/me")
    if r.status_code != 200:
        print("sesion caducada: corre refrescar_sesion.py"); return 1
    yo = r.json()
    yo_nombre = yo.get("full_name") or yo["username"]

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    if lunes.month != hoy.month:
        print("PARADA: la semana pasada cae en otro mes"); return 1
    martes, miercoles, jueves, viernes = (lunes + timedelta(days=i) for i in (1, 2, 3, 4))
    primero = hoy.replace(day=1)
    ultimo = (date(hoy.year + 1, 1, 1) if hoy.month == 12
              else date(hoy.year, hoy.month + 1, 1)) - timedelta(days=1)

    clientes = cli.get(f"{API}/clients").json()
    c1 = clientes[0]
    c2 = next((c for c in clientes if c["id"] != c1["id"]), c1)
    acts = cli.get(f"{API}/time/activities").json()[:2]
    a1, a2 = acts[0], acts[1]
    otros = [u for u in cli.get(f"{API}/users").json() if u["id"] != yo["id"]]

    print("=== 0. Datos de prueba ===")
    proy = {}
    for nombre, cliente, est in ((UNO, c1, 100), (DOS, c2, 4)):
        r = cli.post(f"{API}/time/projects", json={
            "client_id": cliente["id"], "name": nombre,
            "activities": [{"activity_id": a1["id"], "estimated_hours": est},
                           {"activity_id": a2["id"], "estimated_hours": est}]})
        ok(r.status_code == 201, f"'{nombre}' creado ({r.status_code})")
        proy[nombre] = r.json()["id"]

    def reg(dia, nombre, act, horas, fact=True, extra=False, de=None):
        cuerpo = {"date": str(dia), "project_id": proy[nombre], "activity_id": act["id"],
                  "hours": horas, "billable": fact, "overtime": extra}
        if de:
            cuerpo["user_id"] = de
        rr = cli.post(f"{API}/time/entries", json=cuerpo)
        ok(rr.status_code == 201, f"{dia} {horas} h en '{nombre}' ({rr.status_code})")

    reg(lunes, UNO, a1, 8.5)
    reg(martes, UNO, a2, 4, fact=False)
    reg(miercoles, UNO, a1, 2, extra=True)
    reg(jueves, DOS, a1, 9)                       # 9 de 4: desfasado
    if otros:
        reg(lunes, UNO, a1, 6, de=otros[0]["id"])
    psql(f"insert into holidays(id,date,name,user_id,kind) values "
         f"(gen_random_uuid(),'{viernes}','{FESTIVO}',null,'festivo');")

    desde, hasta = str(primero), str(ultimo)

    # ==================== 1. LAS DIEZ SECCIONES ====================
    print("\n=== 1. Las diez secciones (H-D52) ===")
    r = cli.get(f"{API}/time/informe", params={"desde": desde, "hasta": hasta})
    ok(r.status_code == 200, f"GET /time/informe ({r.status_code})")
    if r.status_code != 200:
        print(r.text[:400]); return 1
    inf = r.json()

    for clave in ("resumen", "personas", "facturacion", "por_cliente", "por_actividad",
                  "proyectos", "mapa", "pendientes", "diarias", "detalle"):
        ok(clave in inf, f"viene «{clave}»")
    ok(len(inf["dias"]) == ultimo.day, f"las columnas son los {len(inf['dias'])} dias del mes")
    ok(inf["filtros"]["periodo"].startswith(("enero", "febrero", "marzo", "abril", "mayo",
                                             "junio", "julio", "agosto", "septiembre",
                                             "octubre", "noviembre", "diciembre")),
       f"el periodo se dice en espanol: «{inf['filtros']['periodo']}»")

    # ==================== 2. LAS CIFRAS CUADRAN ====================
    print("\n=== 2. Una cifra, una fuente ===")
    res = inf["resumen"]
    print(f"    resumen: {res['total_hours']} h · ord {res['ordinary_hours']} · "
          f"extra {res['overtime_hours']} · fact {res['billable_hours']} "
          f"({res['billable_pct']} %) · pendientes {res['pending_days']}")

    suma_personas = sum(D(p["total_hours"]) for p in inf["personas"])
    ok(suma_personas == D(res["total_hours"]),
       f"la seccion 2 suma lo mismo que el resumen ({suma_personas})")
    suma_clientes = sum(D(x["hours"]) for x in inf["por_cliente"])
    ok(suma_clientes == D(res["total_hours"]),
       f"la seccion 4 tambien ({suma_clientes})")
    suma_actividades = sum(D(x["hours"]) for x in inf["por_actividad"])
    ok(suma_actividades == D(res["total_hours"]),
       f"y la seccion 5 ({suma_actividades})")
    suma_facturacion = sum(D(x["total_hours"]) for x in inf["facturacion"])
    ok(suma_facturacion == D(res["total_hours"]),
       f"y la seccion 3 ({suma_facturacion})")
    suma_diarias = sum(D(x["total_hours"]) for x in inf["diarias"])
    ok(suma_diarias == D(res["total_hours"]),
       f"y la seccion 9, celda a celda ({suma_diarias})")
    suma_mapa = sum(D(p["total_hours"]) for p in inf["mapa"])
    ok(suma_mapa == D(res["total_hours"]), f"y el mapa de la seccion 7 ({suma_mapa})")
    suma_detalle = sum(D(x["hours"]) for x in inf["detalle"])
    ok(suma_detalle == D(res["total_hours"]), f"y el detalle de la seccion 10 ({suma_detalle})")
    ok(D(res["ordinary_hours"]) + D(res["overtime_hours"]) == D(res["total_hours"]),
       "ordinarias + extra = total")

    print("\n--- contra la CONSULTA de §5 ---")
    r = cli.get(f"{API}/time/consulta", params={"desde": desde, "hasta": hasta})
    con = r.json()
    ok(D(con["total_hours"]) == D(res["total_hours"]),
       f"el informe y la consulta dicen lo mismo ({con['total_hours']} h)")
    ok(D(con["total_overtime"]) == D(res["overtime_hours"]),
       f"y las extra tambien ({con['total_overtime']})")

    print("\n--- contra el CALENDARIO de §4 ---")
    r = cli.get(f"{API}/time/month", params={"anio": hoy.year, "mes": hoy.month})
    mes = r.json()
    mio = next((p for p in inf["personas"] if p["user_name"] == yo_nombre), None)
    ok(mio is not None, "salgo yo en la seccion 2")
    if mio:
        ok(D(mes["total_ordinary"]) == D(mio["ordinary_hours"]),
           f"mis ordinarias: calendario {mes['total_ordinary']} · informe {mio['ordinary_hours']}")
        ok(D(mes["total_overtime"]) == D(mio["overtime_hours"]),
           f"mis extra: calendario {mes['total_overtime']} · informe {mio['overtime_hours']}")
        ok(mes["pending_days"] == mio["pending_days"],
           f"mis dias pendientes: calendario {mes['pending_days']} · informe {mio['pending_days']}")
        ok(D(mes["total_expected"]) >= D(mio["expected_hours"]),
           f"la jornada del informe llega hasta hoy ({mio['expected_hours']} de {mes['total_expected']})")

    # ==================== 3. EL FESTIVO Y EL MAPA ====================
    print("\n=== 3. El mapa y el festivo (seccion 7) ===")
    i_viernes = inf["dias"].index(str(viernes))
    i_lunes = inf["dias"].index(str(lunes))
    i_sabado = inf["dias"].index(str(lunes + timedelta(days=5)))
    mia = next(p for p in inf["mapa"] if p["user_name"] == yo_nombre)
    ok(mia["estados"][i_viernes] == "festivo", f"el festivo sale como festivo ({mia['estados'][i_viernes]})")
    ok(mia["estados"][i_sabado] == "finde", "el sabado como fin de semana")
    ok(mia["estados"][i_lunes] == "trabajado", f"el lunes como trabajado ({mia['estados'][i_lunes]})")
    ok(D(mia["por_dia"][i_lunes]) == D("8.5"), f"con sus 8,5 h ({mia['por_dia'][i_lunes]})")
    futuros = [i for i, d in enumerate(inf["dias"]) if d > str(hoy)]
    ok(all(mia["estados"][i] in ("vacio", "finde", "festivo") for i in futuros),
       "ningun dia futuro se pinta como incompleto")
    ok(not any(p["date"] > str(hoy) for p in inf["pendientes"]),
       "ni aparece en los dias sin registrar (seccion 8)")
    ok(not any(p["date"] == str(viernes) for p in inf["pendientes"]),
       "y el festivo tampoco")

    # ==================== 4. EL DESFASE ====================
    print("\n=== 4. Consumido frente a estimado (seccion 6) ===")
    porp = {p["project_name"]: p for p in inf["proyectos"]}
    ok(DOS in porp and porp[DOS]["overrun_status"] == "desfasado",
       f"'{DOS}' sale desfasado ({porp.get(DOS, {}).get('overrun_status')})")
    ok(porp[DOS]["overrun_label"] == "Desfasado +1 h",
       f"con su cifra: «{porp[DOS]['overrun_label']}»")
    ok(porp[UNO]["overrun_status"] == "en_rango", f"'{UNO}' en rango")
    ok(list(porp).index(DOS) == 0 or inf["proyectos"][0]["overrun_status"] == "desfasado",
       "los desfasados salen primero")

    # ==================== 5. LOS FILTROS ====================
    print("\n=== 5. Los filtros (H-D53) ===")
    r = cli.get(f"{API}/time/informe", params={"desde": desde, "hasta": hasta,
                                               "user_id": yo["id"]})
    solo_yo = r.json()
    ok(len(solo_yo["personas"]) == 1, f"filtro de persona: 1 persona ({len(solo_yo['personas'])})")
    ok(solo_yo["filtros"]["alcance"] == yo_nombre,
       f"y el alcance pasa a ser su nombre («{solo_yo['filtros']['alcance']}»)")
    ok(D(solo_yo["resumen"]["total_hours"]) == D(mio["total_hours"]),
       f"y sus horas son las del desglose sin filtrar "
       f"({solo_yo['resumen']['total_hours']})")

    r = cli.get(f"{API}/time/informe", params={"desde": desde, "hasta": hasta,
                                               "client_id": c1["id"]})
    por_cli = r.json()
    nombres_cli = [x["name"] for x in por_cli["por_cliente"]]
    ok(nombres_cli == [c1["name"]] or c2["name"] not in nombres_cli,
       f"filtro de cliente: {nombres_cli}")

    r = cli.get(f"{API}/time/informe", params={"desde": desde, "hasta": hasta,
                                               "project_id": proy[DOS]})
    por_proy = r.json()
    ok(len(por_proy["proyectos"]) == 1 and por_proy["proyectos"][0]["project_name"] == DOS,
       "filtro de proyecto")

    r = cli.get(f"{API}/time/informe", params={"desde": desde, "hasta": hasta,
                                               "solo_facturables": True})
    fact = r.json()
    ok(D(fact["resumen"]["total_hours"]) == D(fact["resumen"]["billable_hours"]),
       f"solo facturables: todo es facturable ({fact['resumen']['total_hours']})")
    ok(D(fact["resumen"]["billable_pct"]) == D("100"),
       f"y el porcentaje es 100 ({fact['resumen']['billable_pct']})")
    ok(D(fact["personas"][0]["expected_hours"]) > 0,
       "pero la jornada esperada NO se filtra: lo que tocaba trabajar no depende del cobro")

    # ==================== 6. LOS BORDES ====================
    print("\n=== 6. Los bordes ===")
    r = cli.get(f"{API}/time/informe", params={"desde": "2001-01-01", "hasta": "2001-01-31"})
    ok(r.status_code == 200, f"un rango sin datos responde 200 ({r.status_code})")
    vacio = r.json()
    ok(D(vacio["resumen"]["total_hours"]) == 0, "con el resumen en cero")
    ok(vacio["detalle"] == [] and vacio["diarias"] == [], "y las tablas vacias, no un error")
    ok(len(vacio["dias"]) == 31, "pero con sus columnas de dias")

    r = cli.get(f"{API}/time/informe", params={"desde": hasta, "hasta": desde})
    ok(r.status_code == 400, f"rango al reves -> {r.status_code}")
    r = cli.get(f"{API}/time/informe", params={"desde": "2020-01-01", "hasta": "2026-12-31"})
    ok(r.status_code == 400, f"rango de anios -> {r.status_code}")

    limpiar()
    print("\n    datos de prueba borrados")
    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("H5.2 — LOS DATOS DEL INFORME: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


try:
    sys.exit(main())
except Exception:
    limpiar()
    raise
