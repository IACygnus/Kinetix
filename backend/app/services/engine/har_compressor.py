"""
Compresor inteligente de archivos HAR (Sprint 2.4-HF6).

Los HAR reales de aplicaciones grandes pueden pesar 30-50 MB. Mandar eso a
una IA como contexto excede el context window y es muy caro. Este modulo
reduce un HAR a su esencia para generacion de JMeter sin perder lo importante.

Estrategia:
1. Filtrar entries de assets estaticos (CSS, JS, imagenes, fuentes, etc.).
2. Filtrar entries de tracking/analytics (Google Analytics, Hotjar, etc.).
3. Deduplicar entries con misma URL canonica + metodo + body hash.
4. Truncar request/response bodies grandes.
5. Filtrar headers irrelevantes (Cookie, User-Agent, sec-*, x-firefox-*).
6. Mantener metadata util: contador de duplicados, response codes.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

# Extensiones de assets estaticos que NO aportan a un plan de carga
STATIC_EXTENSIONS = {
    ".css", ".scss", ".less",
    ".js", ".mjs", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp4", ".webm", ".mp3", ".wav", ".ogg",
    ".pdf",
}

# Patrones de URL que tipicamente son tracking/analytics (no API real)
TRACKING_URL_PATTERNS = [
    r"google-analytics\.com",
    r"googletagmanager\.com",
    r"doubleclick\.net",
    r"facebook\.com/tr",
    r"hotjar\.com",
    r"segment\.io",
    r"mixpanel\.com",
    r"newrelic\.com",
    r"datadoghq\.com",
    r"sentry\.io",
    r"clarity\.ms",
    r"bing\.com/bat",
    r"linkedin\.com/li/track",
]
TRACKING_RE = re.compile("|".join(TRACKING_URL_PATTERNS), re.IGNORECASE)

# Headers a remover (ruido, no aportan al JMX)
NOISE_HEADER_PREFIXES = (
    "cookie",
    "set-cookie",
    "user-agent",
    "accept-language",
    "accept-encoding",
    "accept",
    "sec-",
    "x-firefox-",
    "x-chrome-",
    "if-",  # if-none-match, if-modified-since
    "cache-control",
    "pragma",
    "dnt",
    "connection",
    "host",
    "referer",
    "origin",
)

# Headers que SI mantener (importantes para el JMX) — toman precedencia sobre
# los prefijos de ruido.
KEEP_HEADERS = {
    "content-type",
    "authorization",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
}

# Tamano maximo de body antes de truncar (en chars)
MAX_BODY_BYTES = 2048


def _is_static_asset(url: str) -> bool:
    """True si la URL apunta a un asset estatico."""
    if not url:
        return False
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in STATIC_EXTENSIONS)


def _is_tracking(url: str) -> bool:
    """True si la URL es de tracking/analytics."""
    if not url:
        return False
    return bool(TRACKING_RE.search(url))


def _should_keep_header(name: str) -> bool:
    """Decide si un header debe mantenerse."""
    if not name:
        return False
    n = name.lower()
    if n in KEEP_HEADERS:
        return True
    for prefix in NOISE_HEADER_PREFIXES:
        if n.startswith(prefix):
            return False
    return True


def _filter_headers(headers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtra headers manteniendo solo los relevantes."""
    return [h for h in (headers or []) if _should_keep_header(h.get("name", ""))]


def _truncate_body(body_text: str) -> str:
    """Trunca body si supera MAX_BODY_BYTES."""
    if not body_text:
        return ""
    if len(body_text) <= MAX_BODY_BYTES:
        return body_text
    return (
        body_text[:MAX_BODY_BYTES]
        + f"\n...truncado ({len(body_text)} bytes total)..."
    )


def _canonical_url(url: str) -> str:
    """URL canonica para dedup: descarta query string completa.

    Mantenemos scheme + netloc + path. La motivacion: queries con
    timestamps/csrf/ids dinamicos rompen el dedup natural y para un plan
    de carga el cliente JMeter va a parametrizar esa parte con
    variables, no necesita cada timestamp original.
    """
    parsed = urlparse(url or "")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _entry_fingerprint(entry: Dict[str, Any]) -> str:
    """Fingerprint para detectar duplicados.

    Mismo metodo + URL canonica + body hash = misma transaccion logica.
    """
    req = entry.get("request", {}) or {}
    method = (req.get("method") or "GET").upper()
    url = _canonical_url(req.get("url", ""))

    body = ""
    post_data = req.get("postData", {}) or {}
    if isinstance(post_data, dict):
        body = post_data.get("text", "") or ""
    body_hash = hashlib.md5(body.encode("utf-8", errors="ignore")).hexdigest()[:8]

    return f"{method}|{url}|{body_hash}"


