"""Analisis multi-fase de un HAR (Sprint 3.0 — Fundacion 1).

El AI Script Designer ya sabe convertir un HAR en JMX de un solo tiro. Lo que
NO sabe es *que es cada request* ni *que dato viaja de uno a otro*: manda el
HAR comprimido entero al modelo y espera que el JMX salga correlacionado. Este
modulo separa esas dos preguntas en dos llamadas explicitas al modelo:

- **Fase 1 — clasificacion.** Cada entry recibe una categoria:
  ``navigation`` | ``xhr`` | ``auth`` | ``write`` | ``config``.
  El HAR que llega aca ya paso por ``compress_har`` (assets estaticos,
  tracking y duplicados fuera), asi que las 5 categorias cubren lo que queda.

- **Fase 2 — dependencias.** Solo sobre los entries *funcionales* (todo menos
  ``navigation``): que dato producido por el entry A consume el entry B —
  tokens de sesion, CSRF, IDs de recurso — con ``source_idx`` /
  ``target_idx`` / ``data_name`` / ``locations``.

Diseño:

- **Sincrono.** No hay cliente de IA propio: el caller inyecta un callback
  ``call_ai(messages) -> str``. En el endpoint ese callback envuelve al
  ``_call_ai`` de ``script_ai.py`` (que ya resuelve OpenAI vs Gemini). Asi el
  modulo se testea sin red y sin API key.
- **Fase 2 no bloquea a Fase 1.** Si la segunda llamada falla, la
  clasificacion se conserva y el status queda ``failed``.
- **Nada de esto bloquea la generacion de JMX**, que sigue su camino actual.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Debajo de este numero de entries el HAR no da para un analisis que valga dos
# llamadas al modelo: una grabacion de 8 requests se entiende leyendola.
_MIN_ENTRIES_FOR_AUTO_ANALYSIS = 20

CATEGORIES = ("navigation", "xhr", "auth", "write", "config")

# Fase 2 corre solo sobre estas. 'navigation' queda fuera: son cargas de pagina
# HTML que rara vez producen el dato que otro request consume (y cuando lo
# hacen —un CSRF en el HTML— el entry aparece igual como fuente porque la
# dependencia se declara por idx contra la lista completa).
FUNCTIONAL_CATEGORIES = ("auth", "write", "xhr", "config")

STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

SCHEMA_VERSION = 1

# Tope de chars por body embebido en el prompt. compress_har ya trunca a 2 KB;
# esto es un segundo cinturon para que 100+ entries no exploten el contexto.
_MAX_BODY_PREVIEW = 600

# Tope de entries que se mandan a la IA en una sola pasada.
_MAX_ENTRIES_PER_CALL = 200


class HarAnalysisError(Exception):
    """Falla controlada del analisis (HAR invalido o respuesta no parseable)."""


# ---------------------------------------------------------------------------
# Lectura del HAR
# ---------------------------------------------------------------------------


def extract_entries(reference_file_content: Optional[str]) -> List[Dict[str, Any]]:
    """Devuelve ``log.entries`` del HAR persistido en el diseno.

    El contenido guardado en ``ai_script_designs.reference_file_content`` es el
    HAR ya comprimido por ``compress_har``, que conserva el shape original
    ``{"log": {"entries": [...]}}``.
    """
    if not reference_file_content or not reference_file_content.strip():
        raise HarAnalysisError("El diseno no tiene contenido de archivo de referencia")

    try:
        har = json.loads(reference_file_content)
    except json.JSONDecodeError as e:
        raise HarAnalysisError(f"HAR invalido (JSON no parseable): {e}")

    if not isinstance(har, dict):
        raise HarAnalysisError("HAR invalido: la raiz no es un objeto JSON")

    log = har.get("log")
    if not isinstance(log, dict):
        raise HarAnalysisError("HAR invalido: falta el objeto 'log'")

    entries = log.get("entries")
    if not isinstance(entries, list):
        raise HarAnalysisError("HAR invalido: 'log.entries' no es una lista")

    return [e for e in entries if isinstance(e, dict)]


def should_auto_analyze(entries: List[Dict[str, Any]]) -> bool:
    """True si el HAR tiene entries suficientes para justificar el analisis."""
    return len(entries) >= _MIN_ENTRIES_FOR_AUTO_ANALYSIS


def source_fingerprint(reference_file_content: Optional[str]) -> str:
    """SHA1 del HAR — permite saltar un re-analisis del mismo contenido.

    Se guarda DENTRO del JSON de clasificacion en vez de en una columna aparte
    para no agregar una cuarta columna a la tabla.
    """
    return hashlib.sha1(
        (reference_file_content or "").encode("utf-8", errors="ignore")
    ).hexdigest()


def response_body_coverage(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """Cuantos entries del HAR traen realmente el body de la respuesta.

    Sprint 3.0 F3.1 — dato barato y puramente estructural (cero llamadas al
    modelo) que condiciona la calidad de la Fase 2: sin body de respuesta no
    hay de donde inferir que valor produce un request y consume otro, asi que
    una cobertura baja explica de antemano una correlacion pobre. Chrome graba
    sin bodies salvo que se exporte con "Preserve log" + contenido, y la UI
    necesita poder avisarlo ANTES de que el usuario gaste una generacion.
    """
    total = len(entries)
    with_body = 0
    for entry in entries:
        response = entry.get("response") or {}
        content = response.get("content") if isinstance(response, dict) else None
        text = content.get("text") if isinstance(content, dict) else None
        if isinstance(text, str) and text.strip():
            with_body += 1
    return {"entries_with_response_body": with_body, "total_entries": total}


# ---------------------------------------------------------------------------
# Digest de entries para el prompt
# ---------------------------------------------------------------------------


def _header_value(headers: Any, name: str) -> str:
    if not isinstance(headers, list):
        return ""
    target = name.lower()
    for h in headers:
        if isinstance(h, dict) and str(h.get("name", "")).lower() == target:
            return str(h.get("value", ""))
    return ""


def _clip(text: Any, limit: int = _MAX_BODY_PREVIEW) -> str:
    s = "" if text is None else str(text)
    s = s.strip()
    if len(s) <= limit:
        return s
    return s[:limit] + f"...[+{len(s) - limit} chars]"


def entry_digest(entry: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Representacion compacta de un entry para mandarlo al modelo."""
    req = entry.get("request") or {}
    res = entry.get("response") or {}
    url = str(req.get("url", ""))
    parsed = urlparse(url)

    post_data = req.get("postData") or {}
    req_body = post_data.get("text", "") if isinstance(post_data, dict) else ""

    res_content = res.get("content") or {}
    res_body = res_content.get("text", "") if isinstance(res_content, dict) else ""

    digest: Dict[str, Any] = {
        "idx": idx,
        "method": str(req.get("method", "GET")).upper(),
        "url": url,
        "path": parsed.path or "/",
        "query": parsed.query or "",
        "status": res.get("status", 0),
    }

    content_type = _header_value(req.get("headers"), "content-type")
    if content_type:
        digest["request_content_type"] = content_type
    if _header_value(req.get("headers"), "authorization"):
        digest["has_authorization_header"] = True
    if req_body:
        digest["request_body"] = _clip(req_body)
    if res_body:
        digest["response_body"] = _clip(res_body)

    return digest


