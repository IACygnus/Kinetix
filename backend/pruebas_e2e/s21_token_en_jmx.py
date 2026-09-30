"""S2.2 — El Backend Listener sale de UN sitio, y el .jmx no lleva el maestro.

    docker exec -e KX_TOKEN_ESCRITURA=... jmeter_backend python3 /tmp/e2e/s21_token_en_jmx.py

Nacio como la sonda de S2.1 (reporte 132), que encontro el token MAESTRO de
InfluxDB dentro de los .jmx del diseñador. Ahora es la suite que lo impide:

  A. La ruta de la IA por el ENDPOINT REAL (`refine_jmx_surgical`, en proceso):
     parseo, resolucion de datos, buzon, aplicador y regenerador. Lo unico
     sustituido es la llamada al modelo, que devuelve la operacion
     `add_listener backend_listener`. 0 llamadas a la IA.
     El .jmx: sin el maestro, `influxdbToken` = el de escritura de `jmeter`, la
     URL como `${__P(influxdbUrl,...)}` y `application` con la regla de O-D4.
  B. La misma ruta SIN cliente: `sin-nombre` y el nombre del Test Plan.
  C. Sin token en `monitoring_config`, por el endpoint: error claro, sin listener.
     (UPDATE dentro de una transaccion que se deshace: la base no cambia.)
  D. El aplicador con el buzon vacio: error, no un listener inventado.
  E. `/monitoring/jmeter-fragmento` entrega lo que genera el modulo.
  F. Prueba real: JMeter corre el .jmx de A dentro del contenedor con
     `-JinfluxdbUrl` y `-Japplication=zztest-s22-<fecha>`, y los puntos llegan
     al cubo `jmeter`. Se borran SOLO los de esa application (regla 35).

El maestro se busca por su SHA-256: esta suite no lo lleva escrito.
Regla 34: contra `jmeter_analyzer_test` y el 8002. Regla 29: todo ZZTEST-/zztest-.
"""
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

sys.path.insert(0, "/app")

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
ESCRITURA = os.environ.get("KX_TOKEN_ESCRITURA", "")
INFLUX = "http://influxdb:8086"
CLIENTE = "ZZTEST-S2.2 listener"
PROYECTO = "zztest-s22"
PLAN = "ZZTEST S2.2 plan"

# SHA-256 del token maestro de InfluxDB (reporte 132). Solo la huella.
HUELLA_MAESTRO = "67bd92341a72daee0a71cf0a132979568153e0848fb8524ae846d0c5d7e5a76f"

JMX_BASE = f"""<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="{PLAN}" enabled="true">
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Usuarios" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller" enabled="true">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">25</stringProp>
        </elementProp>
        <stringProp name="ThreadGroup.num_threads">2</stringProp>
        <stringProp name="ThreadGroup.ramp_time">1</stringProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="ZZTEST docs" enabled="true">
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">
            <collectionProp name="Arguments.arguments"/>
          </elementProp>
          <stringProp name="HTTPSampler.domain">localhost</stringProp>
          <stringProp name="HTTPSampler.port">8002</stringProp>
          <stringProp name="HTTPSampler.protocol">http</stringProp>
          <stringProp name="HTTPSampler.path">/docs</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
        </HTTPSamplerProxy>
        <hashTree/>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
"""

OPS_LISTENER = [{"op": "add_listener", "listener_kind": "backend_listener",
                 # Lo que un modelo viejo podria mandar: se tiene que IGNORAR.
                 "backend_listener_config": {"arguments": [
                     {"name": "influxdbUrl", "value": "http://otro:8086"}]}}]

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def huella(valor):
    return hashlib.sha256((valor or "").encode()).hexdigest()


def sin_maestro(texto):
    """Ningun texto ni atributo del XML es el maestro. Se compara por huella."""
    raiz = ET.fromstring(texto.encode() if "<?xml" in texto[:10] else
                         f"<r>{texto}</r>".encode())
    for el in raiz.iter():
        for valor in [el.text or "", *el.attrib.values()]:
            if huella(valor.strip()) == HUELLA_MAESTRO:
                return False
    return True


def argumentos_del_listener(texto):
    raiz = ET.fromstring(texto.encode() if "<?xml" in texto[:10] else
                         f"<r>{texto}</r>".encode())
    listeners = raiz.findall(".//BackendListener")
    if len(listeners) != 1:
        return None
    valores = {}
    for arg in listeners[0].iter("elementProp"):
        nombre = arg.find("stringProp[@name='Argument.name']")
        valor = arg.find("stringProp[@name='Argument.value']")
        if nombre is not None:
            valores[nombre.text] = (valor.text or "") if valor is not None else ""
    return valores


