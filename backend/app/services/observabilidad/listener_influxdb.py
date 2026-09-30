"""El Backend Listener de InfluxDB, de UN solo sitio — ETAPA S2.2.

**Por qué existe.** Hasta S2.2 había tres listas de argumentos copiadas: la del
diseñador en el navegador (`AIScriptEditor.tsx`), la del aplicador de la IA
(`refine_operations_applier.py`) y la de Observabilidad. Las dos primeras
metían el token MAESTRO de InfluxDB en un argumento llamado `TOKEN`, que
JMeter 5.6.3 no lee: el `.jmx` entregado filtraba el maestro y, encima, no
mandaba ni una métrica (reporte 132).

Aquí se decide, una vez, cómo es el listener:

- **URL**: `${__P(influxdbUrl,<la de /monitoring/jmeter-config>)}`. La
  propiedad deja que quien lo ejecute dentro de Docker la cambie con `-J`.
- **Token**: `influxdbToken` —el nombre que JMeter lee— con el token de
  ESCRITURA del cubo `jmeter` de `monitoring_config`. Nunca vacío: sin token
  no hay listener, hay un error que lo dice.
- **application**: la regla de Observabilidad (`nombre_de_corrida`, O-D4),
  también como propiedad: `${__P(application,<ese nombre>)}`.

Los valores por defecto de `__P` van saneados: una coma, un paréntesis o un
espacio parten la función y JMeter se queda con un trozo.

**El buzón.** El aplicador de la IA es síncrono y no ve la base. El endpoint
resuelve los datos (asíncrono) y los deja en `BUZON`, una `ContextVar` —el
mismo patrón que `gemini.BUZON_FALLO`—; el aplicador solo pide el listener. Si
lo pide con el buzón vacío, el módulo no se inventa nada: lanza
`ListenerSinDatos`.
"""
import re
import uuid
import xml.etree.ElementTree as ET
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.client import Client
from app.db.models.monitoring import MonitoringConfig

CLASE_LISTENER = (
    "org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient")
CLASE_EMISOR = (
    "org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender")

NOMBRE = "InfluxDB de Kinetix"


class ListenerSinDatos(ValueError):
    """No se puede construir un listener que funcione: falta el token o los datos."""


@dataclass(frozen=True)
class DatosListener:
    """Lo que cambia de un listener a otro. Todo lo demás es fijo."""
    url: str
    token: str
    application: str


BUZON: ContextVar[Optional[DatosListener]] = ContextVar(
    "listener_influxdb_buzon", default=None)


def sanear_para_p(valor: str) -> str:
    """Lo que va dentro de `${__P(nombre,valor)}` no puede partir la función."""
    return re.sub(r"[,(){}$\\\s]", "", valor or "")


def url_de_escritura(influxdb_url: Optional[str], org: Optional[str],
                     cubo: Optional[str]) -> str:
    """La URL de escritura que da `/monitoring/jmeter-config`, para un JMeter de fuera.

    Los nombres de servicio de Docker no los resuelve nadie de fuera: el mismo
    cambio que hace `_url_para_el_navegador` en `monitoring.py`.
    """
    base = (influxdb_url or "").replace("influxdb:8086", "localhost:8086").rstrip("/")
    base = base or "http://localhost:8086"
    return f"{base}/api/v2/write?org={org or 'performance'}&bucket={cubo or 'jmeter'}"


def argumentos(datos: DatosListener) -> Dict[str, str]:
    """Los argumentos del `InfluxdbBackendListenerClient`, en el orden de siempre."""
    if not (datos.token or "").strip():
        raise ListenerSinDatos(
            "No hay token de escritura de InfluxDB en la configuración de "
            "monitoreo, y sin él JMeter no puede mandar sus métricas. Pídele a "
            "un administrador que lo cargue en Monitoreo → Configuración.")
    url = f"${{__P(influxdbUrl,{sanear_para_p(datos.url)})}}"
    application = f"${{__P(application,{sanear_para_p(datos.application)})}}"
    return {
        "influxdbMetricsSender": CLASE_EMISOR,
        "influxdbUrl": url,
        "influxdbToken": datos.token,
        "application": application,
        "measurement": "jmeter",
        # En «false» para ver transacción por transacción, no solo el total.
        "summaryOnly": "false",
        "samplersRegex": ".*",
        "percentiles": "90;95;99",
        "testTitle": application,
        "eventTags": "",
    }


