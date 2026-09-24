"""CARGA REAL §4 — la tabla de sinónimos y el aviso de actividades nuevas.

    docker exec -e KX_API_PUERTO=8002 jmeter_backend python3 /tmp/e2e/carga_actividades_nuevas.py

Dos mitades, porque son dos cosas distintas:

**1. La tabla traduce (backend).** Un archivo que dice «Diseño y generación de
script», «Contextualización conocimiento proyecto» o «Análisis» no crea tres
actividades nuevas: las reconoce y las manda a las del catálogo. Es la razón de
ser del módulo, y si dejara de funcionar el catálogo volvería a llenarse de
variantes de escritura que ya no se pueden sumar.

**2. Lo que no conoce se avisa (pantalla).** Una actividad que la tabla no tiene
entra igual —no es un filtro—, pero la vista previa la enseña en un bloque
propio con **su nombre, sus filas y sus horas**, y el resumen lo repite después
de confirmar. Con el nombre a secas no se puede decidir si falta un sinónimo.

El archivo de prueba se fabrica aquí con `openpyxl`: es la única forma de
controlar exactamente qué texto se le da a la tabla.

Datos `ZZTEST-CARGA4` (regla 29), base de pruebas (regla 34). 0 llamadas a la IA.
"""
import io
import json
import os
import subprocess
import sys

import httpx
from playwright.sync_api import sync_playwright

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
PUERTO_API = os.environ.get("KX_API_PUERTO", "8002")

MARCA = "ZZTEST-CARGA4"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Lo que trae el archivo -> lo que tiene que acabar guardando. Las tres primeras
# las conoce la tabla; la cuarta no, y es la que tiene que salir avisada.
CONOCIDAS = [
    ("Diseño y generación de script", "Diseño de script"),
    ("Contextualización conocimiento proyecto", "Etapa de conocimiento"),
    ("Análisis", "Análisis de resultados"),
]
DESCONOCIDA = f"{MARCA} actividad inventada"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def psql(sql):
    return subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", BASE, "-q", "-t", "-A", "-c", sql],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True, text=True)


def limpiar():
    if "test" not in BASE:
        sys.exit(f"PARADA: «{BASE}» no es una base de pruebas. No se borra nada.")
    p = f"name like '{MARCA}%'"
    psql(
        f"delete from time_entries where project_id in (select id from projects where {p});"
        f"delete from project_status_changes where project_id in (select id from projects where {p});"
        f"delete from project_activity_changes where project_id in (select id from projects where {p});"
        f"delete from project_activities where project_id in (select id from projects where {p});"
        f"delete from projects where {p};"
        f"delete from activities where name like '{MARCA}%';"
    )


