# backend/app/services/engine/har_importer.py
"""
HAR Importer — Convierte archivos HAR (HTTP Archive) al Script Model interno.

El formato HAR es generado por las DevTools de Chrome, Firefox y otros navegadores.
Permite importar flujos de navegacion reales sin necesidad de proxy.

Filtros automaticos aplicados:
- Excluye recursos estaticos (JS, CSS, imagenes, fuentes, analytics)
- Excluye peticiones a CDNs conocidos (google-analytics, doubleclick, etc.)
- Conserva solo requests con Content-Type relevante (JSON, XML, form, text/html con body)
"""
import json
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path


# Extensiones de recursos estaticos a filtrar
STATIC_EXTENSIONS = {
    '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.eot', '.otf', '.mp4', '.mp3', '.pdf',
    '.map', '.ts'  # source maps
}

# Dominios/paths de analytics y trackers a filtrar
FILTER_DOMAINS = {
    'google-analytics.com', 'googletagmanager.com', 'doubleclick.net',
    'facebook.com/tr', 'hotjar.com', 'segment.com', 'mixpanel.com',
    'amplitude.com', 'fullstory.com', 'intercom.io', 'zendesk.com',
}

# Content-Types de response que indican recursos estaticos
STATIC_CONTENT_TYPES = {
    'image/', 'font/', 'audio/', 'video/',
    'application/javascript', 'text/javascript',
    'text/css',
}


class HARImporter:
    """
    Convierte un archivo HAR al Script Model JSON interno de SQA Kinetix Pro.

    Uso:
        importer = HARImporter()
        script_model, stats = importer.import_har(har_content, base_url_filter=None)
    """

    def import_har(self, har_content: str, base_url_filter: Optional[str] = None) -> tuple:
        """
        Importar contenido HAR y convertirlo al Script Model.

        Args:
            har_content: String JSON del archivo HAR
            base_url_filter: Si se provee, solo incluye requests a esta URL base
                             Ej: "https://api.miapp.com"

        Returns:
            tuple de (script_model, stats)
            stats: {"total_entries": N, "imported": M, "filtered_static": K, "filtered_other": J}
        """
        try:
            har = json.loads(har_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"El archivo HAR no es JSON valido: {e}")

        if "log" not in har:
            raise ValueError("Formato HAR invalido: falta la clave 'log'")

        entries = har["log"].get("entries", [])
        if not entries:
            raise ValueError("El archivo HAR no contiene entradas")

        requests = []
        stats = {
            "total_entries": len(entries),
            "imported": 0,
            "filtered_static": 0,
            "filtered_tracker": 0,
            "filtered_other": 0,
        }

        for i, entry in enumerate(entries):
            req = entry.get("request", {})
            resp = entry.get("response", {})
            url = req.get("url", "")

            # Filtro 1: URL base
            if base_url_filter and not url.startswith(base_url_filter):
                stats["filtered_other"] += 1
                continue

            # Filtro 2: recursos estaticos por extension
            path = url.split("?")[0].split("#")[0]
            ext = Path(path).suffix.lower()
            if ext in STATIC_EXTENSIONS:
                stats["filtered_static"] += 1
                continue

            # Filtro 3: trackers y analytics
            if self._is_tracker(url):
                stats["filtered_tracker"] += 1
                continue

            # Filtro 4: recursos estaticos por Content-Type de response
            resp_content_type = resp.get("content", {}).get("mimeType", "")
            if any(resp_content_type.startswith(ct) for ct in STATIC_CONTENT_TYPES):
                stats["filtered_static"] += 1
                continue

            # Construir request del Script Model
            script_req = self._build_request(req, resp, order=i)
            if script_req:
                requests.append(script_req)
                stats["imported"] += 1

        # Re-numerar order secuencialmente
        for idx, req in enumerate(requests):
            req["order"] = idx

        # Escanear variables usadas en los requests importados
        import re as _re
        _seen = set()
        _vars = []
        for req in requests:
            for text in [req.get("url", ""), req.get("body", ""), *list((req.get("headers") or {}).values())]:
                for vname in _re.findall(r'\$\{([^}]+)\}', str(text or "")):
                    if vname not in _seen and not vname.startswith('$'):
                        _seen.add(vname)
                        _vars.append({"name": vname, "value": "", "type": "imported", "source_hint": "Detectada al importar HAR", "source": "har"})

        script_model = {
            "requests": requests,
            "variables": _vars,
            "data_files": [],
            "protocol": "http",
        }

        return script_model, stats

    def _is_tracker(self, url: str) -> bool:
        """Detectar si la URL pertenece a un tracker o analytics."""
        url_lower = url.lower()
        return any(domain in url_lower for domain in FILTER_DOMAINS)

    def _build_request(self, req: Dict, resp: Dict, order: int) -> Optional[Dict[str, Any]]:
        """Construir un request del Script Model desde una entrada HAR."""
        url = req.get("url", "")
        method = req.get("method", "GET").upper()

        if not url:
            return None

        # Headers — filtrar headers tecnicos que httpx maneja automaticamente
        SKIP_HEADERS = {
            'host', 'content-length', 'connection', 'accept-encoding',
            ':method', ':path', ':scheme', ':authority',  # HTTP/2 pseudo-headers
        }
        headers = {}
        for h in req.get("headers", []):
            name = h.get("name", "")
            value = h.get("value", "")
            if name.lower() not in SKIP_HEADERS and not name.startswith(":"):
                headers[name] = value

        # Body
        body = ""
        body_type = "raw"
        post_data = req.get("postData", {})
        if post_data:
            body = post_data.get("text", "")
            mime = post_data.get("mimeType", "")
            if "json" in mime:
                body_type = "json"
            elif "xml" in mime:
                body_type = "xml"
            elif "form" in mime:
                body_type = "form"
            else:
                body_type = "raw"

        # Nombre de la transaccion: metodo + path sin query
        path_only = url.split("?")[0]
        path_segments = [s for s in path_only.split("/") if s]
        name = f"{method} /{'/'.join(path_segments[-2:])}" if path_segments else f"{method} /"

        # Assertion por defecto: status code del response real
        status_code = str(resp.get("status", 200))
        assertions = []
        if status_code and status_code != "0":
            assertions.append({"type": "status_code", "value": status_code})

        return {
            "id": str(uuid.uuid4()),
            "order": order,
            "name": name,
            "protocol": "http",
            "method": method,
            "url": url,
            "headers": headers,
            "body": body,
            "body_type": body_type,
            "params": {},
            "assertions": assertions,
            "think_time_ms": 0,
            "extractors": [],
        }
