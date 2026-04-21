# backend/app/services/engine/smoke_test.py
"""
Smoke Test Engine — Ejecuta el script con 1 VU y 1 iteración.

Valida que el flujo completo funcione antes de un load test real.
Escribe el resultado a un archivo JTL y retorna un resumen detallado
con el estado de cada request y las variables extraídas.
"""
import logging
import time
from typing import Dict, Any, Optional, List

from .virtual_user import VirtualUser
from .jtl_writer import JTLWriter
from .metrics_collector import MetricsCollector
from .protocols.base import RequestResult

logger = logging.getLogger(__name__)


def evaluate_assertions(assertions: list, status_code: int, body: str, duration_ms: int = 0) -> tuple:
    """
    Evaluate assertions defined on a request.
    Returns (all_passed, list_of_failure_messages)
    """
    if not assertions:
        # No assertions defined -> pass if status < 400
        return status_code < 400, []

    failures = []
    for assertion in assertions:
        atype = assertion.get("type", "")
        avalue = str(assertion.get("value", ""))

        if atype == "status_code":
            expected = int(avalue) if avalue.isdigit() else 200
            if status_code != expected:
                failures.append(f"Status code esperado {expected}, recibido {status_code}")

        elif atype == "status_code_range":
            parts = avalue.split("-")
            if len(parts) == 2:
                try:
                    lo, hi = int(parts[0]), int(parts[1])
                    if not (lo <= status_code <= hi):
                        failures.append(f"Status code {status_code} fuera del rango {lo}-{hi}")
                except ValueError:
                    pass

        elif atype == "body_contains":
            if avalue and avalue not in body:
                failures.append(f'Body no contiene: "{avalue}"')

        elif atype == "body_not_contains":
            if avalue and avalue in body:
                failures.append(f'Body contiene texto no esperado: "{avalue}"')

        elif atype == "body_json_path":
            try:
                import json
                data = json.loads(body)
                path_parts = avalue.lstrip("$.").split(".")
                current = data
                for part in path_parts:
                    if "[" in part:
                        key, idx_str = part.split("[")
                        idx_val = int(idx_str.rstrip("]"))
                        current = current[key][idx_val]
                    else:
                        current = current[part]
            except Exception as e:
                failures.append(f'JSON path "{avalue}" no encontrado: {str(e)}')

        elif atype == "response_time":
            try:
                max_ms = int(avalue)
                if duration_ms > max_ms:
                    failures.append(f"Tiempo de respuesta {duration_ms}ms excede maximo {max_ms}ms")
            except ValueError:
                pass

    return len(failures) == 0, failures


class SmokeTestResult:
    """Resultado detallado de un smoke test."""

    def __init__(self):
        self.success: bool = False
        self.total_requests: int = 0
        self.passed_requests: int = 0
        self.failed_requests: int = 0
        self.jtl_file_path: str = ""
        self.duration_ms: int = 0
        self.request_details: list = []
        self.unresolved_variables: list = []
        self.error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "total_requests": self.total_requests,
            "passed_requests": self.passed_requests,
            "failed_requests": self.failed_requests,
            "jtl_file_path": self.jtl_file_path,
            "duration_ms": self.duration_ms,
            "request_details": self.request_details,
            "unresolved_variables": self.unresolved_variables,
            "error_message": self.error_message,
        }