def _simplify_entry(
    entry: Dict[str, Any], duplicate_count: int = 1
) -> Dict[str, Any]:
    """Simplifica un entry HAR para reducir tokens.

    - Filtra headers irrelevantes.
    - Trunca bodies grandes.
    - Remueve metadata no util (timings, cache, server_ip, etc.).
    """
    req = entry.get("request", {}) or {}
    res = entry.get("response", {}) or {}

    post_data = req.get("postData", {}) or {}
    post_text = ""
    if isinstance(post_data, dict):
        post_text = post_data.get("text", "") or ""

    res_content = res.get("content", {}) or {}
    res_text = ""
    if isinstance(res_content, dict):
        res_text = res_content.get("text", "") or ""

    simplified: Dict[str, Any] = {
        "request": {
            "method": req.get("method", "GET"),
            "url": req.get("url", ""),
            "headers": _filter_headers(req.get("headers", [])),
        },
        "response": {
            "status": res.get("status", 0),
            "statusText": res.get("statusText", ""),
        },
    }

    if post_text:
        simplified["request"]["postData"] = {
            "mimeType": post_data.get("mimeType", ""),
            "text": _truncate_body(post_text),
        }

    res_mime = (
        res_content.get("mimeType", "") if isinstance(res_content, dict) else ""
    )
    if res_text and any(
        t in res_mime.lower() for t in ("json", "xml", "text")
    ):
        simplified["response"]["content"] = {
            "mimeType": res_mime,
            "text": _truncate_body(res_text),
        }

    if duplicate_count > 1:
        simplified["_duplicate_count"] = duplicate_count

    return simplified


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def compress_har(har_content: str) -> Tuple[str, Dict[str, Any]]:
    """Comprime un HAR para mandarlo a la IA.

    Args:
        har_content: contenido raw del HAR (string JSON).

    Returns:
        (compressed_json_string, stats_dict).

    stats_dict contiene:
        - original_size: bytes del HAR original.
        - compressed_size: bytes del HAR comprimido.
        - reduction_ratio: porcentaje de reduccion.
        - entries_original: numero de entries originales.
        - entries_unique: numero de entries unicos tras dedup.
        - entries_static_filtered: cuantos entries de assets se filtraron.
        - entries_tracking_filtered: cuantos entries de tracking se filtraron.

    Raises:
        ValueError si el HAR no es JSON valido.
    """
    original_size = len(har_content.encode("utf-8"))

    try:
        har = json.loads(har_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"HAR invalido: {e}")

    log = har.get("log", {}) if isinstance(har, dict) else {}
    entries = log.get("entries", []) if isinstance(log, dict) else []
    entries_original = len(entries)

    # 1. Filtrar assets estaticos + tracking
    filtered: List[Dict[str, Any]] = []
    static_filtered = 0
    tracking_filtered = 0
    for entry in entries:
        url = ""
        if isinstance(entry, dict):
            url = (entry.get("request") or {}).get("url", "")
        if _is_static_asset(url):
            static_filtered += 1
            continue
        if _is_tracking(url):
            tracking_filtered += 1
            continue
        filtered.append(entry)

    # 2. Deduplicar por fingerprint
    seen: Dict[str, Dict[str, Any]] = {}
    counts: Dict[str, int] = {}
    order: List[str] = []  # mantener orden de aparicion
    for entry in filtered:
        fp = _entry_fingerprint(entry)
        if fp not in seen:
            seen[fp] = entry
            counts[fp] = 1
            order.append(fp)
        else:
            counts[fp] += 1

    # 3. Simplificar cada entry unico con su contador
    compressed_entries: List[Dict[str, Any]] = [
        _simplify_entry(seen[fp], counts[fp]) for fp in order
    ]

    # 4. Construir HAR comprimido (solo lo esencial)
    compressed_har = {
        "log": {
            "version": log.get("version", "1.2") if isinstance(log, dict) else "1.2",
            "creator": (
                log.get("creator")
                if isinstance(log, dict) and log.get("creator")
                else {"name": "compressed-by-kinetix"}
            ),
            "entries": compressed_entries,
        }
    }

    compressed_content = json.dumps(compressed_har, indent=2, ensure_ascii=False)
    compressed_size = len(compressed_content.encode("utf-8"))

    stats = {
        "original_size": original_size,
        "compressed_size": compressed_size,
        "reduction_ratio": (
            round((1 - compressed_size / original_size) * 100, 1)
            if original_size > 0
            else 0
        ),
        "entries_original": entries_original,
        "entries_unique": len(compressed_entries),
        "entries_static_filtered": static_filtered,
        "entries_tracking_filtered": tracking_filtered,
    }

    return compressed_content, stats
