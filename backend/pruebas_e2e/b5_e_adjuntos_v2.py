"""Reporte 150, parte 1 — el adjunto de errores tras la prueba real de Fredy.

    docker exec -e PYTHONPATH=/app/pruebas_e2e:/app jmeter_backend python3 /app/pruebas_e2e/b5_e_adjuntos_v2.py

Contra el 8002 y la base de PRUEBAS. Un XML ZZTEST sintético con todos los casos:
  - el FORMATO por el contenido: XML con extensión .csv y CSV con extensión .xml;
  - la CAUSA por orden: failureMessage de las aserciones → mensaje de error del
    responseData (errors[].errorMessage, errorMessage, message) → rm; de una
    traza de Java, la primera línea y el «Caused by»;
  - el enmascarado ampliado: Authorization/Bearer, claves JSON con token,
    password, secret, key, doc, account, login, user, customer o name, números
    largos, IP, MAC y cuerpos en base64.
Si existe /tmp/b5_errores_real.xml (una copia TEMPORAL del archivo de Fredy, que
no se versiona y se borra al terminar), se comprueba también: formato, recuento
y causa. Nada de su contenido se imprime.
"""
import base64
import json
import os
import random
from xml.sax.saxutils import escape, quoteattr

import b5_comun as B
from b5_comun import ok

A = B.API + "/analista/sesiones"
admin = B.cliente()
random.seed(150)
B64 = base64.b64encode(bytes(random.randrange(256) for _ in range(300))).decode()
SECRETOS = {
    "bearer": "ZZbearerSecreto150", "cookie": "ZZcookie150", "token": "ZZtoken150valor",
    "password": "ZZclave150!", "secret": "ZZsecret150", "apikey": "ZZapikey150",
    "doc": "1020304050", "account": "9876543210123", "login": "zzlogin150", "user": "zzusuario150",
    "customer": "ZZcliente-150", "fullname": "Ana Prueba Ciento", "name": "Nombre ZZ150",
    "ipv4": "10.20.30.40", "ipv6": "2001:db8:85a3:0:0:8a2e:370:7334", "mac": "00:1A:2B:3C:4D:5E",
    "b64": B64, "numero": "4111111111111111",
}
S = SECRETOS


def muestra(lb, rc, rm, aserciones=(), respuesta="", cabeceras=""):
    a = "".join(f"<assertionResult><name>{escape(n)}</name><failure>true</failure><error>false</error>"
                f"<failureMessage>{escape(m)}</failureMessage></assertionResult>" for n, m in aserciones)
    return (f'<httpSample t="120" ts="1790804838887" s="false" lb={quoteattr(lb)} rc={quoteattr(rc)} '
            f'rm={quoteattr(rm)} tn="Hilo 1-1" ng="28" na="35">{a}'
            f'<requestHeader class="java.lang.String">{escape(cabeceras)}</requestHeader>'
            f'<responseData class="java.lang.String">{escape(respuesta)}</responseData>'
            f'<java.net.URL>https://zztest.local/api/v1?apiKey={S["apikey"]}&amp;login={S["login"]}</java.net.URL>'
            f'<queryString class="java.lang.String">name={S["name"]}&amp;page=2</queryString></httpSample>')


CAB = f"Authorization: Bearer {S['bearer']}\nCookie: sesion={S['cookie']}\nX-Forwarded-For: {S['ipv4']}\nX-Equipo: {S['mac']}\nX-Origen: {S['ipv6']}\n"
CUERPO = json.dumps({"detalle_auth": f"llegó Bearer {S['bearer']} sin permisos", "status": "409", "errors": [{"errorCode": "500", "errorMessage": "Catalogo no disponible"}],
                     "token": S["token"], "password": S["password"], "clientSecret": S["secret"],
                     "documentNumber": S["doc"], "accountNumber": S["account"], "login": S["login"],
                     "userName": S["user"], "customerId": S["customer"], "fullName": S["fullname"],
                     "name": S["name"], "card": S["numero"], "origen": S["ipv6"], "equipo": S["mac"],
                     "payload": S["b64"]})
TRAZA = ("java.lang.IllegalStateException: Fallo al pignorar\n\tat co.zz.Servicio.pignorar(Servicio.java:42)\n"
         "\tat co.zz.Api.post(Api.java:10)\nCaused by: java.sql.SQLTimeoutException: tiempo de espera agotado\n"
         "\tat org.pg.Driver.exec(Driver.java:99)")
