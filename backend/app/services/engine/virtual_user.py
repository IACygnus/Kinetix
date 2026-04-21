# backend/app/services/engine/virtual_user.py
"""
VirtualUser — Coroutine que simula un usuario ejecutando el script completo.

Cada VirtualUser:
1. Tiene su propio HTTPHandler (con jar de cookies aislado)
2. Tiene su propio VariableEngine (contexto de variables)
3. Ejecuta los requests del ScriptDesign en orden
4. Aplica extractores después de cada response
5. Sustituye variables antes de cada request
6. Escribe métricas al JTLWriter después de cada request
7. Aplica think_time entre requests

REGLA CRÍTICA: Nunca propaga excepciones. Todos los errores se capturan
y se convierten en RequestResult con success=False.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from .protocols.base import RequestConfig, RequestResult
from .protocols.http_handler import HTTPHandler
from .jtl_writer import JTLWriter
from .variable_engine import VariableEngine

logger = logging.getLogger(__name__)


class VirtualUser:
    """
    Simula un único usuario virtual ejecutando el script.

    Se instancia por el SteppingController (Sprint 3).
    En Sprint 2 se usa directamente para el Smoke Test (1 VU).
    """

    def __init__(
        self,
        vu_id: int,
        execution_id: int,
        script_model: Dict[str, Any],
        jtl_writer: JTLWriter,
        datafile_row: Optional[Dict[str, str]] = None,
        timeout_sec: float = 30.0,
    ):
        self.vu_id = vu_id
        self.execution_id = execution_id
        self.script_model = script_model
        self.jtl_writer = jtl_writer
        self.datafile_row = datafile_row
        self.thread_name = f"Thread-1-VU-{vu_id}"

        self._handler = HTTPHandler(timeout_sec=timeout_sec, follow_redirects=True)
        self._vars = VariableEngine(thread_name=self.thread_name)
        self._results: List[RequestResult] = []
        self._stopped = False

    async def run(self, iterations: int = 1, all_threads: int = 1) -> List[RequestResult]:
        """
        Ejecutar el script por N iteraciones.

        Args:
            iterations: Número de veces que se repite el flujo (1 para smoke test)
            all_threads: Total de VUs activos (para columna allThreads del JTL)

        Returns:
            Lista de RequestResult de todos los requests ejecutados
        """
        # Inicializar variables con el contexto del script
        self._vars.initialize(
            script_variables=self.script_model.get("variables", []),
            datafile_row=self.datafile_row,
        )

        requests = sorted(
            self.script_model.get("requests", []),
            key=lambda r: r.get("order", 0)
        )

        if not requests:
            logger.warning(f"[{self.thread_name}] Script has no requests — nothing to execute")
            return []

        for iteration in range(iterations):
            if self._stopped:
                break

            logger.info(f"[{self.thread_name}] Starting iteration {iteration + 1}/{iterations}")

            for req_def in requests:
                if self._stopped:
                    break

                result = await self._execute_single_request(req_def, all_threads)
                self._results.append(result)

                # Escribir al JTL inmediatamente (tiempo real)
                await self.jtl_writer.write(result)

                # Think time después del request
                think_time_ms = req_def.get("think_time_ms", 0)
                if think_time_ms > 0 and not self._stopped:
                    await asyncio.sleep(think_time_ms / 1000.0)

        await self._handler.close()
        return self._results

    async def _execute_single_request(self, req_def: Dict[str, Any], all_threads: int) -> RequestResult:
        """
        Ejecutar un único request con sustitución de variables.

        1. Sustituir variables en URL, headers, body, params
        2. Ejecutar con HTTPHandler
        3. Aplicar extractores sobre el response
        4. Retornar RequestResult
        """
        try:
            # Sustituir variables ANTES de enviar el request
            substituted_url = self._vars.substitute(req_def.get("url", ""))
            substituted_headers = self._vars.substitute_dict(req_def.get("headers", {}))
            substituted_body = self._vars.substitute(req_def.get("body", ""))
            substituted_params = self._vars.substitute_dict(req_def.get("params", {}))

            request_config = RequestConfig(
                id=req_def.get("id", ""),
                name=req_def.get("name", "Unnamed"),
                protocol=req_def.get("protocol", "http"),
                method=req_def.get("method", "GET"),
                url=substituted_url,
                headers=substituted_headers,
                body=substituted_body if substituted_body else None,
                body_type=req_def.get("body_type", "json"),
                params=substituted_params,
                think_time_ms=0,  # Ya manejado arriba
                assertions=req_def.get("assertions", []),
                extractors=req_def.get("extractors", []),
            )

            result = await self._handler.execute(
                request=request_config,
                thread_name=self.thread_name,
                all_threads=all_threads,
            )

            # Aplicar extractores usando el VariableEngine
            # (HTTPHandler ya los aplica internamente, pero VariableEngine
            # los persiste para el PRÓXIMO request)
            if result.response_body:
                self._vars.apply_extractors(
                    extractors=req_def.get("extractors", []),
                    response_body=result.response_body,
                    response_headers=result.response_headers,
                )

            # Transferir variables extraídas por HTTPHandler al contexto del VU
            for var_name, var_value in result.extracted_variables.items():
                self._vars.set(var_name, var_value)

            return result

        except Exception as e:
            # NUNCA propagar — capturar todo como failure
            logger.error(f"[{self.thread_name}] Unexpected error in request '{req_def.get('name')}': {e}")
            return RequestResult(
                timestamp_ms=int(time.time() * 1000),
                elapsed_ms=0,
                label=req_def.get("name", "Unknown"),
                response_code="Error",
                response_message=str(e)[:200],
                thread_name=self.thread_name,
                success=False,
                failure_message=f"VirtualUser internal error: {str(e)[:500]}",
                all_threads=all_threads,
                url=req_def.get("url", ""),
            )

    def stop(self):
        """Señalizar al VU que debe detenerse después del request actual."""
        self._stopped = True
        logger.info(f"[{self.thread_name}] Stop signal received")

    @property
    def results(self) -> List[RequestResult]:
        return self._results.copy()

    @property
    def variable_snapshot(self) -> dict:
        return self._vars.snapshot()

    @property
    def unresolved_variables(self) -> list:
        return self._vars.unresolved_variables
