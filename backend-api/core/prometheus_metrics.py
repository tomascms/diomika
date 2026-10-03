"""Prometheus metrics export."""
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass
import time

logger = logging.getLogger("diomika-api")


class MetricType:
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricLabel:
    """Metric label."""
    name: str
    value: str


class Metric:
    """Base metric."""

    def __init__(self, name: str, description: str, metric_type: str, labels: Optional[List[MetricLabel]] = None):
        self.name = name
        self.description = description
        self.metric_type = metric_type
        self.labels = labels or []
        self.value: float = 0
        self.created_at = datetime.utcnow()

    def get_prometheus_line(self) -> str:
        """Get Prometheus format line."""
        label_str = ""
        if self.labels:
            label_pairs = [f'{label.name}="{label.value}"' for label in self.labels]
            label_str = f'{{{",".join(label_pairs)}}}'

        return f"{self.name}{label_str} {self.value}"

    def __str__(self) -> str:
        return self.get_prometheus_line()


class Counter(Metric):
    """Counter metric - monotonically increasing."""

    def __init__(self, name: str, description: str, labels: Optional[List[MetricLabel]] = None):
        super().__init__(name, description, MetricType.COUNTER, labels)

    def increment(self, amount: float = 1):
        """Increment counter."""
        self.value += amount


class Gauge(Metric):
    """Gauge metric - can go up or down."""

    def __init__(self, name: str, description: str, labels: Optional[List[MetricLabel]] = None):
        super().__init__(name, description, MetricType.GAUGE, labels)

    def set(self, value: float):
        """Set gauge value."""
        self.value = value

    def increment(self, amount: float = 1):
        """Increment gauge."""
        self.value += amount

    def decrement(self, amount: float = 1):
        """Decrement gauge."""
        self.value -= amount


class Histogram(Metric):
    """Histogram metric - measures distribution of values."""

    def __init__(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        labels: Optional[List[MetricLabel]] = None,
    ):
        super().__init__(name, description, MetricType.HISTOGRAM, labels)
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self.observations: List[float] = []
        self.sum = 0.0

    def observe(self, value: float):
        """Record an observation."""
        self.observations.append(value)
        self.sum += value

    def get_prometheus_lines(self) -> List[str]:
        """Get Prometheus format lines."""
        lines = []
        count = len(self.observations)

        # Bucket lines
        for bucket in self.buckets:
            bucket_count = sum(1 for o in self.observations if o <= bucket)
            lines.append(f'{self.name}_bucket{{le="{bucket}"}} {bucket_count}')

        # Sum line
        lines.append(f'{self.name}_sum {self.sum}')

        # Count line
        lines.append(f'{self.name}_count {count}')

        return lines


class Summary(Metric):
    """Summary metric - like histogram but for summary statistics."""

    def __init__(
        self,
        name: str,
        description: str,
        quantiles: Optional[List[float]] = None,
        labels: Optional[List[MetricLabel]] = None,
    ):
        super().__init__(name, description, MetricType.SUMMARY, labels)
        self.quantiles = quantiles or [0.5, 0.9, 0.95, 0.99]
        self.observations: List[float] = []
        self.sum = 0.0

    def observe(self, value: float):
        """Record an observation."""
        self.observations.append(value)
        self.sum += value

    def get_prometheus_lines(self) -> List[str]:
        """Get Prometheus format lines."""
        lines = []
        count = len(self.observations)

        if count > 0:
            sorted_obs = sorted(self.observations)
            for quantile in self.quantiles:
                idx = int(quantile * (count - 1))
                lines.append(f'{self.name}{{quantile="{quantile}"}} {sorted_obs[idx]}')

        # Sum and count
        lines.append(f'{self.name}_sum {self.sum}')
        lines.append(f'{self.name}_count {count}')

        return lines


