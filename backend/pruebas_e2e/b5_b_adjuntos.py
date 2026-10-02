"""BLOQUE 5, parte B — el archivo con el detalle de los errores, sin IA.

    docker exec -e PYTHONPATH=/app/pruebas_e2e jmeter_backend python3 /app/pruebas_e2e/b5_b_adjuntos.py

No había muestras reales en `C:\\proyectos\\Kinetix_pruebas\\muestras_errores\\`
(la carpeta no existe): los archivos se fabrican aquí, en memoria, con los
formatos ESTÁNDAR de JMeter a partir de los fallos del JTL de ZZTEST-R1, y se les
siembran secretos falsos para comprobar el enmascarado. Ninguno se versiona.
"""
import csv
import io
import json
from xml.sax.saxutils import escape, quoteattr

import pandas as pd

import b5_comun as B
from b5_comun import ok

from app.services.jtl.jtl_parser import JTLParser   # noqa: E402
from app.services.ai.resumen_serie import _ok   # noqa: E402
from app.services.zona_informe import a_informe   # noqa: E402
from app.services.analista.enmascarar import enmascarar   # noqa: E402

A = B.API + "/analista/sesiones"
admin = B.cliente()

# Secretos FALSOS sembrados en los archivos: no pueden aparecer en ninguna salida.
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ6enRlc3QifQ.c2VjcmV0b19mYWxzb196enRlc3Q"
SECRETOS = {
    "bearer": "ZZsecretoBearer123456",
    "jwt": JWT,
    "password": "ZZclave-Fal5a!",
    "apikey": "ZZapikey987654",
    "cookie": "ZZcookieValor0001",
    "correo": "persona.zztest@cliente-falso.com",
    "tarjeta": "4111 1111 1111 1111",
    "cedula": "1032456789",
    "secret_json": "ZZsecretJson42",
}

p = JTLParser(B.JTL_R1)
p.parse()
df = p.df_main if p.df_main is not None and len(p.df_main) else p.df
err = df[~_ok(df)].copy()
print(f"JTL: {len(err)} fallos")


def csv_errores(filas):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timeStamp", "elapsed", "label", "responseCode", "responseMessage", "threadName", "dataType",
                "success", "failureMessage", "bytes", "sentBytes", "grpThreads", "allThreads", "URL",
                "Latency", "IdleTime", "Connect"])
    for i, (_, r) in enumerate(filas.iterrows()):
        msg = str(r.get("failureMessage") or "")
        if i == 0:
            msg += f" Authorization: Bearer {SECRETOS['bearer']} token={SECRETOS['jwt']}"
        if i == 1:
            msg += f" password={SECRETOS['password']}&apikey={SECRETOS['apikey']} {SECRETOS['correo']}"
        if i == 2:
            msg += f" tarjeta {SECRETOS['tarjeta']} cedula {SECRETOS['cedula']}"
        w.writerow([int(r["timeStamp"]), int(r["elapsed"]), r["label"], r["responseCode"], r["responseMessage"],
                    r.get("threadName", ""), "text", "false", msg, 0, 0, 1, 1,
                    f"https://zztest.local/api?id=1&password={SECRETOS['password']}", 0, 0, 0])
    return buf.getvalue().encode()


def xml_errores(filas):
    partes = ['<?xml version="1.0" encoding="UTF-8"?>', '<testResults version="1.2">']
    for i, (_, r) in enumerate(filas.iterrows()):
        sampler = (f"POST https://zztest.local/api/booking\n\nPOST data:\n"
                   f'{{"usuario": "zz", "password": "{SECRETOS["password"]}", "secret": "{SECRETOS["secret_json"]}"}}'
                   f"\n\nCookie Data:\nJSESSIONID={SECRETOS['cookie']}\n")
        cab = f"Authorization: Bearer {SECRETOS['bearer']}\nCookie: sid={SECRETOS['cookie']}\n"
        resp = f'{{"error": "Forbidden", "detalle": "token {SECRETOS["jwt"]} vencido", "contacto": "{SECRETOS["correo"]}"}}'
        partes.append(
            f'<httpSample t="{int(r["elapsed"])}" ts="{int(r["timeStamp"])}" s="false" lb={quoteattr(str(r["label"]))} '
            f'rc={quoteattr(str(r["responseCode"]))} rm={quoteattr(str(r["responseMessage"]))} tn="hilo 1-1">'
            f'<requestHeader class="java.lang.String">{escape(cab)}</requestHeader>'
            f'<responseData class="java.lang.String">{escape(resp)}</responseData>'
            f'<samplerData class="java.lang.String">{escape(sampler)}</samplerData>'
            f'<assertionResult><name>Codigo</name><failure>true</failure><error>false</error>'
            f'<failureMessage>{escape(str(r.get("failureMessage") or "Test failed"))}</failureMessage></assertionResult>'
            f'<httpSample t="1" ts="{int(r["timeStamp"])}" s="false" lb="sub-muestra" rc="500"/>'
            f'<java.net.URL>https://zztest.local/api/booking?apikey={SECRETOS["apikey"]}</java.net.URL>'
            f'</httpSample>')
    partes.append("</testResults>")
    return "\n".join(partes).encode()


