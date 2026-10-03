"""WebSocket real-time updates for backoffice."""
import logging
import json
from typing import Dict, Set, Optional, List, Callable
from datetime import datetime
import asyncio
import uuid

from fastapi import WebSocket

logger = logging.getLogger("diomika-api")


class WebSocketManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_channels: Dict[str, Set[str]] = {}  # user_id -> channels
        self.message_handlers: Dict[str, List[Callable]] = {}

    async def connect(self, websocket: WebSocket, channel: str, user_id: Optional[str] = None):
        """Register a new WebSocket connection."""
        await websocket.accept()

        if channel not in self.active_connections:
            self.active_connections[channel] = set()

        self.active_connections[channel].add(websocket)

        if user_id:
            if user_id not in self.user_channels:
                self.user_channels[user_id] = set()
            self.user_channels[user_id].add(channel)

        logger.info(f"WebSocket connected to {channel} (total: {len(self.active_connections[channel])})")

    def disconnect(self, websocket: WebSocket, channel: str, user_id: Optional[str] = None):
        """Unregister a WebSocket connection."""
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)

            if not self.active_connections[channel]:
                del self.active_connections[channel]

        if user_id and user_id in self.user_channels:
            self.user_channels[user_id].discard(channel)

        logger.info(f"WebSocket disconnected from {channel}")

    async def broadcast_to_channel(self, channel: str, message: Dict):
        """Broadcast a message to all connections in a channel."""
        if channel not in self.active_connections:
            logger.warning(f"No connections in channel {channel}")
            return

        message["timestamp"] = datetime.utcnow().isoformat()
        message_json = json.dumps(message)

        disconnected = set()
        for websocket in self.active_connections[channel]:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting to {channel}: {e}")
                disconnected.add(websocket)

        # Clean up disconnected
        for websocket in disconnected:
            self.active_connections[channel].discard(websocket)

    async def send_to_user(self, user_id: str, message: Dict):
        """Send message to all connections of a user."""
        channels = self.user_channels.get(user_id, set())

        for channel in channels:
            await self.broadcast_to_channel(channel, message)

    async def send_to_websocket(self, websocket: WebSocket, message: Dict):
        """Send message to a specific WebSocket."""
        message["timestamp"] = datetime.utcnow().isoformat()

        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def register_message_handler(self, channel: str, handler: Callable):
        """Register a handler for messages on a channel."""
        if channel not in self.message_handlers:
            self.message_handlers[channel] = []

        self.message_handlers[channel].append(handler)
        logger.info(f"Registered message handler for {channel}")

    async def handle_message(self, channel: str, message: Dict):
        """Handle incoming message."""
        handlers = self.message_handlers.get(channel, [])

        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error handling message on {channel}: {e}")

    def get_channel_stats(self, channel: Optional[str] = None) -> Dict:
        """Get WebSocket statistics."""
        if channel:
            connections = self.active_connections.get(channel, set())
            return {
                "channel": channel,
                "connections": len(connections),
            }

        total_connections = sum(len(conns) for conns in self.active_connections.values())
        return {
            "total_channels": len(self.active_connections),
            "total_connections": total_connections,
            "channels": {
                channel: len(conns)
                for channel, conns in self.active_connections.items()
            },
        }


# Real-time update publishers
class OrderUpdatePublisher:
    """Publishes real-time order updates."""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager

    async def publish_order_created(self, order_id: str, order_data: Dict):
        """Publish order creation event."""
        await self.ws_manager.broadcast_to_channel(
            "orders",
            {
                "type": "order_created",
                "order_id": order_id,
                "data": order_data,
            }
        )

    async def publish_order_updated(self, order_id: str, changes: Dict):
        """Publish order update event."""
        await self.ws_manager.broadcast_to_channel(
            "orders",
            {
                "type": "order_updated",
                "order_id": order_id,
                "changes": changes,
            }
        )

    async def publish_order_status_changed(self, order_id: str, old_status: str, new_status: str):
        """Publish order status change event."""
        await self.ws_manager.broadcast_to_channel(
            "orders",
            {
                "type": "order_status_changed",
                "order_id": order_id,
                "old_status": old_status,
                "new_status": new_status,
            }
        )


class InventoryUpdatePublisher:
    """Publishes real-time inventory updates."""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager

    async def publish_stock_changed(self, product_id: str, old_quantity: int, new_quantity: int):
        """Publish inventory change event."""
        await self.ws_manager.broadcast_to_channel(
            "inventory",
            {
                "type": "stock_changed",
                "product_id": product_id,
                "old_quantity": old_quantity,
                "new_quantity": new_quantity,
            }
        )

    async def publish_stock_low_alert(self, product_id: str, quantity: int, threshold: int):
        """Publish low stock alert."""
        await self.ws_manager.broadcast_to_channel(
            "inventory",
            {
                "type": "stock_low_alert",
                "product_id": product_id,
                "quantity": quantity,
                "threshold": threshold,
            }
        )


class AnalyticsUpdatePublisher:
    """Publishes real-time analytics updates."""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager

    async def publish_metrics_update(self, metrics: Dict):
        """Publish metrics update."""
        await self.ws_manager.broadcast_to_channel(
            "analytics",
            {
                "type": "metrics_update",
                "metrics": metrics,
            }
        )

    async def publish_dashboard_update(self, dashboard_data: Dict):
        """Publish dashboard update."""
        await self.ws_manager.broadcast_to_channel(
            "dashboard",
            {
                "type": "dashboard_update",
                "data": dashboard_data,
            }
        )


class BackofficeNotificationPublisher:
    """Publishes notifications to backoffice."""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager

    async def send_notification(
        self,
        title: str,
        message: str,
        notification_type: str = "info",
        user_id: Optional[str] = None
    ):
        """Send a notification."""
        notification = {
            "type": "notification",
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "id": str(uuid.uuid4()),
        }

        if user_id:
            await self.ws_manager.send_to_user(user_id, notification)
        else:
            await self.ws_manager.broadcast_to_channel("notifications", notification)

    async def send_success(self, title: str, message: str, user_id: Optional[str] = None):
        """Send success notification."""
        await self.send_notification(title, message, "success", user_id)

    async def send_error(self, title: str, message: str, user_id: Optional[str] = None):
        """Send error notification."""
        await self.send_notification(title, message, "error", user_id)

    async def send_warning(self, title: str, message: str, user_id: Optional[str] = None):
        """Send warning notification."""
        await self.send_notification(title, message, "warning", user_id)


# Global manager
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get global WebSocket manager."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


def get_order_update_publisher() -> OrderUpdatePublisher:
    """Get order update publisher."""
    return OrderUpdatePublisher(get_websocket_manager())


def get_inventory_update_publisher() -> InventoryUpdatePublisher:
    """Get inventory update publisher."""
    return InventoryUpdatePublisher(get_websocket_manager())


def get_analytics_update_publisher() -> AnalyticsUpdatePublisher:
    """Get analytics update publisher."""
    return AnalyticsUpdatePublisher(get_websocket_manager())


def get_backoffice_notification_publisher() -> BackofficeNotificationPublisher:
    """Get backoffice notification publisher."""
    return BackofficeNotificationPublisher(get_websocket_manager())