def comprobar_listener(etiqueta, valores, url_esperada, apps_esperadas):
    if not ok(valores is not None, f"{etiqueta}: hay exactamente un Backend Listener"):
        return
    ok("TOKEN" not in valores, f"{etiqueta}: el argumento «TOKEN» ya no existe")
    ok(huella(valores.get("influxdbToken")) == huella(ESCRITURA),
       f"{etiqueta}: influxdbToken lleva la huella del token de escritura de jmeter "
       f"({huella(valores.get('influxdbToken'))[:10]})")
    ok(valores.get("influxdbUrl") == f"${{__P(influxdbUrl,{url_esperada})}}",
       f"{etiqueta}: la URL es una propiedad con la de /monitoring/jmeter-config: "
       f"{valores.get('influxdbUrl')}")
    app = valores.get("application", "")
    ok(any(app == f"${{__P(application,{a})}}" for a in apps_esperadas),
       f"{etiqueta}: application con la regla de Observabilidad: {app}")
    ok(valores.get("testTitle") == app, f"{etiqueta}: testTitle igual que application")
    ok("Kinetix Test" not in json.dumps(valores), f"{etiqueta}: «Kinetix Test» ya no aparece")
    ok(not re.search(r"__P\([a-zA-Z]+,[^)]*[\s,(][^)]*\)", app + valores.get("influxdbUrl", "")),
       f"{etiqueta}: los valores por defecto de __P no llevan comas, parentesis ni espacios")


async def por_el_endpoint(db, usuario, payload, ops):
    """`refine_jmx_surgical` de verdad; solo la llamada al modelo esta sustituida."""
    from app.api.v1.endpoints import script_ai
    from app.schemas.refine_operations import RefineSurgicalRequest

    async def sin_ia(_db):
        return {}

    script_ai._call_ai = lambda *a, **k: (
        json.dumps({"operations": ops, "explanation": "S2.2"}), None)
    script_ai.load_ai_config_from_db = sin_ia
    return await script_ai.refine_jmx_surgical(RefineSurgicalRequest(**payload), usuario, db)


async def rutas_de_la_ia(client_id, cliente, url_config):
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.api.v1.endpoints.monitoring import nombre_de_corrida
    from app.core.config import settings
    from app.db.models.user import User
    from app.schemas.refine_operations import RefineOperationSet
    from app.services.engine.jmx_to_structure import parse_jmx_to_structure
    from app.services.engine.refine_operations_applier import (
        OperationError, apply_operations)

    url_db = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    url_db = url_db.rsplit("/", 1)[0] + f"/{BASE}"
    motor = create_async_engine(url_db)
    jmx_a = None
    try:
        async with AsyncSession(motor) as db:
            usuario = (await db.execute(
                select(User).where(User.username == "admin"))).scalar_one()

            # ---------- A. Con cliente y proyecto ----------
            print("\n--- A. La ruta de la IA, por el endpoint, con cliente ---")
            antes = nombre_de_corrida(cliente, PROYECTO)
            r = await por_el_endpoint(db, usuario, {
                "current_jmx": JMX_BASE, "prompt": "añade un backend listener",
                "client_id": client_id, "proyecto": PROYECTO}, OPS_LISTENER)
            despues = nombre_de_corrida(cliente, PROYECTO)
            ok(not r.error and r.operations_applied == 1,
               f"el endpoint aplica la operacion ({r.operations_applied}, error={r.error})")
            jmx_a = r.jmx_content
            ok(sin_maestro(jmx_a), "el .jmx NO lleva el token maestro (por huella)")
            comprobar_listener("A", argumentos_del_listener(jmx_a), url_config, {antes, despues})
            ok("otro:8086" not in jmx_a, "backend_listener_config del modelo se ignora")

            # ---------- B. Sin cliente ----------
            print("\n--- B. La misma ruta SIN cliente ni proyecto ---")
            antes = nombre_de_corrida("", PLAN)
            r = await por_el_endpoint(db, usuario, {
                "current_jmx": JMX_BASE, "prompt": "añade un backend listener"},
                OPS_LISTENER)
            despues = nombre_de_corrida("", PLAN)
            ok(not r.error, f"sin cliente NO se niega: el analista recibe el listener ({r.error})")
            ok(sin_maestro(r.jmx_content), "y tampoco lleva el maestro")
            comprobar_listener("B", argumentos_del_listener(r.jmx_content), url_config,
                               {antes, despues})
            ok(antes.startswith("sin-nombre-zztest-s2-2-plan-"),
               f"la regla da «sin-nombre» y el nombre del Test Plan: {antes}")

            # ---------- C. Sin token, por el endpoint ----------
            print("\n--- C. Sin token de escritura: error claro, por el endpoint ---")
            await db.execute(text(
                "UPDATE monitoring_config SET influxdb_token_encrypted = NULL"))
            r = await por_el_endpoint(db, usuario, {
                "current_jmx": JMX_BASE, "prompt": "añade un backend listener",
                "client_id": client_id, "proyecto": PROYECTO}, OPS_LISTENER)
            await db.rollback()
            ok(bool(r.error) and "No hay token de escritura" in r.error,
               f"el endpoint devuelve un error que lo dice: {(r.error or '')[:90]}")
            ok("BackendListener" not in r.jmx_content,
               "y no entrega ningun listener: el .jmx vuelve como estaba")
            tok = (await db.execute(text(
                "SELECT count(*) FROM monitoring_config "
                "WHERE influxdb_token_encrypted IS NOT NULL"))).scalar_one()
            ok(tok >= 1, "la transaccion se deshizo: el token sigue en la base")

        # ---------- D. El buzon vacio ----------
        print("\n--- D. El aplicador con el buzon vacio ---")
        estructura = parse_jmx_to_structure(JMX_BASE)
        ops = RefineOperationSet.model_validate(
            {"operations": OPS_LISTENER, "explanation": "S2.2"})
        try:
            apply_operations(estructura, ops.operations)
            ok(False, "sin buzon, el aplicador NO construye nada")
        except OperationError as exc:
            ok("buzón está vacío" in str(exc),
               f"sin buzon, error claro y ningun listener: {str(exc)[:80]}")
    finally:
        await motor.dispose()
    return jmx_a