def subir(sid, nombre, datos, cli=admin):
    return cli.post(f"{A}/{sid}/adjuntos", files={"archivo": (nombre, datos)})


def sin_secretos(texto, donde):
    vistos = [k for k, v in SECRETOS.items() if v in texto]
    ok(not vistos, f"{donde}: ningún secreto a la vista{' · aparecen: ' + str(vistos) if vistos else ''}")


r = B.crear(admin, proyecto="ZZTEST-B5 adjuntos")
sid = r.json()["id"]

print("== 1. CSV de JMeter, completo")
r = subir(sid, "errores_zztest.csv", csv_errores(err))
ok(r.status_code == 201, f"subir el CSV -> 201 ({r.status_code})")
s = r.json()
adj = s["adjuntos"][0]
res = adj["resumen"]
ok(res["errores"] == len(err) == 1988 and res["filas"] == len(err), "1.988 errores leídos")
ok(sum(g["recuento"] for g in res["grupos"]) + ((res["otros"] or {}).get("recuento", 0)) == res["errores"],
   "los grupos suman todos los errores")
ok(len(res["grupos"]) <= 20 and all(len(g["ejemplos"]) <= 2 for g in res["grupos"]), "como mucho 20 grupos y 2 ejemplos")
claves = err.groupby(["label", "responseCode"]).size()
g0 = res["grupos"][0]
sub = err[(err["label"] == g0["transaccion"]) & (err["responseCode"].astype(str) == g0["codigo"])]
ok(g0["recuento"] <= len(sub) and abs(g0["porcentaje"] - 100 * g0["recuento"] / 1988) < 0.01,
   f"grupo mayor «{g0['transaccion']}» {g0['codigo']}: {g0['recuento']} ({g0['porcentaje']} %)")
ini = a_informe(pd.Timestamp(int(sub["timeStamp"].min()), unit="ms")).strftime("%d/%m/%Y %H:%M:%S")
if g0["recuento"] == len(sub):
    ok(g0["primero"] == ini, f"primer momento en hora de informe ({ini})")
ok(res["cruce"]["cuadra"] and "Cuadra" in res["cruce"]["texto"], f"cruce: {res['cruce']['texto']}")
ok("ruta" not in json.dumps(adj) and "/app/uploads" not in json.dumps(s), "la ruta del archivo no sale por la API")
sin_secretos(json.dumps(s, ensure_ascii=False), "la sesión (CSV)")
ok(any("[oculto]" in e["mensaje"] for g in res["grupos"] for e in g["ejemplos"])
   or any("[oculto]" in e["peticion"] for g in res["grupos"] for e in g["ejemplos"]), "se ve la marca [oculto]")
f = s["ficha"]
ok(next(p for p in f["pendientes"] if p["id"] == "detalle_errores")["estado"] == "resuelto", "pendiente de errores resuelto")
ok(f["errores_detalle"]["adjuntos"][0]["cuadra"] is True, "la ficha lleva el cruce")
fila = B.sql("select resumen::text from analysis_attachments where session_id=%s", (sid,))[0][0]
sin_secretos(fila, "la base (resumen guardado)")

print("== 2. CSV al que le faltan filas: no cuadra")
r = subir(sid, "errores_incompletos.csv", csv_errores(err.iloc[10:]))
c = r.json()["adjuntos"][1]["resumen"]["cruce"]
ok(not c["cuadra"] and c["archivo_total"] == 1978 and c["jtl_total"] == 1988 and c["diferencias"],
   f"no cuadra: {c['texto'][:120]}")
ok(r.json()["ficha"]["errores_detalle"]["adjuntos"][1]["cuadra"] is False, "la ficha dice que no cuadra")

