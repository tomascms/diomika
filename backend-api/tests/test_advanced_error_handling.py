"""Tests for advanced error handling."""
import pytest
from core.advanced_error_handling import (
    ErrorCategory,
    ErrorSeverity,
    DiomikaException,
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    NotFoundException,
    ConflictException,
    RateLimitException,
    ExternalServiceException,
    DatabaseException,
    TimeoutException,
    ErrorRecoveryStrategy,
    ErrorFormatter,
)


class TestExceptionHierarchy:
    """Test custom exception types."""

    def test_diomika_exception(self):
        """Base exception should have all attributes."""
        exc = DiomikaException(
            message="Test error",
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.ERROR,
            http_status=500,
        )
        assert exc.message == "Test error"
        assert exc.http_status == 500

    def test_validation_exception(self):
        """ValidationException should set correct defaults."""
        exc = ValidationException("Invalid field", field="email")
        assert exc.category == ErrorCategory.VALIDATION
        assert exc.severity == ErrorSeverity.WARNING
        assert exc.http_status == 422
        assert exc.details["field"] == "email"

    def test_authentication_exception(self):
        """AuthenticationException should set 401."""
        exc = AuthenticationException("Invalid credentials")
        assert exc.http_status == 401
        assert exc.category == ErrorCategory.AUTHENTICATION

    def test_authorization_exception(self):
        """AuthorizationException should set 403."""
        exc = AuthorizationException("Access denied")
        assert exc.http_status == 403
        assert exc.category == ErrorCategory.AUTHORIZATION

    def test_not_found_exception(self):
        """NotFoundException should set 404."""
        exc = NotFoundException("User not found", resource="user")
        assert exc.http_status == 404
        assert exc.resource == "user"

    def test_conflict_exception(self):
        """ConflictException should set 409."""
        exc = ConflictException("Duplicate entry")
        assert exc.http_status == 409

    def test_rate_limit_exception(self):
        """RateLimitException should set 429 and retry_after."""
        exc = RateLimitException("Too many requests", retry_after=120)
        assert exc.http_status == 429
        assert exc.details["retry_after"] == 120

    def test_external_service_exception(self):
        """ExternalServiceException should set 502."""
        exc = ExternalServiceException("Service down", service="payment")
        assert exc.http_status == 502
        assert exc.details["service"] == "payment"

    def test_database_exception(self):
        """DatabaseException should set 500 and critical."""
        exc = DatabaseException("Connection failed")
        assert exc.http_status == 500
        assert exc.severity == ErrorSeverity.CRITICAL

    def test_timeout_exception(self):
        """TimeoutException should set 504."""
        exc = TimeoutException("Operation timed out", timeout_seconds=30)
        assert exc.http_status == 504
        assert exc.details["timeout_seconds"] == 30


class TestErrorRecoveryStrategy:
    """Test error recovery strategies."""

    def test_should_retry_external_service(self):
        """External service errors should be retried."""
        exc = ExternalServiceException("Service down")
        assert ErrorRecoveryStrategy.should_retry(exc) is True

    def test_should_not_retry_validation(self):
        """Validation errors should not be retried."""
        exc = ValidationException("Invalid data")
        assert ErrorRecoveryStrategy.should_retry(exc) is False

    def test_get_retry_config_exists(self):
        """Should return retry config for known categories."""
        config = ErrorRecoveryStrategy.get_retry_config(ErrorCategory.EXTERNAL_SERVICE)
        assert config["attempts"] == 3
        assert config["backoff"] == 2.0

    def test_get_retry_config_unknown(self):
        """Should return default for unknown categories."""
        config = ErrorRecoveryStrategy.get_retry_config(ErrorCategory.VALIDATION)
        assert config["attempts"] == 0

    def test_get_fallback_response(self):
        """Should return fallback response for service errors."""
        fallback = ErrorRecoveryStrategy.get_fallback_response(ErrorCategory.EXTERNAL_SERVICE)
        assert fallback.get("cached") is True
        assert fallback.get("stale_ok") is True


class TestErrorFormatter:
    """Test error formatting for API responses."""

    def test_format_validation_error(self):
        """Format validation error for response."""
        exc = ValidationException("Invalid email", field="email")
        formatted = ErrorFormatter.format_error(exc)
        assert "error" in formatted
        assert formatted["error"]["category"] == "validation"
        assert formatted["error"]["severity"] == "warning"

    def test_format_error_includes_details(self):
        """Format should include error details."""
        exc = RateLimitException("Too many requests", retry_after=60)
        formatted = ErrorFormatter.format_error(exc)
        assert formatted["error"]["details"]["retry_after"] == 60

    def test_format_validation_errors_list(self):
        """Format list of validation errors."""
        errors = [
            {"field": "email", "message": "Invalid format"},
            {"field": "password", "message": "Too short"},
        ]
        formatted = ErrorFormatter.format_validation_errors(errors)
        assert formatted["error"]["message"] == "Validation failed"
        assert len(formatted["error"]["errors"]) == 2

    def test_log_error_does_not_raise(self):
        """Logging error should not raise exceptions."""
        exc = ValidationException("Test error")
        try:
            ErrorFormatter.log_error(exc)
        except Exception as e:
            pytest.fail(f"log_error should not raise: {e}")


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_circuit_breaker_closed_state(self):
        """Circuit should start closed."""
        from core.advanced_error_handling import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2)
        assert cb.state == "closed"
        assert not cb.is_open()

    def test_circuit_breaker_opens_after_failures(self):
        """Circuit should open after threshold failures."""
        from core.advanced_error_handling import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open()

    def test_circuit_breaker_closes_after_success(self):
        """Circuit should close after successful call."""
        from core.advanced_error_handling import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open()
        cb.record_success()
        assert not cb.is_open()

    def test_circuit_breaker_prevents_calls_when_open(self):
        """Circuit breaker should prevent calls when open."""
        from core.advanced_error_handling import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_open()
