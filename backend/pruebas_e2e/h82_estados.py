"""ETAPA H8.2 — el estado del proyecto, por HTTP.

    docker exec jmeter_backend python3 /tmp/e2e/h82_estados.py

Comprueba la tabla de §3.1 entera: los cinco estados, qué bloquea cada uno,
quién puede ponerlos, el filtro por defecto de H-D84, la excepción de la
importación (§6.2.8) y que **estado y consumo no se pisan** (H-D82).

Contra la base de PRUEBAS (regla 34), con datos marcados `ZZTEST-` (regla 29) y
limpieza por ese prefijo y solo por ese prefijo (regla 30). 0 llamadas a la IA.
"""
import io
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal

import httpx

import analista_de_pruebas

# H7.2 (H-D76): por defecto, la base de PRUEBAS. Nunca la de Fredy.
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
SESION_ANALISTA = "/tmp/e2e_analista_h8.json"

MARCA = "ZZTEST-H8"
CLIENTE = f"{MARCA}-cliente"
ANALISTA = "zztest_h8_analista"
CLAVE_ANALISTA = "ZZtest-h8-2026"

ESTADOS = ("pendiente", "en_ejecucion", "detenido", "no_viable", "finalizado")
ROTULOS = {"pendiente": "Pendiente", "en_ejecucion": "En ejecución",
           "detenido": "Detenido", "no_viable": "No viable",
           "finalizado": "Finalizado"}
# §3.1: la tabla, tal cual. Es contra esto contra lo que se compara.
ADMITE_REGISTRO = {"en_ejecucion"}
ADMITE_ESTIMACION = {"pendiente", "en_ejecucion", "detenido"}

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def psql(sql):
    return subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", BASE, "-q", "-t", "-A", "-c", sql],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True, text=True)


def limpiar():
    """Regla 34: si la base no lleva «test» en el nombre, NO se borra nada.

    Y regla 30: se borra **solo** por el prefijo `ZZTEST-`, nunca por
    diferencia contra una foto anterior.
    """
    if "test" not in BASE:
        print(f"PARADA: la base «{BASE}» no lleva «test». No se borra nada.")
        sys.exit(1)
    p = f"name like '{MARCA}%'"
    psql(
        f"delete from time_entries where project_id in (select id from projects where {p});"
        f"delete from project_status_changes where project_id in (select id from projects where {p});"
        f"delete from project_activity_changes where project_id in (select id from projects where {p});"
        f"delete from project_activities where project_id in (select id from projects where {p});"
        f"delete from projects where {p};"
        f"delete from user_clients where client_id in (select id from clients where {p});"
        f"delete from clients where {p};"
        # El analista NO se borra: es un fixture compartido y persistente, y
        # borrarlo obligaria a un login nuevo en cada pasada (regla 26). Lo
        # retira `analista_de_pruebas.py` cuando se quiera.
    )


def sesion_analista(cli_admin):
    """El analista compartido (regla 26). La logica esta en un solo sitio:
    `analista_de_pruebas.py`, que tambien usa `h85_borrado.py`."""
    return analista_de_pruebas.obtener(cli_admin, API)


