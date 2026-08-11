"""Cache TTL in-process — catálogo read-heavy (por worker/replica)."""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def catalog_cache_ttl() -> int:
    return max(15, int(os.getenv("CATALOG_CACHE_TTL", "60")))


def get_or_set(key: str, ttl_seconds: float, factory: Callable[[], T]) -> T:
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if entry and entry[0] > now:
            return entry[1]  # type: ignore[return-value]

    value = factory()
    expires = now + ttl_seconds
    with _lock:
        _store[key] = (expires, value)
        if len(_store) > 4000:
            _purge(now)
    return value


def invalidate_prefix(prefix: str) -> int:
    with _lock:
        keys = [k for k in _store if k.startswith(prefix)]
        for k in keys:
            del _store[k]
        return len(keys)


def _purge(now: float) -> None:
    expired = [k for k, (exp, _) in _store.items() if exp <= now]
    for k in expired:
        del _store[k]
    if len(_store) > 3000:
        for k in list(_store.keys())[: len(_store) - 2000]:
            del _store[k]
