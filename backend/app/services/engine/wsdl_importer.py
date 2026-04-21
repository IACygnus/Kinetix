# backend/app/services/engine/wsdl_importer.py
"""
WSDL Importer — Convierte archivos SOAP/WSDL XML al Script Model interno.

Soporta WSDL 1.1 con bindings SOAP 1.1 y SOAP 1.2.
Extrae operaciones, endpoints, SOAPAction y genera envelopes de plantilla
listos para personalizar con parametros reales.

Uso:
    importer = WSDLImporter()
    script_model, stats = importer.import_wsdl(wsdl_content)
"""
import uuid
from typing import Dict, Any, List, Optional, Tuple

from lxml import etree


# ── Namespaces ────────────────────────────────────────────────────────────────
NS_WSDL = "http://schemas.xmlsoap.org/wsdl/"
NS_SOAP11 = "http://schemas.xmlsoap.org/wsdl/soap/"
NS_SOAP12 = "http://schemas.xmlsoap.org/wsdl/soap12/"

NSMAP = {
    "wsdl": NS_WSDL,
    "soap": NS_SOAP11,
    "soap12": NS_SOAP12,
}

# SOAP envelope template (1.1)
SOAP_ENVELOPE_TEMPLATE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:tns="{target_namespace}">\n'
    "  <soap:Header/>\n"
    "  <soap:Body>\n"
    "    <tns:{operation_name}>\n"
    "      <!-- Add parameters here -->\n"
    "    </tns:{operation_name}>\n"
    "  </soap:Body>\n"
    "</soap:Envelope>"
)


class WSDLImporter:
    """
    Convierte un archivo WSDL al Script Model JSON interno de SQA Kinetix Pro.

    Uso:
        importer = WSDLImporter()
        script_model, stats = importer.import_wsdl(wsdl_content)
    """

    def import_wsdl(self, content: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Importar contenido WSDL y convertirlo al Script Model.

        Args:
            content: String XML del archivo WSDL

        Returns:
            tuple de (script_model, stats)
            stats: {
                "total_operations": N,
                "imported": M,
                "services_found": K,
                "bindings_found": J,
            }
        """
        try:
            root = etree.fromstring(content.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ValueError(f"El archivo WSDL no es XML valido: {e}")

        # Validate root element is a WSDL definitions
        root_tag = etree.QName(root.tag)
        if root_tag.localname != "definitions" or root_tag.namespace != NS_WSDL:
            raise ValueError(
                "Formato WSDL invalido: el elemento raiz debe ser "
                "<wsdl:definitions>"
            )

        target_namespace = root.get("targetNamespace", "")

        # ── Collect service endpoints ─────────────────────────────────────
        service_endpoints = self._extract_service_endpoints(root)

        # ── Collect SOAPAction per operation from bindings ─────────────────
        binding_actions = self._extract_binding_actions(root)

        # ── Collect operations from portTypes ─────────────────────────────
        operations = self._extract_operations(root)

        # ── Pick the best endpoint URL ────────────────────────────────────
        endpoint_url = ""
        if service_endpoints:
            endpoint_url = list(service_endpoints.values())[0]

        # ── Stats counters ────────────────────────────────────────────────
        services = root.findall("wsdl:service", NSMAP)
        bindings = root.findall("wsdl:binding", NSMAP)

        stats: Dict[str, int] = {
            "total_operations": len(operations),
            "imported": 0,
            "services_found": len(services),
            "bindings_found": len(bindings),
        }

        # ── Build requests ────────────────────────────────────────────────
        requests: List[Dict[str, Any]] = []

        for idx, op_name in enumerate(operations):
            soap_action = binding_actions.get(op_name, "")
            url = endpoint_url or "https://example.com/soap"

            body = SOAP_ENVELOPE_TEMPLATE.format(
                target_namespace=target_namespace,
                operation_name=op_name,
            )

            headers: Dict[str, str] = {
                "Content-Type": "text/xml; charset=utf-8",
            }
            if soap_action:
                headers["SOAPAction"] = soap_action

            request_entry: Dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "order": idx,
                "name": op_name,
                "method": "POST",
                "url": url,
                "protocol": "http",
                "headers": headers,
                "body": body,
                "body_type": "xml",
                "params": {},
                "think_time_ms": 0,
                "assertions": [{"type": "status_code", "value": "200"}],
                "extractors": [],
            }

            requests.append(request_entry)
            stats["imported"] += 1

        script_model: Dict[str, Any] = {
            "requests": requests,
            "variables": [],
            "data_files": [],
            "protocol": "http",
        }

        return script_model, stats

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_service_endpoints(self, root: etree._Element) -> Dict[str, str]:
        """
        Extraer URLs de endpoint desde <service><port><soap:address location="..."/>.

        Returns:
            Dict mapping port_name -> endpoint_url
        """
        endpoints: Dict[str, str] = {}

        for service in root.findall("wsdl:service", NSMAP):
            for port in service.findall("wsdl:port", NSMAP):
                port_name = port.get("name", "")

                # Try SOAP 1.1 address
                address = port.find("soap:address", NSMAP)
                # Fallback to SOAP 1.2 address
                if address is None:
                    address = port.find("soap12:address", NSMAP)

                if address is not None:
                    location = address.get("location", "")
                    if location:
                        endpoints[port_name] = location

        return endpoints

    def _extract_binding_actions(self, root: etree._Element) -> Dict[str, str]:
        """
        Extraer SOAPAction de cada operacion en los bindings.

        Returns:
            Dict mapping operation_name -> soapAction value
        """
        actions: Dict[str, str] = {}

        for binding in root.findall("wsdl:binding", NSMAP):
            for operation in binding.findall("wsdl:operation", NSMAP):
                op_name = operation.get("name", "")
                if not op_name:
                    continue

                # Try SOAP 1.1 <soap:operation soapAction="..."/>
                soap_op = operation.find("soap:operation", NSMAP)
                # Fallback to SOAP 1.2
                if soap_op is None:
                    soap_op = operation.find("soap12:operation", NSMAP)

                if soap_op is not None:
                    soap_action = soap_op.get("soapAction", "")
                    if soap_action:
                        actions[op_name] = soap_action

        return actions

    def _extract_operations(self, root: etree._Element) -> List[str]:
        """
        Extraer nombres de operaciones desde <portType><operation name="...">.

        Returns:
            Lista ordenada de nombres de operacion (sin duplicados).
        """
        seen: set = set()
        operations: List[str] = []

        for port_type in root.findall("wsdl:portType", NSMAP):
            for operation in port_type.findall("wsdl:operation", NSMAP):
                op_name = operation.get("name", "")
                if op_name and op_name not in seen:
                    seen.add(op_name)
                    operations.append(op_name)

        return operations
