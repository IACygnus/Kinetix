"""ETAPA O2d.2 — las sesiones y sus metricas, por HTTP.

    docker exec jmeter_backend python3 /tmp/e2e/o2d2_sesiones.py

Regla 34: contra `jmeter_analyzer_test` por el 8002. Regla 29: todo ZZTEST-.
0 llamadas a la IA.

Lo que se comprueba:
  1. El CRUD de sesiones, con su corrida generada por la definicion UNICA de O-D4.
  2. **O-D35: la sesion se recupera.** Se crea, se lee otra vez, y sigue con sus
     servidores. Eso es lo que Fredy perdia al cambiar de pestana.
  3. O-D45: subir un `.jmx` y recibirlo con el listener puesto.
  4. O-D38: el endpoint de metricas devuelve series pintables — y cuando no hay,
     **dice por que con palabras**, que es lo que evita una pantalla vacia sin
     explicacion.
  5. O-D40: una sesion terminada sigue devolviendo lo que paso.
"""
import json
import os
import sys

import httpx

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
CLIENTE = "ZZTEST-Observabilidad O2c"
OBS = f"{API}/observabilidad"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def main():
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck,
                       headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    clientes = cli.get(f"{API}/clients").json()
    fila = next((c for c in clientes if c["name"] == CLIENTE), None)
    if fila is None:
        fila = cli.post(f"{API}/clients", json={
            "name": CLIENTE, "description": "Cliente de prueba de O2c/O2d."}).json()
    client_id = fila["id"]

    # Los servidores del laboratorio; si no estan, se dan de alta sin credencial
    # (para este paso no hace falta: no se prueba la conexion).
    servidores = cli.get(f"{OBS}/servidores", params={"client_id": client_id}).json()
    for nombre, tipo, direccion, puerto in (
        ("lab_servidor", "linux", "lab_servidor", 22),
        ("lab_db", "postgresql", "lab_db", 5432),
    ):
        if not any(s["name"] == nombre for s in servidores):
            cli.post(f"{OBS}/servidores", json={
                "client_id": client_id, "name": nombre, "tipo": tipo,
                "modo": "sin_agente", "direccion": direccion, "puerto": puerto,
                "usuario": "kinetix_lector"})
    servidores = cli.get(f"{OBS}/servidores", params={"client_id": client_id}).json()
    ids = [s["id"] for s in servidores if s["name"] in ("lab_servidor", "lab_db")]
    ok(len(ids) == 2, f"los dos servidores del laboratorio estan: {len(ids)}")

    # Limpieza de una corrida anterior, solo de ESTE cliente ZZTEST.
    for vieja in cli.get(f"{OBS}/sesiones", params={"client_id": client_id}).json():
        cli.delete(f"{OBS}/sesiones/{vieja['id']}")

    # ---------- 1. Crear ----------
    print("\n--- 1. Crear una sesion (O-D37, paso 1) ---")
    r = cli.post(f"{OBS}/sesiones", json={
        "nombre": "ZZTEST-Sesion O2d", "client_id": client_id,
        "proyecto": "ZZTEST-Tienda", "servidores": ids,
        "notas": "Sesion de prueba de la etapa O2d."})
    ok(r.status_code == 201, f"se crea: {r.status_code}")
    sesion = r.json()
    ok(sesion["estado"] == "preparada", "nace «preparada»")
    ok(sesion["corrida"].startswith("zztest-"),
       f"con su corrida: {sesion['corrida']}")
    ok(len(sesion["servidores"]) == 2, "y con los dos servidores marcados")

    r = cli.post(f"{OBS}/sesiones", json={
        "nombre": "ZZTEST-Sesion O2d", "client_id": client_id,
        "proyecto": "otro"})
    ok(r.status_code == 409, f"dos sesiones con el mismo nombre: {r.status_code}")

    # ---------- 2. O-D35: se recupera ----------
    print("\n--- 2. O-D35: la sesion se recupera ---")
    otra_vez = cli.get(f"{OBS}/sesiones/{sesion['id']}").json()
    ok(otra_vez["corrida"] == sesion["corrida"],
       "al volver a abrirla, la corrida es la MISMA")
    ok(len(otra_vez["servidores"]) == 2, "y sus servidores siguen ahi")
    nombres = sorted(s["name"] for s in otra_vez["servidores"])
    ok(nombres == ["lab_db", "lab_servidor"], f"y son los suyos: {nombres}")

    listado = cli.get(f"{OBS}/sesiones", params={"client_id": client_id}).json()
    ok(any(s["id"] == sesion["id"] for s in listado),
       "y aparece en el listado (O-D36)")

    # ---------- 3. O-D45: el .jmx ----------
    print("\n--- 3. O-D45: subir un .jmx y recibirlo con el listener ---")
    plan = open("/tmp/zztest_o14.jmx", "rb").read()
    ok(b"BackendListener" in plan,
       "el plan de prueba ya traia uno (asi se comprueba el reemplazo)")
    r = cli.post(f"{OBS}/sesiones/{sesion['id']}/jmx",
                 files={"archivo": ("zztest_o14.jmx", plan, "application/xml")})
    ok(r.status_code == 200, f"se procesa: {r.status_code}")
    if r.status_code == 200:
        devuelto = r.content
        ok(sesion["corrida"].encode() in devuelto,
           "el .jmx devuelto lleva la corrida de ESTA sesion")
        ok(devuelto.count(b"<BackendListener") == 1,
           f"y un solo Backend Listener ({devuelto.count(b'<BackendListener')})")
        ok(r.headers.get("X-Kinetix-Reemplazado") == "1",
           "avisa de que reemplazo el que traia")
        ok(sesion["corrida"] in r.headers.get("Content-Disposition", ""),
           "el nombre del fichero lleva la corrida")

    r = cli.post(f"{OBS}/sesiones/{sesion['id']}/jmx",
                 files={"archivo": ("malo.jmx", b"no soy xml", "application/xml")})
    ok(r.status_code == 400, f"un archivo que no vale da 400: {r.status_code}")
    ok("XML" in r.json().get("detail", ""),
       f"con un mensaje claro: {r.json().get('detail', '')[:60]}")

    # ---------- 4. Los valores a mano (la opcion avanzada) ----------
    print("\n--- 4. Los valores, para copiarlos a mano ---")
    cfg = cli.get(f"{OBS}/sesiones/{sesion['id']}/jmeter").json()
    ok(cfg["corrida"] == sesion["corrida"], "la corrida es la de la sesion")
    ok(len(cfg["parametros"]) >= 5, f"con sus parametros: {len(cfg['parametros'])}")
    ok(all(p.get("explicacion") for p in cfg["parametros"]),
       "y cada uno con su explicacion")

    # ---------- 5. O-D38: las metricas ----------
    print("\n--- 5. O-D38: el endpoint de metricas ---")
    m = cli.get(f"{OBS}/sesiones/{sesion['id']}/metricas",
                params={"minutos": 30}).json()
    ok("prueba" in m and "infraestructura" in m,
       "devuelve las dos partes: la prueba y la infraestructura (O-D39)")
    ok(len(m["infraestructura"]) == 2,
       f"una entrada por servidor: {len(m['infraestructura'])}")
    if not m["hay_datos"]:
        ok(bool(m["aviso"]) and len(m["aviso"]) > 40,
           f"sin datos todavia, pero lo DICE: «{m['aviso'][:80]}…»")
    else:
        ok(True, "ya hay datos de esta corrida")

    # Una sesion sin servidores tiene que decirlo con palabras.
    r = cli.post(f"{OBS}/sesiones", json={
        "nombre": "ZZTEST-Sin servidores", "client_id": client_id,
        "proyecto": "ZZTEST-Tienda", "servidores": []})
    if not ok(r.status_code == 201,
              f"se crea una sesion sin servidores: {r.status_code} "
              f"{r.text[:120]}"):
        sys.exit(1)
    vacia = r.json()
    m2 = cli.get(f"{OBS}/sesiones/{vacia['id']}/metricas").json()
    ok("servidor" in m2["aviso"].lower(),
       f"una sesion sin servidores lo explica: «{m2['aviso'][:70]}…»")
    cli.delete(f"{OBS}/sesiones/{vacia['id']}")

    # ---------- 6. O-D40: terminada, pero consultable ----------
    print("\n--- 6. O-D40: una sesion terminada se sigue pudiendo abrir ---")
    r = cli.put(f"{OBS}/sesiones/{sesion['id']}", json={"estado": "terminada"})
    ok(r.status_code == 200 and r.json()["estado"] == "terminada",
       "se puede cerrar")
    ok(r.json()["termino_en"] is not None, "y se anota cuando termino")
    m3 = cli.get(f"{OBS}/sesiones/{sesion['id']}/metricas")
    ok(m3.status_code == 200,
       "y sus metricas se siguen pudiendo pedir, no da error")

    print()
    if fallos:
        print(f"FALLOS: {len(fallos)}")
        for texto in fallos:
            print(f"  - {texto}")
        sys.exit(1)
    print("O2d.2 — LAS SESIONES Y SUS METRICAS: TODO PASA")


if __name__ == "__main__":
    main()
