"""Example CQRS endpoint integration."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import uuid

from core.cqrs import Command, Query, CommandBus, QueryBus
from core.cqrs_handlers import EndpointCommandHandler, EndpointQueryHandler, get_handler_registry
from core.outbox_pattern import OutboxPublisher, get_outbox_publisher
from core.saga_coordinator import OrderSaga, get_saga_orchestrator
from core.job_queue import Job, JobPriority, get_job_queue
from core.endpoint_rate_limiting import RateLimitConfig, RATE_LIMITS

logger = logging.getLogger("diomika-api")

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


# ============================================================================
# COMMANDS & HANDLERS
# ============================================================================

class CreateOrderCommandModel(BaseModel):
    customer_id: str
    total: float
    items: list


class CreateOrderHandler(EndpointCommandHandler):
    """Handler for CreateOrder command."""

    async def _execute(self, command) -> dict:
        """Execute order creation."""
        logger.info(f"Creating order for customer {command.customer_id}")

        # Simulate database insert
        order = {
            "id": str(uuid.uuid4()),
            "customer_id": command.customer_id,
            "total": command.total,
            "status": "pending",
            "items": command.items,
        }

        return order

    def _get_generated_events(self, command, result):
        """Emit events."""
        return [
            {
                "aggregate_id": result["id"],
                "event_type": "order.created",
                "data": {
                    "customer_id": result["customer_id"],
                    "total": result["total"],
                },
            }
        ]


# ============================================================================
# QUERIES & HANDLERS
# ============================================================================

class GetOrderQueryModel(BaseModel):
    order_id: str


class GetOrderHandler(EndpointQueryHandler):
    """Handler for GetOrder query."""

    async def _execute(self, query) -> dict:
        """Execute order retrieval."""
        logger.info(f"Getting order {query.order_id}")

        # Simulate database query
        return {
            "id": query.order_id,
            "customer_id": "customer_123",
            "total": 100.00,
            "status": "confirmed",
        }


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/", response_model=dict)
async def create_order(
    request: Request,
    payload: CreateOrderCommandModel,
):
    """Create a new order using CQRS pattern."""
    try:
        # Create command
        command = CreateOrderCommandModel(**payload.dict())
        command.command_id = str(uuid.uuid4())
        command.user_id = getattr(request.state, "user_id", None)
        command.request_id = getattr(request.state, "request_id", None)

        # Get handler and execute
        handler = CreateOrderHandler()
        result = await handler.handle(command)

        # Trigger saga for order processing
        saga = OrderSaga()
        orchestrator = get_saga_orchestrator()
        saga_instance = await orchestrator.execute_saga(
            saga,
            context={"order_id": result["result"]["id"]},
            user_id=command.user_id,
            request_id=command.request_id,
        )

        # Enqueue email job
        job_queue = get_job_queue()
        await job_queue.enqueue(
            Job(
                job_type="send_email",
                data={
                    "to": payload.customer_id,
                    "subject": "Order Confirmation",
                    "template": "order_confirmation",
                },
                priority=JobPriority.HIGH,
            )
        )

        return {
            "success": True,
            "order": result["result"],
            "saga_id": saga_instance.saga_id,
        }

    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{order_id}", response_model=dict)
async def get_order(
    request: Request,
    order_id: str,
):
    """Get order details using CQRS pattern."""
    try:
        # Create query
        query = GetOrderQueryModel(order_id=order_id)
        query.query_id = str(uuid.uuid4())
        query.user_id = getattr(request.state, "user_id", None)
        query.request_id = getattr(request.state, "request_id", None)

        # Get handler and execute
        handler = GetOrderHandler()
        result = await handler.handle(query)

        return {
            "success": True,
            "order": result["result"],
        }

    except Exception as e:
        logger.error(f"Failed to get order: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{order_id}/saga-status", response_model=dict)
async def get_order_saga_status(
    request: Request,
    order_id: str,
):
    """Get saga status for an order."""
    try:
        orchestrator = get_saga_orchestrator()
        user_sagas = orchestrator.get_user_sagas(
            getattr(request.state, "user_id", None)
        )

        matching_saga = next(
            (s for s in user_sagas if order_id in str(s.context)),
            None
        )

        if not matching_saga:
            raise HTTPException(status_code=404, detail="Saga not found")

        return {
            "success": True,
            "saga": matching_saga.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get saga status: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/saga/{saga_id}", response_model=dict)
async def admin_get_saga(
    request: Request,
    saga_id: str,
):
    """Admin endpoint to get saga details."""
    try:
        orchestrator = get_saga_orchestrator()
        saga = orchestrator.get_saga_status(saga_id)

        if not saga:
            raise HTTPException(status_code=404, detail="Saga not found")

        return {
            "success": True,
            "saga": saga.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get saga: {e}")
        raise HTTPException(status_code=400, detail=str(e))
