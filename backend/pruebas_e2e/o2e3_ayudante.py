"""O2e.3 — lo que `scripts/lab_ingesta_o2e3.sh` necesita del backend de PRUEBAS.

    docker exec -i ... jmeter_backend python3 /app/pruebas_e2e/o2e3_ayudante.py <orden>

Regla 34: 8002 y `jmeter_analyzer_test`. Los tokens entran y salen por la
entrada y la salida estandar, nunca por la linea de ordenes.

    preparar   stdin: el token de escritura de `infra`. Lo carga (PUT, admin),
               crea el cliente ZZTEST-Laboratorio O2e y un token de ingesta
               para el y otro para ZZTEST-Ingesta O2e otro. stdout: JSON.
    revocar    stdin: JSON {"ids": [...]}. Los revoca.
    token      stdout: estado del token de escritura de infra (sin el token).
"""
import json
import os
import sys

import httpx

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
CLIENTE = "ZZTEST-Laboratorio O2e"
OTRO = "ZZTEST-Ingesta O2e otro"


def cliente_http():
    if "8002" not in API:
        sys.exit(f"PARADA: {API} no es el backend de pruebas (8002)")
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=60.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion de pruebas caducada")
    # La sesion dura 30 min y la corrida de O2e.3 pasa de 12: se renueva en
    # cada llamada (sliding session, sin gastar cupo de login — regla 26).
    r = cli.post(f"{API}/auth/refresh")
    if r.status_code == 200:
        ck.update({k: v for k, v in r.cookies.items()})
        json.dump({"cookies": [{"name": k, "value": v, "domain": "localhost", "path": "/",
                                "expires": -1, "httpOnly": False, "secure": False,
                                "sameSite": "Lax"} for k, v in ck.items()],
                   "origins": []}, open(SESION, "w"))
        cli.cookies.update(r.cookies)
        cli.headers["X-CSRF-Token"] = ck.get("csrf_token", "")
    return cli


def id_de_cliente(cli, nombre):
    for c in cli.get(f"{API}/clients").raise_for_status().json():
        if c["name"] == nombre:
            return c["id"]
    return cli.post(f"{API}/clients", json={
        "name": nombre, "description": "Prueba O2e.3. Marca ZZTEST."}
    ).raise_for_status().json()["id"]


def preparar():
    cli = cliente_http()
    token_infra = sys.stdin.read().strip()
    if not token_infra:
        sys.exit("falta el token de infra en la entrada")
    cli.put(f"{API}/ingesta/token-escritura", json={"token": token_infra}).raise_for_status()
    salida = {}
    for clave, nombre in (("bueno", CLIENTE), ("otro", OTRO)):
        cid = id_de_cliente(cli, nombre)
        t = cli.post(f"{API}/ingesta/tokens", json={"client_id": cid}).raise_for_status().json()
        salida[clave] = {"cliente": nombre, "id": t["id"], "token": t["token"],
                         "prefijo": t["prefijo"]}
    print(json.dumps(salida))


def revocar():
    cli = cliente_http()
    for tid in json.loads(sys.stdin.read())["ids"]:
        r = cli.post(f"{API}/ingesta/tokens/{tid}/revocar").raise_for_status().json()
        print(f"revocado {r['prefijo']} a las {r['revocado_en']}")


def revocar_restos():
    """Los tokens de ZZTEST que una corrida interrumpida dejo sin revocar."""
    cli = cliente_http()
    for c in cli.get(f"{API}/clients").raise_for_status().json():
        if c["name"] not in (CLIENTE, OTRO):
            continue
        for t in cli.get(f"{API}/ingesta/tokens", params={"client_id": c["id"]}).json():
            if not t["revocado_en"]:
                cli.post(f"{API}/ingesta/tokens/{t['id']}/revocar").raise_for_status()
                print(f"revocado resto {t['prefijo']} de {c['name']}")


def token():
    print(cliente_http().get(f"{API}/ingesta/token-escritura").json())


if __name__ == "__main__":
    {"preparar": preparar, "revocar": revocar, "revocar-restos": revocar_restos,
     "token": token}[sys.argv[1]]()
