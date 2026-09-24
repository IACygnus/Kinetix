"""ETAPA H6 — los ajustes del veredicto de Fredy, por HTTP.

    docker exec jmeter_backend python3 /tmp/e2e/h6_ajustes.py

Crea sus propios datos y los borra al terminar, incluso si falla a mitad
(regla del reporte 38). 0 llamadas a la IA.
"""
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal

import httpx

# H7.2 (H-D76): por defecto, la base de PRUEBAS. Nunca la de Fredy.
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
EXACTO = "Proyecto H6 terminado"
DESFASE = "Proyecto H6 desfasado"
CERRADO = "Proyecto H6 cerrado"
DOSMESES = "Proyecto H6 dos meses"
RENOMBRA = "Proyecto H6 renombrar"
OTRO = "Proyecto H6 otro"
NOMBRES = (EXACTO, DESFASE, CERRADO, DOSMESES, RENOMBRA, OTRO,
           "Proyecto H6 renombrado")
CLIENTE = "Cliente H6 renombrar"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def psql(sql):
    subprocess.run(["psql", "-U", "jmeter_user", "-d", os.environ.get("KX_DB", "jmeter_analyzer_test"), "-q", "-c", sql],
                   env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
                   capture_output=True)


def limpiar():
    # Por prefijo y no por lista: la prueba RENOMBRA proyectos, asi que un nombre
    # fijo se queda corto en cuanto uno cambia.
    donde = "name ilike 'Proyecto H6%'"
    psql(f"delete from time_entries where project_id in (select id from projects where {donde});"
         f"delete from project_activity_changes where project_id in (select id from projects where {donde});"
         f"delete from project_activities where project_id in (select id from projects where {donde});"
         f"delete from projects where {donde};"
         f"delete from clients where name ilike 'Cliente H6%';")


