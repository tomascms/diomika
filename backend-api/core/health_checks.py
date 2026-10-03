"""Detailed system health monitoring beyond basic endpoints."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger("diomika-api")


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Types of system components."""
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    EXTERNAL_API = "external_api"
    STORAGE = "storage"
    MEMORY = "memory"
    DISK = "disk"
    CPU = "cpu"
    NETWORK = "network"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    component_type: ComponentType
    status: HealthStatus
    response_time_ms: float = 0.0
    last_check: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    details: dict = field(default_factory=dict)
    check_count: int = 0
    failure_count: int = 0

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        if self.check_count == 0:
            return 0.0
        return (self.failure_count / self.check_count) * 100

    @property
    def is_critical(self) -> bool:
        """Check if component failure is critical."""
        return self.status == HealthStatus.UNHEALTHY and self.component_type in [
            ComponentType.DATABASE,
            ComponentType.QUEUE,
        ]


@dataclass
class SystemHealth:
    """Overall system health status."""
    overall_status: HealthStatus
    timestamp: datetime = field(default_factory=datetime.utcnow)
    components: dict[str, ComponentHealth] = field(default_factory=dict)
    uptime_seconds: int = 0
    request_count: int = 0
    error_count: int = 0
    average_response_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    database_query_time_p95: float = 0.0

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self.request_count == 0:
            return 0.0
        return (self.error_count / self.request_count) * 100

    @property
    def critical_issues(self) -> list[ComponentHealth]:
        """Get list of critical component issues."""
        return [c for c in self.components.values() if c.is_critical]

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "overall_status": self.overall_status.value,
            "timestamp": self.timestamp.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "metrics": {
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": f"{self.error_rate:.2f}%",
                "average_response_time_ms": self.average_response_time_ms,
                "cache_hit_rate": f"{self.cache_hit_rate:.2f}%",
                "database_query_time_p95": self.database_query_time_p95,
            },
            "components": {
                name: {
                    "status": comp.status.value,
                    "response_time_ms": comp.response_time_ms,
                    "last_check": comp.last_check.isoformat(),
                    "error_message": comp.error_message,
                    "failure_rate": f"{comp.failure_rate:.2f}%",
                    "details": comp.details,
                }
                for name, comp in self.components.items()
            },
            "critical_issues": len(self.critical_issues),
        }


