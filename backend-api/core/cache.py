"""Cache partilhado (Redis) com fallback in-process por worker."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Callable, TypeVar

from core.redis_client import get_redis, redis_available

logger = logging.getLogger("diomika-api")

T = TypeVar("T")

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}
_REDIS_PREFIX = "diomika:cache:"
_hits = 0
_misses = 0


def catalog_cache_ttl() -> int:
    return max(60, int(os.getenv("CATALOG_CACHE_TTL", "3600")))


def cache_backend() -> str:
    return "redis" if redis_available() else "memory"


def cache_stats() -> dict[str, int | str]:
    return {"backend": cache_backend(), "hits": _hits, "misses": _misses}


def _redis_key(key: str) -> str:
    return f"{_REDIS_PREFIX}{key}"


def _memory_get(key: str) -> Any | None:
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if entry and entry[0] > now:
            return entry[1]
    return None


def _memory_set(key: str, value: Any, ttl_seconds: float) -> None:
    expires = time.monotonic() + ttl_seconds
    with _lock:
        _store[key] = (expires, value)
        if len(_store) > 4000:
            _purge_memory(time.monotonic())


def get_or_set(key: str, ttl_seconds: float, factory: Callable[[], T]) -> T:
    global _hits, _misses

    client = get_redis()
    if client is not None:
        rkey = _redis_key(key)
        try:
            raw = client.get(rkey)
            if raw is not None:
                _hits += 1
                return json.loads(raw)
        except Exception as exc:
            logger.debug("Redis cache read falhou (%s): %s", key, exc)

    cached = _memory_get(key)
    if cached is not None:
        _hits += 1
        return cached  # type: ignore[return-value]

    _misses += 1
    value = factory()

    if client is not None:
        try:
            client.setex(rkey, max(1, int(ttl_seconds)), json.dumps(value, default=str))
        except Exception as exc:
            logger.debug("Redis cache write falhou (%s): %s", key, exc)

    _memory_set(key, value, ttl_seconds)
    return value


def invalidate_key(key: str) -> int:
    count = 0
    client = get_redis()
    if client is not None:
        try:
            count += int(client.delete(_redis_key(key)))
        except Exception:
            pass
    with _lock:
        if key in _store:
            del _store[key]
            count += 1
    return count


def invalidate_prefix(prefix: str) -> int:
    count = 0
    client = get_redis()
    if client is not None:
        pattern = f"{_REDIS_PREFIX}{prefix}*"
        try:
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor=cursor, match=pattern, count=200)
                if keys:
                    count += client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.debug("Redis invalidate_prefix falhou (%s): %s", prefix, exc)

    with _lock:
        keys = [k for k in _store if k.startswith(prefix)]
        for k in keys:
            del _store[k]
        count += len(keys)
    return count


def _purge_memory(now: float) -> None:
    expired = [k for k, (exp, _) in _store.items() if exp <= now]
    for k in expired:
        del _store[k]
    if len(_store) > 3000:
        for k in list(_store.keys())[: len(_store) - 2000]:
            del _store[k]


def invalidate_catalog_change(
    *,
    table_name: str | None = None,
    record: dict | None = None,
    record_id: str | None = None,
) -> None:
    """Invalidação cirúrgica após writes admin — limpa listas/modelos afectados."""
    from core.database import get_db
    from models.catalog_registry import (
        CATALOG_TYPES,
        all_model_tables,
        all_product_tables,
        model_table_for_tipo,
        tipo_for_table,
    )
    from models.schemas import CATEGORY_DEFINITIONS

    invalidate_prefix("admin:merged:")
    invalidate_key("catalog:meta")

    if not table_name:
        invalidate_prefix("categories:")
        invalidate_prefix("catalog:")
        return

    db = get_db()
    row = dict(record or {})
    rid = str(record_id or row.get("id") or "").strip()

    def _virtual_tipos(physical: str) -> list[str]:
        out: list[str] = []
        for definition in CATEGORY_DEFINITIONS.values():
            agg = definition.get("aggregated_tipos") or []
            if physical in agg:
                virtual = definition.get("tipo_catalogo")
                if virtual:
                    out.append(str(virtual))
        return out

    def _invalidate_listings(tipo: str | None, id_categoria: str | None) -> None:
        if not tipo or not id_categoria:
            return
        invalidate_prefix(f"catalog:list:{tipo}:{id_categoria}")
        for virtual in _virtual_tipos(tipo):
            invalidate_prefix(f"catalog:list:{virtual}:{id_categoria}")

    def _invalidate_model(tipo: str | None, id_modelo: str | None) -> None:
        if not id_modelo:
            return
        invalidate_key(f"catalog:modelo-auto:{id_modelo}")
        invalidate_prefix("catalog:modelo-slug:")
        if tipo:
            invalidate_key(f"catalog:modelo:{tipo}:{id_modelo}")

    if table_name == "categories":
        invalidate_prefix("categories:")
        invalidate_prefix("catalog:list:")
        if rid:
            invalidate_prefix(f"catalog:list:")
        return

    tipo = tipo_for_table(table_name)
    mt = model_table_for_tipo(tipo) if tipo else None

    if table_name in all_model_tables():
        id_categoria = str(row.get("id_categoria") or "").strip()
        if not id_categoria and rid:
            fetched = db.table(table_name).select("id_categoria").eq("id", rid).limit(1).execute().data
            id_categoria = str((fetched or [{}])[0].get("id_categoria") or "")
        _invalidate_listings(tipo, id_categoria or None)
        _invalidate_model(tipo, rid or None)
        return

    if table_name in all_product_tables() or table_name in {cfg.get("colors_table") for cfg in CATALOG_TYPES.values()}:
        id_modelo = str(row.get("id_modelo") or "").strip()
        if not id_modelo and rid:
            fetched = db.table(table_name).select("id_modelo").eq("id", rid).limit(1).execute().data
            id_modelo = str((fetched or [{}])[0].get("id_modelo") or "")
        if id_modelo and not mt:
            for t, cfg in CATALOG_TYPES.items():
                if table_name in (cfg["product_table"], cfg.get("colors_table")):
                    tipo = t
                    mt = cfg["model_table"]
                    break
        id_categoria = ""
        if mt and id_modelo:
            fetched = db.table(mt).select("id_categoria").eq("id", id_modelo).limit(1).execute().data
            id_categoria = str((fetched or [{}])[0].get("id_categoria") or "")
            _invalidate_model(tipo, id_modelo)
        _invalidate_listings(tipo, id_categoria or None)
        return

    invalidate_prefix("catalog:")