class MetricsRegistry:
    """Registry for Prometheus metrics."""

    def __init__(self):
        self.metrics: Dict[str, Metric] = {}

    def register_counter(self, name: str, description: str) -> Counter:
        """Register a counter metric."""
        counter = Counter(name, description)
        self.metrics[name] = counter
        logger.debug(f"Registered counter: {name}")
        return counter

    def register_gauge(self, name: str, description: str) -> Gauge:
        """Register a gauge metric."""
        gauge = Gauge(name, description)
        self.metrics[name] = gauge
        logger.debug(f"Registered gauge: {name}")
        return gauge

    def register_histogram(self, name: str, description: str, buckets: Optional[List[float]] = None) -> Histogram:
        """Register a histogram metric."""
        histogram = Histogram(name, description, buckets)
        self.metrics[name] = histogram
        logger.debug(f"Registered histogram: {name}")
        return histogram

    def register_summary(self, name: str, description: str) -> Summary:
        """Register a summary metric."""
        summary = Summary(name, description)
        self.metrics[name] = summary
        logger.debug(f"Registered summary: {name}")
        return summary

    def get_metric(self, name: str) -> Optional[Metric]:
        """Get a metric by name."""
        return self.metrics.get(name)

    def export_prometheus_format(self) -> str:
        """Export all metrics in Prometheus format."""
        lines = []

        for metric in self.metrics.values():
            # Add help line
            lines.append(f"# HELP {metric.name} {metric.description}")
            # Add type line
            lines.append(f"# TYPE {metric.name} {metric.metric_type}")

            # Add metric values
            if isinstance(metric, (Histogram, Summary)):
                lines.extend(metric.get_prometheus_lines())
            else:
                lines.append(str(metric))

        return "\n".join(lines) + "\n"


class ApplicationMetrics:
    """Application-level metrics."""

    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

        # HTTP metrics
        self.http_requests_total = registry.register_counter(
            "http_requests_total",
            "Total HTTP requests"
        )
        self.http_request_duration_seconds = registry.register_histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds"
        )
        self.http_response_size_bytes = registry.register_histogram(
            "http_response_size_bytes",
            "HTTP response size in bytes"
        )

        # Database metrics
        self.db_queries_total = registry.register_counter(
            "db_queries_total",
            "Total database queries"
        )
        self.db_query_duration_seconds = registry.register_histogram(
            "db_query_duration_seconds",
            "Database query duration in seconds"
        )
        self.db_connections_active = registry.register_gauge(
            "db_connections_active",
            "Active database connections"
        )

        # Cache metrics
        self.cache_hits_total = registry.register_counter(
            "cache_hits_total",
            "Total cache hits"
        )
        self.cache_misses_total = registry.register_counter(
            "cache_misses_total",
            "Total cache misses"
        )

        # Job queue metrics
        self.job_queue_size = registry.register_gauge(
            "job_queue_size",
            "Number of jobs in queue"
        )
        self.job_processing_duration_seconds = registry.register_histogram(
            "job_processing_duration_seconds",
            "Job processing duration in seconds"
        )

        # Error metrics
        self.errors_total = registry.register_counter(
            "errors_total",
            "Total errors"
        )

    def record_http_request(self, method: str, path: str, duration_seconds: float, status_code: int):
        """Record HTTP request."""
        self.http_requests_total.increment()
        self.http_request_duration_seconds.observe(duration_seconds)

    def record_database_query(self, query_type: str, duration_seconds: float):
        """Record database query."""
        self.db_queries_total.increment()
        self.db_query_duration_seconds.observe(duration_seconds)

    def record_cache_hit(self):
        """Record cache hit."""
        self.cache_hits_total.increment()

    def record_cache_miss(self):
        """Record cache miss."""
        self.cache_misses_total.increment()

    def record_job_processing(self, duration_seconds: float):
        """Record job processing time."""
        self.job_processing_duration_seconds.observe(duration_seconds)

    def record_error(self, error_type: str):
        """Record error."""
        self.errors_total.increment()


# Global registry
_registry: Optional[MetricsRegistry] = None
_app_metrics: Optional[ApplicationMetrics] = None


def get_metrics_registry() -> MetricsRegistry:
    """Get global metrics registry."""
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


def get_application_metrics() -> ApplicationMetrics:
    """Get global application metrics."""
    global _app_metrics
    if _app_metrics is None:
        registry = get_metrics_registry()
        _app_metrics = ApplicationMetrics(registry)
    return _app_metrics
