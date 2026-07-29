"""Ensamblado incremental de fragmentos JMX (Sprint 3.0 — Fundacion 2).

El chunk 1 produce un JMX completo. Los chunks siguientes producen solo pares
``HTTPSamplerProxy`` + ``hashTree``, que hay que meter DENTRO del hashTree del
Thread Group ya existente. Este modulo hace esa cirugia.

Reglas del contrato, en orden de importancia:

1. **El JMX previo valido nunca se corrompe.** Toda falla —fragmento sin XML,
   fragmento mal formado, JMX sin Thread Group, resultado que no re-parsea—
   devuelve ``(False, jmx_original_intacto, motivo)``. El caller marca el
   chunk como fallido y sigue teniendo el JMX bueno en la mano.
2. **Se valida re-parseando**, no confiando. Despues de insertar, el
   resultado se serializa y se vuelve a parsear; si eso falla, se descarta.
3. **Prefijo ``[Cn]`` en el testname** de los elementos insertados, para que
   dos chunks no colisionen con nombres iguales y para poder rastrear que
   bloque genero cada sampler. Un elemento ya prefijado no se re-prefija.

Todo es logica XML pura: sin DB, sin red, sin IA.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# Envoltura sintetica para poder parsear un fragmento con varios elementos raiz.
_FRAGMENT_ROOT = "kinetixChunkFragment"

# ```xml ... ``` que el modelo mete aunque el prompt lo prohiba.
_FENCE_RE = re.compile(r"```(?:xml)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# testname que ya lleva prefijo de chunk: "[C3] ..."
_PREFIXED_RE = re.compile(r"^\[C\d+\]\s")

# '&' que NO abre una entidad valida (&amp; &#38; &#x26;). Es el error de XML
# mas comun en la salida del modelo: una URL con query string se escribe
# literal —"?page=1&size=20"— y eso rompe el parseo aunque el XML este bien
# formado en todo lo demas. Escapar solo estos '&' es seguro: los que ya son
# entidad quedan intactos.
_BARE_AMP_RE = re.compile(r"&(?!(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#[xX][0-9A-Fa-f]+);)")

# Elementos que cuentan como "sampler" para decidir donde insertar.
_SAMPLER_HINTS = ("sampler", "samplerproxy")


class _NoThreadGroup(Exception):
    """El JMX no tiene un Thread Group con su hashTree."""


# ---------------------------------------------------------------------------
# Extraccion del fragmento
# ---------------------------------------------------------------------------


def escape_bare_ampersands(xml: str) -> str:
    """Escapa los '&' que no abren una entidad valida.

    Corrige la falla mas frecuente de la salida del modelo sin tocar nada mas:
    un XML por lo demas correcto que trae una URL con query string sin escapar.
    No intenta reparar otros defectos — un fragmento realmente roto sigue
    fallando, que es lo que queremos.
    """
    return _BARE_AMP_RE.sub("&amp;", xml or "")


def extract_fragment_xml(raw: Optional[str]) -> str:
    """Recorta el XML util de la respuesta del modelo.

    Tolera fences de markdown, prosa alrededor y '&' sin escapar. Devuelve ""
    si no hay nada que parezca XML — el caller lo trata como fallo del chunk.
    """
    if not raw or not raw.strip():
        return ""

    text = raw.strip()

    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    start = text.find("<")
    end = text.rfind(">")
    if start == -1 or end <= start:
        return ""
    return escape_bare_ampersands(text[start : end + 1].strip())


def _parse_fragment(fragment_xml: str) -> List[ET.Element]:
    """Parsea el fragmento envolviendolo en una raiz sintetica.

    Un fragmento tiene N elementos de primer nivel (sampler, hashTree,
    sampler, hashTree...), lo que no es XML valido por si solo.
    """
    wrapped = f"<{_FRAGMENT_ROOT}>{fragment_xml}</{_FRAGMENT_ROOT}>"
    root = ET.fromstring(wrapped)  # ParseError sube al caller
    return list(root)


# ---------------------------------------------------------------------------
# Localizacion del Thread Group
# ---------------------------------------------------------------------------


def _is_thread_group(elem: ET.Element) -> bool:
    """True para ThreadGroup y sus variantes (Setup/Post/Stepping/Concurrency)."""
    return elem.tag.lower().endswith("threadgroup")


def _is_sampler(elem: ET.Element) -> bool:
    tag = elem.tag.lower()
    return any(hint in tag for hint in _SAMPLER_HINTS)


def find_thread_group_hashtree(root: ET.Element) -> ET.Element:
    """Devuelve el hashTree hermano del primer Thread Group encontrado.

    En un JMX la estructura es ``<ThreadGroup/>`` seguido de su
    ``<hashTree>``: son hermanos, no padre/hijo. ElementTree no da punteros al
    padre, asi que se recorre cada hashTree mirando sus hijos de a pares.
    """
    for parent in root.iter():
        children = list(parent)
        for i, child in enumerate(children):
            if not _is_thread_group(child):
                continue
            if i + 1 < len(children) and children[i + 1].tag == "hashTree":
                return children[i + 1]
    raise _NoThreadGroup("El JMX no tiene un Thread Group con su hashTree")


def _insertion_index(container: ET.Element) -> int:
    """Donde insertar: despues del ultimo par sampler+hashTree.

    Deja los listeners que suelen ir al final del Thread Group en su lugar, en
    vez de empujarlos al medio del flujo.
    """
    children = list(container)
    last = len(children)
    for i in range(len(children) - 1, -1, -1):
        if _is_sampler(children[i]):
            # el hashTree del sampler viene inmediatamente despues
            last = i + 2 if i + 1 < len(children) else i + 1
            break
    return min(last, len(children))


# ---------------------------------------------------------------------------
# Prefijos
# ---------------------------------------------------------------------------


def prefix_testname(elem: ET.Element, chunk_id: int) -> None:
    """Antepone ``[Cn] `` al testname. Idempotente: no re-prefija."""
    name = elem.get("testname")
    if name is None:
        return
    if _PREFIXED_RE.match(name):
        return
    elem.set("testname", f"[C{chunk_id}] {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def count_samplers(jmx: Optional[str]) -> int:
    """Cuantos HTTPSamplerProxy tiene el JMX (para reportar avance)."""
    if not jmx:
        return 0
    return jmx.count("<HTTPSamplerProxy")


def assemble_chunk_into_jmx(
    current_jmx: Optional[str],
    fragment: Optional[str],
    chunk_id: int,
) -> Tuple[bool, str, str]:
    """Inserta el fragmento de un chunk en el JMX existente.

    Args:
        current_jmx: JMX valido acumulado hasta ahora.
        fragment: respuesta cruda del modelo para este chunk.
        chunk_id: numero de chunk, usado para el prefijo ``[Cn]``.

    Returns:
        ``(exito, jmx, motivo)``. Si ``exito`` es False, ``jmx`` es el
        ``current_jmx`` recibido, **sin tocar**, y ``motivo`` explica por que.
    """
    original = current_jmx or ""

    if not original.strip():
        return False, original, "No hay JMX base sobre el cual ensamblar"

    fragment_xml = extract_fragment_xml(fragment)
    if not fragment_xml:
        return False, original, "La IA no devolvio XML para este bloque"

    try:
        root = ET.fromstring(original)
    except ET.ParseError as e:
        return False, original, f"El JMX acumulado no es XML valido: {e}"

    try:
        new_elements = _parse_fragment(fragment_xml)
    except ET.ParseError as e:
        return False, original, f"El fragmento del bloque no es XML valido: {e}"

    if not new_elements:
        return False, original, "El fragmento del bloque venia vacio"

    try:
        container = find_thread_group_hashtree(root)
    except _NoThreadGroup as e:
        return False, original, str(e)

    for elem in new_elements:
        prefix_testname(elem, chunk_id)

    at = _insertion_index(container)
    for offset, elem in enumerate(new_elements):
        container.insert(at + offset, elem)

    try:
        rebuilt = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode(
            "utf-8"
        )
    except Exception as e:  # noqa: BLE001 — serializar no deberia fallar, pero si falla no se pisa nada
        return False, original, f"No se pudo serializar el JMX ensamblado: {e}"

    # Validacion final: el resultado tiene que volver a parsear y seguir siendo
    # un plan de JMeter. Sin esto, un fragmento raro puede dejar XML que parsea
    # pero ya no es un JMX.
    try:
        ET.fromstring(rebuilt)
    except ET.ParseError as e:
        return False, original, f"El JMX ensamblado no re-parsea: {e}"

    if "</jmeterTestPlan>" not in rebuilt:
        return False, original, "El JMX ensamblado perdio el cierre de jmeterTestPlan"

    added = count_samplers(rebuilt) - count_samplers(original)
    logger.info(
        "jmx assembler: chunk %d insertado — %d elementos, %d samplers nuevos",
        chunk_id, len(new_elements), added,
    )
    return True, rebuilt, f"{len(new_elements)} elementos insertados"


def sanitize_generated_jmx(jmx: Optional[str]) -> str:
    """Mismo saneo de entidades para un JMX completo (chunk esqueleto)."""
    return escape_bare_ampersands(jmx or "")


def validate_jmx(jmx: Optional[str]) -> Tuple[bool, str]:
    """Chequeo minimo de un JMX completo: parsea y tiene Thread Group."""
    if not jmx or not jmx.strip():
        return False, "JMX vacio"
    try:
        root = ET.fromstring(jmx)
    except ET.ParseError as e:
        return False, f"XML invalido: {e}"
    if root.tag != "jmeterTestPlan":
        return False, f"La raiz no es jmeterTestPlan (es '{root.tag}')"
    try:
        find_thread_group_hashtree(root)
    except _NoThreadGroup as e:
        return False, str(e)
    return True, "ok"
