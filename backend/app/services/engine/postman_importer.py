# backend/app/services/engine/postman_importer.py
"""
Postman Importer — Convierte Postman Collections (v2.0/v2.1) al Script Model interno.

Soporta:
- Postman Collection v2.0 y v2.1
- Carpetas anidadas (recursivas) — se aplanan automaticamente
- Variables de coleccion ({{var}} -> ${var})
- Body types: raw (json, xml, text), formdata, urlencoded
- Headers, query params, assertions y extractors basicos
"""
import json
import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse


# Regex para convertir variables Postman {{var}} a formato interno ${var}
POSTMAN_VAR_REGEX = re.compile(r'\{\{([^}]+)\}\}')


class PostmanImporter:
    """
    Convierte un archivo Postman Collection JSON al Script Model JSON interno
    de SQA Kinetix Pro.

    Uso:
        importer = PostmanImporter()
        script_model, stats = importer.import_collection(json_content)
    """

    def import_collection(self, json_content: str) -> Tuple[dict, dict]:
        """
        Importar contenido de Postman Collection y convertirlo al Script Model.

        Args:
            json_content: String JSON de la coleccion Postman (v2.0 o v2.1)

        Returns:
            tuple de (script_model, stats)
            stats: {"total_items": N, "imported": M, "folders_flattened": K}
        """
        try:
            collection_data = json.loads(json_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"El archivo Postman no es JSON valido: {e}")

        # Detectar formato: v2.1 tiene "collection" wrapper, v2.0 tiene "info" directo
        collection = self._extract_collection(collection_data)

        if "info" not in collection:
            raise ValueError(
                "Formato Postman invalido: falta la clave 'info'. "
                "Asegurese de exportar como Collection v2.0 o v2.1."
            )

        items = collection.get("item", [])
        if not items:
            raise ValueError("La coleccion Postman no contiene items (requests)")

        # Estadisticas
        stats = {
            "total_items": 0,
            "imported": 0,
            "folders_flattened": 0,
        }

        # Aplanar carpetas recursivamente
        flat_items = self._flatten_items(items, stats)
        stats["total_items"] = len(flat_items)

        # Extraer variables de la coleccion
        variables = self._extract_variables(collection)

        # Convertir cada item a request del Script Model
        requests = []
        for i, item in enumerate(flat_items):
            script_req = self._build_request(item, order=i)
            if script_req:
                requests.append(script_req)
                stats["imported"] += 1

        # Escanear variables usadas en requests que no estan en collection.variable
        seen_var_names = {v["name"] for v in variables}
        for req in requests:
            for text in [
                req.get("url", ""),
                req.get("body", ""),
                *list((req.get("headers") or {}).values()),
            ]:
                for vname in re.findall(r'\$\{([^}]+)\}', str(text or "")):
                    if vname not in seen_var_names and not vname.startswith('$'):
                        seen_var_names.add(vname)
                        variables.append({
                            "name": vname,
                            "value": "",
                            "type": "imported",
                            "source_hint": "Detectada en requests al importar",
                            "source": "postman",
                        })

        # Detectar protocolo predominante
        protocol = self._detect_protocol(requests)

        script_model = {
            "requests": requests,
            "variables": variables,
            "data_files": [],
            "protocol": protocol,
        }

        return script_model, stats

    def _extract_collection(self, data: dict) -> dict:
        """
        Extraer el objeto coleccion independientemente del formato.

        v2.1: {"collection": {"info": ..., "item": [...]}}
        v2.0: {"info": ..., "item": [...]}
        """
        if "collection" in data:
            return data["collection"]
        return data

    def _flatten_items(self, items: List[dict], stats: dict) -> List[dict]:
        """
        Aplanar recursivamente las carpetas de Postman.

        Las carpetas en Postman tienen "item" como sub-array.
        Los requests tienen "request" como objeto.
        """
        flat = []
        for item in items:
            if "item" in item and isinstance(item["item"], list):
                # Es una carpeta — aplanar recursivamente
                stats["folders_flattened"] += 1
                flat.extend(self._flatten_items(item["item"], stats))
            elif "request" in item:
                # Es un request
                flat.append(item)
        return flat

    def _extract_variables(self, collection: dict) -> List[Dict[str, Any]]:
        """
        Extraer variables de la coleccion Postman.

        collection.variable: [{"key": "base_url", "value": "https://...", "type": "string"}]
        """
        variables = []
        for var in collection.get("variable", []):
            key = var.get("key", "")
            value = var.get("value", "")
            if key:
                variables.append({
                    "name": key,
                    "value": str(value) if value is not None else "",
                    "type": "imported",
                    "source_hint": "Postman: collection variable",
                    "source": "postman",
                })
        return variables

    def _convert_variables(self, text: str) -> str:
        """
        Convertir variables Postman {{var}} al formato interno ${var}.
        """
        if not text:
            return text
        return POSTMAN_VAR_REGEX.sub(r'${\1}', text)

    def _build_request(self, item: dict, order: int) -> Optional[Dict[str, Any]]:
        """Construir un request del Script Model desde un item de Postman."""
        req = item.get("request", {})
        if isinstance(req, str):
            # Formato simplificado: request es solo la URL
            return {
                "id": str(uuid.uuid4()),
                "order": order,
                "name": item.get("name", f"Request {order + 1}"),
                "protocol": "http",
                "method": "GET",
                "url": self._convert_variables(req),
                "headers": {},
                "body": "",
                "body_type": "raw",
                "params": {},
                "assertions": [{"type": "status_code", "value": "200"}],
                "think_time_ms": 1000,
                "extractors": [],
            }

        # Nombre del request
        name = item.get("name", f"Request {order + 1}")

        # Metodo HTTP
        method = req.get("method", "GET").upper()

        # URL — puede ser string o objeto
        url, params = self._parse_url(req.get("url", ""))

        # Headers
        headers = self._parse_headers(req.get("header", []))

        # Body
        body, body_type = self._parse_body(req.get("body", {}))

        # Protocolo
        protocol = "https" if url.startswith("https") else "http"

        # Assertion por defecto
        assertions = [{"type": "status_code", "value": "200"}]

        # Extractors basicos — detectar tokens en nombre del request
        extractors = self._detect_extractors(name, method)

        return {
            "id": str(uuid.uuid4()),
            "order": order,
            "name": name,
            "protocol": protocol,
            "method": method,
            "url": self._convert_variables(url),
            "headers": {k: self._convert_variables(v) for k, v in headers.items()},
            "body": self._convert_variables(body),
            "body_type": body_type,
            "params": {k: self._convert_variables(v) for k, v in params.items()},
            "assertions": assertions,
            "think_time_ms": 1000,
            "extractors": extractors,
        }

    def _parse_url(self, url_obj) -> Tuple[str, Dict[str, str]]:
        """
        Parsear URL de Postman. Puede ser string o objeto complejo.

        Formato objeto v2.1:
        {
            "raw": "https://{{host}}/api/v1/users?page=1",
            "protocol": "https",
            "host": ["{{host}}"],
            "path": ["api", "v1", "users"],
            "query": [{"key": "page", "value": "1"}]
        }
        """
        params = {}

        if isinstance(url_obj, str):
            # Formato simple — extraer params de la URL
            url = url_obj
            if "?" in url:
                base, qs = url.split("?", 1)
                for pair in qs.split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k] = v
            return url, params

        if isinstance(url_obj, dict):
            url = url_obj.get("raw", "")

            # Extraer query params del array
            for q in url_obj.get("query", []):
                if q.get("disabled", False):
                    continue
                key = q.get("key", "")
                value = q.get("value", "")
                if key:
                    params[key] = value if value is not None else ""

            # Si no hay "raw", reconstruir desde componentes
            if not url:
                protocol = url_obj.get("protocol", "http")
                host_parts = url_obj.get("host", [])
                host = ".".join(host_parts) if isinstance(host_parts, list) else str(host_parts)
                path_parts = url_obj.get("path", [])
                path = "/".join(path_parts) if isinstance(path_parts, list) else str(path_parts)
                port = url_obj.get("port", "")
                port_str = f":{port}" if port else ""
                url = f"{protocol}://{host}{port_str}/{path}"

            return url, params

        return str(url_obj), params

    def _parse_headers(self, headers_list: Optional[list]) -> Dict[str, str]:
        """
        Parsear array de headers de Postman.

        [{"key": "Content-Type", "value": "application/json", "disabled": false}]
        """
        if not headers_list or not isinstance(headers_list, list):
            return {}

        headers = {}
        SKIP_HEADERS = {
            'host', 'content-length', 'connection', 'accept-encoding',
            'postman-token', 'user-agent',
        }

        for h in headers_list:
            if not isinstance(h, dict):
                continue
            if h.get("disabled", False):
                continue
            key = h.get("key", "")
            value = h.get("value", "")
            if key and key.lower() not in SKIP_HEADERS:
                headers[key] = value if value is not None else ""

        return headers

    def _parse_body(self, body_obj: Optional[dict]) -> Tuple[str, str]:
        """
        Parsear body de Postman.

        Modos soportados: raw, formdata, urlencoded
        """
        if not body_obj or not isinstance(body_obj, dict):
            return "", "raw"

        mode = body_obj.get("mode", "raw")

        if mode == "raw":
            raw_text = body_obj.get("raw", "")
            # Detectar tipo de contenido desde options
            options = body_obj.get("options", {})
            raw_options = options.get("raw", {}) if isinstance(options, dict) else {}
            language = raw_options.get("language", "text") if isinstance(raw_options, dict) else "text"

            if language == "json":
                body_type = "json"
            elif language == "xml":
                body_type = "xml"
            elif language == "text":
                body_type = "raw"
            else:
                # Intentar detectar por contenido
                stripped = raw_text.strip()
                if stripped.startswith(("{", "[")):
                    body_type = "json"
                elif stripped.startswith("<"):
                    body_type = "xml"
                else:
                    body_type = "raw"

            return raw_text, body_type

        elif mode == "formdata":
            # Convertir formdata a JSON-like representation
            form_items = body_obj.get("formdata", [])
            if not isinstance(form_items, list):
                return "", "form"
            parts = []
            for item in form_items:
                if not isinstance(item, dict):
                    continue
                if item.get("disabled", False):
                    continue
                key = item.get("key", "")
                value = item.get("value", "")
                if key:
                    parts.append(f"{key}={value if value is not None else ''}")
            return "&".join(parts), "form"

        elif mode == "urlencoded":
            encoded_items = body_obj.get("urlencoded", [])
            if not isinstance(encoded_items, list):
                return "", "form"
            parts = []
            for item in encoded_items:
                if not isinstance(item, dict):
                    continue
                if item.get("disabled", False):
                    continue
                key = item.get("key", "")
                value = item.get("value", "")
                if key:
                    parts.append(f"{key}={value if value is not None else ''}")
            return "&".join(parts), "form"

        # Modos no soportados (file, graphql, etc.)
        return "", "raw"

    def _detect_extractors(self, name: str, method: str) -> List[Dict[str, Any]]:
        """
        Detectar extractors basicos segun el nombre del request.

        Si el request parece ser un login/auth, agregar extractor de token.
        """
        extractors = []
        name_lower = name.lower()

        login_keywords = ["login", "auth", "token", "signin", "sign-in", "authenticate"]
        if method == "POST" and any(kw in name_lower for kw in login_keywords):
            extractors.append({
                "variable_name": "token",
                "extract_from": "body",
                "regex": "\"token\":\"([^\"]+)\"",
                "match_no": 1,
                "default_value": "",
                "header_name": "",
            })

        return extractors

    def _detect_protocol(self, requests: List[dict]) -> str:
        """Detectar protocolo predominante entre los requests."""
        if not requests:
            return "http"

        https_count = sum(1 for r in requests if r.get("url", "").startswith("https"))
        return "https" if https_count > len(requests) / 2 else "http"
