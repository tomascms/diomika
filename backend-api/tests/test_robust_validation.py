"""Tests for robust validation utilities."""
import pytest
from core.robust_validation import (
    FieldValidator,
    BulkValidator,
    SanitizationRules,
    ValidationError,
)


class TestFieldValidator:
    """Tests for field validators."""

    def test_validate_email_valid(self):
        """Valid email should pass."""
        result = FieldValidator.validate_email("test@example.com")
        assert result is None

    def test_validate_email_required(self):
        """Empty email with required=True should fail."""
        result = FieldValidator.validate_email("", required=True)
        assert result is not None
        assert "required" in result.message.lower()

    def test_validate_email_optional(self):
        """Empty email with required=False should pass."""
        result = FieldValidator.validate_email("", required=False)
        assert result is None

    def test_validate_email_invalid_format(self):
        """Invalid email format should fail."""
        result = FieldValidator.validate_email("not-an-email")
        assert result is not None
        assert "format" in result.message.lower()

    def test_validate_email_too_long(self):
        """Email exceeding 254 chars should fail."""
        long_email = "a" * 250 + "@example.com"
        result = FieldValidator.validate_email(long_email)
        assert result is not None
        assert "too long" in result.message.lower()

    def test_validate_password_valid(self):
        """Valid password should pass."""
        result = FieldValidator.validate_password("MyP@ssw0rd")
        assert result is None

    def test_validate_password_too_short(self):
        """Password < 8 chars should fail."""
        result = FieldValidator.validate_password("Short1!")
        assert result is not None
        assert "8 characters" in result.message

    def test_validate_password_low_complexity(self):
        """Password with < 3 complexity levels should fail."""
        result = FieldValidator.validate_password("password")
        assert result is not None
        assert "uppercase" in result.message.lower() or "complexity" in result.message.lower()

    def test_validate_password_empty(self):
        """Empty password should fail."""
        result = FieldValidator.validate_password("")
        assert result is not None

    def test_validate_phone_valid(self):
        """Valid phone should pass."""
        result = FieldValidator.validate_phone("+1-555-123-4567")
        assert result is None

    def test_validate_phone_required(self):
        """Empty phone with required=True should fail."""
        result = FieldValidator.validate_phone("", required=True)
        assert result is not None

    def test_validate_ean_valid(self):
        """Valid EAN should pass."""
        result = FieldValidator.validate_ean("5901234123457")
        assert result is None

    def test_validate_ean_too_short(self):
        """EAN < 8 digits should fail."""
        result = FieldValidator.validate_ean("1234567")
        assert result is not None

    def test_validate_url_valid(self):
        """Valid URL should pass."""
        result = FieldValidator.validate_url("https://example.com/path")
        assert result is None

    def test_validate_url_invalid(self):
        """Invalid URL should fail."""
        result = FieldValidator.validate_url("not a url")
        assert result is not None

    def test_validate_length_valid(self):
        """Valid length should pass."""
        result = FieldValidator.validate_length("test value", "field", min_len=5, max_len=20)
        assert result is None

    def test_validate_length_too_short(self):
        """Value shorter than min should fail."""
        result = FieldValidator.validate_length("ab", "field", min_len=5)
        assert result is not None

    def test_validate_enum_valid(self):
        """Value in allowed list should pass."""
        result = FieldValidator.validate_enum("red", "color", ["red", "green", "blue"])
        assert result is None

    def test_validate_enum_invalid(self):
        """Value not in allowed list should fail."""
        result = FieldValidator.validate_enum("yellow", "color", ["red", "green", "blue"])
        assert result is not None

    def test_validate_date_valid(self):
        """Valid ISO 8601 date should pass."""
        result = FieldValidator.validate_date("2024-01-15")
        assert result is None

    def test_validate_date_with_timezone(self):
        """ISO date with timezone should pass."""
        result = FieldValidator.validate_date("2024-01-15T10:30:00Z")
        assert result is None

    def test_validate_date_invalid(self):
        """Invalid date format should fail."""
        result = FieldValidator.validate_date("2024/01/15")
        assert result is not None

    def test_validate_positive_number_valid(self):
        """Positive number should pass."""
        result = FieldValidator.validate_positive_number(10.5, "price")
        assert result is None

    def test_validate_positive_number_zero(self):
        """Zero should fail."""
        result = FieldValidator.validate_positive_number(0, "quantity")
        assert result is not None

    def test_validate_percentage_valid(self):
        """Percentage between 0-100 should pass."""
        result = FieldValidator.validate_percentage(75.5, "discount")
        assert result is None

    def test_validate_percentage_over_100(self):
        """Percentage > 100 should fail."""
        result = FieldValidator.validate_percentage(150, "discount")
        assert result is not None

    def test_validate_percentage_negative(self):
        """Negative percentage should fail."""
        result = FieldValidator.validate_percentage(-10, "discount")
        assert result is not None


