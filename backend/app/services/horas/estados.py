"""El estado del proyecto (ETAPA H8, §3.1 de la especificación v1.5).

Una sola definición, en un solo sitio, porque **cuatro endpoints preguntan lo
mismo y no pueden responder distinto**: el listado de proyectos, el registro de
horas, la importación y la consulta. Mismo criterio que `calendario.py` —la
jornada— y `desfase.py` —el consumo—.

**El estado lo decide una persona y es independiente del consumo** (H-D80). Son
dos preguntas distintas y tienen dos columnas distintas (§5.1):

    Estado    ¿en qué punto está este trabajo?      lo pone alguien, aquí
    Consumo   ¿cuántas horas lleva de las estimadas? lo calcula `desfase.py`

La tabla de §3.1, que es de donde sale todo lo demás de este módulo:

    Estado         Registrar horas   Cambiar estimaciones
    pendiente            No                 Sí
    en_ejecucion         Sí                 Sí
    detenido             No                 Sí
    no_viable            No                 No
    finalizado           No                 No

Pendiente y detenido son **temporales**: se planifican aunque no se registren
horas en ellos, y por eso admiten cambios de estimación. No viable y finalizado
están cerrados a todo.

**«Cerrado» ya no existe** (H-D81): el antiguo `status='cerrado'` es ahora
`finalizado` y el antiguo `'activo'` es `en_ejecucion`. La migración la hizo
`docs/sql/h8_estado_proyecto.sql`.
"""
from typing import Optional

# Los cinco de H-D80, en el orden en que se enseñan.
PENDIENTE = "pendiente"
EN_EJECUCION = "en_ejecucion"
DETENIDO = "detenido"
NO_VIABLE = "no_viable"
FINALIZADO = "finalizado"

ESTADOS = (PENDIENTE, EN_EJECUCION, DETENIDO, NO_VIABLE, FINALIZADO)

# El estado con el que nace un proyecto (H-D80).
POR_DEFECTO = EN_EJECUCION

TEXTOS = {
    PENDIENTE: "Pendiente",
    EN_EJECUCION: "En ejecución",
    DETENIDO: "Detenido",
    NO_VIABLE: "No viable",
    FINALIZADO: "Finalizado",
}

# --------------------------------------------------------------------------
# Lo que bloquea cada estado. Son conjuntos y no condiciones sueltas para que
# cada endpoint pregunte en vez de repetir la regla: hoy `cerrado` bloqueaba en
# CUATRO sitios distintos, y bastaba con que uno se quedara atrás.
# --------------------------------------------------------------------------

#: Ningún estado admite registros salvo `en_ejecucion` (§3.1).
BLOQUEAN_REGISTRO = frozenset({PENDIENTE, DETENIDO, NO_VIABLE, FINALIZADO})

#: Pendiente y detenido SÍ admiten cambios de estimación: se planifican aunque
#: todavía no se trabaje en ellos.
BLOQUEAN_ESTIMACION = frozenset({NO_VIABLE, FINALIZADO})

#: §6.2.8 — la excepción. Un Excel trae horas de hace semanas y el proyecto pudo
#: cambiar de estado desde entonces; rechazarlas obligaría a reabrir el
#: proyecto, importar y volver a cerrarlo. Solo `no_viable` se rechaza.
BLOQUEAN_IMPORTACION = frozenset({NO_VIABLE})

#: H-D84 — los listados los esconden hasta que se piden.
OCULTOS_POR_DEFECTO = frozenset({NO_VIABLE, FINALIZADO})

#: Los dos que **cierran** el proyecto: esconden y bloquean las estimaciones.
#: Ponerlos es de administrador (§8), como lo era cerrar un proyecto. Los otros
#: tres los cambia cualquiera.
SOLO_ADMIN = frozenset({NO_VIABLE, FINALIZADO})

# --------------------------------------------------------------------------
# Los valores viejos.
#
# ETAPA H8.6: **escribirlos ya no se puede.** `ck_project_status` acepta solo
# los cinco desde `docs/sql/h8_estado_proyecto_cierre.sql`, y los alias de
# H-D91 —`?estado=activo|cerrado` e `incluir_cerrados`— se retiraron de los
# endpoints.
#
# **Leerlos sigue tolerándose**, y es a propósito. Son dos cosas distintas: el
# CHECK protege lo que entra, esto protege lo que sale. Mientras haya una base
# sin los dos SQL aplicados —el servidor de producción, hoy, es una— sus filas
# siguen diciendo `activo`, y sin esto la API contestaría un estado que la
# pantalla no entiende y la fila saldría en blanco sin explicar por qué.
# Traducir al leer no esconde nada: lo que se escribe son siempre los cinco.
# --------------------------------------------------------------------------

#: Lo que había antes de H8, y en qué se convierte.
LEGADO = {"activo": EN_EJECUCION, "cerrado": FINALIZADO}


def normalizar_legado(valor: Optional[str]) -> str:
    """Traduce un valor viejo al nuevo. Lo demás sale tal cual.

    El SQL de H8 migró las filas, así que esto **no debería hacer nada**. Está
    porque el precio de equivocarse es asimétrico: si una base se quedara sin
    aplicar el script —la de pruebas que se recrea, la del servidor el día del
    despliegue—, sin esto la API contestaría `activo` a una pantalla que solo
    entiende los cinco nuevos, y la fila saldría sin estado y sin explicación.
    Traducir al leer no esconde el problema: lo que se escribe siempre es uno de
    los cinco, y desde H8.6 el CHECK de la base tampoco deja escribir otra cosa.

    >>> normalizar_legado("cerrado")
    'finalizado'
    >>> normalizar_legado(None)
    'en_ejecucion'
    """
    if not valor:
        return POR_DEFECTO
    return LEGADO.get(valor, valor)


def texto(valor: Optional[str]) -> str:
    """El rótulo que se lee en pantalla. Nunca vacío."""
    v = normalizar_legado(valor)
    return TEXTOS.get(v, v)


def es_valido(valor: Optional[str]) -> bool:
    """¿Es uno de los cinco? Los valores viejos **no** lo son: se pueden leer,
    pero no se pueden escribir."""
    return valor in ESTADOS


def admite_registro(valor: Optional[str]) -> bool:
    return normalizar_legado(valor) not in BLOQUEAN_REGISTRO


def admite_estimacion(valor: Optional[str]) -> bool:
    return normalizar_legado(valor) not in BLOQUEAN_ESTIMACION


def admite_importacion(valor: Optional[str]) -> bool:
    """§6.2.8: la importación entra en cualquier estado menos `no_viable`."""
    return normalizar_legado(valor) not in BLOQUEAN_IMPORTACION


def exige_admin(valor: Optional[str]) -> bool:
    return normalizar_legado(valor) in SOLO_ADMIN


def visibles_por_defecto() -> list:
    """Los estados que salen sin pedir nada (H-D84).

    Se devuelve la lista para meterla en un `IN` de SQL: **filtrar por lo que se
    incluye es más seguro que por lo que se excluye**, porque un valor que nadie
    haya previsto se queda fuera en vez de colarse.

    Van también los valores viejos que corresponden a un estado visible —hoy
    solo `activo`—, por la misma razón que existe `normalizar_legado`: en una
    base sin el SQL aplicado, excluirlos dejaría el listado **entero** vacío, y
    un listado vacío parece «no hay proyectos», no «falta una migración».
    """
    visibles = [e for e in ESTADOS if e not in OCULTOS_POR_DEFECTO]
    return visibles + [v for v, nuevo in LEGADO.items() if nuevo in visibles]
