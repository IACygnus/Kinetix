# backend/app/services/engine/stepping_controller.py
"""
SteppingController — Orquesta la ejecución concurrente de múltiples VirtualUsers.

Implementa el patrón de stepping (rampa gradual de carga):
- Arranca con initial_users VUs
- Cada step_duration_sec, agrega step_users VUs más
- Hasta llegar a max_users
- Mantiene la carga durante hold_duration_sec
- Todos los VUs ejecutan el script en loop durante todo el período

Controles en tiempo real:
- stop(): detiene todos los VUs al finalizar el request actual
- pause() / resume(): pausa/reanuda el stepping

Límites:
- MAX_VUS = 200 (asyncio.Semaphore)
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

from .virtual_user import VirtualUser
from .jtl_writer import JTLWriter
from .metrics_collector import MetricsCollector
from .protocols.base import RequestResult

logger = logging.getLogger(__name__)

MAX_VUS = 200
METRICS_INTERVAL_SEC = 5


class SteppingController:
    """
    Controla la ejecución gradual de VirtualUsers según la config de stepping.

    Uso:
        controller = SteppingController(script_model, scenario_config, jtl_path)
        asyncio.create_task(controller.run())
        await controller.stop()
    """

    def __init__(
        self,
        execution_id: int,
        script_model: Dict[str, Any],
        scenario_config: Dict[str, Any],
        jtl_path: str,
        client_name: str = "cliente",
        on_metrics: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.execution_id = execution_id
        self.script_model = script_model
        self.jtl_path = jtl_path
        self.client_name = client_name
        self.on_metrics = on_metrics

        # Config de stepping — adapt from Scenario template keys
        cfg = scenario_config
        self.initial_threads: int = max(1, min(
            cfg.get("initial_threads", cfg.get("initial_users", 1)),
            MAX_VUS
        ))
        self.step_threads: int = max(1,
            cfg.get("step_threads", cfg.get("step_users", 5))
        )
        self.step_delay_sec: float = max(1.0,
            cfg.get("step_delay_sec", cfg.get("step_duration_sec", 30))
        )
        self.max_threads: int = max(1, min(
            cfg.get("max_threads", cfg.get("max_users", 50)),
            MAX_VUS
        ))
        self.hold_sec: float = max(1.0,
            cfg.get("hold_sec", cfg.get("hold_duration_sec", 300))
        )
        self.ramp_up_sec: float = cfg.get("ramp_up_sec", 0)

        # Estado
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Inicia en "no pausado"
        self._active_vus: List[asyncio.Task] = []
        self._active_vus_map: Dict[int, VirtualUser] = {}
        self._vu_count = 0
        self._semaphore = asyncio.Semaphore(MAX_VUS)
        self._jtl_writer: Optional[JTLWriter] = None

        self.metrics_collector = MetricsCollector()
        self._metrics_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # Status público
        self.status: str = "pending"
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error_message: str = ""

    async def run(self) -> MetricsCollector:
        """
        Ejecutar la prueba de carga completa.

        Flow:
        1. Abrir JTLWriter
        2. Lanzar initial_threads VUs
        3. Cada step_delay_sec, lanzar step_threads VUs más hasta max_threads
        4. Una vez en max_threads, mantener hold_sec
        5. Señalizar stop a todos los VUs activos
        6. Esperar que terminen

        Returns:
            MetricsCollector con todas las métricas de la ejecución
        """
        self.status = "running"
        self.started_at = datetime.utcnow()
        logger.info(
            f"[Execution {self.execution_id}] Starting: "
            f"{self.initial_threads}→{self.max_threads} VUs, "
            f"step +{self.step_threads} every {self.step_delay_sec}s, "
            f"hold {self.hold_sec}s"
        )

        metrics_task = asyncio.create_task(self._publish_metrics_loop())

        try:
            async with JTLWriter(self.jtl_path) as jtl_writer:
                self._jtl_writer = jtl_writer

                # Fase de stepping: rampa de carga
                current_threads = 0
                target = self.initial_threads

                while current_threads < self.max_threads and not self._stop_event.is_set():
                    # Lanzar VUs hasta el target actual
                    to_launch = min(target - current_threads, self.max_threads - current_threads)
                    for _ in range(to_launch):
                        if self._stop_event.is_set():
                            break
                        await self._launch_vu()
                        current_threads += 1

                    logger.info(f"[Execution {self.execution_id}] Active VUs: {current_threads}/{self.max_threads}")

                    if current_threads >= self.max_threads:
                        break

                    # Esperar step_delay antes del siguiente batch
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=self.step_delay_sec
                        )
                        break  # Stop fue señalizado durante el wait
                    except asyncio.TimeoutError:
                        pass  # Normal — step_delay expiró

                    # Pausado?
                    while not self._pause_event.is_set() and not self._stop_event.is_set():
                        await asyncio.sleep(0.5)

                    target += self.step_threads

                # Fase de hold: mantener la carga
                if not self._stop_event.is_set():
                    logger.info(f"[Execution {self.execution_id}] Hold phase: {self.hold_sec}s at {current_threads} VUs")
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=self.hold_sec
                        )
                    except asyncio.TimeoutError:
                        pass  # Hold expiró normalmente

                # Señalizar stop a todos los VUs
                await self.stop()

                # Esperar a que todos los VUs terminen (máx 60s)
                if self._active_vus:
                    active_tasks = [t for t in self._active_vus if not t.done()]
                    if active_tasks:
                        done, pending = await asyncio.wait(
                            active_tasks,
                            timeout=60.0
                        )
                        for task in pending:
                            task.cancel()
                        logger.info(
                            f"[Execution {self.execution_id}] All VUs finished. "
                            f"Done: {len(done)}, Cancelled: {len(pending)}"
                        )

            self.metrics_collector.finalize()
            self.status = "completed"
            self.completed_at = datetime.utcnow()
            logger.info(
                f"[Execution {self.execution_id}] Completed. "
                f"Total requests: {self.metrics_collector.total_requests}"
            )

        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            self.completed_at = datetime.utcnow()
            logger.error(f"[Execution {self.execution_id}] Fatal error: {e}")
        finally:
            metrics_task.cancel()

        return self.metrics_collector

    async def _launch_vu(self):
        """Lanzar un nuevo VirtualUser como asyncio.Task."""
        self._vu_count += 1
        vu_id = self._vu_count

        async def vu_wrapper():
            async with self._semaphore:
                vu = VirtualUser(
                    vu_id=vu_id,
                    execution_id=self.execution_id,
                    script_model=self.script_model,
                    jtl_writer=self._jtl_writer,
                    timeout_sec=30.0,
                )
                self._active_vus_map[vu_id] = vu
                try:
                    # Loop: ejecutar hasta que stop sea señalizado
                    while not self._stop_event.is_set():
                        # Pausa check
                        while not self._pause_event.is_set() and not self._stop_event.is_set():
                            await asyncio.sleep(0.5)

                        if self._stop_event.is_set():
                            break

                        results = await vu.run(iterations=1, all_threads=self._vu_count)
                        for r in results:
                            self.metrics_collector.record(r)

                        # Small delay between iterations to yield control
                        if not self._stop_event.is_set():
                            await asyncio.sleep(0.1)
                finally:
                    self._active_vus_map.pop(vu_id, None)

        task = asyncio.create_task(vu_wrapper())
        self._active_vus.append(task)

    async def _publish_metrics_loop(self):
        """Publicar métricas cada METRICS_INTERVAL_SEC."""
        try:
            while True:
                await asyncio.sleep(METRICS_INTERVAL_SEC)
                snapshot = self._build_metrics_snapshot()
                try:
                    self._metrics_queue.put_nowait(snapshot)
                except asyncio.QueueFull:
                    # Drop oldest if queue full
                    try:
                        self._metrics_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    self._metrics_queue.put_nowait(snapshot)

                if self.on_metrics:
                    try:
                        self.on_metrics(snapshot)
                    except Exception as e:
                        logger.warning(f"on_metrics callback error: {e}")
        except asyncio.CancelledError:
            pass

    def _build_metrics_snapshot(self) -> Dict[str, Any]:
        """Construir snapshot de métricas para publicación en tiempo real."""
        summary = self.metrics_collector.get_summary()
        return {
            "execution_id": self.execution_id,
            "timestamp": datetime.utcnow().isoformat(),
            "active_vus": len([t for t in self._active_vus if not t.done()]),
            "status": self.status,
            **summary,
        }

    async def stop(self):
        """Señalizar stop a todos los VUs. Esperan terminar el request actual."""
        if not self._stop_event.is_set():
            self._stop_event.set()
            self._pause_event.set()  # Desbloquear VUs pausados para que puedan terminar
            logger.info(f"[Execution {self.execution_id}] Stop signal sent to all VUs")

    def pause(self):
        """Pausar el stepping (los VUs en vuelo terminan su request actual)."""
        self._pause_event.clear()
        self.status = "paused"
        logger.info(f"[Execution {self.execution_id}] Paused")

    def resume(self):
        """Reanudar el stepping."""
        self._pause_event.set()
        self.status = "running"
        logger.info(f"[Execution {self.execution_id}] Resumed")

    @property
    def active_vu_count(self) -> int:
        return len([t for t in self._active_vus if not t.done()])

    @property
    def metrics_queue(self) -> asyncio.Queue:
        return self._metrics_queue
