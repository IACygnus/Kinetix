"""ETAPA O2a.3 (paso 2) — la prueba que importa.

    docker exec jmeter_backend python3 /tmp/e2e/o2a3_correlacion.py

Tres ventanas seguidas, TODAS con la misma etiqueta `corrida`:

    reposo antes   ->   la prueba   ->   reposo despues

Y una sola pregunta: **¿se ve en los datos que el servidor y la base trabajan
durante la prueba y dejan de hacerlo despues?** Si la respuesta es que no, el
modo sin agente no sirve para nada y hay que decirlo.

El anfitrion pone la etiqueta antes de llamar a este programa (no se puede
desde dentro del contenedor: hace falta `docker kill -s HUP lab_colector`).
0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import httpx

INFLUX = "http://influxdb:8086"
OPERADOR = os.environ.get("KX_INFLUX_TOKEN", "jmeter-token-2024-super-secret")
JMX = os.environ.get("KX_JMX", "/tmp/zztest_lab.jmx")
JMETER = "/opt/apache-jmeter-5.6.3/bin/jmeter"

REPOSO = int(os.environ.get("KX_REPOSO", "70"))
DURACION = int(os.environ.get("KX_DURACION", "120"))
USUARIOS = os.environ.get("KX_USUARIOS", "12")

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flux(consulta):
    r = httpx.post(f"{INFLUX}/api/v2/query", params={"org": "performance"},
                   headers={"Authorization": f"Token {OPERADOR}",
                            "Content-Type": "application/vnd.flux",
                            "Accept": "application/csv"},
                   content=consulta, timeout=90)
    r.raise_for_status()
    return [ln for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")]


def un_numero(consulta):
    """La primera columna `_value` que devuelva la consulta, o None."""
    filas = flux(consulta)
    if len(filas) < 2:
        return None
    cabecera = filas[0].split(",")
    if "_value" not in cabecera:
        return None
    columna = cabecera.index("_value")
    try:
        return float(filas[1].split(",")[columna])
    except (ValueError, IndexError):
        return None


def cpu_en_uso(corrida, desde, hasta):
    return un_numero(f'''
from(bucket: "infra")
  |> range(start: {desde}, stop: {hasta})
  |> filter(fn: (r) => r["_measurement"] == "cpu" and r["host"] == "lab_servidor")
  |> filter(fn: (r) => r["corrida"] == "{corrida}")
  |> filter(fn: (r) => r["_field"] == "usage_idle")
  |> mean()
  |> map(fn: (r) => ({{ r with _value: 100.0 - r._value }}))
''')


def cpu_contenedor(corrida, contenedor, desde, hasta):
    return un_numero(f'''
from(bucket: "infra")
  |> range(start: {desde}, stop: {hasta})
  |> filter(fn: (r) => r["_measurement"] == "docker_container_cpu")
  |> filter(fn: (r) => r["container_name"] == "{contenedor}")
  |> filter(fn: (r) => r["corrida"] == "{corrida}")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> mean()
''')


def transacciones_por_segundo(corrida, desde, hasta, segundos):
    total = un_numero(f'''
from(bucket: "infra")
  |> range(start: {desde}, stop: {hasta})
  |> filter(fn: (r) => r["_measurement"] == "postgresql" and r["db"] == "tienda")
  |> filter(fn: (r) => r["corrida"] == "{corrida}")
  |> filter(fn: (r) => r["_field"] == "xact_commit")
  |> spread()
''')
    return None if total is None else total / segundos


def bloques_de_disco(corrida, desde, hasta):
    return un_numero(f'''
from(bucket: "infra")
  |> range(start: {desde}, stop: {hasta})
  |> filter(fn: (r) => r["_measurement"] == "postgresql" and r["db"] == "tienda")
  |> filter(fn: (r) => r["corrida"] == "{corrida}")
  |> filter(fn: (r) => r["_field"] == "blks_hit")
  |> spread()
''')


def numero(valor, sufijo=""):
    return "sin dato" if valor is None else f"{valor:,.2f}{sufijo}".replace(",", " ")


#: ETAPA H8.6 — igual que en `o2a3_config.py`: sin esto, la suite reventaba con
#: un `FileNotFoundError` que no dice de donde sale ese archivo ni quien lo
#: escribe.
FALTA_CONFIG = """falta /tmp/o2a3_config.json, que lo escribe `o2a3_config.py`.