def libro(filas):
    """Un `.xlsx` en memoria con las columnas de §6.1."""
    from openpyxl import Workbook
    wb = Workbook()
    hoja = wb.active
    hoja.append(["Id", "Observaciones", "Cliente", "Proyecto", "Tarea",
                 "Tipo de hora", "Sub Tipo Hora", "Extra Hour", "Fecha",
                 "Tiempo total", "Facturable"])
    for f in filas:
        hoja.append(f)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        print("sesion caducada: corre refrescar_sesion.py")
        return 1

    print("=== 0. La base, antes de nada (el SQL de H8.1) ===")
    check = psql("select pg_get_constraintdef(oid) from pg_constraint "
                 "where conname = 'ck_project_status';").stdout
    for v in ESTADOS:
        ok(f"'{v}'" in check, f"el CHECK de la base acepta «{v}»")
    viejos = psql("select count(*) from projects where status in ('activo','cerrado');")
    ok(viejos.stdout.strip() == "0",
       f"no queda ningun proyecto en «activo» ni «cerrado» (H-D81): {viejos.stdout.strip()}")

    cliente = cli.post(f"{API}/clients", json={"name": CLIENTE}).json()["id"]
    acts = cli.get(f"{API}/time/activities").json()
    a1 = acts[0]["id"]
    ayer = date.today() - timedelta(days=1)

    def crear(sufijo, estimadas=10):
        r = cli.post(f"{API}/time/projects", json={
            "client_id": cliente, "name": f"{MARCA}-{sufijo}",
            "activities": [{"activity_id": a1, "estimated_hours": estimadas}]})
        assert r.status_code == 201, r.text
        return r.json()

    def poner(pid, estado, cliente_http=None):
        return (cliente_http or cli).post(f"{API}/time/projects/{pid}/estado",
                                          json={"status": estado})

    def registrar(pid, horas=1):
        return cli.post(f"{API}/time/entries", json={
            "date": ayer.isoformat(), "project_id": pid, "activity_id": a1,
            "hours": horas, "billable": True, "overtime": False, "notes": f"{MARCA} prueba"})

    print("\n=== 1. Un proyecto nace «en ejecución» (H-D80) ===")
    p = crear("nace")
    ok(p["status"] == "en_ejecucion", f"status = {p['status']}")
    ok(p["status_label"] == "En ejecución", f"status_label = {p['status_label']}")
    ok(p["can_log_hours"] is True, "can_log_hours = true")
    ok(p["can_edit_estimates"] is True, "can_edit_estimates = true")

    print("\n=== 2. El consumo se llama «En rango», no «En ejecución» (H-D82) ===")
    r = registrar(p["id"], 2)
    ok(r.status_code == 201, f"registrar 2 h en un proyecto en ejecucion: {r.status_code}")
    d = cli.get(f"{API}/time/projects/{p['id']}").json()
    ok(d["overrun_status"] == "en_rango", f"overrun_status = {d['overrun_status']}")
    ok(d["overrun_label"] == "En rango", f"overrun_label = «{d['overrun_label']}»")
    ok(d["status_label"] == "En ejecución",
       "el ESTADO sigue diciendo «En ejecución»: son dos columnas")

    print("\n=== 3. Qué bloquea cada estado (§3.1) ===")
    for e in ESTADOS:
        rr = poner(p["id"], e)
        if not ok(rr.status_code == 200, f"poner el proyecto en «{e}»: {rr.status_code}"):
            continue
        cuerpo = rr.json()
        ok(cuerpo["status_label"] == ROTULOS[e], f"  rotulo «{cuerpo['status_label']}»")
        ok(cuerpo["can_log_hours"] == (e in ADMITE_REGISTRO),
           f"  can_log_hours = {cuerpo['can_log_hours']} (§3.1 dice "
           f"{e in ADMITE_REGISTRO})")
        ok(cuerpo["can_edit_estimates"] == (e in ADMITE_ESTIMACION),
           f"  can_edit_estimates = {cuerpo['can_edit_estimates']} (§3.1 dice "
           f"{e in ADMITE_ESTIMACION})")

        reg = registrar(p["id"])
        esperado = 201 if e in ADMITE_REGISTRO else 409
        ok(reg.status_code == esperado,
           f"  registrar horas devuelve {reg.status_code} (se esperaba {esperado})")
        if reg.status_code == 201:
            cli.delete(f"{API}/time/entries/{reg.json()['id']}")
        else:
            ok(ROTULOS[e] in reg.text,
               f"  el 409 dice en qué estado está: «{ROTULOS[e]}»")

        est = cli.put(f"{API}/time/projects/{p['id']}/actividades",
                      json={"activity_id": a1, "estimated_hours": 11 + ESTADOS.index(e)})
        esperado = 200 if e in ADMITE_ESTIMACION else 409
        ok(est.status_code == esperado,
           f"  cambiar la estimación devuelve {est.status_code} (se esperaba {esperado})")

    print("\n=== 4. El historial del estado (H-D83) ===")
    h = cli.get(f"{API}/time/projects/{p['id']}/historial-estado").json()
    ok(len(h) == len(ESTADOS), f"{len(h)} cambios registrados, uno por estado puesto")
    ok(h[0]["new_status"] == "finalizado", f"el más reciente primero: {h[0]['new_status']}")
    ok(h[0]["new_label"] == "Finalizado", f"con su rótulo: {h[0]['new_label']}")
    ok(h[0]["previous_status"] == "no_viable",
       f"y de dónde venía: {h[0]['previous_status']}")
    ok(bool(h[0]["changed_by_name"]), f"y quién: «{h[0]['changed_by_name']}»")

    print("\n=== 5. Un estado que no existe (400) ===")
    rr = poner(p["id"], "archivado")
    ok(rr.status_code == 400, f"«archivado» devuelve {rr.status_code}")
    rr = poner(p["id"], "finalizado")
    ok(rr.status_code == 409, f"ponerlo en el estado que ya tiene devuelve {rr.status_code}")

    print("\n=== 6. Quién puede cerrar un proyecto (§8) ===")
    cli_an = sesion_analista(cli)
    if cli_an is None:
        fallos.append("no se pudo probar el permiso del analista")
    else:
        q = crear("permisos")
        rr = poner(q["id"], "detenido", cli_an)
        ok(rr.status_code == 200, f"un analista SÍ puede poner «detenido»: {rr.status_code}")
        for e in ("no_viable", "finalizado"):
            rr = poner(q["id"], e, cli_an)
            ok(rr.status_code == 403, f"un analista NO puede poner «{e}»: {rr.status_code}")
            rr = poner(q["id"], e)
            ok(rr.status_code == 200, f"  el admin sí: {rr.status_code}")

    print("\n=== 7. El filtro por defecto (H-D84) ===")
    visibles = crear("visible")
    for e, se_ve in (("pendiente", True), ("en_ejecucion", True), ("detenido", True),
                     ("no_viable", False), ("finalizado", False)):
        poner(visibles["id"], e)
        lista = cli.get(f"{API}/time/projects").json()
        esta = any(x["id"] == visibles["id"] for x in lista)
        ok(esta == se_ve,
           f"con estado «{e}» {'sale' if esta else 'no sale'} en el listado por defecto "
           f"(se esperaba {'que saliera' if se_ve else 'que no'})")

    lista = cli.get(f"{API}/time/projects", params={"incluir_finalizados": "true"}).json()
    ok(any(x["id"] == visibles["id"] for x in lista),
       "con ?incluir_finalizados=true el finalizado vuelve a salir")
    lista = cli.get(f"{API}/time/projects", params={"estado": "finalizado"}).json()
    ok(any(x["id"] == visibles["id"] for x in lista),
       "pedir ?estado=finalizado manda sobre el filtro por defecto")

    # ETAPA H8.6: los alias de H-D91 se RETIRARON. Existieron entre H8.2 y H8.3,
    # mientras la pantalla todavía mandaba los nombres viejos; hoy manda los
    # nuevos y seguir aceptándolos solo serviría para que un cliente viejo
    # pareciera funcionar. Lo que se comprueba ahora es lo contrario que antes.
    for viejo in ("activo", "cerrado"):
        r = cli.get(f"{API}/time/projects", params={"estado": viejo})
        ok(r.status_code == 400,
           f"?estado={viejo} (nombre viejo) ya no vale: {r.status_code}")
        ok("en_ejecucion" in r.text and "finalizado" in r.text,
           f"  y dice cuáles son los cinco: {r.text[:110]}")

    # `incluir_cerrados` ya no existe. FastAPI ignora un parámetro que no
    # declara, así que la llamada responde 200 pero **sin hacer caso**: el
    # finalizado NO sale. Es lo que tiene que pasar, y por eso se comprueba —
    # si alguien lo volviera a añadir por error, esto lo cazaría.
    r = cli.get(f"{API}/time/projects", params={"incluir_cerrados": "true"})
    ok(r.status_code == 200, f"?incluir_cerrados responde {r.status_code}")
    ok(not any(x["id"] == visibles["id"] for x in r.json()),
       "y ya no trae los finalizados: el alias se retiró de verdad")

    print("\n=== 8. Estado y consumo son DOS columnas (H-D82) ===")
    d = crear("desfasado", estimadas=1)
    registrar(d["id"], 3)
    poner(d["id"], "finalizado")
    det = cli.get(f"{API}/time/projects/{d['id']}").json()
    ok(det["status"] == "finalizado", f"estado = {det['status']}")
    ok(det["overrun_status"] == "desfasado", f"consumo = {det['overrun_status']}")
    ok(det["overrun_label"].startswith("Desfasado +2"),
       f"y dice cuántas horas de más: «{det['overrun_label']}»")
    ok(det["status_label"] != det["overrun_label"],
       "el estado y el consumo no dicen lo mismo, que es de lo que se trata")

    print("\n=== 9. La consulta usa el mismo criterio ===")
    params = {"desde": (ayer - timedelta(days=3)).isoformat(),
              "hasta": (ayer + timedelta(days=1)).isoformat()}
    c = cli.get(f"{API}/time/consulta", params=params).json()
    ok(not any(x["project_id"] == d["id"] for x in c["projects"]),
       "un proyecto finalizado no sale en la consulta por defecto")
    c = cli.get(f"{API}/time/consulta",
                params={**params, "incluir_finalizados": "true"}).json()
    fila = next((x for x in c["projects"] if x["project_id"] == d["id"]), None)
    if ok(fila is not None, "con la casilla marcada, sí sale"):
        ok(fila["status"] == "finalizado" and fila["status_label"] == "Finalizado",
           f"con su estado: {fila['status_label']}")
        ok(fila["overrun_status"] == "desfasado",
           f"y su consumo aparte: {fila['overrun_status']}")

    print("\n=== 10. La importación entra salvo en «no viable» (§6.2.8) ===")
    parado = crear("importa-detenido")
    poner(parado["id"], "detenido")
    muerto = crear("importa-no-viable")
    poner(muerto["id"], "no_viable")
    vivo = crear("importa-en-ejecucion")

    nombre_act = acts[0]["name"]
    datos = libro([
        [f"{MARCA}-i1", "de prueba", CLIENTE, parado["name"], nombre_act,
         "", "", "No", ayer.isoformat(), 2, "Si"],
        [f"{MARCA}-i2", "de prueba", CLIENTE, muerto["name"], nombre_act,
         "", "", "No", ayer.isoformat(), 3, "Si"],
        [f"{MARCA}-i3", "de prueba", CLIENTE, vivo["name"], nombre_act,
         "", "", "No", ayer.isoformat(), 4, "Si"],
    ])
    r = cli.post(f"{API}/time/import/preview",
                 files={"archivo": ("zztest_h8.xlsx", datos,
                                    "application/vnd.openxmlformats-officedocument."
                                    "spreadsheetml.sheet")})
    if not ok(r.status_code == 200, f"la vista previa responde {r.status_code}: {r.text[:200]}"):
        return 1
    v = r.json()

    entran = {f["external_id"] for f in v["nuevas"]}
    ok(f"{MARCA}-i1" in entran, "la fila del proyecto DETENIDO entra (§6.2.8)")
    ok(f"{MARCA}-i3" in entran, "la del proyecto en ejecución, también")
    invalidas = {f["external_id"]: f["motivo"] for f in v["invalidas"]}
    ok(f"{MARCA}-i2" in invalidas, "la del proyecto NO VIABLE se rechaza")
    ok("No viable" in invalidas.get(f"{MARCA}-i2", ""),
       f"y dice por qué: «{invalidas.get(f'{MARCA}-i2', '')}»")

    ok(v["filas_no_en_ejecucion"] == 1,
       f"el aviso cuenta las filas fuera de ejecucion: {v['filas_no_en_ejecucion']} (se esperaba 1)")
    fuera = v["proyectos_no_en_ejecucion"]
    if ok(len(fuera) == 1, f"y nombra los proyectos: {len(fuera)} (se esperaba 1)"):
        b = fuera[0]
        ok(b["project_name"] == parado["name"], f"  cuál: {b['project_name']}")
        ok(b["status_label"] == "Detenido", f"  en qué estado: {b['status_label']}")
        ok(b["filas"] == 1, f"  cuántas filas: {b['filas']}")
        ok(Decimal(str(b["horas"])) == Decimal("2"), f"  cuántas horas: {b['horas']}")

    n_antes = psql(f"select count(*) from time_entries where external_id like '{MARCA}%';")
    ok(n_antes.stdout.strip() == "0", "y la vista previa NO escribió nada (§6.2.5)")

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
