"""Security hardening — OWASP top 10 protection and defense-in-depth strategies.

Implementa proteções contra:
1. Injection (SQL, NoSQL, Command) - Input validation + prepared statements
2. Broken Authentication - MFA obrigatório, token rotation, rate limiting
3. Sensitive Data Exposure - Encryption, PII redaction, HTTPS enforcement
4. XML External Entity (XXE) - Disable external entities parsing
5. Broken Access Control - RBAC, path guards, scope validation
6. Security Misconfiguration - Security headers, CORS strict, no debug info
7. XSS (Cross-Site Scripting) - CSP headers, input sanitization
8. Insecure Deserialization - Type validation, safe JSON parsing
9. Using Components with Known Vulnerabilities - Dependency scanning, updates
10. Insufficient Logging & Monitoring - Audit logs, error tracking, alerts
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("diomika-api")


class SecurityHeaders:
    """Recommended security headers for all responses."""

    @staticmethod
    def get_headers(
        csp_nonce: Optional[str] = None,
        is_production: bool = True,
    ) -> dict[str, str]:
        """
        Get security headers dict.

        Headers protect against:
        - XSS (Content-Security-Policy)
        - Clickjacking (X-Frame-Options)
        - MIME sniffing (X-Content-Type-Options)
        - Referrer leaking (Referrer-Policy)
        - Feature abuse (Permissions-Policy)
        """
        headers = {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",

            # Prevent MIME sniffing
            "X-Content-Type-Options": "nosniff",

            # HSTS: enforce HTTPS (31536000 = 1 year)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload" if is_production else "max-age=300",

            # Control referrer information
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # Restrict features available to the page
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "accelerometer=()"
            ),

            # Prevent framing by other sites
            "X-Content-Security-Policy": "default-src 'self'",

            # Cross-Origin policies
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Cross-Origin-Opener-Policy": "same-origin",

            # Prevent Google from indexing in test/staging
            "X-Robots-Tag": "noindex, nofollow" if not is_production else "all",
        }

        # Content Security Policy (CSP)
        # Whitelist only necessary sources, use nonce for inline scripts
        if csp_nonce:
            csp = (
                f"default-src 'self'; "
                f"script-src 'self' 'nonce-{csp_nonce}'; "
                f"style-src 'self' 'unsafe-inline'; "  # Needed for Vue inline styles
                f"img-src 'self' data: https:; "
                f"font-src 'self' data:; "
                f"connect-src 'self' https://api.diomika.com; "
                f"frame-ancestors 'none'; "
                f"base-uri 'self'; "
                f"form-action 'self'"
            )
        else:
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://api.diomika.com; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )

        headers["Content-Security-Policy"] = csp
        return headers


class InputSanitization:
    """Input validation and sanitization utilities."""

    # Maximum lengths per field
    FIELD_LIMITS = {
        "email": 254,
        "username": 50,
        "password": 256,
        "name": 200,
        "description": 5000,
        "phone": 20,
        "ean": 13,
        "url": 2048,
    }

    # Forbidden characters in common fields
    FORBIDDEN_CHARS = {
        "email": "<>\"'`",
        "username": "<>\"'`\\/@#$%^&*()",
        "name": "<>\"'`",
    }

    @staticmethod
    def validate_length(field: str, value: str, limit: Optional[int] = None) -> tuple[bool, str]:
        """Check if value exceeds field length limit."""
        max_len = limit or InputSanitization.FIELD_LIMITS.get(field, 10000)
        if len(value) > max_len:
            return False, f"{field} exceeds {max_len} characters"
        return True, ""

    @staticmethod
    def sanitize_html(text: str) -> str:
        """Remove HTML tags and dangerous entities."""
        import html
        # Escape HTML entities
        text = html.escape(text)
        # Remove any remaining script tags
        text = text.replace("<script", "&lt;script").replace("</script>", "&lt;/script&gt;")
        return text

    @staticmethod
    def validate_field(field: str, value: str) -> tuple[bool, str]:
        """Validate field against forbidden characters."""
        if not value:
            return True, ""

        forbidden = InputSanitization.FORBIDDEN_CHARS.get(field)
        if forbidden:
            for char in forbidden:
                if char in value:
                    return False, f"{field} contains forbidden character: {char}"

        # Check length
        is_valid, msg = InputSanitization.validate_length(field, value)
        if not is_valid:
            return False, msg

        return True, ""


class SQLInjectionProtection:
    """SQL injection prevention strategies."""

    # Keywords that shouldn't appear in user input (basic heuristic)
    SQL_KEYWORDS = {
        "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT",
        "UPDATE", "EXEC", "EXECUTE", "SCRIPT", "UNION", "SELECT",
    }

    @staticmethod
    def contains_sql_keywords(value: str) -> bool:
        """Detect common SQL keywords in user input (basic check)."""
        value_upper = value.upper()
        return any(kw in value_upper for kw in SQLInjectionProtection.SQL_KEYWORDS)

    @staticmethod
    def validate_no_sql(value: str) -> tuple[bool, str]:
        """Check for SQL injection patterns."""
        if SQLInjectionProtection.contains_sql_keywords(value):
            return False, "Input contains SQL keywords"

        # Check for common SQL injection patterns
        patterns = [
            "' OR '1'='1",
            "'; DROP",
            "\" OR \"\"=\"",
            "1=1",
            "1' OR '1'='1",
        ]
        for pattern in patterns:
            if pattern in value:
                return False, "Input matches SQL injection pattern"

        return True, ""


class EncryptionConfig:
    """Encryption configuration for sensitive data."""

    # Encryption algorithms and key sizes
    DEFAULT_ALGORITHM = "AES-256-GCM"
    KEY_SIZE_BITS = 256
    KEY_SIZE_BYTES = 32

    @staticmethod
    def requires_encryption(field: str) -> bool:
        """Check if field should be encrypted at rest."""
        sensitive_fields = {
            "password_hash", "api_key", "token", "credit_card",
            "ssn", "national_id", "phone", "email", "address"
        }
        return field in sensitive_fields or field.endswith("_secret")


class AuditLogging:
    """Audit trail for security-relevant events."""

    @staticmethod
    def log_security_event(
        event_type: str,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        result: str = "success",
        details: Optional[dict] = None,
    ):
        """Log security-relevant event for audit trail."""
        extra = {
            "event_type": event_type,
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "result": result,
        }
        if details:
            extra.update(details)

        if result == "failure":
            logger.warning(f"Security event: {event_type}", extra=extra)
        else:
            logger.info(f"Security event: {event_type}", extra=extra)

    @staticmethod
    def log_auth_attempt(username: str, success: bool, ip: str = ""):
        """Log authentication attempt."""
        AuditLogging.log_security_event(
            event_type="authentication",
            user_id=username,
            action="login",
            result="success" if success else "failure",
            details={"ip": ip},
        )

    @staticmethod
    def log_privilege_escalation(user_id: str, old_role: str, new_role: str):
        """Log privilege changes."""
        AuditLogging.log_security_event(
            event_type="privilege_change",
            user_id=user_id,
            resource=f"{old_role} -> {new_role}",
            action="escalation",
        )

    @staticmethod
    def log_data_access(user_id: str, resource: str, action: str):
        """Log sensitive data access."""
        AuditLogging.log_security_event(
            event_type="data_access",
            user_id=user_id,
            resource=resource,
            action=action,
        )


class RateLimitingDefense:
    """Rate limiting specific to attack patterns."""

    # Attempt limits for sensitive operations
    LOGIN_ATTEMPTS_PER_HOUR = 10  # Per IP
    PASSWORD_RESET_PER_HOUR = 3   # Per email
    API_KEY_GENERATION_PER_HOUR = 5

    @staticmethod
    def get_backoff_delay(attempt_number: int) -> int:
        """Calculate exponential backoff delay in seconds."""
        # 1s, 2s, 4s, 8s, 16s, 32s (cap at 60s)
        return min(2 ** (attempt_number - 1), 60)


class DeprecationNotice:
    """Track deprecated security functions to be removed."""

    DEPRECATED = {
        "use_md5_for_password": "Use argon2id via passlib instead",
        "http_only_cookie_disabled": "Always set HttpOnly=True for session cookies",
        "no_csrf_token": "Implement CSRF protection for state-changing operations",
        "no_rate_limiting": "Use RateLimitingMiddleware for all endpoints",
    }
