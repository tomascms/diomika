"""Advanced error handling with custom exceptions and recovery strategies."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("diomika-api")


class ErrorSeverity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for routing and recovery."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMIT = "rate_limit"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    INTERNAL = "internal"
    TIMEOUT = "timeout"


@dataclass
class ErrorContext:
    """Error context for detailed logging."""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    user_id: Optional[str] = None
    resource: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = None
    details: dict = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.details is None:
            self.details = {}


class DiomikaException(Exception):
    """Base exception for Diomika API."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[dict] = None,
        http_status: int = 500,
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.user_id = user_id
        self.resource = resource
        self.request_id = request_id
        self.details = details or {}
        self.http_status = http_status
        self.context = ErrorContext(
            category=category,
            severity=severity,
            message=message,
            user_id=user_id,
            resource=resource,
            request_id=request_id,
            details=self.details,
        )
        super().__init__(self.message)


class ValidationException(DiomikaException):
    """Validation error."""

    def __init__(self, message: str, field: str = "", **kwargs):
        kwargs.setdefault("category", ErrorCategory.VALIDATION)
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("http_status", 422)
        if "details" not in kwargs:
            kwargs["details"] = {}
        if field:
            kwargs["details"]["field"] = field
        super().__init__(message, **kwargs)


class AuthenticationException(DiomikaException):
    """Authentication error."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("category", ErrorCategory.AUTHENTICATION)
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("http_status", 401)
        super().__init__(message, **kwargs)


class AuthorizationException(DiomikaException):
    """Authorization error."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("category", ErrorCategory.AUTHORIZATION)
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("http_status", 403)
        super().__init__(message, **kwargs)


class NotFoundException(DiomikaException):
    """Resource not found."""

    def __init__(self, message: str, resource: str = "", **kwargs):
        kwargs.setdefault("category", ErrorCategory.NOT_FOUND)
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("http_status", 404)
        kwargs["resource"] = resource
        super().__init__(message, **kwargs)


class ConflictException(DiomikaException):
    """Resource conflict (duplicate, state mismatch)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("category", ErrorCategory.CONFLICT)
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("http_status", 409)
        super().__init__(message, **kwargs)


class RateLimitException(DiomikaException):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        kwargs.setdefault("category", ErrorCategory.RATE_LIMIT)
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("http_status", 429)
        if "details" not in kwargs:
            kwargs["details"] = {}
        kwargs["details"]["retry_after"] = retry_after
        super().__init__(message, **kwargs)


class ExternalServiceException(DiomikaException):
    """External service unavailable or error."""

    def __init__(self, message: str, service: str = "", **kwargs):
        kwargs.setdefault("category", ErrorCategory.EXTERNAL_SERVICE)
        kwargs.setdefault("severity", ErrorSeverity.ERROR)
        kwargs.setdefault("http_status", 502)
        if "details" not in kwargs:
            kwargs["details"] = {}
        if service:
            kwargs["details"]["service"] = service
        super().__init__(message, **kwargs)


class DatabaseException(DiomikaException):
    """Database error."""

    def __init__(self, message: str, query: str = "", **kwargs):
        kwargs.setdefault("category", ErrorCategory.DATABASE)
        kwargs.setdefault("severity", ErrorSeverity.CRITICAL)
        kwargs.setdefault("http_status", 500)
        if "details" not in kwargs:
            kwargs["details"] = {}
        if query:
            kwargs["details"]["query"] = query
        super().__init__(message, **kwargs)


class TimeoutException(DiomikaException):
    """Operation timeout."""

    def __init__(self, message: str, timeout_seconds: int = 0, **kwargs):
        kwargs.setdefault("category", ErrorCategory.TIMEOUT)
        kwargs.setdefault("severity", ErrorSeverity.ERROR)
        kwargs.setdefault("http_status", 504)
        if "details" not in kwargs:
            kwargs["details"] = {}
        if timeout_seconds:
            kwargs["details"]["timeout_seconds"] = timeout_seconds
        super().__init__(message, **kwargs)


class ErrorRecoveryStrategy:
    """Strategies for error recovery."""

    # Retry configuration per error category
    RETRY_CONFIG = {
        ErrorCategory.EXTERNAL_SERVICE: {"attempts": 3, "backoff": 2.0},
        ErrorCategory.TIMEOUT: {"attempts": 2, "backoff": 1.5},
        ErrorCategory.DATABASE: {"attempts": 2, "backoff": 1.0},
        ErrorCategory.RATE_LIMIT: {"attempts": 1, "backoff": 0},
    }

    # Fallback responses per error category
    FALLBACK_RESPONSES = {
        ErrorCategory.EXTERNAL_SERVICE: {"cached": True, "stale_ok": True},
        ErrorCategory.TIMEOUT: {"cached": True, "partial_ok": True},
        ErrorCategory.DATABASE: {"cached": True, "fallback_service": True},
    }

    @staticmethod
    def should_retry(exception: DiomikaException) -> bool:
        """Determine if error should be retried."""
        return exception.category in ErrorRecoveryStrategy.RETRY_CONFIG

    @staticmethod
    def get_retry_config(category: ErrorCategory) -> dict:
        """Get retry configuration for error category."""
        return ErrorRecoveryStrategy.RETRY_CONFIG.get(
            category, {"attempts": 0, "backoff": 0}
        )

    @staticmethod
    def get_fallback_response(category: ErrorCategory) -> dict:
        """Get fallback response for error category."""
        return ErrorRecoveryStrategy.FALLBACK_RESPONSES.get(category, {})

    @staticmethod
    async def retry_with_backoff(
        func: Callable,
        category: ErrorCategory,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with exponential backoff retry."""
        config = ErrorRecoveryStrategy.get_retry_config(category)
        attempts = config.get("attempts", 1)
        backoff = config.get("backoff", 1.0)

        last_exception = None
        for attempt in range(attempts):
            try:
                if hasattr(func, "__call__"):
                    if hasattr(func, "__await__"):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
            except DiomikaException as e:
                last_exception = e
                if attempt < attempts - 1:
                    import asyncio
                    delay = (backoff ** attempt)
                    await asyncio.sleep(delay)
                    logger.warning(
                        f"Retry attempt {attempt + 1} for {category.value} after {delay}s"
                    )

        if last_exception:
            raise last_exception
        raise TimeoutException(f"Operation failed after {attempts} attempts")


