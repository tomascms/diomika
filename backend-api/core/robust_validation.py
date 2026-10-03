"""Robust data validation — comprehensive field validation with clear error messages."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional
from datetime import datetime, date


@dataclass
class ValidationError:
    """Validation error with field and message."""
    field: str
    message: str
    value: Any = None


class FieldValidator:
    """Reusable field validators."""

    # Common regex patterns
    PATTERNS = {
        "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
        "phone": re.compile(r"^\+?[\d\s\-()]{9,20}$"),
        "ean": re.compile(r"^\d{8,14}$"),
        "url": re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE),
        "hex_color": re.compile(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"),
        "uuid": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE),
        "slug": re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
    }

    @staticmethod
    def validate_email(value: str, required: bool = True) -> Optional[ValidationError]:
        """Validate email address."""
        if not value:
            return None if not required else ValidationError("email", "Email is required")

        if not FieldValidator.PATTERNS["email"].match(value):
            return ValidationError("email", "Invalid email format")

        if len(value) > 254:
            return ValidationError("email", "Email too long (max 254 characters)")

        return None

    @staticmethod
    def validate_password(value: str) -> Optional[ValidationError]:
        """Validate password strength."""
        if not value:
            return ValidationError("password", "Password is required")

        if len(value) < 8:
            return ValidationError("password", "Password must be at least 8 characters")

        if len(value) > 128:
            return ValidationError("password", "Password must not exceed 128 characters")

        # Check for complexity
        has_upper = any(c.isupper() for c in value)
        has_lower = any(c.islower() for c in value)
        has_digit = any(c.isdigit() for c in value)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in value)

        complexity_count = sum([has_upper, has_lower, has_digit, has_special])
        if complexity_count < 3:
            return ValidationError(
                "password",
                "Password must contain uppercase, lowercase, digits, and special characters"
            )

        return None

    @staticmethod
    def validate_phone(value: str, required: bool = False) -> Optional[ValidationError]:
        """Validate phone number."""
        if not value:
            return None if not required else ValidationError("phone", "Phone is required")

        if not FieldValidator.PATTERNS["phone"].match(value):
            return ValidationError("phone", "Invalid phone number format")

        return None

    @staticmethod
    def validate_ean(value: str, required: bool = False) -> Optional[ValidationError]:
        """Validate EAN/barcode (8-14 digits)."""
        if not value:
            return None if not required else ValidationError("ean", "EAN is required")

        if not FieldValidator.PATTERNS["ean"].match(value):
            return ValidationError("ean", "EAN must contain 8-14 digits")

        return None

    @staticmethod
    def validate_url(value: str, required: bool = False) -> Optional[ValidationError]:
        """Validate URL."""
        if not value:
            return None if not required else ValidationError("url", "URL is required")

        if not FieldValidator.PATTERNS["url"].match(value):
            return ValidationError("url", "Invalid URL format")

        if len(value) > 2048:
            return ValidationError("url", "URL too long (max 2048 characters)")

        return None

    @staticmethod
    def validate_length(value: str, field: str, min_len: int = 0, max_len: int = 10000) -> Optional[ValidationError]:
        """Validate string length."""
        if len(value) < min_len:
            return ValidationError(field, f"Must be at least {min_len} characters")

        if len(value) > max_len:
            return ValidationError(field, f"Must not exceed {max_len} characters")

        return None

    @staticmethod
    def validate_enum(value: Any, field: str, allowed_values: list) -> Optional[ValidationError]:
        """Validate enum value."""
        if value not in allowed_values:
            return ValidationError(
                field,
                f"Must be one of: {', '.join(str(v) for v in allowed_values)}"
            )
        return None

    @staticmethod
    def validate_date(value: str, field: str = "date") -> Optional[ValidationError]:
        """Validate ISO 8601 date."""
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return None
        except (ValueError, AttributeError):
            return ValidationError(field, "Invalid date format (use ISO 8601)")

    @staticmethod
    def validate_positive_number(value: float | int, field: str) -> Optional[ValidationError]:
        """Validate positive number."""
        if value <= 0:
            return ValidationError(field, "Must be a positive number")
        return None

    @staticmethod
    def validate_percentage(value: float, field: str) -> Optional[ValidationError]:
        """Validate percentage (0-100)."""
        if not (0 <= value <= 100):
            return ValidationError(field, "Must be between 0 and 100")
        return None


class BulkValidator:
    """Validate multiple fields at once."""

    def __init__(self):
        self.errors: list[ValidationError] = []

    def add_error(self, error: Optional[ValidationError]):
        """Add validation error if not None."""
        if error:
            self.errors.append(error)

    def validate_email(self, value: str, field: str = "email", required: bool = True) -> BulkValidator:
        """Validate email."""
        if not value and required:
            self.add_error(ValidationError(field, "Email is required"))
        elif value:
            error = FieldValidator.validate_email(value, required=False)
            if error:
                error.field = field
                self.add_error(error)
        return self

    def validate_password(self, value: str, field: str = "password") -> BulkValidator:
        """Validate password."""
        self.add_error(FieldValidator.validate_password(value))
        return self

    def validate_length(
        self,
        value: str,
        field: str,
        min_len: int = 0,
        max_len: int = 10000,
    ) -> BulkValidator:
        """Validate length."""
        self.add_error(FieldValidator.validate_length(value, field, min_len, max_len))
        return self

    def validate_enum(self, value: Any, field: str, allowed: list) -> BulkValidator:
        """Validate enum."""
        self.add_error(FieldValidator.validate_enum(value, field, allowed))
        return self

    def has_errors(self) -> bool:
        """Check if any errors."""
        return len(self.errors) > 0

    def get_errors_dict(self) -> dict[str, str]:
        """Get errors as dict {field: message}."""
        return {error.field: error.message for error in self.errors}

    def get_errors_list(self) -> list[dict]:
        """Get errors as list of dicts."""
        return [{"field": e.field, "message": e.message} for e in self.errors]


class SanitizationRules:
    """Data sanitization rules."""

    @staticmethod
    def trim_whitespace(value: str) -> str:
        """Remove leading/trailing whitespace."""
        return value.strip() if value else value

    @staticmethod
    def normalize_email(value: str) -> str:
        """Normalize email (lowercase, trim)."""
        return SanitizationRules.trim_whitespace(value).lower() if value else value

    @staticmethod
    def normalize_phone(value: str) -> str:
        """Normalize phone (remove common separators)."""
        if not value:
            return value
        return re.sub(r"[\s\-().]", "", value)

    @staticmethod
    def normalize_slug(value: str) -> str:
        """Normalize to slug format."""
        if not value:
            return value
        # Lowercase and replace spaces with hyphens
        slug = value.lower().strip()
        slug = re.sub(r"\s+", "-", slug)  # Replace spaces with hyphens
        slug = re.sub(r"[^a-z0-9\-]", "", slug)  # Remove invalid characters
        slug = re.sub(r"\-+", "-", slug)  # Consolidate hyphens
        return slug.strip("-")

    @staticmethod
    def escape_html(value: str) -> str:
        """Escape HTML characters."""
        import html
        return html.escape(value) if value else value

    @staticmethod
    def truncate(value: str, length: int, suffix: str = "...") -> str:
        """Truncate string to length."""
        if len(value) <= length:
            return value
        return value[:length - len(suffix)] + suffix
