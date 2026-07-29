"""Ruteo de un HAR analizado hacia una generacion de JMX por bloques.

Sprint 3.0 — Fundacion 2. Consume lo que dejo la Fundacion 1
(``har_analysis_classification`` y ``har_analysis_dependencies``) y decide
como partir la generacion.

Por que partirla: un HAR de 100+ requests no entra en una sola respuesta del
modelo. El techo de salida (32K tokens en gpt-4.1) alcanza para ~30 samplers
completos con headers, bodies, assertions y extractores; mas alla de eso el
modelo trunca el XML a mitad de camino y el JMX sale inservible. Generar de a
bloques cambia el problema de "una respuesta gigante que puede truncarse" a
"N respuestas chicas que se ensamblan".

Estrategia de particion:

- **Chunk 1 (esqueleto).** ``auth`` + ``navigation`` + ``config``. Va primero
  porque es donde nacen los datos que todo lo demas consume: el login produce
  el token, el catalogo produce los IDs. Ademas genera el andamiaje del JMX
  (Test Plan, UDVs, managers, Thread Group), asi que su salida es un JMX
  completo y cerrado, no un fragmento.
- **Chunks siguientes.** ``xhr`` + ``write`` en bloques de ~15 entries, en el
  orden original del HAR. Cada uno produce solo samplers, que el ensamblador
  inserta en el hashTree del Thread Group ya existente.

Todo aca es logica pura: sin DB, sin red, sin cliente de IA. El caller inyecta
``call_ai`` igual que en la Fundacion 1.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services.ai.har_flow_analyzer import (
    FUNCTIONAL_CATEGORIES,
    entry_digest,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Por debajo de esto, una sola llamada al modelo alcanza y el chunking solo
# agrega latencia y costo. El umbral cuenta entries FUNCIONALES —
# FUNCTIONAL_CATEGORIES de la Fundacion 1, que excluye 'navigation'. Las
# navegaciones viajan igual en el chunk 1, pero no empujan la decision: un HAR
# con 40 cargas de pagina y 5 llamadas de API no necesita partirse.
_MIN_FUNCTIONAL_FOR_CHUNKING = 30

# Entries por chunk de transacciones. 15 samplers completos (headers + body +
# assertion + extractores) entran holgados en una respuesta de 32K tokens.
_CHUNK_SIZE = 15

# Categorias del chunk esqueleto, en orden de prioridad narrativa.
_SKELETON_CATEGORIES = ("auth", "navigation", "config")

# Categorias de los chunks de transacciones.
_TRANSACTION_CATEGORIES = ("xhr", "write")

CHUNK_PENDING = "pending"
CHUNK_COMPLETED = "completed"
CHUNK_FAILED = "failed"
# Sprint 3.0 F2.1 — el chunk se partio en dos por truncacion. No se genera ni
# se cuenta: queda en el plan solo como rastro de linaje. Sus entries viven
# ahora en los hijos.
CHUNK_SPLIT = "split"

# Sprint 3.0 F2.1 — cuantas veces se puede partir un chunk original.
# 2 niveles: 15 -> ~8 -> ~4. Mas profundidad no arregla el problema de fondo
# (un request individual demasiado pesado) y multiplica el costo en llamadas.
_MAX_SPLIT_DEPTH = 2

MODE_CHUNKED = "chunked"
MODE_SINGLE = "single"

GENERATION_COMPLETED = "completed"
GENERATION_PARTIAL = "partial"
GENERATION_FAILED = "failed"


# ---------------------------------------------------------------------------
# Decision de modo
# ---------------------------------------------------------------------------


def count_functional_entries(classification: Optional[Dict[str, Any]]) -> int:
    """Entries cuya categoria esta en FUNCTIONAL_CATEGORIES (sin navigation)."""
    if not isinstance(classification, dict):
        return 0
    entries = classification.get("entries")
    if not isinstance(entries, list):
        return 0
    return sum(
        1
        for e in entries
        if isinstance(e, dict) and e.get("category") in FUNCTIONAL_CATEGORIES
    )


def should_use_chunked_generation(
    classification: Optional[Dict[str, Any]],
) -> Tuple[bool, str]:
    """Decide entre generacion por chunks y el flujo clasico de 1 llamada.

    Returns:
        ``(usar_chunks, motivo)``. El motivo es texto para el usuario, no un
        codigo: viaja tal cual en la respuesta del endpoint.
    """
    if not isinstance(classification, dict) or not classification.get("entries"):
        return False, (
            "El diseno no tiene un analisis de HAR utilizable; corre "
            "/analyze-har antes de generar por chunks."
        )

    functional = count_functional_entries(classification)
    if functional <= _MIN_FUNCTIONAL_FOR_CHUNKING:
        return False, (
            f"El HAR tiene {functional} entries funcionales (umbral: mas de "
            f"{_MIN_FUNCTIONAL_FOR_CHUNKING}); el flujo normal de una sola "
            f"llamada lo cubre sin truncarse."
        )

    return True, (
        f"El HAR tiene {functional} entries funcionales (umbral: mas de "
        f"{_MIN_FUNCTIONAL_FOR_CHUNKING}); se genera por bloques."
    )


# ---------------------------------------------------------------------------
# Agrupacion en chunks
# ---------------------------------------------------------------------------


def _idxs_by_categories(
    classification: Dict[str, Any], categories: Tuple[str, ...]
) -> List[int]:
    """Idx de los entries de esas categorias, en el orden original del HAR."""
    out: List[int] = []
    for e in classification.get("entries") or []:
        if not isinstance(e, dict) or e.get("category") not in categories:
            continue
        try:
            out.append(int(e.get("idx")))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def group_entries_into_chunks(
    classification: Dict[str, Any],
    dependencies: Optional[Dict[str, Any]] = None,
    *,
    chunk_size: int = _CHUNK_SIZE,
) -> List[Dict[str, Any]]:
    """Arma el plan de chunks a partir de la clasificacion de la Fundacion 1.

    El plan es lo que se persiste en ``ai_script_designs.chunks_plan``. Cada
    chunk lleva su propio ``status`` para que un fallo a mitad de camino sea
    reanudable sin rehacer lo que ya salio bien.

    Garantia: **ningun entry clasificado se pierde**. La union de los
    ``entry_idxs`` de todos los chunks es exactamente el conjunto de idx
    clasificados.
    """
    skeleton_idxs = _idxs_by_categories(classification, _SKELETON_CATEGORIES)
    transaction_idxs = _idxs_by_categories(classification, _TRANSACTION_CATEGORIES)

    # Cualquier categoria que no caiga en ninguno de los dos grupos (defensa
    # ante una categoria futura) se suma a las transacciones para no perderla.
    known = set(_SKELETON_CATEGORIES) | set(_TRANSACTION_CATEGORIES)
    orphan_idxs = [
        int(e["idx"])
        for e in classification.get("entries") or []
        if isinstance(e, dict)
        and e.get("category") not in known
        and str(e.get("idx", "")).lstrip("-").isdigit()
    ]
    if orphan_idxs:
        logger.warning(
            "chunk router: %d entries con categoria desconocida van a transacciones",
            len(orphan_idxs),
        )
        transaction_idxs = sorted(set(transaction_idxs) | set(orphan_idxs))

    plan: List[Dict[str, Any]] = []
    chunk_id = 1

    if skeleton_idxs:
        plan.append(
            {
                "chunk_id": chunk_id,
                "name": "Chunk 1 - Esqueleto + autenticacion",
                "entry_idxs": skeleton_idxs,
                "categories": list(_SKELETON_CATEGORIES),
                "status": CHUNK_PENDING,
                "is_skeleton": True,
                "failure_reason": None,
                "split_depth": 0,
                "parent_chunk_id": None,
            }
        )
        chunk_id += 1

    blocks = [
        transaction_idxs[i : i + chunk_size]
        for i in range(0, len(transaction_idxs), chunk_size)
    ]
    total_blocks = len(blocks)
    for position, block in enumerate(blocks, start=1):
        is_first = not plan  # sin entries de esqueleto, el bloque 1 hace de tal
        plan.append(
            {
                "chunk_id": chunk_id,
                "name": f"Chunk {chunk_id} - Transacciones {position}/{total_blocks}",
                "entry_idxs": block,
                "categories": list(_TRANSACTION_CATEGORIES),
                "status": CHUNK_PENDING,
                "is_skeleton": is_first,
                "failure_reason": None,
                "split_depth": 0,
                "parent_chunk_id": None,
            }
        )
        chunk_id += 1

    return plan


# ---------------------------------------------------------------------------
# Auto-split de chunks truncados (Sprint 3.0 F2.1)
# ---------------------------------------------------------------------------


def next_free_chunk_id(plan: List[Dict[str, Any]]) -> int:
    """Primer ``chunk_id`` entero libre del plan.

    Los hijos de un split reciben IDs NUEVOS, nunca reciclados: el prefijo
    ``[Cn]`` ya esta escrito en los ``testname`` del JMX persistido de los
    chunks completados. Renumerar romperia esa trazabilidad de forma silenciosa.
    """
    ids = [
        int(c.get("chunk_id", 0))
        for c in plan
        if isinstance(c, dict) and isinstance(c.get("chunk_id"), int)
    ]
    return (max(ids) + 1) if ids else 1


def can_split_chunk(chunk: Dict[str, Any]) -> Tuple[bool, str]:
    """Decide si un chunk truncado se puede partir, y explica por que no.

    El motivo vuelve en el ``failure_reason`` del chunk, asi que esta escrito
    para que lo lea una persona, no un parser.
    """
    idxs = chunk.get("entry_idxs") or []
    depth = int(chunk.get("split_depth") or 0)

    if len(idxs) < 2:
        return False, (
            "El bloque ya es de un solo request: un entry individual excede la "
            "capacidad de salida del modelo y requiere revision manual "
            "(acortar el body/URL de ese request o usar un modelo con mayor "
            "limite de salida)."
        )
    if depth >= _MAX_SPLIT_DEPTH:
        return False, (
            f"El bloque ya se partio {depth} veces (maximo {_MAX_SPLIT_DEPTH}) "
            f"y sigue truncando; requiere revision manual."
        )
    return True, ""


def split_chunk(
    chunk: Dict[str, Any], next_chunk_id: int
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Parte un chunk truncado en dos mitades. Funcion pura.

    Args:
        chunk: el chunk que trunco.
        next_chunk_id: primer ID libre del plan (ver ``next_free_chunk_id``).

    Returns:
        ``(hijo_a, hijo_b)`` o ``None`` si el chunk no es divisible.

    Garantias:

    - **El orden del HAR se preserva**: ``hijo_a`` lleva la primera mitad y
      ``hijo_b`` la segunda, ambas ordenadas. La correlacion depende de que un
      token se extraiga antes de usarse, asi que reordenar romperia el plan.
    - **La union de los hijos es exactamente el padre**, sin duplicados.
    - **IDs nuevos**, nunca reciclados (ver ``next_free_chunk_id``).
    - Si el padre era el esqueleto, ``hijo_a`` hereda ese rol —sigue teniendo
      que generar el JMX completo— y ``hijo_b`` pasa a ser un bloque normal
      que se ensambla dentro de lo que genero su hermano.
    """
    ok, _reason = can_split_chunk(chunk)
    if not ok:
        return None

    idxs = sorted(int(i) for i in (chunk.get("entry_idxs") or []))
    half = len(idxs) // 2  # con impares, la primera mitad es la mas chica
    first, second = idxs[:half], idxs[half:]

    parent_id = chunk.get("chunk_id")
    depth = int(chunk.get("split_depth") or 0) + 1
    base_name = str(chunk.get("name") or f"Chunk {parent_id}")
    # El nombre conserva el del padre para que el plan siga siendo legible
    # despues de dos niveles de split.
    short_name = base_name.split(" - ", 1)[-1]
    categories = list(chunk.get("categories") or [])
    was_skeleton = bool(chunk.get("is_skeleton"))

    def _child(child_id: int, child_idxs: List[int], half_no: int, skeleton: bool):
        return {
            "chunk_id": child_id,
            "name": f"Chunk {child_id} - {short_name} (mitad {half_no}/2 de C{parent_id})",
            "entry_idxs": child_idxs,
            "categories": categories,
            "status": CHUNK_PENDING,
            "is_skeleton": skeleton,
            "failure_reason": None,
            "split_depth": depth,
            "parent_chunk_id": parent_id,
        }

    return (
        _child(next_chunk_id, first, 1, was_skeleton),
        _child(next_chunk_id + 1, second, 2, False),
    )


