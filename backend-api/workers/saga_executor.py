"""Background worker para executar Sagas assincronamente.

Este worker:
1. Processa sagas em background
2. Executa steps multi-phase
3. Aplica compensação automática em falhas
4. Retorna resultado via webhook
5. Loga em DLQ em caso de falha irrecuperável
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4

from core.saga_pattern import (
    SagaDefinition,
    SagaStatus,
    StepStatus,
    get_orchestrator,
    get_saga_repository,
)
from core.resilience import log_dlq_event

logger = logging.getLogger("diomika-saga-worker")


class SagaExecutor:
    """Executa sagas em background com retry e compensação automática."""

    def __init__(self):
        self.orchestrator = get_orchestrator()
        self.repository = get_saga_repository()

    async def execute_saga(
        self,
        saga_id: str,
        webhook_url: Optional[str] = None,
        max_retries: int = 3,
    ) -> dict:
        """Executa saga com retry e webhook callback."""
        saga = self.repository.get(saga_id)
        if not saga:
            logger.error(f"Saga {saga_id} not found")
            return {"status": "failed", "reason": "saga_not_found"}

        logger.info(f"[SAGA] Starting execution of {saga.name} (ID: {saga_id})")

        for attempt in range(max_retries):
            try:
                # Executa saga via orchestrator
                result = await self.orchestrator.execute_saga(saga)

                if result:
                    logger.info(f"[SAGA] {saga_id} completed successfully")
                    status = "completed"
                else:
                    logger.warning(f"[SAGA] {saga_id} failed but was compensated")
                    status = "compensated"

                # Webhook callback
                if webhook_url:
                    await self._send_webhook(
                        webhook_url,
                        {
                            "saga_id": saga_id,
                            "status": status,
                            "completed_at": datetime.utcnow().isoformat(),
                            "steps": len(saga.steps),
                            "failed_at": saga.failed_at.isoformat() if saga.failed_at else None,
                        },
                    )

                return {"status": status, "saga_id": saga_id}

            except Exception as exc:
                logger.error(f"[SAGA] {saga_id} attempt {attempt + 1}/{max_retries} failed: {exc}")

                if attempt == max_retries - 1:
                    # Final attempt failed - log to DLQ
                    log_dlq_event(
                        event_type="saga_execution_failed",
                        data={
                            "saga_id": saga_id,
                            "saga_name": saga.name,
                            "steps_completed": sum(1 for s in saga.steps if s.status == StepStatus.COMPLETED),
                            "error": str(exc),
                            "attempts": max_retries,
                        },
                    )

                    # Webhook com erro
                    if webhook_url:
                        await self._send_webhook(
                            webhook_url,
                            {
                                "saga_id": saga_id,
                                "status": "failed",
                                "error": str(exc),
                                "attempts": max_retries,
                                "failed_at": datetime.utcnow().isoformat(),
                            },
                        )

                    return {"status": "failed", "saga_id": saga_id, "error": str(exc)}

                # Retry com backoff
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"[SAGA] Retrying {saga_id} in {wait_time}s...")
                await asyncio.sleep(wait_time)

    async def execute_saga_step(
        self,
        saga_id: str,
        step_index: int,
    ) -> dict:
        """Executa um step específico de uma saga."""
        saga = self.repository.get(saga_id)
        if not saga:
            return {"status": "failed", "reason": "saga_not_found"}

        if step_index >= len(saga.steps):
            return {"status": "failed", "reason": "invalid_step_index"}

        step = saga.steps[step_index]
        logger.info(f"[SAGA] Executing step {step_index + 1}/{len(saga.steps)}: {step.name}")

        try:
            # Execute step
            step.status = StepStatus.EXECUTING
            if asyncio.iscoroutinefunction(step.action):
                result = await step.action()
            else:
                result = step.action()

            step.result = result
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.utcnow()

            logger.info(f"[SAGA] Step {step.name} completed successfully")
            return {"status": "completed", "step": step.name, "result": result}

        except Exception as exc:
            step.status = StepStatus.FAILED
            step.error = exc
            logger.error(f"[SAGA] Step {step.name} failed: {exc}")

            # Log to DLQ
            log_dlq_event(
                event_type="saga_step_failed",
                data={
                    "saga_id": saga_id,
                    "step_name": step.name,
                    "step_index": step_index,
                    "error": str(exc),
                },
            )

            return {"status": "failed", "step": step.name, "error": str(exc)}

    async def _send_webhook(self, url: str, data: dict) -> None:
        """Envia resultado via webhook."""
        try:
            import httpx  # dependência de produção (aiohttp não está na imagem)

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=data)
                if resp.status_code != 200:
                    logger.warning(f"Webhook {url} returned {resp.status_code}")
        except Exception as exc:
            logger.error(f"Failed to send webhook to {url}: {exc}")


class SagaWorkerPool:
    """Pool de workers para processar múltiplas sagas em paralelo."""

    def __init__(self, num_workers: int = 5):
        self.num_workers = num_workers
        self.executor = SagaExecutor()
        self.pending_sagas: list[tuple[str, Optional[str]]] = []

    async def add_saga(self, saga_id: str, webhook_url: Optional[str] = None) -> None:
        """Adiciona saga à fila de processamento."""
        self.pending_sagas.append((saga_id, webhook_url))
        logger.info(f"Added saga {saga_id} to queue (total: {len(self.pending_sagas)})")

    async def process_pending_sagas(self) -> None:
        """Processa todas as sagas pendentes em paralelo."""
        while self.pending_sagas:
            # Get batch of sagas
            batch = self.pending_sagas[: self.num_workers]
            self.pending_sagas = self.pending_sagas[self.num_workers :]

            # Execute in parallel
            tasks = [
                self.executor.execute_saga(saga_id, webhook_url)
                for saga_id, webhook_url in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (saga_id, _), result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(f"Saga {saga_id} error: {result}")
                else:
                    logger.info(f"Saga {saga_id} result: {result}")

    async def run(self) -> None:
        """Executa worker pool continuamente."""
        logger.info(f"[SAGA WORKER] Starting with {self.num_workers} workers")

        while True:
            if self.pending_sagas:
                await self.process_pending_sagas()
            else:
                # Aguarda 1s antes de próxima verificação
                await asyncio.sleep(1)


# Global instance
_saga_executor: Optional[SagaExecutor] = None
_worker_pool: Optional[SagaWorkerPool] = None


def get_saga_executor() -> SagaExecutor:
    """Get global saga executor."""
    global _saga_executor
    if _saga_executor is None:
        _saga_executor = SagaExecutor()
    return _saga_executor


def get_saga_worker_pool(num_workers: int = 5) -> SagaWorkerPool:
    """Get global saga worker pool."""
    global _worker_pool
    if _worker_pool is None:
        _worker_pool = SagaWorkerPool(num_workers)
    return _worker_pool


async def background_saga_processor(check_interval: int = 5) -> None:
    """Background task para processar sagas periodicamente."""
    executor = get_saga_executor()
    orchestrator = get_orchestrator()
    repository = get_saga_repository()

    logger.info("[SAGA PROCESSOR] Starting background processor")

    while True:
        try:
            # Get pending sagas
            pending = repository.find_by_status(SagaStatus.PENDING)
            for saga in pending:
                logger.debug(f"Processing pending saga {saga.saga_id}")
                await executor.execute_saga(saga.saga_id)

            # Get sagas that need compensation
            failed = repository.find_by_status(SagaStatus.FAILED)
            for saga in failed:
                logger.debug(f"Retrying failed saga {saga.saga_id}")
                await executor.execute_saga(saga.saga_id, max_retries=1)

            await asyncio.sleep(check_interval)

        except Exception as exc:
            logger.error(f"[SAGA PROCESSOR] Error: {exc}", exc_info=True)
            await asyncio.sleep(check_interval)
