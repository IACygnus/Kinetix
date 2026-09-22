"""Renueva /tmp/e2e_sesion.json con UN solo login.

/auth/login esta limitado a 5 intentos por 15 minutos y por IP, y los logins
CORRECTOS tambien consumen cupo: un intento, y si falla, error. Nunca en bucle.
"""
import json
import os
import sys

import httpx

# ETAPA H7.2 (H-D76): las suites pueden apuntar al backend de PRUEBAS (8002),
# que corre contra `jmeter_analyzer_test`. Sin la variable, el de siempre.
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")

with httpx.Client(timeout=60.0) as cli:
    # Si la sesion guardada sigue viva, no se gasta cupo.
    if os.path.exists(SESION):
        ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
        if cli.get(f"{API}/auth/me", cookies=ck).status_code == 200:
            print("la sesion guardada sigue viva: no se hace login")
            sys.exit(0)

    r = cli.post(f"{API}/auth/login",
                 data={"username": os.environ.get("KX_USER", "admin"),
                       "password": os.environ["KX_PWD"]})
    if r.status_code != 200:
        print(f"login {r.status_code}: {r.text[:200]}")
        sys.exit(1)

# Se guarda con la forma que esperan los demas scripts (storage_state de Playwright).
cookies = [{"name": k, "value": v, "domain": "localhost", "path": "/",
            "expires": -1, "httpOnly": False, "secure": False, "sameSite": "Lax"}
           for k, v in cli.cookies.items()]
json.dump({"cookies": cookies, "origins": []}, open(SESION, "w"))
print(f"sesion renovada: {[c['name'] for c in cookies]}")
