"""Performance optimization strategies — caching, compression, query optimization."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Any, Callable

logger = logging.getLogger("diomika-api")


class ResponseCacheStrategy:
    """Smart response caching based on request/response type."""

    # Cache duration recommendations (seconds)
    CACHE_DURATIONS = {
        "catalog_list": 3600,           # 1 hour - catalog lists
        "catalog_detail": 1800,         # 30 min - individual products
        "category": 7200,               # 2 hours - categories (rarely change)
        "featured": 1800,               # 30 min - featured products
        "search": 300,                  # 5 min - search results
        "user_profile": 60,             # 1 min - user data (personalized)
        "health": 10,                   # 10 sec - health checks
        "static": 86400,                # 1 day - static assets (images, fonts)
    }

    @staticmethod
    def get_cache_duration(cache_key: str) -> int:
        """Determine cache duration based on key pattern."""
        for pattern, duration in ResponseCacheStrategy.CACHE_DURATIONS.items():
            if pattern in cache_key:
                return duration
        return 300  # Default 5 minutes

    @staticmethod
    def get_cache_headers(cache_key: str, is_public: bool = True) -> dict[str, str]:
        """Generate Cache-Control headers."""
        duration = ResponseCacheStrategy.get_cache_duration(cache_key)
        visibility = "public" if is_public else "private"
        return {
            "Cache-Control": f"{visibility}, max-age={duration}",
            "Expires": (datetime.utcnow() + timedelta(seconds=duration)).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            ),
        }


class QueryOptimization:
    """Query optimization guidelines and patterns."""

    # Maximum reasonable query complexity
    MAX_OFFSET = 10000
    MAX_LIMIT = 1000
    DEFAULT_LIMIT = 50

    # Recommended indexes
    RECOMMENDED_INDEXES = {
        "product_models": [
            "CREATE INDEX idx_tipo_catalogo ON product_models(tipo_catalogo)",
            "CREATE INDEX idx_id_categoria ON product_models(id_categoria)",
            "CREATE INDEX idx_visibilidade ON product_models(visibilidade)",
        ],
        "product_variants": [
            "CREATE INDEX idx_id_modelo ON product_variants(id_modelo)",
            "CREATE INDEX idx_ean ON product_variants(ean)",
        ],
        "product_model_colors": [
            "CREATE INDEX idx_id_modelo_color ON product_model_colors(id_modelo)",
            "CREATE INDEX idx_id_categoria_color ON product_model_colors(id_categoria)",
        ],
    }

    @staticmethod
    def validate_pagination(offset: int, limit: int) -> tuple[int, int]:
        """Validate and constrain pagination parameters."""
        offset = max(0, min(offset, QueryOptimization.MAX_OFFSET))
        limit = max(1, min(limit, QueryOptimization.MAX_LIMIT))
        return offset, limit

    @staticmethod
    def get_n_plus_one_prevention() -> dict[str, str]:
        """Return SQL patterns to prevent N+1 queries."""
        return {
            "description": "Always use JOINs instead of separate queries",
            "example_bad": "Loop through products and fetch model details in separate query",
            "example_good": "Single query with JOIN to models table",
        }


class DatabaseConnectionPooling:
    """Database connection pool optimization."""

    # Connection pool configuration
    POOL_CONFIG = {
        "min_size": 2,
        "max_size": 20,
        "timeout": 30,
        "recycle": 3600,  # Recycle connections every hour
        "echo": False,    # Set to True for debugging SQL
    }

    @staticmethod
    def get_pool_stats() -> dict[str, Any]:
        """Get connection pool statistics."""
        return {
            "min_connections": DatabaseConnectionPooling.POOL_CONFIG["min_size"],
            "max_connections": DatabaseConnectionPooling.POOL_CONFIG["max_size"],
            "recycle_interval_seconds": DatabaseConnectionPooling.POOL_CONFIG["recycle"],
            "status": "not_yet_implemented",
        }


class AssetOptimization:
    """Static asset optimization strategies."""

    # Asset compression recommendations
    COMPRESSION_TARGETS = {
        "jpg": {"quality": 80, "progressive": True},
        "png": {"quality": 80},
        "webp": {"quality": 80},  # Modern browsers
        "svg": {"remove_comments": True, "optimize": True},
        "css": {"minify": True, "purge_unused": True},
        "js": {"minify": True, "tree_shake": True},
        "fonts": {"subset": True, "woff2": True},  # Use modern formats
    }

    @staticmethod
    def get_image_transform_query(
        width: Optional[int] = None,
        height: Optional[int] = None,
        quality: int = 80,
        format: str = "auto",
    ) -> dict[str, Any]:
        """Build image transformation parameters for CDN."""
        return {
            "width": width,
            "height": height,
            "quality": quality,
            "format": format,  # auto uses best format per browser
            "fit": "cover",
        }


class RenderingOptimization:
    """Frontend rendering optimization strategies."""

    # Lazy loading configuration
    LAZY_LOAD_CONFIG = {
        "images": True,
        "native_lazy_load": True,
        "intersection_observer_threshold": 0.1,
    }

    # Code splitting recommendations
    CODE_SPLITTING = {
        "route_based": "Split by route/page",
        "component_based": "Split large components",
        "vendor_separate": "Keep vendor dependencies separate",
        "critical_path": "Prioritize above-fold content",
    }

    @staticmethod
    def get_bundle_size_targets() -> dict[str, str]:
        """Recommended bundle size targets (gzipped)."""
        return {
            "main_bundle": "< 150 KB",
            "vendor_bundle": "< 200 KB",
            "css": "< 50 KB",
            "total": "< 400 KB",
            "note": "Smaller bundles = faster initial load",
        }


class MetricsCollection:
    """Performance metrics to track."""

    CORE_WEB_VITALS = {
        "LCP": "Largest Contentful Paint (< 2.5s)",
        "FID": "First Input Delay (< 100ms)",
        "CLS": "Cumulative Layout Shift (< 0.1)",
    }

    PERFORMANCE_METRICS = {
        "time_to_first_byte": "TTFB (< 600ms)",
        "first_contentful_paint": "FCP (< 1.8s)",
        "time_to_interactive": "TTI (< 3.8s)",
        "total_blocking_time": "TBT (< 200ms)",
    }

    BACKEND_METRICS = {
        "api_response_time": "P95 < 200ms",
        "database_query_time": "P95 < 100ms",
        "cache_hit_rate": "> 80%",
        "error_rate": "< 0.1%",
    }

    @staticmethod
    def get_performance_checklist() -> list[str]:
        """Performance optimization checklist."""
        return [
            "✓ Enable gzip/brotli compression",
            "✓ CDN for static assets",
            "✓ Database query optimization (indexes, joins)",
            "✓ Connection pooling",
            "✓ Response caching strategy",
            "✓ Lazy loading for images",
            "✓ Code splitting (route/component based)",
            "✓ Image optimization (WebP, quality)",
            "✓ Minify CSS/JS",
            "✓ HTTP/2 or HTTP/3 enabled",
            "✓ Monitor Core Web Vitals",
            "✓ Regular lighthouse audits",
        ]
