"""Integration tests for CQRS + Database."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from core.cqrs import Command, Query, CommandHandler, QueryHandler, CommandBus, QueryBus
from core.cqrs_handlers import EndpointCommandHandler, EndpointQueryHandler
from core.outbox_pattern import OutboxPublisher, OutboxEvent


class CreateOrderCommand(Command):
    """Sample command."""

    def __init__(self, order_id: str, customer_id: str, total: float):
        super().__init__()
        self.order_id = order_id
        self.customer_id = customer_id
        self.total = total

    def execute(self):
        return {"order_id": self.order_id, "created": True}


class GetOrderQuery(Query):
    """Sample query."""

    def __init__(self, order_id: str):
        super().__init__()
        self.order_id = order_id

    def execute(self):
        return {"order_id": self.order_id, "status": "confirmed"}


class CreateOrderCommandHandler(EndpointCommandHandler):
    """Sample command handler."""

    async def _execute(self, command: CreateOrderCommand):
        # Simulate database insert
        return {
            "order_id": command.order_id,
            "customer_id": command.customer_id,
            "total": command.total,
            "status": "created",
        }

    def _get_generated_events(self, command, result):
        return [
            {
                "aggregate_id": result["order_id"],
                "event_type": "order.created",
                "data": {"customer_id": result["customer_id"], "total": result["total"]},
            }
        ]


class GetOrderQueryHandler(EndpointQueryHandler):
    """Sample query handler."""

    async def _execute(self, query: GetOrderQuery):
        # Simulate database query
        return {
            "order_id": query.order_id,
            "customer_id": "customer_123",
            "total": 100.00,
            "status": "confirmed",
        }


@pytest.mark.asyncio
async def test_command_execution():
    """Test command execution."""
    handler = CreateOrderCommandHandler()
    order_id = str(uuid.uuid4())
    command = CreateOrderCommand(order_id, "customer_123", 100.00)

    result = await handler.handle(command)

    assert result["success"]
    assert result["command_id"]
    assert result["result"]["order_id"] == order_id
    assert result["result"]["status"] == "created"


@pytest.mark.asyncio
async def test_query_execution():
    """Test query execution."""
    handler = GetOrderQueryHandler()
    order_id = str(uuid.uuid4())
    query = GetOrderQuery(order_id)

    result = await handler.handle(query)

    assert result["success"]
    assert result["query_id"]
    assert result["result"]["order_id"] == order_id


@pytest.mark.asyncio
async def test_command_bus():
    """Test command bus."""
    bus = CommandBus()
    handler = CreateOrderCommandHandler()

    order_id = str(uuid.uuid4())
    command = CreateOrderCommand(order_id, "customer_123", 100.00)

    bus.register_handler(CreateOrderCommand, handler)
    result = await bus.execute(command)

    assert result["success"]
    assert result["order_id"] == order_id


@pytest.mark.asyncio
async def test_query_bus_with_cache():
    """Test query bus with caching."""
    bus = QueryBus()
    handler = GetOrderQueryHandler()

    order_id = str(uuid.uuid4())
    query = GetOrderQuery(order_id)
    query.query_id = "test_query_123"

    bus.register_handler(GetOrderQuery, handler)

    # First execution
    result1 = await bus.execute(query, use_cache=True)
    assert result1["success"]

    # Second execution should be cached
    result2 = await bus.execute(query, use_cache=True)
    assert result2["success"]

    # Invalidate cache
    bus.invalidate_cache(query.query_id)

    # Third execution should hit handler again
    result3 = await bus.execute(query, use_cache=True)
    assert result3["success"]


@pytest.mark.asyncio
async def test_event_publishing():
    """Test event publishing via outbox."""
    outbox_publisher = AsyncMock(spec=OutboxPublisher)
    registry = MagicMock()
    registry.outbox_publisher = outbox_publisher

    handler = CreateOrderCommandHandler(registry)
    order_id = str(uuid.uuid4())
    command = CreateOrderCommand(order_id, "customer_123", 100.00)

    result = await handler.handle(command)

    # Verify event was published
    assert outbox_publisher.publish_event.called


@pytest.mark.asyncio
async def test_command_handler_error_handling():
    """Test error handling in command handler."""

    class FailingCommandHandler(EndpointCommandHandler):
        async def _execute(self, command):
            raise ValueError("Test error")

    handler = FailingCommandHandler()
    command = CreateOrderCommand("order_123", "customer_123", 100.00)

    with pytest.raises(ValueError):
        await handler.handle(command)


@pytest.mark.asyncio
async def test_audit_trail_logging():
    """Test audit trail logging."""
    handler = CreateOrderCommandHandler()
    order_id = str(uuid.uuid4())
    command = CreateOrderCommand(order_id, "customer_123", 100.00)
    command.user_id = "user_123"
    command.request_id = "request_456"

    result = await handler.handle(command)

    # Verify audit trail logged
    assert handler.audit_trail.command_log
    log_entry = handler.audit_trail.command_log[0]
    assert log_entry["user_id"] == "user_123"
    assert log_entry["command_type"] == "CreateOrderCommand"


@pytest.mark.asyncio
async def test_idempotency():
    """Test idempotent command execution."""
    handler = CreateOrderCommandHandler()
    idempotency_key = str(uuid.uuid4())

    command1 = CreateOrderCommand("order_123", "customer_123", 100.00)
    command1.idempotency_key = idempotency_key

    command2 = CreateOrderCommand("order_123", "customer_123", 100.00)
    command2.idempotency_key = idempotency_key

    result1 = await handler.handle(command1)
    result2 = await handler.handle(command2)

    # Both should succeed
    assert result1["success"]
    assert result2["success"]
