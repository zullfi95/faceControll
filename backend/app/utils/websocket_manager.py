"""
Менеджер WebSocket соединений для реального времени обновлений.

Позволяет рассылать обновления всем подключенным клиентам
при получении новых событий от терминалов.
"""
import json
import logging
from typing import Dict, List
from fastapi import WebSocket
from datetime import datetime

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Менеджер активных WebSocket соединений."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "events": [],      # Для обновлений событий
            "reports": [],     # Для обновлений отчетов
            "dashboard": []    # Для главной панели
        }

    async def connect(self, websocket: WebSocket, channel: str = "events"):
        """Подключение нового WebSocket клиента."""
        if channel not in self.active_connections:
            self.active_connections[channel] = []

        await websocket.accept()
        self.active_connections[channel].append(websocket)
        logger.info(f"WebSocket client connected to channel '{channel}'. Total: {len(self.active_connections[channel])}")

    async def disconnect(self, websocket: WebSocket, channel: str = "events"):
        """Отключение WebSocket клиента."""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
                logger.info(f"WebSocket client disconnected from channel '{channel}'. Remaining: {len(self.active_connections[channel])}")

    async def broadcast(self, message: dict, channel: str = "events"):
        """Рассылка сообщения всем клиентам в канале."""
        if channel not in self.active_connections:
            return

        disconnected = []

        for websocket in self.active_connections[channel]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket client: {e}")
                disconnected.append(websocket)

        # Удаляем отключенные соединения
        for websocket in disconnected:
            await self.disconnect(websocket, channel)

        if disconnected:
            logger.info(f"Cleaned up {len(disconnected)} disconnected WebSocket clients")

    async def notify_event_update(self, event_data: dict):
        """Уведомление о новом событии."""
        message = {
            "type": "event_update",
            "timestamp": datetime.now().isoformat(),
            "data": event_data
        }
        await self.broadcast(message, "events")

    async def notify_report_update(self, report_data: dict):
        """Уведомление об обновлении отчета."""
        message = {
            "type": "report_update",
            "timestamp": datetime.now().isoformat(),
            "data": report_data
        }
        await self.broadcast(message, "reports")

    async def notify_dashboard_update(self, dashboard_data: dict):
        """Уведомление об обновлении главной панели."""
        message = {
            "type": "dashboard_update",
            "timestamp": datetime.now().isoformat(),
            "data": dashboard_data
        }
        await self.broadcast(message, "dashboard")

    def get_connection_count(self, channel: str = None) -> int:
        """Получение количества активных соединений."""
        if channel:
            return len(self.active_connections.get(channel, []))
        return sum(len(connections) for connections in self.active_connections.values())


# Глобальный экземпляр менеджера
websocket_manager = WebSocketManager()