class TestBulkValidator:
    """Tests for bulk validation."""

    def test_no_errors(self):
        """Valid data should have no errors."""
        validator = BulkValidator()
        validator.validate_email("test@example.com", required=True)
        validator.validate_length("test", "username", min_len=3, max_len=20)
        assert not validator.has_errors()

    def test_multiple_errors(self):
        """Multiple errors should accumulate."""
        validator = BulkValidator()
        validator.validate_email("invalid", required=True)
        validator.validate_length("ab", "username", min_len=3)
        assert validator.has_errors()
        assert len(validator.errors) == 2

    def test_get_errors_dict(self):
        """Error dict should map field to message."""
        validator = BulkValidator()
        validator.validate_email("invalid", required=True)
        validator.validate_email("also@invalid", "email2", required=True)
        errors = validator.get_errors_dict()
        assert "email" in errors
        assert "email2" in errors

    def test_get_errors_list(self):
        """Error list should have field and message."""
        validator = BulkValidator()
        validator.validate_email("invalid", required=True)
        errors = validator.get_errors_list()
        assert len(errors) == 1
        assert "field" in errors[0]
        assert "message" in errors[0]

    def test_chaining(self):
        """Validator should support method chaining."""
        validator = (
            BulkValidator()
            .validate_email("test@example.com", required=True)
            .validate_length("username", "username", min_len=3, max_len=20)
            .validate_enum("active", "status", ["active", "inactive"])
        )
        assert not validator.has_errors()


class TestSanitizationRules:
    """Tests for input sanitization."""

    def test_trim_whitespace(self):
        """Whitespace should be trimmed."""
        result = SanitizationRules.trim_whitespace("  hello  ")
        assert result == "hello"

    def test_trim_empty(self):
        """Empty string should remain empty."""
        result = SanitizationRules.trim_whitespace("")
        assert result == ""

    def test_normalize_email(self):
        """Email should be lowercased and trimmed."""
        result = SanitizationRules.normalize_email("  Test@EXAMPLE.COM  ")
        assert result == "test@example.com"

    def test_normalize_phone_removes_separators(self):
        """Phone separators should be removed."""
        result = SanitizationRules.normalize_phone("+1 (555) 123-4567")
        assert result == "+15551234567"

    def test_normalize_slug(self):
        """Text should be converted to slug format."""
        result = SanitizationRules.normalize_slug("Hello World Example!")
        assert result == "hello-world-example"

    def test_normalize_slug_removes_invalid_chars(self):
        """Invalid slug characters should be removed."""
        result = SanitizationRules.normalize_slug("Test@#$Value")
        assert result == "testvalue"

    def test_escape_html(self):
        """HTML entities should be escaped."""
        result = SanitizationRules.escape_html("<script>alert('xss')</script>")
        assert "<script" not in result
        assert "&lt;" in result

    def test_truncate_within_length(self):
        """Text shorter than limit should not be truncated."""
        result = SanitizationRules.truncate("hello", 10)
        assert result == "hello"

    def test_truncate_exceeds_length(self):
        """Text longer than limit should be truncated."""
        result = SanitizationRules.truncate("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8

    def test_truncate_custom_suffix(self):
        """Custom suffix should be used."""
        result = SanitizationRules.truncate("hello world", 10, suffix="--")
        assert result.endswith("--")


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_validation_error_creation(self):
        """ValidationError should be creatable."""
        error = ValidationError("email", "Invalid email format", value="bad@")
        assert error.field == "email"
        assert error.message == "Invalid email format"
        assert error.value == "bad@"

    def test_validation_error_without_value(self):
        """ValidationError should work without value."""
        error = ValidationError("username", "Username is required")
        assert error.field == "username"
        assert error.value is None
