"""BLOQUE 5 — lo comun de las suites del «Analista IA» (reporte 147).

Sesiones sin gastar cupo de login (regla 26): el token se genera en proceso,
como `r1_sesion_test.py`. Solo contra la base de PRUEBAS (regla 34): se para si
el nombre de la base no lleva `test`.

Los dos analistas son ZZTEST (regla 29) y persisten, como el de H8: crearlos y
borrarlos en cada pasada no protege nada.
"""
import os
import sys
import uuid
from datetime import timedelta

import httpx
import psycopg2

sys.path.insert(0, "/app")
from app.core.security import create_access_token, get_password_hash   # noqa: E402

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
DB = os.environ.get("KX_DB", "jmeter_analyzer_test")
JTL_R1 = "/app/uploads/ZZTEST-R1_carga.jtl"
PROYECTO = "ZZTEST-B5"
FALLOS = []

if "test" not in DB:
    sys.exit(f"PARADA: la base '{DB}' no lleva 'test' en el nombre")


def ok(cond, msg):
    print(("  ok   " if cond else "  FALLA ") + msg)
    if not cond:
        FALLOS.append(msg)
    return cond


def sql(q, args=()):
    c = psycopg2.connect(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB)
    c.autocommit = True
    cur = c.cursor()
    cur.execute(q, args)
    filas = cur.fetchall() if cur.description else []
    c.close()
    return filas


def _usuario(nombre, rol):
    fila = sql("select id, role from users where username=%s", (nombre,))
    if fila:
        return fila[0][0]
    uid = str(uuid.uuid4())
    sql("insert into users (id, username, email, full_name, hashed_password, role, is_active, created_at, "
        "updated_at) values (%s,%s,%s,%s,%s,%s,true,now(),now())",
        (uid, nombre, f"{nombre}@zztest-b5.com", f"ZZTEST {nombre}", get_password_hash(uuid.uuid4().hex), rol))
    return uid


def cliente(nombre="admin", rol="admin"):
    """Un httpx.Client con sesion de `nombre`. Los ZZTEST se crean si faltan."""
    uid = sql("select id from users where username=%s", (nombre,))[0][0] if nombre == "admin" else _usuario(nombre, rol)
    tok = create_access_token({"sub": str(uid), "username": nombre, "role": rol}, timedelta(minutes=120))
    csrf = uuid.uuid4().hex
    return httpx.Client(cookies={"access_token": tok, "csrf_token": csrf},
                        headers={"X-CSRF-Token": csrf}, timeout=600)


def crear(c, jtl=JTL_R1, proyecto=PROYECTO + " sesion", tipo="load"):
    with open(jtl, "rb") as f:
        return c.post(f"{API}/analista/sesiones", data={"proyecto": proyecto, "tipo": tipo},
                      files={"files": (os.path.basename(jtl), f)})


def fin(nombre):
    print()
    print(f"{nombre}: TODO PASA" if not FALLOS else f"{nombre}: {len(FALLOS)} FALLA(N)")
    sys.exit(1 if FALLOS else 0)
