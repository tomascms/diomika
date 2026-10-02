"""Saga pattern coordinator for business process orchestration."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import uuid

from core.audit_trail import AuditTrail

logger = logging.getLogger("diomika-api")


class SagaStatus(Enum):
    """Saga execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class StepStatus(Enum):
    """Individual saga step status."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Represents a step in a saga."""
    name: str
    action: Callable
    compensation: Optional[Callable] = None
    timeout_seconds: int = 300
    retry_count: int = 3

    status: StepStatus = field(default=StepStatus.PENDING)
    result: Optional[Any] = None
    error: Optional[str] = None
    executed_at: Optional[datetime] = None
    compensated_at: Optional[datetime] = None


@dataclass
class SagaInstance:
    """Represents an instance of a saga."""
    saga_id: str
    saga_name: str
    user_id: Optional[str]
    request_id: Optional[str]

    status: SagaStatus = field(default=SagaStatus.PENDING)
    steps: List[SagaStep] = field(default_factory=list)
    current_step_index: int = 0

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "saga_id": self.saga_id,
            "saga_name": self.saga_name,
            "status": self.status.value,
            "current_step": self.current_step_index,
            "total_steps": len(self.steps),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status.value,
                    "error": step.error,
                }
                for step in self.steps
            ],
        }


class Saga(ABC):
    """Base class for sagas."""

    def __init__(self):
        self.steps: List[SagaStep] = []
        self.audit_trail = AuditTrail()

    @abstractmethod
    async def build_steps(self, context: Dict[str, Any]) -> List[SagaStep]:
        """Build saga steps. Must be implemented by subclasses."""
        pass

    async def execute(self, context: Dict[str, Any], user_id: Optional[str] = None, request_id: Optional[str] = None) -> SagaInstance:
        """Execute the saga."""
        saga_id = str(uuid.uuid4())
        saga_instance = SagaInstance(
            saga_id=saga_id,
            saga_name=self.__class__.__name__,
            user_id=user_id,
            request_id=request_id,
            context=context,
        )

        try:
            # Build steps
            saga_instance.steps = await self.build_steps(context)
            saga_instance.status = SagaStatus.RUNNING
            saga_instance.started_at = datetime.utcnow()

            logger.info(f"Starting saga {self.__class__.__name__} ({saga_id}) with {len(saga_instance.steps)} steps")

            # Execute steps
            for i, step in enumerate(saga_instance.steps):
                saga_instance.current_step_index = i

                try:
                    logger.info(f"Executing step {i+1}/{len(saga_instance.steps)}: {step.name}")
                    step.status = StepStatus.EXECUTING

                    # Execute with retries
                    step.result = await self._execute_with_retry(step)
                    step.status = StepStatus.SUCCESS
                    step.executed_at = datetime.utcnow()

                    logger.info(f"✓ Step {step.name} completed")

                except Exception as e:
                    logger.error(f"✗ Step {step.name} failed: {e}")
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    saga_instance.error = str(e)

                    # Start compensation
                    await self._compensate(saga_instance)
                    saga_instance.status = SagaStatus.FAILED
                    return saga_instance

            saga_instance.status = SagaStatus.COMPLETED
            saga_instance.completed_at = datetime.utcnow()

            logger.info(f"✓ Saga {self.__class__.__name__} completed successfully")

        except Exception as e:
            logger.error(f"Saga execution failed: {e}")
            saga_instance.status = SagaStatus.FAILED
            saga_instance.error = str(e)
            await self._compensate(saga_instance)

        return saga_instance

    async def _execute_with_retry(self, step: SagaStep) -> Any:
        """Execute a step with retries."""
        last_exception = None

        for attempt in range(step.retry_count):
            try:
                return await step.action()
            except Exception as e:
                last_exception = e
                logger.warning(f"Step {step.name} attempt {attempt+1}/{step.retry_count} failed: {e}")

                if attempt < step.retry_count - 1:
                    # Wait before retry (exponential backoff)
                    import asyncio
                    await asyncio.sleep(2 ** attempt)

        raise last_exception

    async def _compensate(self, saga_instance: SagaInstance):
        """Compensate (rollback) completed steps."""
        logger.info(f"Starting compensation for saga {saga_instance.saga_id}")
        saga_instance.status = SagaStatus.COMPENSATING

        # Compensate in reverse order
        for i in range(saga_instance.current_step_index, -1, -1):
            step = saga_instance.steps[i]

            if step.status != StepStatus.SUCCESS:
                continue

            if not step.compensation:
                logger.debug(f"No compensation for step {step.name}")
                continue

            try:
                logger.info(f"Compensating step {i+1}: {step.name}")
                step.status = StepStatus.COMPENSATING

                await step.compensation()

                step.status = StepStatus.COMPENSATED
                step.compensated_at = datetime.utcnow()
                logger.info(f"✓ Step {step.name} compensated")

            except Exception as e:
                logger.error(f"✗ Compensation for {step.name} failed: {e}")
                # Continue with other compensations

        saga_instance.status = SagaStatus.ROLLED_BACK
        logger.info(f"Compensation complete for saga {saga_instance.saga_id}")


