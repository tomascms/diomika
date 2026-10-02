"""Event subscribers for Outbox pattern."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass
import json

from core.outbox_pattern import OutboxEvent
from core.audit_trail import AuditTrail

logger = logging.getLogger("diomika-api")


@dataclass
class EventSubscription:
    """Represents an event subscription."""
    event_type: str
    handler: Callable
    priority: int = 0


class EventSubscriber(ABC):
    """Base class for event subscribers."""

    @abstractmethod
    async def handle_event(self, event: OutboxEvent) -> bool:
        """Handle an event. Return True if successful."""
        pass

    @property
    @abstractmethod
    def event_types(self) -> List[str]:
        """Event types this subscriber handles."""
        pass


class EventSubscriptionManager:
    """Manages event subscriptions and dispatching."""

    def __init__(self):
        self.subscriptions: Dict[str, List[EventSubscription]] = {}
        self.audit_trail = AuditTrail()

    def subscribe(self, event_type: str, handler: Callable, priority: int = 0):
        """Subscribe to an event type."""
        if event_type not in self.subscriptions:
            self.subscriptions[event_type] = []

        subscription = EventSubscription(
            event_type=event_type,
            handler=handler,
            priority=priority,
        )
        self.subscriptions[event_type].append(subscription)

        # Sort by priority (descending)
        self.subscriptions[event_type].sort(key=lambda s: s.priority, reverse=True)

        logger.info(f"Subscribed to {event_type} with priority {priority}")

    def register_subscriber(self, subscriber: EventSubscriber):
        """Register a subscriber for its event types."""
        for event_type in subscriber.event_types:
            self.subscribe(event_type, subscriber.handle_event)
        logger.info(f"Registered subscriber {subscriber.__class__.__name__} for {subscriber.event_types}")

    async def publish(self, event: OutboxEvent) -> bool:
        """Publish an event to all subscribers."""
        handlers = self.subscriptions.get(event.event_type, [])

        if not handlers:
            logger.warning(f"No subscribers for event type: {event.event_type}")
            return False

        logger.info(f"Publishing {event.event_type} to {len(handlers)} subscribers")

        all_successful = True
        for subscription in handlers:
            try:
                success = await subscription.handler(event)
                if success:
                    logger.debug(f"✓ {subscription.handler.__name__} handled {event.event_type}")
                else:
                    logger.warning(f"✗ {subscription.handler.__name__} failed to handle {event.event_type}")
                    all_successful = False
            except Exception as e:
                logger.error(f"Error in {subscription.handler.__name__}: {e}")
                all_successful = False

        return all_successful

    async def handle_outbox_events(self, events: List[OutboxEvent]) -> Dict[str, Any]:
        """Handle a batch of outbox events."""
        results = {
            "total": len(events),
            "successful": 0,
            "failed": 0,
            "errors": [],
        }

        for event in events:
            try:
                if await self.publish(event):
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({"event_id": event.id, "error": "Handler failed"})
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"event_id": event.id, "error": str(e)})

        logger.info(f"Event batch processing: {results['successful']}/{results['total']} successful")
        return results


class EmailEventSubscriber(EventSubscriber):
    """Subscriber for email events."""

    def __init__(self, email_service):
        self.email_service = email_service

    @property
    def event_types(self) -> List[str]:
        return ["order.created", "order.confirmed", "payment.completed"]

    async def handle_event(self, event: OutboxEvent) -> bool:
        """Handle email-related events."""
        try:
            if event.event_type == "order.created":
                return await self._send_order_confirmation(event)
            elif event.event_type == "order.confirmed":
                return await self._send_order_confirmed(event)
            elif event.event_type == "payment.completed":
                return await self._send_payment_receipt(event)
            return False
        except Exception as e:
            logger.error(f"Error handling email event: {e}")
            return False

    async def _send_order_confirmation(self, event: OutboxEvent) -> bool:
        """Send order confirmation email."""
        try:
            data = json.loads(event.data) if isinstance(event.data, str) else event.data
            customer_email = data.get("customer_email")
            order_id = data.get("order_id")

            logger.info(f"Sending order confirmation email for order {order_id}")
            # Implementation would use actual email service
            return True
        except Exception as e:
            logger.error(f"Failed to send order confirmation: {e}")
            return False

    async def _send_order_confirmed(self, event: OutboxEvent) -> bool:
        """Send order confirmed email."""
        return True

    async def _send_payment_receipt(self, event: OutboxEvent) -> bool:
        """Send payment receipt email."""
        return True


class NotificationEventSubscriber(EventSubscriber):
    """Subscriber for notification events."""

    def __init__(self, notification_service):
        self.notification_service = notification_service

    @property
    def event_types(self) -> List[str]:
        return ["order.created", "order.shipped", "payment.failed"]

    async def handle_event(self, event: OutboxEvent) -> bool:
        """Handle notification events."""
        try:
            if event.event_type == "order.created":
                return await self._notify_order_created(event)
            elif event.event_type == "order.shipped":
                return await self._notify_order_shipped(event)
            elif event.event_type == "payment.failed":
                return await self._notify_payment_failed(event)
            return False
        except Exception as e:
            logger.error(f"Error handling notification event: {e}")
            return False

    async def _notify_order_created(self, event: OutboxEvent) -> bool:
        """Send notification for order creation."""
        logger.info("Sending order creation notification")
        return True

    async def _notify_order_shipped(self, event: OutboxEvent) -> bool:
        """Send notification for order shipped."""
        return True

    async def _notify_payment_failed(self, event: OutboxEvent) -> bool:
        """Send notification for payment failure."""
        return True


class AnalyticsEventSubscriber(EventSubscriber):
    """Subscriber for analytics events."""

    def __init__(self, analytics_service):
        self.analytics_service = analytics_service

    @property
    def event_types(self) -> List[str]:
        return ["order.created", "order.completed", "payment.completed"]

    async def handle_event(self, event: OutboxEvent) -> bool:
        """Handle analytics events."""
        try:
            logger.debug(f"Recording analytics event: {event.event_type}")
            # Implementation would track analytics
            return True
        except Exception as e:
            logger.error(f"Error handling analytics event: {e}")
            return False


class CacheInvalidationSubscriber(EventSubscriber):
    """Subscriber for cache invalidation events."""

    def __init__(self, cache_service):
        self.cache_service = cache_service

    @property
    def event_types(self) -> List[str]:
        return ["catalog.updated", "product.modified", "pricing.changed"]

    async def handle_event(self, event: OutboxEvent) -> bool:
        """Handle cache invalidation events."""
        try:
            data = json.loads(event.data) if isinstance(event.data, str) else event.data
            cache_keys = data.get("cache_keys", [])

            for key in cache_keys:
                await self.cache_service.invalidate(key)
                logger.debug(f"Invalidated cache key: {key}")

            return True
        except Exception as e:
            logger.error(f"Error handling cache invalidation: {e}")
            return False


# Global subscription manager
_subscription_manager: Optional[EventSubscriptionManager] = None


def get_subscription_manager() -> EventSubscriptionManager:
    """Get global subscription manager."""
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = EventSubscriptionManager()
    return _subscription_manager