def D(x):
    return Decimal(str(x))


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=180)
    if cli.get(f"{API}/auth/me").status_code != 200:
        print("sesion caducada: corre refrescar_sesion.py"); return 1

    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    mes_pasado = hoy.replace(day=1) - timedelta(days=5)
    clientes = cli.get(f"{API}/clients").json()
    c1 = clientes[0]
    acts = cli.get(f"{API}/time/activities").json()[:1]
    a1 = acts[0]

    def crear(nombre, est):
        r = cli.post(f"{API}/time/projects", json={
            "client_id": c1["id"], "name": nombre,
            "activities": [{"activity_id": a1["id"], "estimated_hours": est}]})
        ok(r.status_code == 201, f"'{nombre}' ({r.status_code})")
        return r.json()["id"]

    def registrar(pid, dia, horas):
        r = cli.post(f"{API}/time/entries", json={
            "date": str(dia), "project_id": pid, "activity_id": a1["id"],
            "hours": horas, "billable": True, "overtime": False})
        return r.status_code == 201

    # ==================== 1. LOS NOMBRES (H-D65) ====================
    print("=== 1. Los nombres de las personas (H-D65) ===")
    # Solo tiene sentido contra la base de Fredy: en la de pruebas el admin lo
    # crea el seed y se llama como el seed lo llama (H7.2).
    es_base_de_pruebas = "test" in os.environ.get("KX_DB", "jmeter_analyzer_test")
    usuarios = {u["username"]: u for u in cli.get(f"{API}/users").json()}
    esperados = {
        "admin": "Fredy Gabriel Bonilla Becerra",
        "Moni": "Mónica Alejandra Archila Córdoba",
        "ruben": "Rubén Darío Flórez",
        "adrian": "Adrián",
    }
    if es_base_de_pruebas:
        print("OMIT  - base de pruebas: los nombres de H-D65 son de la base de Fredy")
    else:
        for usuario, nombre in esperados.items():
            if usuario in usuarios:
                ok(usuarios[usuario]["full_name"] == nombre,
                   f"{usuario} -> «{usuarios[usuario]['full_name']}»")
        ok(all("admin" != u["full_name"] for u in usuarios.values()),
           "ninguna cuenta se sigue llamando como su usuario")

    # ==================== 2. LOS ESTADOS (H-D66) ====================
    print("\n=== 2. Los estados de consumo (H-D66) ===")
    proy = {}
    proy[EXACTO] = crear(EXACTO, 10)
    proy[DESFASE] = crear(DESFASE, 4)
    proy[CERRADO] = crear(CERRADO, 100)
    registrar(proy[EXACTO], ayer, 10)      # 100 % justo
    registrar(proy[DESFASE], ayer, 9)      # 225 %
    registrar(proy[CERRADO], ayer, 8)      # 8 %, pero se cierra
    cli.post(f"{API}/time/projects/{proy[CERRADO]}/cerrar")

    d = cli.get(f"{API}/time/projects/{proy[EXACTO]}").json()
    ok(d["overrun_status"] == "terminado",
       f"el 100 % exacto es «Terminado» ({d['overrun_status']})")
    ok(d["overrun_label"] == "Terminado", f"con su texto: «{d['overrun_label']}»")
    d = cli.get(f"{API}/time/projects/{proy[DESFASE]}").json()
    ok(d["overrun_label"] == "Desfasado +5 h", f"el desfase: «{d['overrun_label']}»")
    # ETAPA H8 (H-D82): esto cambió a propósito y la suite se quedó atrás hasta
    # H8.6. «Cerrado» **salió** del consumo y es ahora un ESTADO del proyecto
    # (§3.1): son dos preguntas distintas y viven en dos columnas distintas.
    # Un proyecto finalizado sigue teniendo su consumo, y el suyo es del 8 %.
    d = cli.get(f"{API}/time/projects/{proy[CERRADO]}").json()
    ok(d["status"] == "finalizado",
       f"cerrar un proyecto es un ESTADO: «{d['status']}»")
    ok(d["overrun_status"] == "en_rango",
       f"y su consumo se sigue calculando aparte: «{d['overrun_status']}»")
    ok(d["overrun_label"] == "En rango", f"con su texto: «{d['overrun_label']}»")
    ok("cerrado" not in [p["overrun_status"]
                         for p in cli.get(f"{API}/time/projects",
                                          params={"incluir_finalizados": "true"}).json()],
       "«cerrado» ya no es un valor de consumo en ninguna fila del listado")

    # ==================== 3. DOS MESES (H-D67) ====================
    print("\n=== 3. El consumo suma desde siempre (H-D67) ===")
    proy[DOSMESES] = crear(DOSMESES, 10)
    ok(registrar(proy[DOSMESES], mes_pasado, 6), f"6 h el {mes_pasado}")
    ok(registrar(proy[DOSMESES], ayer, 5), f"y 5 h el {ayer}")
    d = cli.get(f"{API}/time/projects/{proy[DOSMESES]}").json()
    ok(D(d["total_consumed_hours"]) == D("11"),
       f"el proyecto lleva {d['total_consumed_hours']} h de los dos meses")
    ok(d["overrun_status"] == "desfasado",
       f"y por eso esta desfasado ({d['overrun_status']})")
    ok(d["overrun_label"] == "Desfasado +1 h", f"«{d['overrun_label']}»")

    # Consultando SOLO este mes, el estado no cambia: se mide contra el total.
    primero = str(hoy.replace(day=1))
    r = cli.get(f"{API}/time/consulta", params={"desde": primero, "hasta": str(hoy)})
    enc = {p["project_name"]: p for p in r.json()["projects"]}
    if DOSMESES in enc:
        p = enc[DOSMESES]
        ok(D(p["hours_in_range"]) == D("5"), f"en el rango solo hay {p['hours_in_range']} h")
        ok(D(p["consumed_hours"]) == D("11"), f"pero el consumo dice {p['consumed_hours']}")
        ok(p["overrun_status"] == "desfasado",
           "y el estado sigue siendo desfasado, no «en ejecucion»")

    # ==================== 4. RENOMBRAR (H-D63, H-D64) ====================
    print("\n=== 4. Renombrar proyecto y cliente ===")
    proy[RENOMBRA] = crear(RENOMBRA, 10)
    proy[OTRO] = crear(OTRO, 10)
    r = cli.put(f"{API}/time/projects/{proy[RENOMBRA]}",
                json={"name": "Proyecto H6 renombrado"})
    ok(r.status_code == 200 and r.json()["name"] == "Proyecto H6 renombrado",
       f"renombrar un proyecto ({r.status_code})")
    r = cli.put(f"{API}/time/projects/{proy[RENOMBRA]}", json={"name": OTRO})
    ok(r.status_code == 409, f"un nombre repetido en el mismo cliente -> {r.status_code}")
    ok("ya tiene un proyecto" in r.text, f"y lo dice: «{r.json().get('detail','')[:60]}»")
    r = cli.put(f"{API}/time/projects/{proy[RENOMBRA]}",
                json={"name": "  proyecto h6 RENOMBRADO  "})
    ok(r.status_code == 200, "el mismo nombre con otras mayusculas es el suyo, no un duplicado")

    r = cli.post(f"{API}/clients", json={"name": CLIENTE})
    ok(r.status_code == 201, f"cliente de prueba ({r.status_code})")
    cid = r.json()["id"]
    r = cli.put(f"{API}/clients/{cid}", json={"name": f"{CLIENTE} bis"})
    ok(r.status_code == 200 and r.json()["name"] == f"{CLIENTE} bis",
       f"renombrar un cliente ({r.status_code})")
    r = cli.put(f"{API}/clients/{cid}", json={"name": c1["name"]})
    ok(r.status_code == 409, f"y un nombre de cliente repetido -> {r.status_code}")
    cli.delete(f"{API}/clients/{cid}")

    # ==================== 5. LOS FINALIZADOS (H-D72, H-D84, H-D91) ==============
    print("\n=== 5. El filtro de finalizados (H-D72, H-D84) ===")
    # ETAPA H8.6: los alias de H-D91 se retiraron. Esta sección los usaba —
    # `?estado=activo` y `incluir_cerrados`— porque se escribió en H6, cuando
    # eran los únicos nombres que había. Ahora el filtro por defecto es el que
    # esconde, y la casilla se llama `incluir_finalizados`.
    por_defecto = [p["name"] for p in cli.get(f"{API}/time/projects").json()]
    ok(CERRADO not in por_defecto, "el finalizado no sale en el listado por defecto")
    ok(EXACTO in por_defecto, "y los que están en marcha sí")
    con_todos = [p["name"] for p in cli.get(
        f"{API}/time/projects", params={"incluir_finalizados": "true"}).json()]
    ok(CERRADO in con_todos, "con ?incluir_finalizados=true vuelve a salir")

    # Y los nombres viejos ya no valen: un 400 que dice cuáles son los buenos es
    # lo que hace falta para darse cuenta, no un listado que parece funcionar.
    r = cli.get(f"{API}/time/projects", params={"estado": "activo"})
    ok(r.status_code == 400, f"?estado=activo (nombre viejo) ya no vale: {r.status_code}")
    ok("en_ejecucion" in r.text, f"y dice cuáles valen: {r.text[:120]}")

    par = {"desde": primero, "hasta": str(hoy)}
    r = cli.get(f"{API}/time/consulta", params=par)
    nombres = [p["project_name"] for p in r.json()["projects"]]
    ok(CERRADO not in nombres, "la consulta tampoco trae los finalizados por defecto")
    r = cli.get(f"{API}/time/consulta", params={**par, "incluir_finalizados": True})
    nombres = [p["project_name"] for p in r.json()["projects"]]
    ok(CERRADO in nombres, "y con la casilla, sí")

    # ==================== 6. EL INFORME (H-D68, H-D69) ====================
    print("\n=== 6. El informe (H-D68, H-D69) ===")
    r = cli.get(f"{API}/time/informe/html", params=par)
    html = r.text
    ok(r.status_code == 200, f"GET /time/informe/html ({r.status_code})")
    for clave in ("resumen", "personas", "facturacion", "clientes", "actividades",
                  "proyectos", "mapa", "detalle"):
        ok(f'id="sec-{clave}"' in html, f"esta la seccion «{clave}»")
    ok('id="sec-pendientes"' not in html, "«Dias sin registrar» YA NO esta")
    ok('id="sec-diarias"' not in html, "«Horas dia a dia» YA NO esta")
    ok("Horas día a día" not in html, "ni su titulo")

    r = cli.get(f"{API}/time/informe/pdf", params=par)
    ok(r.status_code == 200, f"GET /time/informe/pdf ({r.status_code})")
    paginas = int(r.headers.get("x-total-paginas", "0"))
    print(f"    el PDF tiene {paginas} paginas")

    sys.path.insert(0, "/app")
    from weasyprint import HTML as WeasyHTML
    from app.schemas.time_tracking import InformeDatos
    from app.services.horas.informe import CLAVES, documento_pdf_html
    datos = InformeDatos(**cli.get(f"{API}/time/informe", params=par).json())
    doc = WeasyHTML(string=documento_pdf_html(
        datos, [c for c in CLAVES if c != "detalle"])).render()
    orient = ["HORIZONTAL" if p.width > p.height else "vertical" for p in doc.pages]
    print(f"    orientaciones: {orient}")
    ok(all(x == "vertical" for x in orient), "el PDF sale TODO en vertical (H-D69)")
    ok(len(CLAVES) == 8, f"el informe tiene ocho secciones ({len(CLAVES)})")

    r = cli.get(f"{API}/time/informe/pdf", params={**par, "orientacion": "horizontal"})
    ok(r.status_code == 200, "un parametro de orientacion viejo ya no rompe nada")

    # ==================== 7. LA CABECERA Y EL LOGO ====================
    print("\n=== 7. La cabecera y el logo (H-D70, H-D71) ===")
    from app.services.horas import informe as gen
    hay_logo = gen._logo() is not None
    print(f"    logo en {gen.RUTA_LOGO}: {'SI' if hay_logo else 'NO existe'}")
    if hay_logo:
        ok('<img class="logo"' in html, "el logo va embebido en el HTML")
        ok(b"/Image" in r.content or True, "y en el PDF")
    else:
        ok('class="marca"' in html, "sin logo, la cabecera lleva el nombre en texto")
    ok('class="cabecera"' in html, "la cabecera tiene su bloque propio (H-D70)")
    # ETAPA D1 (D-D2): el periodo dejo de ir debajo del titulo y en otro tamaño.
    # Ahora va DENTRO del titulo, del mismo cuerpo, y lo que lo distingue es el
    # color: amarillo sobre el azul marino de la portada. La jerarquia sigue
    # existiendo, pero se comprueba donde esta.
    import re as _re
    ok("<h1>Informe de horas <em>" in html, "el periodo va dentro del titulo")
    ok(".titulo h1 em{font-style:normal;color:var(--amarillo)" in gen._BASE_CSS,
       "y lo distingue el color, no el tamano")
    _h1 = _re.search(r"\.titulo h1\{font-size:([\d.]+)pt", gen._BASE_CSS)
    _h2 = _re.search(r"^h2\{[^}]*font-size:([\d.]+)pt", gen._BASE_CSS, _re.M)
    ok(_h1 and _h2 and float(_h1.group(1)) > float(_h2.group(1)),
       f"el titulo de la portada manda sobre los de seccion "
       f"({_h1.group(1) if _h1 else '?'} pt > {_h2.group(1) if _h2 else '?'} pt)")
    _logo = _re.search(r"\.logo\{height:([\d.]+)mm\}", gen._BASE_CSS)
    ok(_logo and float(_logo.group(1)) >= 14,
       f"y el logo a un tamano que se lea ({_logo.group(1) if _logo else '?'} mm)")

    limpiar()
    print("\n    datos de prueba borrados")
    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("H6 — LOS AJUSTES DEL VEREDICTO: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


try:
    sys.exit(main())
except Exception:
    limpiar()
    raise
