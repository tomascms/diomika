"""Tests for security hardening utilities."""
import pytest
from core.security_hardening import (
    SecurityHeaders,
    InputSanitization,
    SQLInjectionProtection,
    RateLimitingDefense,
)


class TestSecurityHeaders:
    """Tests for security headers."""

    def test_headers_production(self):
        """Production should have strict HSTS."""
        headers = SecurityHeaders.get_headers(is_production=True)
        assert "Strict-Transport-Security" in headers
        assert "max-age=31536000" in headers["Strict-Transport-Security"]
        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"

    def test_headers_dev(self):
        """Dev should have relaxed HSTS."""
        headers = SecurityHeaders.get_headers(is_production=False)
        assert "max-age=300" in headers["Strict-Transport-Security"]

    def test_csp_header(self):
        """CSP should be present."""
        headers = SecurityHeaders.get_headers()
        assert "Content-Security-Policy" in headers
        assert "default-src 'self'" in headers["Content-Security-Policy"]

    def test_noindex_dev(self):
        """Dev should block indexing."""
        headers = SecurityHeaders.get_headers(is_production=False)
        assert headers["X-Robots-Tag"] == "noindex, nofollow"


class TestInputSanitization:
    """Tests for input validation."""

    def test_length_validation(self):
        """Check length limits."""
        valid, msg = InputSanitization.validate_length("email", "test@example.com", limit=100)
        assert valid is True

        valid, msg = InputSanitization.validate_length("email", "x" * 300, limit=100)
        assert valid is False
        assert "exceeds" in msg

    def test_sanitize_html(self):
        """Remove HTML tags."""
        result = InputSanitization.sanitize_html("<script>alert('xss')</script>")
        assert "<script" not in result
        assert "</script>" not in result
        assert "&lt;" in result

    def test_email_forbidden_chars(self):
        """Email shouldn't have certain characters."""
        valid, msg = InputSanitization.validate_field("email", "test<>@example.com")
        assert valid is False
        assert "forbidden character" in msg

    def test_valid_email(self):
        """Valid email should pass."""
        valid, msg = InputSanitization.validate_field("email", "test@example.com")
        assert valid is True

    def test_username_length(self):
        """Username should respect max length."""
        valid, msg = InputSanitization.validate_field("username", "x" * 100)
        assert valid is False


class TestSQLInjectionProtection:
    """Tests for SQL injection detection."""

    def test_contains_sql_keywords(self):
        """Detect SQL keywords."""
        assert SQLInjectionProtection.contains_sql_keywords("SELECT * FROM users") is True
        assert SQLInjectionProtection.contains_sql_keywords("hello world") is False

    def test_sql_injection_patterns(self):
        """Detect common SQL injection patterns."""
        patterns = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1=1",
        ]
        for pattern in patterns:
            valid, msg = SQLInjectionProtection.validate_no_sql(pattern)
            assert valid is False, f"Should detect: {pattern}"

    def test_legitimate_input(self):
        """Legitimate input should pass."""
        valid, msg = SQLInjectionProtection.validate_no_sql("John O'Brien")
        assert valid is True


class TestRateLimitingDefense:
    """Tests for rate limiting defense configuration."""

    def test_login_attempts_limit(self):
        """Verify login attempt limit."""
        assert RateLimitingDefense.LOGIN_ATTEMPTS_PER_HOUR == 10

    def test_backoff_exponential(self):
        """Test exponential backoff calculation."""
        delays = [
            (1, 1),
            (2, 2),
            (3, 4),
            (4, 8),
            (5, 16),
            (6, 32),
            (7, 60),  # Capped
            (8, 60),  # Capped
        ]
        for attempt, expected_delay in delays:
            delay = RateLimitingDefense.get_backoff_delay(attempt)
            assert delay == expected_delay, f"Attempt {attempt} should have {expected_delay}s delay, got {delay}s"

    def test_backoff_capped(self):
        """Backoff should be capped at 60s."""
        delay = RateLimitingDefense.get_backoff_delay(100)
        assert delay == 60
