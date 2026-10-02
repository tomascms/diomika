"""API versioning strategy (v1, v2, etc.)."""
import logging
from typing import Optional, Dict, List, Callable, Annotated
from enum import Enum
from functools import wraps

from fastapi import Header, HTTPException, Depends

logger = logging.getLogger("diomika-api")


class APIVersion(Enum):
    """API versions."""
    V1 = "v1"
    V2 = "v2"
    V3 = "v3"


class APIVersionConfig:
    """Configuration for API versions."""

    def __init__(self):
        self.versions: Dict[APIVersion, VersionInfo] = {}
        self.default_version = APIVersion.V1

    def register_version(
        self,
        version: APIVersion,
        title: str,
        description: str,
        status: str = "stable",
        deprecated: bool = False,
        sunset_date: Optional[str] = None,
    ):
        """Register an API version."""
        info = VersionInfo(
            version=version,
            title=title,
            description=description,
            status=status,
            deprecated=deprecated,
            sunset_date=sunset_date,
        )
        self.versions[version] = info
        logger.info(f"Registered API version {version.value}: {title}")

    def get_version_info(self, version: APIVersion) -> Optional["VersionInfo"]:
        """Get version info."""
        return self.versions.get(version)

    def is_version_supported(self, version: APIVersion) -> bool:
        """Check if version is supported."""
        info = self.versions.get(version)
        return info is not None and not info.deprecated

    def get_supported_versions(self) -> List[APIVersion]:
        """Get all supported versions."""
        return [v for v in self.versions.keys() if self.versions[v].status != "deprecated"]


class VersionInfo:
    """Information about an API version."""

    def __init__(
        self,
        version: APIVersion,
        title: str,
        description: str,
        status: str = "stable",
        deprecated: bool = False,
        sunset_date: Optional[str] = None,
    ):
        self.version = version
        self.title = title
        self.description = description
        self.status = status
        self.deprecated = deprecated
        self.sunset_date = sunset_date

    def to_dict(self) -> Dict:
        return {
            "version": self.version.value,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "deprecated": self.deprecated,
            "sunset_date": self.sunset_date,
        }


def get_api_version(
    x_api_version: Annotated[Optional[str], Header()] = None
) -> APIVersion:
    """Extract API version from request header or use default."""
    if not x_api_version:
        return config.default_version

    try:
        return APIVersion[x_api_version.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported API version: {x_api_version}"
        )


def require_version(required_version: APIVersion):
    """Dependency to require a specific API version."""
    def _require_version(
        x_api_version: Annotated[Optional[str], Header()] = None
    ) -> APIVersion:
        version = get_api_version(x_api_version)
        if version != required_version:
            raise HTTPException(
                status_code=400,
                detail=f"This endpoint requires API version {required_version.value}"
            )
        return version
    return _require_version


def version_handler(version: APIVersion):
    """Decorator to handle version-specific logic."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Add version to kwargs
            kwargs["api_version"] = version
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class VersionMigrationHelper:
    """Helper for handling API version migrations."""

    def __init__(self):
        self.transformers: Dict[tuple, Callable] = {}

    def register_transformer(
        self,
        from_version: APIVersion,
        to_version: APIVersion,
        transformer: Callable,
    ):
        """Register a data transformer between versions."""
        key = (from_version, to_version)
        self.transformers[key] = transformer
        logger.debug(f"Registered transformer from {from_version.value} to {to_version.value}")

    def transform(
        self,
        data: Dict,
        from_version: APIVersion,
        to_version: APIVersion,
    ) -> Dict:
        """Transform data between versions."""
        if from_version == to_version:
            return data

        key = (from_version, to_version)
        transformer = self.transformers.get(key)

        if not transformer:
            logger.warning(f"No transformer found for {from_version.value} -> {to_version.value}")
            return data

        return transformer(data)


class ResponseVersioningMiddleware:
    """Middleware to handle response versioning."""

    def __init__(self, config: APIVersionConfig):
        self.config = config

    async def __call__(self, scope, receive, send):
        """ASGI middleware for response versioning."""
        if scope["type"] != "http":
            await send(scope)
            return

        # Extract version from headers
        headers = dict(scope.get("headers", []))
        version_header = headers.get(b"x-api-version", b"v1").decode()

        try:
            version = APIVersion[version_header.upper()]
        except KeyError:
            version = self.config.default_version

        # Store version in scope
        scope["api_version"] = version

        # Add version to response headers
        async def send_with_version(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-api-version", version.value.encode()))
                message["headers"] = headers

            await send(message)

        await send_with_version(scope)


class DeprecationWarning:
    """Deprecation warning for endpoints."""

    def __init__(self, deprecated_version: APIVersion, sunset_date: str, replacement: Optional[str] = None):
        self.deprecated_version = deprecated_version
        self.sunset_date = sunset_date
        self.replacement = replacement

    def to_header(self) -> str:
        """Convert to Deprecation header."""
        parts = [f'version={self.deprecated_version.value}']
        parts.append(f'sunset="{self.sunset_date}"')
        if self.replacement:
            parts.append(f'link="{self.replacement}"')
        return "; ".join(parts)


# Version changelog
CHANGELOG = {
    APIVersion.V1: {
        "released": "2024-01-01",
        "status": "stable",
        "features": [
            "Basic CRUD operations",
            "Authentication",
            "Rate limiting",
        ],
    },
    APIVersion.V2: {
        "released": "2024-06-01",
        "status": "stable",
        "features": [
            "Improved error handling",
            "Webhook support",
            "Advanced filtering",
            "Batch operations",
        ],
        "breaking_changes": [
            "Removed deprecated endpoints",
            "Changed response format",
        ],
    },
    APIVersion.V3: {
        "released": "2024-09-01",
        "status": "beta",
        "features": [
            "GraphQL support",
            "Real-time updates",
            "Advanced analytics",
            "Custom fields",
        ],
        "breaking_changes": [
            "Changed authentication flow",
        ],
    },
}


# Global configuration
config = APIVersionConfig()

# Register default versions
config.register_version(
    APIVersion.V1,
    "API v1",
    "Original API version - stable",
    status="stable",
)

config.register_version(
    APIVersion.V2,
    "API v2",
    "Enhanced API with better features - stable",
    status="stable",
)

config.register_version(
    APIVersion.V3,
    "API v3",
    "Next-generation API - beta",
    status="beta",
)


def get_api_version_config() -> APIVersionConfig:
    """Get global API version config."""
    return config
