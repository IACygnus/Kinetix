"""O2e.2b — la ruta de ingesta, contra el backend de PRUEBAS. Sin InfluxDB real.

    docker exec -e KX_API=http://localhost:8002/api/v1 -e KX_DB=jmeter_analyzer_test \
        -e KX_SESION=/tmp/e2e_sesion_test.json jmeter_backend \
        python3 /app/pruebas_e2e/o2e2b_ingesta.py

Regla 34: `jmeter_analyzer_test` por el 8002; si la base no lleva «test» en el
nombre, se para sin tocar nada. Regla 29: los clientes son ZZTEST-. Requiere
docs/sql/o2e_infra_write_token.sql aplicado en esa base.

**No escribe en InfluxDB.** La suite levanta un InfluxDB FALSO en este mismo
proceso (127.0.0.1:8099), apunta ahi el `monitoring_config` de la base de
pruebas y lo deja como estaba al terminar. Asi se ve exactamente qué reenvia
Kinetix —cuerpo, token, cubo— y se puede hacer fallar a InfluxDB a voluntad.
La escritura real en `infra` es de O2e.3, con el agente del laboratorio.

1. CSRF: la escritura entra sin cookie; CUALQUIER otra ruta de /ingesta/, no.
2. El token de escritura de `infra`: se carga y no vuelve a salir.
3. Los tokens de ingesta: el alta lo ensena una vez; la lista, nunca.
4. La escritura: aceptada, rechazada por cliente (400 con recuento), cubo,
   token, cuerpo grande (413), InfluxDB caido o quejandose, revocado.
5. El ritmo: 300 por minuto y token, 429 con Retry-After.
6. La constancia en el log, y que ningun token aparece en el.
"""
import gzip
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import httpx
import psycopg2

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
LOG = os.environ.get("KX_LOG", "/tmp/backend_test.log")
ESCRIBIR = f"{API}/ingesta/api/v2/write"

CLIENTE = "ZZTEST-Ingesta O2e"          # con espacio: Telegraf lo escapa
OTRO = "ZZTEST-Ingesta O2e otro"
TOKEN_INFRA = "ZZTEST-token-infra-falso-" + uuid.uuid4().hex
PUERTO_FALSO = 8099

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


# ---------------------------------------------------------------------------
# El InfluxDB falso
# ---------------------------------------------------------------------------
class Falso:
    recibidas = []
    estado = 204


class Manejador(BaseHTTPRequestHandler):
    def do_POST(self):   # noqa: N802
        largo = int(self.headers.get("content-length") or 0)
        u = urlparse(self.path)
        Falso.recibidas.append({
            "ruta": u.path, "params": {k: v[0] for k, v in parse_qs(u.query).items()},
            "auth": self.headers.get("authorization"),
            "cuerpo": self.rfile.read(largo)})
        self.send_response(Falso.estado)
        cuerpo = b"" if Falso.estado == 204 else json.dumps(
            {"code": "unprocessable entity",
             "message": "ZZTEST field type conflict"}).encode()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass


def lineas(cliente, n=3, medida="zztest_o2e"):
    etiqueta = cliente.replace(" ", "\\ ").replace(",", "\\,")
    return "\n".join(f"{medida},cliente={etiqueta},host=zztest-srv{i} valor={i}i "
                     f"{1790000000 + i}" for i in range(n)) + "\n"


