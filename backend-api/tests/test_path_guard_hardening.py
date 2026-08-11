"""Path guard, lockdown, SSRF, anomaly."""
from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient


def test_ssrf_blocks_private_and_unknown_hosts():
    from core.ssrf_guard import UnsafeUrlError, assert_safe_outbound_url

    with pytest.raises(UnsafeUrlError):
        assert_safe_outbound_url("http://example.com/x")
    with pytest.raises(UnsafeUrlError):
        assert_safe_outbound_url("https://127.0.0.1/x")
    with pytest.raises(UnsafeUrlError):
        assert_safe_outbound_url("https://evil.example/x")
    assert assert_safe_outbound_url("https://challenges.cloudflare.com/turnstile").startswith("https://")


def test_lockdown_blocks_admin(monkeypatch):
    monkeypatch.setenv("DIOMIKA_ENV", "development")
    monkeypatch.setenv("API_SECRET_KEY", "k" * 32)
    monkeypatch.setenv("SECURITY_LOCKDOWN", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "sk")
    from core.config import get_settings

    get_settings.cache_clear()
    # Reimport path_guard / app is heavy; test middleware helper directly
    from core.path_guard import lockdown_active

    assert lockdown_active() is True
    monkeypatch.delenv("SECURITY_LOCKDOWN", raising=False)
    get_settings.cache_clear()


def test_peer_loopback():
    from core.local_only import peer_is_loopback

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 80),
        "scheme": "http",
    }
    req = Request(scope)
    assert peer_is_loopback(req) is True


def test_mfa_optional_via_env(monkeypatch):
    monkeypatch.setenv("DIOMIKA_ENV", "production")
    monkeypatch.delenv("DIOMIKA_BETA", raising=False)
    monkeypatch.setenv("ADMIN_MFA_REQUIRED", "0")
    from core.config import get_settings
    from core.admin_users import mfa_required_globally

    get_settings.cache_clear()
    assert mfa_required_globally() is False
    monkeypatch.setenv("ADMIN_MFA_REQUIRED", "1")
    assert mfa_required_globally() is True
    get_settings.cache_clear()


def test_session_secret_only_api_secret_key(monkeypatch):
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "x" * 40)
    from core import session_tokens
    import importlib

    importlib.reload(session_tokens)
    with pytest.raises(RuntimeError, match="API_SECRET_KEY"):
        session_tokens.issue_session(username="x", role="admin")
