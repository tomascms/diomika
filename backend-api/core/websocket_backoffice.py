"""WebSocket para backoffice — real-time inventory, orders, analytics."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional, Set
from dataclasses import dataclass
from enum import Enum

import socketio
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("diomika-websocket")


class WSMessageType(Enum):
    """WebSocket message types."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    INVENTORY_UPDATE = "inventory_update"
    ORDER_STATUS = "order_status"
    ANALYTICS_METRIC = "analytics_metric"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"


@dataclass
class WSMessage:
    """WebSocket message structure."""
    type: WSMessageType
    payload: dict[str, Any]
    timestamp: datetime
    request_id: Optional[str] = None


class BackofficeWSManager:
    """Gerencia conexões WebSocket para backoffice."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, Set[str]] = {}  # channel -> {user_ids}
        self.handlers: dict[WSMessageType, Callable] = {}
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*',
        )
        self._setup_handlers()

    def _setup_handlers(self):
        """Register internal handlers."""
        self.handlers[WSMessageType.SUBSCRIBE] = self._handle_subscribe
        self.handlers[WSMessageType.UNSUBSCRIBE] = self._handle_unsubscribe
        self.handlers[WSMessageType.HEARTBEAT] = self._handle_heartbeat

    async def connect(self, websocket: WebSocket, user_id: str, client_id: str):
        """Register a new WebSocket connection."""
        await websocket.accept()
        connection_key = f"{user_id}:{client_id}"
        self.active_connections[connection_key] = websocket

        logger.info(f"[WS] Client connected: {connection_key}")

        # Send welcome message
        await self._send_message(
            websocket,
            WSMessage(
                type=WSMessageType.HEARTBEAT,
                payload={"status": "connected", "timestamp": datetime.utcnow().isoformat()},
            ),
        )

    async def disconnect(self, user_id: str, client_id: str):
        """Unregister a WebSocket connection."""
        connection_key = f"{user_id}:{client_id}"
        if connection_key in self.active_connections:
            del self.active_connections[connection_key]

        # Cleanup subscriptions
        for channel_subscribers in self.subscriptions.values():
            channel_subscribers.discard(user_id)

        logger.info(f"[WS] Client disconnected: {connection_key}")

    async def broadcast_inventory_update(self, inventory_data: dict[str, Any]):
        """Broadcast inventory update para todos os conectados."""
        message = WSMessage(
            type=WSMessageType.INVENTORY_UPDATE,
            payload={
                "ean": inventory_data.get("ean"),
                "quantity": inventory_data.get("quantity"),
                "reserved": inventory_data.get("reserved", 0),
                "status": inventory_data.get("status", "ok"),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        await self._broadcast_channel("inventory", message)

    async def broadcast_order_status(self, order_id: str, status: str, details: Optional[dict] = None):
        """Broadcast order status update para backoffice."""
        message = WSMessage(
            type=WSMessageType.ORDER_STATUS,
            payload={
                "order_id": order_id,
                "status": status,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        await self._broadcast_channel("orders", message)

    async def broadcast_analytics_metric(self, metric_name: str, value: float, tags: Optional[dict] = None):
        """Broadcast analytics metric em tempo real."""
        message = WSMessage(
            type=WSMessageType.ANALYTICS_METRIC,
            payload={
                "metric": metric_name,
                "value": value,
                "tags": tags or {},
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        await self._broadcast_channel("analytics", message)

    async def broadcast_alert(self, alert_level: str, message_text: str, details: Optional[dict] = None):
        """Broadcast alert para backoffice."""
        message = WSMessage(
            type=WSMessageType.ALERT,
            payload={
                "level": alert_level,  # "info", "warning", "critical"
                "message": message_text,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        await self._broadcast_channel("alerts", message)

    async def _handle_subscribe(self, user_id: str, payload: dict[str, Any]):
        """Handle subscription request."""
        channel = payload.get("channel")
        if not channel:
            return

        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()

        self.subscriptions[channel].add(user_id)
        logger.info(f"[WS] User {user_id} subscribed to {channel}")

    async def _handle_unsubscribe(self, user_id: str, payload: dict[str, Any]):
        """Handle unsubscription request."""
        channel = payload.get("channel")
        if channel and channel in self.subscriptions:
            self.subscriptions[channel].discard(user_id)
            logger.info(f"[WS] User {user_id} unsubscribed from {channel}")

    async def _handle_heartbeat(self, user_id: str, payload: dict[str, Any]):
        """Handle heartbeat/ping."""
        # Just log — client expects no response
        logger.debug(f"[WS] Heartbeat from {user_id}")

    async def _broadcast_channel(self, channel: str, message: WSMessage):
        """Broadcast message para todos subscribers de um channel."""
        if channel not in self.subscriptions:
            return

        message_json = json.dumps({
            "type": message.type.value,
            "payload": message.payload,
            "timestamp": message.timestamp.isoformat(),
        })

        failed = []
        for connection_key, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"[WS] Failed to send to {connection_key}: {e}")
                failed.append(connection_key)

        # Cleanup failed connections
        for connection_key in failed:
            del self.active_connections[connection_key]

    async def _send_message(self, websocket: WebSocket, message: WSMessage):
        """Send message para um websocket específico."""
        try:
            message_json = json.dumps({
                "type": message.type.value,
                "payload": message.payload,
                "timestamp": message.timestamp.isoformat(),
            })
            await websocket.send_text(message_json)
        except Exception as e:
            logger.error(f"[WS] Failed to send message: {e}")

    async def heartbeat_loop(self):
        """Background task: periodic heartbeat para keep-alive."""
        while True:
            try:
                await asyncio.sleep(30)
                message = WSMessage(
                    type=WSMessageType.HEARTBEAT,
                    payload={"status": "alive", "timestamp": datetime.utcnow().isoformat()},
                )
                await self._broadcast_channel("backoffice", message)
            except Exception as e:
                logger.error(f"[WS] Heartbeat loop error: {e}")


# Global instance
_ws_manager: Optional[BackofficeWSManager] = None


def get_ws_manager() -> BackofficeWSManager:
    """Get global WebSocket manager."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = BackofficeWSManager()
    return _ws_manager


async def start_ws_heartbeat():
    """Start WebSocket heartbeat background task."""
    manager = get_ws_manager()
    asyncio.create_task(manager.heartbeat_loop())
