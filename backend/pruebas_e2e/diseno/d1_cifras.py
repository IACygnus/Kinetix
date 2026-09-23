#!/usr/bin/env python3
"""ETAPA D1.5 — **ninguna cifra cambió** (D-D8). 0 llamadas a la IA.

El rediseño solo podía tocar la presentación. Esto lo comprueba número a
número, no a ojo: genera el informe con el generador **de antes** —el de
`f5bf053`, copiado a `/tmp/antes/informe_antes.py`— y con el de ahora, **con los
mismos datos**, y compara.

La comparación es por tabla: de cada una se saca la lista ordenada de números
que contiene y se enfrentan las dos. Así aguanta que una tabla haya cambiado de
forma —la del reparto pasó de cuatro columnas a tres, y los indicadores de dos
filas a otra maqueta— pero **no aguanta que un número cambie, desaparezca o se
mueva de sitio**.

Lo que el rediseño SÍ añadió —los párrafos de sección, el pie de cada indicador
y las gráficas— se quita antes de comparar: son texto nuevo que repite cifras
que ya estaban, no cifras nuevas. Cada una de ellas se comprueba aparte, contra
el dato del que sale.

    docker exec jmeter_backend python /app/pruebas_e2e/diseno/d1_cifras.py
"""
import json
import os
import re
import sys

import httpx
import lxml.html

sys.path.insert(0, "/app")
# El generador de ANTES no se congela en el repositorio: son 781 líneas que solo
# sirven para esta comparación, y a partir del commit de D1 el «antes» está en
# git. Se saca así, desde el anfitrión, antes de correr esto:
#
#   git show f5bf053:backend/app/services/horas/informe.py > informe_antes.py
#   docker cp informe_antes.py jmeter_backend:/tmp/antes/informe_antes.py
#
ANTES = os.environ.get("KX_INFORME_ANTES", "/tmp/antes")
sys.path.insert(0, ANTES)

API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
fallos = []

# `8.600,5` · `81,5` · `57` · `-6,5`
NUMERO = re.compile(r"-?\d{1,3}(?:\.\d{3})*(?:,\d+)?")
# Lo que el rediseño AÑADIÓ y no es una cifra del informe: los párrafos de
# sección, el pie de cada indicador y las gráficas. Repiten cifras que ya
# estaban; cada una se comprueba aparte contra el dato del que sale.
NUEVO = ('.//p[@class="sec-intro"]', './/span[@class="ind-pie"]',
         './/div[@class="grafica"]')
# Lo que el rediseño QUITÓ y tampoco era una cifra del informe: el cuadro
# numerado del título llevaba el ordinal de la sección —1 a 8—, que es un número
# pero no es un dato. Sin sacarlo, la comparación lo acusaría como cifra perdida.
VIEJO = ('.//span[@class="numsec"]',)


def ok(c, t):
    print(f"{'PASA ' if c else 'FALLA'} | {t}")
    if not c:
        fallos.append(t)
    return c


def numeros(texto: str):
    return NUMERO.findall(texto or "")


def tablas(documento: str):
    """Por cada tabla del documento, la lista ordenada de sus números."""
    raiz = lxml.html.fromstring(documento)
    for selector in NUEVO:
        for el in raiz.xpath(selector):
            el.getparent().remove(el)
    salida = []
    for t in raiz.xpath("//table"):
        nums = []
        for celda in t.xpath(".//td|.//th"):
            nums.extend(numeros(celda.text_content()))
        salida.append(nums)
    return salida


