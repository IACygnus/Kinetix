# backend/app/api/v1/endpoints/ws_metrics.py
"""
WebSocket endpoint para métricas en tiempo real.

El cliente se conecta a /api/v1/ws/executions/{execution_id}/metrics
y recibe un JSON cada METRICS_INTERVAL_SEC con las métricas actuales.

Protocolo:
- Cliente conecta → servidor envía snapshot inmediato + cada 5s
- Cliente puede enviar "stop", "pause", "resume" como texto plano
- Servidor cierra la conexión cuando la ejecución termina
"""
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.engine.execution_manager import execution_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/executions/{execution_id}/metrics")
async def ws_execution_metrics(websocket: WebSocket, execution_id: int):
    """
    WebSocket para métricas en tiempo real de una ejecución.

    Mensajes del servidor: JSON con snapshot de métricas cada 5s
    Comandos del cliente (texto): "stop" | "pause" | "resume"
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for execution {execution_id}")

    controller = execution_manager.get(execution_id)
    if not controller:
        await websocket.send_text(json.dumps({
            "error": f"Execution {execution_id} not found or already finished"
        }))
        await websocket.close()
        return

    # Tarea para recibir comandos del cliente
    async def receive_commands():
        try:
            while True:
                msg = await websocket.receive_text()
                cmd = msg.strip().lower()
                if cmd == "stop":
                    await controller.stop()
                    logger.info(f"WS command: stop execution {execution_id}")
                elif cmd == "pause":
                    controller.pause()
                elif cmd == "resume":
                    controller.resume()
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning(f"WS receive error: {e}")

    receive_task = asyncio.create_task(receive_commands())

    try:
        # Enviar métricas mientras la ejecución esté activa
        while controller.status in ("running", "paused", "pending"):
            try:
                snapshot = await asyncio.wait_for(
                    controller.metrics_queue.get(),
                    timeout=6.0
                )
                await websocket.send_text(json.dumps(snapshot, default=str))

                if controller.status in ("completed", "error"):
                    break

            except asyncio.TimeoutError:
                if controller.status in ("completed", "error"):
                    break
                # Enviar heartbeat snapshot
                snapshot = controller._build_metrics_snapshot()
                await websocket.send_text(json.dumps(snapshot, default=str))

        # Enviar snapshot final
        final_snapshot = controller._build_metrics_snapshot()
        final_snapshot["final"] = True
        await websocket.send_text(json.dumps(final_snapshot, default=str))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for execution {execution_id}")
    except Exception as e:
        logger.error(f"WebSocket error for execution {execution_id}: {e}")
    finally:
        receive_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info(f"WebSocket closed for execution {execution_id}")
