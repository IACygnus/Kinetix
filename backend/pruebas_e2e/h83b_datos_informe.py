"""ETAPA H8.3b — datos de sección 6 para las comprobaciones del informe.

    docker exec jmeter_backend python3 /tmp/e2e/h83b_datos_informe.py crear
    docker exec jmeter_backend python3 /tmp/e2e/h83b_datos_informe.py limpiar

Crea **un proyecto por cada uno de los cinco estados**, con horas en septiembre
de 2026, para que la sección 6 del informe tenga las cinco píldoras y un
desfase que mirar. Uno de ellos queda desfasado a propósito.

Existe aparte de `h83b_informe.py` porque `d1_cifras.py` y el rasterizado del
PDF necesitan los datos **puestos antes** y **quitados después**, y los dos son
programas distintos. Datos `ZZTEST-` (regla 29), limpieza solo por ese prefijo
(regla 30), y solo contra una base con «test» en el nombre (regla 34).
"""
import json
import os
import subprocess
import sys

import httpx

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
MARCA = "ZZTEST-H83B"

# Uno por estado. El desfasado es el `en_ejecucion`: 4 h estimadas y 8,5 puestas.
PLAN = [
    ("pendiente", "pendiente", 20, "4"),
    ("en-ejecucion", "en_ejecucion", 4, "8.5"),
    ("detenido", "detenido", 20, "4"),
    ("no-viable", "no_viable", 20, "4"),
    ("finalizado", "finalizado", 20, "4"),
]
DIAS = ["2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"]


def psql(sql):
    return subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", BASE, "-q", "-t", "-A", "-c", sql],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True, text=True)


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
    )
    print("limpio")


def crear():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    cliente = cli.get(f"{API}/clients").json()[0]["id"]
    act = cli.get(f"{API}/time/activities").json()[0]["id"]

    for i, (sufijo, estado, estimadas, horas_) in enumerate(PLAN):
        nombre = f"{MARCA}-{sufijo}"
        r = cli.post(f"{API}/time/projects", json={
            "client_id": cliente, "name": nombre,
            "activities": [{"activity_id": act, "estimated_hours": estimadas}]})
        if r.status_code != 201:
            sys.exit(f"no se pudo crear «{nombre}»: {r.status_code} {r.text[:200]}")
        pid = r.json()["id"]
        # Las horas ANTES de cambiar el estado: los cuatro que no están en
        # ejecución no admiten registros (§3.1).
        cli.post(f"{API}/time/entries", json={
            "project_id": pid, "activity_id": act, "date": DIAS[i],
            "hours": horas_, "billable": True, "overtime": False,
            "notes": f"{MARCA} prueba"})
        if estado != "en_ejecucion":
            rr = cli.post(f"{API}/time/projects/{pid}/estado", json={"status": estado})
            if rr.status_code != 200:
                sys.exit(f"no se pudo poner «{nombre}» en «{estado}»: {rr.status_code}")
        print(f"creado {nombre} ({estado})")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "limpiar":
        limpiar()
    else:
        crear()
