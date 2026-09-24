"""La corrida con la que probar el tablero — buscada, no escrita a mano.

    docker exec jmeter_backend python3 /tmp/e2e/corrida_para_tablero.py

Imprime el nombre de una corrida `zztest-` que tenga datos **en los dos cubos**
y calla si no hay ninguna (codigo 1).

POR QUE EXISTE (ETAPA H8.6)
---------------------------
`cierre_o2d.sh` llevaba la corrida escrita en el propio guion:

    export KX_CORRIDA=zztest-o2d-20260922-190026

Dos dias despues, esa corrida seguia en el cubo `infra` pero ya no estaba en
`jmeter`, y el panel «Tiempo de respuesta de la prueba vs CPU del servidor»
devolvia cero filas. La prueba decia «FALLA» y el tablero estaba perfectamente:
lo que fallaba era el dato de prueba, que habia caducado.

Es el mismo problema que los contadores escritos a mano que H8.6 tuvo que
actualizar —«sus 10 proyectos», «sus 24 registros»—, y la misma leccion: un
valor fijo que depende de datos vivos se pudre, y cuando se pudre miente en la
direccion mala, diciendo que algo esta roto cuando no lo esta.

El tablero cruza las dos mitades —la prueba, del cubo `jmeter` con la etiqueta
`application`; el servidor, del cubo `infra` con la etiqueta `corrida`—, asi que
solo sirve una corrida que este en los dos. Eso es lo que se busca aqui.

LA VENTANA ES LA DEL PANEL, Y NO ES UN DETALLE
----------------------------------------------
Los paneles miran **los ultimos 40 minutos** (`v.timeRangeStart = -40m` en
`probar_tablero.py`). Que una corrida aparezca en la lista de etiquetas no
basta: `zztest-o2d-20260922-190026` seguia en las dos listas dos dias despues y
sus datos estaban fuera de la ventana, asi que el panel devolvia cero filas
igual. Por eso se busca con **la misma ventana que el panel** —`schema.tagValues`
solo devuelve las etiquetas que tienen puntos dentro del rango que se le pida—,
y si no hay ninguna se dice que hace falta una pasada del laboratorio, en vez de
dar una que va a fallar.
"""
import os
import sys
import urllib.request

INFLUX = os.environ.get("KX_INFLUX", "http://influxdb:8086")
TOKEN = os.environ.get("KX_INFLUX_TOKEN", "jmeter-token-2024-super-secret")
MARCA = os.environ.get("KX_MARCA", "zztest-")
# La MISMA que miran los paneles en `probar_tablero.py`. Ver la cabecera.
VENTANA = os.environ.get("KX_VENTANA", "-40m")


def etiquetas(cubo: str, etiqueta: str) -> list:
    """Los valores de una etiqueta en un cubo, en el orden que los da InfluxDB."""
    flux = (f'import "influxdata/influxdb/schema"\n'
            f'schema.tagValues(bucket: "{cubo}", tag: "{etiqueta}", '
            f'start: {VENTANA})')
    peticion = urllib.request.Request(
        INFLUX + "/api/v2/query?org=performance", data=flux.encode("utf-8"),
        headers={"Authorization": "Token " + TOKEN,
                 "Content-Type": "application/vnd.flux",
                 "Accept": "application/csv"})
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            texto = respuesta.read().decode("utf-8")
    except Exception as e:                       # InfluxDB caido, cubo que no esta
        print(f"no se pudo consultar {cubo}: {e}", file=sys.stderr)
        return []
    salida = []
    for linea in texto.splitlines():
        partes = linea.split(",")
        if len(partes) > 3 and not linea.startswith("#") and partes[3] != "_value":
            salida.append(partes[3].strip())
    return salida


def main() -> int:
    prueba = {v for v in etiquetas("jmeter", "application") if v.startswith(MARCA)}
    servidor = {v for v in etiquetas("infra", "corrida") if v.startswith(MARCA)}
    comunes = prueba & servidor
    if not comunes:
        print(f"no hay ninguna corrida «{MARCA}» con datos en los DOS cubos "
              f"(jmeter/application y infra/corrida) en los ultimos "
              f"{VENTANA.lstrip('-')}, que es lo que miran los paneles.\n"
              "La genera una pasada del laboratorio, que escribe en los dos:\n"
              "    bash scripts/lab_prueba_correlacion.sh\n"
              "Esto NO es un fallo del tablero: es que no hay datos frescos "
              "que ensenarle.", file=sys.stderr)
        return 1
    # El nombre lleva la fecha y la hora al final (O-D4:
    # <cliente>-<proyecto>-<aaaammdd-hhmm>), asi que ordenar por texto ordena
    # por tiempo. La mas reciente es la que mas probabilidades tiene de seguir
    # dentro de la ventana que mira el tablero.
    print(sorted(comunes)[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