def build_digests(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Digests indexados por posicion real en ``log.entries``."""
    return [entry_digest(e, i) for i, e in enumerate(entries[:_MAX_ENTRIES_PER_CALL])]


# ---------------------------------------------------------------------------
# Parser de respuestas de la IA
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_ai_json(raw: Optional[str]) -> Any:
    """Extrae el JSON de una respuesta del modelo.

    Tolera lo que los modelos hacen aunque el prompt lo prohiba: envolver en
    ```json ... ```, agregar un parrafo antes o despues, o ambas. Si no hay
    JSON parseable lanza ``HarAnalysisError`` en vez de reventar el request.
    """
    if not raw or not raw.strip():
        raise HarAnalysisError("La IA devolvio una respuesta vacia")

    text = raw.strip()

    candidates: List[str] = []
    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    candidates.append(text)

    # Ultimo recurso: recortar desde el primer { o [ hasta su cierre exterior.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise HarAnalysisError("La IA no devolvio JSON parseable")


# ---------------------------------------------------------------------------
# Fase 1 — clasificacion
# ---------------------------------------------------------------------------

_PHASE1_SYSTEM = """Eres un analista de trafico HTTP especializado en pruebas de carga con JMeter.

Recibes los requests de una grabacion HAR ya filtrada (sin assets estaticos ni
tracking). Tu unica tarea es clasificar CADA request en exactamente una categoria:

- navigation: carga de una pagina/vista (documento HTML, redireccion de UI).
- auth: login, logout, refresh de token, obtencion de CSRF, SSO, sesion.
- write: operacion que MODIFICA estado en el servidor (POST/PUT/PATCH/DELETE de negocio).
- config: catalogos, parametros, feature flags, menus, datos maestros de solo lectura.
- xhr: cualquier otra llamada de API de solo lectura (consultas, busquedas, listados).

Reglas:
- Si un request califica para 'auth' y para 'write', gana 'auth'.
- Si califica para 'config' y para 'xhr', gana 'config'.
- Respeta el idx recibido; no reordenes ni omitas requests.

RESPONDE UNICAMENTE CON JSON VALIDO. Sin markdown, sin ```json, sin texto antes
ni despues. Formato exacto:
{"entries":[{"idx":0,"category":"auth","reason":"texto breve"}]}"""


def build_phase1_messages(digests: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    payload = json.dumps({"requests": digests}, ensure_ascii=False)
    user = (
        f"Clasifica los {len(digests)} requests siguientes. "
        f"Devuelve un objeto con la clave 'entries' y un item por cada idx.\n\n"
        f"{payload}"
    )
    return [
        {"role": "system", "content": _PHASE1_SYSTEM},
        {"role": "user", "content": user},
    ]


def _normalize_category(value: Any) -> str:
    cat = str(value or "").strip().lower()
    return cat if cat in CATEGORIES else "xhr"


def parse_phase1_response(raw: str, digests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Normaliza la salida de Fase 1 contra los digests enviados.

    El modelo puede devolver la lista suelta o envuelta en ``entries``, saltarse
    idx o inventar categorias. Todo entry no clasificado cae a ``xhr`` para que
    la Fase 2 tenga siempre un universo completo.
    """
    parsed = parse_ai_json(raw)

    items: List[Any]
    if isinstance(parsed, dict):
        raw_items = parsed.get("entries") or parsed.get("requests") or []
        items = raw_items if isinstance(raw_items, list) else []
    elif isinstance(parsed, list):
        items = parsed
    else:
        raise HarAnalysisError("Fase 1: la IA devolvio un JSON con forma inesperada")

    by_idx: Dict[int, Dict[str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("idx"))
        except (TypeError, ValueError):
            continue
        by_idx[idx] = {
            "category": _normalize_category(item.get("category")),
            "reason": _clip(item.get("reason", ""), 200),
        }

    if not by_idx:
        raise HarAnalysisError("Fase 1: la IA no clasifico ningun request")

    classified: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {c: 0 for c in CATEGORIES}
    for digest in digests:
        idx = digest["idx"]
        hit = by_idx.get(idx, {"category": "xhr", "reason": "sin clasificar por la IA"})
        counts[hit["category"]] += 1
        classified.append(
            {
                "idx": idx,
                "method": digest["method"],
                "url": digest["url"],
                "category": hit["category"],
                "reason": hit["reason"],
            }
        )

    return {"entries": classified, "counts": counts}


# ---------------------------------------------------------------------------
# Fase 2 — dependencias
# ---------------------------------------------------------------------------

_PHASE2_SYSTEM = """Eres un especialista en correlacion de datos para pruebas de carga JMeter.

Recibes requests de una grabacion, ya clasificados, con sus bodies. Tu tarea es
detectar DEPENDENCIAS DE DATOS: valores que un request PRODUCE en su respuesta y
que otro request posterior CONSUME (tokens de sesion, JWT, CSRF, cookies de
aplicacion, IDs de recurso creados, numeros de orden, correlation ids).

Reglas:
- source_idx debe ser MENOR que target_idx (el dato se produce antes de usarse).
- Solo reporta dependencias con evidencia real en los datos recibidos. Si no
  encuentras ninguna, devuelve una lista vacia. NO inventes.
- locations describe donde esta el dato: usa rutas como
  "response.body.access_token" o "request.header.Authorization".
- extractor_hint: que extractor de JMeter usarias (JSON Extractor, Regular
  Expression Extractor, Boundary Extractor) y sobre que.
- confidence: "high" | "medium" | "low".

RESPONDE UNICAMENTE CON JSON VALIDO. Sin markdown, sin ```json, sin texto antes
ni despues. Formato exacto:
{"dependencies":[{"source_idx":0,"target_idx":3,"data_name":"access_token",
"locations":["response.body.access_token","request.header.Authorization"],
"extractor_hint":"JSON Extractor sobre $.access_token","confidence":"high"}]}"""


def build_phase2_messages(
    functional_digests: List[Dict[str, Any]],
    categories_by_idx: Dict[int, str],
) -> List[Dict[str, str]]:
    enriched = [
        {**d, "category": categories_by_idx.get(d["idx"], "xhr")}
        for d in functional_digests
    ]
    payload = json.dumps({"requests": enriched}, ensure_ascii=False)
    user = (
        f"Detecta las dependencias de datos entre estos {len(enriched)} requests "
        f"funcionales. Los idx son los de la grabacion completa; usalos tal cual.\n\n"
        f"{payload}"
    )
    return [
        {"role": "system", "content": _PHASE2_SYSTEM},
        {"role": "user", "content": user},
    ]


def filter_functional(
    digests: List[Dict[str, Any]], classification: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Digests cuyas categorias estan en ``FUNCTIONAL_CATEGORIES``."""
    functional_idx = {
        e["idx"]
        for e in classification.get("entries", [])
        if e.get("category") in FUNCTIONAL_CATEGORIES
    }
    return [d for d in digests if d["idx"] in functional_idx]


def parse_phase2_response(raw: str, valid_idx: set) -> List[Dict[str, Any]]:
    """Normaliza la salida de Fase 2 y descarta dependencias imposibles."""
    parsed = parse_ai_json(raw)

    items: List[Any]
    if isinstance(parsed, dict):
        raw_items = parsed.get("dependencies") or []
        items = raw_items if isinstance(raw_items, list) else []
    elif isinstance(parsed, list):
        items = parsed
    else:
        raise HarAnalysisError("Fase 2: la IA devolvio un JSON con forma inesperada")

    deps: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            source_idx = int(item.get("source_idx"))
            target_idx = int(item.get("target_idx"))
        except (TypeError, ValueError):
            continue
        # Una dependencia hacia atras o hacia un idx que no mandamos es ruido
        # del modelo, no un hallazgo.
        if source_idx >= target_idx:
            continue
        if source_idx not in valid_idx or target_idx not in valid_idx:
            continue

        locations = item.get("locations")
        if isinstance(locations, str):
            locations = [locations]
        elif not isinstance(locations, list):
            locations = []

        confidence = str(item.get("confidence", "")).strip().lower()
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"

        deps.append(
            {
                "source_idx": source_idx,
                "target_idx": target_idx,
                "data_name": _clip(item.get("data_name", ""), 120) or "dato_sin_nombre",
                "locations": [_clip(loc, 200) for loc in locations if loc],
                "extractor_hint": _clip(item.get("extractor_hint", ""), 300),
                "confidence": confidence,
            }
        )

    return deps


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------


def analyze_har_flow(
    reference_file_content: Optional[str],
    call_ai: Callable[[List[Dict[str, str]]], str],
    *,
    min_entries: int = _MIN_ENTRIES_FOR_AUTO_ANALYSIS,
) -> Dict[str, Any]:
    """Corre las dos fases sobre el HAR de un diseno. Sincrono.

    Args:
        reference_file_content: HAR (comprimido) tal como esta en la DB.
        call_ai: ``messages -> texto crudo del modelo``. El endpoint inyecta
            aca el ``_call_ai`` de ``script_ai.py``.
        min_entries: umbral de auto-analisis; expuesto para los tests.

    Returns:
        ``{status, classification, dependencies, error}`` listo para persistir.
        Nunca levanta por fallas del modelo: las traduce a ``status``.
        ``HarAnalysisError`` solo sale si el HAR en si es ilegible.
    """
    entries = extract_entries(reference_file_content)

    if len(entries) < min_entries:
        logger.info(
            "HAR flow analyzer: %d entries (< %d) -> skipped", len(entries), min_entries
        )
        return {
            "status": STATUS_SKIPPED,
            "classification": None,
            "dependencies": None,
            "error": (
                f"HAR con {len(entries)} entries funcionales; el analisis "
                f"automatico requiere al menos {min_entries}."
            ),
        }

    digests = build_digests(entries)
    fingerprint = source_fingerprint(reference_file_content)

    # ---- Fase 1 ----
    try:
        raw_phase1 = call_ai(build_phase1_messages(digests))
        phase1 = parse_phase1_response(raw_phase1, digests)
    except HarAnalysisError as e:
        logger.warning("HAR flow analyzer: Fase 1 fallo — %s", e)
        return {
            "status": STATUS_FAILED,
            "classification": None,
            "dependencies": None,
            "error": f"Fase 1 (clasificacion) fallo: {e}",
        }
    except Exception as e:  # noqa: BLE001 — el proveedor de IA puede fallar de mil formas
        logger.exception("HAR flow analyzer: Fase 1 lanzo excepcion")
        return {
            "status": STATUS_FAILED,
            "classification": None,
            "dependencies": None,
            "error": f"Fase 1 (clasificacion) fallo: {e}",
        }

    classification: Dict[str, Any] = {
        "version": SCHEMA_VERSION,
        "source_sha1": fingerprint,
        "total_entries": len(entries),
        "analyzed_entries": len(digests),
        "counts": phase1["counts"],
        "entries": phase1["entries"],
        "phase2_error": None,
        # F3.1 — se persiste junto a la clasificacion en vez de en una columna
        # propia: es un atributo del MISMO HAR que describe el resto del blob,
        # y asi queda invalidado por el mismo `source_sha1` sin logica extra.
        "response_body_coverage": response_body_coverage(entries),
    }

    # ---- Fase 2 ----
    functional = filter_functional(digests, phase1)
    if not functional:
        logger.info("HAR flow analyzer: sin entries funcionales -> Fase 2 vacia")
        return {
            "status": STATUS_COMPLETED,
            "classification": classification,
            "dependencies": {
                "version": SCHEMA_VERSION,
                "analyzed_entries": 0,
                "dependencies": [],
            },
            "error": None,
        }

    categories_by_idx = {e["idx"]: e["category"] for e in phase1["entries"]}
    valid_idx = {d["idx"] for d in functional}

    try:
        raw_phase2 = call_ai(build_phase2_messages(functional, categories_by_idx))
        deps = parse_phase2_response(raw_phase2, valid_idx)
    except Exception as e:  # noqa: BLE001 — Fase 2 nunca tumba a Fase 1
        logger.warning("HAR flow analyzer: Fase 2 fallo — %s", e)
        classification["phase2_error"] = str(e)
        return {
            "status": STATUS_FAILED,
            "classification": classification,
            "dependencies": None,
            "error": f"Fase 2 (dependencias) fallo: {e}",
        }

    logger.info(
        "HAR flow analyzer: OK — %d entries, %d funcionales, %d dependencias",
        len(entries), len(functional), len(deps),
    )
    return {
        "status": STATUS_COMPLETED,
        "classification": classification,
        "dependencies": {
            "version": SCHEMA_VERSION,
            "analyzed_entries": len(functional),
            "dependencies": deps,
        },
        "error": None,
    }