def construir(datos: DatosListener, nombre: str = NOMBRE) -> ET.Element:
    """El `<BackendListener>` entero. Su `<hashTree/>` lo pone quien lo cuelga."""
    valores = argumentos(datos)
    listener = ET.Element("BackendListener", {
        "guiclass": "BackendListenerGui", "testclass": "BackendListener",
        "testname": nombre or NOMBRE, "enabled": "true",
    })
    elemento = ET.SubElement(listener, "elementProp", {
        "name": "arguments", "elementType": "Arguments",
        "guiclass": "ArgumentsPanel", "testclass": "Arguments",
        "testname": "args", "enabled": "true",
    })
    coleccion = ET.SubElement(elemento, "collectionProp",
                              {"name": "Arguments.arguments"})
    for clave, valor in valores.items():
        argumento = ET.SubElement(coleccion, "elementProp",
                                  {"name": clave, "elementType": "Argument"})
        ET.SubElement(argumento, "stringProp",
                      {"name": "Argument.name"}).text = clave
        ET.SubElement(argumento, "stringProp",
                      {"name": "Argument.value"}).text = valor
        ET.SubElement(argumento, "stringProp",
                      {"name": "Argument.metadata"}).text = "="
    ET.SubElement(listener, "stringProp",
                  {"name": "classname"}).text = CLASE_LISTENER
    return listener


def xml_del_listener(datos: DatosListener, nombre: str = NOMBRE) -> str:
    """El listener como texto, sin su `hashTree` (el regenerador lo añade)."""
    elemento = construir(datos, nombre)
    ET.indent(elemento)
    return ET.tostring(elemento, encoding="unicode")


def fragmento(datos: DatosListener) -> str:
    """Listener + `hashTree`, listo para pegar dentro de un Thread Group."""
    return "\n".join([
        "<!-- Backend Listener generado por Kinetix Pro -->",
        f"<!-- Corrida: {sanear_para_p(datos.application)} -->",
        xml_del_listener(datos),
        "<hashTree/>",
        "",
    ])


def listener_del_buzon(nombre: str = NOMBRE) -> str:
    """Lo que pide el aplicador de la IA. Sin datos en el buzón, error: no se inventa."""
    datos = BUZON.get()
    if datos is None:
        raise ListenerSinDatos(
            "Se pidió un Backend Listener sin los datos de escritura de "
            "InfluxDB (el buzón está vacío). Es un fallo de Kinetix, no del "
            "script: quien aplica la operación tiene que resolverlos antes.")
    return xml_del_listener(datos, nombre)


async def resolver(db: AsyncSession, client_id: Optional[uuid.UUID],
                   proyecto: Optional[str], plan: str = "") -> DatosListener:
    """Los datos de escritura de una corrida, desde `monitoring_config`.

    Sin cliente no se niega nada (S2.2): se aplica la regla de Observabilidad,
    que ya convierte en `sin-nombre` la parte que falta, y el proyecto que no
    llega se toma del nombre del Test Plan.

    El token NO se valida aquí: un token vacío o que no se descifra sale como
    cadena vacía, y es `argumentos()` quien se niega a construir con él. Así el
    error es el mismo venga de donde venga.
    """
    # Aquí dentro para no importar un endpoint al cargar el módulo: monitoring.py
    # importa este módulo, y al revés sería un ciclo.
    from app.api.v1.endpoints.monitoring import _decrypt_token, nombre_de_corrida

    config = (await db.execute(
        select(MonitoringConfig).limit(1))).scalar_one_or_none()
    cliente = ""
    if client_id:
        cliente = (await db.execute(
            select(Client.name).where(Client.id == client_id))).scalar_one_or_none() or ""

    token = ""
    if config is not None and config.influxdb_token_encrypted:
        try:
            token = _decrypt_token(config.influxdb_token_encrypted)
        except Exception:
            token = ""

    return DatosListener(
        url=url_de_escritura(
            config.influxdb_url if config else None,
            config.influxdb_org if config else None,
            config.influxdb_bucket if config else None),
        token=token,
        application=nombre_de_corrida(cliente, (proyecto or "").strip() or plan),
    )