XML = ('<?xml version="1.0" encoding="UTF-8"?>\n<testResults version="1.2">\n' + "\n".join([
    muestra("1. Servicio A", "400", "", [("Assertion JSON", "Value in json path '$.status' expected '200' but was '409'"),
                                         ("Eco", "No devolvio transactionIdSN")], CUERPO, CAB),
    muestra("1. Servicio A", "400", "", [("Assertion JSON", "Value in json path '$.status' expected '200' but was '409'"),
                                         ("Eco", "No devolvio transactionIdSN")], CUERPO, CAB),
    muestra("2. Servicio B", "409", "Conflict", [], json.dumps({"errorMessage": "Fondos insuficientes en la cuenta"})),
    muestra("2. Servicio B", "500", "Internal Server Error", [],
            json.dumps({"errors": [{"errorCode": "E1", "message": "Timeout del core bancario"}]})),
    muestra("3. Servicio C", "500", "Internal Server Error", [], TRAZA),
    muestra("3. Servicio C", "502", "Bad Gateway", [], "<html>gateway</html>"),
    muestra("3. Servicio C", "503", "Service Unavailable", [], f"cuerpo cifrado {S['b64']}"),
]) + "\n</testResults>\n").encode()
CSV = (b"timeStamp,elapsed,label,responseCode,responseMessage,success,failureMessage\n"
       b"1790804838887,120,1. Servicio A,500,Internal Server Error,false,\n")

r = B.crear(admin, proyecto="ZZTEST-B5 adjuntos v2")
sid = r.json()["id"]


def subir(nombre, datos):
    return admin.post(f"{A}/{sid}/adjuntos", files={"archivo": (nombre, datos)})


print("== 1. El formato, por el contenido")
r = subir("errores_zztest.csv", XML)
ok(r.status_code == 201, f"XML con extensión .csv -> 201 ({r.status_code})")
s = r.json()
adj = s["adjuntos"][-1]
ok(adj["formato"] == "xml" and adj["resumen"]["formato"] == "xml", "se lee como XML")
r2 = subir("errores_zztest.xml", CSV)
ok(r2.status_code == 201 and r2.json()["adjuntos"][-1]["formato"] == "csv", "CSV con extensión .xml -> se lee como CSV")
ok(subir("errores.jtl", XML).status_code == 201, "también .jtl")
ok(subir("errores.txt", XML).status_code == 415, "una extensión que no es de JMeter, no")

print("== 2. La causa")
G = {(g["transaccion"], g["codigo"]): g for g in adj["resumen"]["grupos"]}
ga = G[("1. Servicio A", "400")]
ok(ga["recuento"] == 2 and "expected '200' but was '409'" in ga["mensaje"] and "transactionIdSN" in ga["mensaje"],
   "1) el failureMessage de las aserciones (las dos), antes que la respuesta")
ok(G[("2. Servicio B", "409")]["mensaje"] == "Fondos insuficientes en la cuenta", "2) errorMessage del JSON")
ok(G[("2. Servicio B", "500")]["mensaje"] == "Timeout del core bancario", "2) errors[].message del JSON")
gc = G[("3. Servicio C", "500")]["mensaje"]
ok(gc == "java.lang.IllegalStateException: Fallo al pignorar · Caused by: java.sql.SQLTimeoutException: tiempo de espera agotado",
   "traza de Java: primera línea y «Caused by»")
ok(G[("3. Servicio C", "502")]["mensaje"] == "Bad Gateway", "3) el rm cuando no hay nada más")
ok(len(adj["resumen"]["grupos"]) == 6, "grupos por transacción + código + causa (6)")

print("== 3. El enmascarado ampliado")
todo = json.dumps(s, ensure_ascii=False) + B.sql("select resumen::text from analysis_attachments where session_id=%s",
                                                (sid,))[0][0]
vistos = [k for k, v in SECRETOS.items() if v in todo]
ok(not vistos, f"ningún secreto a la vista, ni en la API ni en la base{' · aparecen: ' + str(vistos) if vistos else ''}")
ej = ga["ejemplos"][0]
for marca, que in (("Bearer [oculto]", "Bearer"), ("Authorization: [oculto]", "Authorization"),
                   ("[ip]", "IP"), ("[mac]", "MAC"), ("[cuerpo cifrado, ", "cuerpo en base64"),
                   ('"documentNumber": "[oculto]"', "doc"), ('"accountNumber": "[oculto]"', "account"),
                   ('"customerId": "[oculto]"', "customer"), ('"userName": "[oculto]"', "user"),
                   ('"fullName": "[oculto]"', "name")):
    ok(marca in ej["peticion"] + ej["respuesta"] + json.dumps(adj, ensure_ascii=False), f"se ve la marca de {que}")
ok("Catalogo no disponible" in ej["respuesta"], "lo que no es sensible sigue legible (el mensaje de error)")

print("== 4. El archivo real de Fredy (copia temporal, si está)")
REAL = "/tmp/b5_errores_real.xml"
if os.path.exists(REAL):
    datos = open(REAL, "rb").read()
    r = subir("real.csv", datos)
    ok(r.status_code == 201, f"el archivo real se lee ({r.status_code})")
    res = r.json()["adjuntos"][-1]["resumen"]
    ok(r.json()["adjuntos"][-1]["formato"] == "xml", "como XML, aunque se llame .csv")
    ok(res["errores"] == 2, f"sus 2 errores ({res['errores']})")
    ok(all("expected to match regexp" in g["mensaje"] for g in res["grupos"][:1]), "la causa sale de la aserción")
    texto = json.dumps(res, ensure_ascii=False)
    ok("PENDIENTE_CLIENTE" not in texto and "Authorization: [oculto]" in texto, "su Authorization, tapada")
else:
    print("  (no está la copia temporal: se salta)")

B.fin("B5 E (adjuntos v2)")
