# backend/app/services/engine/protocols/http_handler.py
"""
HTTP/S Protocol Handler para el motor de SQA Kinetix Pro.

Usa httpx con soporte async, HTTP/1.1 y manejo de
cookies por sesion (necesario para flujos con autenticacion).
"""
import httpx
import time
import re
from typing import Dict, Optional
from .base import ProtocolHandler, RequestConfig, RequestResult


class HTTPHandler(ProtocolHandler):
    """
    Maneja requests HTTP/S para un VirtualUser.

    Cada VirtualUser tiene su propio HTTPHandler con su propio
    cliente httpx, lo que garantiza aislamiento de cookies y sesion.
    """

    def __init__(self, timeout_sec: float = 30.0, follow_redirects: bool = True,
                 verify_ssl: bool = True):
        self._timeout = httpx.Timeout(timeout_sec)
        self._follow_redirects = follow_redirects
        self._verify_ssl = verify_ssl
        # El cliente se crea una vez por VirtualUser y se reutiliza
        # para que las cookies persistan entre requests del mismo flujo
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=self._follow_redirects,
                verify=self._verify_ssl,
                http2=False  # HTTP/1.1 por defecto para maxima compatibilidad
            )
        return self._client

    @property
    def protocol_name(self) -> str:
        return "http"

    async def execute(self, request: RequestConfig, thread_name: str, all_threads: int) -> RequestResult:
        """Ejecutar request HTTP y retornar resultado. Nunca lanza excepcion."""
        client = await self._get_client()

        timestamp_ms = int(time.time() * 1000)
        connect_start = time.monotonic()

        try:
            # Preparar kwargs segun body_type
            kwargs = {
                "method": request.method.upper(),
                "url": request.url,
                "headers": request.headers,
                "params": request.params if request.params else None,
            }

            if request.body and request.method.upper() not in ("GET", "HEAD", "OPTIONS"):
                if request.body_type == "json":
                    kwargs["content"] = request.body.encode("utf-8")
                    if "Content-Type" not in {k.title() for k in request.headers}:
                        kwargs["headers"] = {**request.headers, "Content-Type": "application/json"}
                elif request.body_type == "xml":
                    kwargs["content"] = request.body.encode("utf-8")
                    if "Content-Type" not in {k.title() for k in request.headers}:
                        kwargs["headers"] = {**request.headers, "Content-Type": "application/xml"}
                elif request.body_type == "form":
                    # body viene como string "key=value&key2=value2"
                    from urllib.parse import parse_qs
                    form_data = dict(parse_qs(request.body, keep_blank_values=True))
                    kwargs["data"] = {k: v[0] for k, v in form_data.items()}
                else:
                    kwargs["content"] = request.body.encode("utf-8") if isinstance(request.body, str) else request.body

            connect_time_start = time.monotonic()
            response = await client.request(**kwargs)
            latency_ms = int((time.monotonic() - connect_time_start) * 1000)
            elapsed_ms = int((time.monotonic() - connect_start) * 1000)

            # Leer body de respuesta
            response_body = ""
            try:
                response_body = response.text
            except Exception:
                response_body = str(response.content[:10000])

            # Evaluar assertions
            success = True
            failure_message = ""
            for assertion in request.assertions:
                if assertion.get("type") == "status_code":
                    expected = str(assertion.get("value", "200"))
                    if str(response.status_code) != expected:
                        success = False
                        failure_message = f"Expected status {expected}, got {response.status_code}"
                        break
                elif assertion.get("type") == "response_contains":
                    if assertion.get("value", "") not in response_body:
                        success = False
                        failure_message = f"Response does not contain: {assertion.get('value')}"
                        break

            # Extraer variables con regex
            extracted_variables: Dict[str, str] = {}
            for extractor in request.extractors:
                var_name = extractor.get("variable_name", "")
                regex = extractor.get("regex", "")
                extract_from = extractor.get("extract_from", "body")  # body | header
                match_no = extractor.get("match_no", 1)
                default = extractor.get("default_value", "")

                if not var_name or not regex:
                    continue

                source_text = ""
                if extract_from == "body":
                    source_text = response_body
                elif extract_from == "header":
                    header_name = extractor.get("header_name", "")
                    source_text = response.headers.get(header_name, "")

                try:
                    matches = re.findall(regex, source_text)
                    if matches:
                        idx = min(match_no - 1, len(matches) - 1)
                        val = matches[idx]
                        extracted_variables[var_name] = val if isinstance(val, str) else val[0]
                    else:
                        extracted_variables[var_name] = default
                except re.error:
                    extracted_variables[var_name] = default

            # Calcular bytes enviados (aproximado)
            body_bytes = len(request.body.encode("utf-8")) if request.body else 0
            header_bytes = sum(len(k) + len(v) + 4 for k, v in request.headers.items())
            sent_bytes = body_bytes + header_bytes + len(request.url) + 20

            return RequestResult(
                timestamp_ms=timestamp_ms,
                elapsed_ms=elapsed_ms,
                label=request.name,
                response_code=str(response.status_code),
                response_message=response.reason_phrase or "OK",
                thread_name=thread_name,
                success=success,
                failure_message=failure_message,
                bytes_received=len(response.content),
                sent_bytes=sent_bytes,
                all_threads=all_threads,
                url=str(response.url),
                latency_ms=latency_ms,
                connect_ms=max(0, latency_ms - 5),
                response_body=response_body,
                response_headers=dict(response.headers),
                extracted_variables=extracted_variables,
            )

        except httpx.TimeoutException as e:
            elapsed_ms = int((time.monotonic() - connect_start) * 1000)
            return RequestResult(
                timestamp_ms=timestamp_ms,
                elapsed_ms=elapsed_ms,
                label=request.name,
                response_code="Timeout",
                response_message=f"Connection timed out: {str(e)[:100]}",
                thread_name=thread_name,
                success=False,
                failure_message=f"Timeout after {elapsed_ms}ms",
                all_threads=all_threads,
                url=request.url,
            )

        except httpx.ConnectError as e:
            elapsed_ms = int((time.monotonic() - connect_start) * 1000)
            return RequestResult(
                timestamp_ms=timestamp_ms,
                elapsed_ms=elapsed_ms,
                label=request.name,
                response_code="Connection refused",
                response_message=str(e)[:200],
                thread_name=thread_name,
                success=False,
                failure_message=f"Connection error: {str(e)[:200]}",
                all_threads=all_threads,
                url=request.url,
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - connect_start) * 1000)
            return RequestResult(
                timestamp_ms=timestamp_ms,
                elapsed_ms=elapsed_ms,
                label=request.name,
                response_code="Error",
                response_message=str(e)[:200],
                thread_name=thread_name,
                success=False,
                failure_message=str(e)[:500],
                all_threads=all_threads,
                url=request.url,
            )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
