"""ETAPA H8.4 — las horas extra en el mapa del mes (H-D85, H-D86).

    docker exec jmeter_backend python3 /tmp/e2e/h84_mapa.py

Un día con horas extra se pinta **partido**: abajo las ordinarias con el color
del día y arriba las extra en azul, **en proporción a las horas de cada tipo**.
En pantalla, en el HTML y en el PDF.

Lo que no se puede dar por bueno leyendo el HTML es **si WeasyPrint honra el
gradiente**. Eso se comprueba rasterizando el PDF y **contando píxeles de cada
color dentro de la casilla**: si el gradiente se ignorara, la casilla saldría de
un solo color y la cuenta de azul sería cero.

Datos `ZZTEST-H84` (regla 29), limpieza solo por ese prefijo (regla 30), contra
la base de pruebas (regla 34). 0 llamadas a la IA.
"""
import glob
import json
import os
import re
import subprocess
import sys
from decimal import Decimal

import httpx

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
MARCA = "ZZTEST-H84"
PERIODO = {"desde": "2026-09-01", "hasta": "2026-09-30"}

# Martes 8 y miércoles 9 de septiembre de 2026, los dos laborables.
DIA_NORMAL = "2026-09-08"       # 8,5 ordinarias, jornada completa, sin extras
DIA_CON_EXTRA = "2026-09-09"    # 8,5 ordinarias + 2 extra -> 10,5 en total

# 8,5 de 10,5 son ordinarias: el corte va al 81,0 %.
CORTE = round(float(Decimal("8.5") / Decimal("10.5")) * 100, 1)
VERDE = (0xdc, 0xfc, 0xe7)
AZUL = (0xbf, 0xdb, 0xfe)

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
    )


def cerca(pixel, color, tolerancia=12):
    return all(abs(pixel[i] - color[i]) <= tolerancia for i in range(3))