Esta suite es el PASO 2 de O2a.3 y no se lanza sola. El paso 1 le deja ahi la
corrida, y entre los dos hace falta poner esa etiqueta en el recolector, que
solo se puede desde el anfitrion. Los tres pasos, en orden, los da:

    bash scripts/lab_prueba_correlacion.sh"""


def main():
    if not os.path.exists("/tmp/o2a3_config.json"):
        sys.exit(FALTA_CONFIG)
    cfg = json.load(open("/tmp/o2a3_config.json"))
    corrida = cfg["application"]
    if not corrida.startswith("zztest-"):
        sys.exit("la corrida no lleva la marca zztest-: me paro (regla 29)")

    print(f"corrida: {corrida}")
    print(f"reposo {REPOSO}s · prueba {DURACION}s · reposo {REPOSO}s\n")

    # ---------- 1. Reposo, antes ----------
    print("--- 1. El servidor en reposo, antes ---")
    t0 = ahora()
    time.sleep(REPOSO)
    t1 = ahora()
    antes = {
        "cpu": cpu_en_uso(corrida, t0, t1),
        "app": cpu_contenedor(corrida, "lab_servidor", t0, t1),
        "db": cpu_contenedor(corrida, "lab_db", t0, t1),
        "tps": transacciones_por_segundo(corrida, t0, t1, REPOSO),
    }
    ok(antes["cpu"] is not None,
       "llegan metricas de CPU sin agente con la etiqueta de esta corrida")
    ok(antes["app"] is not None, "y metricas por contenedor (O-D16)")
    ok(antes["tps"] is not None, "y metricas de PostgreSQL sin agente")
    print(f"    CPU maquina {numero(antes['cpu'], ' %')} · contenedor de la app "
          f"{numero(antes['app'], ' %')} · base {numero(antes['db'], ' %')} · "
          f"{numero(antes['tps'], ' tx/s')}")

    # ---------- 2. La prueba ----------
    print("\n--- 2. La prueba, con el Backend Listener de Kinetix ---")
    t2 = ahora()
    salida = subprocess.run(
        [JMETER, "-n", "-t", JMX, "-l", "/tmp/zztest_o2a3.jtl",
         f"-JinfluxdbUrl={cfg['influxdbUrl']}",
         f"-JinfluxdbToken={cfg['influxdbToken']}",
         f"-Japplication={corrida}",
         f"-Jduracion={DURACION}", f"-Jusuarios={USUARIOS}"],
        capture_output=True, text=True, timeout=DURACION + 180, cwd="/tmp")
    resumenes = [l for l in salida.stdout.splitlines() if l.startswith("summary =")]
    print(f"    {resumenes[-1] if resumenes else salida.stdout[-300:]}")
    ok(bool(resumenes), "la prueba corrio")
    ok(bool(resumenes) and "Err:     0" in resumenes[-1],
       "y sin errores contra la aplicacion del laboratorio")
    t3 = ahora()

    registro = "/tmp/jmeter.log"
    log = open(registro, encoding="utf-8", errors="ignore").read() \
        if os.path.exists(registro) else ""
    ok("Error writing metrics to influxDB" not in log,
       "el Backend Listener escribio sin quejarse")

    durante = {
        "cpu": cpu_en_uso(corrida, t2, t3),
        "app": cpu_contenedor(corrida, "lab_servidor", t2, t3),
        "db": cpu_contenedor(corrida, "lab_db", t2, t3),
        "tps": transacciones_por_segundo(corrida, t2, t3, DURACION),
    }
    print(f"    CPU maquina {numero(durante['cpu'], ' %')} · contenedor de la app "
          f"{numero(durante['app'], ' %')} · base {numero(durante['db'], ' %')} · "
          f"{numero(durante['tps'], ' tx/s')}")

    # ---------- 3. Reposo, despues ----------
    print("\n--- 3. El servidor en reposo, despues ---")
    time.sleep(REPOSO)
    t4 = ahora()
    despues = {
        "cpu": cpu_en_uso(corrida, t3, t4),
        "app": cpu_contenedor(corrida, "lab_servidor", t3, t4),
        "db": cpu_contenedor(corrida, "lab_db", t3, t4),
        "tps": transacciones_por_segundo(corrida, t3, t4, REPOSO),
    }
    print(f"    CPU maquina {numero(despues['cpu'], ' %')} · contenedor de la app "
          f"{numero(despues['app'], ' %')} · base {numero(despues['db'], ' %')} · "
          f"{numero(despues['tps'], ' tx/s')}")

    # ---------- 4. La aceptacion ----------
    print("\n--- 4. ¿Se ve la prueba en los datos del servidor? ---")

    def sube_y_baja(clave, texto, minimo=0.0):
        a, d, p = antes[clave], durante[clave], despues[clave]
        if None in (a, d, p):
            return ok(False, f"{texto}: falta algun dato")
        ok(d > a and d - a >= minimo, f"{texto}: sube durante la prueba "
                                      f"({numero(a)} -> {numero(d)})")
        return ok(d > p, f"{texto}: y vuelve a bajar despues "
                         f"({numero(d)} -> {numero(p)})")

    sube_y_baja("app", "CPU del contenedor de la aplicacion")
    sube_y_baja("db", "CPU del contenedor de la base")
    sube_y_baja("tps", "Transacciones por segundo de PostgreSQL")
    sube_y_baja("cpu", "CPU de la maquina (leida por SSH)")

    # ---------- 5. La misma etiqueta en los dos cubos ----------
    print("\n--- 5. La misma corrida, en los dos cubos ---")
    en_infra = flux(f'''
import "influxdata/influxdb/schema"
schema.tagValues(bucket: "infra", tag: "corrida", start: -2h)
''')
    en_jmeter = flux(f'''
import "influxdata/influxdb/schema"
schema.tagValues(bucket: "jmeter", tag: "application", start: -2h)
''')
    ok(any(corrida in ln for ln in en_infra),
       f"«{corrida}» esta en el cubo infra, etiqueta `corrida`")
    ok(any(corrida in ln for ln in en_jmeter),
       f"«{corrida}» esta en el cubo jmeter, etiqueta `application`")

    puntos = un_numero(f'''
from(bucket: "jmeter")
  |> range(start: -2h)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["application"] == "{corrida}")
  |> filter(fn: (r) => r["_field"] == "avg" and r["statut"] == "all")
  |> count()
''')
    ok(bool(puntos) and puntos > 0,
       f"la prueba dejo {int(puntos or 0)} puntos de tiempo de respuesta")

    print()
    if fallos:
        print(f"FALLOS: {len(fallos)}")
        for texto in fallos:
            print(f"  - {texto}")
        sys.exit(1)
    print("O2a.3 — LA PRUEBA SE VE EN EL SERVIDOR: TODO PASA")


if __name__ == "__main__":
    main()
