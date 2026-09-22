"""ETAPA O2c.1 — el modelo y los endpoints, contra el laboratorio de verdad.

    docker exec jmeter_backend python3 /tmp/e2e/o2c1_backend.py

Regla 34: contra `jmeter_analyzer_test` por el 8002. Regla 29: todo marcado
ZZTEST-. 0 llamadas a la IA.

Lo que se comprueba, en orden:
  1. El CRUD entero.
  2. **O-D26: la credencial NO vuelve a salir.** Ni en el alta, ni en la
     lectura, ni en la lista, ni tras editarla. Se busca el valor literal en el
     cuerpo crudo de cada respuesta, no en el JSON ya interpretado.
  3. La prueba de conexion (O-D24) contra los dos servidores del laboratorio.
  4. El generador de configuracion (O-D25) en los dos modos.
  5. O-D27: los servidores activos del cliente salen por `de-corrida`.
"""
import json
import os
import sys
import uuid

import httpx

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
CLIENTE = "ZZTEST-Observabilidad O2c"
# La contrasena del rol de solo lectura del laboratorio. Se pasa por entorno:
# no se escribe en el codigo ni se imprime nunca.
CLAVE_PG = os.environ.get("LAB_PG_LECTOR_PASSWORD", "")
LLAVE_SSH = os.environ.get("KX_LLAVE_SSH", "")

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def sin_rastro(respuesta, secretos, donde):
    """El secreto no puede estar en el cuerpo CRUDO de la respuesta.

    Se mira el texto tal cual, no el JSON ya interpretado: si algun dia
    apareciera dentro de un mensaje de error o de un campo nuevo, asi se ve.
    """
    crudo = respuesta.text
    for secreto in secretos:
        if secreto and secreto in crudo:
            return ok(False, f"{donde}: EL SECRETO APARECE EN LA RESPUESTA")
    return ok(True, f"{donde}: la credencial no aparece")