print("== 3. XML de JMeter con datos")
r = subir(sid, "errores_zztest.xml", xml_errores(err))
ok(r.status_code == 201, f"subir el XML -> 201 ({r.status_code})")
x = r.json()["adjuntos"][2]["resumen"]
ok(x["errores"] == 1988 and x["cruce"]["cuadra"], "XML: 1.988 errores (sin contar las sub-muestras) y cuadra")
e = x["grupos"][0]["ejemplos"][0]
ok(e["respuesta"].startswith('{"error": "Forbidden"') and "POST https://zztest.local" in e["peticion"],
   "XML: el ejemplo trae petición y respuesta")
ok("[oculto]" in e["peticion"] and "[jwt]" in e["respuesta"] and "[correo]" in e["respuesta"],
   "XML: password, cookie, JWT y correo tapados")
sin_secretos(json.dumps(r.json(), ensure_ascii=False), "la sesión (XML)")

print("== 4. Lo que no se admite")
ok(subir(sid, "errores.txt", b"hola").status_code == 415, "un .txt -> 415")
ok(subir(sid, "errores.json", b"{}").status_code == 415, "un .json -> 415")
ok(subir(sid, "sin_extension", b"x").status_code == 415, "sin extensión -> 415")
ok(subir(sid, "no_jmeter.csv", b"a,b\n1,2\n").status_code == 400, "un CSV que no es de JMeter -> 400")
ok(subir(sid, "roto.xml", b"<testResults><httpSample").status_code == 400, "un XML roto -> 400")
bomba = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">'
         b'<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;">]><testResults><httpSample lb="&lol3;" s="false"/></testResults>')
r = subir(sid, "bomba.xml", bomba)
ok(r.status_code == 400 and "DOCTYPE" in r.json()["detail"], "XML con entidades anidadas (billion laughs) -> 400")
xxe = (b'<?xml version="1.0"?><!DOCTYPE t [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
       b'<testResults><httpSample lb="&x;" s="false"/></testResults>')
ok(subir(sid, "xxe.xml", xxe).status_code == 400, "XML con entidad externa (XXE) -> 400")
escondida = b'<?xml version="1.0"?><!--' + b"x" * 200000 + b'--><!DOCTYPE t [<!ENTITY x "y">]><testResults/>'
ok(subir(sid, "escondida.xml", escondida).status_code == 400, "DOCTYPE escondido tras un comentario de 200 KB -> 400")
ok(subir(sid, "grande.csv", b"x" * (20 * 1024 * 1024 + 10)).status_code == 413, "21 MB -> 413")
ok(subir(sid, "quinto.csv", csv_errores(err.iloc[:5])).status_code == 201, "el cuarto adjunto entra")
ok(subir(sid, "quinto2.csv", csv_errores(err.iloc[:5])).status_code == 201, "el quinto, también")
ok(subir(sid, "sexto.csv", csv_errores(err.iloc[:5])).status_code == 409, "el sexto -> 409")
anb = B.cliente("zztest_b5_analista_b", "analyst")
ok(subir(sid, "ajeno.csv", csv_errores(err.iloc[:5]), anb).status_code == 404, "en la sesión de otro -> 404")
ok(len(admin.get(f"{A}/{sid}").json()["adjuntos"]) == 5, "los rechazados no dejan rastro")

print("== 5. El enmascarado, regla a regla")
for entrada, no_debe in (
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
        ("Cookie: a=b; c=d", "a=b"),
        ('{"access_token": "abc123xyz"}', "abc123xyz"),
        ('{"password":12345}', "12345"),
        ("<ns:clientSecret>s3cr3t</ns:clientSecret>", "s3cr3t"),
        ("<password>pw</password>", ">pw<"),
        ("url?api_key=KK&x=1", "KK"),
        ("clave=Hola123", "Hola123"),
        ("contacto: ana@zz.com", "ana@zz.com"),
        ("tarjeta 5500-0000-0000-0004", "5500-0000-0000-0004"),
        ("documento 52123456", "52123456"),
        ("Bearer abcdefghijkl", "abcdefghijkl"),
        (JWT, "eyJhbGciOiJIUzI1NiJ9")):
    ok(no_debe not in enmascarar(entrada), f"tapa: {entrada[:40]}")
ok(enmascarar("HTTP 500 en 3 de 10") == "HTTP 500 en 3 de 10", "no toca códigos ni números cortos")

B.fin("B5 B (adjuntos de errores)")
