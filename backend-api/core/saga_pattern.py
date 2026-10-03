"""Saga pattern for handling distributed transactions."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Any, Callable, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("diomika-api")


class SagaStatus(Enum):
    """Saga execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"


class StepStatus(Enum):
    """Individual step status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Individual step in a saga."""
    name: str
    action: Callable
    compensation: Callable
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class SagaDefinition:
    """Definition of a saga with steps and configurations."""
    saga_id: str
    name: str
    steps: List[SagaStep] = field(default_factory=list)
    status: SagaStatus = SagaStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    user_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def add_step(self, step: SagaStep) -> SagaDefinition:
        """Add a step to the saga."""
        self.steps.append(step)
        return self

    def is_completed(self) -> bool:
        """Check if saga is completed."""
        return self.status == SagaStatus.COMPLETED

    def is_failed(self) -> bool:
        """Check if saga failed."""
        return self.status == SagaStatus.FAILED

    def completion_percentage(self) -> float:
        """Get saga completion percentage."""
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return (completed / len(self.steps)) * 100


class SagaOrchestrator:
    """Orchestrates saga execution with compensation on failure."""

    def __init__(self):
        self.sagas: dict[str, SagaDefinition] = {}
        self.middleware: List[Callable] = []

    def create_saga(self, saga_id: str, name: str) -> SagaDefinition:
        """Create a new saga."""
        saga = SagaDefinition(saga_id=saga_id, name=name)
        self.sagas[saga_id] = saga
        logger.info(f"Created saga {name} (ID: {saga_id})")
        return saga

    def add_middleware(self, middleware: Callable):
        """Add middleware to saga pipeline."""
        self.middleware.append(middleware)

    async def execute_saga(self, saga: SagaDefinition) -> bool:
        """Execute saga with automatic compensation on failure."""
        saga.status = SagaStatus.RUNNING
        saga.started_at = datetime.utcnow()
        logger.info(f"Starting saga {saga.saga_id}")

        try:
            # Execute steps forward
            for i, step in enumerate(saga.steps):
                try:
                    step.status = StepStatus.EXECUTING
                    step.executed_at = datetime.utcnow()
                    logger.info(f"Executing step {i+1}/{len(saga.steps)}: {step.name}")

                    # Apply middleware
                    for middleware in self.middleware:
                        step = await middleware(step)

                    # Execute step
                    step.result = await self._execute_step(step.action)
                    step.status = StepStatus.COMPLETED
                    step.completed_at = datetime.utcnow()
                    logger.info(f"Step {step.name} completed successfully")

                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = e
                    logger.error(f"Step {step.name} failed: {str(e)}")

                    # Compensate previous steps in reverse order
                    await self._compensate_saga(saga, i - 1)

                    saga.status = SagaStatus.FAILED
                    saga.failed_at = datetime.utcnow()
                    saga.error_message = str(e)
                    raise

            # All steps completed successfully
            saga.status = SagaStatus.COMPLETED
            saga.completed_at = datetime.utcnow()
            logger.info(f"Saga {saga.saga_id} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Saga {saga.saga_id} failed: {str(e)}")
            return False

    async def _execute_step(self, action: Callable) -> Any:
        """Execute a step action."""
        if hasattr(action, "__await__"):
            return await action()
        else:
            return action()

    async def _compensate_saga(self, saga: SagaDefinition, last_step_index: int):
        """Compensate saga by running compensation in reverse order."""
        saga.status = SagaStatus.COMPENSATING
        logger.info(f"Starting compensation for saga {saga.saga_id}")

        for i in range(last_step_index, -1, -1):
            step = saga.steps[i]
            if step.status == StepStatus.COMPLETED:
                try:
                    logger.info(f"Compensating step {step.name}")
                    await self._execute_step(step.compensation)
                    step.status = StepStatus.COMPENSATED
                    logger.info(f"Step {step.name} compensated successfully")
                except Exception as e:
                    logger.error(f"Compensation of step {step.name} failed: {str(e)}")

    def get_saga(self, saga_id: str) -> Optional[SagaDefinition]:
        """Get saga by ID."""
        return self.sagas.get(saga_id)

    def list_sagas(self, status: Optional[SagaStatus] = None) -> List[SagaDefinition]:
        """List sagas, optionally filtered by status."""
        sagas = list(self.sagas.values())
        if status:
            sagas = [s for s in sagas if s.status == status]
        return sagas


class SagaTransaction:
    """Transaction builder for creating sagas fluently."""

    def __init__(self, saga_id: str, name: str):
        self.saga = SagaDefinition(saga_id=saga_id, name=name)

    def add_step(
        self,
        name: str,
        action: Callable,
        compensation: Callable,
    ) -> SagaTransaction:
        """Add a step to the transaction."""
        step = SagaStep(name=name, action=action, compensation=compensation)
        self.saga.add_step(step)
        return self

    def with_metadata(self, key: str, value: Any) -> SagaTransaction:
        """Add metadata to the saga."""
        self.saga.metadata[key] = value
        return self

    def build(self) -> SagaDefinition:
        """Build the saga."""
        return self.saga


class SagaRepository:
    """Repository for storing and retrieving saga definitions."""

    def __init__(self):
        self.storage: dict[str, SagaDefinition] = {}

    def save(self, saga: SagaDefinition):
        """Save saga to repository."""
        self.storage[saga.saga_id] = saga
        logger.info(f"Saved saga {saga.saga_id} to repository")

    def get(self, saga_id: str) -> Optional[SagaDefinition]:
        """Get saga from repository."""
        return self.storage.get(saga_id)

    def find_by_status(self, status: SagaStatus) -> List[SagaDefinition]:
        """Find sagas by status."""
        return [s for s in self.storage.values() if s.status == status]

    def find_by_user(self, user_id: str) -> List[SagaDefinition]:
        """Find sagas by user."""
        return [s for s in self.storage.values() if s.user_id == user_id]

    def delete(self, saga_id: str):
        """Delete saga from repository."""
        if saga_id in self.storage:
            del self.storage[saga_id]
            logger.info(f"Deleted saga {saga_id} from repository")


# Global orchestrator and repository
_orchestrator: Optional[SagaOrchestrator] = None
_repository: Optional[SagaRepository] = None


def get_orchestrator() -> SagaOrchestrator:
    """Get global saga orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SagaOrchestrator()
    return _orchestrator


def get_saga_repository() -> SagaRepository:
    """Get global saga repository."""
    global _repository
    if _repository is None:
        _repository = SagaRepository()
    return _repository
