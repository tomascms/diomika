"""CQRS integration layer para admin_crud — adapta handlers assíncronos em sync endpoints.

Este módulo fornece wrappers síncronos que chamam os handlers CQRS assíncronos
e integram com:
- Audit logging (AuditTrail)
- Cache invalidation (GranularCacheInvalidator)
- Rate limiting
- Outbox pattern (event publishing)
- Error handling com DLQ
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from uuid import uuid4

from fastapi import Request

from core.audit_trail import AuditTrail, AuditAction, AuditResult
from core.cache_invalidation_strategy import GranularCacheInvalidator, CacheInvalidationAnalyzer
from core.cqrs_admin_handlers import (
    CreateEntityCommand,
    UpdateEntityCommand,
    DeleteEntityCommand,
    CreateEntityHandler,
    UpdateEntityHandler,
    DeleteEntityHandler,
)
from core.database import get_db
from core.outbox_pattern import get_outbox_store
from core.resilience import log_dlq_event
from core.request_context import get_request_context

logger = logging.getLogger("diomika-cqrs-integration")


class CQRSAdminIntegration:
    """Integração CQRS para operações CRUD — adapta async handlers em sync endpoints."""

    def __init__(self):
        self.audit = AuditTrail()
        self.cache_invalidator = GranularCacheInvalidator()
        self.outbox_store = get_outbox_store()

    def _run_async(self, coro):
        """Executa coroutine assíncrona em contexto síncrono."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Já há loop rodando (FastAPI context)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return loop.run_in_executor(executor, asyncio.run, coro)
            else:
                return asyncio.run(coro)
        except RuntimeError:
            return asyncio.run(coro)

    async def create_entity_async(
        self,
        request: Request,
        table_name: str,
        data: dict[str, Any],
        idempotency_key: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """CREATE entity via CQRS command com audit trail completo."""
        request_context = get_request_context()
        user_id = request_context.user_id if request_context else "system"
        request_id = request_context.request_id if request_context else str(uuid4())

        command = CreateEntityCommand(
            command_id=str(uuid4()),
            table_name=table_name,
            data=data,
            user_id=user_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

        handler = CreateEntityHandler()
        try:
            # Executa handler
            result = await handler.handle(command)
            record_id = result.get("id")

            # Log audit
            self.audit.log_create(
                action=AuditAction.CREATE,
                result=AuditResult.SUCCESS,
                user_id=user_id,
                resource_type=table_name,
                resource_id=record_id,
                request_id=request_id,
                ip_address=ip_address,
                details={"columns_created": len(data)},
            )

            # Cache invalidation
            strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
                table_name,
                old_record=None,
                new_record=result,
            )
            count = self.cache_invalidator.execute_strategy(
                strategy,
                table_name=table_name,
                tipo=result.get("tipo_catalogo"),
                id_modelo=result.get("id_modelo"),
                id_categoria=result.get("id_categoria"),
                record_id=record_id,
            )
            logger.debug(f"Cache invalidated {count} keys using {strategy.value} strategy")

            # Emit event
            self.outbox_store.add_event(
                {
                    "event_type": f"{table_name}.created",
                    "aggregate_id": record_id,
                    "aggregate_type": table_name,
                    "payload": result,
                    "user_id": user_id,
                    "request_id": request_id,
                }
            )

            logger.info(f"[CREATE] {table_name}/{record_id} completed successfully")
            return result

        except Exception as exc:
            logger.error(f"[CREATE] {table_name} failed: {exc}")

            # Log audit failure
            self.audit.log_create(
                action=AuditAction.CREATE,
                result=AuditResult.FAILURE,
                user_id=user_id,
                resource_type=table_name,
                request_id=request_id,
                ip_address=ip_address,
                error_message=str(exc),
            )

            # Log DLQ
            log_dlq_event(
                event_type=f"{table_name}.create_failed",
                data={"command": command.__dict__, "error": str(exc)},
                user_id=user_id,
            )

            raise

    async def update_entity_async(
        self,
        request: Request,
        table_name: str,
        entity_id: str,
        data: dict[str, Any],
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """UPDATE entity via CQRS command com audit trail completo."""
        request_context = get_request_context()
        user_id = request_context.user_id if request_context else "system"
        request_id = request_context.request_id if request_context else str(uuid4())

        # Get old record for change tracking
        db = get_db()
        old_record_res = db.table(table_name).select("*").eq("id", entity_id).limit(1).execute()
        old_record = (old_record_res.data or [{}])[0] if old_record_res.data else {}

        command = UpdateEntityCommand(
            command_id=str(uuid4()),
            table_name=table_name,
            entity_id=entity_id,
            data=data,
            user_id=user_id,
            request_id=request_id,
        )

        handler = UpdateEntityHandler()
        try:
            # Executa handler
            result = await handler.handle(command)

            # Log audit com changes
            self.audit.log_update(
                action=AuditAction.UPDATE,
                result=AuditResult.SUCCESS,
                user_id=user_id,
                resource_type=table_name,
                resource_id=entity_id,
                request_id=request_id,
                ip_address=ip_address,
                old_values=old_record,
                new_values=result,
                changes={k: (old_record.get(k), result.get(k)) for k in data.keys()},
            )

            # Cache invalidation
            strategy = CacheInvalidationAnalyzer.get_strategy_for_change(
                table_name,
                old_record=old_record,
                new_record=result,
            )
            count = self.cache_invalidator.execute_strategy(
                strategy,
                table_name=table_name,
                tipo=result.get("tipo_catalogo"),
                id_modelo=result.get("id_modelo"),
                id_categoria=result.get("id_categoria"),
                record_id=entity_id,
            )
            logger.debug(f"Cache invalidated {count} keys using {strategy.value} strategy")

            # Emit event
            self.outbox_store.add_event(
                {
                    "event_type": f"{table_name}.updated",
                    "aggregate_id": entity_id,
                    "aggregate_type": table_name,
                    "payload": result,
                    "user_id": user_id,
                    "request_id": request_id,
                }
            )

            logger.info(f"[UPDATE] {table_name}/{entity_id} completed successfully")
            return result

        except Exception as exc:
            logger.error(f"[UPDATE] {table_name}/{entity_id} failed: {exc}")

            # Log audit failure
            self.audit.log_update(
                action=AuditAction.UPDATE,
                result=AuditResult.FAILURE,
                user_id=user_id,
                resource_type=table_name,
                resource_id=entity_id,
                request_id=request_id,
                ip_address=ip_address,
                error_message=str(exc),
            )

            # Log DLQ
            log_dlq_event(
                event_type=f"{table_name}.update_failed",
                data={"command": command.__dict__, "error": str(exc)},
                user_id=user_id,
            )

            raise

    async def delete_entity_async(
        self,
        request: Request,
        table_name: str,
        entity_id: str,
        hard_delete: bool = False,
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """DELETE entity via CQRS command com audit trail completo."""
        request_context = get_request_context()
        user_id = request_context.user_id if request_context else "system"
        request_id = request_context.request_id if request_context else str(uuid4())

        # Get old record for audit
        db = get_db()
        old_record_res = db.table(table_name).select("*").eq("id", entity_id).limit(1).execute()
        old_record = (old_record_res.data or [{}])[0] if old_record_res.data else {}

        command = DeleteEntityCommand(
            command_id=str(uuid4()),
            table_name=table_name,
            entity_id=entity_id,
            user_id=user_id,
            request_id=request_id,
            hard_delete=hard_delete,
        )

        handler = DeleteEntityHandler()
        try:
            # Executa handler
            result = await handler.handle(command)

            # Log audit
            action = AuditAction.DELETE if hard_delete else AuditAction.DELETE
            self.audit.log_delete(
                action=action,
                result=AuditResult.SUCCESS,
                user_id=user_id,
                resource_type=table_name,
                resource_id=entity_id,
                request_id=request_id,
                ip_address=ip_address,
                old_values=old_record,
            )

            # Cache invalidation
            self.cache_invalidator.invalidate_surgical(
                table_name=table_name,
                record_id=entity_id,
                tipo=old_record.get("tipo_catalogo"),
                id_modelo=old_record.get("id_modelo"),
                id_categoria=old_record.get("id_categoria"),
            )

            # Emit event
            delete_type = "hard_deleted" if hard_delete else "soft_deleted"
            self.outbox_store.add_event(
                {
                    "event_type": f"{table_name}.{delete_type}",
                    "aggregate_id": entity_id,
                    "aggregate_type": table_name,
                    "payload": {"deleted": True, "hard": hard_delete},
                    "user_id": user_id,
                    "request_id": request_id,
                }
            )

            logger.info(f"[DELETE] {table_name}/{entity_id} ({delete_type}) completed successfully")
            return result

        except Exception as exc:
            logger.error(f"[DELETE] {table_name}/{entity_id} failed: {exc}")

            # Log audit failure
            self.audit.log_delete(
                action=AuditAction.DELETE,
                result=AuditResult.FAILURE,
                user_id=user_id,
                resource_type=table_name,
                resource_id=entity_id,
                request_id=request_id,
                ip_address=ip_address,
                error_message=str(exc),
            )

            # Log DLQ
            log_dlq_event(
                event_type=f"{table_name}.delete_failed",
                data={"command": command.__dict__, "error": str(exc)},
                user_id=user_id,
            )

            raise

    # Sync wrappers para endpoints FastAPI
    def create_entity(
        self,
        request: Request,
        table_name: str,
        data: dict[str, Any],
        idempotency_key: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """Sync wrapper para create."""
        return self._run_async(
            self.create_entity_async(request, table_name, data, idempotency_key, ip_address)
        )

    def update_entity(
        self,
        request: Request,
        table_name: str,
        entity_id: str,
        data: dict[str, Any],
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """Sync wrapper para update."""
        return self._run_async(
            self.update_entity_async(request, table_name, entity_id, data, ip_address)
        )

    def delete_entity(
        self,
        request: Request,
        table_name: str,
        entity_id: str,
        hard_delete: bool = False,
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """Sync wrapper para delete."""
        return self._run_async(
            self.delete_entity_async(request, table_name, entity_id, hard_delete, ip_address)
        )


# Global instance
_cqrs_integration: Optional[CQRSAdminIntegration] = None


def get_cqrs_integration() -> CQRSAdminIntegration:
    """Get global CQRS integration instance."""
    global _cqrs_integration
    if _cqrs_integration is None:
        _cqrs_integration = CQRSAdminIntegration()
    return _cqrs_integration
