"""CARGA REAL §2 — borrar un proyecto (`DELETE /time/projects/{id}`).

    docker exec jmeter_backend python3 /tmp/e2e/carga_borrado_proyecto.py

El endpoint nació para poder empezar un periodo de cero: el producto sabía
borrar registros (`/time/borrado`) pero no los proyectos que una importación
había creado con el nombre equivocado, y esos nombres se quedaban compitiendo
con los buenos en todas las pantallas.

Es una operación destructiva, así que esta suite comprueba sobre todo **lo que
NO tiene que pasar**:

| # | Qué se comprueba |
|---|---|
| 1 | Un analista **no puede**: 403, y el proyecto sigue ahí |
| 2 | Un proyecto **con horas registradas** no se borra: 409 que dice cuántas |
| 3 | Un id que no existe: 404 |
| 4 | El admin borra, y **las tres tablas hijas se van con él** |
| 5 | Queda **constancia** en `project_deletions`: quién, qué, de qué cliente |
| 6 | El borrado está **acotado**: el proyecto vecino no se entera |

Contra `jmeter_analyzer_test` y el 8002 (regla 34). Datos `ZZTEST-CARGA`
(regla 29), limpieza solo por ese prefijo (regla 30). 0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys

import httpx

import analista_de_pruebas

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")

MARCA = "ZZTEST-CARGA"

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


def uno(sql, base=None):
    return psql(sql, base).stdout.strip()


def cuenta_hijas(pid):
    """Las tres tablas que cuelgan del proyecto, contadas de la base."""
    return {
        t: int(uno(f"select count(*) from {t} where project_id = '{pid}';") or 0)
        for t in ("project_activities", "project_activity_changes",
                  "project_status_changes")
    }


def limpiar():
    # El freno de la regla 34: si la base no se llama «test», no se borra nada.
    if "test" not in BASE:
        sys.exit(f"PARADA: «{BASE}» no es una base de pruebas. No se borra nada.")
    p = f"name like '{MARCA}%'"
    psql(
        f"delete from time_entries where project_id in (select id from projects where {p});"
        f"delete from project_status_changes where project_id in (select id from projects where {p});"
        f"delete from project_activity_changes where project_id in (select id from projects where {p});"
        f"delete from project_activities where project_id in (select id from projects where {p});"
        f"delete from projects where {p};"
        # El rastro que deja esta misma suite. Se quita por el prefijo, nunca
        # por diferencia (regla 30).
        f"delete from project_deletions where project_name like '{MARCA}%';"
    )


def crear_proyecto(cli, cliente, act, sufijo):
    r = cli.post(f"{API}/time/projects", json={
        "client_id": cliente, "name": f"{MARCA}-{sufijo}",
        "activities": [{"activity_id": act, "estimated_hours": 40}]})
    if r.status_code != 201:
        sys.exit(f"no se pudo crear el proyecto {sufijo}: {r.status_code} {r.text[:200]}")
    return r.json()["id"]


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    cliente = cli.get(f"{API}/clients").json()[0]["id"]
    nombre_cliente = cli.get(f"{API}/clients").json()[0]["name"]
    act = cli.get(f"{API}/time/activities").json()[0]["id"]

    # Tres proyectos: el que se borra, el que tiene horas y el vecino que
    # demuestra que el borrado está acotado.
    pid = crear_proyecto(cli, cliente, act, "se-borra")
    pid_con_horas = crear_proyecto(cli, cliente, act, "con-horas")
    pid_vecino = crear_proyecto(cli, cliente, act, "vecino")

    # Al que se va a borrar se le mueve la estimación y el estado, para que las
    # tres tablas hijas tengan filas de verdad que perder.
    cli.put(f"{API}/time/projects/{pid}/actividades",
            json={"activity_id": act, "estimated_hours": 60})
    cli.post(f"{API}/time/projects/{pid}/estado", json={"status": "detenido"})

    r = cli.post(f"{API}/time/entries", json={
        "project_id": pid_con_horas, "activity_id": act, "date": "2026-08-04",
        "hours": "4", "billable": True, "overtime": False,
        "notes": f"{MARCA} prueba"})
    if r.status_code != 201:
        sys.exit(f"no se pudo registrar la hora: {r.status_code} {r.text[:200]}")

    hijas_antes = cuenta_hijas(pid)
    print(f"hijas del proyecto que se va a borrar: {hijas_antes}")
    ok(all(v > 0 for v in hijas_antes.values()),
       "las tres tablas hijas tienen filas antes de borrar")

    print("\n=== 1. Un analista NO puede ===")
    cli_an = analista_de_pruebas.obtener(cli, API)
    if cli_an is None:
        print("      (sin sesión de analista: corre antes h82_estados.py)")
        fallos.append("no se pudo probar el 403 del analista")
    else:
        rr = cli_an.delete(f"{API}/time/projects/{pid}")
        ok(rr.status_code == 403, f"el analista recibe {rr.status_code}")
        ok(cli.get(f"{API}/time/projects/{pid}").status_code == 200,
           "y el proyecto sigue ahí")

    print("\n=== 2. Un proyecto CON HORAS no se borra ===")
    rr = cli.delete(f"{API}/time/projects/{pid_con_horas}")
    ok(rr.status_code == 409, f"responde {rr.status_code}")
    detalle = rr.json().get("detail", "") if rr.status_code == 409 else ""
    ok("1 registro" in detalle, f"y dice CUÁNTOS son: «{detalle[:90]}…»")
    ok(cli.get(f"{API}/time/projects/{pid_con_horas}").status_code == 200,
       "el proyecto sigue ahí")
    ok(int(uno(f"select count(*) from time_entries where project_id='{pid_con_horas}';")) == 1,
       "y su registro de horas también")

    print("\n=== 3. Un id que no existe ===")
    rr = cli.delete(f"{API}/time/projects/00000000-0000-0000-0000-000000000000")
    ok(rr.status_code == 404, f"responde {rr.status_code}")

    print("\n=== 4. El admin borra, y se lleva las tres tablas hijas ===")
    rr = cli.delete(f"{API}/time/projects/{pid}")
    if not ok(rr.status_code == 200, f"responde {rr.status_code} {rr.text[:160]}"):
        return 1
    d = rr.json()
    ok(d["name"] == f"{MARCA}-se-borra", f"devuelve el nombre: «{d['name']}»")
    ok(d["client_name"] == nombre_cliente, f"y el cliente: «{d['client_name']}»")
    ok(d["estimaciones_borradas"] == hijas_antes["project_activities"],
       f"dice {d['estimaciones_borradas']} estimaciones, las que había")
    ok(d["historial_estimaciones_borrado"] == hijas_antes["project_activity_changes"],
       f"y {d['historial_estimaciones_borrado']} cambios de estimación")
    ok(d["historial_estados_borrado"] == hijas_antes["project_status_changes"],
       f"y {d['historial_estados_borrado']} cambios de estado")

    ok(cli.get(f"{API}/time/projects/{pid}").status_code == 404,
       "el proyecto ya no está")
    hijas_despues = cuenta_hijas(pid)
    ok(all(v == 0 for v in hijas_despues.values()),
       f"y las tres tablas hijas están vacías: {hijas_despues}")

    print("\n=== 5. Queda constancia ===")
    fila = uno("select project_name||'|'||client_name||'|'||estimaciones_borradas"
               f"||'|'||coalesce(u.username,'?') from project_deletions p "
               "left join users u on u.id = p.performed_by "
               f"where project_name = '{MARCA}-se-borra';")
    ok(fila.startswith(f"{MARCA}-se-borra|{nombre_cliente}|"),
       f"`project_deletions` lo guardó: {fila}")
    ok(fila.endswith("|admin"), "y de quién fue: admin")

    print("\n=== 6. El borrado está acotado ===")
    ok(cli.get(f"{API}/time/projects/{pid_vecino}").status_code == 200,
       "el proyecto vecino no se enteró")
    ok(cuenta_hijas(pid_vecino)["project_activities"] == 1,
       "y conserva su estimación")

    limpiar()
    print("\n" + "=" * 70)
    if fallos:
        print(f"FALLAN {len(fallos)}:")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("TODO PASA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
