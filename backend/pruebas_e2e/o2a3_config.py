"""ETAPA O2a.3 (paso 1) — pedirle a Kinetix la configuracion de la corrida.

    docker exec jmeter_backend python3 /tmp/e2e/o2a3_config.py

No inventa nada: usa los MISMOS endpoints que la pantalla «Monitoreo en vivo»
de O1. Lo que imprime es lo que la pantalla le ensenaria a Fredy.

Regla 34 y H-D76: contra `jmeter_analyzer_test` por el 8002, nunca la base de
Fredy. Regla 29: el cliente y el proyecto llevan la marca ZZTEST.
"""
import json
import os
import sys

import httpx

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
INFLUX_INTERNO = "http://influxdb:8086"
CLIENTE = "ZZTEST-Laboratorio O2a"
PROYECTO = "ZZTEST-Tienda"
DESTINO = "/tmp/o2a3_config.json"


#: ETAPA H8.6 — lo que hace falta y no se puede adivinar. Sin esto, la suite
#: reventaba con un `KeyError: 'KX_TOKEN_ESCRITURA'` en mitad de una llamada, y
#: un traceback no dice a nadie que lo que falta es el guion del anfitrion.
FALTA_TOKEN = """falta la variable KX_TOKEN_ESCRITURA (el token de escritura de
InfluxDB, O-D2).

Esta suite no se lanza sola: la llama `scripts/lab_prueba_correlacion.sh`, que
lee el token de `lab/lab.env` y lo pasa. Desde el anfitrion:

    bash scripts/lab_prueba_correlacion.sh

Es el recorrido entero de O2a.3, y hace dos cosas que NO se pueden hacer desde
dentro de un contenedor: poner la etiqueta de corrida en el recolector
(`docker kill -s HUP lab_colector`) y preguntarle a `lab_db` con su psql."""


def main():
    if "KX_TOKEN_ESCRITURA" not in os.environ:
        sys.exit(FALTA_TOKEN)
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck,
                       headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=60.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre /tmp/e2e/refrescar_sesion.py")

    # La base de pruebas apunta al mismo InfluxDB y al mismo Grafana que O1.
    r = cli.put(f"{API}/monitoring/config", json={
        "grafana_url": "http://grafana:3000",
        "grafana_dashboard_uid": "jmeter-performance",
        "influxdb_url": INFLUX_INTERNO,
        "influxdb_org": "performance",
        "influxdb_bucket": "jmeter",
        "influxdb_token": os.environ["KX_TOKEN_ESCRITURA"],
    })
    if r.status_code != 200:
        sys.exit(f"config de monitoreo: {r.status_code} {r.text[:200]}")

    # El cliente, si no estaba.
    clientes = cli.get(f"{API}/clients").json()
    fila = next((c for c in clientes if c["name"] == CLIENTE), None)
    if fila is None:
        r = cli.post(f"{API}/clients", json={
            "name": CLIENTE,
            "description": "Cliente de prueba de la etapa O2a. Marca ZZTEST (regla 29).",
        })
        if r.status_code not in (200, 201):
            sys.exit(f"no se pudo crear el cliente: {r.status_code} {r.text[:200]}")
        fila = r.json()
    print(f"cliente: {fila['name']}  ({fila['id']})")

    # Y la configuracion de JMeter, la misma que da la pantalla.
    r = cli.get(f"{API}/monitoring/jmeter-config",
                params={"client_id": fila["id"], "proyecto": PROYECTO})
    if r.status_code != 200:
        sys.exit(f"jmeter-config: {r.status_code} {r.text[:300]}")
    cfg = r.json()

    valores = {a["nombre"]: a["valor"] for a in cfg["argumentos"]}
    if cfg.get("aviso"):
        sys.exit("la pantalla avisa: " + cfg["aviso"])

    salida = {
        "application": cfg["application"],
        # La pantalla da la URL para un JMeter de FUERA de Docker; el nuestro
        # corre dentro, donde InfluxDB se llama por su nombre de servicio.
        "influxdbUrl": valores["influxdbUrl"].replace("localhost:8086", "influxdb:8086"),
        "influxdbToken": valores["influxdbToken"],
        "url_tablero": cfg["url_tablero"],
    }
    if not salida["application"].startswith("zztest-"):
        sys.exit("la corrida no lleva la marca zztest-: me paro (regla 29)")

    with open(DESTINO, "w") as fichero:
        json.dump(salida, fichero, indent=2)

    print(f"corrida:  {salida['application']}")
    print(f"url:      {salida['influxdbUrl']}")
    print(f"token:    {salida['influxdbToken'][:12]}... (de solo escritura, O-D2)")
    print(f"tablero:  {salida['url_tablero']}")
    print(f"escrito:  {DESTINO}")
    # Esta linea la lee el guion del anfitrion.
    print("APPLICATION=" + salida["application"])


if __name__ == "__main__":
    main()