def libro(cliente, proyecto):
    """El `.xlsx` de prueba, con las columnas que pide H-D42.

    Cuatro filas de las conocidas y **dos** de la desconocida, para que el
    bloque tenga algo que contar: una sola fila no distingue «lo avisa» de «lo
    cuenta bien».
    """
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Id", "Observaciones", "Cliente", "Proyecto", "Tarea",
               "Extra Hour", "Fecha", "Tiempo total", "Facturable"])
    filas = [(t, "2026-08-18", 2) for t, _ in CONOCIDAS]
    filas += [(DESCONOCIDA, "2026-08-19", 3), (DESCONOCIDA, "2026-08-20", 1.5)]
    for i, (tarea, fecha, horas) in enumerate(filas, start=1):
        ws.append([f"{MARCA}-{i}", f"{MARCA} prueba", cliente, proyecto, tarea,
                   "No", fecha, horas, "Si"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=120.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    cliente = cli.get(f"{API}/clients").json()[0]["name"]
    proyecto = f"{MARCA}-proyecto"
    datos = libro(cliente, proyecto)

    print("=== 1. La vista previa: traduce lo que conoce y avisa lo que no ===")
    r = cli.post(f"{API}/time/import/preview",
                 files={"archivo": ("prueba.xlsx", datos, XLSX)})
    if not ok(r.status_code == 200, f"la previa responde {r.status_code} {r.text[:160]}"):
        return 1
    v = r.json()

    por_fila = {f["numero"]: f for f in v["nuevas"]}
    for i, (viene, deberia) in enumerate(CONOCIDAS, start=2):
        f = por_fila.get(i, {})
        ok(f.get("activity_name") == deberia,
           f"fila {i}: «{viene}» -> «{f.get('activity_name')}»")
        ok(f.get("activity_original") == viene,
           f"  y se conserva lo que decía el archivo: «{f.get('activity_original')}»")
    ok(por_fila.get(5, {}).get("activity_original") == "",
       "la desconocida NO se traduce: `activity_original` viene vacío")

    ok(v["actividades_a_crear"] == [DESCONOCIDA],
       f"solo se crea una actividad, la desconocida: {v['actividades_a_crear']}")

    bloques = v["actividades_nuevas"]
    if ok(len(bloques) == 1, f"el bloque del §4 trae {len(bloques)} actividad(es)"):
        b = bloques[0]
        ok(b["name"] == DESCONOCIDA, f"con su nombre: «{b['name']}»")
        ok(b["filas"] == [5, 6], f"y en qué filas aparece: {b['filas']}")
        ok(str(b["horas"]) in ("4.5", "4.50"), f"y cuántas horas trae: {b['horas']}")

    catalogo = [a["name"] for a in cli.get(f"{API}/time/activities").json()]
    ok(DESCONOCIDA not in catalogo,
       "**y la previa no creó nada**: la desconocida no está en el catálogo")

    print("\n=== 2. La pantalla lo enseña (ANTES de confirmar) ===")
    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={"width": 1600, "height": 1400},
                              storage_state=SESION, locale="es-CO")
        page = ctx.new_page()
        if PUERTO_API != "8001":
            page.route("http://localhost:8001/**", lambda rt: rt.continue_(
                url=rt.request.url.replace("localhost:8001", f"localhost:{PUERTO_API}")))
        page.goto(f"{WEB}/horas/importar", wait_until="networkidle")
        page.set_input_files("[data-testid=archivo]", {
            "name": "prueba.xlsx", "mimeType": XLSX, "buffer": datos})
        # Elegir el archivo NO analiza: la previa es un paso que se pide, no un
        # efecto de tocar el selector (§6.2.5).
        page.click("[data-testid=analizar]")
        page.wait_for_selector("[data-testid=vista-previa]", timeout=30000)
        page.wait_for_selector("[data-testid=actividades-nuevas]", timeout=30000)

        bloque = page.locator("[data-testid=actividades-nuevas]")
        ok(bloque.is_visible(), "el bloque «actividades nuevas» se ve")
        texto = bloque.inner_text()
        ok("no estaban en el catálogo" in texto,
           "y dice de qué va, con esas palabras")
        ok("sinónimo" in texto, "y que lo que puede faltar es un sinónimo")

        fila = page.locator("[data-testid=actividad-nueva]")
        ok(fila.count() == 1, f"con una sola actividad: {fila.count()}")
        ok(fila.first.get_attribute("data-nombre") == DESCONOCIDA,
           "la desconocida, por su nombre")
        ok(fila.first.get_attribute("data-filas") == "2",
           f"con sus 2 filas: {fila.first.get_attribute('data-filas')}")
        ok("4,5" in fila.first.inner_text(),
           f"y sus 4,5 h en español: «{fila.first.inner_text()}»")
        nav.close()

    print("\n=== 3. El resumen repite el bloque después de confirmar ===")
    r = cli.post(f"{API}/time/import/confirm",
                 files={"archivo": ("prueba.xlsx", datos, XLSX)})
    if not ok(r.status_code == 200, f"confirma {r.status_code} {r.text[:160]}"):
        return 1
    d = r.json()
    ok(d["creados"] == 5, f"entran las 5 filas: {d['creados']}")
    ok(d["actividades_creadas"] == [DESCONOCIDA],
       f"se creó solo la desconocida: {d['actividades_creadas']}")
    ok([b["name"] for b in d["actividades_nuevas"]] == [DESCONOCIDA],
       "y el resumen la vuelve a nombrar")

    guardadas = psql(
        "select a.name, sum(te.hours) from time_entries te "
        "join activities a on a.id = te.activity_id "
        f"join projects p on p.id = te.project_id where p.name = '{proyecto}' "
        "group by a.name order by a.name;").stdout.strip().splitlines()
    esperado = sorted([f"{d}|2.00" for _, d in CONOCIDAS] + [f"{DESCONOCIDA}|4.50"])
    ok(sorted(guardadas) == esperado,
       f"y en la base quedan con el nombre del catálogo: {sorted(guardadas)}")

    limpiar()
    print("\n" + "=" * 70)
    if fallos:
        print(f"FALLAN {len(fallos)}:")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("TODO PASA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
