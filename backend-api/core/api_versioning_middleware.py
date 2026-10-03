"""API Versioning middleware — X-API-Version header support."""
import logging
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("diomika-api")


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Handle API version negotiation via X-API-Version header.

    Supported versions:
    - 1.0: Legacy (deprecated, sunset date 2026-12-01)
    - 2.0: Current (stable)
    - 3.0: Beta (new features, breaking changes)
    """

    CURRENT_VERSION = "2.0"
    SUPPORTED_VERSIONS = {"1.0", "2.0", "3.0"}
    DEPRECATED_VERSIONS = {"1.0"}
    VERSION_SUNSET_DATES = {
        "1.0": "2026-12-01",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with version negotiation."""
        # Get requested version from header (default to current)
        requested_version = request.headers.get("X-API-Version", self.CURRENT_VERSION).strip()

        # Validate version
        if requested_version not in self.SUPPORTED_VERSIONS:
            return Response(
                content=f"Unsupported API version: {requested_version}. Supported: {', '.join(sorted(self.SUPPORTED_VERSIONS))}",
                status_code=400,
                headers={"X-API-Version": self.CURRENT_VERSION},
            )

        # Warn if deprecated
        if requested_version in self.DEPRECATED_VERSIONS:
            sunset_date = self.VERSION_SUNSET_DATES.get(requested_version, "unknown")
            logger.warning(
                f"[DEPRECATED_API] Client using version {requested_version} "
                f"(sunset: {sunset_date}). Request: {request.method} {request.url.path}"
            )

        # Store version in request state para uso downstream
        request.state.api_version = requested_version

        # Call next middleware/route
        response = await call_next(request)

        # Add version info to response
        response.headers["X-API-Version"] = self.CURRENT_VERSION
        response.headers["X-API-Version-Requested"] = requested_version

        if requested_version in self.DEPRECATED_VERSIONS:
            sunset_date = self.VERSION_SUNSET_DATES.get(requested_version)
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = sunset_date or ""
            response.headers["Warning"] = f'299 - "API version {requested_version} is deprecated, sunset {sunset_date}"'

        return response


class VersionedEndpoint:
    """Decorator para versioned endpoints."""

    def __init__(self, min_version: str = "1.0", max_version: Optional[str] = None):
        self.min_version = min_version
        self.max_version = max_version or "3.0"

    def __call__(self, func):
        """Wrap endpoint function com version checking."""
        async def wrapper(request: Request, *args, **kwargs):
            version = getattr(request.state, "api_version", APIVersionMiddleware.CURRENT_VERSION)

            # Simple version string comparison (assumes semver)
            if not self._is_version_in_range(version):
                return Response(
                    content=f"Endpoint not available in API version {version}",
                    status_code=400,
                )

            return await func(request, *args, **kwargs) if asyncio.iscoroutinefunction(func) else func(request, *args, **kwargs)

        return wrapper

    def _is_version_in_range(self, version: str) -> bool:
        """Check if version is within min/max range."""
        # Simplified: just string comparison
        return self.min_version <= version <= self.max_version


import asyncio


# Example usage em routes:
# @router.get("/catalog")
# @VersionedEndpoint(min_version="1.0")
# async def get_catalog(request: Request):
#     version = request.state.api_version
#     # Handle version-specific logic
#     ...
