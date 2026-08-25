"""Auth roles, audit e storage sanitization."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


def test_resolve_role_admin_and_ops(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "a" * 40)
    monkeypatch.setenv("API_OPS_KEY", "b" * 40)
    from core.auth import resolve_role

    assert resolve_role("a" * 40) == "admin"
    assert resolve_role("b" * 40) == "ops"
    assert resolve_role("wrong") is None


def test_require_ops_blocks_admin_when_ops_configured(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "a" * 40)
    monkeypatch.setenv("API_OPS_KEY", "b" * 40)
    from core.auth import require_ops

    with pytest.raises(HTTPException) as exc:
        require_ops(role="admin")
    assert exc.value.status_code == 403


def test_require_admin_blocks_ops_when_ops_configured(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "a" * 40)
    monkeypatch.setenv("API_OPS_KEY", "b" * 40)
    from core.auth import require_admin

    with pytest.raises(HTTPException) as exc:
        require_admin(role="ops")
    assert exc.value.status_code == 403


def test_audit_redacts_secrets():
    from core.audit import _safe_detail

    out = _safe_detail({"password": "x", "nome": "ok", "api_key": "secret"})
    assert out["password"] == "[redacted]"
    assert out["api_key"] == "[redacted]"
    assert out["nome"] == "ok"


def test_sanitize_storage_path():
    from utils.storage import sanitize_storage_path

    assert sanitize_storage_path("../evil/../x.png") == "evil/x.png"
    assert ".." not in sanitize_storage_path("a/../../b.png")
    with pytest.raises(ValueError):
        sanitize_storage_path("/")
    with pytest.raises(ValueError):
        sanitize_storage_path("..")


def test_assert_table_action_blocks_sensitive_hard_delete():
    from core.auth import assert_table_action

    with pytest.raises(HTTPException) as exc:
        assert_table_action("contact_messages", "hard_delete", "admin")
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException):
        assert_table_action("categories", "read", "ops")

    with pytest.raises(HTTPException):
        assert_table_action("outbox_events", "read", "admin")

    assert_table_action("categories", "create", "admin")
    assert_table_action("contact_messages", "read", "mensagens")


def test_hard_delete_blocked_in_production(monkeypatch):
    monkeypatch.setenv("DIOMIKA_ENV", "production")
    monkeypatch.delenv("DIOMIKA_BETA", raising=False)
    from core.config import get_settings

    get_settings.cache_clear()

    from routes.admin_crud import delete_record

    class Req:
        state = type("S", (), {"api_role": "admin", "request_id": "t"})()

    with patch("routes.admin_crud._schema_for"), patch("routes.admin_crud.get_db"):
        with pytest.raises(HTTPException) as exc:
            delete_record(Req(), "categories", "00000000-0000-0000-0000-000000000001", hard=True)
        assert exc.value.status_code == 403

    get_settings.cache_clear()