def token_de_lectura():
    """El mismo token de lectura que usa la pantalla (O-D33)."""
    import psycopg2
    from app.api.v1.endpoints.observabilidad import _descifrar
    pg = psycopg2.connect(host="postgres", dbname=BASE, user="jmeter_user",
                          password=os.environ.get("PGPASSWORD", "jmeter_secure_2024"))
    try:
        cur = pg.cursor()
        cur.execute("SELECT influxdb_read_token_encrypted FROM monitoring_config "
                    "WHERE influxdb_read_token_encrypted IS NOT NULL LIMIT 1")
        return _descifrar(cur.fetchone()[0])
    finally:
        pg.close()


def flux(token, consulta):
    r = httpx.post(f"{INFLUX}/api/v2/query", params={"org": "performance"},
                   headers={"Authorization": f"Token {token}",
                            "Content-Type": "application/vnd.flux",
                            "Accept": "application/csv"},
                   content=consulta, timeout=60)
    r.raise_for_status()
    return [ln for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")]


def main():
    if "test" not in BASE:
        sys.exit(f"La base «{BASE}» no lleva «test» en el nombre: no se toca nada")
    if not ESCRITURA:
        sys.exit("falta KX_TOKEN_ESCRITURA (esta en lab/lab.env)")

    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=90.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    fila = next((c for c in cli.get(f"{API}/clients").json() if c["name"] == CLIENTE), None)
    if fila is None:
        fila = cli.post(f"{API}/clients", json={
            "name": CLIENTE, "description": "Suite S2.2: el Backend Listener."}).json()
    client_id = fila["id"]

    cfg = cli.get(f"{API}/monitoring/jmeter-config",
                  params={"client_id": client_id, "proyecto": PROYECTO}).json()
    valores_cfg = {a["nombre"]: a["valor"] for a in cfg["argumentos"]}
    url_config = valores_cfg["influxdbUrl"]
    ok(huella(valores_cfg["influxdbToken"]) == huella(ESCRITURA),
       "/monitoring/jmeter-config entrega el token de escritura de jmeter")

    jmx_a = asyncio.run(rutas_de_la_ia(client_id, CLIENTE, url_config))

    # ---------- E. El fragmento ----------
    print("\n--- E. /monitoring/jmeter-fragmento sale del modulo ---")
    r = cli.get(f"{API}/monitoring/jmeter-fragmento",
                params={"client_id": client_id, "proyecto": PROYECTO})
    ok(r.status_code == 200, f"el fragmento responde: {r.status_code}")
    ok(sin_maestro(r.text), "el fragmento no lleva el maestro")
    ok(r.text.rstrip().endswith("<hashTree/>"), "y lleva su hashTree para pegarlo")
    comprobar_listener("E", argumentos_del_listener(r.text), url_config,
                       {cfg["application"]})

    # ---------- F. La prueba real ----------
    print("\n--- F. JMeter de verdad, con el .jmx de la IA ---")
    if not jmx_a:
        ok(False, "no hay .jmx de la ruta A: no se puede correr")
        return terminar()
    application = f"zztest-s22-{datetime.now():%Y%m%d-%H%M%S}"
    url_dentro = url_config.replace("localhost:8086", "influxdb:8086")
    with open("/tmp/zztest_s22.jmx", "w", encoding="utf-8") as f:
        f.write(jmx_a)
    for viejo in ("/tmp/zztest_s22.jtl", "/tmp/zztest_s22.log"):
        if os.path.exists(viejo):
            os.remove(viejo)
    salida = subprocess.run(
        ["/opt/apache-jmeter-5.6.3/bin/jmeter", "-n", "-t", "/tmp/zztest_s22.jmx",
         "-l", "/tmp/zztest_s22.jtl", "-j", "/tmp/zztest_s22.log",
         f"-JinfluxdbUrl={url_dentro}", f"-Japplication={application}"],
        capture_output=True, text=True, timeout=240, cwd="/tmp")
    resumen = [l for l in salida.stdout.splitlines() if l.startswith("summary =")]
    print(f"    {resumen[-1] if resumen else salida.stdout[-300:]}")
    ok(bool(resumen) and "Err:     0" in resumen[-1], "la corrida termino sin errores")
    log = open("/tmp/zztest_s22.log", encoding="utf-8", errors="ignore").read() \
        if os.path.exists("/tmp/zztest_s22.log") else ""
    ok("Error writing metrics to influxDB" not in log and " 401" not in log,
       "el Backend Listener no se quejo al escribir (ni 401)")

    lectura = token_de_lectura()
    time.sleep(3)
    puntos = flux(lectura,
                  f'from(bucket:"jmeter") |> range(start:-1h)'
                  f' |> filter(fn:(r) => r["application"]=="{application}")'
                  f' |> group() |> count()')
    cuantos = int(puntos[1].split(",")[-1]) if len(puntos) > 1 else 0
    ok(cuantos > 0, f"llegaron puntos al cubo jmeter bajo {application}: {cuantos}")

    # ---------- La limpieza (regla 35) ----------
    print("\n--- Limpieza, regla 35 ---")
    apps = flux(lectura,
                'import "influxdata/influxdb/schema"'
                ' schema.tagValues(bucket:"jmeter", tag:"application", start:-2h)')
    nuestras = sorted({l.split(",")[-1] for l in apps[1:] if "zztest-s22-" in l})
    print(f"    applications zztest-s22-* en el cubo: {nuestras}")
    if ok(nuestras == [application] and application.startswith("zztest-"),
          "comprobacion previa: la unica zztest-s22-* es la de esta corrida"):
        r = httpx.post(f"{INFLUX}/api/v2/delete",
                       params={"org": "performance", "bucket": "jmeter"},
                       headers={"Authorization": f"Token {ESCRITURA}"},
                       json={"start": "2020-01-01T00:00:00Z", "stop": "2030-01-01T00:00:00Z",
                             "predicate": f'application="{application}"'}, timeout=60)
        ok(r.status_code == 204, f"borrado solo application={application}: {r.status_code}")
        quedan = flux(lectura,
                      f'from(bucket:"jmeter") |> range(start:-2h)'
                      f' |> filter(fn:(r) => r["application"]=="{application}") |> count()')
        ok(len(quedan) <= 1, "y ya no queda ningun punto suyo")
    for viejo in ("/tmp/zztest_s22.jmx", "/tmp/zztest_s22.jtl", "/tmp/zztest_s22.log"):
        if os.path.exists(viejo):
            os.remove(viejo)
    return terminar()


def terminar():
    print()
    if fallos:
        print(f"FALLOS: {len(fallos)}")
        for texto in fallos:
            print(f"  - {texto}")
        sys.exit(1)
    print("S2.2 — EL BACKEND LISTENER, DE UN SOLO SITIO: TODO PASA")


if __name__ == "__main__":
    main()
