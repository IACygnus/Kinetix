"""Ponerle el Backend Listener a un plan de JMeter — ETAPA O2d (O-D45, O-D46).

**Por qué existe.** JMeter no manda sus métricas a ningún sitio por su cuenta.
Hasta O2c, la pantalla daba diez parámetros y alguien tenía que copiarlos uno a
uno dentro de JMeter. Eso es lo que Fredy no entendió, y con razón: no es trabajo
de una persona.

Aquí se le inserta al `.jmx` el componente ya configurado, con los valores de la
sesión, y se devuelve **una copia**. El archivo original no se toca (O-D46).

Módulo nuevo: no toca `services/jmx_parser.py` —que solo lee— ni nada protegido.
"""
import io
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

CLASE_LISTENER = (
    "org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient")
CLASE_EMISOR = (
    "org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender")

NOMBRE = "InfluxDB de Kinetix"


class JmxInvalido(ValueError):
    """El archivo no es un plan de prueba de JMeter que podamos tocar."""


def _argumentos(valores: Dict[str, str]) -> ET.Element:
    """La colección de argumentos del Backend Listener, en el orden de siempre."""
    elemento = ET.Element("elementProp", {
        "name": "arguments", "elementType": "Arguments",
        "guiclass": "ArgumentsPanel", "testclass": "Arguments",
        "testname": "args", "enabled": "true",
    })
    coleccion = ET.SubElement(elemento, "collectionProp",
                              {"name": "Arguments.arguments"})
    for nombre, valor in valores.items():
        argumento = ET.SubElement(coleccion, "elementProp",
                                  {"name": nombre, "elementType": "Argument"})
        ET.SubElement(argumento, "stringProp",
                      {"name": "Argument.name"}).text = nombre
        ET.SubElement(argumento, "stringProp",
                      {"name": "Argument.value"}).text = valor
    return elemento


def construir_listener(url: str, token: str, corrida: str) -> ET.Element:
    """El componente entero, listo para colgar del árbol."""
    listener = ET.Element("BackendListener", {
        "guiclass": "BackendListenerGui", "testclass": "BackendListener",
        "testname": NOMBRE, "enabled": "true",
    })
    listener.append(_argumentos({
        "influxdbMetricsSender": CLASE_EMISOR,
        "influxdbUrl": url,
        "influxdbToken": token,
        "application": corrida,
        "measurement": "jmeter",
        # En «false» para ver transacción por transacción, no solo el total.
        "summaryOnly": "false",
        "samplersRegex": ".*",
        "percentiles": "90;95;99",
        "testTitle": corrida,
        "eventTags": "",
    }))
    ET.SubElement(listener, "stringProp",
                  {"name": "classname"}).text = CLASE_LISTENER
    return listener


def _padre_de(raiz: ET.Element, hijo: ET.Element) -> Optional[ET.Element]:
    for candidato in raiz.iter():
        for actual in list(candidato):
            if actual is hijo:
                return candidato
    return None


def insertar(contenido: bytes, url: str, token: str, corrida: str
             ) -> Tuple[bytes, Dict[str, object]]:
    """Devuelve (el jmx nuevo, qué se hizo).

    El informe que devuelve es lo que la pantalla le enseña a quien sube el
    archivo: si se añadió o se reemplazó, y dónde.
    """
    try:
        raiz = ET.fromstring(contenido)
    except ET.ParseError as exc:
        raise JmxInvalido(
            f"El archivo no es XML válido: {exc}. ¿Seguro que es un .jmx?")

    if raiz.tag != "jmeterTestPlan":
        raise JmxInvalido(
            f"El XML no es un plan de prueba de JMeter (la raíz es "
            f"«{raiz.tag}», debería ser «jmeterTestPlan»).")

    if raiz.find(".//TestPlan") is None:
        raise JmxInvalido(
            "El archivo no contiene ningún Test Plan. Puede estar incompleto.")

    # Dónde colgarlo: dentro del primer Thread Group, que es donde JMeter espera
    # encontrarlo para que recoja sus muestras.
    hashtree_raiz = raiz.find("hashTree")
    if hashtree_raiz is None:
        raise JmxInvalido("El plan no tiene la estructura que JMeter espera.")

    grupo = raiz.find(".//ThreadGroup")
    if grupo is None:
        # Sin Thread Group el plan no corre, pero se deja insertar: quien lo
        # suba sabra si le falta algo, y es mejor que rechazarlo sin mas.
        destino = hashtree_raiz
        donde = "al final del plan (no se encontró ningún Thread Group)"
    else:
        padre = _padre_de(raiz, grupo)
        hermanos = list(padre) if padre is not None else []
        posicion = hermanos.index(grupo) if grupo in hermanos else -1
        # En un .jmx, cada elemento va seguido de SU hashTree: ahi dentro es
        # donde viven los samplers del grupo, y donde tiene que ir el listener.
        destino = (hermanos[posicion + 1]
                   if 0 <= posicion + 1 < len(hermanos)
                   and hermanos[posicion + 1].tag == "hashTree"
                   else hashtree_raiz)
        nombre_grupo = grupo.get("testname", "sin nombre")
        donde = f"dentro del grupo de hilos «{nombre_grupo}»"

    # ¿Ya traía uno? Se REEMPLAZA su configuración, no se duplica (O-D46): dos
    # Backend Listeners mandando a sitios distintos es peor que ninguno.
    existentes = raiz.findall(".//BackendListener")
    reemplazados = []
    for viejo in existentes:
        clase = viejo.find("stringProp[@name='classname']")
        etiqueta = viejo.get("testname", "sin nombre")
        reemplazados.append(etiqueta)
        padre_viejo = _padre_de(raiz, viejo)
        if padre_viejo is not None:
            indice = list(padre_viejo).index(viejo)
            padre_viejo.remove(viejo)
            # Cada elemento va seguido de su hashTree; si se quita uno hay que
            # quitar el suyo, o el archivo queda descuadrado y JMeter no lo abre.
            if indice < len(list(padre_viejo)) and list(padre_viejo)[indice].tag == "hashTree":
                padre_viejo.remove(list(padre_viejo)[indice])
        logger.info("Reemplazado un Backend Listener existente: %s (%s)",
                    etiqueta, clase.text if clase is not None else "sin clase")

    destino.append(construir_listener(url, token, corrida))
    destino.append(ET.Element("hashTree"))

    salida = io.BytesIO()
    ET.ElementTree(raiz).write(salida, encoding="UTF-8", xml_declaration=True)

    informe = {
        "reemplazado": bool(reemplazados),
        "reemplazados": reemplazados,
        "donde": donde,
        "corrida": corrida,
    }
    return salida.getvalue(), informe


def mensaje(informe: Dict[str, object]) -> str:
    """Lo que se le dice a quien acaba de subir el archivo."""
    if informe.get("reemplazado"):
        cuales = ", ".join(f"«{n}»" for n in informe.get("reemplazados") or [])
        return (
            f"Listo, pero ojo: el archivo YA traía un Backend Listener ({cuales}) "
            f"y se ha reemplazado por el de esta sesión — dos a la vez mandando "
            f"a sitios distintos daría métricas partidas. Se puso {informe['donde']}. "
            f"El archivo original no se ha tocado: esto es una copia.")
    return (
        f"Listo. Se le insertó el Backend Listener con los valores de esta "
        f"sesión, {informe['donde']}. El archivo original no se ha tocado: "
        f"esto es una copia.")
