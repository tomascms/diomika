"""Tests for audit trail logging."""
import pytest
from core.audit_trail import (
    AuditAction,
    AuditResult,
    AuditEntry,
    AuditLogger,
)


class TestAuditEntry:
    """Test audit entry creation and conversion."""

    def test_audit_entry_creation(self):
        """Should create audit entry with required fields."""
        entry = AuditEntry(
            timestamp=None,
            action=AuditAction.CREATE,
            result=AuditResult.SUCCESS,
            user_id="user123",
            resource_type="product",
            resource_id="prod456",
        )
        assert entry.action == AuditAction.CREATE
        assert entry.result == AuditResult.SUCCESS
        assert entry.user_id == "user123"

    def test_audit_entry_with_changes(self):
        """Should record changes in audit entry."""
        entry = AuditEntry(
            timestamp=None,
            action=AuditAction.UPDATE,
            result=AuditResult.SUCCESS,
            resource_type="product",
            resource_id="prod123",
            old_values={"name": "Old Name"},
            new_values={"name": "New Name"},
            changes={"name": "Old Name -> New Name"},
        )
        assert entry.old_values["name"] == "Old Name"
        assert entry.new_values["name"] == "New Name"

    def test_audit_entry_to_dict(self):
        """Should convert entry to dictionary."""
        entry = AuditEntry(
            timestamp=None,
            action=AuditAction.CREATE,
            result=AuditResult.SUCCESS,
            user_id="user123",
            resource_type="product",
        )
        data = entry.to_dict()
        assert data["action"] == "create"
        assert data["result"] == "success"
        assert data["user_id"] == "user123"

    def test_audit_entry_to_json(self):
        """Should convert entry to JSON."""
        entry = AuditEntry(
            timestamp=None,
            action=AuditAction.DELETE,
            result=AuditResult.SUCCESS,
            user_id="user123",
            resource_type="product",
        )
        json_str = entry.to_json()
        assert isinstance(json_str, str)
        assert "delete" in json_str
        assert "success" in json_str


class TestAuditLogger:
    """Test audit logging operations."""

    def test_log_create(self):
        """Should log record creation."""
        entry = AuditLogger.log_create(
            user_id="user123",
            resource_type="product",
            resource_id="prod456",
            resource_name="Test Product",
            new_values={"name": "Test Product", "price": 99.99},
        )
        assert entry.action == AuditAction.CREATE
        assert entry.result == AuditResult.SUCCESS
        assert entry.new_values["name"] == "Test Product"

    def test_log_update(self):
        """Should log record update."""
        entry = AuditLogger.log_update(
            user_id="user123",
            resource_type="product",
            resource_id="prod456",
            old_values={"price": 99.99},
            new_values={"price": 89.99},
            changes={"price": "99.99 -> 89.99"},
        )
        assert entry.action == AuditAction.UPDATE
        assert entry.result == AuditResult.SUCCESS

    def test_log_delete(self):
        """Should log record deletion."""
        entry = AuditLogger.log_delete(
            user_id="user123",
            resource_type="product",
            resource_id="prod456",
            old_values={"name": "Product", "price": 99.99},
            affected_records=1,
        )
        assert entry.action == AuditAction.DELETE
        assert entry.affected_records == 1

    def test_log_read(self):
        """Should log record read."""
        entry = AuditLogger.log_read(
            user_id="user123",
            resource_type="product",
            resource_id="prod456",
        )
        assert entry.action == AuditAction.READ
        assert entry.result == AuditResult.SUCCESS

    def test_log_list(self):
        """Should log list operation."""
        entry = AuditLogger.log_list(
            user_id="user123",
            resource_type="product",
            affected_records=42,
            details={"filters": {"category": "electronics"}},
        )
        assert entry.action == AuditAction.LIST
        assert entry.affected_records == 42

    def test_log_error(self):
        """Should log action failure."""
        entry = AuditLogger.log_error(
            action=AuditAction.CREATE,
            user_id="user123",
            resource_type="product",
            error_message="Database connection failed",
        )
        assert entry.result == AuditResult.FAILURE
        assert entry.error_message == "Database connection failed"

    def test_log_auth_success(self):
        """Should log successful authentication."""
        entry = AuditLogger.log_auth(
            action=AuditAction.LOGIN,
            result=AuditResult.SUCCESS,
            user_id="user123",
            user_email="user@example.com",
            ip_address="192.168.1.1",
        )
        assert entry.action == AuditAction.LOGIN
        assert entry.result == AuditResult.SUCCESS

    def test_log_auth_failure(self):
        """Should log failed authentication."""
        entry = AuditLogger.log_auth(
            action=AuditAction.LOGIN,
            result=AuditResult.FAILURE,
            user_id="user123",
            ip_address="192.168.1.1",
            error_message="Invalid password",
        )
        assert entry.result == AuditResult.FAILURE
        assert entry.error_message == "Invalid password"

    def test_log_security_event(self):
        """Should log security event."""
        entry = AuditLogger.log_security_event(
            event_type="suspicious_activity",
            result=AuditResult.SUCCESS,
            user_id="user123",
            ip_address="192.168.1.1",
            details={"attempt_count": 5},
        )
        assert entry.action == AuditAction.SECURITY_EVENT
        assert "security:suspicious_activity" in entry.resource_type

    def test_log_import(self):
        """Should log data import."""
        entry = AuditLogger.log_import(
            user_id="user123",
            resource_type="product",
            affected_records=100,
            details={"file": "products.csv"},
        )
        assert entry.action == AuditAction.IMPORT
        assert entry.affected_records == 100

    def test_log_export(self):
        """Should log data export."""
        entry = AuditLogger.log_export(
            user_id="user123",
            resource_type="product",
            affected_records=50,
            details={"format": "csv"},
        )
        assert entry.action == AuditAction.EXPORT
        assert entry.affected_records == 50


class TestAuditActionEnum:
    """Test audit action enumeration."""

    def test_audit_actions_exist(self):
        """Should have all expected audit actions."""
        actions = [
            AuditAction.CREATE,
            AuditAction.READ,
            AuditAction.UPDATE,
            AuditAction.DELETE,
            AuditAction.LIST,
            AuditAction.LOGIN,
            AuditAction.LOGOUT,
            AuditAction.SECURITY_EVENT,
        ]
        assert len(actions) > 0

    def test_audit_result_enum(self):
        """Should have result status."""
        assert AuditResult.SUCCESS.value == "success"
        assert AuditResult.FAILURE.value == "failure"
        assert AuditResult.PARTIAL.value == "partial"
