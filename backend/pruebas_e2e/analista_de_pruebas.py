"""El usuario analista que comparten las suites de H8 (regla 26).

Varias suites necesitan comprobar que **un usuario que no es admin no puede**
hacer algo. Para eso hace falta una sesión suya, y una sesión cuesta un login.

`/auth/login` admite **cinco intentos por cuarto de hora y por IP, y los
correctos también consumen cupo** (regla 26). Si cada suite creara su analista,
entrara y lo borrara al terminar, correr tres suites seguidas dejaría la
plataforma sin acceso durante quince minutos.

Así que el analista es un **fixture compartido y persistente**:

- vive en la base de PRUEBAS, con prefijo `zztest_` (regla 29);
- su sesión se guarda en `/tmp/e2e_analista_h8.json` y se reutiliza;
- **ninguna suite lo borra al terminar**. Lo limpia `limpiar()` de abajo, que se
  llama a mano cuando de verdad se quiere quitar.

Es la excepción razonada a la limpieza por prefijo: el dato existe para las
pruebas, está marcado como tal, y borrarlo en cada pasada cuesta más de lo que
protege.
"""
import json
import os
import subprocess
import sys

import httpx

USUARIO = "zztest_h8_analista"
CLAVE = "ZZtest-h8-2026"
CORREO = f"{USUARIO}@zztest-h8.com"
SESION = "/tmp/e2e_analista_h8.json"


def obtener(cli_admin, api: str):
    """La sesión del analista. Lo crea y entra solo si hace falta.

    Devuelve un `httpx.Client` listo, o `None` si no se pudo (y lo dice).
    """
    # Crear es idempotente en la práctica: si ya existe, el backend contesta 400
    # y se sigue igual.
    cli_admin.post(f"{api}/users", json={
        "username": USUARIO, "email": CORREO, "full_name": "ZZTEST H8 Analista",
        "password": CLAVE, "role": "analyst", "is_active": True})

    if os.path.exists(SESION):
        ck = json.load(open(SESION))
        cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                           timeout=60.0)
        if cli.get(f"{api}/auth/me").status_code == 200:
            return cli

    r = httpx.post(f"{api}/auth/login", data={"username": USUARIO, "password": CLAVE},
                   timeout=60.0)
    if r.status_code != 200:
        print(f"no se pudo entrar como analista: {r.status_code} {r.text[:200]}")
        return None
    ck = dict(r.cookies)
    json.dump(ck, open(SESION, "w"))
    return httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                        timeout=60.0)


def limpiar(base: str = "jmeter_analyzer_test"):
    """Quita el analista. **No la llama ninguna suite**: es para cuando se
    quiera dejar la base de pruebas sin rastro."""
    if "test" not in base:
        sys.exit(f"PARADA: «{base}» no es una base de pruebas. No se borra nada.")
    subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", base, "-q", "-c",
         f"delete from user_clients where user_id in "
         f"  (select id from users where username = '{USUARIO}');"
         f"delete from users where username = '{USUARIO}';"],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True, text=True)
    if os.path.exists(SESION):
        os.remove(SESION)
    print("analista de pruebas retirado")


if __name__ == "__main__":
    limpiar(os.environ.get("KX_DB", "jmeter_analyzer_test"))