def main():
    if "test" not in BASE:
        sys.exit(f"La base «{BASE}» no lleva «test» en el nombre: no se toca nada")

    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO_FALSO), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    pg = psycopg2.connect(host="postgres", dbname=BASE, user="jmeter_user",
                          password=os.environ.get("PGPASSWORD", "jmeter_secure_2024"))
    pg.autocommit = True
    cur = pg.cursor()
    cur.execute("SELECT id, influxdb_url, influxdb_infra_write_token_encrypted "
                "FROM monitoring_config")
    antes = cur.fetchall()
    print(f"monitoring_config de pruebas: {len(antes)} filas guardadas para restaurar")

    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=60.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py con KX_API y KX_SESION")
    crudo = httpx.Client(timeout=60.0)    # sin cookie y sin cabecera CSRF
    log_inicio = os.path.getsize(LOG) if os.path.exists(LOG) else 0
    tokens_vistos = [TOKEN_INFRA]

    try:
        cur.execute("UPDATE monitoring_config SET influxdb_url = %s",
                    (f"http://127.0.0.1:{PUERTO_FALSO}",))
        correr(cli, crudo, cur, tokens_vistos)
    finally:
        for fila_id, url, tok in antes:
            cur.execute("UPDATE monitoring_config SET influxdb_url = %s, "
                        "influxdb_infra_write_token_encrypted = %s WHERE id = %s",
                        (url, tok, fila_id))
        cur.execute("SELECT id, influxdb_url, influxdb_infra_write_token_encrypted "
                    "FROM monitoring_config")
        ok(sorted(map(tuple, cur.fetchall())) == sorted(map(tuple, antes)),
           "monitoring_config de pruebas restaurada tal como estaba")
        servidor.shutdown()

    # ---------- 6. La constancia ----------
    print("\n--- 6. La constancia en el log ---")
    time.sleep(1)
    with open(LOG, encoding="utf-8", errors="replace") as f:
        f.seek(log_inicio)
        log = f.read()
    etiqueta = repr(CLIENTE)
    for resultado in ("aceptado", "rechazado_400", "rechazado_401",
                      "rechazado_413", "rechazado_429", "rechazado_503",
                      "rechazado_422"):
        ok(f"ingesta cliente={etiqueta}" in log and f"resultado={resultado}" in log,
           f"el log deja constancia de «{resultado}»")
    ok(f"ingesta cliente={etiqueta} puntos=3 resultado=aceptado" in log,
       "con el cliente y el numero de puntos")
    ok("3 lineas con cliente=«ZZTEST-Ingesta O2e»" in log,
       "y el motivo del rechazo")
    ok(not any(t in log for t in tokens_vistos),
       f"NINGUNO de los {len(tokens_vistos)} tokens aparece en el log")

    print()
    print("RESULTADO:", "TODO BIEN" if not fallos else f"{len(fallos)} FALLOS")
    for f in fallos:
        print("   -", f)
    sys.exit(1 if fallos else 0)


