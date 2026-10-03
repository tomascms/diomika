"""CQRS handlers para operações CRUD do backoffice — integração real com audit, events, cache."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.audit_trail import AuditTrail
from core.cache_invalidation_strategy import GranularCacheInvalidator, CacheInvalidationAnalyzer
from core.cqrs import Command, CommandHandler
from core.database import get_db
from core.outbox import enqueue_event
from core.rate_limiting import RateLimitCounter
from core.resilience import log_dlq_event

logger = logging.getLogger("diomika-cqrs")


@dataclass
class CreateEntityCommand(Command):
    """Comando: criar entidade."""
    table_name: str
    data: dict[str, Any]
    user_id: str
    request_id: str
    idempotency_key: Optional[str] = None


@dataclass
class UpdateEntityCommand(Command):
    """Comando: atualizar entidade."""
    table_name: str
    entity_id: str
    data: dict[str, Any]
    user_id: str
    request_id: str
    idempotency_key: Optional[str] = None


@dataclass
class DeleteEntityCommand(Command):
    """Comando: eliminar entidade (soft delete por default)."""
    table_name: str
    entity_id: str
    user_id: str
    request_id: str
    hard_delete: bool = False


class CreateEntityHandler(CommandHandler):
    """Handler: criar nova entidade com audit trail."""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or get_db()
        self.audit = AuditTrail()
        self.cache_invalidator = GranularCacheInvalidator()
        self.rate_limiter = RateLimitCounter()

    async def handle(self, command: CreateEntityCommand) -> dict[str, Any]:
        """Execute command: CREATE operation com audit + cache invalidation."""
        command_id = str(uuid4())
        logger.info(
            f"[CREATE] table={command.table_name}, user={command.user_id}, "
            f"request={command.request_id}, cmd_id={command_id}"
        )

        # Rate limiting check
        key = f"create:{command.table_name}:{command.user_id}"
        if self.rate_limiter.is_limited(key, limit=100, window_seconds=60):
            logger.warning(f"Rate limit exceeded for {key}")
            raise Exception(f"Rate limit exceeded for table {command.table_name}")

        try:
            # Insert record (Supabase)
            data_with_meta = {
                **command.data,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": command.user_id,
            }

            result = self.db.table(command.table_name).insert(data_with_meta).execute()
            entity = result.data[0]
            entity_id = entity.get("id")

            logger.info(f"[CREATE] SUCCESS entity_id={entity_id}")

            # Audit trail
            self.audit.log(
                action="CREATE",
                table=command.table_name,
                entity_id=entity_id,
                user_id=command.user_id,
                request_id=command.request_id,
                changes=command.data,
                status="success",
            )

            # Event emission
            await enqueue_event(
                event_type=f"{command.table_name}.created",
                payload={
                    "entity_id": entity_id,
                    "table": command.table_name,
                    "data": command.data,
                    "user_id": command.user_id,
                    "command_id": command_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            # Cache invalidation
            self.cache_invalidator.invalidate_entity(command.table_name, entity_id)
            self.cache_invalidator.invalidate_list(command.table_name)

            return {"id": entity_id, "status": "created", "command_id": command_id}

        except Exception as exc:
            logger.error(f"[CREATE] FAILED: {exc}", exc_info=True)

            # Audit trail (failed)
            self.audit.log(
                action="CREATE",
                table=command.table_name,
                user_id=command.user_id,
                request_id=command.request_id,
                changes=command.data,
                status="failed",
                error=str(exc),
            )

            # DLQ log
            log_dlq_event("CQRS_CREATE", command_id, exc)

            raise


class UpdateEntityHandler(CommandHandler):
    """Handler: atualizar entidade com audit trail."""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or get_db()
        self.audit = AuditTrail()
        self.cache_invalidator = GranularCacheInvalidator()
        self.rate_limiter = RateLimitCounter()

    async def handle(self, command: UpdateEntityCommand) -> dict[str, Any]:
        """Execute command: UPDATE operation com audit + cache invalidation."""
        command_id = str(uuid4())
        logger.info(
            f"[UPDATE] table={command.table_name}, entity_id={command.entity_id}, "
            f"user={command.user_id}, request={command.request_id}, cmd_id={command_id}"
        )

        # Rate limiting check
        key = f"update:{command.table_name}:{command.user_id}"
        if self.rate_limiter.is_limited(key, limit=200, window_seconds=60):
            logger.warning(f"Rate limit exceeded for {key}")
            raise Exception(f"Rate limit exceeded for table {command.table_name}")

        try:
            # Fetch current state (para audit diff)
            current = self.db.table(command.table_name).select("*").eq("id", command.entity_id).execute()
            if not current.data:
                raise ValueError(f"Entity not found: {command.entity_id}")

            old_state = current.data[0]

            # Update record
            data_with_meta = {
                **command.data,
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": command.user_id,
            }

            result = self.db.table(command.table_name).update(data_with_meta).eq("id", command.entity_id).execute()
            entity = result.data[0]

            logger.info(f"[UPDATE] SUCCESS entity_id={command.entity_id}")

            # Audit trail (com diff)
            self.audit.log(
                action="UPDATE",
                table=command.table_name,
                entity_id=command.entity_id,
                user_id=command.user_id,
                request_id=command.request_id,
                changes=command.data,
                old_state=old_state,
                new_state=entity,
                status="success",
            )

            # Event emission
            await enqueue_event(
                event_type=f"{command.table_name}.updated",
                payload={
                    "entity_id": command.entity_id,
                    "table": command.table_name,
                    "old_data": old_state,
                    "new_data": command.data,
                    "user_id": command.user_id,
                    "command_id": command_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            # Cache invalidation
            self.cache_invalidator.invalidate_entity(command.table_name, command.entity_id)
            self.cache_invalidator.invalidate_list(command.table_name)

            return {"id": command.entity_id, "status": "updated", "command_id": command_id}

        except Exception as exc:
            logger.error(f"[UPDATE] FAILED: {exc}", exc_info=True)

            # Audit trail (failed)
            self.audit.log(
                action="UPDATE",
                table=command.table_name,
                entity_id=command.entity_id,
                user_id=command.user_id,
                request_id=command.request_id,
                changes=command.data,
                status="failed",
                error=str(exc),
            )

            # DLQ log
            log_dlq_event("CQRS_UPDATE", command_id, exc)

            raise


class DeleteEntityHandler(CommandHandler):
    """Handler: eliminar entidade (soft delete por default)."""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or get_db()
        self.audit = AuditTrail()
        self.cache_invalidator = GranularCacheInvalidator()
        self.rate_limiter = RateLimitCounter()

    async def handle(self, command: DeleteEntityCommand) -> dict[str, Any]:
        """Execute command: DELETE operation (soft or hard) com audit."""
        command_id = str(uuid4())
        logger.info(
            f"[DELETE] table={command.table_name}, entity_id={command.entity_id}, "
            f"user={command.user_id}, hard_delete={command.hard_delete}, cmd_id={command_id}"
        )

        # Rate limiting check
        key = f"delete:{command.table_name}:{command.user_id}"
        if self.rate_limiter.is_limited(key, limit=50, window_seconds=60):
            logger.warning(f"Rate limit exceeded for {key}")
            raise Exception(f"Rate limit exceeded for table {command.table_name}")

        try:
            # Fetch current state
            current = self.db.table(command.table_name).select("*").eq("id", command.entity_id).execute()
            if not current.data:
                raise ValueError(f"Entity not found: {command.entity_id}")

            old_state = current.data[0]

            if command.hard_delete:
                # Hard delete (apenas permitido para admins)
                self.db.table(command.table_name).delete().eq("id", command.entity_id).execute()
                logger.info(f"[DELETE] HARD SUCCESS entity_id={command.entity_id}")
                action = "HARD_DELETE"
            else:
                # Soft delete (defaul: marcar como deleted_at)
                self.db.table(command.table_name).update({
                    "deleted_at": datetime.utcnow().isoformat(),
                    "deleted_by": command.user_id,
                    "visibilidade": False,
                }).eq("id", command.entity_id).execute()
                logger.info(f"[DELETE] SOFT SUCCESS entity_id={command.entity_id}")
                action = "DELETE"

            # Audit trail
            self.audit.log(
                action=action,
                table=command.table_name,
                entity_id=command.entity_id,
                user_id=command.user_id,
                request_id=command.request_id,
                old_state=old_state,
                status="success",
            )

            # Event emission
            await enqueue_event(
                event_type=f"{command.table_name}.deleted",
                payload={
                    "entity_id": command.entity_id,
                    "table": command.table_name,
                    "old_data": old_state,
                    "user_id": command.user_id,
                    "hard_delete": command.hard_delete,
                    "command_id": command_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            # Cache invalidation
            self.cache_invalidator.invalidate_entity(command.table_name, command.entity_id)
            self.cache_invalidator.invalidate_list(command.table_name)

            return {"id": command.entity_id, "status": "deleted", "command_id": command_id}

        except Exception as exc:
            logger.error(f"[DELETE] FAILED: {exc}", exc_info=True)

            # Audit trail (failed)
            self.audit.log(
                action="DELETE",
                table=command.table_name,
                entity_id=command.entity_id,
                user_id=command.user_id,
                request_id=command.request_id,
                status="failed",
                error=str(exc),
            )

            # DLQ log
            log_dlq_event("CQRS_DELETE", command_id, exc)

            raise


# Global command bus registry
_command_handlers = {
    CreateEntityCommand: CreateEntityHandler,
    UpdateEntityCommand: UpdateEntityHandler,
    DeleteEntityCommand: DeleteEntityHandler,
}


def get_command_handler(command_type: type) -> CommandHandler:
    """Get handler para tipo de comando."""
    handler_class = _command_handlers.get(command_type)
    if not handler_class:
        raise ValueError(f"No handler registered for {command_type}")
    return handler_class()
