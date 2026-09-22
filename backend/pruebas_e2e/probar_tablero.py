"""ETAPA O2a.4 — los paneles del tablero devuelven datos, no «deberian».

Saca la consulta de CADA panel del JSON provisionado, le pone la corrida de
verdad en lugar de la variable, y la lanza contra InfluxDB. Un panel que no
devuelve ni una fila es un panel vacio en pantalla, y eso no se ve leyendo el
JSON: se ve preguntando.
"""
import json
import os
import sys
import urllib.request

CORRIDA = os.environ["KX_CORRIDA"]
TABLERO = "/g/dashboards/infraestructura.json"
INFLUX = "http://influxdb:8086"
TOKEN = os.environ.get("KX_INFLUX_TOKEN", "jmeter-token-2024-super-secret")

# Lo que Grafana sustituye antes de mandar la consulta.
SUSTITUCIONES = [
    ("v.timeRangeStart", "-40m"),
    ("v.timeRangeStop", "now()"),
    ("v.windowPeriod", "30s"),
    ("${corrida}", CORRIDA),
    ("${modo}", os.environ.get("KX_MODO", "sin_agente")),
]


def consultar(flux):
    peticion = urllib.request.Request(
        INFLUX + "/api/v2/query?org=performance", data=flux.encode("utf-8"),
        headers={"Authorization": "Token " + TOKEN,
                 "Content-Type": "application/vnd.flux",
                 "Accept": "application/csv"})
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        texto = respuesta.read().decode("utf-8")
    return [l for l in texto.splitlines()
            if l.strip() and not l.startswith("#") and not l.startswith(",result")]


def main():
    tablero = json.load(open(TABLERO))
    fallos = []
    paneles = [p for p in tablero["panels"] if p["type"] != "row"]
    print("paneles (sin contar las filas de titulo): %d\n" % len(paneles))

    for panel in paneles:
        for objetivo in panel.get("targets", []):
            flux = objetivo["query"]
            for viejo, nuevo in SUSTITUCIONES:
                flux = flux.replace(viejo, nuevo)
            try:
                filas = consultar(flux)
            except Exception as exc:
                print("FALLA | %-52s %s" % (panel["title"][:52], str(exc)[:60]))
                fallos.append(panel["title"])
                continue
            marca = "PASA " if filas else "FALLA"
            if not filas:
                fallos.append(panel["title"] + " / " + objetivo["refId"])
            print("%s | %-52s %s: %d filas"
                  % (marca, panel["title"][:52], objetivo["refId"], len(filas)))

    # Y las variables. Solo las de tipo «query» llevan Flux dentro: la de modo
    # es una lista fija, y lanzarla contra InfluxDB devuelve un 400.
    for variable in tablero["templating"]["list"]:
        if variable.get("type") != "query":
            print("\nPASA  | la variable «%s» es una lista fija: %s"
                  % (variable["label"], variable["query"]))
            continue
        valores = consultar(variable["query"])
        hay = any(CORRIDA in v for v in valores)
        print("\n%s | la variable «%s» ofrece esta corrida (%d valores)"
              % ("PASA " if hay else "FALLA", variable["label"], len(valores)))
        if not hay:
            fallos.append("variable " + variable["label"])

    print()
    if fallos:
        print("PANELES SIN DATOS: %d" % len(fallos))
        for texto in fallos:
            print("  - " + texto)
        sys.exit(1)
    print("O2a.4 — LOS %d PANELES DEVUELVEN DATOS: TODO PASA" % len(paneles))


if __name__ == "__main__":
    main()