# ---------------------------------------------------------------------------
# Dependencias por chunk
# ---------------------------------------------------------------------------


def get_dependencies_for_chunk(
    chunk: Dict[str, Any], dependencies: Optional[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """Parte las dependencias globales en las que le importan a un chunk.

    - ``produces``: el dato nace en este chunk (``source_idx`` adentro). Son
      los extractores que este chunk DEBE generar.
    - ``consumes``: el dato lo produjo un chunk anterior (``target_idx``
      adentro, ``source_idx`` afuera). Son las variables que este chunk usa
      pero no extrae.
    - ``internal``: ambos extremos adentro. Subconjunto de ``produces``, se
      expone aparte porque el prompt lo menciona distinto (el modelo ve el
      extractor y su uso en el mismo bloque).
    """
    deps = []
    if isinstance(dependencies, dict):
        raw = dependencies.get("dependencies")
        if isinstance(raw, list):
            deps = [d for d in raw if isinstance(d, dict)]

    inside = set(chunk.get("entry_idxs") or [])

    produces: List[Dict[str, Any]] = []
    consumes: List[Dict[str, Any]] = []
    internal: List[Dict[str, Any]] = []

    for d in deps:
        src_in = d.get("source_idx") in inside
        tgt_in = d.get("target_idx") in inside
        if src_in:
            produces.append(d)
            if tgt_in:
                internal.append(d)
        elif tgt_in:
            consumes.append(d)

    return {"produces": produces, "consumes": consumes, "internal": internal}


def variables_available_from(
    plan: List[Dict[str, Any]],
    dependencies: Optional[Dict[str, Any]],
    up_to_chunk_id: int,
) -> List[Dict[str, Any]]:
    """Variables ya extraidas por los chunks COMPLETADOS anteriores.

    Es lo que el prompt del chunk N recibe como "esto ya existe, usalo": sin
    esta lista el modelo re-inventa el login en cada bloque.
    """
    # F2.1 — el corte es por POSICION en el plan, no por chunk_id. Tras un
    # split los hijos reciben IDs altos pero se insertan en el lugar del padre,
    # asi que comparar IDs escondia variables ya extraidas de los bloques
    # posteriores.
    cutoff = len(plan)
    for pos, chunk in enumerate(plan):
        if chunk.get("chunk_id") == up_to_chunk_id:
            cutoff = pos
            break

    done_idxs: set = set()
    for chunk in plan[:cutoff]:
        if chunk.get("status") != CHUNK_COMPLETED:
            continue
        done_idxs |= set(chunk.get("entry_idxs") or [])

    if not done_idxs or not isinstance(dependencies, dict):
        return []

    seen: set = set()
    out: List[Dict[str, Any]] = []
    for d in dependencies.get("dependencies") or []:
        if not isinstance(d, dict) or d.get("source_idx") not in done_idxs:
            continue
        name = d.get("data_name")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(
            {
                "data_name": name,
                "extractor_hint": d.get("extractor_hint", ""),
                "locations": d.get("locations", []),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Digests de los entries de un chunk
# ---------------------------------------------------------------------------


def digests_for_chunk(
    entries: List[Dict[str, Any]],
    chunk: Dict[str, Any],
    classification: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Digests (reusa ``entry_digest`` de la Fundacion 1) de este chunk.

    ``entries`` es la lista cruda de ``log.entries``; los idx del chunk son
    posiciones en esa lista. Un idx fuera de rango se ignora en vez de romper:
    el HAR pudo haber cambiado despues del analisis.
    """
    categories: Dict[int, str] = {}
    if isinstance(classification, dict):
        for e in classification.get("entries") or []:
            if isinstance(e, dict) and isinstance(e.get("idx"), int):
                categories[e["idx"]] = e.get("category", "")

    out: List[Dict[str, Any]] = []
    for idx in chunk.get("entry_idxs") or []:
        if not isinstance(idx, int) or idx < 0 or idx >= len(entries):
            continue
        digest = entry_digest(entries[idx], idx)
        if idx in categories:
            digest["category"] = categories[idx]
        out.append(digest)
    return out


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_CHUNK_SYSTEM = """Eres un arquitecto experto en Apache JMeter 5.6.3.

Generas XML de JMeter valido y nada mas: sin explicaciones, sin comentarios
fuera del XML, sin texto antes ni despues del bloque.

Reglas de calidad que aplican SIEMPRE:
- Un HTTP Request Sampler por cada request recibido, en el mismo orden.
- Nombres de sampler descriptivos y numerados.
- Header Manager por sampler cuando el request tiene headers relevantes.
- Response Assertion por sampler sobre el codigo esperado.
- Nada de URLs, hosts ni credenciales hardcodeadas: usa variables ${...}.
- Los valores dinamicos (tokens, IDs) SIEMPRE por variable, nunca literales."""


def _extractor_block(deps: Dict[str, List[Dict[str, Any]]]) -> str:
    """Instrucciones de extractores/uso derivadas de las dependencias reales."""
    lines: List[str] = []

    if deps["produces"]:
        lines.append(
            "EXTRACTORES OBLIGATORIOS (estos requests producen datos que el "
            "resto del plan consume):"
        )
        for d in deps["produces"]:
            lines.append(
                f"- Del request idx {d.get('source_idx')} extrae "
                f"'{d.get('data_name')}' hacia la variable "
                f"${{{d.get('data_name')}}}. Sugerencia: "
                f"{d.get('extractor_hint') or 'JSON Extractor'}. "
                f"Lo consume el request idx {d.get('target_idx')}."
            )

    if deps["consumes"]:
        lines.append("")
        lines.append(
            "VARIABLES QUE YA EXISTEN (extraidas en bloques anteriores; usalas, "
            "NO vuelvas a crear el extractor):"
        )
        for d in deps["consumes"]:
            where = ", ".join(str(x) for x in (d.get("locations") or [])) or "n/d"
            lines.append(
                f"- ${{{d.get('data_name')}}} — se usa en el request idx "
                f"{d.get('target_idx')} ({where})."
            )

    return "\n".join(lines)


def build_first_chunk_prompt(
    chunk: Dict[str, Any],
    digests: List[Dict[str, Any]],
    deps: Dict[str, List[Dict[str, Any]]],
    *,
    plan_name: str = "Plan de carga",
    total_chunks: int = 1,
) -> List[Dict[str, str]]:
    """Chunk esqueleto: JMX COMPLETO y cerrado.

    Los conteos del prompt se calculan de los datos; nada hardcodeado.
    """
    n = len(digests)
    extractors = _extractor_block(deps)

    user = f"""Genera un JMX COMPLETO y CERRADO para "{plan_name}".

Este es el bloque 1 de {total_chunks}: arma TODO el andamiaje del plan mas los
{n} requests de este bloque. Los bloques siguientes solo agregaran samplers
dentro del hashTree del Thread Group que generes aca, asi que la estructura
tiene que quedar completa y valida por si sola.

ESTRUCTURA OBLIGATORIA:
1. <?xml version="1.0" encoding="UTF-8"?> y <jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
2. Test Plan con nombre descriptivo.
3. User Defined Variables con host(s), scheme, port y todo lo parametrizable.
4. HTTP Request Defaults.
5. HTTP Cookie Manager y HTTP Cache Manager.
6. UN solo Thread Group (los bloques siguientes insertan ahi).
7. Dentro del hashTree del Thread Group, los {n} samplers de este bloque en el
   orden recibido.
8. Cierra correctamente jmeterTestPlan.

{extractors}

REQUESTS DE ESTE BLOQUE ({n}):
{json.dumps(digests, ensure_ascii=False, indent=1)}

Responde SOLO con el XML del JMX, sin markdown ni explicaciones."""

    return [
        {"role": "system", "content": _CHUNK_SYSTEM},
        {"role": "user", "content": user},
    ]


def build_next_chunk_prompt(
    chunk: Dict[str, Any],
    digests: List[Dict[str, Any]],
    deps: Dict[str, List[Dict[str, Any]]],
    available_variables: List[Dict[str, Any]],
    *,
    total_chunks: int = 1,
) -> List[Dict[str, str]]:
    """Chunks siguientes: SOLO samplers + sus hashTree, sin envoltura."""
    n = len(digests)
    chunk_id = chunk.get("chunk_id", 2)
    extractors = _extractor_block(deps)

    if available_variables:
        var_lines = "\n".join(
            f"- ${{{v['data_name']}}}"
            + (f" ({v['extractor_hint']})" if v.get("extractor_hint") else "")
            for v in available_variables
        )
        vars_block = (
            "VARIABLES YA DISPONIBLES EN EL PLAN (extraidas por bloques "
            "anteriores — usalas en headers, URLs y bodies donde corresponda; "
            "NO generes extractores para ellas):\n" + var_lines
        )
    else:
        vars_block = (
            "No hay variables extraidas por bloques anteriores; parametriza lo "
            "que necesites con User Defined Variables ya existentes."
        )

    user = f"""Genera los samplers del bloque {chunk_id} de {total_chunks}.

Este bloque se INSERTA dentro del hashTree de un Thread Group que ya existe.
Por eso NO generes jmeterTestPlan, ni TestPlan, ni Thread Group, ni Cookie
Manager, ni User Defined Variables: solo los {n} HTTPSamplerProxy de este
bloque, cada uno seguido de su <hashTree> con sus Header Manager, Response
Assertion y extractores.

FORMATO DE SALIDA (exacto, repetido {n} veces):
<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="..." enabled="true">
  ...
</HTTPSamplerProxy>
<hashTree>
  ...
</hashTree>

{vars_block}

{extractors}

REQUESTS DE ESTE BLOQUE ({n}):
{json.dumps(digests, ensure_ascii=False, indent=1)}

Responde SOLO con los {n} pares sampler+hashTree, sin envoltura y sin markdown."""

    return [
        {"role": "system", "content": _CHUNK_SYSTEM},
        {"role": "user", "content": user},
    ]
