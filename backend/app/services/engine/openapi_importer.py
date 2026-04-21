# backend/app/services/engine/openapi_importer.py
"""
OpenAPI/Swagger Importer — Convierte specs OpenAPI 3.x y Swagger 2.0
al Script Model JSON interno de SQA Kinetix Pro.

Soporta specs en formato JSON o YAML. La dependencia PyYAML es opcional:
si no esta instalada, solo se aceptan specs en formato JSON.

Funcionalidades:
- Deteccion automatica de version (OpenAPI 3.x vs Swagger 2.0)
- Construccion de base URL desde servers[] o host+basePath+schemes
- Conversion de path params {param} a ${param}
- Generacion de body de ejemplo a partir del schema JSON
- Extraccion de variables desde path y query parameters
- Assertions automaticas basadas en codigos de respuesta 2xx
"""
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


# Tipos de datos JSON Schema y sus valores de ejemplo
_SCHEMA_DEFAULTS = {
    "string": "string",
    "integer": 0,
    "number": 0.0,
    "boolean": True,
    "array": [],
    "object": {},
}


class OpenAPIImporter:
    """
    Convierte una spec OpenAPI/Swagger al Script Model JSON interno.

    Uso:
        importer = OpenAPIImporter()
        script_model, stats = importer.import_spec(spec_content)
    """

    def import_spec(self, content: str) -> Tuple[dict, dict]:
        """
        Importar contenido OpenAPI/Swagger y convertirlo al Script Model.

        Args:
            content: String JSON o YAML de la spec OpenAPI/Swagger

        Returns:
            tuple de (script_model, stats)
            stats: {"total_paths": N, "total_operations": M, "imported": K}

        Raises:
            ValueError: Si el contenido no es valido o el formato no es soportado
        """
        spec = self._parse_content(content)
        version = self._detect_version(spec)

        if version == "3.x":
            base_url = self._get_base_url_v3(spec)
        else:
            base_url = self._get_base_url_v2(spec)

        paths = spec.get("paths", {})
        requests: List[Dict[str, Any]] = []
        variables_map: Dict[str, str] = {}
        total_operations = 0
        imported = 0

        http_methods = {"get", "post", "put", "delete", "patch", "head", "options"}

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Path-level parameters apply to all operations in this path
            path_level_params = path_item.get("parameters", [])

            for method in http_methods:
                operation = path_item.get(method)
                if operation is None or not isinstance(operation, dict):
                    continue

                total_operations += 1

                # Merge path-level and operation-level parameters
                op_params = operation.get("parameters", [])
                merged_params = self._merge_parameters(path_level_params, op_params)

                # Build request
                script_req = self._build_request(
                    spec=spec,
                    version=version,
                    base_url=base_url,
                    path=path,
                    method=method.upper(),
                    operation=operation,
                    parameters=merged_params,
                    order=len(requests),
                )
                if script_req:
                    requests.append(script_req)
                    imported += 1

                # Collect variables from parameters
                for param in merged_params:
                    if not isinstance(param, dict):
                        continue
                    param_in = param.get("in", "")
                    param_name = param.get("name", "")
                    if param_in in ("path", "query") and param_name:
                        variables_map[param_name] = ""

        # Build variables list
        variables = [
            {"name": name, "value": value, "type": "imported", "source_hint": "OpenAPI: parameter", "source": "openapi"}
            for name, value in sorted(variables_map.items())
        ]

        script_model = {
            "requests": requests,
            "variables": variables,
            "data_files": [],
            "protocol": "http",
        }

        stats = {
            "total_paths": len(paths),
            "total_operations": total_operations,
            "imported": imported,
        }

        return script_model, stats

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_content(self, content: str) -> dict:
        """Parsear contenido como JSON o YAML."""
        # Intentar JSON primero
        try:
            spec = json.loads(content)
            if isinstance(spec, dict):
                return spec
        except (json.JSONDecodeError, TypeError):
            pass

        # Intentar YAML
        if yaml is not None:
            try:
                spec = yaml.safe_load(content)
                if isinstance(spec, dict):
                    return spec
            except yaml.YAMLError:
                pass
            raise ValueError(
                "El contenido no es una spec OpenAPI/Swagger valida (JSON ni YAML)"
            )

        raise ValueError(
            "El contenido no es JSON valido y PyYAML no esta instalado "
            "para parsear YAML. Instale PyYAML: pip install pyyaml"
        )

    def _detect_version(self, spec: dict) -> str:
        """Detectar si es OpenAPI 3.x o Swagger 2.0."""
        if "openapi" in spec:
            version_str = str(spec["openapi"])
            if version_str.startswith("3."):
                return "3.x"
            raise ValueError(f"Version OpenAPI no soportada: {version_str}")

        if "swagger" in spec:
            version_str = str(spec["swagger"])
            if version_str.startswith("2."):
                return "2.0"
            raise ValueError(f"Version Swagger no soportada: {version_str}")

        raise ValueError(
            "No se pudo detectar la version: falta 'openapi' o 'swagger' en la spec"
        )

    # ------------------------------------------------------------------
    # Base URL resolution
    # ------------------------------------------------------------------

    def _get_base_url_v3(self, spec: dict) -> str:
        """Extraer base URL de OpenAPI 3.x servers[0].url."""
        servers = spec.get("servers", [])
        if servers and isinstance(servers, list) and isinstance(servers[0], dict):
            url = servers[0].get("url", "")
            if url:
                return url.rstrip("/")
        return ""

    def _get_base_url_v2(self, spec: dict) -> str:
        """Extraer base URL de Swagger 2.0 host + basePath + schemes."""
        host = spec.get("host", "")
        if not host:
            return ""

        base_path = spec.get("basePath", "").rstrip("/")
        schemes = spec.get("schemes", ["https"])
        scheme = schemes[0] if schemes else "https"

        return f"{scheme}://{host}{base_path}"

    # ------------------------------------------------------------------
    # Request building
    # ------------------------------------------------------------------

    def _build_request(
        self,
        spec: dict,
        version: str,
        base_url: str,
        path: str,
        method: str,
        operation: dict,
        parameters: List[dict],
        order: int,
    ) -> Optional[Dict[str, Any]]:
        """Construir un request del Script Model desde una operacion OpenAPI."""
        # Convertir path params: {param} -> ${param}
        converted_path = re.sub(r'\{([^}]+)\}', r'${\1}', path)
        url = f"{base_url}{converted_path}"

        # Nombre: operationId o METHOD /path
        operation_id = operation.get("operationId", "")
        name = operation_id if operation_id else f"{method} {path}"

        # Separar parametros por ubicacion
        headers: Dict[str, str] = {}
        query_params: Dict[str, str] = {}

        for param in parameters:
            if not isinstance(param, dict):
                continue
            param_in = param.get("in", "")
            param_name = param.get("name", "")
            if not param_name:
                continue

            if param_in == "header":
                default = self._get_param_default(param, version)
                headers[param_name] = default
            elif param_in == "query":
                default = self._get_param_default(param, version)
                query_params[param_name] = default

        # Body
        body = ""
        body_type = "raw"
        if version == "3.x":
            body, body_type = self._extract_body_v3(spec, operation)
        else:
            body, body_type = self._extract_body_v2(spec, operation, parameters)

        # Assertion: primer codigo de respuesta 2xx
        assertions = self._build_assertions(operation)

        # Protocol
        protocol = "http"
        if url.startswith("https"):
            protocol = "https"

        return {
            "id": str(uuid.uuid4()),
            "order": order,
            "name": name,
            "protocol": protocol,
            "method": method,
            "url": url,
            "headers": headers,
            "body": body,
            "body_type": body_type,
            "params": query_params,
            "assertions": assertions,
            "think_time_ms": 0,
            "extractors": [],
        }

    # ------------------------------------------------------------------
    # Parameter helpers
    # ------------------------------------------------------------------

    def _merge_parameters(
        self, path_params: List, op_params: List
    ) -> List[dict]:
        """
        Combinar parametros de path-level y operation-level.
        Los de operation tienen prioridad (override por name+in).
        """
        merged: Dict[str, dict] = {}
        for param in (path_params or []):
            if isinstance(param, dict):
                key = f"{param.get('in', '')}:{param.get('name', '')}"
                merged[key] = param
        for param in (op_params or []):
            if isinstance(param, dict):
                key = f"{param.get('in', '')}:{param.get('name', '')}"
                merged[key] = param
        return list(merged.values())

    def _get_param_default(self, param: dict, version: str) -> str:
        """Obtener valor por defecto de un parametro."""
        # OpenAPI 3.x: schema.default / schema.example
        if version == "3.x":
            schema = param.get("schema", {})
            if isinstance(schema, dict):
                if "default" in schema:
                    return str(schema["default"])
                if "example" in schema:
                    return str(schema["example"])
        else:
            # Swagger 2.0: default directamente en el param
            if "default" in param:
                return str(param["default"])

        if "example" in param:
            return str(param["example"])

        return ""

    # ------------------------------------------------------------------
    # Body extraction
    # ------------------------------------------------------------------

    def _extract_body_v3(
        self, spec: dict, operation: dict
    ) -> Tuple[str, str]:
        """Extraer body de una operacion OpenAPI 3.x."""
        request_body = operation.get("requestBody", {})
        if not isinstance(request_body, dict):
            return "", "raw"

        # Resolver $ref en requestBody
        request_body = self._resolve_ref(spec, request_body)

        content = request_body.get("content", {})
        if not isinstance(content, dict):
            return "", "raw"

        # Preferir application/json
        if "application/json" in content:
            media = content["application/json"]
            schema = media.get("schema", {})
            schema = self._resolve_ref(spec, schema)
            sample = self._generate_sample(spec, schema)
            try:
                body_str = json.dumps(sample, indent=2, ensure_ascii=False)
            except (TypeError, ValueError):
                body_str = "{}"
            return body_str, "json"

        # application/x-www-form-urlencoded
        if "application/x-www-form-urlencoded" in content:
            media = content["application/x-www-form-urlencoded"]
            schema = media.get("schema", {})
            schema = self._resolve_ref(spec, schema)
            sample = self._generate_sample(spec, schema)
            try:
                body_str = json.dumps(sample, indent=2, ensure_ascii=False)
            except (TypeError, ValueError):
                body_str = "{}"
            return body_str, "form"

        # application/xml
        if "application/xml" in content:
            return "", "xml"

        return "", "raw"

    def _extract_body_v2(
        self, spec: dict, operation: dict, parameters: List[dict]
    ) -> Tuple[str, str]:
        """Extraer body de una operacion Swagger 2.0."""
        for param in parameters:
            if not isinstance(param, dict):
                continue
            if param.get("in") != "body":
                continue

            schema = param.get("schema", {})
            schema = self._resolve_ref(spec, schema)
            sample = self._generate_sample(spec, schema)
            try:
                body_str = json.dumps(sample, indent=2, ensure_ascii=False)
            except (TypeError, ValueError):
                body_str = "{}"
            return body_str, "json"

        # Check for formData parameters
        form_params = [
            p for p in parameters
            if isinstance(p, dict) and p.get("in") == "formData"
        ]
        if form_params:
            sample = {}
            for p in form_params:
                name = p.get("name", "")
                p_type = p.get("type", "string")
                sample[name] = _SCHEMA_DEFAULTS.get(p_type, "string")
            try:
                body_str = json.dumps(sample, indent=2, ensure_ascii=False)
            except (TypeError, ValueError):
                body_str = "{}"
            return body_str, "form"

        return "", "raw"

    # ------------------------------------------------------------------
    # Schema sample generation
    # ------------------------------------------------------------------

    def _generate_sample(self, spec: dict, schema: dict, depth: int = 0) -> Any:
        """
        Generar un valor de ejemplo a partir de un JSON Schema.
        Limita la profundidad de recursion para evitar loops infinitos en $ref circulares.
        """
        if depth > 5 or not isinstance(schema, dict):
            return None

        schema = self._resolve_ref(spec, schema)

        # Si tiene example, usarlo directamente
        if "example" in schema:
            return schema["example"]

        schema_type = schema.get("type", "")

        # Enum: usar el primer valor
        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]

        if schema_type == "object" or "properties" in schema:
            result = {}
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    continue
                prop_schema = self._resolve_ref(spec, prop_schema)
                result[prop_name] = self._generate_sample(
                    spec, prop_schema, depth + 1
                )
            return result

        if schema_type == "array":
            items = schema.get("items", {})
            if isinstance(items, dict):
                items = self._resolve_ref(spec, items)
                item_sample = self._generate_sample(spec, items, depth + 1)
                return [item_sample] if item_sample is not None else []
            return []

        if schema_type == "string":
            fmt = schema.get("format", "")
            if fmt == "date":
                return "2024-01-01"
            if fmt == "date-time":
                return "2024-01-01T00:00:00Z"
            if fmt == "email":
                return "user@example.com"
            if fmt == "uuid":
                return "00000000-0000-0000-0000-000000000000"
            if fmt == "uri" or fmt == "url":
                return "https://example.com"
            if fmt == "password":
                return "********"
            return "string"

        if schema_type == "integer":
            return schema.get("minimum", 0)

        if schema_type == "number":
            return schema.get("minimum", 0.0)

        if schema_type == "boolean":
            return True

        return _SCHEMA_DEFAULTS.get(schema_type)

    # ------------------------------------------------------------------
    # $ref resolution
    # ------------------------------------------------------------------

    def _resolve_ref(self, spec: dict, obj: dict) -> dict:
        """Resolver una referencia $ref dentro de la spec (solo refs internas)."""
        if not isinstance(obj, dict) or "$ref" not in obj:
            return obj

        ref_path = obj["$ref"]
        if not ref_path.startswith("#/"):
            return obj

        parts = ref_path[2:].split("/")
        resolved = spec
        for part in parts:
            # Decodificar escape JSON Pointer (/ -> ~1, ~ -> ~0)
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(resolved, dict):
                resolved = resolved.get(part, {})
            else:
                return obj

        return resolved if isinstance(resolved, dict) else obj

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def _build_assertions(self, operation: dict) -> List[Dict[str, str]]:
        """Construir assertion basada en el primer codigo de respuesta 2xx."""
        responses = operation.get("responses", {})
        if not isinstance(responses, dict):
            return [{"type": "status_code", "value": "200"}]

        # Buscar el primer codigo 2xx
        for code in sorted(responses.keys()):
            code_str = str(code)
            if code_str.startswith("2"):
                return [{"type": "status_code", "value": code_str}]

        # Si no hay 2xx definido, asumir 200
        return [{"type": "status_code", "value": "200"}]