class SagaOrchestrator:
    """Orchestrates saga execution and tracking."""

    def __init__(self):
        self.sagas: Dict[str, SagaInstance] = {}
        self.audit_trail = AuditTrail()

    async def execute_saga(
        self,
        saga: Saga,
        context: Dict[str, Any],
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SagaInstance:
        """Execute a saga and track it."""
        saga_instance = await saga.execute(context, user_id, request_id)
        self.sagas[saga_instance.saga_id] = saga_instance

        # Audit
        self.audit_trail.log_custom(
            event_type="saga_executed",
            data={
                "saga_id": saga_instance.saga_id,
                "saga_name": saga_instance.saga_name,
                "status": saga_instance.status.value,
            },
            user_id=user_id,
            request_id=request_id,
        )

        return saga_instance

    def get_saga_status(self, saga_id: str) -> Optional[SagaInstance]:
        """Get status of a saga."""
        return self.sagas.get(saga_id)

    def get_user_sagas(self, user_id: str) -> List[SagaInstance]:
        """Get all sagas for a user."""
        return [s for s in self.sagas.values() if s.user_id == user_id]


# Example: Order Saga
class OrderSaga(Saga):
    """Saga for order processing flow."""

    async def build_steps(self, context: Dict[str, Any]) -> List[SagaStep]:
        """Build order processing steps."""
        order_id = context.get("order_id")

        return [
            SagaStep(
                name="Reserve Inventory",
                action=lambda: self._reserve_inventory(order_id, context),
                compensation=lambda: self._release_inventory(order_id),
            ),
            SagaStep(
                name="Process Payment",
                action=lambda: self._process_payment(order_id, context),
                compensation=lambda: self._refund_payment(order_id),
            ),
            SagaStep(
                name="Confirm Order",
                action=lambda: self._confirm_order(order_id),
                compensation=lambda: self._cancel_order(order_id),
            ),
            SagaStep(
                name="Create Shipment",
                action=lambda: self._create_shipment(order_id),
                compensation=lambda: self._cancel_shipment(order_id),
            ),
        ]

    async def _reserve_inventory(self, order_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reserve inventory for order."""
        logger.info(f"Reserving inventory for order {order_id}")
        return {"reservation_id": str(uuid.uuid4())}

    async def _release_inventory(self, order_id: str):
        """Release reserved inventory."""
        logger.info(f"Releasing inventory for order {order_id}")

    async def _process_payment(self, order_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment for order."""
        logger.info(f"Processing payment for order {order_id}")
        return {"transaction_id": str(uuid.uuid4())}

    async def _refund_payment(self, order_id: str):
        """Refund payment for order."""
        logger.info(f"Refunding payment for order {order_id}")

    async def _confirm_order(self, order_id: str) -> Dict[str, Any]:
        """Confirm order."""
        logger.info(f"Confirming order {order_id}")
        return {"confirmed": True}

    async def _cancel_order(self, order_id: str):
        """Cancel order."""
        logger.info(f"Canceling order {order_id}")

    async def _create_shipment(self, order_id: str) -> Dict[str, Any]:
        """Create shipment for order."""
        logger.info(f"Creating shipment for order {order_id}")
        return {"shipment_id": str(uuid.uuid4())}

    async def _cancel_shipment(self, order_id: str):
        """Cancel shipment."""
        logger.info(f"Canceling shipment for order {order_id}")


# Global orchestrator
_orchestrator: Optional[SagaOrchestrator] = None


def get_saga_orchestrator() -> SagaOrchestrator:
    """Get global saga orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SagaOrchestrator()
    return _orchestrator
