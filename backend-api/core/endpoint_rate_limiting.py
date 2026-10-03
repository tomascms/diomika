"""Per-endpoint rate limiting."""
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from functools import wraps
import asyncio

from fastapi import HTTPException, Request, Depends
from core.cache import get_redis

logger = logging.getLogger("diomika-api")


@dataclass
class RateLimitConfig:
    """Rate limit configuration for an endpoint."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: Optional[int] = None
    key_func: Optional[callable] = None  # Custom key extractor


class RateLimiter:
    """Per-endpoint rate limiting with Redis."""

    def __init__(self):
        self.redis = None
        self.configs: Dict[str, RateLimitConfig] = {}

    async def initialize(self):
        """Initialize Redis connection."""
        self.redis = await get_redis()

    def register_endpoint(self, endpoint_key: str, config: RateLimitConfig):
        """Register rate limit config for an endpoint."""
        self.configs[endpoint_key] = config
        logger.debug(f"Registered rate limit for {endpoint_key}: {config.requests_per_minute}/min, {config.requests_per_hour}/h, {config.requests_per_day}/d")

    async def check_rate_limit(
        self,
        endpoint_key: str,
        identifier: str,  # user_id, IP, etc.
    ) -> Tuple[bool, Dict[str, int]]:
        """Check if request is within rate limits."""
        config = self.configs.get(endpoint_key)
        if not config:
            return True, {}

        limits = {
            "minute": config.requests_per_minute,
            "hour": config.requests_per_hour,
            "day": config.requests_per_day,
        }

        now = datetime.utcnow()
        checks = {
            "minute": (60, config.requests_per_minute),
            "hour": (3600, config.requests_per_hour),
            "day": (86400, config.requests_per_day),
        }

        remaining = {}
        for window_name, (window_seconds, limit) in checks.items():
            key = f"rate_limit:{endpoint_key}:{identifier}:{window_name}"

            # Get current count
            current = await self.redis.get(key) or "0"
            current_count = int(current)

            if current_count >= limit:
                return False, remaining

            # Increment counter
            await self.redis.incr(key)
            await self.redis.expire(key, window_seconds)

            remaining[window_name] = limit - current_count - 1

        return True, remaining

    async def get_limit_status(
        self,
        endpoint_key: str,
        identifier: str,
    ) -> Dict[str, Dict]:
        """Get current limit status for an identifier."""
        config = self.configs.get(endpoint_key)
        if not config:
            return {}

        status = {}
        windows = {
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }

        for window_name, window_seconds in windows.items():
            key = f"rate_limit:{endpoint_key}:{identifier}:{window_name}"
            current = await self.redis.get(key) or "0"
            current_count = int(current)

            limit = getattr(config, f"requests_per_{window_name}", 0)
            remaining = max(0, limit - current_count)

            status[window_name] = {
                "limit": limit,
                "remaining": remaining,
                "reset_in_seconds": await self.redis.ttl(key) or 0,
            }

        return status

    def create_rate_limit_decorator(self, endpoint_key: str, config: RateLimitConfig):
        """Create a decorator for rate limiting an endpoint."""
        self.register_endpoint(endpoint_key, config)

        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                # Extract identifier
                if config.key_func:
                    identifier = config.key_func(request)
                else:
                    # Default: use user_id or IP
                    identifier = getattr(request.state, "user_id", None) or request.client.host

                # Check rate limit
                allowed, remaining = await self.check_rate_limit(endpoint_key, identifier)

                if not allowed:
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded",
                        headers={
                            "Retry-After": "60",
                        },
                    )

                # Add remaining info to headers
                request.state.rate_limit_remaining = remaining

                return await func(request, *args, **kwargs)

            return wrapper
        return decorator


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts limits based on system load."""

    def __init__(self):
        super().__init__()
        self.load_factors: Dict[str, float] = {}

    async def update_load_factor(self, endpoint_key: str, factor: float):
        """Update load factor for an endpoint (0.5 = half capacity, 2.0 = double)."""
        self.load_factors[endpoint_key] = factor
        logger.debug(f"Updated load factor for {endpoint_key}: {factor}")

    async def check_rate_limit_adaptive(
        self,
        endpoint_key: str,
        identifier: str,
    ) -> Tuple[bool, Dict[str, int]]:
        """Check rate limit with adaptive factors."""
        config = self.configs.get(endpoint_key)
        if not config:
            return True, {}

        # Apply load factor
        factor = self.load_factors.get(endpoint_key, 1.0)

        # Temporarily reduce limits
        adjusted_config = RateLimitConfig(
            requests_per_minute=int(config.requests_per_minute * factor),
            requests_per_hour=int(config.requests_per_hour * factor),
            requests_per_day=int(config.requests_per_day * factor),
            burst_size=config.burst_size,
            key_func=config.key_func,
        )

        # Swap config temporarily
        original = self.configs[endpoint_key]
        self.configs[endpoint_key] = adjusted_config

        try:
            return await self.check_rate_limit(endpoint_key, identifier)
        finally:
            self.configs[endpoint_key] = original


class RateLimitMiddleware:
    """Middleware to add rate limit headers to responses."""

    async def __call__(self, scope, receive, send):
        """ASGI middleware for rate limiting."""
        if scope["type"] != "http":
            await send(scope)
            return

        async def send_with_rate_limit_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                # Add rate limit headers if available
                if "rate_limit_remaining" in scope:
                    remaining = scope["rate_limit_remaining"]
                    if "minute" in remaining:
                        headers.append((
                            b"X-RateLimit-Remaining-Minute",
                            str(remaining["minute"]).encode()
                        ))
                    if "hour" in remaining:
                        headers.append((
                            b"X-RateLimit-Remaining-Hour",
                            str(remaining["hour"]).encode()
                        ))
                    if "day" in remaining:
                        headers.append((
                            b"X-RateLimit-Remaining-Day",
                            str(remaining["day"]).encode()
                        ))

                message["headers"] = headers

            await send(message)

        await send_with_rate_limit_headers(scope)


# Global limiter
_rate_limiter: Optional[RateLimiter] = None
_adaptive_limiter: Optional[AdaptiveRateLimiter] = None


async def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
        await _rate_limiter.initialize()
    return _rate_limiter


async def get_adaptive_rate_limiter() -> AdaptiveRateLimiter:
    """Get global adaptive rate limiter."""
    global _adaptive_limiter
    if _adaptive_limiter is None:
        _adaptive_limiter = AdaptiveRateLimiter()
        await _adaptive_limiter.initialize()
    return _adaptive_limiter


# Predefined rate limit configs
RATE_LIMITS = {
    "public": RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=500,
        requests_per_day=5000,
    ),
    "authenticated": RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=2000,
        requests_per_day=20000,
    ),
    "premium": RateLimitConfig(
        requests_per_minute=300,
        requests_per_hour=10000,
        requests_per_day=100000,
    ),
    "internal": RateLimitConfig(
        requests_per_minute=1000,
        requests_per_hour=100000,
        requests_per_day=1000000,
    ),
}
