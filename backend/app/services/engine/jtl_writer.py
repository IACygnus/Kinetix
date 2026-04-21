# backend/app/services/engine/jtl_writer.py
"""
JTL Writer — Genera archivos .jtl estandar de JMeter.

El formato JTL es un CSV con columnas especificas que JMeter puede abrir.
Se escribe de forma incremental (append) para no acumular resultados en memoria
durante ejecuciones largas.

Columnas estandar JMeter 5.x:
timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,
success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,
IdleTime,Connect
"""
import csv
import re
import asyncio
from datetime import datetime
from pathlib import Path
from .protocols.base import RequestResult


# Columnas en el orden exacto que JMeter espera
JTL_COLUMNS = [
    "timeStamp",
    "elapsed",
    "label",
    "responseCode",
    "responseMessage",
    "threadName",
    "dataType",
    "success",
    "failureMessage",
    "bytes",
    "sentBytes",
    "grpThreads",
    "allThreads",
    "URL",
    "Latency",
    "IdleTime",
    "Connect",
]

# Directorio base para guardar archivos JTL
JTL_BASE_DIR = Path("/app/data/jtl_results")


class JTLWriter:
    """
    Escribe resultados de ejecucion al formato .jtl estandar de JMeter.

    Thread-safe mediante asyncio.Lock — multiples VirtualUsers pueden escribir
    concurrentemente sin corromper el archivo.

    Uso:
        async with JTLWriter(filepath) as writer:
            await writer.write(result)
    """

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self._lock = asyncio.Lock()
        self._file = None
        self._writer = None

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def open(self) -> None:
        """Crear el archivo y escribir el header CSV."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        # Abrir en modo write para crear el archivo con header
        self._file = open(self.filepath, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=JTL_COLUMNS)
        self._writer.writeheader()
        self._file.flush()

    async def write(self, result: RequestResult) -> None:
        """Escribir un RequestResult al archivo JTL. Thread-safe."""
        async with self._lock:
            if self._writer is None:
                raise RuntimeError("JTLWriter no esta abierto. Usar 'async with JTLWriter(...)'")

            row = {
                "timeStamp": result.timestamp_ms,
                "elapsed": result.elapsed_ms,
                "label": result.label,
                "responseCode": result.response_code,
                "responseMessage": result.response_message,
                "threadName": result.thread_name,
                "dataType": result.data_type,
                "success": "true" if result.success else "false",
                "failureMessage": result.failure_message,
                "bytes": result.bytes_received,
                "sentBytes": result.sent_bytes,
                "grpThreads": result.grp_threads,
                "allThreads": result.all_threads,
                "URL": result.url,
                "Latency": result.latency_ms,
                "IdleTime": result.idle_time_ms,
                "Connect": result.connect_ms,
            }
            self._writer.writerow(row)
            self._file.flush()  # Flush en cada write para que sea visible en tiempo real

    async def close(self) -> None:
        """Cerrar el archivo."""
        if self._file and not self._file.closed:
            self._file.close()

    @staticmethod
    def build_filepath(client_name: str, project_name: str, execution_id: int) -> str:
        """
        Genera la ruta del archivo JTL con el naming estandar.
        Formato: NombreCliente_NombreProyecto_YYYYMMDD_HHMMSS.jtl
        """
        now = datetime.utcnow()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        # Sanitizar nombres: solo alfanumerico y guiones
        def sanitize(name: str) -> str:
            return re.sub(r'[^a-zA-Z0-9\-_]', '_', name.strip())[:50]

        client_clean = sanitize(client_name) if client_name else "cliente"
        project_clean = sanitize(project_name) if project_name else "proyecto"

        filename = f"{client_clean}_{project_clean}_{timestamp}.jtl"
        return str(JTL_BASE_DIR / filename)
