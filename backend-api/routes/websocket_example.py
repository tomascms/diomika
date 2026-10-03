"""Example WebSocket real-time updates."""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import json

from core.websocket_manager import (
    get_websocket_manager,
    get_order_update_publisher,
    get_inventory_update_publisher,
    get_backoffice_notification_publisher,
)

logger = logging.getLogger("diomika-api")

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/orders/{order_id}")
async def websocket_order_updates(websocket: WebSocket, order_id: str):
    """WebSocket endpoint for real-time order updates."""
    ws_manager = get_websocket_manager()

    try:
        # Connect to WebSocket
        await ws_manager.connect(
            websocket,
            channel=f"order_{order_id}",
            user_id=None  # Would extract from token
        )

        logger.info(f"Client connected to order {order_id} updates")

        # Send initial connection message
        await ws_manager.send_to_websocket(
            websocket,
            {
                "type": "connection_established",
                "order_id": order_id,
                "message": "Connected to order updates",
            }
        )

        # Keep connection open
        while True:
            data = await websocket.receive_text()

            # Handle incoming messages (ping, heartbeat, etc.)
            message = json.loads(data)
            logger.debug(f"Received message on order {order_id}: {message}")

            if message.get("type") == "ping":
                await ws_manager.send_to_websocket(
                    websocket,
                    {"type": "pong"}
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(
            websocket,
            channel=f"order_{order_id}",
        )
        logger.info(f"Client disconnected from order {order_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal error")


@router.websocket("/backoffice")
async def websocket_backoffice(websocket: WebSocket):
    """WebSocket endpoint for backoffice real-time updates."""
    ws_manager = get_websocket_manager()

    try:
        # Connect to multiple channels
        await ws_manager.connect(
            websocket,
            channel="backoffice_main",
        )

        logger.info("Backoffice client connected")

        # Send initial dashboard data
        await ws_manager.send_to_websocket(
            websocket,
            {
                "type": "dashboard_data",
                "orders_pending": 5,
                "orders_shipped": 12,
                "revenue_today": 5000.00,
                "inventory_items": 150,
            }
        )

        # Keep connection open
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await ws_manager.send_to_websocket(
                    websocket,
                    {"type": "pong"}
                )

            elif message.get("type") == "subscribe":
                channel = message.get("channel")
                await ws_manager.connect(
                    websocket,
                    channel=channel,
                )
                logger.info(f"Subscribed to channel: {channel}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel="backoffice_main")
        logger.info("Backoffice client disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal error")


@router.websocket("/inventory")
async def websocket_inventory_updates(websocket: WebSocket):
    """WebSocket endpoint for real-time inventory updates."""
    ws_manager = get_websocket_manager()

    try:
        await ws_manager.connect(
            websocket,
            channel="inventory",
        )

        logger.info("Inventory client connected")

        await ws_manager.send_to_websocket(
            websocket,
            {
                "type": "connection_established",
                "message": "Connected to inventory updates",
            }
        )

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await ws_manager.send_to_websocket(
                    websocket,
                    {"type": "pong"}
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel="inventory")
        logger.info("Inventory client disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# HTTP endpoints for triggering WebSocket broadcasts

@router.post("/broadcast/order-update")
async def broadcast_order_update(order_id: str, status: str):
    """Trigger order update broadcast."""
    publisher = get_order_update_publisher()

    await publisher.publish_order_status_changed(
        order_id=order_id,
        old_status="pending",
        new_status=status,
    )

    return {"success": True, "message": "Broadcast sent"}


@router.post("/broadcast/inventory-update")
async def broadcast_inventory_update(product_id: str, old_qty: int, new_qty: int):
    """Trigger inventory update broadcast."""
    publisher = get_inventory_update_publisher()

    await publisher.publish_stock_changed(
        product_id=product_id,
        old_quantity=old_qty,
        new_quantity=new_qty,
    )

    return {"success": True, "message": "Broadcast sent"}


@router.post("/broadcast/notification")
async def broadcast_notification(title: str, message: str, notification_type: str = "info"):
    """Send notification to backoffice."""
    publisher = get_backoffice_notification_publisher()

    await publisher.send_notification(
        title=title,
        message=message,
        notification_type=notification_type,
    )

    return {"success": True, "message": "Notification sent"}


@router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    ws_manager = get_websocket_manager()
    return ws_manager.get_channel_stats()
