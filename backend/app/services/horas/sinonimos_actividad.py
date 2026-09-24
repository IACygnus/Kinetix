"""Qué texto del Excel corresponde a cuál de las ocho actividades del catálogo.

**Definición única.** Las dos importaciones —la de registros y la de proyectos—
preguntan aquí. No se copia la tabla en ninguna de las dos: es el mismo error
que la plantilla paralela del informe por transacción, que acabó divergiendo.

Por qué existe: los tres archivos de septiembre de 2026 traen la misma actividad
escrita de seis maneras —«Diseño y generación de script», «Diseño y
configuración», «Generación de scripts», «Variabilización», «Smoke test»,
«Configuración»— y todas son **Diseño de script**. Sin esta tabla, la
importación creaba una actividad por variante y el catálogo se llenaba de
duplicados que ya no se podían sumar.

Tres reglas, y las tres importan:

1. **Solo en las importaciones.** El registro a mano no pasa por aquí: ahí la
   persona elige del catálogo y escribe lo que quiera. Traducirle lo que teclea
   sería corregirle sin avisar.
2. **Lo que no esté en la tabla se crea igual.** Esto no es un filtro: una
   actividad desconocida entra, con su nombre tal cual viene. Lo que cambia es
   que la vista previa la **avisa en un bloque propio**, con sus filas y sus
   horas, para que se decida antes de confirmar si faltaba un sinónimo.
3. **Se compara normalizado** con `normalizar()` de H1 —sin tildes, sin
   mayúsculas, sin espacios de más—, la misma función que evita duplicar un
   cliente por una tilde. Por eso «gestion de proyectos» ya casa con «Gestión de
   proyectos» sin necesidad de aparecer en la lista.

Ampliarla es añadir una línea. Es lo que hay que hacer cuando una previa avise
de una actividad nueva que debería haberse reconocido.
"""
from typing import Dict, List, Optional

from app.db.models.time_tracking import normalizar

# ===================== LAS OCHO =====================

# El catálogo, en el orden en que se trabaja un proyecto. Es el mismo que
# siembra `db/seed_time_tracking.py`: si aquí se añade una, allí también.
CANONICAS: List[str] = [
    "Etapa de conocimiento",
    "Planeación",
    "Diseño de script",
    "Ejecución",
    "Análisis de resultados",
    "Gestión de proyectos",
    "Preventa",
    "Investigación",
]

# ===================== LA TABLA =====================

# Canónica -> cómo puede venir escrita en un archivo. El nombre canónico NO hace
# falta repetirlo aquí: se añade solo más abajo.
SINONIMOS: Dict[str, List[str]] = {
    "Etapa de conocimiento": [
        "Etapa conocimiento",
        "Contextualización conocimiento proyecto",
        "Levantamiento de información",
        "Lectura de documentación",
    ],
    "Planeación": [
        "Etapa planeacion",
        "Etapa de planeación",
        "Plan de pruebas",
    ],
    "Diseño de script": [
        "Etapa diseño",
        "Diseño y configuración",
        "Diseño y generación de script",
        "Diseño de scripts",
        "Configuración",
        "Generación de scripts",
        "Variabilización",
        "Smoke test",
    ],
    "Ejecución": [
        "Etapa ejecución",
        "Ejecución de scripts",
    ],
    "Análisis de resultados": [
        "Etapa análisis",
        "Análisis",
        "Análisis de logs",
        "Informes y resultados",
    ],
    "Gestión de proyectos": [
        "Actividades administrativas",
        "Actividades administrativas y transversales",
        "Administrativas o gerenciales",
        "Reuniones de seguimiento",
        "Alineación y seguimiento",
    ],
    "Preventa": [],
    "Investigación": [],
}

# ===================== EL ÍNDICE =====================


def _construir() -> Dict[str, str]:
    """`{nombre normalizado: canónica}`, con las canónicas incluidas.

    Se construye una vez al importar el módulo. Si dos canónicas se disputaran
    el mismo sinónimo, el error salta aquí —al arrancar el backend— y no en
    mitad de una importación, donde nadie sabría de dónde viene.
    """
    indice: Dict[str, str] = {}
    for canonica in CANONICAS:
        if canonica not in SINONIMOS:
            raise ValueError(f"«{canonica}» está en CANONICAS y no en SINONIMOS")
        for texto in [canonica] + SINONIMOS[canonica]:
            clave = normalizar(texto)
            duenio = indice.get(clave)
            if duenio and duenio != canonica:
                raise ValueError(
                    f"«{texto}» está asociado a «{duenio}» y a «{canonica}»")
            indice[clave] = canonica
    sobran = set(SINONIMOS) - set(CANONICAS)
    if sobran:
        raise ValueError(f"SINONIMOS tiene claves que no son canónicas: {sorted(sobran)}")
    return indice


INDICE: Dict[str, str] = _construir()


def canonica(texto: Optional[str]) -> Optional[str]:
    """La actividad del catálogo a la que corresponde `texto`, o `None`.

    `None` significa «no la conozco», no «es inválida»: la importación la crea
    igual y la vista previa la avisa (regla 2 de la cabecera).
    """
    if not texto:
        return None
    return INDICE.get(normalizar(texto))


def traducir(texto: Optional[str]) -> str:
    """El nombre con el que la importación debe trabajar esa actividad.

    Si la tabla la conoce, la canónica; si no, el texto tal como vino —limpio de
    espacios, nada más—. Es la única función que llaman los dos importadores.
    """
    conocida = canonica(texto)
    if conocida:
        return conocida
    return (texto or "").strip()