async def run_smoke_test(
    script_model: Dict[str, Any],
    execution_id: int,
    client_name: str = "cliente",
    project_name: str = "proyecto",
    datafile_row: Optional[Dict[str, str]] = None,
    timeout_sec: float = 30.0,
) -> SmokeTestResult:
    """
    Ejecutar smoke test: 1 VU, 1 iteración completa del script.

    Args:
        script_model: El JSON interno del ScriptDesign
        execution_id: ID del PerformanceExecution en DB
        client_name: Para naming del archivo JTL
        project_name: Para naming del archivo JTL
        datafile_row: Fila de data file para este VU (opcional)
        timeout_sec: Timeout por request

    Returns:
        SmokeTestResult con detalle de cada request
    """
    result = SmokeTestResult()

    start_time = time.monotonic()

    # Generar ruta del JTL
    jtl_path = JTLWriter.build_filepath(client_name, project_name, execution_id)
    result.jtl_file_path = jtl_path

    try:
        async with JTLWriter(jtl_path) as jtl_writer:
            vu = VirtualUser(
                vu_id=1,
                execution_id=execution_id,
                script_model=script_model,
                jtl_writer=jtl_writer,
                datafile_row=datafile_row,
                timeout_sec=timeout_sec,
            )

            request_results = await vu.run(iterations=1, all_threads=1)

        end_time = time.monotonic()
        result.duration_ms = int((end_time - start_time) * 1000)

        # Construir detalle por request (formato JMeter-compatible)
        requests_defs = script_model.get("requests", [])
        for i, req_result in enumerate(request_results):
            status_str = req_result.response_code or ""
            status_int = None
            try:
                status_int = int(status_str)
            except (ValueError, TypeError):
                pass

            # Obtener definición del request para method y headers enviados
            req_def = requests_defs[i] if i < len(requests_defs) else {}
            method = req_def.get("method", "GET")
            # Show RESOLVED values (not raw ${var} placeholders) using the VU's variable engine
            sent_headers_dict = vu._vars.substitute_dict(req_def.get("headers", {}))
            body_sent = vu._vars.substitute(req_def.get("body", ""))

            # Cabeceras de respuesta
            resp_headers = req_result.response_headers or {}
            resp_headers_raw = ""
            if resp_headers:
                status_line = f"HTTP/1.1 {status_str} {req_result.response_message}"
                header_lines = "\n".join(f"{k}: {v}" for k, v in resp_headers.items())
                resp_headers_raw = f"{status_line}\n{header_lines}"

            # Evaluate assertions defined in the request
            assertions_def = req_def.get("assertions", [])
            assertion_passed, assertion_failures = evaluate_assertions(
                assertions_def,
                status_int or 0,
                req_result.response_body or "",
                req_result.elapsed_ms,
            )
            # Final success: engine success AND assertion success
            final_success = req_result.success and assertion_passed
            final_failure = req_result.failure_message or ""
            if assertion_failures:
                af_text = "; ".join(assertion_failures)
                final_failure = f"{final_failure}; {af_text}" if final_failure else af_text

            detail = {
                "name": req_result.label,
                "resolved_url": req_result.url,
                "method": method,
                "status_code": status_str,
                "duration_ms": req_result.elapsed_ms,
                "elapsed_ms": req_result.elapsed_ms,
                "success": final_success,
                "failure_message": final_failure,
                "bytes": req_result.bytes_received,
                # Petición enviada
                "petition_text": f"{method} {req_result.url}" + (f"\n\n{body_sent}" if body_sent else ""),
                "sent_headers": "\n".join(f"{k}: {v}" for k, v in sent_headers_dict.items()),
                "sent_body": body_sent or "",
                # Respuesta recibida
                "response_body": req_result.response_body or "",
                "response_headers": resp_headers,
                "response_headers_raw": resp_headers_raw,
                "error": final_failure if not final_success else None,
                "assertion_failures": assertion_failures,
            }
            result.request_details.append(detail)

        result.total_requests = len(result.request_details)
        result.passed_requests = sum(1 for d in result.request_details if d["success"])
        result.failed_requests = sum(1 for d in result.request_details if not d["success"])
        result.unresolved_variables = vu.unresolved_variables
        result.success = result.failed_requests == 0 and result.total_requests > 0

        logger.info(
            f"Smoke test {execution_id}: {result.passed_requests}/{result.total_requests} passed, "
            f"{result.duration_ms}ms total"
        )

    except Exception as e:
        logger.error(f"Smoke test {execution_id} failed with exception: {e}")
        result.success = False
        result.error_message = str(e)

    return result