def main() -> None:
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, timeout=180)
    par = {"desde": os.environ.get("KX_DESDE", "2026-09-01"),
           "hasta": os.environ.get("KX_HASTA", "2026-09-30")}
    d = cli.get(f"{API}/time/informe", params=par).json()

    from app.schemas.time_tracking import InformeDatos
    from app.services.horas import informe as ahora
    try:
        import informe_antes as antes
    except ImportError:
        print(f"No esta el generador de antes en {ANTES}/informe_antes.py.\n"
              "Se saca con `git show f5bf053:backend/app/services/horas/informe.py`;\n"
              "mira la cabecera de este archivo.")
        sys.exit(2)

    datos = InformeDatos(**d)
    print(f"periodo {par['desde']} .. {par['hasta']} · "
          f"{d['resumen']['entries_count']} registros · "
          f"{len(d['personas'])} persona(s) · {len(d['detalle'])} filas de detalle\n")

    viejo = tablas(antes.documento_html(datos))
    nuevo = tablas(ahora.documento_html(datos))

    print("=== 1. Tabla por tabla ===")
    ok(len(viejo) == len(nuevo),
       f"el documento tiene las mismas tablas ({len(viejo)} antes, {len(nuevo)} ahora)")
    total = iguales = 0
    for i, (a, b) in enumerate(zip(viejo, nuevo)):
        total += len(a)
        if a == b:
            iguales += len(a)
            print(f"PASA  | tabla {i + 1}: {len(a)} cifras, todas iguales")
            continue
        fallos.append(f"tabla {i + 1}")
        print(f"FALLA | tabla {i + 1}: {len(a)} cifras antes, {len(b)} ahora")
        for j, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print(f"        primera diferencia en la posicion {j}: "
                      f"antes «{x}», ahora «{y}»")
                break
        else:
            print(f"        sobran o faltan cifras al final: "
                  f"antes {a[len(b):]!r}, ahora {b[len(a):]!r}")
    print(f"\n    {iguales} de {total} cifras comparadas, una a una")

    print("\n=== 2. El documento entero, como conjunto ===")

    def todas(doc, quitar):
        raiz = lxml.html.fromstring(doc)
        for selector in quitar:
            for el in raiz.xpath(selector):
                el.getparent().remove(el)
        cuerpo = raiz.xpath("//body")[0]
        for el in cuerpo.xpath(".//script|.//style"):
            el.getparent().remove(el)
        # Con un espacio entre trozo y trozo: `text_content()` pega el texto de
        # celdas contiguas, y un «8» seguido de un «3» se leía como «83».
        return sorted(numeros(" ".join(cuerpo.itertext())))

    ta = todas(antes.documento_html(datos), NUEVO + VIEJO)
    tn = todas(ahora.documento_html(datos), NUEVO + VIEJO)
    ok(ta == tn, f"el mismo conjunto de cifras en todo el documento "
                 f"({len(ta)} antes, {len(tn)} ahora)")
    if ta != tn:
        from collections import Counter
        ca, cn = Counter(ta), Counter(tn)
        print(f"        solo antes: {sorted((ca - cn).elements())[:20]}")
        print(f"        solo ahora: {sorted((cn - ca).elements())[:20]}")

    print("\n=== 3. Lo que el rediseño añadió sale del dato, no de la nada ===")
    r, cap = datos.resumen, datos.capacidad
    h = ahora.horas
    doc = ahora.documento_html(datos)
    for texto, de_donde in (
            (f"en {ahora.num(r.entries_count, 0)} registros", "resumen.entries_count"),
            (f"sobre una jornada de {h(r.expected_hours)}", "resumen.expected_hours"),
            (f"de {ahora.num(r.total_hours)}", "resumen.total_hours (la grafica)"),
            (f"{h(cap.hours_per_analyst)} por analista", "capacidad.hours_per_analyst"),
            (f"Los {ahora.num(d['detalle_total'], 0)} registros", "detalle_total")):
        ok(texto in doc, f"«{texto}» sale de {de_donde}")

    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S) — HAY CIFRAS QUE CAMBIARON. PARADA (D-D8):")
        for f in fallos:
            print("  -", f)
    else:
        print("D1.5 — NINGUNA CIFRA CAMBIO")
    print("=" * 70)
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
