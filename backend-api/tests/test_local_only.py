"""Admin/system só em localhost na produção final."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


def test_admin_local_allows_loopback_in_production(monkeypatch):
    monkeypatch.setenv("DIOMIKA_ENV", "production")
    monkeypatch.delenv("DIOMIKA_BETA", raising=False)
    monkeypatch.delenv("ADMIN_ALLOW_REMOTE", raising=False)
    from core.config import get_settings
    from core.local_only import admin_must_be_local

    get_settings.cache_clear()
    req = MagicMock()
    req.client.host = "127.0.0.1"
    admin_must_be_local(req)
    get_settings.cache_clear()


def test_admin_local_blocks_remote_in_production(monkeypatch):
    monkeypatch.setenv("DIOMIKA_ENV", "production")
    monkeypatch.delenv("DIOMIKA_BETA", raising=False)
    monkeypatch.delenv("ADMIN_ALLOW_REMOTE", raising=False)
    from core.config import get_settings
    from core.local_only import admin_must_be_local

    get_settings.cache_clear()
    req = MagicMock()
    req.client.host = "198.51.100.10"
    with pytest.raises(HTTPException) as exc:
        admin_must_be_local(req)
    assert exc.value.status_code == 403
    get_settings.cache_clear()


def test_admin_local_allows_remote_in_beta(monkeypatch):
    monkeypatch.setenv("DIOMIKA_ENV", "production")
    monkeypatch.setenv("DIOMIKA_BETA", "1")
    from core.config import get_settings
    from core.local_only import admin_must_be_local

    get_settings.cache_clear()
    req = MagicMock()
    req.client.host = "198.51.100.10"
    admin_must_be_local(req)
    get_settings.cache_clear()


def test_admin_allow_remote_ignored_in_final_production(monkeypatch):
    monkeypatch.setenv("DIOMIKA_ENV", "production")
    monkeypatch.delenv("DIOMIKA_BETA", raising=False)
    monkeypatch.setenv("ADMIN_ALLOW_REMOTE", "1")
    from core.config import get_settings
    from core.local_only import admin_must_be_local

    get_settings.cache_clear()
    req = MagicMock()
    req.client.host = "198.51.100.10"
    with pytest.raises(HTTPException) as exc:
        admin_must_be_local(req)
    assert exc.value.status_code == 403
    get_settings.cache_clear()
