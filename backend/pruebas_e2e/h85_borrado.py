"""ETAPA H8.5 — el borrado de los registros de un periodo (§4.3, H-D88/H-D89).

    docker exec jmeter_backend python3 /tmp/e2e/h85_borrado.py

Es la operación más peligrosa del módulo, así que esta suite comprueba sobre
todo **lo que NO tiene que pasar**: que la previa no escriba, que un analista no
pueda, que sin casilla no se borre, que con la frase mal no se borre, que con
otro rango no se borre, y que **proyectos, actividades, clientes y estimaciones
sigan exactamente igual** después.

Y al final, la comprobación que pidió Fredy: **su base sigue con sus 24
registros**. Esta suite no la toca nunca —trabaja contra el 8002 y
`jmeter_analyzer_test` (regla 34), con el freno de siempre—, pero después de un
borrado en bloque eso se comprueba, no se supone (regla 33).

Datos `ZZTEST-H85` (regla 29), limpieza solo por ese prefijo (regla 30).
0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal

import httpx

import analista_de_pruebas

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
BASE_FREDY = os.environ.get("KX_DB_FREDY", "jmeter_analyzer_db")
# Cambia cuando Fredy carga o borra de verdad: la CARGA REAL del 24 de
# septiembre de 2026 dejó su base en 107 registros (eran 24). Se actualiza
# cuando eso pasa **a sabiendas**; que falle sin que nadie haya cargado nada es
# justo lo que esta comprobación tiene que delatar.
REGISTROS_DE_FREDY = int(os.environ.get("KX_REGISTROS_FREDY", "107"))

MARCA = "ZZTEST-H85"

# Cuántas purgas tenía la base de Fredy al empezar. Lo rellena `main()`.
PURGAS_AL_EMPEZAR = 0


# Dentro del rango que se borra, y fuera de él. El de fuera es el que demuestra
# que el DELETE está acotado.
DENTRO = ["2026-08-04", "2026-08-05", "2026-08-06"]
FUERA = "2026-09-01"
PERIODO = {"desde": "2026-08-01", "hasta": "2026-08-31"}
FRASE = "agosto de 2026"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def psql(sql, base=None):
    return subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", base or BASE, "-q", "-t", "-A", "-c", sql],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True, text=True)


def cuenta(tabla, base=None):
    return int(psql(f"select count(*) from {tabla};", base).stdout.strip() or 0)


def limpiar():
    if "test" not in BASE:
        sys.exit(f"PARADA: «{BASE}» no es una base de pruebas. No se borra nada.")
    p = f"name like '{MARCA}%'"
    psql(
        f"delete from time_entries where project_id in (select id from projects where {p});"
        f"delete from project_status_changes where project_id in (select id from projects where {p});"
        f"delete from project_activity_changes where project_id in (select id from projects where {p});"
        f"delete from project_activities where project_id in (select id from projects where {p});"
        f"delete from projects where {p};"
        # El rastro de los borrados de prueba: se quita por su rango, que es de
        # agosto de 2026 y no lo usa nadie más.
        f"delete from time_entry_purges where desde = '2026-08-01' and hasta = '2026-08-31';"
    )


def sesion_analista(cli_admin):
    """El analista compartido (regla 26). Misma función que usa `h82_estados`."""
    return analista_de_pruebas.obtener(cli_admin, API)


def main():
    # La foto de la base de Fredy ANTES de tocar nada. Es contra esto contra lo
    # que se compara al final: lo que delata un borrado accidental es que el
    # número crezca durante la pasada.
    global PURGAS_AL_EMPEZAR
    PURGAS_AL_EMPEZAR = cuenta("time_entry_purges", BASE_FREDY)

    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    cliente = cli.get(f"{API}/clients").json()[0]["id"]
    act = cli.get(f"{API}/time/activities").json()[0]["id"]
    r = cli.post(f"{API}/time/projects", json={
        "client_id": cliente, "name": f"{MARCA}-proyecto",
        "activities": [{"activity_id": act, "estimated_hours": 40}]})
    if r.status_code != 201:
        sys.exit(f"no se pudo crear el proyecto: {r.status_code} {r.text[:200]}")
    pid = r.json()["id"]

    for fecha in DENTRO + [FUERA]:
        rr = cli.post(f"{API}/time/entries", json={
            "project_id": pid, "activity_id": act, "date": fecha, "hours": "4",
            "billable": True, "overtime": False, "notes": f"{MARCA} prueba"})
        if rr.status_code != 201:
            sys.exit(f"no se pudo registrar {fecha}: {rr.status_code} {rr.text[:200]}")

    # La foto de antes. Es contra esto contra lo que se compara al final.
    antes = {t: cuenta(t) for t in ("time_entries", "projects", "project_activities",
                                    "activities", "clients", "project_activity_changes")}
    print(f"antes: {antes}")

    print("\n=== 1. La vista previa dice qué se va a borrar, y NO escribe ===")
    p = cli.get(f"{API}/time/borrado/preview", params=PERIODO)
    if not ok(p.status_code == 200, f"la previa responde {p.status_code}"):
        return 1
    v = p.json()
    ok(v["periodo"] == FRASE, f"el periodo se llama «{v['periodo']}»")
    ok(v["total_entries"] == len(DENTRO),
       f"cuenta {v['total_entries']} registros, los {len(DENTRO)} del rango")
    ok(Decimal(str(v["total_hours"])) == Decimal("12"),
       f"y {v['total_hours']} h en total")
    ok(len(v["por_persona"]) == 1 and v["por_persona"][0]["entries"] == len(DENTRO),
       f"y dice de quién: {v['por_persona']}")
    ok(v["manuales"] == len(DENTRO) and v["de_importacion"] == 0,
       f"y de dónde vinieron: {v['manuales']} a mano, {v['de_importacion']} importados")
    ok(v["frase_de_confirmacion"] == FRASE,
       f"la frase que hay que teclear: «{v['frase_de_confirmacion']}»")
    ok("pg_dump" in v["comando_copia"] and "Kinetix_pruebas" in v["comando_copia"],
       "y el comando de la copia, ya escrito")
    ok("SOLO registros de horas" in v["lo_que_no_se_borra"],
       "dice con esas palabras qué se borra")
    for palabra in ("proyecto", "actividad", "cliente", "estimaci"):
        ok(palabra in v["lo_que_no_se_borra"], f"  y que los {palabra}… sobreviven")

    ok(cuenta("time_entries") == antes["time_entries"],
       "**y la previa no escribió nada**: siguen los mismos registros")

    print("\n=== 2. Lo que NO puede borrar ===")
    cli_an = sesion_analista(cli)
    if cli_an is None:
        print("      (sin sesión de analista: corre antes h82_estados.py)")
        fallos.append("no se pudo probar el 403 del analista")
    else:
        rr = cli_an.post(f"{API}/time/borrado/confirm", json={
            **PERIODO, "confirmacion": FRASE, "copia_hecha": True})
        ok(rr.status_code == 403, f"un analista no puede borrar: {rr.status_code}")
        rr = cli_an.get(f"{API}/time/borrado/preview", params=PERIODO)
        ok(rr.status_code == 403, f"ni siquiera ver la previa: {rr.status_code}")

    casos = [
        ({"confirmacion": FRASE, "copia_hecha": False}, "sin marcar la copia"),
        ({"confirmacion": "", "copia_hecha": True}, "con la frase vacía"),
        ({"confirmacion": "agosto 2026", "copia_hecha": True},
         "con la frase casi bien («agosto 2026», sin el «de»)"),
        ({"confirmacion": "septiembre de 2026", "copia_hecha": True},
         "con la frase de OTRO periodo"),
    ]
    for cuerpo, que in casos:
        rr = cli.post(f"{API}/time/borrado/confirm", json={**PERIODO, **cuerpo})
        ok(rr.status_code == 400, f"no borra {que}: {rr.status_code}")
    # El rango cambiado: la frase ya no corresponde y tiene que rebotar.
    rr = cli.post(f"{API}/time/borrado/confirm", json={
        "desde": "2026-08-01", "hasta": "2026-09-30",
        "confirmacion": FRASE, "copia_hecha": True})
    ok(rr.status_code == 400,
       f"no borra si se cambia el rango después de revisarlo: {rr.status_code}")

    ok(cuenta("time_entries") == antes["time_entries"],
       "**después de seis intentos rechazados, no falta ni un registro**")

    print("\n=== 3. La frase, tolerante con las mayúsculas y las tildes ===")
    # Se prueba con un rango vacío para no borrar: lo que se comprueba es que
    # NO rebota por la frase, sino por no haber nada.
    rr = cli.post(f"{API}/time/borrado/confirm", json={
        "desde": "2026-07-01", "hasta": "2026-07-31",
        "confirmacion": "  JULIO  de 2026 ", "copia_hecha": True})
    ok(rr.status_code == 404,
       f"«  JULIO  de 2026 » se acepta como «julio de 2026»: {rr.status_code} "
       f"({rr.json().get('detail', '')[:60]})")

    print("\n=== 4. El borrado ===")
    rr = cli.post(f"{API}/time/borrado/confirm", json={
        **PERIODO, "confirmacion": "Agosto de 2026", "copia_hecha": True})
    if not ok(rr.status_code == 200, f"borra: {rr.status_code} {rr.text[:200]}"):
        return 1
    res = rr.json()
    ok(res["entries_deleted"] == len(DENTRO), f"{res['entries_deleted']} registros")
    ok(Decimal(str(res["hours_deleted"])) == Decimal("12"), f"{res['hours_deleted']} h")
    ok(bool(res["performed_by"]), f"y quién lo hizo: «{res['performed_by']}»")

    print("\n=== 5. Lo que queda ===")
    despues = {t: cuenta(t) for t in antes}
    print(f"después: {despues}")
    ok(despues["time_entries"] == antes["time_entries"] - len(DENTRO),
       f"se fueron exactamente los {len(DENTRO)} del rango")
    queda = psql("select count(*) from time_entries where date = '%s';" % FUERA).stdout.strip()
    ok(queda == "1", f"y el registro de fuera del rango sigue ahí: {queda}")
    for tabla in ("projects", "project_activities", "activities", "clients",
                  "project_activity_changes"):
        ok(despues[tabla] == antes[tabla],
           f"«{tabla}» sigue igual: {despues[tabla]}")

    print("\n=== 6. Queda constancia (H-D88) ===")
    fila = psql("select entries_deleted, hours_deleted, confirmation_text "
                "from time_entry_purges where desde='2026-08-01' and hasta='2026-08-31';")
    partes = fila.stdout.strip().split("|")
    if ok(len(partes) == 3, f"hay una fila en `time_entry_purges`: {fila.stdout.strip()}"):
        ok(partes[0] == str(len(DENTRO)), f"con los registros borrados: {partes[0]}")
        ok(Decimal(partes[1]) == Decimal("12"), f"y las horas: {partes[1]}")
        ok(partes[2] == "Agosto de 2026",
           f"y lo que se tecleó, literal: «{partes[2]}»")

    print("\n=== 7. La base de Fredy, intacta ===")
    suyos = cuenta("time_entries", BASE_FREDY)
    ok(suyos == REGISTROS_DE_FREDY,
       f"«{BASE_FREDY}» sigue con sus {suyos} registros "
       f"(se esperaban {REGISTROS_DE_FREDY})")
    # Lo que se comprueba es que **esta suite** no borre en la base de Fredy,
    # no que allí no se haya borrado nunca: la CARGA REAL del 24 de septiembre
    # de 2026 dejó una purga suya, la de septiembre. Lo que delata un borrado
    # accidental es que el número CREZCA durante la pasada, así que se compara
    # contra el de antes de empezar, no contra cero.
    purgas_suyas = cuenta("time_entry_purges", BASE_FREDY)
    ok(purgas_suyas == PURGAS_AL_EMPEZAR,
       f"y sin ningún borrado nuevo: {purgas_suyas} "
       f"(las mismas {PURGAS_AL_EMPEZAR} de antes de empezar)")

    print()
    if fallos:
        print(f"=== {len(fallos)} FALLO(S) ===")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("=== TODO PASA ===")
    return 0


if __name__ == "__main__":
    codigo = 1
    try:
        codigo = main()
    finally:
        limpiar()
    sys.exit(codigo)