def main():
    if not CLAVE_PG or not LLAVE_SSH:
        sys.exit("faltan LAB_PG_LECTOR_PASSWORD o KX_LLAVE_SSH en el entorno")

    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck,
                       headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=90.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre /tmp/e2e/refrescar_sesion.py")

    # ---------- El cliente ----------
    print("\n--- 0. El cliente de la prueba ---")
    clientes = cli.get(f"{API}/clients").json()
    fila = next((c for c in clientes if c["name"] == CLIENTE), None)
    if fila is None:
        fila = cli.post(f"{API}/clients", json={
            "name": CLIENTE,
            "description": "Cliente de prueba de la etapa O2c. Marca ZZTEST.",
        }).json()
    client_id = fila["id"]
    ok(bool(client_id), f"cliente «{CLIENTE}» listo")

    # Limpieza de una corrida anterior: SOLO lo de este cliente ZZTEST.
    for viejo in cli.get(f"{API}/observabilidad/servidores",
                         params={"client_id": client_id}).json():
        cli.delete(f"{API}/observabilidad/servidores/{viejo['id']}")

    # ---------- 1. Alta ----------
    print("\n--- 1. Alta de los dos servidores del laboratorio ---")
    r = cli.post(f"{API}/observabilidad/servidores", json={
        "client_id": client_id,
        "name": "lab_servidor", "tipo": "linux", "modo": "sin_agente",
        "direccion": "lab_servidor", "puerto": 22,
        "usuario": "kinetix_lector", "credencial": LLAVE_SSH,
        "notas": "ZZTEST — el Linux del laboratorio",
    })
    ok(r.status_code == 201, f"alta del Linux: {r.status_code}")
    sin_rastro(r, [LLAVE_SSH], "en la respuesta del alta")
    linux = r.json()
    ok(linux["tiene_credencial"] is True, "dice que tiene credencial")
    ok("credencial" not in linux and "credencial_cifrada" not in linux,
       "y no hay ningun campo de credencial en la respuesta")

    r = cli.post(f"{API}/observabilidad/servidores", json={
        "client_id": client_id,
        "name": "lab_db", "tipo": "postgresql", "modo": "sin_agente",
        "direccion": "lab_db", "puerto": 5432,
        "usuario": "kinetix_lector", "credencial": CLAVE_PG,
        "notas": "tienda",
    })
    ok(r.status_code == 201, f"alta de PostgreSQL: {r.status_code}")
    sin_rastro(r, [CLAVE_PG], "en la respuesta del alta de la base")
    base = r.json()

    # Nombre repetido en el mismo cliente.
    r = cli.post(f"{API}/observabilidad/servidores", json={
        "client_id": client_id, "name": "lab_servidor", "tipo": "linux",
        "modo": "sin_agente", "direccion": "otro", "puerto": 22})
    ok(r.status_code == 409, f"dos servidores con el mismo nombre: {r.status_code}")

    # ---------- 2. O-D26, en todas las lecturas ----------
    print("\n--- 2. O-D26: la credencial no vuelve a salir NUNCA ---")
    sin_rastro(cli.get(f"{API}/observabilidad/servidores/{linux['id']}"),
               [LLAVE_SSH], "en el detalle")
    sin_rastro(cli.get(f"{API}/observabilidad/servidores",
                       params={"client_id": client_id}),
               [LLAVE_SSH, CLAVE_PG], "en la lista")

    r = cli.put(f"{API}/observabilidad/servidores/{linux['id']}",
                json={"notas": "ZZTEST — editado sin tocar la credencial"})
    ok(r.status_code == 200 and r.json()["tiene_credencial"] is True,
       "editar sin mandar credencial la deja intacta")
    sin_rastro(r, [LLAVE_SSH], "tras editar")

    r = cli.put(f"{API}/observabilidad/servidores/{linux['id']}",
                json={"credencial": "ZZTEST-credencial-sustituida"})
    ok(r.status_code == 200 and r.json()["tiene_credencial"] is True,
       "se puede sustituir por una nueva")
    sin_rastro(r, ["ZZTEST-credencial-sustituida"], "tras sustituirla")
    # Y se devuelve la buena, que la prueba de conexion la necesita.
    cli.put(f"{API}/observabilidad/servidores/{linux['id']}",
            json={"credencial": LLAVE_SSH})

    r = cli.put(f"{API}/observabilidad/servidores/{base['id']}",
                json={"credencial": ""})
    ok(r.status_code == 200 and r.json()["tiene_credencial"] is False,
       "la cadena vacia la borra, que es una decision explicita")
    cli.put(f"{API}/observabilidad/servidores/{base['id']}",
            json={"credencial": CLAVE_PG})

    # ---------- 3. O-D24, la prueba de conexion ----------
    print("\n--- 3. O-D24: la prueba de conexion ---")
    r = cli.post(f"{API}/observabilidad/servidores/{linux['id']}/probar")
    ok(r.status_code == 200, f"probar el Linux responde: {r.status_code}")
    prueba = r.json()
    print(f"    {prueba['resumen']}  ({prueba['duracion_ms']} ms)")
    for lectura in prueba["lecturas"]:
        print(f"      {'si' if lectura['ok'] else 'NO'}  {lectura['que']}: "
              f"{lectura['detalle'][:90]}")
    ok(prueba["ok"] is True, "se llega al Linux del laboratorio")
    ok(any("SSH" in l["detalle"] for l in prueba["lecturas"]),
       "y se reconoce que habla SSH")
    sin_rastro(r, [LLAVE_SSH], "en el resultado de la prueba")

    r = cli.post(f"{API}/observabilidad/servidores/{base['id']}/probar")
    prueba_db = r.json()
    print(f"    {prueba_db['resumen']}  ({prueba_db['duracion_ms']} ms)")
    for lectura in prueba_db["lecturas"]:
        print(f"      {'si' if lectura['ok'] else 'NO'}  {lectura['que']}: "
              f"{lectura['detalle'][:90]}")
    ok(prueba_db["ok"] is True, "se conecta a la base del laboratorio")
    vistas = {l["que"]: l["ok"] for l in prueba_db["lecturas"]}
    ok(any(v and "pg_stat_database" in q for q, v in vistas.items()),
       "y lee pg_stat_database")
    ok(any(v and "pg_stat_statements" in q for q, v in vistas.items()),
       "y pg_stat_statements, que es la de consultas lentas")
    sin_rastro(r, [CLAVE_PG], "en el resultado de la prueba de la base")

    # Uno que no existe, para ver que el error REAL sale (O-D24).
    r = cli.post(f"{API}/observabilidad/servidores", json={
        "client_id": client_id, "name": "ZZTEST-inalcanzable", "tipo": "linux",
        "modo": "sin_agente", "direccion": "no-existe-este-host", "puerto": 22})
    malo = r.json()
    prueba_mala = cli.post(
        f"{API}/observabilidad/servidores/{malo['id']}/probar").json()
    ok(prueba_mala["ok"] is False, "un servidor inalcanzable falla")
    ok(bool(prueba_mala["error"]),
       f"y dice el error de verdad: {str(prueba_mala['error'])[:70]}")
    cli.delete(f"{API}/observabilidad/servidores/{malo['id']}")

    # ---------- 4. O-D25, el generador ----------
    print("\n--- 4. O-D25: el generador de configuracion ---")
    r = cli.get(f"{API}/observabilidad/servidores/{linux['id']}/configuracion")
    cfg = r.json()
    ok(r.status_code == 200 and cfg["modo"] == "sin_agente",
       "modo sin agente: da los parametros del recolector")
    nombres = [p["nombre"] for p in cfg["parametros"]]
    ok("KX_OBJETIVOS" in nombres and "KX_INFLUX_BUCKET" in nombres,
       f"con los parametros que hacen falta: {len(nombres)}")
    ok("O-D28" not in cfg["aviso"] and "NO la ejecuta" in cfg["aviso"],
       "y con el aviso de que Kinetix no ejecuta nada (O-D28)")
    sin_rastro(r, [LLAVE_SSH, CLAVE_PG], "en la configuracion generada")

    cli.put(f"{API}/observabilidad/servidores/{linux['id']}",
            json={"modo": "agente"})
    cfg = cli.get(
        f"{API}/observabilidad/servidores/{linux['id']}/configuracion").json()
    ok(cfg["modo"] == "agente" and cfg["orden"],
       "modo agente: da la orden de instalacion")
    ok("--token-fichero" in cfg["orden"],
       "con --token-fichero, no --token (el token no va en la linea de ordenes)")
    ok("instalar_agente.sh" in cfg["orden"], "y llama al instalador de O2b")
    cli.put(f"{API}/observabilidad/servidores/{linux['id']}",
            json={"modo": "sin_agente"})

    # ---------- 5. O-D27 ----------
    print("\n--- 5. O-D27: los servidores de la corrida ---")
    de_corrida = cli.get(f"{API}/observabilidad/servidores/de-corrida",
                         params={"client_id": client_id}).json()
    ok(len(de_corrida) == 2,
       f"los dos servidores activos del cliente: {len(de_corrida)}")
    cli.put(f"{API}/observabilidad/servidores/{base['id']}",
            json={"activo": False})
    de_corrida = cli.get(f"{API}/observabilidad/servidores/de-corrida",
                         params={"client_id": client_id}).json()
    ok(len(de_corrida) == 1, "uno desactivado ya no entra en la corrida")
    cli.put(f"{API}/observabilidad/servidores/{base['id']}",
            json={"activo": True})

    # ---------- 6. Baja ----------
    print("\n--- 6. Baja ---")
    r = cli.post(f"{API}/observabilidad/servidores", json={
        "client_id": client_id, "name": "ZZTEST-para-borrar", "tipo": "otro",
        "modo": "sin_agente", "direccion": "x", "puerto": 1})
    sobra = r.json()["id"]
    ok(cli.delete(f"{API}/observabilidad/servidores/{sobra}").status_code == 204,
       "se da de baja")
    ok(cli.get(f"{API}/observabilidad/servidores/{sobra}").status_code == 404,
       "y ya no esta")

    print()
    if fallos:
        print(f"FALLOS: {len(fallos)}")
        for texto in fallos:
            print(f"  - {texto}")
        sys.exit(1)
    print("O2c.1 — EL MODELO Y LOS ENDPOINTS: TODO PASA")


if __name__ == "__main__":
    main()