class ErrorFormatter:
    """Format errors for API responses."""

    @staticmethod
    def format_error(exception: DiomikaException) -> dict:
        """Format exception as API response."""
        return {
            "error": {
                "message": exception.message,
                "category": exception.category.value,
                "severity": exception.severity.value,
                "request_id": exception.request_id,
                "details": exception.details,
            }
        }

    @staticmethod
    def format_validation_errors(errors: list[dict]) -> dict:
        """Format validation errors for API response."""
        return {
            "error": {
                "message": "Validation failed",
                "category": ErrorCategory.VALIDATION.value,
                "severity": ErrorSeverity.WARNING.value,
                "errors": errors,
            }
        }

    @staticmethod
    def log_error(exception: DiomikaException):
        """Log error with context."""
        context = exception.context
        log_data = {
            "category": context.category.value,
            "severity": context.severity.value,
            "user_id": context.user_id,
            "resource": context.resource,
            "request_id": context.request_id,
            "timestamp": context.timestamp.isoformat(),
            "details": context.details,
        }

        if context.severity == ErrorSeverity.CRITICAL:
            logger.critical(context.message, extra=log_data)
        elif context.severity == ErrorSeverity.ERROR:
            logger.error(context.message, extra=log_data)
        elif context.severity == ErrorSeverity.WARNING:
            logger.warning(context.message, extra=log_data)
        else:
            logger.info(context.message, extra=log_data)


class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = DiomikaException,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    def is_open(self) -> bool:
        """Check if circuit is open."""
        if self.state == "open":
            import time
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure > self.recovery_timeout:
                self.state = "half_open"
                return False
            return True
        return False

    def record_success(self):
        """Record successful call."""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        import time
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute call with circuit breaker protection."""
        if self.is_open():
            raise ExternalServiceException(
                "Circuit breaker is open",
                details={"state": self.state, "failures": self.failure_count}
            )

        try:
            if hasattr(func, "__await__"):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exception as e:
            self.record_failure()
            raise
