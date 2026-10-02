"""Request context management for FastAPI."""
from __future__ import annotations

import logging
from typing import Optional, Any, Dict
from contextvars import ContextVar
from uuid import uuid4
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger("diomika-api")

# Context variables
_request_context: ContextVar[RequestContext] = ContextVar("request_context", default=None)


@dataclass
class RequestContext:
    """Context information for a single request."""
    request_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_roles: list[str] = field(default_factory=list)
    ip_address: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None

    def set_user(self, user_id: str, user_email: str = "", roles: list[str] = None):
        """Set user information in context."""
        self.user_id = user_id
        self.user_email = user_email
        self.user_roles = roles or []

    def add_metadata(self, key: str, value: Any):
        """Add metadata to context."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from context."""
        return self.metadata.get(key, default)

    def is_admin(self) -> bool:
        """Check if user is admin."""
        return "admin" in self.user_roles

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.user_id is not None

    def get_duration_ms(self) -> float:
        """Get request duration in milliseconds."""
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return (datetime.utcnow() - self.started_at).total_seconds() * 1000


def get_request_context() -> Optional[RequestContext]:
    """Get current request context."""
    return _request_context.get()


def set_request_context(context: RequestContext) -> None:
    """Set current request context."""
    _request_context.set(context)


def create_request_context(
    request_id: str = None,
    user_id: str = None,
    ip_address: str = None,
    method: str = None,
    path: str = None,
) -> RequestContext:
    """Create and set new request context."""
    context = RequestContext(
        request_id=request_id or str(uuid4()),
        user_id=user_id,
        ip_address=ip_address,
        method=method,
        path=path,
    )
    set_request_context(context)
    logger.debug(f"Created request context {context.request_id}")
    return context


class ContextMiddleware:
    """Middleware to create and manage request context."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request, call_next):
        # Create new context
        context = create_request_context(
            user_id=getattr(request.state, "user_id", None),
            ip_address=request.client.host if request.client else None,
            method=request.method,
            path=request.url.path,
        )

        # Check for idempotency key
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            context.idempotency_key = idempotency_key

        # Check for correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if correlation_id:
            context.correlation_id = correlation_id

        # Copy request_id from middleware if available
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            context.request_id = request_id

        # Execute request
        response = await call_next(request)

        # Update context with response info
        context.status_code = response.status_code
        context.completed_at = datetime.utcnow()
        context.response_time_ms = context.get_duration_ms()

        # Log completion
        logger.debug(
            f"Request {context.request_id} completed with status {context.status_code} "
            f"in {context.response_time_ms:.1f}ms"
        )

        return response


class RequestContextDependency:
    """FastAPI dependency for injecting request context."""

    async def __call__(self) -> Optional[RequestContext]:
        return get_request_context()


def get_request_id() -> str:
    """Get current request ID."""
    context = get_request_context()
    return context.request_id if context else "unknown"


def get_user_id() -> Optional[str]:
    """Get current user ID."""
    context = get_request_context()
    return context.user_id if context else None


def get_ip_address() -> Optional[str]:
    """Get current IP address."""
    context = get_request_context()
    return context.ip_address if context else None


def is_authenticated() -> bool:
    """Check if current request is authenticated."""
    context = get_request_context()
    return context.is_authenticated() if context else False


def is_admin() -> bool:
    """Check if current user is admin."""
    context = get_request_context()
    return context.is_admin() if context else False


def add_metadata(key: str, value: Any):
    """Add metadata to current request context."""
    context = get_request_context()
    if context:
        context.add_metadata(key, value)


def get_metadata(key: str, default: Any = None) -> Any:
    """Get metadata from current request context."""
    context = get_request_context()
    if context:
        return context.get_metadata(key, default)
    return default


class ContextLogger:
    """Logger wrapper that includes request context."""

    def __init__(self, logger_instance):
        self.logger = logger_instance

    def _get_context_info(self) -> dict:
        """Get current context info for logging."""
        context = get_request_context()
        if not context:
            return {}
        return {
            "request_id": context.request_id,
            "user_id": context.user_id,
            "ip_address": context.ip_address,
        }

    def debug(self, msg: str, *args, **kwargs):
        """Log debug with context."""
        extra = self._get_context_info()
        self.logger.debug(msg, *args, extra=extra, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info with context."""
        extra = self._get_context_info()
        self.logger.info(msg, *args, extra=extra, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning with context."""
        extra = self._get_context_info()
        self.logger.warning(msg, *args, extra=extra, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error with context."""
        extra = self._get_context_info()
        self.logger.error(msg, *args, extra=extra, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical with context."""
        extra = self._get_context_info()
        self.logger.critical(msg, *args, extra=extra, **kwargs)
