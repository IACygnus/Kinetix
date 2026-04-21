# backend/app/services/engine/execution_manager.py
"""
ExecutionManager — Registry singleton de ejecuciones activas.

Mantiene un diccionario de execution_id → SteppingController para
poder pausar/reanudar/detener ejecuciones desde el endpoint HTTP.

Patrón: Singleton a nivel de proceso (vida de la app FastAPI).
"""
import logging
from typing import Dict, Optional
from .stepping_controller import SteppingController

logger = logging.getLogger(__name__)


class ExecutionManager:
    """Singleton que mantiene referencias a los SteppingControllers activos."""

    def __init__(self):
        self._controllers: Dict[int, SteppingController] = {}

    def register(self, execution_id: int, controller: SteppingController):
        self._controllers[execution_id] = controller
        logger.info(f"ExecutionManager: registered execution {execution_id}")

    def get(self, execution_id: int) -> Optional[SteppingController]:
        return self._controllers.get(execution_id)

    def unregister(self, execution_id: int):
        self._controllers.pop(execution_id, None)
        logger.info(f"ExecutionManager: unregistered execution {execution_id}")

    def active_ids(self) -> list:
        return list(self._controllers.keys())


# Instancia global (singleton)
execution_manager = ExecutionManager()
