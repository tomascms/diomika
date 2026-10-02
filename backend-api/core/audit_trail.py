"""Comprehensive audit trail logging for all operations."""
from __future__ import annotations

import logging
import json
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger("diomika-api")


class AuditAction(Enum):
    """Types of auditable actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    EXPORT = "export"
    IMPORT = "import"
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"
    SECURITY_EVENT = "security_event"


class AuditResult(Enum):
    """Result of audited action."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class AuditEntry:
    """Single audit trail entry."""
    timestamp: datetime
    action: AuditAction
    result: AuditResult
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    changes: dict = None
    old_values: dict = None
    new_values: dict = None
    error_message: Optional[str] = None
    details: dict = None
    affected_records: int = 0

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.changes is None:
            self.changes = {}
        if self.old_values is None:
            self.old_values = {}
        if self.new_values is None:
            self.new_values = {}
        if self.details is None:
            self.details = {}

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["action"] = self.action.value
        data["result"] = self.result.value
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Central audit logging manager."""

    @staticmethod
    def log_action(
        action: AuditAction,
        result: AuditResult,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        changes: Optional[dict] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        error_message: Optional[str] = None,
        details: Optional[dict] = None,
        affected_records: int = 0,
    ) -> AuditEntry:
        """Log an action to audit trail."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            action=action,
            result=result,
            user_id=user_id,
            user_email=user_email,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            request_id=request_id,
            ip_address=ip_address,
            changes=changes or {},
            old_values=old_values or {},
            new_values=new_values or {},
            error_message=error_message,
            details=details or {},
            affected_records=affected_records,
        )

        # Log to application logger
        log_level = logging.INFO if result == AuditResult.SUCCESS else logging.WARNING
        log_message = f"AUDIT [{action.value}] {resource_type or 'unknown'} - {result.value}"
        extra = entry.to_dict()
        logger.log(log_level, log_message, extra=extra)

        return entry

    @staticmethod
    def log_create(
        user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        resource_name: str = "",
        new_values: Optional[dict] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs
    ):
        """Log record creation."""
        return AuditLogger.log_action(
            action=AuditAction.CREATE,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            new_values=new_values or {},
            request_id=request_id,
            ip_address=ip_address,
            **kwargs
        )

    @staticmethod
    def log_update(
        user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        resource_name: str = "",
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        changes: Optional[dict] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs
    ):
        """Log record update."""
        return AuditLogger.log_action(
            action=AuditAction.UPDATE,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_values=old_values or {},
            new_values=new_values or {},
            changes=changes or {},
            request_id=request_id,
            ip_address=ip_address,
            **kwargs
        )

    @staticmethod
    def log_delete(
        user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        resource_name: str = "",
        old_values: Optional[dict] = None,
        affected_records: int = 1,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs
    ):
        """Log record deletion."""
        return AuditLogger.log_action(
            action=AuditAction.DELETE,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_values=old_values or {},
            affected_records=affected_records,
            request_id=request_id,
            ip_address=ip_address,
            **kwargs
        )

    @staticmethod
    def log_read(
        user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        resource_name: str = "",
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs
    ):
        """Log record read."""
        return AuditLogger.log_action(
            action=AuditAction.READ,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            request_id=request_id,
            ip_address=ip_address,
            **kwargs
        )

    @staticmethod
    def log_list(
        user_id: Optional[str],
        resource_type: str,
        affected_records: int = 0,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[dict] = None,
        **kwargs
    ):
        """Log list operation."""
        return AuditLogger.log_action(
            action=AuditAction.LIST,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            resource_type=resource_type,
            affected_records=affected_records,
            request_id=request_id,
            ip_address=ip_address,
            details=details or {},
            **kwargs
        )

    @staticmethod
    def log_error(
        action: AuditAction,
        user_id: Optional[str],
        resource_type: str,
        error_message: str,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs
    ):
        """Log action failure."""
        return AuditLogger.log_action(
            action=action,
            result=AuditResult.FAILURE,
            user_id=user_id,
            resource_type=resource_type,
            error_message=error_message,
            request_id=request_id,
            ip_address=ip_address,
            **kwargs
        )

    @staticmethod
    def log_auth(
        action: AuditAction,
        result: AuditResult,
        user_id: Optional[str],
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        error_message: Optional[str] = None,
        **kwargs
    ):
        """Log authentication/authorization events."""
        return AuditLogger.log_action(
            action=action,
            result=result,
            user_id=user_id,
            user_email=user_email,
            resource_type="auth",
            ip_address=ip_address,
            error_message=error_message,
            **kwargs
        )

    @staticmethod
    def log_security_event(
        event_type: str,
        result: AuditResult,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[dict] = None,
        **kwargs
    ):
        """Log security-related event."""
        return AuditLogger.log_action(
            action=AuditAction.SECURITY_EVENT,
            result=result,
            user_id=user_id,
            resource_type=f"security:{event_type}",
            request_id=request_id,
            ip_address=ip_address,
            details=details or {},
            **kwargs
        )

    @staticmethod
    def log_import(
        user_id: Optional[str],
        resource_type: str,
        affected_records: int,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[dict] = None,
        **kwargs
    ):
        """Log data import."""
        return AuditLogger.log_action(
            action=AuditAction.IMPORT,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            resource_type=f"import:{resource_type}",
            affected_records=affected_records,
            request_id=request_id,
            ip_address=ip_address,
            details=details or {},
            **kwargs
        )

    @staticmethod
    def log_export(
        user_id: Optional[str],
        resource_type: str,
        affected_records: int,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[dict] = None,
        **kwargs
    ):
        """Log data export."""
        return AuditLogger.log_action(
            action=AuditAction.EXPORT,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            resource_type=f"export:{resource_type}",
            affected_records=affected_records,
            request_id=request_id,
            ip_address=ip_address,
            details=details or {},
            **kwargs
        )


class AuditFilter(logging.Filter):
    """Logging filter to add request context to audit logs."""

    def filter(self, record):
        """Add audit metadata to log record."""
        if hasattr(record, "action"):
            record.audit_action = record.action
        return True