class HealthCheckRunner:
    """Run health checks on system components."""

    def __init__(self):
        self.components: dict[str, ComponentHealth] = {}
        self.check_history: dict[str, list[HealthStatus]] = {}
        self.start_time = datetime.utcnow()
        self.request_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        self.cache_hits = 0
        self.cache_misses = 0
        self.query_times: list[float] = []

    def register_component(
        self,
        name: str,
        component_type: ComponentType,
    ) -> None:
        """Register a component for health checking."""
        self.components[name] = ComponentHealth(
            name=name,
            component_type=component_type,
            status=HealthStatus.UNKNOWN,
        )
        self.check_history[name] = []

    async def check_database(
        self,
        name: str = "primary_db",
        query_timeout: float = 5.0,
    ) -> ComponentHealth:
        """Check database health."""
        if name not in self.components:
            self.register_component(name, ComponentType.DATABASE)

        component = self.components[name]
        start = asyncio.get_event_loop().time()

        try:
            # Simulate database connection check
            await asyncio.sleep(0.01)  # Placeholder for actual query
            component.status = HealthStatus.HEALTHY
            component.response_time_ms = (asyncio.get_event_loop().time() - start) * 1000
            component.error_message = None
            component.failure_count = max(0, component.failure_count - 1)
        except Exception as e:
            component.status = HealthStatus.UNHEALTHY
            component.error_message = str(e)
            component.failure_count += 1

        component.last_check = datetime.utcnow()
        component.check_count += 1
        self.check_history[name].append(component.status)

        return component

    async def check_cache(
        self,
        name: str = "redis_cache",
    ) -> ComponentHealth:
        """Check cache health."""
        if name not in self.components:
            self.register_component(name, ComponentType.CACHE)

        component = self.components[name]
        start = asyncio.get_event_loop().time()

        try:
            # Simulate cache connection check
            await asyncio.sleep(0.005)  # Placeholder for actual check
            component.status = HealthStatus.HEALTHY
            component.response_time_ms = (asyncio.get_event_loop().time() - start) * 1000
            component.error_message = None
        except Exception as e:
            component.status = HealthStatus.DEGRADED
            component.error_message = str(e)
            component.failure_count += 1

        component.last_check = datetime.utcnow()
        component.check_count += 1
        self.check_history[name].append(component.status)

        return component

    async def check_all(self) -> SystemHealth:
        """Run all registered health checks."""
        tasks = []

        for name, component in self.components.items():
            if component.component_type == ComponentType.DATABASE:
                tasks.append(self.check_database(name))
            elif component.component_type == ComponentType.CACHE:
                tasks.append(self.check_cache(name))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return self.get_system_health()

    def get_system_health(self) -> SystemHealth:
        """Get overall system health status."""
        unhealthy_critical = sum(
            1 for c in self.components.values() if c.is_critical
        )

        if unhealthy_critical > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.UNHEALTHY for c in self.components.values()):
            overall_status = HealthStatus.DEGRADED
        elif all(c.status == HealthStatus.HEALTHY for c in self.components.values()):
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN

        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        avg_response_time = (
            self.total_response_time / self.request_count
            if self.request_count > 0
            else 0.0
        )
        cache_hit_rate = (
            (self.cache_hits / (self.cache_hits + self.cache_misses) * 100)
            if (self.cache_hits + self.cache_misses) > 0
            else 0.0
        )
        db_query_p95 = self._calculate_percentile(self.query_times, 95)

        return SystemHealth(
            overall_status=overall_status,
            components=self.components,
            uptime_seconds=int(uptime),
            request_count=self.request_count,
            error_count=self.error_count,
            average_response_time_ms=avg_response_time,
            cache_hit_rate=cache_hit_rate,
            database_query_time_p95=db_query_p95,
        )

    @staticmethod
    def _calculate_percentile(values: list[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = (percentile / 100) * len(sorted_values)
        if index >= len(sorted_values):
            return sorted_values[-1]
        return sorted_values[int(index)]

    def record_request(self, response_time_ms: float, is_error: bool = False):
        """Record API request metrics."""
        self.request_count += 1
        self.total_response_time += response_time_ms
        if is_error:
            self.error_count += 1

    def record_cache_hit(self):
        """Record cache hit."""
        self.cache_hits += 1

    def record_cache_miss(self):
        """Record cache miss."""
        self.cache_misses += 1

    def record_query_time(self, query_time_ms: float):
        """Record database query time."""
        self.query_times.append(query_time_ms)
        # Keep only last 1000 measurements
        if len(self.query_times) > 1000:
            self.query_times = self.query_times[-1000:]


class HealthCheckMiddleware:
    """Middleware to track health metrics."""

    def __init__(self, app, health_runner: HealthCheckRunner):
        self.app = app
        self.health_runner = health_runner

    async def __call__(self, request, call_next):
        import time
        start = time.time()
        response = await call_next(request)
        elapsed_ms = (time.time() - start) * 1000

        is_error = response.status_code >= 400
        self.health_runner.record_request(elapsed_ms, is_error)

        return response


class HealthEndpointHandler:
    """Handle health check endpoints."""

    def __init__(self, health_runner: HealthCheckRunner):
        self.health_runner = health_runner

    async def health(self) -> dict:
        """Basic health check."""
        health = self.health_runner.get_system_health()
        return health.to_dict()

    async def health_detailed(self) -> dict:
        """Detailed health check with component checks."""
        await self.health_runner.check_all()
        health = self.health_runner.get_system_health()
        return health.to_dict()

    async def health_ready(self) -> dict:
        """Readiness probe for Kubernetes."""
        health = self.health_runner.get_system_health()
        if health.overall_status == HealthStatus.HEALTHY:
            return {"ready": True, "status": "ready"}
        else:
            return {"ready": False, "status": health.overall_status.value}

    async def health_live(self) -> dict:
        """Liveness probe for Kubernetes."""
        health = self.health_runner.get_system_health()
        # System is considered live if not critically unhealthy
        is_live = not health.critical_issues
        return {"live": is_live, "status": health.overall_status.value}