def main():
    limpiar()
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=180.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    cliente = cli.get(f"{API}/clients").json()[0]["id"]
    act = cli.get(f"{API}/time/activities").json()[0]["id"]
    r = cli.post(f"{API}/time/projects", json={
        "client_id": cliente, "name": f"{MARCA}-proyecto",
        "activities": [{"activity_id": act, "estimated_hours": 100}]})
    if r.status_code != 201:
        sys.exit(f"no se pudo crear el proyecto: {r.status_code} {r.text[:200]}")
    pid = r.json()["id"]

    for fecha, h, extra in ((DIA_NORMAL, "8.5", False),
                            (DIA_CON_EXTRA, "8.5", False),
                            (DIA_CON_EXTRA, "2", True)):
        rr = cli.post(f"{API}/time/entries", json={
            "project_id": pid, "activity_id": act, "date": fecha, "hours": h,
            "billable": True, "overtime": extra, "notes": f"{MARCA} prueba"})
        if rr.status_code != 201:
            sys.exit(f"no se pudo registrar {fecha} ({h} h): {rr.status_code} {rr.text[:200]}")

    print("=== 1. El dato llega separado ===")
    datos = cli.get(f"{API}/time/informe", params=PERIODO).json()
    fila = next((m for m in datos["mapa"] if m["user_name"]), None)
    if not ok(fila is not None, "el mapa trae la fila de la persona"):
        return 1
    i_normal = datos["dias"].index(DIA_NORMAL)
    i_extra = datos["dias"].index(DIA_CON_EXTRA)
    ok("extra_por_dia" in fila, "la respuesta trae `extra_por_dia` (H-D85)")
    ok(len(fila["extra_por_dia"]) == len(fila["por_dia"]),
       "alineado con `por_dia`, día a día")
    ok(Decimal(str(fila["por_dia"][i_extra])) == Decimal("10.5"),
       f"el día con extras suma 10,5 h: {fila['por_dia'][i_extra]}")
    ok(Decimal(str(fila["extra_por_dia"][i_extra])) == Decimal("2"),
       f"y 2 de ellas son extra: {fila['extra_por_dia'][i_extra]}")
    ok(Decimal(str(fila["extra_por_dia"][i_normal])) == Decimal("0"),
       "el día sin extras trae 0")

    print("\n=== 2. El HTML parte la casilla, y solo esa ===")
    html = cli.get(f"{API}/time/informe/html", params=PERIODO).text
    mapa = re.search(r'<table class="mapa">.*?</table>', html, re.S)
    if not ok(mapa is not None, "se encuentra la tabla del mapa"):
        return 1
    casillas = re.findall(r'<td class="casilla([^"]*)"([^>]*)>', mapa.group(0))
    partidas = [(c, a) for c, a in casillas if "conextra" in c]
    ok(len(partidas) == 1, f"hay UNA casilla partida, no {len(partidas)}")
    if partidas:
        atributos = partidas[0][1]
        ok(f"{CORTE}%" in atributos,
           f"el corte va al {CORTE} % —8,5 de 10,5—, en proporción: {atributos[:120]}")
        ok("#dcfce7" in atributos and "#bfdbfe" in atributos,
           "con el verde abajo y el azul de H-D85 arriba")
        ok("linear-gradient(to top" in atributos,
           "y el azul va ARRIBA, no abajo")
        ok('data-extra="2"' in atributos, "la casilla dice cuántas extra lleva")

    print("\n=== 3. La leyenda y el párrafo (H-D86) ===")
    ok('<span class="mini extra"></span> horas extra</span>' in html,
       "la leyenda nombra el azul, como a los otros cinco")
    ok(".mini.extra{background:#bfdbfe}" in html,
       "con el color del documento de diseño")
    ok("sale partido" in html and "en proporción" in html,
       "el párrafo de la sección lo explica en una línea")

    print("\n=== 4. El PDF: ¿WeasyPrint honra el gradiente? ===")
    # **Solo la sección del mapa.** Si va el informe entero, la píldora
    # «En ejecución» de la sección 6 usa el MISMO `#bfdbfe` (H-D103) y la cuenta
    # de píxeles deja de decir nada sobre el mapa. Aislar la sección es más
    # barato y más honesto que recortar la imagen a ojo.
    pdf = cli.get(f"{API}/time/informe/pdf", params={**PERIODO, "seccion": "mapa"})
    ok(pdf.status_code == 200 and pdf.content[:4] == b"%PDF",
       f"el PDF se genera ({len(pdf.content)} bytes)")
    open("/tmp/h84.pdf", "wb").write(pdf.content)
    # **Primero se borran los PNG de la corrida anterior.** `pdf_a_png.py`
    # escribe `_p1.._pN` y no borra nada: si una corrida anterior dejó un `_p4`,
    # el barrido de abajo lo cuenta como si fuera de este documento. Pasó.
    for viejo in glob.glob("/tmp/h84_p*.png"):
        os.remove(viejo)
    subprocess.run([sys.executable, "/app/pruebas_e2e/diseno/pdf_a_png.py",
                    "/tmp/h84.pdf", "/tmp/h84", "--escala=3"],
                   capture_output=True, text=True)

    # **Se cuenta DENTRO de la fila del mapa, no en la página entera.** La
    # leyenda lleva su propia muestra azul de 3,5 mm, y contando toda la hoja la
    # prueba pasaba con el gradiente roto: el azul que veía era el de la
    # leyenda. Es el mismo error que la Etapa 6 ya cometió una vez —una
    # comprobación que pasa sin mirar lo que dice mirar—.
    from PIL import Image

    def bandas_con_color(ruta):
        """Las franjas horizontales que llevan verde o azul, de arriba abajo."""
        im = Image.open(ruta).convert("RGB")
        ancho, alto = im.size
        por_fila = {}
        for y in range(alto):
            v = a = 0
            # Todos los píxeles, no uno de cada dos: la proporción que se
            # comprueba abajo tiene que ser la de verdad.
            for x in range(ancho):
                px = im.getpixel((x, y))
                if cerca(px, VERDE):
                    v += 1
                elif cerca(px, AZUL):
                    a += 1
            if v or a:
                por_fila[y] = (v, a)
        if not por_fila:
            return []
        ys = sorted(por_fila)
        grupos, ini, prev = [], ys[0], ys[0]
        for y in ys[1:]:
            if y - prev > 3:
                grupos.append((ini, prev))
                ini = y
            prev = y
        grupos.append((ini, prev))
        return [(a, b,
                 sum(por_fila[y][0] for y in range(a, b + 1) if y in por_fila),
                 sum(por_fila[y][1] for y in range(a, b + 1) if y in por_fila))
                for a, b in grupos]

    todas = []
    for ruta in sorted(glob.glob("/tmp/h84_p*.png")):
        todas += bandas_con_color(ruta)
    if not ok(todas, "hay color en el PDF"):
        return 1
    for y0, y1, v, a in todas:
        print(f"    banda y={y0}..{y1}: verde {v} · azul {a}")

    # La fila del mapa es una banda ALTA —una casilla mide unos 65 px a escala
    # 3—; la leyenda es una tira de 3,5 mm, menos de 40. Filtrar por altura evita
    # confundirlas, que es lo que hacía que esta prueba mirase la muestra de la
    # leyenda en vez de la casilla.
    altas = [b for b in todas if b[1] - b[0] > 40]
    if not ok(altas, "se distingue la fila del mapa de la leyenda"):
        return 1
    fila_mapa = max(altas, key=lambda b: b[2])
    verdes, azules = fila_mapa[2], fila_mapa[3]
    ok(verdes > 0, "la fila del mapa tiene verde: las horas ordinarias")
    ok(azules > 0,
       f"**y azul DENTRO de la fila ({azules} px): WeasyPrint honra el "
       "gradiente**. Si lo ignorara, la casilla saldría entera del color de su "
       "clase y aquí habría un cero")
    # Dos casillas de día trabajado, una de ellas partida al 81 %: el azul es
    # 0,19 de casilla contra 1,81 de verde, o sea alrededor del 10 %.
    if azules:
        proporcion = azules / verdes * 100
        ok(4 <= proporcion <= 20,
           f"y en la proporción que toca: el azul es el {proporcion:.1f} % del "
           "verde (se espera ~10 %: 0,19 casillas contra 1,81)")

    print()
    if fallos:
        print(f"=== {len(fallos)} FALLO(S) ===")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("=== TODO PASA ===")
    return 0


if __name__ == "__main__":
    codigo = 1
    try:
        codigo = main()
    finally:
        limpiar()
    sys.exit(codigo)
