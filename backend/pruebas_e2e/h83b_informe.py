"""ETAPA H8.3b — en el informe queda UNA sola columna de estado, la última.

    docker exec jmeter_backend python3 /tmp/e2e/h83b_datos_informe.py crear
    docker exec jmeter_backend python3 /tmp/e2e/h83b_informe.py
    docker exec jmeter_backend python3 /tmp/e2e/h83b_datos_informe.py limpiar

H-D102 retira la columna «Consumo» de la sección 6 y mueve «Estado» al final,
con color (H-D103). **En las pantallas no cambia nada** (H-D105), y eso también
se comprueba aquí: es lo fácil de romper sin darse cuenta.

Los datos los pone `h83b_datos_informe.py` —un proyecto por estado, uno de
ellos desfasado—, porque el rasterizado del PDF y `d1_cifras.py` los necesitan
puestos antes y quitados después. 0 llamadas a la IA.
"""
import json
import os
import re
import subprocess
import sys

import httpx

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
MARCA = "ZZTEST-H83B"
PERIODO = {"desde": "2026-09-01", "hasta": "2026-09-30"}

# H-D103: los cinco tonos, tal como los fija `docs/diseno-informe-horas.md`.
# Si alguien cambia un color en el código sin pasar por el documento, esto falla.
COLORES = {
    "pendiente": ("#f3f4f6", "#4b5563"),
    "en_ejecucion": ("#bfdbfe", "#03287D"),
    "detenido": ("#fef3c7", "#92400e"),
    "no_viable": ("#e5e7eb", "#991b1b"),
    "finalizado": ("#dcfce7", "#166534"),
}
ROTULOS = {"pendiente": "Pendiente", "en_ejecucion": "En ejecución",
           "detenido": "Detenido", "no_viable": "No viable",
           "finalizado": "Finalizado"}

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def main():
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")},
                       timeout=180.0)
    if cli.get(f"{API}/auth/me").status_code != 200:
        sys.exit("sesion caducada: corre refrescar_sesion.py")

    html = cli.get(f"{API}/time/informe/html", params=PERIODO).text

    print("=== 1. La tabla: una sola columna de estado, y la última ===")
    tabla = re.search(r'<table[^>]*>\s*<thead><tr>(.*?)</tr></thead>(.*?)</table>',
                      html[html.index("Consumido frente a estimado"):], re.S)
    if not ok(tabla is not None, "se encuentra la tabla de la sección 6"):
        return 1
    cabeceras = re.findall(r"<th[^>]*>(.*?)</th>", tabla.group(1), re.S)
    cabeceras = [re.sub(r"<[^>]+>", "", c).strip() for c in cabeceras]
    ok(cabeceras == ["Cliente", "Proyecto", "En el periodo", "Estimadas",
                     "Consumidas", "Restantes", "Estado"],
       f"las cabeceras, en orden: {cabeceras}")
    ok(cabeceras.count("Estado") == 1, "«Estado» aparece UNA vez")
    ok("Consumo" not in cabeceras, "y «Consumo» ya no está")
    ok(cabeceras[-1] == "Estado", "«Estado» es la última columna (H-D102)")

    print("\n=== 2. Ningún rótulo de consumo en la tabla ===")
    cuerpo = tabla.group(2)
    for palabra in ("En rango", "Por agotarse", "Desfasado", "Terminado"):
        ok(palabra not in cuerpo, f"no aparece «{palabra}» en la tabla")
    for clase in ('pill bien', 'pill ojo', 'pill mal'):
        ok(f'class="{clase}"' not in cuerpo,
           f"ni la píldora «{clase}», que significa otra cosa en la sección 8")

    print("\n=== 3. Los cinco estados, cada uno con el suyo (H-D103) ===")
    for estado, rotulo in ROTULOS.items():
        fila = re.search(r'<tr[^>]*data-estado="' + estado + r'"[^>]*>(.*?)</tr>',
                         cuerpo, re.S)
        if not ok(fila is not None, f"está la fila del proyecto «{estado}»"):
            continue
        celdas = fila.group(1)
        ok(f'class="pill est-{estado}"' in celdas,
           f"  con su píldora `est-{estado}`")
        ok(rotulo in celdas, f"  y su rótulo «{rotulo}»")
        ok(celdas.count('class="pill') == 1, "  una sola píldora en la fila")
        fondo, tinta = COLORES[estado]
        ok(f".pill.est-{estado}{{background:{fondo};color:{tinta}}}" in html,
           f"  y los colores del documento de diseño ({fondo} / {tinta})")

    print("\n=== 4. El desfase se ve en «Restantes» (H-D106) ===")
    fila = re.search(r'<tr[^>]*data-proyecto="' + MARCA + r'-en-ejecucion"[^>]*>(.*?)</tr>',
                     cuerpo, re.S)
    if ok(fila is not None, "está la fila del proyecto desfasado"):
        ok('<strong class="mal">-4,5 h</strong>' in fila.group(1),
           "«Restantes» sale en negativo y en rojo")
    fila_ok = re.search(r'<tr[^>]*data-proyecto="' + MARCA + r'-detenido"[^>]*>(.*?)</tr>',
                        cuerpo, re.S)
    if ok(fila_ok is not None, "y la de uno que va sobrado"):
        ok('<strong class="mal">' not in fila_ok.group(1),
           "esa NO lleva rojo: 16 h restantes no son un aviso")

    print("\n=== 5. El párrafo de la sección (H-D104) ===")
    ok("lo decide una persona" in html,
       "dice quién decide el estado")
    ok("Restantes en rojo" in html,
       "y explica el rojo de «Restantes» en media línea")
    ok("dos preguntas distintas" not in html,
       "y ya NO habla de dos columnas, que es lo que había que reescribir")

    print("\n=== 6. Las PANTALLAS no cambian (H-D105) ===")
    # Se mira el contrato, que es lo que las pantallas pintan: si el backend
    # dejara de mandar una de las dos, las dos pantallas se quedarían sin
    # columna y esto lo dice antes que el navegador.
    proys = cli.get(f"{API}/time/projects", params={"incluir_finalizados": "true"}).json()
    mio = next((p for p in proys if p["name"] == f"{MARCA}-en-ejecucion"), None)
    if ok(mio is not None, "el listado de Proyectos trae el proyecto de prueba"):
        ok(mio["status"] == "en_ejecucion" and mio["status_label"] == "En ejecución",
           "con su ESTADO")
        ok(mio["overrun_status"] == "desfasado" and mio["overrun_label"].startswith("Desfasado"),
           f"y su CONSUMO, que en pantalla sigue: «{mio['overrun_label']}»")
    consulta = cli.get(f"{API}/time/consulta",
                       params={**PERIODO, "incluir_finalizados": "true"}).json()
    fila_c = next((p for p in consulta["projects"]
                   if p["project_name"] == f"{MARCA}-en-ejecucion"), None)
    if ok(fila_c is not None, "la Consulta también lo trae"):
        ok(bool(fila_c["status_label"]) and bool(fila_c["overrun_label"]),
           f"con las dos: «{fila_c['status_label']}» y «{fila_c['overrun_label']}»")

    print("\n=== 7. El PDF ===")
    pdf = cli.get(f"{API}/time/informe/pdf", params=PERIODO)
    ok(pdf.status_code == 200 and pdf.content[:4] == b"%PDF",
       f"se genera ({pdf.status_code}, {len(pdf.content)} bytes)")
    open("/tmp/h83b.pdf", "wb").write(pdf.content)
    r = subprocess.run([sys.executable, "/app/pruebas_e2e/diseno/pdf_a_png.py",
                        "/tmp/h83b.pdf", "/tmp/h83b", "--escala=2"],
                       capture_output=True, text=True)
    ok(r.returncode == 0, f"y se rasteriza para mirarlo: {r.stdout.strip().splitlines()[-1:]}")
    print("    las capturas quedan en /tmp/h83b_p*.png")

    print()
    if fallos:
        print(f"=== {len(fallos)} FALLO(S) ===")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("=== TODO PASA ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
