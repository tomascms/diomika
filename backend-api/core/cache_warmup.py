"""Pré-aquece cache Redis após arranque — 1.º visitante não paga cold start."""
from __future__ import annotations

import logging

logger = logging.getLogger("diomika-api")


def warm_catalog_cache() -> None:
    from core.cache import catalog_cache_ttl, get_or_set
    from core.cqrs.queries.catalog import ListCategoriesQuery, list_categories
    from models.catalog_registry import catalog_metadata

    ttl = float(catalog_cache_ttl())
    try:
        get_or_set("categories:all", ttl, lambda: list_categories(ListCategoriesQuery()))
        get_or_set("catalog:meta", ttl, catalog_metadata)
        logger.info("Cache catálogo pré-aquecido (categories + meta, ttl=%ss)", int(ttl))
    except Exception as exc:
        logger.warning("Warm cache falhou (não crítico): %s", exc)
