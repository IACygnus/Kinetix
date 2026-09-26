"""Sesion de la base de PRUEBAS sin gastar cupo de login: token generado en proceso."""
import json, os, sys, uuid
from datetime import timedelta
sys.path.insert(0, "/app")
import psycopg2
from app.core.security import create_access_token
c = psycopg2.connect(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname="jmeter_analyzer_test")
cur = c.cursor(); cur.execute("select id, username, role from users where username='admin'"); uid, un, ro = cur.fetchone()
tok = create_access_token({"sub": str(uid), "username": un, "role": ro}, timedelta(minutes=120))
ck = [{"name": n, "value": v, "domain": "localhost", "path": "/", "expires": -1, "httpOnly": False, "secure": False, "sameSite": "Lax"}
      for n, v in (("access_token", tok), ("csrf_token", uuid.uuid4().hex))]
json.dump({"cookies": ck, "origins": []}, open(os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json"), "w")); print("ok")
