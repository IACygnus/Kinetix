"""ETAPA H2b.2 — el calendario del mes y el estado de desfase, por HTTP.

    docker exec jmeter_backend python3 /tmp/e2e/h2b2_backend.py

Crea SUS PROPIOS datos —tres proyectos, un festivo y sus registros— y los borra
al terminar, incluso si falla a mitad (regla del reporte 38). 0 llamadas a la IA.

El mes que se arma tiene, a propósito, las cuatro situaciones de §4.1:
un festivo, un día incompleto, un día con extras y un registro desfasado.
"""
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import httpx

# H7.2 (H-D76): por defecto, la base de PRUEBAS. Nunca la de Fredy.
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
RANGO = "Proyecto H2b en rango"
AGOTAR = "Proyecto H2b por agotarse"
DESFASE = "Proyecto H2b desfasado"
NOMBRES = (RANGO, AGOTAR, DESFASE)
FESTIVO = "Festivo de prueba H2b"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def psql(sql):
    return subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", os.environ.get("KX_DB", "jmeter_analyzer_test"), "-q", "-c", sql],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True, text=True)


def limpiar():
    lista = ",".join(f"'{n}'" for n in NOMBRES)
    psql(
        f"delete from time_entries where project_id in (select id from projects where name in ({lista}));"
        f"delete from project_activity_changes where project_id in (select id from projects where name in ({lista}));"
        f"delete from project_activities where project_id in (select id from projects where name in ({lista}));"
        f"delete from projects where name in ({lista});"
        f"delete from holidays where name = '{FESTIVO}';"
    )


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        print("sesion caducada: corre refrescar_sesion.py"); return 1

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday() + 7)   # lunes de la semana pasada
    if lunes.month != hoy.month:
        print("PARADA: la semana pasada cae en otro mes; repetir mas adelante en el mes")
        return 1
    jueves_previo = lunes - timedelta(days=4)
    if jueves_previo.month != hoy.month:
        jueves_previo = lunes                        # cabe en el mismo mes igual
    martes, miercoles, jueves, viernes = (lunes + timedelta(days=i) for i in (1, 2, 3, 4))

    print("=== 0. Tres proyectos, uno por cada estado de §5.1 ===")
    cliente = cli.get(f"{API}/clients").json()[0]["id"]
    acts = cli.get(f"{API}/time/activities").json()
    a1 = acts[0]["id"]
    proy = {}
    for nombre, estimadas in ((RANGO, 40), (AGOTAR, 10), (DESFASE, 4)):
        r = cli.post(f"{API}/time/projects", json={
            "client_id": cliente, "name": nombre,
            "activities": [{"activity_id": a1, "estimated_hours": estimadas}]})
        ok(r.status_code == 201, f"'{nombre}' creado con {estimadas} h estimadas ({r.status_code})")
        proy[nombre] = r.json()["id"]

    def registrar(dia, nombre, horas, extra=False):
        r = cli.post(f"{API}/time/entries", json={
            "date": str(dia), "project_id": proy[nombre], "activity_id": a1,
            "hours": horas, "billable": True, "overtime": extra})
        ok(r.status_code == 201, f"{dia} · {horas} h en '{nombre}'{' (extra)' if extra else ''} ({r.status_code})")
        return r.json()

    print("\n=== 1. Armar el mes de §4.1 ===")
    registrar(lunes, RANGO, 8.5)                    # dia completo
    desfasado = registrar(martes, DESFASE, 8.5)     # 8,5 sobre 4 estimadas
    registrar(miercoles, RANGO, 2)                  # dia incompleto: faltan 6,5
    registrar(jueves, RANGO, 3, extra=True)         # dia con extras
    registrar(jueves_previo, AGOTAR, 9)             # 9 de 10: el 90 % justo
    ok(desfasado["over_estimate"] is True, "el registro de 8,5 sobre 4 viene marcado")
    psql(f"insert into holidays(id,date,name,user_id,kind) values "
         f"(gen_random_uuid(),'{viernes}','{FESTIVO}',null,'festivo');")
    print(f"    festivo colocado el viernes {viernes}")

    print("\n=== 2. GET /time/month ===")
    r = cli.get(f"{API}/time/month", params={"anio": hoy.year, "mes": hoy.month})
    ok(r.status_code == 200, f"responde ({r.status_code})")
    mes = r.json()
    ok(mes["first_day"] == str(date(hoy.year, hoy.month, 1)), f"primer dia {mes['first_day']}")
    ultimo = (date(hoy.year + 1, 1, 1) if hoy.month == 12
              else date(hoy.year, hoy.month + 1, 1)) - timedelta(days=1)
    ok(mes["last_day"] == str(ultimo), f"ultimo dia {mes['last_day']}")
    ok(len(mes["days"]) == ultimo.day, f"trae el mes entero: {len(mes['days'])} casillas")
    dia = {d["date"]: d for d in mes["days"]}

    print("\n--- el festivo (§4.2.7) ---")
    v = dia[str(viernes)]
    ok(v["is_holiday"] is True, "sale como festivo")
    ok(v["incomplete"] is False, "y NO se reclama aunque no tenga horas")
    ok(v["non_working_reason"] == FESTIVO, f"con su nombre: {v['non_working_reason']}")
    ok(float(v["expected_hours"]) == 0, f"no espera horas ({v['expected_hours']})")

    print("\n--- el dia incompleto (H-D24) ---")
    mi = dia[str(miercoles)]
    ok(mi["incomplete"] is True, "el miercoles esta incompleto")
    ok(float(mi["missing_hours"]) == 6.5, f"faltan {mi['missing_hours']} de 8,5")
    ok(mi["entries_count"] == 1, f"y cuenta sus registros ({mi['entries_count']})")

    print("\n--- el dia con extras (H-D17) ---")
    ju = dia[str(jueves)]
    ok(float(ju["overtime_hours"]) == 3.0, f"3 h extra separadas ({ju['overtime_hours']})")
    ok(float(ju["ordinary_hours"]) == 0, f"y ninguna ordinaria ({ju['ordinary_hours']})")
    ok(ju["incomplete"] is False, "un dia con extras NO se marca incompleto")

    print("\n--- el dia con desfase (H-D27) ---")
    ma = dia[str(martes)]
    ok(ma["has_over_estimate"] is True, "el martes avisa que toca una actividad desfasada")
    ok(dia[str(lunes)]["has_over_estimate"] is False, "el lunes, que no la toca, no avisa")
    ok(float(dia[str(lunes)]["total_hours"]) == 8.5, f"el lunes suma {dia[str(lunes)]['total_hours']}")
    ok(dia[str(lunes)]["incomplete"] is False, "y esta completo")

    print("\n--- fin de semana y totales ---")
    sabado = lunes + timedelta(days=5)
    ok(float(dia[str(sabado)]["expected_hours"]) == 0 and dia[str(sabado)]["incomplete"] is False,
       "el sabado no se reclama")
    ok(mes["pending_days"] > 0, f"cuenta los dias pendientes del mes ({mes['pending_days']})")
    futuros = [d for d in mes["days"] if d["date"] > str(hoy) and d["incomplete"]]
    ok(not futuros, f"ningun dia futuro se marca incompleto ({len(futuros)})")
    print(f"    totales: esperadas {mes['total_expected']} · ordinarias {mes['total_ordinary']}"
          f" · extra {mes['total_overtime']} · pendientes {mes['pending_days']}")

    print("\n=== 3. Los tres estados en el listado de proyectos (§5.1) ===")
    r = cli.get(f"{API}/time/projects")
    ok(r.status_code == 200, f"GET /time/projects ({r.status_code})")
    lista = {p["name"]: p for p in r.json() if p["name"] in NOMBRES}
    ok(len(lista) == 3, f"los tres proyectos estan ({len(lista)})")

    esperado = {
        RANGO:   ("en_rango",     "En rango",  13.5, 33.75, 0),   # H-D66
        AGOTAR:  ("por_agotarse", "Por agotarse",   9.0, 90.0,  0),
        DESFASE: ("desfasado",    "Desfasado +4,5 h", 8.5, 212.5, 4.5),
    }
    for nombre, (est, etiq, consumidas, pct, de_mas) in esperado.items():
        p = lista[nombre]
        ok(float(p["total_consumed_hours"]) == consumidas,
           f"'{nombre}': consumidas {p['total_consumed_hours']}")
        ok(abs(float(p["consumed_pct"]) - pct) < 0.01,
           f"'{nombre}': {float(p['consumed_pct']):.2f} % (esperado {pct})")
        ok(p["overrun_status"] == est, f"'{nombre}': estado {p['overrun_status']}")
        ok(p["overrun_label"] == etiq, f"'{nombre}': etiqueta «{p['overrun_label']}»")
        ok(float(p["overrun_hours"]) == de_mas, f"'{nombre}': horas de desfase {p['overrun_hours']}")

    print("\n--- el 90 % justo es el borde (§5.1) ---")
    ok(float(lista[AGOTAR]["consumed_pct"]) == 90.0 and lista[AGOTAR]["overrun_status"] == "por_agotarse",
       "9 de 10 ya avisa, no espera a pasarse")

    print("\n=== 4. El detalle lo repite por actividad ===")
    d = cli.get(f"{API}/time/projects/{proy[DESFASE]}").json()
    act = d["activities"][0]
    ok(act["overrun_status"] == "desfasado", f"la actividad: {act['overrun_status']}")
    ok(act["overrun_label"] == "Desfasado +4,5 h", f"su etiqueta: «{act['overrun_label']}»")
    ok(act["over_estimate"] is True, "y la marca que ya existia sigue igual (contrato de H1/H2)")
    ok(float(act["remaining_hours"]) == -4.5, f"restantes {act['remaining_hours']}")

    print("\n=== 5. La palabra «exceso» no sale del backend (H-D27) ===")
    crudo = (cli.get(f"{API}/time/projects").text
             + cli.get(f"{API}/time/projects/{proy[DESFASE]}").text
             + cli.get(f"{API}/time/month", params={"anio": hoy.year, "mes": hoy.month}).text)
    ok("exceso" not in crudo.lower(), "ni en el listado, ni en el detalle, ni en el mes")

    limpiar()
    print("\n    datos de prueba borrados")
    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("H2b.2 — CALENDARIO DEL MES Y ESTADO DE DESFASE: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


try:
    sys.exit(main())
except Exception:
    limpiar()
    raise