def correr(cli, crudo, cur, tokens_vistos):
    # ---------- 0. Los clientes ----------
    # Se buscan por SQL de LECTURA y no por GET /clients: en la base de pruebas
    # hay un `ZZTEST-R1` sin `created_at` que hace fallar esa lista entera (500
    # de validacion). No es de esta etapa y no se toca.
    clientes = {}
    for nombre in (CLIENTE, OTRO):
        cur.execute("SELECT id FROM clients WHERE name = %s", (nombre,))
        fila = cur.fetchone()
        clientes[nombre] = str(fila[0]) if fila else cli.post(f"{API}/clients", json={
            "name": nombre, "description": "Prueba O2e.2b. Marca ZZTEST."}).json()["id"]
    uno, otro = clientes[CLIENTE], clientes[OTRO]

    # ---------- 1. CSRF ----------
    print("\n--- 1. CSRF: la exencion es de UNA ruta ---")
    r = crudo.post(f"{ESCRIBIR}?bucket=infra", content=lineas(CLIENTE))
    ok(r.status_code == 401, f"la escritura sin cookie pasa el CSRF y pide token: {r.status_code}")
    for metodo, ruta in (
            ("POST", "/ingesta/tokens"),
            ("POST", f"/ingesta/tokens/{uuid.uuid4()}/revocar"),
            ("PUT", "/ingesta/token-escritura"),
            ("POST", "/ingesta/api/v2/write/"),
            ("POST", "/ingesta/api/v2/writex"),
            ("POST", "/ingesta/api/v2/write/otra"),
            ("POST", "/ingesta/API/v2/write"),
            ("POST", "/ingesta/api/v2/query"),
            ("POST", "/ingesta/"),
            ("PUT", "/ingesta/api/v2/write"),
            ("DELETE", "/ingesta/api/v2/write")):
        r = crudo.request(metodo, f"{API}{ruta}", content=b"{}",
                          headers={"Authorization": "Token x"})
        ok(r.status_code == 403 and "CSRF" in r.text,
           f"{metodo} {ruta} sin cookie ni cabecera: {r.status_code}")

    # ---------- 2. El token de escritura de infra ----------
    print("\n--- 2. El token de escritura de «infra» ---")
    r = cli.get(f"{API}/ingesta/token-escritura")
    ok(r.status_code == 200 and r.json()["columna_aplicada"] is True,
       f"la columna esta aplicada: {r.text}")
    r = cli.put(f"{API}/ingesta/token-escritura", json={"token": TOKEN_INFRA})
    ok(r.status_code == 204, f"el admin lo carga: {r.status_code}")
    r = cli.get(f"{API}/ingesta/token-escritura")
    ok(r.json()["hay_token"] is True and TOKEN_INFRA not in r.text,
       "dice que lo hay y no lo ensena")
    cur.execute("SELECT count(*) FROM monitoring_config "
                "WHERE influxdb_infra_write_token_encrypted LIKE %s",
                (f"%{TOKEN_INFRA}%",))
    ok(cur.fetchone()[0] == 0, "en la base esta cifrado, no en claro")

    # ---------- 3. Los tokens de ingesta ----------
    print("\n--- 3. Los tokens de ingesta ---")
    r = cli.post(f"{API}/ingesta/tokens", json={"client_id": uno})
    ok(r.status_code == 201, f"alta: {r.status_code}")
    alta = r.json()
    tok_a = alta["token"]
    tokens_vistos.append(tok_a)
    ok(tok_a.startswith("kxi_") and "una sola vez" in alta["aviso"],
       f"el alta lo ensena con el aviso: «{alta['aviso'][:60]}...»")
    r = cli.get(f"{API}/ingesta/tokens", params={"client_id": uno})
    ok(r.status_code == 200 and tok_a not in r.text and "token" not in r.json()[0],
       "la lista no lo lleva, ni entero ni como campo")
    cur.execute("SELECT count(*) FROM ingest_tokens WHERE huella = %s OR prefijo = %s",
                (tok_a, tok_a))
    ok(cur.fetchone()[0] == 0, "en la base no esta el token, solo su huella")
    tok_otro = cli.post(f"{API}/ingesta/tokens", json={"client_id": otro}).json()["token"]
    tokens_vistos.append(tok_otro)
    r = cli.post(f"{API}/ingesta/tokens", json={"client_id": str(uuid.uuid4())})
    ok(r.status_code == 404, f"cliente inexistente: {r.status_code}")

    def escribir(token, cuerpo, bucket="infra", gz=True, **extra):
        datos = cuerpo.encode() if isinstance(cuerpo, str) else cuerpo
        cab = {"Authorization": f"Token {token}", **extra}
        if gz:
            datos, cab["Content-Encoding"] = gzip.compress(datos), "gzip"
        return crudo.post(ESCRIBIR, params={"bucket": bucket, "org": "cualquiera"},
                          content=datos, headers=cab)

    # ---------- 4. La escritura ----------
    print("\n--- 4. La escritura ---")
    Falso.recibidas.clear()
    r = escribir(tok_a, lineas(CLIENTE))
    ok(r.status_code == 204, f"lote bueno con gzip: {r.status_code} {r.text}")
    ok(len(Falso.recibidas) == 1, "llega una peticion a InfluxDB")
    if Falso.recibidas:
        rec = Falso.recibidas[0]
        ok(rec["cuerpo"].decode() == lineas(CLIENTE),
           "reenvia exactamente el lote revisado, descomprimido")
        ok(rec["auth"] == f"Token {TOKEN_INFRA}",
           "con el token de escritura de infra, no con el del agente")
        ok(rec["params"].get("bucket") == "infra" and rec["params"].get("org") == "performance",
           f"al cubo infra y con el org de Kinetix, no el que mande el agente: {rec['params']}")
    fila = cli.get(f"{API}/ingesta/tokens", params={"client_id": uno}).json()[0]
    ok(fila["ultimo_uso"] is not None, f"el ultimo uso queda anotado: {fila['ultimo_uso']}")
    r = escribir(tok_a, lineas(CLIENTE), gz=False)
    ok(r.status_code == 204, f"sin comprimir tambien: {r.status_code}")

    Falso.recibidas.clear()
    r = escribir(tok_otro, lineas(CLIENTE))
    ok(r.status_code == 400 and "3 lineas con cliente=«ZZTEST-Ingesta O2e»" in r.json()["message"],
       f"token de otro cliente: {r.status_code} «{r.json().get('message')}»")
    mezcla = lineas(CLIENTE, 2) + lineas(OTRO, 1) + "zztest_o2e,host=x valor=1i\n"
    r = escribir(tok_a, mezcla)
    msg = r.json().get("message", "")
    ok(r.status_code == 400 and "2 de 4 lineas" in msg
       and "1 linea con cliente=«ZZTEST-Ingesta O2e otro»" in msg
       and "1 linea sin la etiqueta cliente" in msg,
       f"lote mezclado, rechazado entero: «{msg}»")
    ok(not Falso.recibidas, "y a InfluxDB no llega nada de ninguno de los dos")

    r = escribir(tok_a, lineas(CLIENTE), bucket="jmeter")
    ok(r.status_code == 400 and "infra" in r.json()["message"], f"cubo jmeter: {r.status_code}")
    r = crudo.post(ESCRIBIR, params={"bucket": "infra"}, content=lineas(CLIENTE))
    ok(r.status_code == 401, f"sin token: {r.status_code}")
    r = escribir("kxi_" + "x" * 43, lineas(CLIENTE))
    ok(r.status_code == 401, f"token inventado: {r.status_code}")

    r = escribir(tok_a, b"0" * (20 * 1024 * 1024))
    ok(r.status_code == 413, f"bomba de gzip (20 MB en ~20 KB): {r.status_code}")
    r = escribir(tok_a, b"x" * (1024 * 1024 + 1), gz=False)
    ok(r.status_code == 413, f"1 MB + 1 sin comprimir: {r.status_code}")
    r = escribir(tok_a, b"no es gzip", gz=False, **{"Content-Encoding": "gzip"})
    ok(r.status_code == 400, f"gzip roto: {r.status_code}")

    print("   · InfluxDB se queja o se cae")
    Falso.estado = 422
    r = escribir(tok_a, lineas(CLIENTE))
    ok(r.status_code == 422 and "ZZTEST field type conflict" in r.text,
       f"un 422 de InfluxDB es del lote: se devuelve tal cual: {r.status_code}")
    Falso.estado = 500
    r = escribir(tok_a, lineas(CLIENTE))
    ok(r.status_code == 503, f"un 500 de InfluxDB -> 503, Telegraf reintenta: {r.status_code}")
    Falso.estado = 401
    r = escribir(tok_a, lineas(CLIENTE))
    ok(r.status_code == 503, f"InfluxDB rechaza NUESTRO token -> 503, no se tiran lotes: {r.status_code}")
    Falso.estado = 204
    cur.execute("UPDATE monitoring_config SET influxdb_url = 'http://127.0.0.1:8098'")
    r = escribir(tok_a, lineas(CLIENTE))
    ok(r.status_code == 503, f"InfluxDB no responde -> 503: {r.status_code}")
    cur.execute("UPDATE monitoring_config SET influxdb_url = %s",
                (f"http://127.0.0.1:{PUERTO_FALSO}",))
    cur.execute("UPDATE monitoring_config SET influxdb_infra_write_token_encrypted = NULL")
    r = escribir(tok_a, lineas(CLIENTE))
    ok(r.status_code == 503 and "token de escritura" in r.json()["message"],
       f"sin token de infra cargado -> 503: {r.status_code}")
    cli.put(f"{API}/ingesta/token-escritura", json={"token": TOKEN_INFRA})

    print("   · revocar")
    r = cli.post(f"{API}/ingesta/tokens/{alta['id']}/revocar")
    ok(r.status_code == 200 and r.json()["revocado_en"], f"revocado: {r.status_code}")
    r = escribir(tok_a, lineas(CLIENTE))
    ok(r.status_code == 401 and "revoco" in r.json()["message"],
       f"con el token revocado ya no entra: {r.status_code} «{r.json().get('message')}»")

    # ---------- 5. El ritmo ----------
    print("\n--- 5. El ritmo: 300 por minuto y token ---")
    tok_c = cli.post(f"{API}/ingesta/tokens", json={"client_id": uno}).json()
    tokens_vistos.append(tok_c["token"])
    inicio, codigos = time.time(), []
    # Al cubo `jmeter`: el limitador ya las cuenta y no se reenvia nada.
    for _ in range(300):
        codigos.append(escribir(tok_c["token"], "x", bucket="jmeter", gz=False).status_code)
    duracion = time.time() - inicio
    ok(codigos.count(400) == 300, f"las 300 primeras pasan el limitador ({duracion:.0f} s)")
    r = escribir(tok_c["token"], lineas(CLIENTE))
    espera = r.headers.get("retry-after", "")
    ok(r.status_code == 429 and espera.isdigit() and 1 <= int(espera) <= 60,
       f"la 301: {r.status_code} con Retry-After: {espera!r}")
    r = escribir(tok_otro, lineas(OTRO))
    ok(r.status_code == 204, f"otro token no se ve afectado: {r.status_code}")

    # Limpieza: revocar lo que queda (regla 28: no se borra, se revoca).
    for cid in (uno, otro):
        for t in cli.get(f"{API}/ingesta/tokens", params={"client_id": cid}).json():
            if not t["revocado_en"]:
                cli.post(f"{API}/ingesta/tokens/{t['id']}/revocar")


if __name__ == "__main__":
    main()
