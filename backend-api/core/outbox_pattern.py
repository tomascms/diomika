"""Outbox pattern for reliable event publishing."""
from __future__ import annotations

import logging
import json
from enum import Enum
from typing import Optional, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("diomika-api")


class EventPublishStatus(Enum):
    """Status of event in outbox."""
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class OutboxEvent:
    """Event stored in outbox before publishing."""
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    payload: dict
    status: EventPublishStatus = EventPublishStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def is_retryable(self) -> bool:
        """Check if event can be retried."""
        return (
            self.status == EventPublishStatus.FAILED
            and self.retry_count < self.max_retries
        )

    def should_retry_now(self, retry_delay_seconds: int = 300) -> bool:
        """Check if event should be retried now."""
        if not self.is_retryable():
            return False
        time_since_creation = (datetime.utcnow() - self.created_at).total_seconds()
        expected_delay = retry_delay_seconds * (2 ** self.retry_count)  # Exponential backoff
        return time_since_creation >= expected_delay

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps(self.to_dict(), default=str)


class EventPublisher:
    """Publisher for outbox events."""

    def __init__(self):
        self.subscribers: dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info(f"Subscribed to {event_type}")

    async def publish(self, event: OutboxEvent) -> bool:
        """Publish event to subscribers."""
        handlers = self.subscribers.get(event.event_type, [])
        if not handlers:
            logger.warning(f"No subscribers for event type {event.event_type}")
            return False

        for handler in handlers:
            try:
                logger.info(f"Publishing event {event.event_id} to handler")
                if hasattr(handler, "__await__"):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Failed to publish event {event.event_id}: {str(e)}")
                return False

        return True


class OutboxStore:
    """Storage for outbox events."""

    def __init__(self):
        self.events: dict[str, OutboxEvent] = {}

    def add_event(self, event: OutboxEvent):
        """Add event to outbox."""
        self.events[event.event_id] = event
        logger.info(f"Added event {event.event_id} to outbox (type: {event.event_type})")

    def get_event(self, event_id: str) -> Optional[OutboxEvent]:
        """Get event by ID."""
        return self.events.get(event_id)

    def get_pending_events(self) -> List[OutboxEvent]:
        """Get all pending events."""
        return [e for e in self.events.values() if e.status == EventPublishStatus.PENDING]

    def get_failed_events(self) -> List[OutboxEvent]:
        """Get all failed events."""
        return [e for e in self.events.values() if e.status == EventPublishStatus.FAILED]

    def get_retryable_events(self) -> List[OutboxEvent]:
        """Get all events that can be retried."""
        return [e for e in self.events.values() if e.is_retryable()]

    def mark_published(self, event_id: str) -> bool:
        """Mark event as published."""
        event = self.get_event(event_id)
        if event:
            event.status = EventPublishStatus.PUBLISHED
            event.published_at = datetime.utcnow()
            logger.info(f"Event {event_id} marked as published")
            return True
        return False

    def mark_failed(self, event_id: str, error: str) -> bool:
        """Mark event as failed."""
        event = self.get_event(event_id)
        if event:
            event.status = EventPublishStatus.FAILED
            event.error_message = error
            event.retry_count += 1
            logger.warning(f"Event {event_id} marked as failed: {error}")
            return True
        return False

    def delete_event(self, event_id: str) -> bool:
        """Delete event from outbox."""
        if event_id in self.events:
            del self.events[event_id]
            logger.info(f"Deleted event {event_id} from outbox")
            return True
        return False

    def list_events(
        self,
        status: Optional[EventPublishStatus] = None,
        event_type: Optional[str] = None,
    ) -> List[OutboxEvent]:
        """List events with optional filtering."""
        events = list(self.events.values())
        if status:
            events = [e for e in events if e.status == status]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events


class OutboxProcessor:
    """Process outbox events and publish them."""

    def __init__(self, store: OutboxStore, publisher: EventPublisher):
        self.store = store
        self.publisher = publisher
        self.batch_size = 10
        self.retry_delay = 300  # 5 minutes

    async def process_pending(self):
        """Process all pending events."""
        events = self.store.get_pending_events()[:self.batch_size]

        for event in events:
            try:
                event.status = EventPublishStatus.PUBLISHING
                published = await self.publisher.publish(event)

                if published:
                    self.store.mark_published(event.event_id)
                    logger.info(f"Event {event.event_id} published successfully")
                else:
                    self.store.mark_failed(event.event_id, "No subscribers")
            except Exception as e:
                self.store.mark_failed(event.event_id, str(e))

    async def process_retryable(self):
        """Process events that can be retried."""
        events = self.store.get_retryable_events()

        for event in events:
            if event.should_retry_now(self.retry_delay):
                try:
                    event.status = EventPublishStatus.PUBLISHING
                    published = await self.publisher.publish(event)

                    if published:
                        self.store.mark_published(event.event_id)
                        logger.info(f"Event {event.event_id} retried and published")
                    else:
                        self.store.mark_failed(event.event_id, "Retry failed")
                except Exception as e:
                    self.store.mark_failed(event.event_id, f"Retry error: {str(e)}")

    async def cleanup_old_published(self, days: int = 30):
        """Clean up published events older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        published = self.store.get_event
        events = self.store.list_events(status=EventPublishStatus.PUBLISHED)

        deleted_count = 0
        for event in events:
            if event.published_at and event.published_at < cutoff_date:
                self.store.delete_event(event.event_id)
                deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} old published events")


class OutboxTransaction:
    """Transaction builder for creating outbox events."""

    def __init__(self, event_id: str, event_type: str, aggregate_id: str, aggregate_type: str):
        self.event = OutboxEvent(
            event_id=event_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            payload={},
        )

    def add_payload(self, key: str, value: Any) -> OutboxTransaction:
        """Add payload data."""
        self.event.payload[key] = value
        return self

    def with_metadata(self, key: str, value: Any) -> OutboxTransaction:
        """Add metadata."""
        self.event.metadata[key] = value
        return self

    def build(self) -> OutboxEvent:
        """Build the event."""
        return self.event


# Global instances
_store: Optional[OutboxStore] = None
_publisher: Optional[EventPublisher] = None
_processor: Optional[OutboxProcessor] = None


def get_outbox_store() -> OutboxStore:
    """Get global outbox store."""
    global _store
    if _store is None:
        _store = OutboxStore()
    return _store


def get_event_publisher() -> EventPublisher:
    """Get global event publisher."""
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher


def get_outbox_processor() -> OutboxProcessor:
    """Get global outbox processor."""
    global _processor
    if _processor is None:
        _processor = OutboxProcessor(get_outbox_store(), get_event_publisher())
    return _processor
